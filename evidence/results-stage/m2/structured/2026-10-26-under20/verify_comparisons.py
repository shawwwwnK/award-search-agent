"""Offline source and request replay for a composition-only comparison diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import runtime_runner as base


def verify(directory: Path) -> dict[str, object]:
    from award_agent.ranking.projection_contracts import SolutionProjection
    from award_agent.results.contracts import ResultsConfig
    from award_agent.results.focused import (
        COMPOSER_SETTINGS,
        _replay_pass,
        _request,
        prepare_focused_composer,
        replay_focused_results,
    )
    from award_agent.results.focused_contracts import FocusedPass, FocusedResultsArtifact
    from award_agent.results.focused_wire import decode as decode_focused_wire
    from award_agent.results.interactive_contracts import InteractivePreparedInput
    from award_agent.results.structured import resolve_structured_document
    from award_agent.results.workspace_contracts import WorkspaceEvidence

    value = json.loads((directory / "diagnostic-artifact.json").read_text(encoding="utf-8"))
    if value.get("contract") != "comparison-composition-diagnostic-v1" or \
            value.get("new_selector_calls") != 0 or \
            value.get("new_count_calls") not in {0, 1} or \
            value.get("new_generation_calls") not in {0, 1}:
        raise ValueError("invalid diagnostic identity or call accounting")
    source_path = base.REPO / value["source_artifact"]
    if base.campaign_utils.sha256(source_path) != value["source_sha256"]:
        raise ValueError("prior selector source hash differs")
    prior = FocusedResultsArtifact.model_validate_json(source_path.read_bytes())
    replay_focused_results(prior)
    if prior.passes[0].model_dump(mode="json") != value["old_selector_pass"]:
        raise ValueError("old selector provenance differs")
    evidence = WorkspaceEvidence.model_validate(value["evidence"])
    config = ResultsConfig.model_validate(value["config"])
    selector = InteractivePreparedInput.model_validate(value["selector_prepared"])
    if evidence != prior.evidence or config != prior.config or selector != prior.selector_prepared:
        raise ValueError("diagnostic source evidence differs")
    selection = prior.passes[0].selection
    if selection is None:
        raise ValueError("old selector has no valid selection")
    projection = SolutionProjection.model_validate(evidence.source.model_dump(mode="json"))
    focus = prepare_focused_composer(selection, selector, projection, evidence,
                                     composition_format="comparisons-v1")
    if focus != InteractivePreparedInput.model_validate(value["focus_prepared"]):
        raise ValueError("diagnostic comparison packet differs")
    answer_pass = FocusedPass.model_validate(value["composer_pass"])
    _replay_pass(answer_pass, _request(focus, config, COMPOSER_SETTINGS, "composition", projection),
        config, lambda raw: decode_focused_wire(raw, focus, projection), projection, focus)
    resolved = (resolve_structured_document(answer_pass.document, focus.structured,
                                            evidence, answer_pass.findings)
                if answer_pass.document is not None else None)
    if (resolved.model_dump(mode="json") if resolved else None) != value["resolved"] or \
            (answer_pass.document.model_dump(mode="json") if answer_pass.document else None) \
            != value["document"]:
        raise ValueError("diagnostic answer differs from source and wire")
    receipt = {"verification": "composition-only-source-replay", "passed": True,
               "source_artifact": value["source_artifact"],
               "old_selector_request_digest": prior.passes[0].request_digest,
               "composer_request_digest": answer_pass.request_digest,
               "resolved_matches": True, "replay_made_live_calls": False}
    receipt_path = directory / "verification-receipt.json"
    if receipt_path.exists():
        if json.loads(receipt_path.read_text(encoding="utf-8")) != receipt:
            raise ValueError("saved diagnostic replay receipt differs")
    else:
        base.campaign_utils.write_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(verify(parser.parse_args().directory), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
