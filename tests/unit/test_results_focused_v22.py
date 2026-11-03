"""V22 bounds selected authoring evidence without trimming the source inventory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer
from test_results_focused_v19 import _FrozenV19Writer
from test_results_focused_v21 import _source

from award_agent.cli import results as results_cli
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_patch_contracts import FocusedResultsArtifactV12
from award_agent.results.focused_selection_plan import decode


def _run(selection_wire: str, profile: str = "focused-v22") -> tuple[FocusedResultsArtifactV12, _FrozenV19Writer]:
    source, config, _ = _source("scout-v19-admitted")
    writer = _FrozenV19Writer(selection_wire)
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile=profile)
    assert isinstance(artifact, FocusedResultsArtifactV12)
    return artifact, writer


def test_v22_rejects_five_refs_without_truncation_or_extra_calls() -> None:
    source, config, selection = _source("scout-v19-admitted")
    prepared = prepare_focused_selector(source, config, selection_format="roles-v21")
    original = json.loads(selection)["choices"]
    assert len(original) == 4
    selected = {row["r"] for row in original}
    extra = next(row[0] for row in prepared.packet["journey_rows"] if row[0] not in selected)
    oversized = {"choices": [*original, {"k": "j", "r": extra,
                                        "purpose": "Another source comparator", "compare_to": None}]}
    with pytest.raises(ValueError, match="4-reference"):
        decode(oversized, prepared.structured, source, max_references=4)
    artifact, writer = _run(json.dumps(oversized))
    assert len(writer.requests) == len(artifact.passes) == 1
    assert writer.requests[0]["text"]["format"]["schema"]["properties"]["choices"]["maxItems"] == 4
    assert artifact.passes[0].outcome == "generation_error"
    assert artifact.passes[0].failure_subtype == "schema_error"
    assert artifact.passes[0].raw_wire is not None
    assert len(json.loads(artifact.passes[0].raw_wire)["choices"]) == 5
    assert artifact.focus_prepared is None and artifact.resolved is None
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) is None


@pytest.mark.parametrize("count", [1, 4])
def test_v22_accepts_one_and_four_exact_refs_with_full_inventory(count: int) -> None:
    source, config, selection = _source("scout-v19-admitted")
    choices = json.loads(selection)["choices"][:count]
    if count == 1:
        choices[0]["compare_to"] = None
    artifact, writer = _run(json.dumps({"choices": choices}))
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v21"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v19"
    assert len(writer.requests) == len(artifact.passes) == 3
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "none", "low", "medium"]
    assert writer.requests[0]["text"]["format"]["schema"]["properties"]["choices"]["maxItems"] == 4
    v21 = prepare_focused_selector(source, config, selection_format="roles-v20")
    v22 = artifact.selector_prepared
    old_packet, new_packet = dict(v21.packet), dict(v22.packet)
    old_packet.pop("selection_format")
    new_packet.pop("selection_format")
    assert old_packet == new_packet
    assert len(new_packet["journey_rows"]) > 4
    assert len(artifact.focus_prepared.packet["editorial_plan"]) == count
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


def test_v22_preserves_v21_requests_after_marker_and_cap_normalization() -> None:
    _, _, selection = _source("scout-v19-admitted")
    old, old_writer = _run(selection, profile="focused-v21")
    new, new_writer = _run(selection)
    assert old.focus_prepared is not None and new.focus_prepared is not None
    assert len(old_writer.requests) == len(new_writer.requests) == 3
    for index, (old_request, new_request) in enumerate(
            zip(old_writer.requests, new_writer.requests, strict=True)):
        old_packet = json.loads(str(old_request["input"]))
        new_packet = json.loads(str(new_request["input"]))
        old_packet["packet"]["selection_format"] = "roles-v21"
        if index:
            old_packet["packet"]["composition_format"] = "complete-v19"
            assert old_request["instructions"] == new_request["instructions"]
        else:
            assert old_request["text"]["format"]["schema"]["properties"]["choices"]["maxItems"] == 8
            assert new_request["text"]["format"]["schema"]["properties"]["choices"]["maxItems"] == 4
            assert old_request["instructions"].replace(
                "strict maximum of eight references TOTAL",
                "strict maximum of four references TOTAL") == new_request["instructions"]
        assert old_packet == new_packet
    assert replay_focused_results(parse_focused_artifact(old.model_dump_json())) == old.resolved


def test_v22_cli_explicit_measure_author_replay(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    source, config, selection = _source("scout-v19-admitted")
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", "focused-v22", "--projection",
              str(source_path), "--config", str(config_path)]
    measure_path = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    assert json.loads(measure_path.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format="roles-v21").packet_digest
    from award_agent.results import interactive_adapter

    writer = _FrozenV19Writer(selection)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    artifact_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(artifact_path)]) == 0
    assert len(writer.requests) == 3
    assert json.loads(artifact_path.read_text())["contract_version"] == "results-artifact-v12"
    replay_path = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(artifact_path),
                             "--output", str(replay_path)]) == 0
