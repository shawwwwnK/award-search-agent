import json
from datetime import date
from types import SimpleNamespace
from typing import cast

import pytest
from openai import OpenAI
from openai.lib._pydantic import to_strict_json_schema

from award_agent.domain import (
    AnchorWindowConstraint,
    CalendarPeriodSemantics,
    CoarseIntentExtraction,
    DurationModifier,
    Holiday,
    HolidayAnchor,
    MonthPortionConstraint,
    RawRequest,
    RelativeCalendarPeriodConstraint,
    RelativeOffsetConstraint,
    RelativeWeekdayConstraint,
    RelativeWeekendConstraint,
    RequestContext,
    SemanticDurationConstraint,
    TemporalDirection,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalTarget,
    TemporalUnit,
    UnboundedBoundaryConstraint,
    UnresolvedRelationConstraint,
    Weekday,
)
from award_agent.intent.evidence import (
    TemporalResolutionValidationError,
    assign_stable_anchor_ids,
    ground_temporal_evidence,
)
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    ExplicitAnchorCatalogEntry,
    RejectedCoarseExtractionView,
    StructuredValidationErrorView,
    SymbolicReferenceCatalogEntry,
    TemporalEvidenceCatalogEntry,
    TemporalInterpretationInput,
    build_temporal_interpretation_input,
)
from award_agent.intent.openai_extractor import (
    AnchorWindowWire,
    DateResolutionError,
    DurationWire,
    IntentExtractionError,
    MonthPortionWire,
    OpenAIExtractorConfig,
    OpenAIIntentExtractor,
    RelativeCalendarPeriodWire,
    RelativeOffsetWire,
    RelativeWeekdayWire,
    RelativeWeekendWire,
    TemporalDecisionSetWire,
    TemporalDecisionWire,
    TemporalRelationGraphWire,
    UnboundedBoundaryWire,
    UnresolvedWire,
)


class FakeResponses:
    def __init__(
        self,
        outputs: list[object | None],
        usages: list[object | None] | None = None,
    ) -> None:
        self.outputs = outputs
        self.usages = usages or [None] * len(outputs)
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_parsed=self.outputs.pop(0),
            usage=self.usages.pop(0),
        )


class FakeClient:
    def __init__(
        self,
        outputs: list[object | None],
        usages: list[object | None] | None = None,
    ) -> None:
        self.responses = FakeResponses(outputs, usages)


class TraceResponse:
    def __init__(self, output: object | None) -> None:
        self.output_parsed = output
        self.usage = None

    def model_dump_json(self) -> str:
        return '{"id":"response-1","output":[{"type":"output_text"}]}'


class TraceResponses:
    def __init__(self, output: object | None) -> None:
        self.output = output

    def parse(self, **_kwargs: object) -> TraceResponse:
        return TraceResponse(self.output)


class TraceClient:
    def __init__(self, output: object | None) -> None:
        self.responses = TraceResponses(output)


class FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int, total_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens

    def model_dump(self, *, mode: str) -> dict[str, int]:
        assert mode == "json"
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


def test_post_conformance_repair_serializes_only_the_retained_local_decision_wire() -> None:
    raw_request = RawRequest(
        text="Travel Labor Day weekend.",
        context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
    )
    extraction = CoarseIntentExtraction(
        date_anchors=[
            HolidayAnchor(
                kind="holiday",
                anchor_id="model-local",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="Labor Day",
                holiday=Holiday.LABOR_DAY,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="Labor Day weekend",
                claim_ids=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
            )
        ],
    )
    evidence = ground_temporal_evidence(raw_request, extraction)
    extraction = assign_stable_anchor_ids(raw_request, extraction)
    model_input = build_temporal_interpretation_input(raw_request.text, extraction, evidence)
    evidence_handle = next(
        entry.handle for entry in model_input.evidence_catalog if entry.text == "Labor Day weekend"
    )
    local_wire = TemporalDecisionSetWire(
        decisions=[
            TemporalDecisionWire(
                evidence=evidence_handle,
                relation_kind="anchor_window",
                target="departure",
                anchor="a0",
                window="holiday_weekend",
            )
        ]
    )
    client = FakeClient([local_wire, local_wire])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    resolved = extractor.resolve_dates(model_input)
    canonical_evidence = model_input._evidence_ids[evidence_handle]
    repaired = extractor.repair_dates(
        model_input,
        resolved.relations,
        [
            StructuredValidationErrorView(
                stage="pass_two_conformance",
                error_code="incompatible_relation_fields",
                evidence_id=canonical_evidence,
                reference_id=model_input._anchor_ids["a0"],
                validation_cause="canonical implementation detail must not cross the boundary",
            )
        ],
    )

    assert len(repaired.constraints) == 1
    repair_payload = str(client.responses.calls[1]["input"])
    assert '"evidence":"' + evidence_handle + '"' in repair_payload
    for prohibited in (
        canonical_evidence,
        model_input._anchor_ids["a0"],
        "request:",
        "anchor:",
        "relation:",
        "canonical implementation detail",
    ):
        assert prohibited not in repair_payload


