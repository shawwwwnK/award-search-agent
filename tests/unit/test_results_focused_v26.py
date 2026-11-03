"""V26 spends selector effort only on incomplete source cases."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer
from test_results_focused_v23 import SavedWriter
from test_results_focused_v24 import COMPLETE, RUNS, _saved

from award_agent.cli import results as results_cli
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_comparison_contracts import FocusedResultsArtifactV11


@pytest.mark.parametrize("name", COMPLETE)
def test_complete_request_and_delivery_exactly_match_saved_v23(name: str) -> None:
    old, source, config = _saved(name)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    new = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v26")
    assert isinstance(new, FocusedResultsArtifactV11)
    assert writer.requests == [old.passes[0].request, old.passes[1].request]
    assert new.resolved == old.resolved
    assert new.selector_prepared.packet["selection_format"] == "roles-v21"
    assert new.focus_prepared is not None
    assert new.focus_prepared.packet["composition_format"] == "complete-v19"


def test_partial_changes_only_selector_effort_and_markers_from_v25() -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    source, config = old.evidence.source, old.config
    previous_writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    previous = run_focused_results(source, config, previous_writer, FakeMeasurer(), profile="focused-v25")
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    current = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v26")
    assert isinstance(previous, FocusedResultsArtifactV11)
    assert isinstance(current, FocusedResultsArtifactV11)
    assert current.selector_prepared.packet["selection_format"] == "roles-v24"
    assert current.focus_prepared is not None and previous.focus_prepared is not None
    assert current.focus_prepared.packet["composition_format"] == "complete-v22"
    assert [request["reasoning"]["effort"] for request in writer.requests] == ["low", "medium"]
    assert len(writer.requests) == 2
    for index, (old_request, new_request) in enumerate(zip(previous_writer.requests,
                                                             writer.requests, strict=True)):
        normalized = deepcopy(new_request)
        normalized["input"] = json.loads(str(normalized["input"]))
        normalized["input"]["packet"]["selection_format"] = "roles-v23"
        if index == 0:
            normalized["reasoning"] = {"effort": "none"}
        else:
            normalized["input"]["packet"]["composition_format"] = "complete-v21"
        comparison = deepcopy(old_request)
        comparison["input"] = json.loads(str(comparison["input"]))
        assert normalized == comparison
    normalized_focus = deepcopy(current.focus_prepared.packet)
    normalized_focus["selection_format"] = "roles-v23"
    normalized_focus["composition_format"] = "complete-v21"
    assert normalized_focus == previous.focus_prepared.packet
    assert replay_focused_results(parse_focused_artifact(current.model_dump_json())) == current.resolved
    assert replay_focused_results(previous) == previous.resolved
    forged = current.model_dump(mode="json")
    forged["selector_settings"]["reasoning_effort"] = "none"
    with pytest.raises(ValueError, match="settings"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


def test_partial_failed_check_repairs_with_low_effort_and_replays() -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    changed = json.loads(old.passes[1].raw_wire)
    changed["blocks"][0]["v"] += " A1 is an internal alias."
    writer = SavedWriter([old.passes[0].raw_wire, json.dumps(changed), old.passes[1].raw_wire])
    artifact = run_focused_results(old.evidence.source, old.config, writer,
                                   FakeMeasurer(), profile="focused-v26")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "low", "medium", "low"]
    assert len(artifact.passes) == 3
    assert artifact.passes[1].outcome == "recoverable"
    assert any(f.outcome == "failed" for f in artifact.passes[1].findings)
    assert json.loads(str(writer.requests[2]["input"]))["packet"] == json.loads(
        str(writer.requests[1]["input"]))["packet"]
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


def test_cli_measure_partial(tmp_path: Path) -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    source, config = old.evidence.source, old.config
    source_path, config_path, output = (tmp_path / name for name in
                                        ("source.json", "config.json", "measure.json"))
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    assert results_cli.main(["measure", "--interactive", "--packet-profile", "focused-v26",
                             "--projection", str(source_path), "--config", str(config_path),
                             "--output", str(output)]) == 0
    assert json.loads(output.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format="roles-v24").packet_digest


def test_selector_failure_still_identifies_v26_policy() -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    writer = SavedWriter(["{}"])
    artifact = run_focused_results(old.evidence.source, old.config, writer,
                                   FakeMeasurer(), profile="focused-v26")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(artifact.passes) == 1
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v24"
    assert artifact.selector_settings.reasoning_effort == "low"
    assert artifact.composer_settings.reasoning_effort == "medium"
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) is None


def test_incomplete_marker_rejects_complete_source() -> None:
    old, _, _ = _saved(COMPLETE[0])
    forged = old.model_dump(mode="json")
    forged["selector_prepared"]["packet"]["selection_format"] = "roles-v24"
    forged["selector_settings"]["reasoning_effort"] = "low"
    forged["composer_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="complete journey source"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


def test_cli_author_replay_partial(tmp_path: Path,
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
    assert results_cli.main(["author", "--interactive", "--packet-profile", "focused-v26",
                             "--projection", str(source_path), "--config", str(config_path),
                             "--live", "--output", str(output)]) == 0
    assert [request["reasoning"]["effort"] for request in writer.requests] == ["low", "medium"]
    artifact = parse_focused_artifact(output.read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v24"
    replay = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(output), "--output", str(replay)]) == 0
