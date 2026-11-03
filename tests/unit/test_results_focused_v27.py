"""V27 changes only incomplete selector effort relative to V26."""

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
def test_complete_requests_and_delivery_are_v23_exact(name: str) -> None:
    old, source, config = _saved(name)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    current = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v27")
    assert isinstance(current, FocusedResultsArtifactV11)
    assert writer.requests == [old.passes[0].request, old.passes[1].request]
    assert current.resolved == old.resolved
    assert current.selector_prepared.packet["selection_format"] == "roles-v21"
    assert current.focus_prepared is not None
    assert current.focus_prepared.packet["composition_format"] == "complete-v19"


def test_partial_request_payload_and_guidance_are_v26_exact_after_marker_effort_normalization() -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    wires = [old.passes[0].raw_wire, old.passes[1].raw_wire]
    v26_writer, v27_writer = SavedWriter(wires), SavedWriter(wires)
    previous = run_focused_results(old.evidence.source, old.config, v26_writer,
                                   FakeMeasurer(), profile="focused-v26")
    current = run_focused_results(old.evidence.source, old.config, v27_writer,
                                  FakeMeasurer(), profile="focused-v27")
    assert isinstance(previous, FocusedResultsArtifactV11)
    assert isinstance(current, FocusedResultsArtifactV11)
    assert len(v27_writer.requests) == 2
    assert [request["reasoning"]["effort"] for request in v27_writer.requests] == [
        "medium", "medium"]
    assert current.selector_prepared.packet["selection_format"] == "roles-v25"
    assert current.focus_prepared is not None and previous.focus_prepared is not None
    assert current.focus_prepared.packet["composition_format"] == "complete-v23"
    for index, (before, after) in enumerate(zip(v26_writer.requests, v27_writer.requests,
                                                  strict=True)):
        normalized = deepcopy(after)
        normalized["input"] = json.loads(str(normalized["input"]))
        normalized["input"]["packet"]["selection_format"] = "roles-v24"
        if index == 0:
            normalized["reasoning"] = {"effort": "low"}
        else:
            normalized["input"]["packet"]["composition_format"] = "complete-v22"
        comparison = deepcopy(before)
        comparison["input"] = json.loads(str(comparison["input"]))
        assert normalized == comparison
    normalized_focus = deepcopy(current.focus_prepared.packet)
    normalized_focus["selection_format"] = "roles-v24"
    normalized_focus["composition_format"] = "complete-v22"
    assert normalized_focus == previous.focus_prepared.packet
    assert replay_focused_results(parse_focused_artifact(current.model_dump_json())) == current.resolved
    assert replay_focused_results(previous) == previous.resolved
    forged = current.model_dump(mode="json")
    forged["selector_settings"]["reasoning_effort"] = "low"
    with pytest.raises(ValueError, match="settings"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


def test_selector_failure_retains_policy_marker_and_historical_guard() -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    artifact = run_focused_results(old.evidence.source, old.config, SavedWriter(["{}"]),
                                   FakeMeasurer(), profile="focused-v27")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(artifact.passes) == 1
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v25"
    assert artifact.selector_settings.reasoning_effort == "medium"
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) is None
    complete, _, _ = _saved(COMPLETE[0])
    forged = complete.model_dump(mode="json")
    forged["selector_prepared"]["packet"]["selection_format"] = "roles-v25"
    forged["selector_settings"]["reasoning_effort"] = "medium"
    forged["composer_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="complete journey source"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


def test_failed_draft_uses_one_low_correction() -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    bad = json.loads(old.passes[1].raw_wire)
    bad["blocks"][0]["v"] += " A1 is an internal alias."
    writer = SavedWriter([old.passes[0].raw_wire, json.dumps(bad), old.passes[1].raw_wire])
    artifact = run_focused_results(old.evidence.source, old.config, writer,
                                   FakeMeasurer(), profile="focused-v27")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "medium", "medium", "low"]
    assert len(artifact.passes) == 3
    assert artifact.passes[1].outcome == "recoverable"
    assert any(f.outcome == "failed" for f in artifact.passes[1].findings)
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


def test_cli_measure_and_author_partial(tmp_path: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(old.evidence.source.model_dump_json())
    config_path.write_text(old.config.model_dump_json())
    measure = tmp_path / "measure.json"
    assert results_cli.main(["measure", "--interactive", "--packet-profile", "focused-v27",
                             "--projection", str(source_path), "--config", str(config_path),
                             "--output", str(measure)]) == 0
    assert json.loads(measure.read_text())["packet_digest"] == prepare_focused_selector(
        old.evidence.source, old.config, selection_format="roles-v25").packet_digest
    from award_agent.results import interactive_adapter

    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    output = tmp_path / "artifact.json"
    assert results_cli.main(["author", "--interactive", "--packet-profile", "focused-v27",
                             "--projection", str(source_path), "--config", str(config_path),
                             "--live", "--output", str(output)]) == 0
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "medium", "medium"]
    assert isinstance(parse_focused_artifact(output.read_bytes()), FocusedResultsArtifactV11)
    replay = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(output), "--output", str(replay)]) == 0
