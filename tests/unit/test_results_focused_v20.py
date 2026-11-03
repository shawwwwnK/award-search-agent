"""V20 canonical traveler support and versioned Results requests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer
from test_results_focused_v19 import _FrozenV19Writer

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import RawField
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_patch import patch_schema
from award_agent.results.focused_patch_contracts import FocusedResultsArtifactV12
from award_agent.results.focused_records import writer_packet
from award_agent.results.focused_traveler_evidence import _count

RUNS = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/runs")
CONFIG = Path("data/results/fast-default.json")


def _run(name: str) -> tuple[FocusedResultsArtifactV12, _FrozenV19Writer, object]:
    old = parse_focused_artifact((RUNS / name / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(old.evidence.source.model_dump(mode="json"))
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    assert old.passes[0].raw_wire is not None
    writer = _FrozenV19Writer(old.passes[0].raw_wire)
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v20")
    assert isinstance(artifact, FocusedResultsArtifactV12)
    return artifact, writer, old


@pytest.mark.parametrize("name,journey_count", [
    ("scout-v19-admitted", 3),
    ("scout-v19-conditional", 2),
    ("scout-v19-incomplete", 0),
])
def test_v20_traveler_evidence_is_owned_by_exact_selected_journey(
        name: str, journey_count: int) -> None:
    artifact, writer, old = _run(name)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v19"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v17"
    assert len(artifact.passes) == len(writer.requests) == 3
    packet = json.loads(str(writer.requests[1]["input"]))["packet"]
    assert packet["format"] == "focused-authoring-records-v3"
    assert packet == json.loads(str(writer.requests[2]["input"]))["packet"]
    records = packet["authoring_records"]
    journeys = {ref: row for ref, row in records.items() if row["role"] == "journey"}
    assert len(journeys) == journey_count
    assert all("traveler_evidence" not in row for row in records.values()
               if row["role"] != "journey")
    by_component = {item.observation_id: item for item in artifact.evidence.components}
    by_journey = {item.candidate_id: item for item in artifact.evidence.journeys}
    aliases = artifact.focus_prepared.packet["wire_aliases"]
    for ref, record in journeys.items():
        summary = record["traveler_evidence"]
        canonical = artifact.focus_prepared.structured.references.journeys[aliases[ref]]
        journey = by_journey[canonical]
        award = by_component[journey.award_observation_id]
        cash = by_component[journey.cash_observation_id] if journey.cash_observation_id else None
        assert summary["requested_travelers"] == artifact.evidence.source.view.request.travelers
        assert summary["award_component_ref"] == record["member"]["award_ref"]
        assert summary["cash_component_ref"] == record["member"].get("cash_ref")
        assert summary["award_reported_seats"] == award.seats.model_dump(mode="json")
        assert summary["award_returned_travelers"] == award.returned_travelers.model_dump(mode="json")
        assert summary["cash_returned_travelers"] == (
            cash.returned_travelers.model_dump(mode="json") if cash else None)
        assert summary["award_support_for_requested_party"] == record["facts"]["traveler_support"]
        assert summary["award_minimum_seats_check"] == record["facts"]["seat_support"]
    assert "selected_comparisons" not in packet and "temporal_comparisons" not in packet
    assert all("purpose" not in row for row in packet["editorial_plan"])
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    assert replay_focused_results(old) == old.resolved


def test_v20_q071_knows_request_but_does_not_transfer_cash_echo_to_award() -> None:
    _, writer, _ = _run("scout-v19-conditional")
    packet = json.loads(str(writer.requests[1]["input"]))["packet"]
    journeys = [row for row in packet["authoring_records"].values() if row["role"] == "journey"]
    assert len(journeys) == 2
    for row in journeys:
        summary = row["traveler_evidence"]
        assert summary["requested_travelers"] == 1
        assert summary["award_support_for_requested_party"] == "unknown"
        assert summary["award_reported_seats"]["state"] == "unknown"
        assert summary["award_returned_travelers"]["state"] == "absent"
        assert summary["cash_returned_travelers"]["state"] == "value"
        assert summary["cash_returned_travelers"]["value"] == 1
        assert row["award_component"]["quote"]["price_scope"] == "unknown"


def test_v20_absent_echo_can_coexist_with_supported_award_seats() -> None:
    _, writer, _ = _run("scout-v19-admitted")
    packet = json.loads(str(writer.requests[1]["input"]))["packet"]
    journeys = [row for row in packet["authoring_records"].values() if row["role"] == "journey"]
    assert any(row["traveler_evidence"]["award_returned_travelers"]["state"] == "absent"
               and row["traveler_evidence"]["award_reported_seats"]["state"] == "value"
               and row["traveler_evidence"]["award_support_for_requested_party"] == "passed"
               for row in journeys)
    assert _count(RawField(state="value", value=0, source_field="RemainingSeats")) == {
        "state": "value", "value": 0, "source_field": "RemainingSeats"}
    assert _count(RawField(state="unknown", source_field="RemainingSeats"))["value"] is None


def test_v20_replay_rejects_forged_traveler_support_with_updated_packet_digest() -> None:
    artifact, _, _ = _run("scout-v19-conditional")
    data = artifact.model_dump(mode="json")
    focus = data["focus_prepared"]
    ref = next(iter(focus["packet"]["traveler_evidence"]))
    focus["packet"]["traveler_evidence"][ref]["award_support_for_requested_party"] = "passed"
    from award_agent.providers.contracts import content_digest

    focus["packet_digest"] = content_digest(focus["packet"])
    with pytest.raises(ValueError):
        replay_focused_results(FocusedResultsArtifactV12.model_validate(data))


def test_v20_writer_requires_exact_traveler_summary_refs() -> None:
    artifact, _, _ = _run("scout-v19-conditional")
    assert artifact.focus_prepared is not None
    packet = dict(artifact.focus_prepared.packet)
    packet.pop("traveler_evidence")
    with pytest.raises(ValueError, match="traveler evidence"):
        writer_packet(artifact.focus_prepared.model_copy(update={"packet": packet}))


def test_v20_editor_keeps_one_numbered_draft_and_atomic_patch_schema() -> None:
    artifact, writer, _ = _run("scout-v19-conditional")
    assert artifact.focus_prepared is not None
    editor_input = json.loads(str(writer.requests[2]["input"]))
    assert "numbered_draft" not in editor_input
    assert editor_input["previous_wire"] == {"blocks": [
        {"index": index, "block": block} for index, block in enumerate(
            json.loads(artifact.passes[1].raw_wire)["blocks"])]}
    shape = patch_schema(artifact.focus_prepared)
    assert shape["properties"]["edits"]["items"]["properties"]["blocks"]["maxItems"] == 1
    packet = dict(artifact.focus_prepared.packet)
    packet["traveler_evidence"] = {**packet["traveler_evidence"], "J999": {}}
    with pytest.raises(ValueError, match="traveler evidence"):
        writer_packet(artifact.focus_prepared.model_copy(update={"packet": packet}))


def test_v20_cli_explicit_measure_author_replay(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    old = parse_focused_artifact((RUNS / "scout-v19-conditional" / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(old.evidence.source.model_dump(mode="json"))
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", "focused-v20", "--projection",
              str(source_path), "--config", str(config_path)]
    measure_path = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    assert json.loads(measure_path.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format="roles-v19").packet_digest
    from award_agent.results import interactive_adapter

    assert old.passes[0].raw_wire is not None
    writer = _FrozenV19Writer(old.passes[0].raw_wire)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    artifact_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(artifact_path)]) == 0
    assert json.loads(artifact_path.read_text())["contract_version"] == "results-artifact-v12"
    replay_path = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(artifact_path),
                             "--output", str(replay_path)]) == 0
    assert json.loads(replay_path.read_text())["contract_version"] == "results-focused-resolved-v1"
