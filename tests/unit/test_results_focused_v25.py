"""V25 changes only incomplete authoring effort over V24 named lead facts."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer
from test_results_focused_v23 import SavedWriter
from test_results_focused_v24 import COMPLETE, INCOMPLETE, RUNS, _saved

from award_agent.cli import results as results_cli
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_comparison_contracts import FocusedResultsArtifactV11


@pytest.mark.parametrize("name", COMPLETE)
def test_v25_complete_branch_keeps_v23_requests_delivery_and_low_author(name: str) -> None:
    old, source, config = _saved(name)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v25")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(writer.requests) == len(artifact.passes) == 2
    assert writer.requests == [old.passes[0].request, old.passes[1].request]
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v21"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v19"
    assert artifact.composer_settings.reasoning_effort == "low"
    assert artifact.resolved == old.resolved
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == old.resolved


@pytest.mark.parametrize("name", ("scout-v24-incomplete-1", "scout-v24-incomplete-2"))
def test_v25_partial_requests_differ_from_v24_only_by_markers_and_author_effort(name: str) -> None:
    old = parse_focused_artifact((RUNS / name / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    source = old.evidence.source
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    artifact = run_focused_results(source, old.config, writer, FakeMeasurer(), profile="focused-v25")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v23"
    assert artifact.focus_prepared is not None and old.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v21"
    assert len(writer.requests) == len(artifact.passes) == 2
    assert [request["reasoning"]["effort"] for request in writer.requests] == ["none", "medium"]
    assert artifact.correction_settings.reasoning_effort == "low"
    for index, (previous, current) in enumerate(zip(
            [old.passes[0].request, old.passes[1].request], writer.requests, strict=True)):
        normalized = deepcopy(current)
        normalized["input"] = json.loads(str(normalized["input"]))
        old_request = deepcopy(previous)
        old_request["input"] = json.loads(str(old_request["input"]))
        normalized["input"]["packet"]["selection_format"] = "roles-v22"
        if index == 1:
            normalized["input"]["packet"]["composition_format"] = "complete-v20"
            normalized["reasoning"] = {"effort": "low"}
        assert normalized == old_request
    previous_focus = deepcopy(old.focus_prepared.packet)
    current_focus = deepcopy(artifact.focus_prepared.packet)
    current_focus["selection_format"] = "roles-v22"
    current_focus["composition_format"] = "complete-v20"
    assert current_focus == previous_focus
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    assert replay_focused_results(old) == old.resolved
    forged_old = old.model_dump(mode="json")
    forged_old["composer_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="settings"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged_old))
    forged_new = artifact.model_dump(mode="json")
    forged_new["composer_settings"]["reasoning_effort"] = "low"
    with pytest.raises(ValueError, match="settings"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged_new))


def test_v25_incomplete_marker_rejects_complete_source() -> None:
    old, _, _ = _saved(COMPLETE[0])
    forged = old.model_dump(mode="json")
    forged["selector_prepared"]["packet"]["selection_format"] = "roles-v23"
    forged["composer_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="complete journey source"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


def test_v25_partial_failed_check_uses_one_low_full_document_correction() -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    changed = json.loads(old.passes[1].raw_wire)
    changed["blocks"][0]["v"] += " A1 is an internal alias."
    writer = SavedWriter([old.passes[0].raw_wire, json.dumps(changed), old.passes[1].raw_wire])
    artifact = run_focused_results(old.evidence.source, old.config, writer,
                                    FakeMeasurer(), profile="focused-v25")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(writer.requests) == len(artifact.passes) == 3
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "none", "medium", "low"]
    assert artifact.passes[1].outcome == "recoverable"
    assert any(f.outcome == "failed" for f in artifact.passes[1].findings)
    correction = writer.requests[2]
    assert correction["text"]["format"]["name"] == "FocusedResultsComparisonDocument"
    assert json.loads(str(correction["input"]))["packet"] == json.loads(
        str(writer.requests[1]["input"]))["packet"]
    assert artifact.selected_pass_index == 2
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


@pytest.mark.parametrize("name,marker", [(COMPLETE[0], "roles-v21"),
                                        (INCOMPLETE[0], "roles-v23")])
def test_v25_cli_measure_source_branch(name: str, marker: str, tmp_path: Path) -> None:
    _, source, config = _saved(name)
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    output = tmp_path / "measure.json"
    assert results_cli.main(["measure", "--interactive", "--packet-profile", "focused-v25",
                             "--projection", str(source_path), "--config", str(config_path),
                             "--output", str(output)]) == 0
    assert json.loads(output.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format=marker).packet_digest


def test_v25_cli_author_replay_partial_uses_medium(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(old.evidence.source.model_dump_json())
    config_path.write_text(old.config.model_dump_json())
    from award_agent.results import interactive_adapter

    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    output = tmp_path / "artifact.json"
    assert results_cli.main(["author", "--interactive", "--packet-profile", "focused-v25",
                             "--projection", str(source_path), "--config", str(config_path),
                             "--live", "--output", str(output)]) == 0
    assert [request["reasoning"]["effort"] for request in writer.requests] == ["none", "medium"]
    artifact = parse_focused_artifact(output.read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v23"
    replay = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(output), "--output", str(replay)]) == 0
