"""V23 keeps V22's first two requests and corrects only failed checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig, WriterReceipt
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_comparison_contracts import FocusedResultsArtifactV11

ROOT = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default")
RUNS = ROOT / "runs"
REVIEWS = {"scout-v22-admitted": "q088", "scout-v22-conditional": "q090",
           "scout-v22-incomplete": "q092"}


class SavedWriter:
    def __init__(self, wires: list[str]) -> None:
        self.wires = wires
        self.requests: list[dict[str, object]] = []
        self.pending: WriterReceipt | None = None

    def author(self, request: dict[str, object], config: ResultsConfig, settings: object) -> str:
        index = len(self.requests)
        self.requests.append(request)
        raw = self.wires[index]
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self.pending = self.pending, None
        return receipt


def _saved(name: str) -> tuple[object, SolutionProjection, ResultsConfig]:
    old = parse_focused_artifact((RUNS / name / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(old.evidence.source.model_dump(mode="json"))
    return old, source, old.config


@pytest.mark.parametrize("name", list(REVIEWS))
def test_v23_exact_v22_first_two_requests_and_reviewed_initial_answer(name: str) -> None:
    old, source, config = _saved(name)
    first, second = old.passes[:2]
    assert first.raw_wire is not None and second.raw_wire is not None
    writer = SavedWriter([first.raw_wire, second.raw_wire])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v23")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v21"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v19"
    assert len(writer.requests) == len(artifact.passes) == 2
    assert writer.requests == [first.request, second.request]
    assert [content_digest(request) for request in writer.requests] == [
        first.request_digest, second.request_digest]
    assert [p.request["reasoning"]["effort"] for p in artifact.passes] == ["none", "low"]
    assert artifact.passes[1].findings == second.findings == ()
    assert artifact.passes[1].raw_wire == second.raw_wire
    reviewed = json.loads((ROOT / "review-bundles" / REVIEWS[name] / "document.json").read_text())
    assert artifact.passes[1].document is not None
    assert artifact.passes[1].document.model_dump(mode="json") == reviewed
    index = json.loads((ROOT / "review-index.json").read_text())
    assert index[REVIEWS[name]]["run"] == f"runs/{name}"
    assert index[REVIEWS[name]]["pass_index"] == 1
    assert artifact.selected_pass_index == 1
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    assert replay_focused_results(old) == old.resolved


def test_v23_failed_mechanical_check_gets_one_low_full_document_correction() -> None:
    old, source, config = _saved("scout-v22-admitted")
    selection, draft = old.passes[:2]
    assert selection.raw_wire is not None and draft.raw_wire is not None
    changed = json.loads(draft.raw_wire)
    changed["blocks"] = [block for block in changed["blocks"] if block.get("k") != "a"]
    writer = SavedWriter([selection.raw_wire, json.dumps(changed), draft.raw_wire])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v23")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(writer.requests) == len(artifact.passes) == 3
    assert artifact.passes[1].outcome == "recoverable"
    assert any(f.outcome == "failed" for f in artifact.passes[1].findings)
    correction = writer.requests[2]
    assert correction["reasoning"]["effort"] == "low"
    assert correction["text"]["format"]["name"] == "FocusedResultsComparisonDocument"
    assert correction["text"]["format"]["schema"] == writer.requests[1]["text"]["format"]["schema"]
    input_data = json.loads(str(correction["input"]))
    assert input_data["packet"] == json.loads(str(writer.requests[1]["input"]))["packet"]
    assert input_data["previous_wire"] == changed
    assert input_data["feedback"]
    assert artifact.selected_pass_index == 2
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    clean = run_focused_results(source, config, SavedWriter([selection.raw_wire, draft.raw_wire]),
                                FakeMeasurer(), profile="focused-v23")
    assert isinstance(clean, FocusedResultsArtifactV11)
    forged = clean.model_dump(mode="json")
    forged["passes"].append(artifact.passes[2].model_dump(mode="json"))
    with pytest.raises(ValueError, match="lacks failed draft"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(forged))


def test_v23_unrecoverable_draft_does_not_trigger_correction() -> None:
    old, source, config = _saved("scout-v22-admitted")
    assert old.passes[0].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, "{}"])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v23")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(writer.requests) == len(artifact.passes) == 2
    assert artifact.passes[1].outcome == "generation_error"
    assert artifact.resolved is None
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) is None


def test_v23_failed_correction_retains_annotated_initial_draft() -> None:
    old, source, config = _saved("scout-v22-admitted")
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    changed = json.loads(old.passes[1].raw_wire)
    changed["blocks"] = [block for block in changed["blocks"] if block.get("k") != "a"]
    writer = SavedWriter([old.passes[0].raw_wire, json.dumps(changed), "{}"])
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v23")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert len(writer.requests) == len(artifact.passes) == 3
    assert artifact.passes[2].outcome == "generation_error"
    assert artifact.selected_pass_index == 1
    assert artifact.validation_outcome == "annotated"
    assert artifact.delivery_outcome == "delivered"
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


def test_v23_cli_explicit_measure_author_replay(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    old, source, config = _saved("scout-v22-admitted")
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", "focused-v23", "--projection",
              str(source_path), "--config", str(config_path)]
    measure_path = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    assert json.loads(measure_path.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format="roles-v21").packet_digest
    from award_agent.results import interactive_adapter

    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    writer = SavedWriter([old.passes[0].raw_wire, old.passes[1].raw_wire])
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    artifact_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(artifact_path)]) == 0
    assert len(writer.requests) == 2
    assert json.loads(artifact_path.read_text())["contract_version"] == "results-artifact-v11"
    replay_path = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(artifact_path),
                             "--output", str(replay_path)]) == 0
