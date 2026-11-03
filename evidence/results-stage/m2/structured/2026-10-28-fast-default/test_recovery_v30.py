"""Narrow offline V30 selected-source correction and replay control."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import verify


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "tests/unit"))
    from test_results_focused import FakeMeasurer
    from test_results_focused_v23 import SavedWriter

    from award_agent.results.focused import parse_focused_artifact, replay_focused_results, run_focused_results

    old = parse_focused_artifact(
        (verify.RUNS / "scout-v29-incomplete" / "artifact.json").read_bytes())
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    bad = json.loads(old.passes[1].raw_wire)
    selected_alias = json.loads(old.passes[0].raw_wire)["choices"][0]["r"]
    selected_observation_id = old.selector_prepared.structured.references.awards[selected_alias]
    selected_refs = old.passes[0].selection.incomplete_observation_ids
    selected_ref = next(ref for ref, alias in
                        old.focus_prepared.packet["wire_aliases"].items()
                        if alias == selected_alias)
    assert selected_observation_id in selected_refs
    assert selected_alias in {row[0] for row in old.selector_prepared.packet["lead_rows"]}
    selected_block = next(block for block in bad["blocks"]
                          if block.get("r") == selected_ref)
    selected_block["v"] += f" {selected_alias} is an internal alias."
    writer = SavedWriter([old.passes[0].raw_wire, json.dumps(bad), old.passes[1].raw_wire])
    artifact = run_focused_results(old.evidence.source, old.config, writer,
                                   FakeMeasurer(), profile="focused-v30")
    assert artifact.contract_version == "results-artifact-v11"
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v30"
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v28"
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "medium", "low", "low"]
    assert [item.phase for item in artifact.passes] == [
        "selection", "composition", "correction"]
    assert any(finding.outcome == "failed" for finding in artifact.passes[1].findings)
    assert not any(finding.outcome == "failed" for finding in artifact.passes[2].findings)
    selector = artifact.passes[0]
    assert not verify._v28_selector_issues(
        selector.request, selector.raw_wire, selector.selection)
    assert not verify._grouped_lead_selector_issues(
        selector.request, artifact.selector_prepared, selection_format="roles-v30")
    assert not verify._v30_selector_guidance_issues(selector.request, incomplete=True)
    composer_packet = json.loads(artifact.passes[1].request["input"])["packet"]
    assert composer_packet["selection_format"] == "roles-v30"
    assert composer_packet["composition_format"] == "complete-v28"
    assert not verify._v23_correction_issues(artifact.passes[1], artifact.passes[2])
    assert replay_focused_results(artifact) == artifact.resolved
    print("V30 incomplete selector guidance, conditional low correction and replay passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
