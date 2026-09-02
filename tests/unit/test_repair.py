from datetime import date

import pytest

from award_agent.domain import (
    AnchorWindowConstraint,
    CalendarPeriodSemantics,
    CoarseIntentExtraction,
    ModelPassRepairTrace,
    MonthAnchor,
    RawRequest,
    RelativeCalendarPeriodConstraint,
    RequestContext,
    SymbolicContextReference,
    TemporalDirection,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalRelationGraph,
    TemporalTarget,
    TemporalUnit,
)
from award_agent.intent.evidence import TemporalResolutionValidationError
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    StructuredValidationErrorView,
    TemporalInterpretationInput,
    TemporalResolutionResult,
)
from award_agent.intent.workflow import understand_request


def _request(text: str) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
    )


def _next_month_extraction() -> CoarseIntentExtraction:
    return CoarseIntentExtraction(
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="next month",
            )
        ]
    )


def _next_month_graph() -> TemporalRelationGraph:
    return TemporalRelationGraph(
        constraints=[
            RelativeCalendarPeriodConstraint(
                kind="relative_calendar_period",
                target=TemporalTarget.DEPARTURE,
                reference=SymbolicContextReference(
                    kind="symbolic_context", key="context:request_date"
                ),
                direction=TemporalDirection.AFTER,
                unit=TemporalUnit.MONTH,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                raw_text="next month",
            )
        ]
    )


class RepairPipeline:
    def __init__(
        self,
        *,
        extraction: CoarseIntentExtraction,
        relations: TemporalRelationGraph,
        repaired_extraction: CoarseIntentExtraction | None = None,
        repaired_relations: TemporalRelationGraph | None = None,
    ) -> None:
        self.extraction = extraction
        self.relations = relations
        self.repaired_extraction = repaired_extraction
        self.repaired_relations = repaired_relations
        self.pass_one_repairs: list[CoarseExtractionRepairInput] = []
        self.pass_two_repairs: list[
            tuple[
                TemporalInterpretationInput,
                TemporalRelationGraph,
                list[StructuredValidationErrorView],
            ]
        ] = []

    def extract(self, model_input: CoarseExtractionInput) -> CoarseIntentExtraction:
        return self.extraction

    def repair_extract(self, model_input: CoarseExtractionRepairInput) -> CoarseIntentExtraction:
        self.pass_one_repairs.append(model_input)
        assert self.repaired_extraction is not None
        return self.repaired_extraction

    def resolve_dates(self, model_input: TemporalInterpretationInput) -> TemporalResolutionResult:
        return TemporalResolutionResult(
            relations=self.relations,
            repair_trace=ModelPassRepairTrace(
                first_attempt_valid=True,
                repair_ran=False,
                repair_succeeded=False,
            ),
        )

    def repair_dates(
        self,
        model_input: TemporalInterpretationInput,
        rejected_output: TemporalRelationGraph,
        validation_errors: list[StructuredValidationErrorView],
    ) -> TemporalRelationGraph:
        self.pass_two_repairs.append((model_input, rejected_output, validation_errors))
        assert self.repaired_relations is not None
        return self.repaired_relations


def test_pass_one_validation_can_be_repaired_once_without_calendar_leakage() -> None:
    invalid = CoarseIntentExtraction(
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="inferred",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="next month",
                month=9,
                year=2026,
            )
        ]
    )
    pipeline = RepairPipeline(
        extraction=invalid,
        repaired_extraction=_next_month_extraction(),
        relations=_next_month_graph(),
    )

    result = understand_request(_request("Travel next month."), pipeline, pipeline)

    assert result.repair_trace is not None
    assert result.repair_trace.pass_one.repair_succeeded is True
    assert len(pipeline.pass_one_repairs) == 1
    payload = pipeline.pass_one_repairs[0].model_dump_json()
    for prohibited in (
        "reference_date",
        "timezone",
        "2026",
        '"month":9',
        "month 9",
        "September",
    ):
        assert prohibited not in payload
    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.start == date(2026, 9, 1)


def test_pass_one_second_validation_failure_is_explicit_and_not_retried() -> None:
    invalid = CoarseIntentExtraction(
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="not in request",
            )
        ]
    )
    pipeline = RepairPipeline(
        extraction=invalid,
        repaired_extraction=invalid,
        relations=TemporalRelationGraph(),
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        understand_request(_request("Travel next month."), pipeline, pipeline)

    assert len(pipeline.pass_one_repairs) == 1
    assert captured.value.repair_trace["repair_ran"] is True
    assert captured.value.repair_trace["repair_succeeded"] is False


def test_pass_two_graph_validation_repair_reruns_complete_validation() -> None:
    invalid_graph = TemporalRelationGraph(
        constraints=[
            AnchorWindowConstraint(
                kind="anchor_window",
                target=TemporalTarget.DEPARTURE,
                anchor_id="invented",
                window="anchor",
                raw_text="May",
            )
        ]
    )
    extraction = CoarseIntentExtraction(
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="model-id",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="May",
                month=5,
            )
        ]
    )
    repaired_graph = TemporalRelationGraph(
        constraints=[
            AnchorWindowConstraint(
                kind="anchor_window",
                target=TemporalTarget.DEPARTURE,
                anchor_id="anchor:month:departure:10:13",
                window="anchor",
                raw_text="May",
            )
        ]
    )
    pipeline = RepairPipeline(
        extraction=extraction,
        relations=invalid_graph,
        repaired_relations=repaired_graph,
    )

    result = understand_request(_request("Travel in May."), pipeline, pipeline)

    assert result.repair_trace is not None
    assert result.repair_trace.pass_two.repair_succeeded is True
    assert len(pipeline.pass_two_repairs) == 1
    repair_input = pipeline.pass_two_repairs[0][0].model_dump_json()
    for prohibited in ("reference_date", "timezone", "2026-05-01", "source_detail"):
        assert prohibited not in repair_input


def test_pass_two_second_graph_failure_is_explicit_and_not_retried() -> None:
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="next month",
            )
        ]
    )
    invalid = TemporalRelationGraph(
        constraints=[
            AnchorWindowConstraint(
                kind="anchor_window",
                target=TemporalTarget.DEPARTURE,
                anchor_id="invented",
                window="anchor",
                raw_text="next month",
            )
        ]
    )
    pipeline = RepairPipeline(
        extraction=extraction,
        relations=invalid,
        repaired_relations=invalid,
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        understand_request(_request("Travel next month."), pipeline, pipeline)

    assert len(pipeline.pass_two_repairs) == 1
    assert captured.value.repair_trace["repair_succeeded"] is False


def test_valid_passes_do_not_use_repair_calls() -> None:
    pipeline = RepairPipeline(
        extraction=_next_month_extraction(),
        relations=_next_month_graph(),
    )

    result = understand_request(_request("Travel next month."), pipeline, pipeline)

    assert result.repair_trace is not None
    assert result.repair_trace.pass_one.repair_ran is False
    assert result.repair_trace.pass_two.repair_ran is False
    assert pipeline.pass_one_repairs == []
    assert pipeline.pass_two_repairs == []
