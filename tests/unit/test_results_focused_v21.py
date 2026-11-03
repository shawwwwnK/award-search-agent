"""V21 changes only Luna reasoning allocation over the V20 source contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer
from test_results_focused_v19 import CONFIG, RUNS, _FrozenV19Writer

from award_agent.cli import results as results_cli
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_patch_contracts import FocusedResultsArtifactV12


def _source(name: str) -> tuple[SolutionProjection, ResultsConfig, str]:
    archived = parse_focused_artifact((RUNS / name / "artifact.json").read_bytes())
    assert archived.passes[0].raw_wire is not None
    return (SolutionProjection.model_validate(archived.evidence.source.model_dump(mode="json")),
            ResultsConfig.model_validate_json(CONFIG.read_bytes()), archived.passes[0].raw_wire)


@pytest.mark.parametrize("name", ["scout-v19-admitted", "scout-v19-conditional",
                                    "scout-v19-incomplete"])
def test_v21_three_requests_have_none_low_medium_and_v20_facts(name: str) -> None:
    source, config, selection = _source(name)
    writer = _FrozenV19Writer(selection)
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v21")
    assert isinstance(artifact, FocusedResultsArtifactV12)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v20"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v18"
    assert len(writer.requests) == len(artifact.passes) == 3
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "none", "low", "medium"]
    assert [settings.reasoning_effort for settings in (
        artifact.selector_settings, artifact.composer_settings, artifact.revision_settings)] == [
            "none", "low", "medium"]
    assert all(request["model"] == "gpt-6-luna" for request in writer.requests)
    assert artifact.focus_prepared.packet["comparison_pairs"] is not None
    draft_packet = json.loads(str(writer.requests[1]["input"]))["packet"]
    editor_packet = json.loads(str(writer.requests[2]["input"]))["packet"]
    assert draft_packet == editor_packet
    assert all("purpose" not in row for row in draft_packet["editorial_plan"])
    assert all("traveler_evidence" in row for row in draft_packet["authoring_records"].values()
               if row["role"] == "journey")
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    altered = artifact.model_dump(mode="json")
    altered["selector_settings"]["reasoning_effort"] = "low"
    with pytest.raises(ValueError, match="settings"):
        replay_focused_results(FocusedResultsArtifactV12.model_validate(altered))


def test_v21_preserves_v20_request_instructions_and_source_packet() -> None:
    source, config, selection = _source("scout-v19-conditional")
    old_writer, new_writer = _FrozenV19Writer(selection), _FrozenV19Writer(selection)
    old = run_focused_results(source, config, old_writer, FakeMeasurer(), profile="focused-v20")
    new = run_focused_results(source, config, new_writer, FakeMeasurer(), profile="focused-v21")
    assert old.focus_prepared is not None and new.focus_prepared is not None
    for old_request, new_request in zip(old_writer.requests, new_writer.requests, strict=True):
        assert old_request["instructions"] == new_request["instructions"]
        old_payload = json.loads(str(old_request["input"]))
        new_payload = json.loads(str(new_request["input"]))
        old_payload["packet"]["selection_format"] = "roles-v20"
        if "composition_format" in old_payload["packet"]:
            old_payload["packet"]["composition_format"] = "complete-v18"
        assert old_payload == new_payload
    assert replay_focused_results(parse_focused_artifact(old.model_dump_json())) == old.resolved


def test_v21_cli_explicit_measure_author_replay(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    source, config, selection = _source("scout-v19-conditional")
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", "focused-v21", "--projection",
              str(source_path), "--config", str(config_path)]
    measure_path = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    assert json.loads(measure_path.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format="roles-v20").packet_digest
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
