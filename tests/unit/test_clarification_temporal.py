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
    DateWindowPrecision,
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


def _embedded_amendment(
    answer_text: str,
    temporal_text: str,
    target: Literal[
        AmendmentTarget.DEPARTURE,
        AmendmentTarget.RETURN_OR_DURATION,
        AmendmentTarget.CONFLICTING_DATES,
    ],
) -> TemporalAmendment:
    start = answer_text.index(temporal_text)
    return _amendment(temporal_text, target).model_copy(
        update={
            "span": MessageSpan(
                message_id="answer-1",
                start=start,
                end=start + len(temporal_text),
                text=temporal_text,
            )
        }
    )


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


def test_hedged_named_month_is_an_accepted_whole_month_departure_range() -> None:
    text = "Maybe in October?"
    result = normalize_temporal_amendment(
        _amendment(text, AmendmentTarget.DEPARTURE),
        answer_text=text,
        requirements=(_requirement(BlockingRequirementKind.DEPARTURE),),
        context=_context(),
    )

    contribution = result.contributions[0]
    assert contribution.kind is TemporalContributionKind.DEPARTURE_WINDOW
    assert contribution.date_window is not None
    assert contribution.date_window.start == date(2026, 10, 1)
    assert contribution.date_window.end == date(2026, 10, 31)
    assert contribution.date_window.precision is DateWindowPrecision.MONTH
    assert contribution.date_window.raw_text == "October"


def test_named_month_uses_initial_path_next_occurrence_policy() -> None:
    result = normalize_temporal_amendment(
        _amendment("January", AmendmentTarget.DEPARTURE),
        answer_text="January",
        requirements=(_requirement(BlockingRequirementKind.DEPARTURE),),
        context=_context(date(2026, 9, 8)),
    )

    window = result.contributions[0].date_window
    assert window is not None
    assert (window.start, window.end) == (date(2027, 1, 1), date(2027, 1, 31))


def test_reported_numbered_relative_weekend_and_weekday_answers_have_deterministic_ownership() -> (
    None
):
    requirements = (
        _requirement(BlockingRequirementKind.DEPARTURE),
        _requirement(BlockingRequirementKind.RETURN_OR_DURATION),
    )

    departure = normalize_temporal_amendment(
        _embedded_amendment(
            "1. This weekend\n2. On Monday", "1. This weekend", AmendmentTarget.DEPARTURE
        ),
        answer_text="1. This weekend\n2. On Monday",
        requirements=requirements,
        context=_context(date(2026, 9, 9)),
    ).contributions[0]
    assert departure.kind is TemporalContributionKind.DEPARTURE_WINDOW
    assert departure.date_window is not None
    assert (departure.date_window.start, departure.date_window.end) == (
        date(2026, 9, 12),
        date(2026, 9, 13),
    )
    assert departure.date_window.precision is DateWindowPrecision.WINDOW

    returning = normalize_temporal_amendment(
        _embedded_amendment(
            "1. This weekend\n2. On Monday", "2. On Monday", AmendmentTarget.RETURN_OR_DURATION
        ),
        answer_text="1. This weekend\n2. On Monday",
        requirements=requirements,
        context=_context(date(2026, 9, 9)),
    ).contributions[0]
    assert returning.kind is TemporalContributionKind.RETURN_WINDOW
    assert returning.date_window is not None
    assert returning.date_window.start == returning.date_window.end == date(2026, 9, 14)


def test_reported_explicit_relative_weekday_answers_resolve_each_endpoint() -> None:
    requirements = (
        _requirement(BlockingRequirementKind.DEPARTURE),
        _requirement(BlockingRequirementKind.RETURN_OR_DURATION),
    )
    text = "Leave this friday and come back on Monday"
    departure_text, return_text = "Leave this friday", "come back on Monday"

    departure = normalize_temporal_amendment(
        _embedded_amendment(text, departure_text, AmendmentTarget.DEPARTURE),
        answer_text=text,
        requirements=requirements,
        context=_context(date(2026, 9, 9)),
    ).contributions[0]
    returning = normalize_temporal_amendment(
        _embedded_amendment(text, return_text, AmendmentTarget.RETURN_OR_DURATION),
        answer_text=text,
        requirements=requirements,
        context=_context(date(2026, 9, 9)),
    ).contributions[0]

    assert departure.date_window is not None
    assert departure.date_window.start == departure.date_window.end == date(2026, 9, 11)
    assert returning.date_window is not None
    assert returning.date_window.start == returning.date_window.end == date(2026, 9, 14)


def test_two_concrete_dates_joined_by_and_follow_the_pending_date_question_order() -> None:
    requirements = (
        _requirement(BlockingRequirementKind.DEPARTURE),
        _requirement(BlockingRequirementKind.RETURN_OR_DURATION),
    )
    text = "10/25 and 11/1"

    departure = normalize_temporal_amendment(
        _embedded_amendment(text, "10/25", AmendmentTarget.DEPARTURE),
        answer_text=text,
        requirements=requirements,
        context=_context(),
    ).contributions[0]
    returning = normalize_temporal_amendment(
        _embedded_amendment(text, "11/1", AmendmentTarget.RETURN_OR_DURATION),
        answer_text=text,
        requirements=requirements,
        context=_context(),
    ).contributions[0]

    assert departure.date_window is not None
    assert departure.date_window.start == date(2026, 10, 25)
    assert returning.date_window is not None
    assert returning.date_window.start == date(2026, 11, 1)


