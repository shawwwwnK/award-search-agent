"""Package and verify replayable Provider Stage runs from compiled search plans.

Usage:
  python scripts/provider_plan_corpus.py add --corpus DIR --case NAME \
      --planning-input FILE --bundle FILE --tape FILE --result FILE \
      --runtime DIR [--catalog DIR]
  python scripts/provider_plan_corpus.py verify --corpus DIR [--catalog DIR]

Every entry is one complete provider execution. Standalone provider captures are
not corpus entries; the bundle, result and exact replay must share one plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from award_agent.cli.provider_results import ProviderInputBundle
from award_agent.domain import EffectiveRequest
from award_agent.providers.contracts import ProviderResultSet
from award_agent.providers.evidence import evidence_sha256
from award_agent.providers.execution import validate_result_attachment
from award_agent.providers.replay import ReplayTape
from award_agent.search_planning.compilation_contracts import CompiledSearchPlan

ROOT = Path(__file__).resolve().parents[1]
CASE = re.compile(r"^[a-z][a-z0-9_-]*$")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_files(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        raise ValueError(f"run directory is absent: {directory}")
    if any(path.is_symlink() for path in directory.rglob("*")):
        raise ValueError("symlinks are not allowed in saved runs")
    if not (directory / "runtime").is_dir():
        raise ValueError("run requires a runtime evidence directory")
    files = sorted(path for path in directory.rglob("*") if path.is_file())
    if any(path.relative_to(directory).parts[0] not in
           {"planning-input.json", "bundle.json", "tape.json", "result.json", "runtime"}
           for path in files):
        raise ValueError("unexpected file outside the plan-run artifacts")
    if not {"planning-input.json", "bundle.json", "tape.json", "result.json"} <= {
        path.relative_to(directory).as_posix() for path in files
    }:
        raise ValueError("run requires planning-input.json, bundle.json, tape.json, and result.json")
    return {path.relative_to(directory).as_posix(): _digest(path) for path in files}


def _validate_run(directory: Path, *, catalog: Path | None) -> dict[str, Any]:
    planning_input = _json(directory / "planning-input.json")
    bundle = ProviderInputBundle.model_validate_json((directory / "bundle.json").read_text())
    result = ProviderResultSet.model_validate_json((directory / "result.json").read_text())
    tape = ReplayTape.model_validate_json((directory / "tape.json").read_text())
    if result.status == "stale":
        raise ValueError("stale results cannot enter the saved corpus")
    if bundle.plan.identity.compilation_binding_digest != bundle.expected_compilation_binding_digest:
        raise ValueError("bundle compilation binding differs from its plan")
    if (CompiledSearchPlan.model_validate(planning_input["plan"]) != bundle.plan
            or EffectiveRequest.model_validate(planning_input["current_effective_request"])
            != bundle.current_effective_request
            or planning_input["current_session_id"] != bundle.current_session_id
            or planning_input["current_revision"] != bundle.current_revision
            or planning_input["expected_compilation_binding_digest"]
            != bundle.expected_compilation_binding_digest):
        raise ValueError("provider bundle differs from its frozen search-planning input")
    if bundle.plan.identity.session_id != bundle.current_session_id or bundle.plan.identity.revision != bundle.current_revision:
        raise ValueError("bundle authority differs from its plan")
    if catalog is not None:
        manifest = catalog / "manifest.json"
        receipt = bundle.plan.identity.catalog_receipt
        if (_digest(manifest) != receipt.manifest_sha256
                or _json(manifest)["release_id"] != receipt.release_id):
            raise ValueError("selected catalog differs from the compiled plan")
    if result.execution_plan.binding.run_id != bundle.run_id:
        raise ValueError("result run ID differs from bundle")
    validate_result_attachment(
        bundle.plan, result, current_session_id=bundle.current_session_id,
        current_revision=bundle.current_revision,
        current_effective_request=bundle.current_effective_request,
        expected_compilation_binding_digest=bundle.expected_compilation_binding_digest,
        policy=bundle.policy, award_capability=bundle.award_capability,
        cash_capability=bundle.cash_capability,
    )
    runtime = directory / "runtime"
    captures = {entry.response.evidence.relative_path for entry in tape.entries}
    for entry in tape.entries:
        path = runtime / entry.response.evidence.relative_path
        if not path.resolve().is_relative_to(runtime.resolve()) or not path.is_file():
            raise ValueError(f"missing saved provider body: {entry.response.evidence.relative_path}")
        body = _json(path)
        if body != entry.response.body or evidence_sha256(body) != entry.response.evidence.sha256:
            raise ValueError(f"saved provider body differs from tape: {path.name}")
    runtime_files = {path.relative_to(runtime).as_posix() for path in runtime.rglob("*") if path.is_file()}
    if runtime_files != captures:
        raise ValueError("runtime files must exactly match tape evidence")
    with tempfile.TemporaryDirectory(prefix="provider-plan-corpus-") as temp:
        output = Path(temp) / "replay.json"
        command = [sys.executable, "-m", "award_agent.cli.provider_results", "--mode", "replay",
                   "--bundle", str(directory / "bundle.json"), "--tape", str(directory / "tape.json"),
                   "--output", str(output)]
        if catalog is not None:
            command.extend(("--catalog", str(catalog)))
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=900, check=False)
        expected_exit = 0 if result.status == "completed" else 1
        if run.returncode != expected_exit or not output.is_file() or output.read_bytes() != (directory / "result.json").read_bytes():
            raise ValueError(f"exact provider replay differs (exit {run.returncode}): {run.stderr[-1000:]}")
    return {
        "session_id": bundle.plan.identity.session_id,
        "revision": bundle.plan.identity.revision,
        "catalog_release_id": bundle.plan.identity.catalog_receipt.release_id,
        "catalog_manifest_sha256": bundle.plan.identity.catalog_receipt.manifest_sha256,
        "plan_digest": bundle.plan.plan_digest,
        "compilation_binding_digest": bundle.plan.identity.compilation_binding_digest,
        "effective_request_digest": bundle.plan.identity.effective_request_digest,
        "run_id": bundle.run_id,
        "status": result.status,
        "queries": len(result.execution_plan.queries),
        "observations": len(result.observations),
        "coverage_units": len(result.coverage),
        "transport_receipts": len(result.transport_receipts),
        "tape_entries": len(tape.entries),
    }


def verify(corpus: Path, *, catalog: Path | None = None) -> dict[str, int]:
    index = _json(corpus / "index.json")
    if index.get("schema_version") != 1 or not isinstance(index.get("runs"), list):
        raise ValueError("unsupported plan corpus index")
    seen: set[str] = set()
    run_ids: set[str] = set()
    for item in index["runs"]:
        case = item["case"]
        if not CASE.fullmatch(case) or case in seen:
            raise ValueError(f"invalid or repeated case: {case}")
        seen.add(case)
        directory = corpus / "runs" / case
        files = _run_files(directory)
        if files != item["files"]:
            raise ValueError(f"saved run files differ: {case}")
        metadata = _validate_run(directory, catalog=catalog)
        if metadata != item["metadata"]:
            raise ValueError(f"saved run metadata differs: {case}")
        if metadata["run_id"] in run_ids:
            raise ValueError(f"duplicate provider run ID: {metadata['run_id']}")
        run_ids.add(metadata["run_id"])
    actual = {path.name for path in (corpus / "runs").iterdir() if path.is_dir()} if (corpus / "runs").exists() else set()
    if actual != seen:
        raise ValueError("unindexed or missing plan run directory")
    return {"runs": len(seen), "observations": sum(item["metadata"]["observations"] for item in index["runs"])}


def add(corpus: Path, case: str, *, bundle: Path, tape: Path, result: Path,
        runtime: Path, planning_input: Path, catalog: Path | None = None) -> dict[str, int]:
    if not CASE.fullmatch(case):
        raise ValueError("case must use lowercase letters, digits, underscores or hyphens")
    if (corpus / "runs" / case).exists():
        raise ValueError(f"case already exists: {case}")
    if (corpus / "index.json").exists():
        verify(corpus, catalog=catalog)
        index = _json(corpus / "index.json")
    else:
        index = {"schema_version": 1, "runs": []}
    with tempfile.TemporaryDirectory(prefix="provider-plan-add-") as temporary:
        staged = Path(temporary) / case
        staged.mkdir()
        for source, name in ((planning_input, "planning-input.json"), (bundle, "bundle.json"),
                             (tape, "tape.json"), (result, "result.json")):
            shutil.copyfile(source, staged / name)
        saved_runtime = staged / "runtime"
        saved_runtime.mkdir()
        source_tape = ReplayTape.model_validate_json((staged / "tape.json").read_text())
        for entry in source_tape.entries:
            relative = Path(entry.response.evidence.relative_path)
            source = (runtime / relative).resolve()
            if not source.is_relative_to(runtime.resolve()) or not source.is_file():
                raise ValueError(f"missing source evidence body: {relative}")
            target = saved_runtime / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        files = _run_files(staged)
        metadata = _validate_run(staged, catalog=catalog)
        if metadata["run_id"] in {item["metadata"]["run_id"] for item in index["runs"]}:
            raise ValueError(f"provider run is already saved: {metadata['run_id']}")
        (corpus / "runs").mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, corpus / "runs" / case)
    index["runs"].append({"case": case, "metadata": metadata, "files": files})
    index["runs"].sort(key=lambda item: item["case"])
    (corpus / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"runs": len(index["runs"]),
            "observations": sum(item["metadata"]["observations"] for item in index["runs"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("add", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--corpus", type=Path, required=True)
        command.add_argument("--catalog", type=Path)
        if name == "add":
            command.add_argument("--case", required=True)
            for field in ("planning-input", "bundle", "tape", "result", "runtime"):
                command.add_argument(f"--{field}", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "add":
        counts = add(args.corpus, args.case, planning_input=args.planning_input,
                     bundle=args.bundle, tape=args.tape, result=args.result,
                     runtime=args.runtime, catalog=args.catalog)
    else:
        counts = verify(args.corpus, catalog=args.catalog)
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
