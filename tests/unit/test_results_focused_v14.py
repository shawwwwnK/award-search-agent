"""V14 purposeful selection notes stay separate from canonical authoring facts."""

import json
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer, _config, _source

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.contracts import WriterReceipt
from award_agent.results.focused import (
    _request,
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_comparison_contracts import FocusedResultsArtifactV11
from award_agent.results.focused_selection_plan import decode as decode_planned_selection
from award_agent.results.focused_selection_plan import instructions as planned_instructions
from award_agent.results.focused_selection_plan import instructions_v15
from award_agent.results.focused_selection_plan import schema as planned_schema
from award_agent.results.focused_v4 import LOW_SELECTOR_SETTINGS


class PlannedWriter:
    def __init__(self, *, bad_target: bool = False, missing_endpoint: bool = False,
                 selector_effort: str = "medium") -> None:
        self.bad_target, self.missing_endpoint = bad_target, missing_endpoint
        self.selector_effort = selector_effort
        self.requests = []
        self.pending = None

    def author(self, request, config, settings):
        index = len(self.requests)
        assert settings.reasoning_effort == ("low" if index == 2 else
                                            self.selector_effort if index == 0 else "medium")
        assert settings.service_tier == "fast"
        self.requests.append(request)
        payload = json.loads(request["input"])
        packet = payload["packet"]
        if index == 0:
            first, second = (list(packet["journey_records"])[:2] if
                             "journey_records" in packet else
                             [row[0] for row in packet["journey_rows"][:2]])
            raw = json.dumps({"choices": [
                {"k": "j", "r": first, "purpose": "Test an unsupported luxury hypothesis",
                 "compare_to": "J999" if self.bad_target else second},
                {"k": "j", "r": second, "purpose": "Compare the arrival and connection tradeoff",
                 "compare_to": first}]})
        else:
            assert packet["format"] == "focused-authoring-records-v2"
            refs = [ref for ref, row in packet["authoring_records"].items()
                    if row["role"] == "journey"]
            blocks = [{"k": "p", "r": refs[0], "n": "First", "v": "Useful first choice."}]
            if index == 2 or not self.missing_endpoint:
                blocks.append({"k": "a", "r": refs[1], "n": "Second",
                               "v": "Useful alternative with a real tradeoff."})
            if packet["temporal_comparisons"]:
                blocks.append({"k": "x", "r": packet["temporal_comparisons"][0]["id"]})
            raw = json.dumps({"blocks": blocks})
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self):
        receipt, self.pending = self.pending, None
        return receipt


@pytest.mark.parametrize("missing_endpoint", [False, True])
def test_v14_two_or_three_calls_keep_plan_unverified_and_replay(missing_endpoint) -> None:
    writer = PlannedWriter(missing_endpoint=missing_endpoint)
    artifact = run_focused_results(_source(), _config(), writer, FakeMeasurer(),
                                   profile="focused-v14")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v13"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v11"
    assert len(writer.requests) == (3 if missing_endpoint else 2)
    assert [p.request["reasoning"]["effort"] for p in artifact.passes] == (
        ["medium", "medium", "low"] if missing_endpoint else ["medium", "medium"])
    selected = json.loads(artifact.passes[1].request["input"])["packet"]
    plan = selected["editorial_plan"]
    assert len(plan) == 2
    assert all(row["status"] == "unverified_editorial_suggestion" for row in plan)
    assert all(row["ref"] in selected["authoring_records"] for row in plan)
    assert all(row["compare_to"] in selected["authoring_records"] for row in plan)
    assert "unsupported luxury hypothesis" in plan[0]["purpose"]
    assert "unsupported luxury hypothesis" not in json.dumps(selected["authoring_records"])
    assert artifact.selected_pass_index == (2 if missing_endpoint else 1)
    if missing_endpoint:
        assert selected == json.loads(artifact.passes[2].request["input"])["packet"]
        assert artifact.passes[1].findings[-1].code == "comparison_endpoint_not_visible"
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    changed = artifact.model_dump(mode="json")
    changed["focus_prepared"]["packet"]["editorial_plan"][0]["purpose"] = "tampered"
    with pytest.raises(ValueError, match="source packet|source|packet"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(changed))


def test_v14_unselected_compare_target_is_schema_failure_without_composer() -> None:
    writer = PlannedWriter(bad_target=True)
    artifact = run_focused_results(_source(), _config(), writer, FakeMeasurer(),
                                   profile="focused-v14")
    assert len(writer.requests) == len(artifact.passes) == 1
    assert artifact.passes[0].failure_subtype == "schema_error"
    assert artifact.delivery_outcome == "not_delivered"
    assert replay_focused_results(artifact) is None


@pytest.mark.parametrize("purpose,target,pattern", [
    (" ", None, "nonempty purpose"),
    ("Check a real tradeoff", "self", "another selected ref"),
    ("Check a real tradeoff", "J999", "another selected ref"),
])
def test_v14_plan_metadata_validation_keeps_exact_core_roles(purpose, target, pattern) -> None:
    source = _source()
    selector = prepare_focused_selector(source, _config(), selection_format="roles-v13")
    first, second = [row[0] for row in selector.packet["journey_rows"][:2]]
    shape = planned_schema(selector.structured, source)
    assert shape["properties"]["choices"]["maxItems"] == 8
    assert all(set(branch["required"]) == {"k", "r", "purpose", "compare_to"}
               for branch in shape["properties"]["choices"]["items"]["anyOf"])
    raw = {"choices": [{"k": "j", "r": first, "purpose": purpose,
                        "compare_to": first if target == "self" else target},
                       {"k": "j", "r": second, "purpose": "Useful comparison",
                        "compare_to": first}]}
    with pytest.raises(ValueError, match=pattern):
        decode_planned_selection(raw, selector.structured, source)


