"""Offline deterministic tests for answer-only temporal normalization."""

from datetime import date
from typing import Literal

import pytest

from award_agent.clarification.interpreter import ClarificationInterpretationError
from award_agent.clarification.temporal import (
    AmbiguousClarificationTemporalAnswer,
    ClarificationTemporalNormalizationError,
    UnsupportedClarificationTemporalAnswer,
    normalize_temporal_amendment,
)
from award_agent.domain import (
    AmendmentTarget,
    BlockingRequirement,
    BlockingRequirementKind,
    EffectiveField,
    MessageSpan,
    RequestContext,
    TemporalAmendment,
    TemporalContributionKind,
)


def _requirement(kind: BlockingRequirementKind) -> BlockingRequirement:
    field_by_kind = {
        BlockingRequirementKind.DEPARTURE: EffectiveField.DEPARTURE,
        BlockingRequirementKind.RETURN_OR_DURATION: EffectiveField.RETURN_OR_DURATION,
        BlockingRequirementKind.TRAVELERS: EffectiveField.TRAVELERS,
    }
    return BlockingRequirement(
        requirement_id=f"required:{kind.value}",
        kind=kind,
        field=field_by_kind.get(kind),
        conflict_code="date_conflict" if kind is BlockingRequirementKind.CONFLICT else None,
    )


def _amendment(
    text: str,
    target: Literal[
        AmendmentTarget.DEPARTURE,
        AmendmentTarget.RETURN_OR_DURATION,
        AmendmentTarget.CONFLICTING_DATES,
    ],
) -> TemporalAmendment:
    return TemporalAmendment(
        amendment_id="temporal-1",
        target=target,
        requirement_ids=(f"required:{target.value}",),
        span=MessageSpan(message_id="answer-1", start=0, end=len(text), text=text),
        temporal_text=text,
    )


def _context(reference_date: date = date(2026, 9, 8)) -> RequestContext:
    return RequestContext(reference_date=reference_date, timezone="America/Los_Angeles")


def test_bare_day_duration_is_accepted_only_for_active_return_or_duration() -> None:
    requirement = _requirement(BlockingRequirementKind.RETURN_OR_DURATION)
    result = normalize_temporal_amendment(
        _amendment("10 days", AmendmentTarget.RETURN_OR_DURATION),
        answer_text="10 days",
        requirements=(requirement,),
        context=_context(),
    )

    contribution = result.contributions[0]
    assert contribution.kind is TemporalContributionKind.DURATION
    assert contribution.interpreted_duration is not None
    assert contribution.interpreted_duration.minimum_days == 10
    assert contribution.source.span.message_id == "answer-1"

    with pytest.raises(UnsupportedClarificationTemporalAnswer, match="only while return/duration"):
        normalize_temporal_amendment(
            _amendment("10 days", AmendmentTarget.RETURN_OR_DURATION),
            answer_text="10 days",
            requirements=(_requirement(BlockingRequirementKind.DEPARTURE),),
            context=_context(),
        )


def test_explicit_duration_correction_is_accepted_when_return_duration_is_resolved() -> None:
    text = "Actually make the trip 10 days"
    amendment = _amendment(text, AmendmentTarget.RETURN_OR_DURATION).model_copy(
        update={"is_correction": True, "requirement_ids": ()}
    )

    result = normalize_temporal_amendment(
        amendment,
        answer_text=text,
        requirements=(_requirement(BlockingRequirementKind.TRAVELERS),),
        context=_context(),
    )

    duration = result.contributions[0].interpreted_duration
    assert duration is not None
    assert (duration.minimum_days, duration.maximum_days) == (10, 10)


def test_numeric_date_uses_original_context_and_active_endpoint_ownership() -> None:
    result = normalize_temporal_amendment(
        _amendment("10/6", AmendmentTarget.DEPARTURE),
        answer_text="10/6",
        requirements=(_requirement(BlockingRequirementKind.DEPARTURE),),
        context=_context(),
    )

    contribution = result.contributions[0]
    assert contribution.kind is TemporalContributionKind.DEPARTURE_WINDOW
    assert contribution.date_window is not None
    assert contribution.date_window.start == date(2026, 10, 6)
    assert contribution.source.span.text == "10/6"

    next_year = normalize_temporal_amendment(
        _amendment("10/6", AmendmentTarget.DEPARTURE),
        answer_text="10/6",
        requirements=(_requirement(BlockingRequirementKind.DEPARTURE),),
        context=_context(date(2026, 10, 7)),
    )
    assert next_year.contributions[0].date_window is not None
    assert next_year.contributions[0].date_window.start == date(2027, 10, 6)


def test_explicit_endpoint_cue_permits_date_correction_when_both_endpoints_are_active() -> None:
    text = "Actually make departure October 6"
    amendment = _amendment(text, AmendmentTarget.DEPARTURE).model_copy(
        update={"is_correction": True, "requirement_ids": ()}
    )
    result = normalize_temporal_amendment(
        amendment,
        answer_text=text,
        requirements=(
            _requirement(BlockingRequirementKind.DEPARTURE),
            _requirement(BlockingRequirementKind.RETURN_OR_DURATION),
        ),
        context=_context(),
    )

    assert result.contributions[0].kind is TemporalContributionKind.DEPARTURE_WINDOW
    assert result.contributions[0].date_window is not None
    assert result.contributions[0].date_window.start == date(2026, 10, 6)


def test_ambiguous_bare_multi_endpoint_date_is_reasked_and_target_mismatch_is_rejected() -> None:
    both = (
        _requirement(BlockingRequirementKind.DEPARTURE),
        _requirement(BlockingRequirementKind.RETURN_OR_DURATION),
    )
    with pytest.raises(AmbiguousClarificationTemporalAnswer, match="bare date"):
        normalize_temporal_amendment(
            _amendment("October 6", AmendmentTarget.DEPARTURE),
            answer_text="October 6",
            requirements=both,
            context=_context(),
        )

    with pytest.raises(ClarificationTemporalNormalizationError, match="does not match"):
        normalize_temporal_amendment(
            _amendment("Return 2026-10-06", AmendmentTarget.DEPARTURE),
            answer_text="Return 2026-10-06",
            requirements=(_requirement(BlockingRequirementKind.RETURN_OR_DURATION),),
            context=_context(),
        )


def test_normalizer_rechecks_answer_message_grounding() -> None:
    amendment = _amendment("10/6", AmendmentTarget.DEPARTURE).model_copy(
        update={"span": MessageSpan(message_id="answer-1", start=0, end=4, text="10/6")}
    )

    with pytest.raises(ClarificationInterpretationError, match="does not equal"):
        normalize_temporal_amendment(
            amendment,
            answer_text="X10/6",
            requirements=(_requirement(BlockingRequirementKind.DEPARTURE),),
            context=_context(),
        )
