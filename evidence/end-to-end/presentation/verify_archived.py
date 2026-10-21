"""Replay an experimental Results artifact with its archived source in a temp copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iteration", help="Archived live iteration number")
    parser.add_argument("case", help="Case name inside the iteration")
    args = parser.parse_args()
    iteration = ROOT / "iterations" / args.iteration
    archive = iteration / "results-source-snapshot.zip"
    receipt = json.loads((iteration / "source-snapshot.json").read_text())
    artifact = iteration / args.case / "artifact.json"
    answer = iteration / args.case / "answer.md"
    if digest(archive) != receipt["sha256"]:
        raise ValueError("archived Results source hash differs")
    with tempfile.TemporaryDirectory(prefix="results-archived-replay-") as temporary:
        temp = Path(temporary)
        shutil.copytree(REPO / "src", temp / "src")
        with zipfile.ZipFile(archive) as zipped:
            expected = set(receipt["files"])
            if set(zipped.namelist()) != expected:
                raise ValueError("archived Results file list differs")
            for name in expected:
                if hashlib.sha256(zipped.read(name)).hexdigest() != receipt["files"][name]:
                    raise ValueError(f"archived Results file hash differs: {name}")
            zipped.extractall(temp)
        script = (
            "from pathlib import Path\n"
            "from award_agent.results import ResultsArtifact, replay_results\n"
            f"artifact = ResultsArtifact.model_validate_json(Path({str(artifact)!r}).read_text())\n"
            f"expected = Path({str(answer)!r}).read_text()\n"
            "actual = replay_results(artifact)\n"
            "if actual != expected: raise ValueError('archived replay differs from answer.md')\n"
            "print('archived replay matches answer.md')\n"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(temp / "src")
        result = subprocess.run([sys.executable, "-c", script], cwd=REPO,
                                env=environment, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        print(result.stdout.strip())


if __name__ == "__main__":
    main()