def request() -> RawRequest:
    return RawRequest(
        text="Travel in May.",
        context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
    )


def coarse_input() -> CoarseExtractionInput:
    return CoarseExtractionInput(request_text=request().text)


def temporal_input() -> TemporalInterpretationInput:
    return TemporalInterpretationInput(
        temporal_transcript="Travel in May.",
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id="request:10:13",
                text="May",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_ANCHOR],
                source_order=0,
                source_start=10,
                source_end=13,
            )
        ],
        explicit_anchor_catalog=[
            ExplicitAnchorCatalogEntry(
                anchor_id="month_1",
                kind="month",
                applies_to=TemporalTarget.DEPARTURE,
                direct_relation_kind="month_portion",
            ),
            ExplicitAnchorCatalogEntry(
                anchor_id="date_1",
                kind="exact_date",
                applies_to=TemporalTarget.DEPARTURE,
                direct_relation_kind="anchor_window",
            ),
        ],
        allowed_symbolic_references=[
            SymbolicReferenceCatalogEntry.from_key("context:request_date"),
            SymbolicReferenceCatalogEntry.from_key("anchor_ref:month_1:start"),
            SymbolicReferenceCatalogEntry.from_key("anchor_ref:month_1:end"),
            SymbolicReferenceCatalogEntry.from_key("request_field:departure:end"),
        ],
    )


def next_month_temporal_input() -> TemporalInterpretationInput:
    return TemporalInterpretationInput(
        temporal_transcript="Travel next month.",
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id="request:7:17",
                text="next month",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
                source_order=0,
                source_start=7,
                source_end=17,
            )
        ],
        allowed_symbolic_references=[
            SymbolicReferenceCatalogEntry.from_key("context:request_date")
        ],
    )


def test_two_pass_usage_capture_includes_repair_and_resets_between_workflows() -> None:
    invalid_wire = TemporalRelationGraphWire(
        unresolved=[
            UnresolvedWire(
                target="departure",
                evidence_id="request:invented",
                reason="bad catalog selection",
            )
        ]
    )
    repaired_wire = TemporalRelationGraphWire(
        relative_calendar_periods=[
            RelativeCalendarPeriodWire(
                target=TemporalTarget.DEPARTURE,
                reference_key="context:request_date",
                direction=TemporalDirection.AFTER,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                evidence_id="request:7:17",
            )
        ]
    )
    client = FakeClient(
        [
            CoarseIntentExtraction(),
            CoarseIntentExtraction(),
            invalid_wire,
            repaired_wire,
            CoarseIntentExtraction(travelers=2),
        ],
        [
            FakeUsage(10, 2, 12),
            FakeUsage(4, 2, 6),
            FakeUsage(20, 4, 24),
            FakeUsage(5, 1, 6),
            FakeUsage(7, 3, 10),
        ],
    )
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    extractor.reset_usage()
    extractor.extract(coarse_input())
    repair_error = TemporalResolutionValidationError(
        "repair pass one",
        stage="pass_one_grounding",
        error_code="ungrounded_quote",
    )
    extractor.repair_extract(
        CoarseExtractionRepairInput(
            original_input=coarse_input(),
            rejected_output=RejectedCoarseExtractionView.from_output(CoarseIntentExtraction()),
            validation_errors=[StructuredValidationErrorView.from_details(repair_error.details)],
        )
    )
    resolved = extractor.resolve_dates(next_month_temporal_input())
    first_usage = extractor.take_usage()

    assert resolved.repair_trace.repair_succeeded is True
    assert first_usage == {
        "calls": 4,
        "captured_calls": 4,
        "missing_calls": 0,
        "input_tokens": 39,
        "output_tokens": 9,
        "total_tokens": 48,
    }
    assert all("usage" not in str(call["input"]) for call in client.responses.calls)

    extractor.extract(coarse_input())
    assert extractor.take_usage() == {
        "calls": 1,
        "captured_calls": 1,
        "missing_calls": 0,
        "input_tokens": 7,
        "output_tokens": 3,
        "total_tokens": 10,
    }
    assert extractor.take_usage() is None


def test_usage_capture_remains_explicitly_unavailable_when_response_omits_usage() -> None:
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, FakeClient([CoarseIntentExtraction()])),
    )

    extractor.reset_usage()
    extractor.extract(coarse_input())

    assert extractor.take_usage() is None


