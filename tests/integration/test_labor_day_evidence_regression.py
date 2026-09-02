from datetime import date
from pathlib import Path
from typing import cast

import pytest
import yaml

from award_agent.cli.intent_eval import _evaluation_summary, _hard_checks_pass, _score_result
from award_agent.domain import (
    AnchorReference,
    AnchorWindowConstraint,
    ClarificationAction,
    CoarseIntentExtraction,
    DurationModifier,
    Holiday,
    HolidayAnchor,
    LocationKind,
    LocationRef,
    ModelPassRepairTrace,
    RawRequest,
    RelativeWeekdayConstraint,
    RequestContext,
    RequestFieldReference,
    SemanticDurationConstraint,
    TemporalDirection,
    TemporalEdge,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalRelationGraph,
    TemporalTarget,
    TemporalUnit,
    Weekday,
)
from award_agent.intent.evidence import TemporalEvidenceValidationError
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    StructuredValidationErrorView,
    TemporalInterpretationInput,
    TemporalResolutionResult,
)
from award_agent.intent.workflow import understand_request

REQUEST_TEXT = (
    "My boyfriend and I want to go to Thailand from SF leaving on Labor Day weekend "
    "for about 10 days. We are flexible to leave on the Thursday as well."
)


class FixedPipeline:
    def __init__(self, extraction: CoarseIntentExtraction) -> None:
        self.extraction = extraction

    def extract(self, model_input: CoarseExtractionInput) -> CoarseIntentExtraction:
        return self.extraction

    def repair_extract(self, model_input: CoarseExtractionRepairInput) -> CoarseIntentExtraction:
        return self.extraction

    def resolve_dates(
        self,
        model_input: TemporalInterpretationInput,
    ) -> TemporalResolutionResult:
        labor_day_id = model_input.explicit_anchor_catalog[0].anchor_id
        return TemporalResolutionResult(
            relations=TemporalRelationGraph(
                constraints=[
                    AnchorWindowConstraint(
                        kind="anchor_window",
                        target=TemporalTarget.DEPARTURE,
                        anchor_id=labor_day_id,
                        window="holiday_weekend",
                        raw_text="leaving on Labor Day weekend",
                    ),
                    RelativeWeekdayConstraint(
                        kind="relative_weekday",
                        target=TemporalTarget.DEPARTURE,
                        reference=AnchorReference(
                            kind="anchor", anchor_id=labor_day_id, edge=TemporalEdge.START
                        ),
                        direction=TemporalDirection.BEFORE,
                        ordinal=1,
                        weekday=Weekday.THURSDAY,
                        raw_text="on the Thursday as well",
                    ),
                    SemanticDurationConstraint(
                        kind="duration",
                        reference=RequestFieldReference(
                            kind="request_field",
                            field=TemporalTarget.DEPARTURE,
                            edge=TemporalEdge.END,
                        ),
                        stated_minimum_quantity=10,
                        stated_maximum_quantity=10,
                        unit=TemporalUnit.DAY,
                        modifier=DurationModifier.APPROXIMATE,
                        raw_text="about 10 days",
                    ),
                ]
            ),
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
        return rejected_output


class LaborDayProvider:
    def holiday_date(self, holiday: Holiday, year: int) -> date:
        assert holiday is Holiday.LABOR_DAY
        assert year == 2026
        return date(2026, 9, 7)


def request() -> RawRequest:
    return RawRequest(
        text=REQUEST_TEXT,
        context=RequestContext(
            reference_date=date(2026, 8, 29),
            timezone="America/Los_Angeles",
        ),
    )


def base_extraction(*phrases: TemporalPhrase) -> CoarseIntentExtraction:
    return CoarseIntentExtraction(
        travelers=2,
        origins=[LocationRef(kind=LocationKind.CITY, value="San Francisco", raw_text="SF")],
        destinations=[
            LocationRef(kind=LocationKind.COUNTRY, value="Thailand", raw_text="Thailand")
        ],
        date_anchors=[
            HolidayAnchor(
                kind="holiday",
                anchor_id="labor_day",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="Labor Day",
                holiday=Holiday.LABOR_DAY,
            )
        ],
        temporal_phrases=list(phrases),
    )


def temporal_phrase(
    quote: str,
    *claims: TemporalEvidenceClaim,
) -> TemporalPhrase:
    return TemporalPhrase(
        applies_to=TemporalPhraseTarget.UNSPECIFIED,
        raw_text=quote,
        claim_ids=list(claims),
    )


def recorded_invalid_extraction() -> CoarseIntentExtraction:
    return base_extraction(
        temporal_phrase(
            "leaving on Labor Day weekend",
            TemporalEvidenceClaim.DEPARTURE_ANCHOR,
            TemporalEvidenceClaim.DEPARTURE_PERIOD,
        ),
        temporal_phrase(
            "about 10 days",
            TemporalEvidenceClaim.APPROXIMATE_DURATION,
        ),
        temporal_phrase(
            "leaving on the Thursday as well",
            TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY,
        ),
    )


def recorded_trial_two_extraction() -> CoarseIntentExtraction:
    return base_extraction(
        temporal_phrase(
            "leaving on Labor Day weekend",
            TemporalEvidenceClaim.DEPARTURE_ANCHOR,
            TemporalEvidenceClaim.DEPARTURE_PERIOD,
        ),
        temporal_phrase(
            "about 10 days",
            TemporalEvidenceClaim.APPROXIMATE_DURATION,
        ),
        temporal_phrase(
            "on the Thursday as well",
            TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY,
        ),
    )


def labor_day_expected() -> dict[str, object]:
    payload = yaml.safe_load(Path("evals/intent/cases.yaml").read_text())
    scenario = next(
        item for item in payload["scenarios"] if item["id"] == "labor_day_thursday_flexibility"
    )
    return cast(dict[str, object], scenario["expected"])


@pytest.mark.parametrize("trial", [1, 3])
def test_recorded_synthetic_quote_trials_fail_strict_grounding(trial: int) -> None:
    pipeline = FixedPipeline(recorded_invalid_extraction())

    with pytest.raises(TemporalEvidenceValidationError) as captured:
        understand_request(request(), pipeline, pipeline, LaborDayProvider())

    assert trial in {1, 3}
    assert captured.value.code.value == "ungrounded_quote"
    assert captured.value.quote == "leaving on the Thursday as well"
    assert captured.value.claim_id == "alternate_departure_day"


def test_recorded_trial_two_passes_full_case_with_boundary_diagnostic_only() -> None:
    pipeline = FixedPipeline(recorded_trial_two_extraction())

    result = understand_request(request(), pipeline, pipeline, LaborDayProvider())
    checks = _score_result(labor_day_expected(), result)
    evaluation = _evaluation_summary(checks)

    assert _hard_checks_pass(checks) is True
    assert evaluation == {
        "schema_valid": True,
        "grounding_valid": True,
        "semantic_fields_valid": True,
        "evidence_support_valid": True,
        "deterministic_outputs_valid": True,
        "preferred_boundary_exact_match": False,
        "missing_expected_claims": [],
        "unsupported_claims": [],
        "overbroad_spans": [],
        "insufficient_spans": [],
    }
    assert result.parsed_request.travelers == 2
    assert result.parsed_request.origins[0].raw_text == "SF"
    assert result.parsed_request.destinations[0].value == "Thailand"
    assert result.parsed_request.departure_window is not None
    assert (
        result.parsed_request.departure_window.start,
        result.parsed_request.departure_window.end,
    ) == (
        date(2026, 9, 3),
        date(2026, 9, 7),
    )
    assert result.parsed_request.return_window is not None
    assert (result.parsed_request.return_window.start, result.parsed_request.return_window.end) == (
        date(2026, 9, 12),
        date(2026, 9, 18),
    )
    assert result.clarification.action is ClarificationAction.NONE

    checks_by_name = {check["name"]: check for check in checks}
    assert checks_by_name["grounding_valid"]["passed"] is True
    assert checks_by_name["evidence_support_valid"]["passed"] is True
    assert checks_by_name["preferred_boundary_exact_match"] == {
        "name": "preferred_boundary_exact_match",
        "passed": False,
        "expected": True,
        "actual": False,
        "blocking": False,
    }

    evidence = result.parsed_request.temporal_evidence
    weekend = next(item for item in evidence if item.span.text == "leaving on Labor Day weekend")
    assert weekend.claim_ids == [
        TemporalEvidenceClaim.DEPARTURE_ANCHOR,
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
    ]
    assert weekend.span.text == REQUEST_TEXT[weekend.span.start : weekend.span.end]
