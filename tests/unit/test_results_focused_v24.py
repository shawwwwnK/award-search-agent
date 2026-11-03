"""V24 lossless named lead view only when no complete journey is eligible."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer
from test_results_focused_v23 import SavedWriter

from award_agent.cli import results as results_cli
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_comparison_contracts import FocusedResultsArtifactV11
from award_agent.results.focused_selector_records import selector_packet

RUNS = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/runs")
COMPLETE = ("confirm-v23-default-1-admitted", "confirm-v23-default-2-admitted",
            "confirm-v23-default-1-conditional", "confirm-v23-default-2-conditional")
INCOMPLETE = ("confirm-v23-default-1-incomplete", "confirm-v23-default-2-incomplete")


def _saved(name: str) -> tuple[FocusedResultsArtifactV11, SolutionProjection, ResultsConfig]:
    old = parse_focused_artifact((RUNS / name / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    source = SolutionProjection.model_validate(old.evidence.source.model_dump(mode="json"))
    return old, source, old.config


@pytest.mark.parametrize("name", COMPLETE)
def test_v24_complete_source_reuses_exact_v23_requests_and_delivery(name: str) -> None:
    old, source, config = _saved(name)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v24")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v21"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v19"
    assert len(writer.requests) == len(artifact.passes) == len(old.passes) == 2
    assert writer.requests == [old.passes[0].request, old.passes[1].request]
    assert artifact.passes[1].document == old.passes[1].document
    assert artifact.resolved == old.resolved
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == old.resolved


@pytest.mark.parametrize("name", INCOMPLETE)
def test_v24_named_lead_view_round_trips_every_original_row_and_quote(name: str) -> None:
    old, source, config = _saved(name)
    v23 = prepare_focused_selector(source, config, selection_format="roles-v21")
    v24 = prepare_focused_selector(source, config, selection_format="roles-v22")
    assert v24.packet["lead_rows"] == v23.packet["lead_rows"]
    assert v24.packet["exact_details"] == v23.packet["exact_details"]
    old_view = selector_packet(v23)
    new_view = selector_packet(v24)
    columns = v24.packet["legend"]["lead_row"]
    records = new_view["lead_records"]
    assert len(records) == len(v24.packet["lead_rows"]) == 378
    assert [list(record) for record in records] == [[*columns, "original_quote"]] * 378
    assert [[record[column] for column in columns] for record in records] == v24.packet["lead_rows"]
    assert [type(record[column]) for record in records for column in columns] == [
        type(value) for row in v24.packet["lead_rows"] for value in row]
    assert all(record["original_quote"] == v24.packet["exact_details"]["component_quotes"][record["A_or_C"]]
               for record in records)
    assert "lead_rows" not in new_view
    lead_refs = [record["A_or_C"] for record in records]
    assert len(lead_refs) == len(set(lead_refs))
    assert not set(lead_refs) & set(new_view["exact_details"]["component_quotes"])
    column_values = {column: [record[column] for record in records] for column in columns}
    assert 0 in column_values["fees"] and 0 in column_values["seats"]
    assert "unknown" in column_values["seats"]
    assert "absent" in column_values["returned_travelers"]
    restored = deepcopy(new_view)
    restored["selection_format"] = "roles-v21"
    restored["lead_rows"] = [[record[column] for column in columns] for record in records]
    restored["legend"]["lead_row"] = restored["legend"].pop("lead_records")[:-1]
    restored.pop("lead_records")
    restored["exact_details"]["component_quotes"].update({
        record["A_or_C"]: record["original_quote"] for record in records})
    assert restored == old_view
    # A synthetic unsupported source state is relocated unchanged as well.
    changed = deepcopy(v24.packet)
    changed["lead_rows"][0][columns.index("seats")] = "unsupported"
    changed["exact_details"]["component_quotes"][lead_refs[0]]["amount_state"] = "unsupported"
    synthetic = selector_packet(v24.model_copy(update={"packet": changed}))
    assert synthetic["lead_records"][0]["seats"] == "unsupported"
    assert synthetic["lead_records"][0]["original_quote"]["amount_state"] == "unsupported"
    assert old.selector_prepared.packet["selection_format"] == "roles-v21"


def test_v24_incomplete_runtime_replay_and_rejects_forged_complete_source_marker() -> None:
    old, source, config = _saved(INCOMPLETE[0])
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v24")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v22"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v20"
    assert len(writer.requests) == len(artifact.passes) == 2
    assert writer.requests[0]["text"]["format"]["schema"]["properties"]["choices"]["maxItems"] == 4
    instructions = writer.requests[0]["instructions"]
    assert "and component original-currency quotes in major units" not in instructions
    assert "Lead original-currency quotes are in each lead_records entry's original_quote object" in instructions
    assert "Other component quotes remain in exact_details.component_quotes" in instructions
    assert [item.request["reasoning"]["effort"] for item in artifact.passes] == ["none", "low"]
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    assert replay_focused_results(old) == old.resolved
    complete, _, _ = _saved(COMPLETE[0])
    forged = complete.model_dump(mode="json")
    forged["selector_prepared"]["packet"]["selection_format"] = "roles-v22"
    with pytest.raises(ValueError, match="complete journey source"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


@pytest.mark.parametrize("name,marker", [(COMPLETE[0], "roles-v21"),
                                        (INCOMPLETE[0], "roles-v22")])
def test_v24_cli_measure_chooses_source_branch(name: str, marker: str,
                                               tmp_path: Path) -> None:
    _, source, config = _saved(name)
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    output = tmp_path / "measure.json"
    assert results_cli.main(["measure", "--interactive", "--packet-profile", "focused-v24",
                             "--projection", str(source_path), "--config", str(config_path),
                             "--output", str(output)]) == 0
    assert json.loads(output.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format=marker).packet_digest


def test_v24_cli_author_and_replay_incomplete_view(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    old, source, config = _saved(INCOMPLETE[0])
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    from award_agent.results import interactive_adapter

    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    artifact_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", "--interactive", "--packet-profile", "focused-v24",
                             "--projection", str(source_path), "--config", str(config_path),
                             "--live", "--output", str(artifact_path)]) == 0
    artifact = parse_focused_artifact(artifact_path.read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v22"
    assert len(writer.requests) == 2
    replay_path = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(artifact_path),
                             "--output", str(replay_path)]) == 0