def duration_temporal_input() -> TemporalInterpretationInput:
    return TemporalInterpretationInput(
        temporal_transcript="Stay for 1 or 2 weeks.",
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id="request:5:21",
                text="for 1 or 2 weeks",
                claim_labels=[TemporalEvidenceClaim.DURATION],
                source_order=0,
                source_start=5,
                source_end=21,
            )
        ],
        allowed_symbolic_references=[
            SymbolicReferenceCatalogEntry.from_key("request_field:departure:end")
        ],
    )


def test_openai_extractor_uses_coarse_structured_output_without_storing_response() -> None:
    client = FakeClient([CoarseIntentExtraction(travelers=2)])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    result = extractor.extract(coarse_input())

    call = client.responses.calls[0]
    assert result.travelers == 2
    assert call["model"] == "test-model"
    assert "preserve" in str(call["instructions"]).casefold()
    assert "normalized semantic-name candidate" in str(call["instructions"]).casefold()
    assert 'raw_text "lax" has value "lax"' in str(call["instructions"]).casefold()
    assert "never expand a city into airports" in str(call["instructions"]).casefold()
    instructions = str(call["instructions"])
    assert "Every quote must be one" in instructions
    assert "contiguous substring" in instructions
    assert "Never combine words from separate positions" in instructions
    assert "shortest contiguous quote that fully supports" in instructions
    assert "occurrence_index is zero-based" in instructions
    assert 'Invalid evidence is "leave on Sunday"' in instructions
    assert "Do not calculate character offsets" in instructions
    assert "Anchor claims" not in instructions  # prose uses the exact enum labels below
    assert "departure_anchor / return_anchor" in instructions
    assert '"next month" and "next spring"' in instructions.casefold()
    assert "empty date_anchors and temporal_phrases" in instructions
    assert call["text_format"] is CoarseIntentExtraction
    assert call["store"] is False
    payload = json.loads(str(call["input"]))
    assert payload == {"request_text": "Travel in May."}
    assert "reference_date" not in str(call["input"])
    assert "timezone" not in str(call["input"])


def test_openai_extractor_captures_exact_model_call_when_enabled() -> None:
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, TraceClient(CoarseIntentExtraction(travelers=2))),
        capture_llm_io=True,
    )

    extractor.extract(coarse_input())

    traces = extractor.take_call_traces()
    assert len(traces) == 1
    trace = traces[0]
    assert trace["stage"] == "pass_one"
    request_payload = trace["request"]
    assert isinstance(request_payload, dict)
    assert request_payload["model"] == "test-model"
    assert request_payload["input"] == '{"request_text":"Travel in May."}'
    assert request_payload["store"] is False
    schema = request_payload["text_format"]
    assert isinstance(schema, dict)
    assert schema["name"] == "CoarseIntentExtraction"
    assert trace["response_json"] == '{"id":"response-1","output":[{"type":"output_text"}]}'
    parsed_output = trace["parsed_output"]
    assert isinstance(parsed_output, dict)
    assert parsed_output["travelers"] == 2
    assert trace["error"] is None
    assert extractor.take_call_traces() == []


def test_openai_extractor_captures_provider_exception_when_enabled() -> None:
    class FailingResponses:
        def parse(self, **_kwargs: object) -> TraceResponse:
            raise TimeoutError("provider timed out")

    class FailingClient:
        def __init__(self) -> None:
            self.responses = FailingResponses()

    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, FailingClient()),
        capture_llm_io=True,
    )

    with pytest.raises(IntentExtractionError):
        extractor.extract(coarse_input())

    trace = extractor.take_call_traces()[0]
    assert trace["response_json"] is None
    assert trace["parsed_output"] is None
    assert trace["error"] == {"type": "TimeoutError", "message": "provider timed out"}


def test_repair_prompt_allows_only_explicit_source_years() -> None:
    client = FakeClient([CoarseIntentExtraction()])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )
    error = TemporalResolutionValidationError(
        "invalid explicit anchor",
        stage="pass_one_anchor_validation",
        error_code="anchor_kind_evidence_mismatch",
        validation_cause="literal evidence does not name the selected month",
    )

    extractor.repair_extract(
        CoarseExtractionRepairInput(
            original_input=coarse_input(),
            rejected_output=RejectedCoarseExtractionView.from_output(CoarseIntentExtraction()),
            validation_errors=[StructuredValidationErrorView.from_details(error.details)],
        )
    )

    instructions = str(client.responses.calls[0]["instructions"])
    assert "unstated year" in instructions
    assert "original_input.request_text" in instructions
    assert "Contract-v2 decision list" not in instructions


