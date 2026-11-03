"""Prepare blind, source-grounded Results answer bundles for independent review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import ledger

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
INDEX = HERE / "review-index.json"


def create(run_name: str, bundle_name: str, *, pass_index: int | None = None) -> Path:
    if (not run_name or Path(run_name).name != run_name or
            not bundle_name or Path(bundle_name).name != bundle_name):
        raise ValueError("names must be single path components")
    source = RUNS / run_name
    if not (source / "artifact.json").is_file():
        raise FileNotFoundError("run artifact is missing")
    if ledger.read_json(source / "settings.json").get("recovery_diagnostic", False):
        raise ValueError("recovery diagnostic cannot enter blind natural-answer review")
    index = ledger.read_json(INDEX) if INDEX.exists() else {}
    if bundle_name in index:
        raise ValueError("bundle already indexed")
    from run import _preview

    from award_agent.results.focused import parse_focused_artifact, replay_focused_results
    from award_agent.results.focused_comparison_wire import resolve_focused_comparison_document
    from award_agent.results.structured import resolve_structured_document

    artifact = parse_focused_artifact((source / "artifact.json").read_bytes())
    replayed = replay_focused_results(artifact)
    if replayed != artifact.resolved:
        raise ValueError("saved artifact differs from source replay")
    selected_index = getattr(artifact, "selected_pass_index", None)
    if selected_index is None:
        selected_index = next((i for i in range(len(artifact.passes) - 1, -1, -1)
                               if artifact.passes[i].document is not None), None)
    if selected_index is None or artifact.resolved is None:
        raise ValueError("run has no resolved document to review")
    if pass_index is not None and (artifact.contract_version not in {
                                   "results-artifact-v10", "results-artifact-v11",
                                   "results-artifact-v12"} or
                                   pass_index != 1):
        raise ValueError("only a versioned editorial initial draft can be separately reviewed")
    chosen = selected_index if pass_index is None else pass_index
    if pass_index == 1 and selected_index == 1:
        raise ValueError("initial draft is already the selected final answer")
    for prior in index.values():
        prior_run = prior if isinstance(prior, str) else prior.get("run")
        prior_pass = None if isinstance(prior, str) else prior.get("pass_index")
        if prior_run == f"runs/{run_name}" and (
                prior_pass == chosen or (prior_pass is None and pass_index is None)):
            raise ValueError("run pass already has a review bundle")
    document = artifact.passes[chosen].document
    if document is None:
        raise ValueError("selected pass has no document")
    if pass_index is None:
        preview = source / "answer-preview.md"
        if not preview.is_file():
            raise FileNotFoundError("answer preview is missing")
        answer = _preview(replayed).encode("utf-8")
        if preview.read_bytes() != answer:
            raise ValueError("saved answer preview differs from source replay")
    else:
        assert artifact.focus_prepared is not None
        if artifact.contract_version in {"results-artifact-v11", "results-artifact-v12"}:
            assert artifact.comparison_registry is not None
            resolved = resolve_focused_comparison_document(document,
                artifact.focus_prepared, artifact.evidence,
                artifact.comparison_registry, artifact.passes[chosen].findings)
        else:
            resolved = resolve_structured_document(document,
                artifact.focus_prepared.structured, artifact.evidence,
                artifact.passes[chosen].findings)
        answer = _preview(resolved).encode("utf-8")
    target = HERE / "review-bundles" / bundle_name
    target.mkdir(parents=True, exist_ok=False)
    ledger.write_new(target / "document.json", document.model_dump(mode="json"))
    ledger.write_new(target / "evidence.json", artifact.evidence.model_dump(mode="json"))
    ledger.write_new(target / "references.json",
                     artifact.selector_prepared.structured.references.model_dump(mode="json"))
    if artifact.contract_version in {"results-artifact-v11", "results-artifact-v12"}:
        assert artifact.comparison_registry is not None
        ledger.write_new(target / "comparison-registry.json",
                         artifact.comparison_registry.model_dump(mode="json"))
    (target / "answer.md").write_bytes(answer)
    # Reviewer-facing files contain no run arm, settings, timing, usage, or tier.
    index[bundle_name] = {"run": f"runs/{run_name}", "pass_index": chosen}
    temporary = INDEX.with_suffix(".tmp")
    temporary.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    temporary.replace(INDEX)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--pass-index", type=int)
    args = parser.parse_args()
    print(create(args.run, args.bundle, pass_index=args.pass_index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
