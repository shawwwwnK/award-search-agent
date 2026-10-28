"""Create immutable anonymized source-review bundles from saved runs."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
BUNDLES = HERE / "review-bundles"
INDEX = HERE / "review-index.json"
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _prototype_references(run: Path, summary: dict[str, Any]) -> dict[str, Any]:
    from award_agent.results.contracts import ResultsConfig
    from award_agent.results.structured import prepare_structured_results
    from award_agent.results.structured_contracts import StructuredResultsArtifact

    case = summary["case"]
    source_artifact = StructuredResultsArtifact.model_validate_json(
        (SOURCE / case / "artifact.json").read_text(encoding="utf-8"))
    source_config = ResultsConfig.model_validate_json(
        (SOURCE / case / "config.json").read_text(encoding="utf-8"))
    settings = _read(run / "settings.json")
    config = source_config.model_copy(update={
        "model": "gpt-6-luna", "max_output_tokens": settings.get("max_output_tokens", 8192),
        "timeout_seconds": settings.get("timeout_seconds", 240.0)})
    prepared = prepare_structured_results(source_artifact.evidence.source, config)
    return prepared.references.model_dump(mode="json")


def create(run_name: str, bundle_name: str) -> Path:
    if not run_name or Path(run_name).name != run_name:
        raise ValueError("run name must be one path component")
    if not bundle_name or Path(bundle_name).name != bundle_name:
        raise ValueError("bundle name must be one path component")
    run = RUNS / run_name
    if not run.is_dir():
        raise FileNotFoundError(f"unknown run: {run_name}")
    index = _read(INDEX) if INDEX.exists() else {}
    if bundle_name in index:
        raise ValueError(f"bundle already indexed: {bundle_name}")
    if run_name in index.values():
        raise ValueError(f"run already has a review bundle: {run_name}")
    target = BUNDLES / bundle_name
    if target.exists():
        raise FileExistsError(f"bundle directory already exists: {target}")
    summary = _read(run / "summary.json")

    diagnostic_path = run / "diagnostic-artifact.json"
    if diagnostic_path.exists():
        diagnostic = _read(diagnostic_path)
        if diagnostic.get("contract") != "comparison-composition-diagnostic-v1":
            raise ValueError("unknown custom diagnostic artifact contract")
        if diagnostic.get("document") is None or diagnostic.get("resolved") is None:
            raise ValueError("composition diagnostic has no resolved composition to review")
        document = diagnostic["document"]
        evidence = diagnostic["evidence"]
        focus_prepared = diagnostic.get("focus_prepared") or {}
        structured = focus_prepared.get("structured") or {}
        authoring_view = structured.get("authoring_view") or {}
        references = authoring_view.get("references")
        if not isinstance(references, dict):
            raise ValueError("composition diagnostic has no prepared reference map")
        answer_path = run / "answer-preview.md"
    else:
        diagnostic = None

    artifact_path = run / "artifact.json"
    if diagnostic is not None:
        pass
    elif artifact_path.exists():
        raw_artifact = _read(artifact_path)
        if raw_artifact.get("contract_version") == "results-artifact-v8":
            from award_agent.results.focused_contracts import FocusedResultsArtifact

            artifact = FocusedResultsArtifact.model_validate_json(artifact_path.read_text(encoding="utf-8"))
            composition = next((item for item in artifact.passes
                                if item.phase == "composition"), None)
            if composition is None or composition.document is None or artifact.resolved is None:
                raise ValueError("focused run has no resolved composition to review")
            document = composition.document.model_dump(mode="json")
            evidence = artifact.evidence.model_dump(mode="json")
            references = _prototype_references(run, summary)
            answer_path = run / "answer-preview.md"
        else:
            from award_agent.results.interactive_contracts import InteractiveResultsArtifact

            artifact = InteractiveResultsArtifact.model_validate_json(artifact_path.read_text(encoding="utf-8"))
            if artifact.selected_attempt is None:
                raise ValueError("run has no selected document to review")
            selected = artifact.attempts[artifact.selected_attempt]
            if selected.document is None or artifact.resolved is None:
                raise ValueError("selected attempt lacks a resolved answer")
            document = selected.document.model_dump(mode="json")
            evidence = artifact.evidence.model_dump(mode="json")
            references = artifact.prepared.structured.references.model_dump(mode="json")
            answer_path = run / "answer-preview.md"
    else:
        selected_index = summary.get("selected_attempt")
        if not isinstance(selected_index, int) or selected_index < 0:
            raise ValueError("prototype run has no selected attempt")
        attempt_path = run / f"attempt-{selected_index + 1:02d}.json"
        if not attempt_path.exists():
            raise FileNotFoundError(f"selected prototype attempt missing: {attempt_path.name}")
        attempt = _read(attempt_path)
        if attempt.get("document") is None:
            raise ValueError("selected prototype attempt lacks a document")
        source_artifact = _read(SOURCE / summary["case"] / "artifact.json")
        document = attempt["document"]
        evidence = source_artifact["evidence"]
        references = _prototype_references(run, summary)
        answer_path = run / "answer-preview.md"
    if not answer_path.is_file():
        raise FileNotFoundError(f"run has no answer preview: {run_name}")

    target.mkdir(parents=True, exist_ok=False)
    _write(target / "document.json", document)
    _write(target / "evidence.json", evidence)
    _write(target / "references.json", references)
    shutil.copyfile(answer_path, target / "answer.md")
    # The index is the sole bundle-to-run link. Do not include arm, timing,
    # tier, usage, settings, or API receipts in the reviewer-facing bundle.
    index[bundle_name] = f"runs/{run_name}"
    temp_index = INDEX.with_suffix(".json.tmp")
    temp_index.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    temp_index.replace(INDEX)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--bundle", required=True)
    args = parser.parse_args()
    print(create(args.run, args.bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
