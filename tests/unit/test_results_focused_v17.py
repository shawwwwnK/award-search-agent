"""V17 atomic editorial splices, bounded calls, retention, and replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer, _config, _source

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import content_digest
from award_agent.results.contracts import InputTokenReceipt, ResultsWriterError, WriterReceipt
from award_agent.results.focused import (
    parse_focused_artifact,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_patch import apply_patch, decode_patch
from award_agent.results.focused_patch_contracts import FocusedResultsArtifactV12


def _receipt(raw: str) -> WriterReceipt:
    return WriterReceipt(status="completed", raw_response=json.dumps({
        "status": "completed", "service_tier": "priority",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))


class PatchWriter:
    def __init__(self, mode: str = "tie", *, editor_effort: str = "medium") -> None:
        self.mode = mode
        self.editor_effort = editor_effort
        self.requests: list[dict[str, object]] = []
        self.pending: WriterReceipt | None = None

    def author(self, request, config, settings):
        phase = len(self.requests)
        assert settings.reasoning_effort == (self.editor_effort if phase == 2 else "low")
        assert settings.service_tier == "fast"
        self.requests.append(request)
        payload = json.loads(request["input"])
        packet = payload["packet"]
        if phase == 0:
            if self.mode == "selection_failure":
                raw = "{}"
            else:
                refs = list(packet["journey_records"])[:2]
                raw = json.dumps({"choices": [
                    {"k": "j", "r": refs[0], "purpose": "Check the schedule tradeoff",
                     "compare_to": refs[1]},
                    {"k": "j", "r": refs[1], "purpose": "Compare useful arrival evidence",
                     "compare_to": refs[0]}]})
        elif phase == 1:
            if self.mode == "draft_failure":
                raw = "{}"
            else:
                refs = [ref for ref, row in packet["authoring_records"].items()
                        if row["role"] == "journey"]
                opening = ("Internal J1 note." if self.mode == "repair" else
                           "A useful starting option with a tradeoff.")
                blocks = [
                    {"k": "t", "v": opening},
                    {"k": "p", "r": refs[0], "n": "First option", "v": "A useful first option."},
                    {"k": "a", "r": refs[1], "n": "Second option", "v": "A distinct alternative."}]
                if self.mode == "missing_endpoint":
                    blocks.append({"k": "x", "r": packet["temporal_comparisons"][0]["id"]})
                raw = json.dumps({"blocks": blocks})
        else:
            assert payload["revision_trigger"] == "editorial_revision"
            if self.editor_effort == "low":
                assert "numbered_draft" not in payload
                assert payload["previous_wire"]["blocks"] == [
                    {"index": i, "block": row["block"]}
                    for i, row in enumerate(payload["previous_wire"]["blocks"])]
                assert "Never print internal J/A/C/T/JP/CP identifiers" in request["instructions"]
                assert "why a traveler might choose it over the lead" in request["instructions"]
                assert "what they give up" in request["instructions"]
                assert "valid comparison endpoints" in request["instructions"]
                original_blocks = [row["block"] for row in payload["previous_wire"]["blocks"]]
            else:
                assert payload["numbered_draft"] == [
                    {"index": i, "block": block}
                    for i, block in enumerate(payload["previous_wire"]["blocks"])]
                original_blocks = payload["previous_wire"]["blocks"]
            assert payload["draft_digest"]
            if self.mode in {"api_error", "refusal", "incomplete"}:
                response = ({"status": "failed", "output": []} if self.mode == "api_error" else
                            {"status": "incomplete", "output": []} if self.mode == "incomplete" else
                            {"status": "completed", "output": [{"type": "message",
                                "content": [{"type": "refusal", "refusal": "No."}]}]})
                raise ResultsWriterError(self.mode, self.mode, json.dumps(response))
            if self.mode == "tie":
                assert payload["feedback"] == []
                raw = '{"edits":[]}'
            elif self.mode == "repair":
                assert payload["feedback"]
                raw = json.dumps({"edits": [{"start": 0, "end": 1,
                    "blocks": [{"k": "t", "v": "A supported comparison."}]}]})
            elif self.mode == "worse":
                raw = json.dumps({"edits": [{"start": 0, "end": 1,
                    "blocks": [{"k": "t", "v": "Internal J1 note."}]}]})
            elif self.mode == "bad_patch":
                raw = '{"edits":[{"start":0,"end":4,"blocks":[]}]}'
            elif self.mode == "invalid_result":
                raw = '{"edits":[{"start":0,"end":3,"blocks":[]}]}'
            elif self.mode == "missing_endpoint":
                raw = '{"edits":[{"start":2,"end":3,"blocks":[]}]}'
            elif self.mode == "lost_recommendation":
                first = original_blocks[1]
                raw = json.dumps({"edits": [{"start": 1, "end": 2,
                    "blocks": [{**first, "k": "a"}]}]})
            elif self.mode == "bad_label":
                first = original_blocks[1]
                raw = json.dumps({"edits": [{"start": 1, "end": 2,
                    "blocks": [{**first, "n": ""}]}]})
            else:
                raise AssertionError(self.mode)
        self.pending = _receipt(raw)
        return raw

    def take_receipt(self):
        result, self.pending = self.pending, None
        return result


@pytest.mark.parametrize("mode,index,reason,count", [
    ("tie", 2, "revision_tie", 3),
    ("repair", 2, "revision_fewer_failures", 3),
    ("worse", 1, "initial_fewer_failures", 3),
    ("bad_patch", 1, "revision_unrecoverable", 3),
    ("invalid_result", 1, "revision_unrecoverable", 3),
    ("missing_endpoint", 1, "initial_fewer_failures", 3),
    ("lost_recommendation", 1, "initial_fewer_failures", 3),
    ("bad_label", 1, "revision_unrecoverable", 3),
    ("api_error", 1, "revision_unrecoverable", 3),
    ("refusal", 1, "revision_unrecoverable", 3),
    ("incomplete", 1, "revision_unrecoverable", 3),
    ("draft_failure", None, "no_recoverable_draft", 2),
    ("selection_failure", None, "no_recoverable_draft", 1),
])
def test_v17_bounded_runs_replay_and_retention(mode, index, reason, count) -> None:
    writer = PatchWriter(mode)
    artifact = run_focused_results(_source(), _config(), writer, FakeMeasurer(),
                                   profile="focused-v17")
    assert isinstance(artifact, FocusedResultsArtifactV12)
    assert len(writer.requests) == len(artifact.passes) == count
    assert artifact.selected_pass_index == index
    assert artifact.selection_reason == reason
    assert artifact.revision_trigger == ("editorial_revision" if count == 3 else None)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v16"
    if artifact.focus_prepared is not None:
        assert artifact.focus_prepared.packet["composition_format"] == "complete-v14"
    if count == 3 and mode in {"tie", "repair", "worse", "missing_endpoint",
                                "lost_recommendation"}:
        assert artifact.passes[2].raw_patch is not None
        assert artifact.passes[2].materialized_wire is not None
        assert artifact.passes[2].raw_patch != artifact.passes[2].materialized_wire
    if mode in {"bad_patch", "invalid_result", "bad_label"}:
        assert artifact.passes[2].failure_subtype == "schema_error"
        assert artifact.passes[2].raw_patch is not None
    if mode == "missing_endpoint":
        assert any(f.code == "comparison_endpoint_not_visible" and f.outcome == "failed"
                   for f in artifact.passes[2].findings)
    if mode == "lost_recommendation":
        assert any(f.outcome == "failed" and "recommendation" in f.code
                   for f in artifact.passes[2].findings)
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


@pytest.mark.parametrize("failure", ["measurement_error", "context_limit"])
def test_v17_uncalled_editor_retains_draft(failure: str) -> None:
    class EditorMeasurer(FakeMeasurer):
        def measure(self, request, config):
            if request["text"]["format"]["name"] == "FocusedResultsEditorialPatch":
                if failure == "measurement_error":
                    raise ValueError("count unavailable")
                return InputTokenReceipt(request_digest=content_digest(request),
                    input_tokens=config.context_limit_tokens, raw_response={
                    "object": "response.input_tokens", "input_tokens":
                    config.context_limit_tokens})
            return super().measure(request, config)

    writer = PatchWriter()
    artifact = run_focused_results(_source(), _config(), writer, EditorMeasurer(),
                                   profile="focused-v17")
    assert len(writer.requests) == 2
    assert len(artifact.passes) == 3
    assert artifact.passes[2].outcome == failure
    assert artifact.passes[2].writer_called is False
    assert artifact.selected_pass_index == 1
    assert artifact.selection_reason == "revision_unrecoverable"
    assert replay_focused_results(artifact) == artifact.resolved


@pytest.mark.parametrize("patch,expected", [
    ({"edits": []}, ["A", "B", "C"]),
    ({"edits": [{"start": 1, "end": 1, "blocks": [{"k": "t", "v": "X"}]}]},
     ["A", "X", "B", "C"]),
    ({"edits": [{"start": 1, "end": 2, "blocks": []}]}, ["A", "C"]),
    ({"edits": [{"start": 0, "end": 3, "blocks": [{"k": "t", "v": "X"}]}]}, ["X"]),
    ({"edits": [{"start": 0, "end": 1, "blocks": [{"k": "t", "v": "X"}]},
                {"start": 2, "end": 2, "blocks": [{"k": "t", "v": "Y"}]}]},
     ["X", "B", "Y", "C"]),
])
def test_atomic_splice_preserves_untouched_blocks(patch, expected) -> None:
    draft = json.dumps({"blocks": [{"k": "t", "v": value} for value in "ABC"]})
    result = json.loads(apply_patch(draft, decode_patch(patch)))
    assert [block["v"] for block in result["blocks"]] == expected


@pytest.mark.parametrize("edits", [
    [{"start": 1, "end": 1, "blocks": []}, {"start": 1, "end": 2, "blocks": []}],
    [{"start": 2, "end": 3, "blocks": []}, {"start": 0, "end": 1, "blocks": []}],
    [{"start": 0, "end": 2, "blocks": []}, {"start": 1, "end": 3, "blocks": []}],
    [{"start": 0, "end": 4, "blocks": []}],
    [{"start": 2, "end": 1, "blocks": []}],
    [{"start": -1, "end": 1, "blocks": []}],
    [{"start": True, "end": 1, "blocks": []}],
    [{"start": 0.0, "end": 1, "blocks": []}],
])
def test_atomic_splice_rejects_invalid_ranges(edits) -> None:
    draft = json.dumps({"blocks": [{"k": "t", "v": value} for value in "ABC"]})
    with pytest.raises(ValueError):
        apply_patch(draft, decode_patch({"edits": edits}))


@pytest.mark.parametrize("field", ["draft_digest", "raw_patch", "materialized_wire",
                                   "materialized_digest", "findings", "revision_trigger",
                                   "selected_pass_index"])
def test_v17_replay_rejects_editor_evidence_tampering(field: str) -> None:
    artifact = run_focused_results(_source(), _config(), PatchWriter(), FakeMeasurer(),
                                   profile="focused-v17")
    data = artifact.model_dump(mode="json")
    target = data if field in {"revision_trigger", "selected_pass_index"} else data["passes"][2]
    target[field] = (1 if field == "selected_pass_index" else "changed")
    with pytest.raises((ValueError, TypeError)):
        replay_focused_results(FocusedResultsArtifactV12.model_validate(data))


@pytest.mark.parametrize("mutation", ["patch", "response", "draft_wire", "request",
                                     "document", "selection"])
def test_v17_replay_recomputes_each_handoff(mutation: str) -> None:
    artifact = run_focused_results(_source(), _config(), PatchWriter(), FakeMeasurer(),
                                   profile="focused-v17")
    data = artifact.model_dump(mode="json")
    if mutation == "patch":
        data["passes"][2]["patch"]["edits"] = [{"start": 0, "end": 0,
            "blocks": [{"k": "t", "v": "Inserted."}]}]
    elif mutation == "response":
        raw = json.loads(data["passes"][2]["writer_receipt"]["raw_response"])
        raw["output"][0]["content"][0]["text"] = '{"edits":[{"start":0,"end":0,"blocks":[]}]}'
        data["passes"][2]["writer_receipt"]["raw_response"] = json.dumps(raw)
    elif mutation == "draft_wire":
        data["passes"][1]["raw_wire"] = data["passes"][1]["raw_wire"].replace(
            "starting option", "different option")
    elif mutation == "request":
        data["passes"][2]["request"]["input"] = '{}'
    elif mutation == "document":
        data["passes"][2]["document"]["blocks"][0]["text"] = "Wrong answer."
    else:
        data["passes"][0]["selection"]["journey_ids"] = []
    with pytest.raises((ValueError, TypeError)):
        replay_focused_results(FocusedResultsArtifactV12.model_validate(data))


def test_v17_old_archive_replay_is_unchanged() -> None:
    old = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/runs/scout-v16-conditional/artifact.json")
    archived = parse_focused_artifact(old.read_bytes())
    assert replay_focused_results(archived) == archived.resolved


@pytest.mark.parametrize("profile,editor_effort", [
    ("focused-v17", "medium"), ("focused-v18", "low")])
def test_patch_cli_opt_in_measure_author_and_replay(tmp_path, monkeypatch,
                                                     profile, editor_effort) -> None:
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(_source().model_dump_json())
    config_path.write_text(_config().model_dump_json())
    common = ["--interactive", "--packet-profile", profile,
              "--projection", str(source_path), "--config", str(config_path)]
    measure_path = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    assert json.loads(measure_path.read_text())["prepared_version"]
    from award_agent.results import adapter, interactive_adapter

    writer = PatchWriter(editor_effort=editor_effort)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(adapter, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    artifact_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(artifact_path)]) == 0
    artifact = parse_focused_artifact(artifact_path.read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV12)
    assert len(writer.requests) == 3
    replay_path = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(artifact_path),
                             "--output", str(replay_path)]) == 0
    assert json.loads(replay_path.read_text()) == artifact.resolved.model_dump(mode="json")


@pytest.mark.parametrize("mode,count,selected", [
    ("tie", 3, 2), ("repair", 3, 2), ("bad_patch", 3, 1),
    ("draft_failure", 2, None), ("selection_failure", 1, None),
])
def test_v18_single_numbered_draft_and_low_editor(mode, count, selected) -> None:
    writer = PatchWriter(mode, editor_effort="low")
    artifact = run_focused_results(_source(), _config(), writer, FakeMeasurer(),
                                   profile="focused-v18")
    assert isinstance(artifact, FocusedResultsArtifactV12)
    assert len(artifact.passes) == len(writer.requests) == count
    assert artifact.selected_pass_index == selected
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v17"
    assert [item.request["reasoning"]["effort"] for item in artifact.passes] == ["low"] * count
    assert artifact.revision_settings.reasoning_effort == "low"
    if artifact.focus_prepared is not None:
        assert artifact.focus_prepared.packet["composition_format"] == "complete-v15"
    if count == 3:
        payload = json.loads(artifact.passes[2].request["input"])
        assert "numbered_draft" not in payload
        assert payload["previous_wire"] == {"blocks": [
            {"index": i, "block": block} for i, block in enumerate(
                json.loads(artifact.passes[1].raw_wire)["blocks"])]}
        assert "Never print internal J/A/C/T/JP/CP identifiers" in artifact.passes[2].request["instructions"]
        assert "why a traveler might choose it over the lead" in artifact.passes[2].request["instructions"]
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


def test_v18_editor_request_replay_rejects_numbered_input_tampering() -> None:
    artifact = run_focused_results(_source(), _config(), PatchWriter(editor_effort="low"),
                                   FakeMeasurer(), profile="focused-v18")
    data = artifact.model_dump(mode="json")
    input_data = json.loads(data["passes"][2]["request"]["input"])
    input_data["previous_wire"]["blocks"][0]["index"] = 9
    data["passes"][2]["request"]["input"] = json.dumps(input_data)
    with pytest.raises(ValueError):
        replay_focused_results(FocusedResultsArtifactV12.model_validate(data))


class _IncompletePhaseWriter(PatchWriter):
    def __init__(self, phase: int) -> None:
        super().__init__(editor_effort="low")
        self.failed_phase = phase

    def author(self, request, config, settings):
        if len(self.requests) == self.failed_phase:
            self.requests.append(request)
            response = json.dumps({"status": "incomplete", "output": []})
            self.pending = WriterReceipt(status="incomplete", raw_response=response)
            raise ResultsWriterError("incomplete", "writer stopped early", response)
        return super().author(request, config, settings)


@pytest.mark.parametrize("phase,mode", [
    (0, "incomplete"), (1, "incomplete"), (2, "incomplete"),
    (2, "api_error"), (2, "refusal"),
])
def test_v18_replay_rejects_terminal_response_relabelled_as_schema_failure(
        phase: int, mode: str) -> None:
    writer = (_IncompletePhaseWriter(phase) if phase < 2 else
              PatchWriter(mode, editor_effort="low"))
    artifact = run_focused_results(_source(), _config(), writer, FakeMeasurer(),
                                   profile="focused-v18")
    assert isinstance(artifact, FocusedResultsArtifactV12)
    assert replay_focused_results(artifact) == artifact.resolved
    data = artifact.model_dump(mode="json")
    attempt = data["passes"][phase]
    assert attempt["failure_subtype"] == mode
    attempt["failure_subtype"] = "schema_error"
    attempt["error"] = "schema_error: invented decoding failure"
    if mode == "api_error":
        attempt["outcome"] = "generation_error"
    with pytest.raises(ValueError, match="subtype differs from response"):
        replay_focused_results(FocusedResultsArtifactV12.model_validate(data))


def test_v17_archived_editor_request_replays_without_v18_guide() -> None:
    archived = parse_focused_artifact(Path(
        "evidence/results-stage/m2/structured/2026-10-28-fast-default/runs/scout-v17-admitted/artifact.json"
    ).read_bytes())
    assert replay_focused_results(archived) == archived.resolved
    assert archived.revision_settings.reasoning_effort == "medium"
    editor = archived.passes[2]
    assert "numbered_draft" in json.loads(editor.request["input"])
    assert "Never print internal J/A/C/T/JP/CP identifiers" not in editor.request["instructions"]
