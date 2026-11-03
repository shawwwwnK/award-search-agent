"""V28 keeps source facts while narrowing the selected authoring bundle."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer
from test_results_focused_v23 import SavedWriter
from test_results_focused_v24 import COMPLETE, INCOMPLETE, RUNS, _saved

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
from award_agent.results.focused_selection_plan import decode as decode_planned


def _choice(kind: str, ref: str) -> dict[str, object]:
    return {"k": kind, "r": ref, "purpose": "Check exact source evidence", "compare_to": None}


def _prepared(name: str, marker: str):
    _, source, config = _saved(name)
    prepared = prepare_focused_selector(source, config, selection_format=marker)
    return source, config, prepared


@pytest.mark.parametrize("name,marker,kind", [
    (COMPLETE[0], "roles-v26", "j"), (INCOMPLETE[0], "roles-v27", "l")])
def test_three_total_two_main_one_benchmark_caps_without_truncation(
        name: str, marker: str, kind: str) -> None:
    source, _, prepared = _prepared(name, marker)
    journeys, cash, leads = _roles(prepared.structured, source)
    main = journeys if kind == "j" else leads
    assert len(main) >= 3 and cash
    choices = [_choice(kind, main[0]), _choice(kind, main[1]), _choice("b", cash[0])]
    selected = decode_planned({"choices": choices}, prepared.structured, source,
                              max_references=3, max_nonbenchmark_references=2)
    assert len(selected.journey_ids) + len(selected.incomplete_observation_ids) == 2
    assert selected.benchmark_observation_id is not None
    for accepted in (choices[:1], choices[:2], choices):
        decode_planned({"choices": accepted}, prepared.structured, source,
                       max_references=3, max_nonbenchmark_references=2)
    with pytest.raises(ValueError, match="nonbenchmark"):
        decode_planned({"choices": choices[:2] + [_choice(kind, main[2])]},
                       prepared.structured, source, max_references=3,
                       max_nonbenchmark_references=2)
    with pytest.raises(ValueError, match="3-reference"):
        decode_planned({"choices": choices + [_choice(kind, main[2])]},
                       prepared.structured, source, max_references=3,
                       max_nonbenchmark_references=2)
    with pytest.raises(ValueError, match="benchmark"):
        decode_planned({"choices": [_choice(kind, main[0]), _choice("b", cash[0]),
                                    _choice("b", cash[1])]}, prepared.structured, source,
                       max_references=3, max_nonbenchmark_references=2)
    # The former four-reference policy remains independently valid.
    decode_planned({"choices": choices + [_choice(kind, main[2])]},
                   prepared.structured, source, max_references=4)


@pytest.mark.parametrize("name,marker,previous", [
    (COMPLETE[0], "roles-v26", "focused-v27"),
    (INCOMPLETE[0], "roles-v27", "focused-v27")])
def test_branch_settings_source_packet_and_replay(name: str, marker: str,
                                                   previous: str) -> None:
    source, config, prepared = _prepared(name, marker)
    journeys, cash, leads = _roles(prepared.structured, source)
    kind, main = ("j", journeys) if journeys else ("l", leads)
    raw = json.dumps({"choices": [_choice(kind, main[0]), _choice(kind, main[1]),
                                  _choice("b", cash[0])]})
    wires = [raw, '{"blocks":[]}']
    writer, old_writer = SavedWriter(wires), SavedWriter(wires)
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v28")
    old = run_focused_results(source, config, old_writer, FakeMeasurer(), profile=previous)
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert isinstance(old, FocusedResultsArtifactV11)
    assert len(writer.requests) == 2
    assert artifact.selector_prepared.packet["selection_format"] == marker
    assert artifact.focus_prepared is not None and old.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == (
        "complete-v24" if kind == "j" else "complete-v25")
    assert [request["reasoning"]["effort"] for request in writer.requests] == (
        ["none", "medium"] if kind == "j" else ["medium", "low"])
    assert writer.requests[0]["text"]["format"]["schema"]["properties"]["choices"]["maxItems"] == 3
    assert "strict maximum of three references TOTAL" in str(writer.requests[0]["instructions"])
    assert "at most two nonbenchmark" in str(writer.requests[0]["instructions"])
    for index, (before, after) in enumerate(zip(old_writer.requests, writer.requests,
                                                  strict=True)):
        a, b = json.loads(str(after["input"])), json.loads(str(before["input"]))
        a["packet"]["selection_format"] = "roles-v21" if kind == "j" else "roles-v25"
        if index == 1:
            a["packet"]["composition_format"] = "complete-v19" if kind == "j" else "complete-v23"
        assert a == b
        if index == 0:
            old_instructions = str(before["instructions"])
            guide = "\n" + config.authoring_guidance
            assert old_instructions.endswith(guide)
            expected_base = old_instructions.removesuffix(guide).replace(
                "strict maximum of four references TOTAL",
                "strict maximum of three references TOTAL")
            assert after["instructions"] == expected_base + (
                    " Choose at most two nonbenchmark journey or lead references combined, "
                    "and at most one direct cash benchmark. These are ceilings, not counts "
                    "to fill; never truncate or substitute a selected reference.") + guide
        else:
            assert after["instructions"] == before["instructions"]
            assert after["text"] == before["text"]
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    forged = artifact.model_dump(mode="json")
    forged["selector_settings"]["reasoning_effort"] = "low"
    with pytest.raises(ValueError, match="settings"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


@pytest.mark.parametrize("name,marker,selector_effort,author_effort", [
    (COMPLETE[0], "roles-v26", "none", "medium"),
    (INCOMPLETE[0], "roles-v27", "medium", "low")])
def test_selector_failure_keeps_branch_policy_marker(name: str, marker: str,
                                                     selector_effort: str,
                                                     author_effort: str) -> None:
    _, source, config = _saved(name)
    artifact = run_focused_results(source, config, SavedWriter(["{}"]),
                                   FakeMeasurer(), profile="focused-v28")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(artifact.passes) == 1
    assert artifact.selector_prepared.packet["selection_format"] == marker
    assert artifact.selector_settings.reasoning_effort == selector_effort
    assert artifact.composer_settings.reasoning_effort == author_effort
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) is None


@pytest.mark.parametrize("name,marker", [(COMPLETE[0], "roles-v26"),
                                         (INCOMPLETE[0], "roles-v27")])
def test_overcap_selection_stops_before_authoring_and_replays(name: str, marker: str) -> None:
    source, config, prepared = _prepared(name, marker)
    journeys, _, leads = _roles(prepared.structured, source)
    kind, main = ("j", journeys) if journeys else ("l", leads)
    raw = json.dumps({"choices": [_choice(kind, ref) for ref in main[:3]]})
    writer = SavedWriter([raw])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v28")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(writer.requests) == len(artifact.passes) == 1
    assert artifact.passes[0].outcome != "recoverable"
    assert artifact.selector_prepared.packet["selection_format"] == marker
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) is None


def test_v28_replay_rejects_wrong_source_branch() -> None:
    old, _, _ = _saved(COMPLETE[0])
    forged = old.model_dump(mode="json")
    forged["selector_prepared"]["packet"]["selection_format"] = "roles-v27"
    forged["selector_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="complete journey source"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))
    old, _, _ = _saved(INCOMPLETE[0])
    forged = old.model_dump(mode="json")
    forged["selector_prepared"]["packet"]["selection_format"] = "roles-v26"
    forged["composer_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="lacks a complete journey source"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


def test_incomplete_failed_check_uses_low_correction() -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[1].raw_wire is not None
    source, config, prepared = _prepared(INCOMPLETE[0], "roles-v27")
    _, cash, leads = _roles(prepared.structured, source)
    raw = json.dumps({"choices": [_choice("l", leads[0]), _choice("l", leads[1]),
                                  _choice("b", cash[0])]})
    document = json.loads(old.passes[1].raw_wire)
    document["blocks"] = [block for block in document["blocks"]
                          if not (block.get("k") == "l" and str(block.get("r", "")).startswith("A37@"))]
    bad = deepcopy(document)
    bad["blocks"][0]["v"] += " A1 is an internal alias."
    writer = SavedWriter([raw, json.dumps(bad), json.dumps(document)])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v28")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "medium", "low", "low"]
    assert len(artifact.passes) == 3
    assert artifact.passes[1].outcome == "recoverable"
    assert any(f.outcome == "failed" for f in artifact.passes[1].findings)
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


@pytest.mark.parametrize("name,marker", [(COMPLETE[0], "roles-v26"),
                                         (INCOMPLETE[0], "roles-v27")])
def test_cli_measure_author_replay_branches(name: str, marker: str, tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    source, config, prepared = _prepared(name, marker)
    journeys, cash, leads = _roles(prepared.structured, source)
    kind, main = ("j", journeys) if journeys else ("l", leads)
    wire = json.dumps({"choices": [_choice(kind, main[0]), _choice("b", cash[0])]})
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", "focused-v28",
              "--projection", str(source_path), "--config", str(config_path)]
    measure = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure)]) == 0
    assert json.loads(measure.read_text())["packet_digest"] == prepared.packet_digest
    from award_agent.results import interactive_adapter

    class CliWriter(SavedWriter):
        def author(self, request: dict[str, object], config: object, settings: object) -> str:
            if len(self.requests) == 1:
                packet = json.loads(str(request["input"]))["packet"]
                main_ref = next(ref for ref, record in packet["authoring_records"].items()
                                if record["role"] in {"journey", "lead"})
                benchmark_ref = next(ref for ref, record in packet["authoring_records"].items()
                                     if record["role"] == "benchmark")
                self.wires[1] = json.dumps({"blocks": [
                    {"k": "t", "v": "These selected search results need current verification."},
                    {"k": "p" if kind == "j" else "l", "r": main_ref,
                     "n": "Selected journey" if kind == "j" else "Selected lead",
                     "v": "Check the reported source facts and current availability."},
                    {"k": "b", "r": benchmark_ref, "n": "Direct cash baseline",
                     "v": "This is separate cash context, subject to quote scope."}]})
            return super().author(request, config, settings)

    writer = CliWriter([wire, ""])
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    output = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(output)]) == 0
    artifact = parse_focused_artifact(output.read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == marker
    replay = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(output), "--output", str(replay)]) == 0
    assert DEFAULT_RESULTS_PROFILE == "focused-v27"