def test_v14_plan_rejects_wrong_source_role_even_with_valid_target() -> None:
    source = _source()
    selector = prepare_focused_selector(source, _config(), selection_format="roles-v13")
    first, second = [row[0] for row in selector.packet["journey_rows"][:2]]
    raw = {"choices": [{"k": "b", "r": first, "purpose": "Check a tradeoff",
                        "compare_to": second},
                       {"k": "j", "r": second, "purpose": "Compare arrival",
                        "compare_to": first}]}
    with pytest.raises(ValueError, match="wrong-role|unknown"):
        decode_planned_selection(raw, selector.structured, source)


@pytest.mark.parametrize("pass_index", [0, 1])
def test_replay_rejects_schema_failure_hiding_completed_author_wire(pass_index) -> None:
    artifact = run_focused_results(_source(), _config(), PlannedWriter(), FakeMeasurer(),
                                   profile="focused-v14")
    raw = artifact.model_dump(mode="json")
    attempt = raw["passes"][pass_index]
    attempt.update(outcome="generation_error", failure_subtype="schema_error",
                   error="fabricated schema failure", raw_wire=None,
                   selection=None, document=None, findings=[])
    with pytest.raises(ValueError, match="hides completed author wire"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(raw))


@pytest.mark.parametrize("pass_index", [0, 1])
def test_replay_accepts_completed_no_output_schema_failure(pass_index) -> None:
    artifact = run_focused_results(_source(), _config(), PlannedWriter(), FakeMeasurer(),
                                   profile="focused-v14")
    raw = artifact.model_dump(mode="json")
    attempt = raw["passes"][pass_index]
    response = {"status": "completed", "service_tier": "priority", "output": []}
    attempt["writer_receipt"]["raw_response"] = json.dumps(response)
    attempt.update(outcome="generation_error", failure_subtype="schema_error",
                   error="schema_error: no output text", raw_wire=None,
                   selection=None, document=None, findings=[])
    if pass_index == 0:
        raw["passes"] = raw["passes"][:1]
        raw["focus_prepared"] = None
        raw["comparison_registry"] = None
    raw.update(selected_pass_index=None, selection_reason="no_recoverable_draft",
               generation_outcome="generation_error", validation_outcome="unavailable",
               delivery_outcome="not_delivered", resolved=None, resolved_digest=None)
    assert replay_focused_results(FocusedResultsArtifactV11.model_validate(raw)) is None


@pytest.mark.parametrize("missing_endpoint", [False, True])
def test_v15_admitted_keeps_v14_brief_with_low_selector_effort(missing_endpoint) -> None:
    v14 = run_focused_results(_source(), _config(),
        PlannedWriter(missing_endpoint=missing_endpoint), FakeMeasurer(), profile="focused-v14")
    v15 = run_focused_results(_source(), _config(),
        PlannedWriter(missing_endpoint=missing_endpoint, selector_effort="low"),
        FakeMeasurer(), profile="focused-v15")
    assert isinstance(v15, FocusedResultsArtifactV11)
    assert v15.selector_prepared.packet["selection_format"] == "roles-v14"
    assert v15.focus_prepared is not None
    assert v15.focus_prepared.packet["composition_format"] == "complete-v12"
    assert [p.request["reasoning"]["effort"] for p in v15.passes] == (
        ["low", "medium", "low"] if missing_endpoint else ["low", "medium"])
    assert v15.composer_settings == v14.composer_settings
    assert v15.correction_settings == v14.correction_settings
    assert v15.comparison_registry == v14.comparison_registry
    assert v15.resolved == v14.resolved
    assert len(v15.passes) == len(v14.passes) <= 3
    for old, new in zip(v14.passes, v15.passes, strict=True):
        assert old.request["instructions"] == new.request["instructions"]
        assert old.request["text"] == new.request["text"]
        old_input = json.loads(old.request["input"])
        new_input = json.loads(new.request["input"])
        old_input["packet"].pop("selection_format")
        new_input["packet"].pop("selection_format")
        old_input["packet"].pop("composition_format", None)
        new_input["packet"].pop("composition_format", None)
        assert old_input == new_input
    assert replay_focused_results(parse_focused_artifact(v15.model_dump_json())) == v15.resolved
    tampered = v15.model_dump(mode="json")
    tampered["selector_settings"]["reasoning_effort"] = "medium"
    with pytest.raises(ValueError, match="settings differ"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(tampered))


def test_v15_incomplete_selector_adds_only_lead_comparison_clarification() -> None:
    path = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/runs/confirm-v11-default-1-incomplete/artifact.json")
    archived = parse_focused_artifact(path.read_bytes())
    source = SolutionProjection.model_validate(archived.evidence.source.model_dump(mode="json"))
    v14 = prepare_focused_selector(source, _config(), archived.evidence,
                                   selection_format="roles-v13")
    v15 = prepare_focused_selector(source, _config(), archived.evidence,
                                   selection_format="roles-v14")
    before = planned_instructions(v14.structured, source)
    after = instructions_v15(v15.structured, source)
    assert after.startswith(before)
    added = after.removeprefix(before)
    assert "lead-to-lead difference" in added
    assert "potential upside and its real tradeoff" in added
    assert "cash as a separate baseline" in added
    assert "one lead is enough" in added
    assert "unverified hypotheses" in added
    assert planned_schema(v14.structured, source) == planned_schema(v15.structured, source)
    envelope = _request(v15, _config(), LOW_SELECTOR_SETTINGS, "selection", source)
    assert envelope.request["instructions"] == after
    assert envelope.request["reasoning"] == {"effort": "low"}
