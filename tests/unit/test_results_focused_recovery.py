"""Focused V9 correction is conditional, bounded and replayable."""

import json

import pytest
from test_results_focused import FakeMeasurer, FakeWriter, _config, _source

from award_agent.results.contracts import ResultsWriterError, WriterReceipt
from award_agent.results.focused import (
    parse_focused_artifact,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_contracts import FocusedResultsArtifactV9
from award_agent.results.focused_v4 import _findings
from award_agent.results.interactive_contracts import InteractiveSettings
from award_agent.results.structured_contracts import (
    StructuredBlock,
    StructuredDocument,
    StructuredSelection,
)


class RepairWriter(FakeWriter):
    def __init__(self, *, corrected_text: str | None = "A source-grounded choice.",
                 fail_correction: bool = False,
                 bad_composition: bool = False) -> None:
        super().__init__(v2=True)
        self.corrected_text = corrected_text
        self.fail_correction = fail_correction
        self.bad_composition = bad_composition

    def author(self, request, config, settings):
        if len(self.requests) == 2 and self.fail_correction:
            self.requests.append(request)
            raise ResultsWriterError("api_error", "forced correction failure")
        raw = super().author(request, config, settings)
        if len(self.requests) < 2:
            return raw
        if len(self.requests) == 2 and self.bad_composition:
            raw = "{}"
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority",
                "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": raw}]}]}))
            return raw
        packet = json.loads(request["input"])["packet"]
        ref = packet["journeys"][0]["members"][0]["ref"]
        text = ("J1 is an internal alias." if len(self.requests) == 2 else
                self.corrected_text)
        if text is None:
            text = "J1 is still an internal alias."
        extra = []
        if text == "worse":
            text = "J1 remains an internal alias."
            extra = [{"k": "t", "v": "J1 is repeated in narrative."}]
        raw = json.dumps({"blocks": [{"k": "p", "r": ref, "n": "Choice",
                                       "v": text}, *extra]})
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw


class V5Writer(FakeWriter):
    def __init__(self) -> None:
        super().__init__(v2=True)

    def author(self, request, config, settings):
        assert settings.reasoning_effort == "low"
        return super().author(request, config, InteractiveSettings(
            reasoning_effort="none" if not self.requests else "low",
            service_tier="fast"))


class V6Writer(FakeWriter):
    def __init__(self) -> None:
        super().__init__(v2=True)

    def author(self, request, config, settings):
        assert settings.reasoning_effort == "medium"
        return super().author(request, config, InteractiveSettings(
            reasoning_effort="none" if not self.requests else "low",
            service_tier="fast"))


class V7Writer(FakeWriter):
    def __init__(self) -> None:
        super().__init__(v2=True)

    def author(self, request, config, settings):
        assert settings.reasoning_effort == ("low" if not self.requests else "medium")
        return super().author(request, config, InteractiveSettings(
            reasoning_effort="none" if not self.requests else "low",
            service_tier="fast"))


def test_clean_v4_stops_after_two_calls_and_replays() -> None:
    writer, measurer = FakeWriter(v2=True), FakeMeasurer()
    artifact = run_focused_results(_source(), _config(), writer, measurer,
                                   profile="focused-v4")
    assert isinstance(artifact, FocusedResultsArtifactV9)
    assert [item.phase for item in artifact.passes] == ["selection", "composition"]
    assert artifact.selected_pass_index == 1
    assert artifact.selection_reason == "initial_only"
    assert len(writer.requests) == len(measurer.requests) == 2
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


def test_v5_uses_low_selector_and_versioned_briefs_with_exact_replay() -> None:
    artifact = run_focused_results(_source(), _config(), V5Writer(), FakeMeasurer(),
                                   profile="focused-v5")
    assert artifact.selector_settings.reasoning_effort == "low"
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v4"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v2"
    assert "price_scope is unknown" in artifact.passes[1].request["instructions"]
    assert "same-program alternatives" in artifact.passes[0].request["instructions"]
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    tampered = artifact.model_dump(mode="json")
    tampered["selector_settings"]["reasoning_effort"] = "none"
    with pytest.raises(ValueError, match="model settings differ"):
        replay_focused_results(FocusedResultsArtifactV9.model_validate(tampered))


def test_v6_uses_medium_both_and_comparison_pool_briefs_with_exact_replay() -> None:
    artifact = run_focused_results(_source(), _config(), V6Writer(), FakeMeasurer(),
                                   profile="focused-v6")
    assert artifact.selector_settings.reasoning_effort == "medium"
    assert artifact.composer_settings.reasoning_effort == "medium"
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v5"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v3"
    assert "membership" in artifact.passes[0].request["instructions"]
    assert "absent cash-benchmark cabin" in artifact.passes[1].request["instructions"]
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    changed = artifact.model_dump(mode="json")
    changed["composer_settings"]["reasoning_effort"] = "low"
    with pytest.raises(ValueError, match="model settings differ"):
        replay_focused_results(FocusedResultsArtifactV9.model_validate(changed))


