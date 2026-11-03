"""V29 groups incomplete selector leads without changing their source facts."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer
from test_results_focused_v23 import SavedWriter
from test_results_focused_v24 import COMPLETE, INCOMPLETE, RUNS, _saved
from test_results_focused_v28 import _choice, _prepared

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
from award_agent.results.focused_selector_records import selector_packet


def _grouped() -> tuple[dict[str, object], dict[str, object]]:
    _, source, config = _saved(INCOMPLETE[0])
    old = prepare_focused_selector(source, config, selection_format="roles-v27")
    new = prepare_focused_selector(source, config, selection_format="roles-v29")
    return selector_packet(old), selector_packet(new)


def test_grouped_leads_invert_exactly_to_all_original_named_records() -> None:
    flat, grouped = _grouped()
    records = flat["lead_records"]
    assert isinstance(records, list) and len(records) == 378
    assert "lead_records" not in grouped and "lead_rows" not in grouped
    groups = grouped["lead_program_groups"]
    assert isinstance(groups, list)
    assert len(groups) == 13
    seen: list[tuple[int, dict[str, object]]] = []
    first_programs: list[object] = []
    for group in groups:
        program = group["program"]
        assert not any(type(program) is type(old) and program == old for old in first_programs)
        first_programs.append(program)
        ordinals: list[int] = []
        for member in group["members"]:
            ordinal, record = member["source_ordinal"], member["record"]
            assert type(ordinal) is int
            assert type(program) is type(record["program"]) and program == record["program"]
            assert record["original_quote"] == records[ordinal]["original_quote"]
            assert json.dumps(record, sort_keys=True) == json.dumps(records[ordinal], sort_keys=True)
            ordinals.append(ordinal)
            seen.append((ordinal, record))
        assert ordinals == sorted(ordinals)
    assert [ordinal for ordinal, _ in sorted(seen)] == list(range(378))
    assert [record for _, record in sorted(seen)] == records
    normalized = deepcopy(grouped)
    normalized["selection_format"] = "roles-v27"
    normalized["lead_records"] = [record for _, record in sorted(seen)]
    normalized.pop("lead_program_groups")
    normalized["legend"]["lead_records"] = normalized["legend"].pop("lead_program_groups")
    assert normalized == flat


def test_grouping_preserves_unknown_and_typed_program_values() -> None:
    _, source, config = _saved(INCOMPLETE[0])
    prepared = prepare_focused_selector(source, config, selection_format="roles-v29")
    packet = deepcopy(prepared.packet)
    column = packet["legend"]["lead_row"].index("program")
    values = (None, 0, False, "unknown", "UNKNOWN")
    for index, value in enumerate(values):
        packet["lead_rows"][index][column] = value
    grouped = selector_packet(prepared.model_copy(update={"packet": packet}))
    members = [member for group in grouped["lead_program_groups"] for member in group["members"]]
    by_ordinal = {item["source_ordinal"]: item["record"]["program"] for item in members}
    for index, value in enumerate(values):
        assert type(by_ordinal[index]) is type(value) and by_ordinal[index] == value


@pytest.mark.parametrize("name,marker,efforts", [
    (COMPLETE[0], "roles-v28", ["low", "medium"]),
    (INCOMPLETE[0], "roles-v29", ["medium", "low"])])
def test_branch_settings_caps_and_replay(name: str, marker: str, efforts: list[str]) -> None:
    source, config, prepared = _prepared(name, marker)
    journeys, cash, leads = _roles(prepared.structured, source)
    kind, main = ("j", journeys) if journeys else ("l", leads)
    raw = json.dumps({"choices": [_choice(kind, main[0]), _choice("b", cash[0])]})
    writer = SavedWriter([raw, '{"blocks":[]}'])
    previous_writer = SavedWriter([raw, '{"blocks":[]}'])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v29")
    previous = run_focused_results(source, config, previous_writer, FakeMeasurer(),
                                   profile="focused-v28")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert isinstance(previous, FocusedResultsArtifactV11)
    assert len(writer.requests) == 2
    assert [request["reasoning"]["effort"] for request in writer.requests] == efforts
    assert artifact.selector_prepared.packet["selection_format"] == marker
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == (
        "complete-v26" if kind == "j" else "complete-v27")
    assert writer.requests[0]["text"]["format"]["schema"]["properties"]["choices"]["maxItems"] == 3
    assert writer.requests[0]["text"] == previous_writer.requests[0]["text"]
    assert writer.requests[1]["instructions"] == previous_writer.requests[1]["instructions"]
    assert writer.requests[1]["text"] == previous_writer.requests[1]["text"]
    new_author = json.loads(str(writer.requests[1]["input"]))
    old_author = json.loads(str(previous_writer.requests[1]["input"]))
    new_author["packet"]["selection_format"] = "roles-v26" if kind == "j" else "roles-v27"
    new_author["packet"]["composition_format"] = "complete-v24" if kind == "j" else "complete-v25"
    assert new_author == old_author
    if kind == "j":
        new_selector = json.loads(str(writer.requests[0]["input"]))
        old_selector = json.loads(str(previous_writer.requests[0]["input"]))
        new_selector["packet"]["selection_format"] = "roles-v26"
        assert new_selector == old_selector
        assert writer.requests[0]["instructions"] == previous_writer.requests[0]["instructions"]
    else:
        assert "lead_program_groups" in str(writer.requests[0]["instructions"])
        assert "lead_records" not in str(writer.requests[0]["instructions"])
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    forged = artifact.model_dump(mode="json")
    forged["selector_settings"]["reasoning_effort"] = "none"
    with pytest.raises(ValueError, match="settings"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))
    decode_planned({"choices": [_choice(kind, main[0]), _choice(kind, main[1]),
                                _choice("b", cash[0])]}, prepared.structured, source,
                   max_references=3, max_nonbenchmark_references=2)
    with pytest.raises(ValueError, match="nonbenchmark"):
        decode_planned({"choices": [_choice(kind, item) for item in main[:3]]},
                       prepared.structured, source, max_references=3,
                       max_nonbenchmark_references=2)


@pytest.mark.parametrize("name,marker,effort", [
    (COMPLETE[0], "roles-v28", "low"), (INCOMPLETE[0], "roles-v29", "medium")])
def test_failed_selector_still_identifies_profile(name: str, marker: str, effort: str) -> None:
    _, source, config = _saved(name)
    artifact = run_focused_results(source, config, SavedWriter(["{}"]),
                                   FakeMeasurer(), profile="focused-v29")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(artifact.passes) == 1
    assert artifact.selector_prepared.packet["selection_format"] == marker
    assert artifact.selector_settings.reasoning_effort == effort
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) is None


def test_v29_branch_guards_and_historical_v28_replay() -> None:
    for name, marker, effort, message in (
            (COMPLETE[0], "roles-v29", "medium", "complete journey source"),
            (INCOMPLETE[0], "roles-v28", "low", "lacks a complete journey source")):
        old, _, _ = _saved(name)
        forged = old.model_dump(mode="json")
        forged["selector_prepared"]["packet"]["selection_format"] = marker
        forged["selector_settings"]["reasoning_effort"] = effort
        forged["composer_settings"]["reasoning_effort"] = (
            "low" if marker == "roles-v29" else "medium")
        with pytest.raises(ValueError, match=message):
            replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))
    _, source, config = _saved(INCOMPLETE[0])
    prepared = prepare_focused_selector(source, config, selection_format="roles-v27")
    _, cash, leads = _roles(prepared.structured, source)
    raw = json.dumps({"choices": [_choice("l", leads[0]), _choice("b", cash[0])]})
    previous = run_focused_results(source, config, SavedWriter([raw, '{"blocks":[]}']),
                                   FakeMeasurer(), profile="focused-v28")
    assert isinstance(previous, FocusedResultsArtifactV11)
    assert replay_focused_results(parse_focused_artifact(previous.model_dump_json())) == previous.resolved
    assert previous.selector_settings.reasoning_effort == "medium"
    assert previous.composer_settings.reasoning_effort == "low"


@pytest.mark.parametrize("name,marker", [(COMPLETE[0], "roles-v28"),
                                         (INCOMPLETE[0], "roles-v29")])
def test_v29_overcap_selection_rejected_before_authoring(name: str, marker: str) -> None:
    source, config, prepared = _prepared(name, marker)
    journeys, cash, leads = _roles(prepared.structured, source)
    kind, main = ("j", journeys) if journeys else ("l", leads)
    raw = json.dumps({"choices": [_choice(kind, ref) for ref in main[:3]]})
    writer = SavedWriter([raw])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v29")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(writer.requests) == len(artifact.passes) == 1
    assert artifact.passes[0].outcome != "recoverable"
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) is None
    with pytest.raises(ValueError, match="3-reference"):
        decode_planned({"choices": [_choice(kind, ref) for ref in main[:3]] +
                                    [_choice("b", cash[0])]}, prepared.structured, source,
                       max_references=3, max_nonbenchmark_references=2)


def test_incomplete_failed_draft_uses_low_correction() -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[1].raw_wire is not None
    source, config, prepared = _prepared(INCOMPLETE[0], "roles-v29")
    _, cash, leads = _roles(prepared.structured, source)
    raw = json.dumps({"choices": [_choice("l", leads[0]), _choice("l", leads[1]),
                                  _choice("b", cash[0])]})
    document = json.loads(old.passes[1].raw_wire)
    document["blocks"] = [block for block in document["blocks"]
                          if not (block.get("k") == "l" and str(block.get("r", "")).startswith("A37@"))]
    bad = deepcopy(document)
    bad["blocks"][0]["v"] += " A1 is an internal alias."
    writer = SavedWriter([raw, json.dumps(bad), json.dumps(document)])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v29")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "medium", "low", "low"]
    assert len(artifact.passes) == 3
    assert artifact.passes[1].outcome == "recoverable"
    assert any(f.outcome == "failed" for f in artifact.passes[1].findings)
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


@pytest.mark.parametrize("name,marker", [(COMPLETE[0], "roles-v28"),
                                         (INCOMPLETE[0], "roles-v29")])
def test_cli_measure_author_replay(name: str, marker: str, tmp_path: Path,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
    source, config, prepared = _prepared(name, marker)
    journeys, cash, leads = _roles(prepared.structured, source)
    kind, main = ("j", journeys) if journeys else ("l", leads)
    wire = json.dumps({"choices": [_choice(kind, main[0]), _choice("b", cash[0])]})
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", "focused-v29",
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