def test_openai_resolver_receives_only_date_free_temporal_catalogs() -> None:
    wire_relations = TemporalRelationGraphWire(
        month_portions=[
            MonthPortionWire(
                target=TemporalTarget.DEPARTURE,
                anchor_id="month_1",
                portion="whole",
                evidence_id="request:10:13",
            )
        ]
    )
    client = FakeClient([wire_relations])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )
    result = extractor.resolve_dates(temporal_input())

    call = client.responses.calls[0]
    payload = json.loads(str(call["input"]))
    assert len(result.relations.constraints) == 1
    assert result.repair_trace.first_attempt_valid is True
    assert [item["handle"] for item in payload["explicit_anchor_catalog"]] == ["a0", "a1"]
    references = {entry["handle"]: entry for entry in payload["allowed_symbolic_references"]}
    assert references["r0"]["allowed_relation_kinds"] == ["relative_calendar_period"]
    assert references["r3"]["allowed_targets"] == ["return"]
    assert "duration" in references["r3"]["allowed_relation_kinds"]
    assert "duration" not in payload["evidence_catalog"][0]["allowed_relation_kinds"]
    serialized = str(call["input"])
    for prohibited in (
        "request:10:13",
        "month_1",
        "date_1",
        "reference_date",
        "timezone",
        "resolved_anchors",
        "2027-05-01",
        "source_detail",
        "travelers",
        "origins",
        "destinations",
    ):
        assert prohibited not in serialized
    assert getattr(call["text_format"], "__name__", None) == "TemporalDecisionSetWireForInput"
    assert call["store"] is False


def test_openai_resolver_instructions_define_semantic_relation_boundary() -> None:
    client = FakeClient(
        [
            TemporalRelationGraphWire(
                unresolved=[
                    UnresolvedWire(
                        target="departure",
                        evidence_id="request:10:13",
                        reason="No supported interpretation.",
                    )
                ]
            )
        ]
    )
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    extractor.resolve_dates(temporal_input())

    instructions = str(client.responses.calls[0]["instructions"])
    assert "bounded decisions" in instructions
    assert "Never propose, copy, or calculate final dates" in instructions
    assert "decision.evidence" in instructions
    assert "extend_start" in instructions
    assert "whole departure interval" in instructions


def test_temporal_relation_graph_is_strict_structured_output_compatible() -> None:
    schema = to_strict_json_schema(TemporalRelationGraphWire)
    serialized = json.dumps(schema)

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "oneOf" not in serialized
    assert "anyOf" not in serialized
    expected_collections = {
        "anchor_windows",
        "month_portions",
        "relative_calendar_periods",
        "relative_weekends",
        "relative_weekdays",
        "relative_offsets",
        "durations",
        "unbounded_boundaries",
        "unresolved",
    }
    assert set(schema["properties"]) == expected_collections
    assert set(schema["required"]) == expected_collections
    for definition in schema["$defs"].values():
        if definition.get("type") == "object":
            assert set(definition["required"]) == set(definition["properties"])
    duration_properties = schema["$defs"]["DurationWire"]["properties"]
    assert set(duration_properties) == {
        "stated_minimum_quantity",
        "stated_maximum_quantity",
        "unit",
        "modifier",
        "evidence_id",
    }
    assert "minimum_days" not in serialized
    assert "maximum_days" not in serialized


def test_model_facing_schemas_put_semantic_rules_next_to_governing_fields() -> None:
    coarse = to_strict_json_schema(CoarseIntentExtraction)
    wire = to_strict_json_schema(TemporalRelationGraphWire)

    claim_description = coarse["$defs"]["TemporalPhrase"]["properties"]["claim_ids"]["description"]
    anchor_description = coarse["properties"]["date_anchors"]["description"]
    assert "*_anchor only for a literal date" in claim_description
    assert "duration for exact trip length" in claim_description
    assert "next month" in anchor_description
    assert "season" in anchor_description

    evidence_description = wire["$defs"]["DurationWire"]["properties"]["evidence_id"]["description"]
    minimum_description = wire["$defs"]["DurationWire"]["properties"]["stated_minimum_quantity"][
        "description"
    ]
    reference_description = wire["$defs"]["RelativeWeekendWire"]["properties"]["reference_key"][
        "description"
    ]
    unresolved_target = wire["$defs"]["UnresolvedWire"]["properties"]["target"]["description"]
    assert "evidence_id" in evidence_description
    assert "'a week' means 1, never 7" in minimum_description
    assert "allowed_targets lists target" in reference_description
    assert "allowed_relation_kinds lists relative_weekend" in reference_description
    assert "calendar policy is unsupported" in unresolved_target


def test_strict_output_schemas_use_only_supported_union_shapes() -> None:
    """The live-supported pass-one unions are nullable scalars or the anchor ref union."""

    for contract in (CoarseIntentExtraction, TemporalRelationGraphWire):
        schema = to_strict_json_schema(contract)
        serialized = json.dumps(schema)
        assert "oneOf" not in serialized

        def visit(value: object) -> None:
            if isinstance(value, dict):
                if "anyOf" in value:
                    alternatives = value["anyOf"]
                    assert isinstance(alternatives, list)
                    nullable = any(
                        isinstance(item, dict) and item.get("type") == "null"
                        for item in alternatives
                    )
                    anchor_union = all(
                        isinstance(item, dict) and "$ref" in item for item in alternatives
                    )
                    assert nullable or anchor_union
                for nested in value.values():
                    visit(nested)
            elif isinstance(value, list):
                for nested in value:
                    visit(nested)

        visit(schema)


