"""Final V30 changes only incomplete selector guidance."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer
from test_results_focused_v23 import SavedWriter
from test_results_focused_v24 import RUNS
from test_results_focused_v28 import _choice

from award_agent.cli import results as results_cli
from award_agent.results import DEFAULT_RESULTS_PROFILE
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_comparison_contracts import FocusedResultsArtifactV11
from award_agent.results.focused_packet import _roles
from award_agent.results.focused_selector_records import selector_packet

COMPLETE = ("scout-v29-admitted", "scout-v29-conditional")
PARTIAL = "scout-v29-incomplete"


def _saved(name: str) -> FocusedResultsArtifactV11:
    artifact = parse_focused_artifact((RUNS / name / "artifact.json").read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV11)
    return artifact


@pytest.mark.parametrize("name", COMPLETE)
def test_complete_branch_exact_v29_requests_document_and_delivery(name: str) -> None:
    old = _saved(name)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    artifact = run_focused_results(old.evidence.source, old.config, writer,
                                   FakeMeasurer(), profile="focused-v30")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v28"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v26"
    assert writer.requests == [old.passes[0].request, old.passes[1].request]
    assert artifact.passes[1].document == old.passes[1].document
    assert artifact.resolved == old.resolved
    assert artifact.delivery_outcome == old.delivery_outcome
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == old.resolved


def test_partial_source_and_authoring_requests_are_v29_exact_after_markers() -> None:
    old = _saved(PARTIAL)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    artifact = run_focused_results(old.evidence.source, old.config, writer,
                                   FakeMeasurer(), profile="focused-v30")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v30"
    assert artifact.focus_prepared is not None and old.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v28"
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "medium", "low"]
    old_selector = selector_packet(old.selector_prepared)
    new_selector = selector_packet(artifact.selector_prepared)
    new_selector["selection_format"] = "roles-v29"
    assert new_selector == old_selector
    assert "lead_records" not in new_selector and "lead_program_groups" in new_selector
    assert len([member for group in new_selector["lead_program_groups"]
                for member in group["members"]]) == 378
    old_author = deepcopy(old.passes[1].request)
    new_author = deepcopy(writer.requests[1])
    new_author["input"] = json.loads(str(new_author["input"]))
    old_author["input"] = json.loads(str(old_author["input"]))
    new_author["input"]["packet"]["selection_format"] = "roles-v29"
    new_author["input"]["packet"]["composition_format"] = "complete-v27"
    assert new_author == old_author
    assert artifact.passes[1].document == old.passes[1].document
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    assert replay_focused_results(old) == old.resolved


def test_partial_selector_guidance_changes_only_accepted_clause() -> None:
    old = _saved(PARTIAL)
    assert old.passes[0].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, '{"blocks":[]}'])
    run_focused_results(old.evidence.source, old.config, writer,
                        FakeMeasurer(), profile="focused-v30")
    old_text = str(old.passes[0].request["instructions"])
    new_text = str(writer.requests[0]["instructions"])
    previous = ("Do not compare points across programs as economic value, or prices across "
                "currencies or unknown scopes as total savings.")
    accepted = ("Each rewards program has its own points unit. A smaller number in another "
                "program is not a supported advantage, even when called stated, nominal, "
                "or potential, and cannot supply the upside of a points-versus-fees "
                "tradeoff. Original program quotes remain reportable separately. Before "
                "retaining a comparator, remove cross-program numerical magnitude from the "
                "rationale and identify the source-supported benefit for which a traveler "
                "might accept its downside. An unspecified program preference alone does "
                "not establish that benefit. If no benefit remains, examine other leads in "
                "the full inventory. A supported conditional choice can suffice; no "
                "program, date, cabin, or count quota applies. Do not compare prices across "
                "currencies or unknown scopes as total savings.")
    assert new_text == old_text.replace(previous, accepted)
    assert writer.requests[0]["text"] == old.passes[0].request["text"]


def test_partial_selector_failure_retains_new_marker_and_replay_guard() -> None:
    old = _saved(PARTIAL)
    artifact = run_focused_results(old.evidence.source, old.config, SavedWriter(["{}"]),
                                   FakeMeasurer(), profile="focused-v30")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(artifact.passes) == 1
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v30"
    assert artifact.selector_settings.reasoning_effort == "medium"
    assert artifact.composer_settings.reasoning_effort == "low"
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) is None
    forged = artifact.model_dump(mode="json")
    forged["selector_settings"]["reasoning_effort"] = "low"
    with pytest.raises(ValueError, match="settings"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


def test_v30_replay_rejects_forged_source_branch() -> None:
    complete = _saved(COMPLETE[0]).model_dump(mode="json")
    complete["selector_prepared"]["packet"]["selection_format"] = "roles-v30"
    complete["selector_settings"]["reasoning_effort"] = "medium"
    complete["composer_settings"]["reasoning_effort"] = "low"
    with pytest.raises(ValueError, match="complete journey source"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(complete))
    partial = _saved(PARTIAL).model_dump(mode="json")
    partial["selector_prepared"]["packet"]["selection_format"] = "roles-v28"
    partial["selector_settings"]["reasoning_effort"] = "low"
    partial["composer_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="lacks a complete journey source"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(partial))


def test_v30_caps_and_conditional_low_repair() -> None:
    old = _saved(PARTIAL)
    source, config = old.evidence.source, old.config
    prepared = prepare_focused_selector(source, config, selection_format="roles-v30")
    _, _, leads = _roles(prepared.structured, source)
    overcap = json.dumps({"choices": [_choice("l", ref) for ref in leads[:3]]})
    stopped = run_focused_results(source, config, SavedWriter([overcap]),
                                  FakeMeasurer(), profile="focused-v30")
    assert isinstance(stopped, FocusedResultsArtifactV11)
    assert len(stopped.passes) == 1 and stopped.passes[0].outcome != "recoverable"
    assert replay_focused_results(parse_focused_artifact(stopped.model_dump_json())) is None
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    bad = json.loads(old.passes[1].raw_wire)
    bad["blocks"][0]["v"] += " A2 is an internal alias."
    writer = SavedWriter([old.passes[0].raw_wire, json.dumps(bad), old.passes[1].raw_wire])
    repaired = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v30")
    assert isinstance(repaired, FocusedResultsArtifactV11)
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "medium", "low", "low"]
    assert len(repaired.passes) == 3
    assert repaired.passes[1].outcome == "recoverable"
    assert any(f.outcome == "failed" for f in repaired.passes[1].findings)
    assert replay_focused_results(parse_focused_artifact(repaired.model_dump_json())) == repaired.resolved


def test_cli_partial_measure_author_replay(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    old = _saved(PARTIAL)
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(old.evidence.source.model_dump_json())
    config_path.write_text(old.config.model_dump_json())
    common = ["--interactive", "--packet-profile", "focused-v30",
              "--projection", str(source_path), "--config", str(config_path)]
    measure = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure)]) == 0
    assert json.loads(measure.read_text())["packet_digest"] == prepare_focused_selector(
        old.evidence.source, old.config, selection_format="roles-v30").packet_digest
    from award_agent.results import interactive_adapter

    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    output = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(output)]) == 0
    artifact = parse_focused_artifact(output.read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v30"
    replay = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(output), "--output", str(replay)]) == 0
    assert DEFAULT_RESULTS_PROFILE == "focused-v27"
