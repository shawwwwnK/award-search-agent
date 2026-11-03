"""V10 editorial revision retains bounded attempts and exact replay."""

import json

import pytest
from test_results_focused import FakeMeasurer, _config, _source

from award_agent.results.contracts import ResultsWriterError, WriterReceipt
from award_agent.results.focused import (
    parse_focused_artifact,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_contracts import FocusedResultsArtifactV10


class EditorialWriter:
    def __init__(self, *, draft: str = "clean", revision: str = "clean",
                 bad_selection: bool = False,
                 revision_effort: str = "medium",
                 draft_effort: str = "low") -> None:
        self.draft, self.revision, self.bad_selection = draft, revision, bad_selection
        self.revision_effort = revision_effort
        self.draft_effort = draft_effort
        self.requests: list[dict[str, object]] = []
        self.pending: WriterReceipt | None = None

    def author(self, request, config, settings):
        index = len(self.requests)
        expected = (self.revision_effort if index == 2 else
                    self.draft_effort if index == 1 else "low")
        assert settings.reasoning_effort == expected
        assert settings.service_tier == "fast"
        self.requests.append(request)
        packet = json.loads(request["input"])["packet"]
        if index == 0:
            ref = "J999" if self.bad_selection else packet["journey_rows"][0][0]
            raw = json.dumps({"choices": [{"k": "j", "r": ref}]})
        else:
            mode = self.draft if index == 1 else self.revision
            if mode == "api_error":
                raise ResultsWriterError("api_error", "editorial call failed")
            if mode == "schema_error":
                raw = "{}"
            else:
                ref = packet["journeys"][0]["members"][0]["ref"]
                text = "J1 is an internal alias." if mode in {"failed", "worse"} else \
                       "A grounded choice with a real downside."
                blocks = [{"k": "p", "r": ref, "n": "Choice", "v": text}]
                if mode == "worse":
                    blocks.append({"k": "t", "v": "J1 is repeated in narrative."})
                raw = json.dumps({"blocks": blocks})
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self):
        receipt, self.pending = self.pending, None
        return receipt


def _run(*, profile="focused-v8", **writer_options):
    writer, measurer = EditorialWriter(**writer_options), FakeMeasurer()
    artifact = run_focused_results(_source(), _config(), writer, measurer,
                                   profile=profile)
    return artifact, writer, measurer


def test_clean_v8_always_revises_in_three_calls() -> None:
    artifact, writer, measurer = _run()
    assert isinstance(artifact, FocusedResultsArtifactV10)
    assert [item.phase for item in artifact.passes] == [
        "selection", "composition", "revision"]
    assert len(writer.requests) == len(measurer.requests) == 3
    assert artifact.revision_trigger == "editorial_revision"
    assert artifact.passes[1].findings == ()
    payload = json.loads(artifact.passes[2].request["input"])
    assert payload["revision_trigger"] == "editorial_revision"
    assert payload["feedback"] == []
    assert payload["previous_wire"] == json.loads(artifact.passes[1].raw_wire)
    assert "Write the full first draft" in artifact.passes[1].request["instructions"]
    assert "Write the full first draft" not in artifact.passes[2].request["instructions"]
    assert "An editorial pass will review" not in artifact.passes[2].request["instructions"]
    assert "This is the final editorial revision" in artifact.passes[2].request["instructions"]
    assert artifact.selected_pass_index == 2
    assert artifact.selection_reason == "revision_tie"
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


