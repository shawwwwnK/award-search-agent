"""Run Results authoring only on saved Ranking exports; never invoke providers."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import zipfile
from pathlib import Path

from dotenv import load_dotenv

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig, replay_results, run_results
from award_agent.results.adapter import OpenAIResultsInputMeasurer, OpenAIResultsWriter


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
SOURCE = ROOT.parent / "2026-10-08-golden-diagnostic" / "early-2027" / "runs"
CASES = {
    "admitted": SOURCE / "mixed_award_cash_eligible" / "continuation-3",
    "conditional": SOURCE / "typo_recognizable_date" / "continuation-3",
    "incomplete": SOURCE / "ready_whole_month",
    "holiday_window": SOURCE / "ready_holiday_window" / "continuation-1",
    "home_airport": SOURCE / "default_award_home_airport_not_return",
    "early_month": SOURCE / "ready_early_month",
}
INITIAL_COHORT = ("admitted", "conditional", "incomplete")
VERSION = "results-artifact-v4"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as output:
        output.write(content)


def ensure_source_snapshot(iteration: Path) -> None:
    files = sorted((REPO / "src" / "award_agent" / "results").glob("*.py"))
    archive_path = iteration / "results-source-snapshot.zip"
    receipt_path = iteration / "source-snapshot.json"
    hashes = {str(path.relative_to(REPO)): digest(path) for path in files}
    if archive_path.exists() or receipt_path.exists():
        if not (archive_path.exists() and receipt_path.exists()):
            raise ValueError("partial source snapshot exists")
        receipt = json.loads(receipt_path.read_text())
        if receipt["files"] != hashes or receipt["sha256"] != digest(archive_path):
            raise ValueError("Results source differs from this iteration's snapshot")
        return
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, str(path.relative_to(REPO)))
    receipt = {"sha256": digest(archive_path), "files": hashes,
               "dependencies": {name: importlib.metadata.version(name)
                                for name in ("pydantic", "openai", "python-dotenv")}}
    write_new(receipt_path, json.dumps(receipt, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iteration", help="New immutable iteration directory")
    parser.add_argument("--case", choices=tuple(CASES), action="append",
                        help="Run only selected cases; otherwise run all three")
    parser.add_argument("--config", type=Path, required=True,
                        help="Saved explicit ResultsConfig, including guidance")
    args = parser.parse_args()
    selected = args.case or list(INITIAL_COHORT)
    iteration = ROOT / "iterations" / args.iteration
    if iteration.exists() and any((iteration / case / "artifact.json").exists() for case in selected):
        parser.error("a requested case already has an artifact in this iteration")
    config = ResultsConfig.model_validate_json(args.config.read_text())
    load_dotenv(REPO / ".env")
    config_copy = iteration / "config.json"
    if not config_copy.exists():
        write_new(config_copy, config.model_dump_json(indent=2) + "\n")
    elif config_copy.read_bytes() != (config.model_dump_json(indent=2) + "\n").encode():
        parser.error("iteration config differs; start a new iteration")
    ensure_source_snapshot(iteration)
    for case in selected:
        source = CASES[case]
        projection_file = source / "solutions.json"
        baseline = source / "answer.md"
        source_artifact = source / "results-artifact.json"
        case_dir = iteration / case
        if any((case_dir / name).exists() for name in
               ("receipt.json", "artifact.json", "failure.json", "answer.md")):
            parser.error(f"{case} already has evidence in this iteration")
        source_before = {name: digest(path) for name, path in {
            "projection": projection_file, "artifact": source_artifact,
            "baseline_answer": baseline, "config": config_copy}.items()}
        code_files = [REPO / "src" / "award_agent" / "results" / name for name in
                      ("core.py", "contracts.py", "request.py", "adapter.py")]
        code_before = {str(path.relative_to(REPO)): digest(path) for path in code_files}
        git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                            text=True).strip()
        git_dirty = subprocess.check_output(["git", "status", "--short"], cwd=REPO,
                                             text=True).splitlines()
        try:
            projection = SolutionProjection.model_validate_json(projection_file.read_text())
            artifact = run_results(projection, config, OpenAIResultsWriter(),
                                   input_measurer=OpenAIResultsInputMeasurer(),
                                   render_version=VERSION)
            rendered = replay_results(artifact)
        except Exception as error:
            write_new(case_dir / "failure.json", json.dumps({
                "error_type": type(error).__name__, "error": str(error),
                "source_hashes_before": source_before, "code_hashes_before": code_before,
                "git_head": git_head, "git_dirty_paths": git_dirty}, indent=2) + "\n")
            raise
        source_after = {name: digest(path) for name, path in {
            "projection": projection_file, "artifact": source_artifact,
            "baseline_answer": baseline, "config": config_copy}.items()}
        code_after = {str(path.relative_to(REPO)): digest(path) for path in code_files}
        write_new(case_dir / "artifact.json", artifact.model_dump_json(indent=2) + "\n")
        write_new(case_dir / "answer.md", rendered)
        receipt = {
            "method": "live Results writer on saved Ranking SolutionProjection; no provider calls",
            "source_projection": str(projection_file.relative_to(REPO)),
            "source_projection_sha256": source_before["projection"],
            "source_artifact_sha256": source_before["artifact"],
            "baseline_answer_sha256": source_before["baseline_answer"],
            "config_sha256": source_before["config"],
            "inputs_unchanged_during_call": source_before == source_after,
            "code_unchanged_during_call": code_before == code_after,
            "code_sha256": code_before,
            "git_head_before_call": git_head,
            "git_dirty_paths_before_call": git_dirty,
            "render_version": VERSION,
            "generation_outcome": artifact.generation_outcome,
            "validation_outcome": artifact.validation_outcome,
            "delivery_outcome": artifact.delivery_outcome,
            "attempts": len(artifact.attempts),
            "measured_input_tokens": [a.input_token_receipt.input_tokens if a.input_token_receipt
                                      else None for a in artifact.attempts],
            "writer_usage": [a.writer_receipt.usage if a.writer_receipt else None
                             for a in artifact.attempts],
            "finding_counts": {outcome: sum(f.outcome == outcome for a in artifact.attempts
                                            for f in a.findings)
                               for outcome in ("supported", "failed", "unchecked",
                                               "insufficient_evidence")},
            "rendered_digest": artifact.rendered_digest,
            "replay_equal": rendered == artifact.rendered_markdown,
        }
        write_new(case_dir / "receipt.json", json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({"case": case, **{key: receipt[key] for key in
            ("generation_outcome", "validation_outcome", "delivery_outcome", "attempts",
             "measured_input_tokens", "writer_usage", "finding_counts")}}, indent=2), flush=True)


if __name__ == "__main__":
    main()
