"""V11 temporal card authoring, checks, correction and exact replay."""

import json

import pytest
from test_results_focused import FakeMeasurer, _config, _source

from award_agent.results.contracts import ResultsWriterError, WriterReceipt
from award_agent.results.focused import (
    parse_focused_artifact,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_comparison_contracts import (
    FocusedResultsArtifactV11,
    ResolvedFocusedComparisonBlock,
    TemporalComparisonRegistry,
)
from award_agent.results.focused_comparison_wire import (
    format_focused_comparison_block,
    resolve_focused_comparison_document,
)


class ComparisonWriter:
    def __init__(self, *, first: str = "clean", correction: str = "clean",
                 composer_effort: str = "medium") -> None:
        self.first, self.correction = first, correction
        self.composer_effort = composer_effort
        self.calls: list[dict[str, object]] = []
        self.pending = None

    def author(self, request, config, settings):
        index = len(self.calls)
        assert settings.reasoning_effort == (self.composer_effort if index == 1 else "low")
        assert settings.service_tier == "fast"
        self.calls.append(request)
        packet = json.loads(request["input"])["packet"]
        if index == 0:
            refs = [row[0] for row in packet["journey_rows"][:2]]
            raw = json.dumps({"choices": [{"k": "j", "r": ref} for ref in refs]})
        else:
            mode = self.first if index == 1 else self.correction
            if mode == "api_error":
                raise ResultsWriterError("api_error", "fake correction API failure")
            if mode == "schema_error":
                raw = "{}"
            else:
                refs = [member["ref"] for group in packet["journeys"]
                        for member in group["members"]]
                blocks = [{"k": "p", "r": refs[0], "n": "First", "v": "Useful first choice."}]
                if mode not in {"missing_endpoint", "worse"}:
                    blocks.append({"k": "a", "r": refs[1], "n": "Second", "v": "Useful alternative."})
                if packet["temporal_comparisons"]:
                    blocks.append({"k": "x", "r": ("T999" if mode == "unknown_id" else
                        packet["temporal_comparisons"][0]["id"])})
                if mode == "worse":
                    blocks.append({"k": "t", "v": "J1 is an internal alias."})
                if mode == "false_prose":
                    blocks.append({"k": "t", "v": "The first arrives 999 hours before the second."})
                if mode == "tid_prose":
                    blocks.append({"k": "t", "v": "See T01 for the time difference."})
                raw = json.dumps({"blocks": blocks})
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self):
        receipt, self.pending = self.pending, None
        return receipt


def _run(first="clean", correction="clean", profile="focused-v11"):
    writer = ComparisonWriter(first=first, correction=correction,
                              composer_effort="low" if profile == "focused-v12" else "medium")
    artifact = run_focused_results(_source(), _config(), writer, FakeMeasurer(),
                                   profile=profile)
    return artifact, writer


def test_clean_v11_optional_card_resolves_without_correction() -> None:
    artifact, writer = _run()
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v10"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v8"
    assert artifact.focus_prepared.comparison_contract_version == "focused-comparison-prepared-v1"
    assert "editorial pass will review" not in artifact.passes[1].request["instructions"]
    assert artifact.comparison_registry is not None
    assert [pass_.phase for pass_ in artifact.passes] == ["selection", "composition"]
    assert len(writer.calls) == 2
    assert artifact.selected_pass_index == 1
    assert artifact.passes[1].findings == ()
    assert artifact.resolved is not None
    cards = [b for b in artifact.resolved.blocks if isinstance(b, ResolvedFocusedComparisonBlock)]
    assert len(cards) == 1
    visible = format_focused_comparison_block(cards[0])
    assert "T01" not in visible
    assert cards[0].comparison.first_source.origin in visible
    assert cards[0].comparison.first_source.destination in visible
    assert cards[0].comparison.first_source.departure_local_iso in visible
    assert cards[0].comparison.second_source.arrival_local_iso in visible
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved


def test_missing_visible_endpoint_gets_one_low_effort_correction() -> None:
    artifact, writer = _run(first="missing_endpoint")
    assert len(writer.calls) == 3
    assert artifact.passes[1].findings[-1].code == "comparison_endpoint_not_visible"
    assert artifact.correction_settings.reasoning_effort == "low"
    assert artifact.selected_pass_index == 2
    assert artifact.selection_reason == "correction_fewer_failures"
    assert json.loads(artifact.passes[2].request["input"])["packet"] == \
           json.loads(artifact.passes[1].request["input"])["packet"]
    assert json.loads(artifact.passes[2].request["input"])["previous_wire"] == \
           json.loads(artifact.passes[1].raw_wire)
    assert replay_focused_results(artifact) == artifact.resolved


@pytest.mark.parametrize("correction,selected,reason", [
    ("missing_endpoint", 2, "correction_tie"),
    ("worse", 1, "initial_fewer_failures"),
])
def test_recoverable_correction_retention(correction, selected, reason) -> None:
    artifact, writer = _run(first="missing_endpoint", correction=correction)
    assert len(writer.calls) == 3
    assert artifact.selected_pass_index == selected
    assert artifact.selection_reason == reason
    assert replay_focused_results(artifact) == artifact.resolved


def test_false_numerical_prose_is_not_claimed_verified_by_card() -> None:
    artifact, _ = _run(first="false_prose")
    assert artifact.passes[1].findings == ()
    assert artifact.validation_outcome == "clean"
    assert replay_focused_results(artifact) == artifact.resolved


def test_known_temporal_id_in_visible_prose_triggers_correction() -> None:
    artifact, writer = _run(first="tid_prose")
    assert len(writer.calls) == 3
    assert any(f.code == "visible_internal_alias" for f in artifact.passes[1].findings)
    assert artifact.selected_pass_index == 2
    assert replay_focused_results(artifact) == artifact.resolved


@pytest.mark.parametrize("failure", ["api_error", "schema_error"])
def test_failed_correction_retains_original(failure) -> None:
    artifact, writer = _run(first="missing_endpoint", correction=failure)
    assert len(writer.calls) == 3
    assert artifact.selected_pass_index == 1
    assert artifact.selection_reason == "initial_only"
    assert replay_focused_results(artifact) == artifact.resolved