def test_v7_low_selector_medium_composer_and_visible_comparator_brief() -> None:
    artifact = run_focused_results(_source(), _config(), V7Writer(), FakeMeasurer(),
                                   profile="focused-v7")
    assert artifact.selector_settings.reasoning_effort == "low"
    assert artifact.composer_settings.reasoning_effort == "medium"
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v6"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v4"
    assert "membership" in artifact.passes[0].request["instructions"]
    assert "own visible exact reference block" in artifact.passes[1].request["instructions"]
    assert len(artifact.passes) == 2
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    changed = artifact.model_dump(mode="json")
    changed["selector_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="model settings differ"):
        replay_focused_results(FocusedResultsArtifactV9.model_validate(changed))


@pytest.mark.parametrize("corrected_text,expected_index,reason", [
    ("A source-grounded choice.", 2, "correction_fewer_failures"),
    (None, 2, "correction_tie"),
])
def test_failed_visible_alias_triggers_one_correction_and_best_draft(
        corrected_text, expected_index, reason) -> None:
    writer, measurer = RepairWriter(corrected_text=corrected_text), FakeMeasurer()
    artifact = run_focused_results(_source(), _config(), writer, measurer,
                                   profile="focused-v4")
    assert len(writer.requests) == len(measurer.requests) == 3
    assert [item.phase for item in artifact.passes] == [
        "selection", "composition", "correction"]
    assert any(f.code == "visible_internal_alias" for f in artifact.passes[1].findings)
    payload = json.loads(artifact.passes[2].request["input"])
    assert payload["previous_wire"] == json.loads(artifact.passes[1].raw_wire)
    assert payload["feedback"]
    assert artifact.selected_pass_index == expected_index
    assert artifact.selection_reason == reason
    assert replay_focused_results(artifact) == artifact.resolved


def test_failed_correction_retains_recoverable_initial_and_replay() -> None:
    artifact = run_focused_results(_source(), _config(), RepairWriter(fail_correction=True),
                                   FakeMeasurer(), profile="focused-v4")
    assert artifact.selected_pass_index == 1
    assert artifact.selection_reason == "initial_only"
    assert artifact.validation_outcome == "annotated"
    assert artifact.passes[2].outcome == "api_error"
    assert replay_focused_results(artifact) == artifact.resolved


def test_worse_correction_retains_initial_with_fewer_failures() -> None:
    artifact = run_focused_results(_source(), _config(),
                                   RepairWriter(corrected_text="worse"),
                                   FakeMeasurer(), profile="focused-v4")
    assert len([f for f in artifact.passes[2].findings if f.outcome == "failed"]) > \
           len([f for f in artifact.passes[1].findings if f.outcome == "failed"])
    assert artifact.selected_pass_index == 1
    assert artifact.selection_reason == "initial_fewer_failures"
    assert replay_focused_results(artifact) == artifact.resolved


def test_v9_replay_rejects_missing_or_tampered_correction() -> None:
    artifact = run_focused_results(_source(), _config(), RepairWriter(), FakeMeasurer(),
                                   profile="focused-v4")
    raw = artifact.model_dump(mode="json")
    raw["passes"].pop()
    with pytest.raises(ValueError, match="correction is missing"):
        replay_focused_results(FocusedResultsArtifactV9.model_validate(raw))
    raw = artifact.model_dump(mode="json")
    raw["passes"][2]["request"]["input"] = "tampered"
    with pytest.raises(ValueError, match="request differs"):
        replay_focused_results(FocusedResultsArtifactV9.model_validate(raw))
    raw = artifact.model_dump(mode="json")
    raw["selected_pass_index"] = 1
    with pytest.raises(ValueError, match="selected draft differs"):
        replay_focused_results(FocusedResultsArtifactV9.model_validate(raw))


def test_v9_selector_failure_never_composes_or_corrects() -> None:
    writer, measurer = FakeWriter(v2=True, bad_selection=True), FakeMeasurer()
    artifact = run_focused_results(_source(), _config(), writer, measurer,
                                   profile="focused-v4")
    assert artifact.delivery_outcome == "not_delivered"
    assert artifact.selected_pass_index is None
    assert len(writer.requests) == len(measurer.requests) == 1
    assert replay_focused_results(artifact) is None


def test_unknown_focused_profile_fails_before_any_model_call() -> None:
    writer, measurer = FakeWriter(v2=True), FakeMeasurer()
    with pytest.raises(ValueError, match="unknown focused Results profile"):
        run_focused_results(_source(), _config(), writer, measurer,
                            profile="focused-v99")  # type: ignore[arg-type]
    assert writer.requests == measurer.requests == []


def test_v9_unrecoverable_composer_is_not_retried() -> None:
    writer, measurer = RepairWriter(bad_composition=True), FakeMeasurer()
    artifact = run_focused_results(_source(), _config(), writer, measurer,
                                   profile="focused-v4")
    assert len(writer.requests) == len(measurer.requests) == 2
    assert artifact.passes[1].outcome == "generation_error"
    assert artifact.selected_pass_index is None
    assert replay_focused_results(artifact) is None


def test_v4_checks_selected_role_coverage_from_packet() -> None:
    source = _source()
    artifact = run_focused_results(source, _config(), FakeWriter(v2=True), FakeMeasurer(),
                                   profile="focused-v4")
    focus = artifact.focus_prepared
    assert focus is not None
    narrative = StructuredDocument(selection=StructuredSelection(),
        blocks=(StructuredBlock(kind="narrative", text="The search is incomplete."),))
    missing_journey = _findings(narrative, source, focus)
    assert any(f.code == "missing_complete_recommendation" for f in missing_journey)
    packet = dict(focus.packet)
    packet["selection_scope"] = {"journey_count": 0, "lead_count": 1,
                                  "benchmark_selected": True}
    with_roles = focus.model_copy(update={"packet": packet})
    missing_context = _findings(narrative, source, with_roles)
    assert {f.code for f in missing_context} >= {
        "missing_cash_context", "missing_incomplete_lead"}