def test_v9_low_editor_uses_exact_details_and_replay() -> None:
    old, _, _ = _run()
    artifact, writer, measurer = _run(profile="focused-v9", revision_effort="low")
    assert len(writer.requests) == len(measurer.requests) == 3
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v8"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v6"
    assert artifact.revision_settings.reasoning_effort == "low"
    assert "exact_details index" in artifact.passes[0].request["instructions"]
    assert "selected_details index" in artifact.passes[1].request["instructions"]
    assert "selected_details index" in artifact.passes[2].request["instructions"]
    assert "exact_details index" not in old.passes[0].request["instructions"]
    assert json.loads(artifact.passes[2].request["input"])["feedback"] == []
    assert artifact.selection_reason == "revision_tie"
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    changed = artifact.model_dump(mode="json")
    changed["revision_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="profile settings differ"):
        replay_focused_results(FocusedResultsArtifactV10.model_validate(changed))


def test_v10_none_draft_medium_editor_preserves_enriched_v9_briefs() -> None:
    old, _, _ = _run(profile="focused-v9", revision_effort="low")
    artifact, writer, measurer = _run(profile="focused-v10", draft_effort="none")
    assert len(writer.requests) == len(measurer.requests) == 3
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v9"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v7"
    assert artifact.selector_settings.reasoning_effort == "low"
    assert artifact.composer_settings.reasoning_effort == "none"
    assert artifact.revision_settings.reasoning_effort == "medium"
    assert [p.request["instructions"] for p in artifact.passes] == [
        p.request["instructions"] for p in old.passes]
    assert artifact.selector_prepared.packet["exact_details"] == \
           old.selector_prepared.packet["exact_details"]
    assert artifact.focus_prepared.packet["selected_details"] == \
           old.focus_prepared.packet["selected_details"]
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    changed = artifact.model_dump(mode="json")
    changed["composer_settings"]["reasoning_effort"] = "low"
    with pytest.raises(ValueError, match="profile settings differ"):
        replay_focused_results(FocusedResultsArtifactV10.model_validate(changed))


@pytest.mark.parametrize("draft,revision,selected,reason", [
    ("failed", "clean", 2, "revision_fewer_failures"),
    ("failed", "failed", 2, "revision_tie"),
    ("failed", "worse", 1, "initial_fewer_failures"),
])
def test_failed_draft_revisions_choose_fewer_mechanical_failures(
        draft, revision, selected, reason) -> None:
    artifact, writer, measurer = _run(draft=draft, revision=revision)
    assert len(writer.requests) == len(measurer.requests) == 3
    assert artifact.passes[1].findings
    assert json.loads(artifact.passes[2].request["input"])["feedback"]
    assert artifact.selected_pass_index == selected
    assert artifact.selection_reason == reason
    assert replay_focused_results(artifact) == artifact.resolved


@pytest.mark.parametrize("revision", ["api_error", "schema_error"])
def test_failed_revision_keeps_original_draft(revision) -> None:
    artifact, writer, measurer = _run(revision=revision)
    assert len(writer.requests) == len(measurer.requests) == 3
    assert artifact.selected_pass_index == 1
    assert artifact.selection_reason == "initial_only"
    assert artifact.delivery_outcome == "delivered"
    assert replay_focused_results(artifact) == artifact.resolved


def test_unrecoverable_draft_never_revises() -> None:
    artifact, writer, measurer = _run(draft="schema_error")
    assert len(writer.requests) == len(measurer.requests) == 2
    assert artifact.revision_trigger is None
    assert artifact.selected_pass_index is None
    assert artifact.delivery_outcome == "not_delivered"
    assert replay_focused_results(artifact) is None


def test_unrecoverable_selection_never_writes() -> None:
    artifact, writer, measurer = _run(bad_selection=True)
    assert len(writer.requests) == len(measurer.requests) == 1
    assert artifact.revision_trigger is None
    assert artifact.selected_pass_index is None
    assert replay_focused_results(artifact) is None


def test_v10_replay_rejects_missing_revision_and_tampering() -> None:
    artifact, _, _ = _run()
    raw = artifact.model_dump(mode="json")
    raw["passes"].pop()
    with pytest.raises(ValueError, match="revision trigger differs"):
        replay_focused_results(FocusedResultsArtifactV10.model_validate(raw))
    raw = artifact.model_dump(mode="json")
    raw["passes"][2]["request"]["input"] = "tampered"
    with pytest.raises(ValueError, match="request differs"):
        replay_focused_results(FocusedResultsArtifactV10.model_validate(raw))
    raw = artifact.model_dump(mode="json")
    raw["selected_pass_index"] = 1
    with pytest.raises(ValueError, match="selected draft differs"):
        replay_focused_results(FocusedResultsArtifactV10.model_validate(raw))
    raw = artifact.model_dump(mode="json")
    raw["revision_settings"]["reasoning_effort"] = "low"
    with pytest.raises(ValueError, match="profile settings differ"):
        replay_focused_results(FocusedResultsArtifactV10.model_validate(raw))
    raw = artifact.model_dump(mode="json")
    raw["revision_trigger"] = None
    with pytest.raises(ValueError, match="revision trigger differs"):
        replay_focused_results(FocusedResultsArtifactV10.model_validate(raw))