def test_narrow_relative_fact_spans_repair_only_their_local_endpoint_cues() -> None:
    requirements = (
        _requirement(BlockingRequirementKind.DEPARTURE),
        _requirement(BlockingRequirementKind.RETURN_OR_DURATION),
    )
    text = "Leave this Friday and come back on Monday"

    departure = normalize_temporal_amendment(
        _embedded_amendment(text, "this Friday", AmendmentTarget.DEPARTURE),
        answer_text=text,
        requirements=requirements,
        context=_context(date(2026, 9, 9)),
    ).contributions[0]
    returning = normalize_temporal_amendment(
        _embedded_amendment(text, "on Monday", AmendmentTarget.RETURN_OR_DURATION),
        answer_text=text,
        requirements=requirements,
        context=_context(date(2026, 9, 9)),
    ).contributions[0]

    assert departure.source.span.text == "this Friday"
    assert departure.date_window is not None
    assert departure.date_window.start == date(2026, 9, 11)
    assert returning.source.span.text == "on Monday"
    assert returning.date_window is not None
    assert returning.date_window.start == date(2026, 9, 14)


def test_narrow_cue_repair_rejects_disjunction_distant_cue_and_swapped_target() -> None:
    requirements = (
        _requirement(BlockingRequirementKind.DEPARTURE),
        _requirement(BlockingRequirementKind.RETURN_OR_DURATION),
    )
    context = _context(date(2026, 9, 9))

    alternative = "Leave this Friday or come back on Monday"
    with pytest.raises(AmbiguousClarificationTemporalAnswer, match="alternative or disjunction"):
        normalize_temporal_amendment(
            _embedded_amendment(alternative, "this Friday", AmendmentTarget.DEPARTURE),
            answer_text=alternative,
            requirements=requirements,
            context=context,
        )

    uncoordinated = "Leave this Friday, come back on Monday"
    with pytest.raises(AmbiguousClarificationTemporalAnswer, match="one explicit coordinator"):
        normalize_temporal_amendment(
            _embedded_amendment(uncoordinated, "this Friday", AmendmentTarget.DEPARTURE),
            answer_text=uncoordinated,
            requirements=requirements,
            context=context,
        )

    distant_cue = "Leave this Friday. on Monday"
    with pytest.raises(AmbiguousClarificationTemporalAnswer, match="bare date"):
        normalize_temporal_amendment(
            _embedded_amendment(distant_cue, "on Monday", AmendmentTarget.RETURN_OR_DURATION),
            answer_text=distant_cue,
            requirements=requirements,
            context=context,
        )

    text = "Leave this Friday and come back on Monday"
    with pytest.raises(ClarificationTemporalNormalizationError, match="does not match"):
        normalize_temporal_amendment(
            _embedded_amendment(text, "on Monday", AmendmentTarget.DEPARTURE),
            answer_text=text,
            requirements=requirements,
            context=context,
        )


def test_narrow_numbered_relative_fact_keeps_ordered_prompt_ownership() -> None:
    requirements = (
        _requirement(BlockingRequirementKind.DEPARTURE),
        _requirement(BlockingRequirementKind.RETURN_OR_DURATION),
    )
    text = "1. This weekend\n2. On Monday"
    result = normalize_temporal_amendment(
        _embedded_amendment(text, "This weekend", AmendmentTarget.DEPARTURE),
        answer_text=text,
        requirements=requirements,
        context=_context(date(2026, 9, 9)),
    )

    contribution = result.contributions[0]
    assert contribution.kind is TemporalContributionKind.DEPARTURE_WINDOW
    assert contribution.source.span.text == "This weekend"


def test_relative_temporal_ownership_rejects_bare_or_invalid_numbered_items() -> None:
    both = (
        _requirement(BlockingRequirementKind.DEPARTURE),
        _requirement(BlockingRequirementKind.RETURN_OR_DURATION),
    )
    with pytest.raises(AmbiguousClarificationTemporalAnswer, match="bare date"):
        normalize_temporal_amendment(
            _amendment("This weekend", AmendmentTarget.DEPARTURE),
            answer_text="This weekend",
            requirements=both,
            context=_context(),
        )
    with pytest.raises(AmbiguousClarificationTemporalAnswer, match="no supplied requirement"):
        normalize_temporal_amendment(
            _amendment("3. This weekend", AmendmentTarget.DEPARTURE),
            answer_text="3. This weekend",
            requirements=both,
            context=_context(),
        )
    with pytest.raises(AmbiguousClarificationTemporalAnswer, match="bare date"):
        normalize_temporal_amendment(
            _amendment("1) This weekend", AmendmentTarget.DEPARTURE),
            answer_text="1) This weekend",
            requirements=both,
            context=_context(),
        )
    with pytest.raises(UnsupportedClarificationTemporalAnswer, match="does not own"):
        normalize_temporal_amendment(
            _amendment("1. This weekend", AmendmentTarget.DEPARTURE),
            answer_text="1. This weekend",
            requirements=(_requirement(BlockingRequirementKind.TRAVELERS),),
            context=_context(),
        )


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

    with pytest.raises(AmbiguousClarificationTemporalAnswer, match="bare date"):
        normalize_temporal_amendment(
            _amendment("Maybe in October", AmendmentTarget.DEPARTURE),
            answer_text="Maybe in October",
            requirements=both,
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