def test_v11_replay_rejects_registry_and_settings_tampering() -> None:
    artifact, _ = _run()
    raw = artifact.model_dump(mode="json")
    raw["comparison_registry"]["facts"][0]["difference_minutes"] = "7300"
    with pytest.raises(ValueError, match="registry differs"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(raw))
    raw = artifact.model_dump(mode="json")
    raw["correction_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="settings differ"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(raw))


def test_direct_resolver_recomputes_temporal_fact_from_canonical_source() -> None:
    artifact, _ = _run()
    assert artifact.focus_prepared is not None
    assert artifact.comparison_registry is not None
    assert artifact.passes[1].document is not None
    changed = artifact.comparison_registry.model_dump(mode="json")
    changed["facts"][0]["difference_minutes"] = "999"
    bad = TemporalComparisonRegistry.model_validate(changed)
    with pytest.raises(ValueError, match="registry differs"):
        resolve_focused_comparison_document(artifact.passes[1].document,
            artifact.focus_prepared, artifact.evidence, bad, artifact.passes[1].findings)


def test_unknown_comparison_id_is_schema_failure_without_retry() -> None:
    artifact, writer = _run(first="unknown_id")
    assert len(writer.calls) == 2
    assert artifact.passes[1].outcome == "generation_error"
    assert artifact.passes[1].failure_subtype == "schema_error"
    assert artifact.delivery_outcome == "not_delivered"
    assert replay_focused_results(artifact) is None


@pytest.mark.parametrize("pass_index", [0, 1])
def test_replay_rejects_completed_wire_relabelled_as_api_failure(pass_index) -> None:
    artifact, _ = _run()
    raw = artifact.model_dump(mode="json")
    attempt = raw["passes"][pass_index]
    attempt.update(outcome="api_error", failure_subtype="api_error",
                   error="fabricated API error", document=None, selection=None,
                   findings=[])
    with pytest.raises(ValueError, match="returned raw wire|completed response"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(raw))


def test_replay_accepts_actual_completed_refusal_evidence() -> None:
    artifact, _ = _run()
    raw = artifact.model_dump(mode="json")
    attempt = raw["passes"][1]
    response = {"status": "completed", "service_tier": "priority",
                "output": [{"type": "message", "content": [{"type": "refusal",
                                                       "refusal": "unable"}]}]}
    attempt.update(outcome="generation_error", failure_subtype="refusal",
                   error="refused", raw_wire=None, document=None, findings=[],
                   writer_receipt=WriterReceipt(status="completed",
                       raw_response=json.dumps(response)).model_dump(mode="json"))
    raw.update(selected_pass_index=None, selection_reason="no_recoverable_draft",
               generation_outcome="generation_error", validation_outcome="unavailable",
               delivery_outcome="not_delivered", resolved=None, resolved_digest=None)
    assert replay_focused_results(FocusedResultsArtifactV11.model_validate(raw)) is None


@pytest.mark.parametrize("subtype", ["api_error", "incomplete", "refusal"])
def test_replay_rejects_forged_failure_against_completed_output(subtype) -> None:
    artifact, _ = _run()
    raw = artifact.model_dump(mode="json")
    attempt = raw["passes"][1]
    attempt.update(outcome="api_error" if subtype == "api_error" else "generation_error",
                   failure_subtype=subtype, error="fabricated failure", raw_wire=None,
                   document=None, findings=[])
    with pytest.raises(ValueError, match="status differs|refusal lacks"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(raw))


@pytest.mark.parametrize("first", ["clean", "missing_endpoint"])
def test_v12_changes_only_markers_and_composer_effort(first) -> None:
    v11, _ = _run(first=first)
    v12, writer = _run(first=first, profile="focused-v12")
    assert isinstance(v12, FocusedResultsArtifactV11)
    assert v12.selector_prepared.packet["selection_format"] == "roles-v11"
    assert v12.focus_prepared is not None
    assert v12.focus_prepared.packet["composition_format"] == "complete-v9"
    assert [item.request["reasoning"]["effort"] for item in v12.passes] == (
        ["low", "low", "low"] if first == "missing_endpoint" else ["low", "low"])
    assert len(writer.calls) == len(v12.passes) <= 3
    assert v12.composer_settings.reasoning_effort == "low"
    assert v12.correction_settings.reasoning_effort == "low"
    assert v11.comparison_registry is not None
    assert v12.comparison_registry is not None
    assert v12.comparison_registry == v11.comparison_registry
    assert v12.selector_prepared.packet["exact_details"] == \
           v11.selector_prepared.packet["exact_details"]
    assert v12.focus_prepared.packet["selected_details"] == \
           v11.focus_prepared.packet["selected_details"]
    assert v12.focus_prepared.packet["temporal_comparisons"] == \
           v11.focus_prepared.packet["temporal_comparisons"]
    for old_pass, new_pass in zip(v11.passes, v12.passes, strict=True):
        assert old_pass.request["instructions"] == new_pass.request["instructions"]
        assert old_pass.request["text"] == new_pass.request["text"]
        old_packet = json.loads(old_pass.request["input"])
        new_packet = json.loads(new_pass.request["input"])
        old_packet["packet"].pop("selection_format")
        new_packet["packet"].pop("selection_format")
        old_packet["packet"].pop("composition_format", None)
        new_packet["packet"].pop("composition_format", None)
        assert old_packet == new_packet
    assert v12.resolved == v11.resolved
    assert replay_focused_results(parse_focused_artifact(v12.model_dump_json())) == v12.resolved
    tampered = v12.model_dump(mode="json")
    tampered["composer_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="settings differ"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(tampered))
