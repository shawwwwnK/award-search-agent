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
    TemporalTarget,
    TemporalUnit,
    UnboundedBoundaryConstraint,
    UnresolvedRelationConstraint,
    Weekday,
)
from award_agent.intent.evidence import TemporalResolutionValidationError
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    ExplicitAnchorCatalogEntry,
    RejectedCoarseExtractionView,
    StructuredValidationErrorView,
    SymbolicReferenceCatalogEntry,
    TemporalEvidenceCatalogEntry,
    TemporalInterpretationInput,
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
            )
        ],
        allowed_symbolic_references=[
            SymbolicReferenceCatalogEntry(key="context:request_date"),
            SymbolicReferenceCatalogEntry(key="anchor_ref:month_1:start"),
            SymbolicReferenceCatalogEntry(key="anchor_ref:month_1:end"),
            SymbolicReferenceCatalogEntry(key="request_field:departure:end"),
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
        allowed_symbolic_references=[SymbolicReferenceCatalogEntry(key="context:request_date")],
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
            SymbolicReferenceCatalogEntry(key="request_field:departure:end")
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
    assert call["text_format"] is CoarseIntentExtraction
    assert call["store"] is False
    payload = json.loads(str(call["input"]))
    assert payload == {"request_text": "Travel in May."}
    assert "reference_date" not in str(call["input"])
    assert "timezone" not in str(call["input"])


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
    assert "only when that year is explicitly present" in instructions
    assert "pass two has no year field" in instructions.casefold()


def test_openai_resolver_receives_only_date_free_temporal_catalogs() -> None:
    wire_relations = TemporalRelationGraphWire(
        anchor_windows=[
            AnchorWindowWire(
                target=TemporalTarget.DEPARTURE,
                anchor_id="month_1",
                window="anchor",
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
    assert payload["explicit_anchor_catalog"] == [
        {"anchor_id": "month_1", "kind": "month", "applies_to": "departure"}
    ]
    serialized = str(call["input"])
    for prohibited in (
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
    assert call["text_format"] is TemporalRelationGraphWire
    assert call["store"] is False


def test_openai_resolver_instructions_define_semantic_relation_boundary() -> None:
    client = FakeClient(
        [
            TemporalRelationGraphWire(
                unresolved=[
                    UnresolvedWire(
                        target="unspecified",
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
    assert "semantic constraints only" in instructions
    assert "Never propose, copy, or calculate final calendar dates" in instructions
    assert "relative_weekend" in instructions
    assert "reference_key is request_field:departure:end" in instructions
    assert "anchor_id exactly equals the matching supplied" in instructions
    assert "Do not invent a human-readable anchor ID" in instructions
    assert "anchor_id labor_day" not in instructions
    assert "unbounded_boundary" in instructions
    assert "Do not emit 2026 dates" in instructions


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
                anchor_id="month_1",
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
                .model_copy(update={"claim_labels": list(TemporalEvidenceClaim)})
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


def test_context_request_date_is_visible_but_private_value_is_absent() -> None:
    payload = temporal_input().model_dump(mode="json")

    assert {entry["key"] for entry in payload["allowed_symbolic_references"]} >= {
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
        allowed_symbolic_references=[SymbolicReferenceCatalogEntry(key="context:request_date")],
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


def test_wire_rejects_relation_incompatible_anchor_kind() -> None:
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

    with pytest.raises(ValueError, match="holiday_weekend requires a holiday anchor"):
        wire.to_domain(temporal_input())


def test_wire_rejects_relation_incompatible_anchor_target() -> None:
    wire = TemporalRelationGraphWire(
        anchor_windows=[
            AnchorWindowWire(
                target=TemporalTarget.RETURN,
                anchor_id="month_1",
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
    assert error["evidence_id"] == "request:5:21"
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