@pytest.mark.parametrize(
    ("minimum", "maximum", "modifier", "message"),
    [
        (1, 2, DurationModifier.EXACT, "require one stated quantity"),
        (1, 2, DurationModifier.APPROXIMATE, "require one stated quantity"),
        (1, 1, DurationModifier.ALTERNATIVE, "requires distinct stated quantities"),
        (2, 1, DurationModifier.ALTERNATIVE, "maximum stated duration precedes"),
    ],
)
def test_duration_wire_conversion_rejects_invalid_literal_shapes_structurally(
    minimum: int,
    maximum: int,
    modifier: DurationModifier,
    message: str,
) -> None:
    wire = TemporalRelationGraphWire(
        durations=[
            DurationWire(
                stated_minimum_quantity=minimum,
                stated_maximum_quantity=maximum,
                unit=TemporalUnit.WEEK,
                modifier=modifier,
                evidence_id="request:5:21",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError, match=message) as captured:
        wire.to_domain(duration_temporal_input())

    details = captured.value.details
    assert details.stage == "pass_two_wire_conversion"
    assert details.collection == "durations"
    assert details.relation_index == 0
    assert details.constraint_index == 0
    assert details.selected_relation_kind == "duration"
    assert details.contradictory_fields == (
        "stated_minimum_quantity",
        "stated_maximum_quantity",
        "modifier",
    )
    assert details.evidence_id == "request:5:21"
    assert message in details.validation_cause


def test_fixed_wire_collections_convert_exhaustively_to_typed_graph() -> None:
    wire = TemporalRelationGraphWire(
        anchor_windows=[
            AnchorWindowWire(
                target=TemporalTarget.DEPARTURE,
                anchor_id="date_1",
                window="anchor",
                evidence_id="request:10:13",
            )
        ],
        month_portions=[
            MonthPortionWire(
                target=TemporalTarget.DEPARTURE,
                anchor_id="month_1",
                portion="early",
                evidence_id="request:10:13",
            )
        ],
        relative_calendar_periods=[
            RelativeCalendarPeriodWire(
                target=TemporalTarget.DEPARTURE,
                reference_key="context:request_date",
                direction=TemporalDirection.AFTER,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                evidence_id="request:10:13",
            )
        ],
        relative_weekends=[
            RelativeWeekendWire(
                target=TemporalTarget.RETURN,
                reference_key="request_field:departure:end",
                direction=TemporalDirection.AFTER,
                ordinal=1,
                evidence_id="request:10:13",
            )
        ],
        relative_weekdays=[
            RelativeWeekdayWire(
                target=TemporalTarget.RETURN,
                reference_key="anchor_ref:month_1:end",
                direction=TemporalDirection.AFTER,
                ordinal=1,
                weekday=Weekday.THURSDAY,
                evidence_id="request:10:13",
            )
        ],
        relative_offsets=[
            RelativeOffsetWire(
                target=TemporalTarget.RETURN,
                reference_key="anchor_ref:month_1:end",
                direction=TemporalDirection.AFTER,
                amount=2,
                unit=TemporalUnit.WEEK,
                evidence_id="request:10:13",
            )
        ],
        durations=[
            DurationWire(
                stated_minimum_quantity=10,
                stated_maximum_quantity=10,
                unit=TemporalUnit.DAY,
                modifier=DurationModifier.APPROXIMATE,
                evidence_id="request:10:13",
            )
        ],
        unbounded_boundaries=[
            UnboundedBoundaryWire(
                target=TemporalTarget.DEPARTURE,
                reference_key="anchor_ref:month_1:start",
                direction=TemporalDirection.AFTER,
                evidence_id="request:10:13",
            )
        ],
        unresolved=[
            UnresolvedWire(
                target="unspecified",
                evidence_id="request:10:13",
                reason="unsupported wording",
            )
        ],
    )

    exhaustive_input = temporal_input().model_copy(
        update={
            "evidence_catalog": [
                temporal_input()
                .evidence_catalog[0]
                .model_copy(
                        update={
                            "claim_labels": list(TemporalEvidenceClaim),
                            "allowed_targets": ["departure", "return", "unspecified"],
                            "allowed_relation_kinds": [
                            "anchor_window",
                            "month_portion",
                            "relative_calendar_period",
                            "relative_weekend",
                            "relative_weekday",
                            "relative_offset",
                            "duration",
                            "unbounded_boundary",
                            "unresolved",
                        ],
                    }
                )
            ]
        }
    )
    graph = wire.to_domain(exhaustive_input)

    assert [type(item) for item in graph.constraints] == [
        AnchorWindowConstraint,
        MonthPortionConstraint,
        RelativeCalendarPeriodConstraint,
        RelativeWeekendConstraint,
        RelativeWeekdayConstraint,
        RelativeOffsetConstraint,
        SemanticDurationConstraint,
        UnboundedBoundaryConstraint,
        UnresolvedRelationConstraint,
    ]
    duration = graph.constraints[6]
    assert isinstance(duration, SemanticDurationConstraint)
    assert duration.target is TemporalTarget.RETURN
    assert duration.reference.field is TemporalTarget.DEPARTURE
    assert duration.reference.edge is not None
    assert duration.reference.edge.value == "end"
    assert duration.stated_minimum_quantity == 10
    assert duration.stated_maximum_quantity == 10
    assert duration.modifier is DurationModifier.APPROXIMATE
    unresolved = graph.constraints[-1]
    assert isinstance(unresolved, UnresolvedRelationConstraint)
    assert unresolved.target is None


def test_wire_rejects_invented_evidence_id() -> None:
    wire = TemporalRelationGraphWire(
        unresolved=[
            UnresolvedWire(
                target="departure",
                evidence_id="request:invented",
                reason="ambiguous wording",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        wire.to_domain(temporal_input())

    assert "evidence is not in supplied catalog" in str(captured.value)
    assert captured.value.details.error_code == "unknown_evidence_id"
    assert captured.value.details.collection == "unresolved"
    assert captured.value.details.relation_index == 0


def test_wire_rejects_invented_anchor_id() -> None:
    wire = TemporalRelationGraphWire(
        anchor_windows=[
            AnchorWindowWire(
                target=TemporalTarget.DEPARTURE,
                anchor_id="invented",
                window="anchor",
                evidence_id="request:10:13",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        wire.to_domain(temporal_input())

    assert "anchor is not in supplied catalog" in str(captured.value)
    assert captured.value.details.error_code == "unknown_anchor_id"
    assert captured.value.details.reference_id == "invented"


def test_wire_rejects_invented_symbolic_reference_key() -> None:
    wire = TemporalRelationGraphWire(
        relative_weekends=[
            RelativeWeekendWire(
                target=TemporalTarget.RETURN,
                reference_key="request_field:invented:end",
                direction=TemporalDirection.AFTER,
                ordinal=1,
                evidence_id="request:10:13",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        wire.to_domain(temporal_input())

    assert "reference is not in supplied catalog" in str(captured.value)
    assert captured.value.details.error_code == "unknown_reference_key"
    assert captured.value.details.reference_id == "request_field:invented:end"


def test_wire_rejects_cataloged_self_reference_with_local_coordinates() -> None:
    wire = TemporalRelationGraphWire(
        relative_weekends=[
            RelativeWeekendWire(
                target=TemporalTarget.DEPARTURE,
                reference_key="request_field:departure:end",
                direction=TemporalDirection.AFTER,
                ordinal=1,
                evidence_id="request:10:13",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        wire.to_domain(temporal_input())

    details = captured.value.details
    assert details.error_code == "incompatible_reference_target"
    assert details.collection == "relative_weekends"
    assert details.relation_index == 0
    assert details.constraint_index == 0
    assert details.evidence_id == "request:10:13"
    assert details.reference_id == "request_field:departure:end"
    assert details.contradictory_fields == ("reference_key", "target")


def test_wire_rejects_reference_not_permitted_for_relation_kind() -> None:
    wire = TemporalRelationGraphWire(
        relative_weekends=[
            RelativeWeekendWire(
                target=TemporalTarget.DEPARTURE,
                reference_key="context:request_date",
                direction=TemporalDirection.AFTER,
                ordinal=1,
                evidence_id="request:10:13",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        wire.to_domain(temporal_input())

    assert captured.value.details.error_code == "incompatible_reference_relation"
    assert captured.value.details.reference_id == "context:request_date"
    assert captured.value.details.contradictory_fields == (
        "reference_key",
        "relation_kind",
    )


def test_wire_rejects_duration_selected_from_non_duration_evidence() -> None:
    wire = TemporalRelationGraphWire(
        durations=[
            DurationWire(
                stated_minimum_quantity=1,
                stated_maximum_quantity=1,
                unit=TemporalUnit.WEEK,
                modifier=DurationModifier.EXACT,
                evidence_id="request:10:13",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        wire.to_domain(temporal_input())

    details = captured.value.details
    assert details.error_code == "incompatible_evidence_relation"
    assert details.collection == "durations"
    assert details.evidence_id == "request:10:13"
    assert details.contradictory_fields == ("evidence_id", "relation_kind")


def test_context_request_date_is_visible_but_private_value_is_absent() -> None:
    payload = temporal_input().model_dump(mode="json")

    assert {entry["handle"] for entry in payload["allowed_symbolic_references"]} >= {
        "context:request_date"
    }
    assert "2026-08-30" not in json.dumps(payload)


def test_next_month_wire_selects_private_context_reference_and_catalog_evidence() -> None:
    model_input = TemporalInterpretationInput(
        temporal_transcript="Travel next month.",
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id="request:7:17",
                text="next month",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
                source_order=0,
                source_start=7,
                source_end=17,
            )
        ],
        allowed_symbolic_references=[
            SymbolicReferenceCatalogEntry.from_key("context:request_date")
        ],
    )
    wire = TemporalRelationGraphWire(
        relative_calendar_periods=[
            RelativeCalendarPeriodWire(
                target=TemporalTarget.DEPARTURE,
                reference_key="context:request_date",
                direction=TemporalDirection.AFTER,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                evidence_id="request:7:17",
            )
        ]
    )

    relation = wire.to_domain(model_input).constraints[0]

    assert isinstance(relation, RelativeCalendarPeriodConstraint)
    assert relation.raw_text == "next month"
    assert relation.reference.key == "context:request_date"
    assert relation.period_semantics is CalendarPeriodSemantics.WHOLE


def test_relative_calendar_period_rejects_unsupplied_context_reference() -> None:
    wire = RelativeCalendarPeriodWire(
        target=TemporalTarget.DEPARTURE,
        reference_key="context:request_date",
        direction=TemporalDirection.AFTER,
        ordinal=1,
        period_semantics=CalendarPeriodSemantics.WHOLE,
        evidence_id="request:10:13",
    )
    model_input = temporal_input().model_copy(update={"allowed_symbolic_references": []})

    with pytest.raises(ValueError, match="reference is not in supplied catalog"):
        wire.to_domain(model_input)


def test_wire_rejects_noncanonical_direct_month_relation() -> None:
    wire = TemporalRelationGraphWire(
        anchor_windows=[
            AnchorWindowWire(
                target=TemporalTarget.DEPARTURE,
                anchor_id="month_1",
                window="holiday_weekend",
                evidence_id="request:10:13",
            )
        ]
    )

    with pytest.raises(ValueError, match="anchor_window is not the canonical direct use"):
        wire.to_domain(temporal_input())


def test_wire_rejects_relation_incompatible_anchor_target() -> None:
    wire = TemporalRelationGraphWire(
        anchor_windows=[
            AnchorWindowWire(
                target=TemporalTarget.RETURN,
                anchor_id="date_1",
                window="anchor",
                evidence_id="request:10:13",
            )
        ]
    )

    with pytest.raises(ValueError, match="anchor target is incompatible"):
        wire.to_domain(temporal_input())


def test_openai_extractor_fails_explicitly_when_output_is_missing() -> None:
    client = FakeClient([None])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    with pytest.raises(IntentExtractionError, match="no parsed coarse intent"):
        extractor.extract(coarse_input())


def test_openai_resolver_fails_explicitly_when_output_is_missing() -> None:
    client = FakeClient([None])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    with pytest.raises(DateResolutionError, match="no parsed date-resolution"):
        extractor.resolve_dates(temporal_input())


def test_openai_resolver_preserves_structured_wire_conversion_failure() -> None:
    client = FakeClient(
        [
            TemporalRelationGraphWire(
                unresolved=[
                    UnresolvedWire(
                        target="departure",
                        evidence_id="request:invented",
                        reason="unsupported wording",
                    )
                ]
            ),
            TemporalRelationGraphWire(
                unresolved=[
                    UnresolvedWire(
                        target="departure",
                        evidence_id="request:still-invented",
                        reason="unsupported wording",
                    )
                ]
            ),
        ]
    )
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        extractor.resolve_dates(temporal_input())

    assert captured.value.details.stage == "pass_two_wire_conversion"
    assert captured.value.details.error_code == "unknown_evidence_id"
    assert "invalid temporal reference" not in str(captured.value)
    assert len(client.responses.calls) == 2
    assert captured.value.repair_trace["repair_ran"] is True


def test_openai_resolver_repairs_wire_once_with_date_free_original_context() -> None:
    client = FakeClient(
        [
            TemporalRelationGraphWire(
                unresolved=[
                    UnresolvedWire(
                        target="departure",
                        evidence_id="request:invented",
                        reason="bad catalog selection",
                    )
                ]
            ),
            TemporalRelationGraphWire(
                relative_calendar_periods=[
                    RelativeCalendarPeriodWire(
                        target=TemporalTarget.DEPARTURE,
                        reference_key="context:request_date",
                        direction=TemporalDirection.AFTER,
                        ordinal=1,
                        period_semantics=CalendarPeriodSemantics.WHOLE,
                        evidence_id="request:7:17",
                    )
                ]
            ),
        ]
    )
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    result = extractor.resolve_dates(next_month_temporal_input())

    assert len(client.responses.calls) == 2
    assert result.repair_trace.repair_succeeded is True
    repair_payload = json.loads(str(client.responses.calls[1]["input"]))
    assert set(repair_payload) == {
        "original_input",
        "rejected_output",
        "validation_errors",
    }
    serialized = str(client.responses.calls[1]["input"])
    for prohibited in (
        "request:5:21",
        "reference_date",
        "timezone",
        "2026-08-30",
        "2026-09-01",
        "September",
        "source_detail",
        "expected",
    ):
        assert prohibited not in serialized


def test_invalid_duration_wire_gets_one_bounded_successful_repair() -> None:
    invalid = TemporalRelationGraphWire(
        durations=[
            DurationWire(
                stated_minimum_quantity=1,
                stated_maximum_quantity=2,
                unit=TemporalUnit.WEEK,
                modifier=DurationModifier.EXACT,
                evidence_id="request:5:21",
            )
        ]
    )
    repaired = TemporalRelationGraphWire(
        durations=[
            DurationWire(
                stated_minimum_quantity=1,
                stated_maximum_quantity=2,
                unit=TemporalUnit.WEEK,
                modifier=DurationModifier.ALTERNATIVE,
                evidence_id="request:5:21",
            )
        ]
    )
    client = FakeClient([invalid, repaired])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    result = extractor.resolve_dates(duration_temporal_input())

    assert len(client.responses.calls) == 2
    assert result.repair_trace.first_attempt_valid is False
    assert result.repair_trace.repair_ran is True
    assert result.repair_trace.repair_succeeded is True
    assert len(result.relations.constraints) == 1
    repair_payload = json.loads(str(client.responses.calls[1]["input"]))
    error = repair_payload["validation_errors"][0]
    assert error["stage"] == "pass_two_wire_conversion"
    assert error["collection"] == "durations"
    assert error["relation_index"] == 0
    assert error["constraint_index"] == 0
    assert error["selected_relation_kind"] == "duration"
    assert error["contradictory_fields"] == [
        "stated_minimum_quantity",
        "stated_maximum_quantity",
        "modifier",
    ]
    assert "evidence_id" not in error
    assert "validation_cause" not in error
    serialized = str(client.responses.calls[1]["input"])
    for prohibited in (
        "reference_date",
        "timezone",
        "resolved_anchors",
        "source_detail",
        "expected",
        "2026-08-30",
    ):
        assert prohibited not in serialized


def test_second_invalid_duration_wire_is_final_structured_failure() -> None:
    first_invalid = TemporalRelationGraphWire(
        durations=[
            DurationWire(
                stated_minimum_quantity=1,
                stated_maximum_quantity=2,
                unit=TemporalUnit.WEEK,
                modifier=DurationModifier.EXACT,
                evidence_id="request:5:21",
            )
        ]
    )
    second_invalid = TemporalRelationGraphWire(
        durations=[
            DurationWire(
                stated_minimum_quantity=1,
                stated_maximum_quantity=2,
                unit=TemporalUnit.WEEK,
                modifier=DurationModifier.APPROXIMATE,
                evidence_id="request:5:21",
            )
        ]
    )
    client = FakeClient([first_invalid, second_invalid])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        extractor.resolve_dates(duration_temporal_input())

    assert len(client.responses.calls) == 2
    details = captured.value.details
    assert details.stage == "pass_two_wire_conversion"
    assert details.collection == "durations"
    assert details.relation_index == 0
    assert details.constraint_index == 0
    assert details.selected_relation_kind == "duration"
    assert details.contradictory_fields == (
        "stated_minimum_quantity",
        "stated_maximum_quantity",
        "modifier",
    )
    assert details.evidence_id == "request:5:21"
    assert "require one stated quantity" in details.validation_cause
    assert captured.value.repair_trace["repair_ran"] is True
    assert captured.value.repair_trace["repair_succeeded"] is False


@pytest.mark.parametrize("model", ["gpt-4o-mini", "gpt-5-mini", "intent-eval-candidate"])
def test_model_candidates_are_forwarded_without_environment_state(model: str) -> None:
    client = FakeClient([CoarseIntentExtraction()])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model=model),
        client=cast(OpenAI, client),
    )

    extractor.extract(coarse_input())

    assert extractor.config.model == model
    assert client.responses.calls[0]["model"] == model


def test_model_config_rejects_blank_model() -> None:
    with pytest.raises(ValueError, match="model must not be empty"):
        OpenAIExtractorConfig(model="  ")
