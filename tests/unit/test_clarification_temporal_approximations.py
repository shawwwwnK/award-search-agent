"""ADR 0012 accepting temporal approximation contract tests."""

from datetime import date

import pytest

from award_agent.clarification.temporal_approximations import (
    ClarificationTemporalApproximationBinding,
    ClarificationTemporalApproximationError,
    ClarificationTemporalApproximationSelection,
    compile_temporal_approximation_selection,
    global_temporal_approximation_projection,
)
from award_agent.domain import (
    BlockingRequirement,
    BlockingRequirementKind,
    EffectiveField,
    MessageSpan,
    RequestContext,
)

_CONTEXT = RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles")
_REQUIREMENTS = (
    BlockingRequirement(requirement_id="departure", kind=BlockingRequirementKind.DEPARTURE, field=EffectiveField.DEPARTURE),
    BlockingRequirement(requirement_id="return_or_duration", kind=BlockingRequirementKind.RETURN_OR_DURATION, field=EffectiveField.RETURN_OR_DURATION),
)


def _span(text: str, phrase: str) -> MessageSpan:
    start = text.index(phrase)
    return MessageSpan(message_id="m1", start=start, end=start + len(phrase), text=phrase)


@pytest.mark.parametrize(
    ("phrase", "handle", "start", "end"),
    [
        ("early next month", "a1", date(2026, 10, 1), date(2026, 10, 10)),
        ("mid October", "a2", date(2026, 10, 11), date(2026, 10, 20)),
        ("late October", "a3", date(2026, 10, 21), date(2026, 10, 31)),
    ],
)
def test_month_portions_compile_to_documented_bounded_windows(
    phrase: str, handle: str, start: date, end: date
) -> None:
    text = f"1. {phrase}\n2. a week"
    selection = ClarificationTemporalApproximationSelection(
        selected=(
            ClarificationTemporalApproximationBinding(
                approximation_handle=handle,
                span=_span(text, phrase),
                month_reference="next_month" if "next month" in phrase else "named_month",
                month_name=None if "next month" in phrase else "october",
            ),
            ClarificationTemporalApproximationBinding(approximation_handle="a4", span=_span(text, "a week")),
        ),
        complete=True,
    )
    facts = compile_temporal_approximation_selection(
        global_temporal_approximation_projection(), selection,
        context=_CONTEXT, text=text, requirements=_REQUIREMENTS,
    )
    assert facts[0].window is not None
    assert (facts[0].window.start, facts[0].window.end) == (start, end)
    assert facts[0].provenance.assumption_disclosure is not None
    assert facts[1].duration is not None
    assert (facts[1].duration.minimum_days, facts[1].duration.maximum_days) == (7, 7)


def test_about_a_week_is_a_visible_six_to_eight_day_assumption() -> None:
    text = "depart early next month and return in about a week"
    selection = ClarificationTemporalApproximationSelection(
        selected=(
            ClarificationTemporalApproximationBinding(
                approximation_handle="a1", span=_span(text, "early next month"), month_reference="next_month"
            ),
            ClarificationTemporalApproximationBinding(approximation_handle="a5", span=_span(text, "about a week")),
        ),
        complete=True,
    )
    facts = compile_temporal_approximation_selection(
        global_temporal_approximation_projection(), selection,
        context=_CONTEXT, text=text, requirements=_REQUIREMENTS,
    )
    assert facts[1].duration is not None
    assert (facts[1].duration.minimum_days, facts[1].duration.maximum_days) == (6, 8)


def test_open_surface_wording_uses_grounded_closed_month_slots() -> None:
    text = "I want to leave during the beginning of October for a week"
    selection = ClarificationTemporalApproximationSelection(
        selected=(
            ClarificationTemporalApproximationBinding(
                approximation_handle="a1",
                span=_span(text, "the beginning of October"),
                month_reference="named_month",
                month_name="october",
            ),
            ClarificationTemporalApproximationBinding(
                approximation_handle="a4", span=_span(text, "a week")
            ),
        ),
        complete=True,
    )
    facts = compile_temporal_approximation_selection(
        global_temporal_approximation_projection(), selection,
        context=_CONTEXT, text=text, requirements=_REQUIREMENTS,
    )
    assert facts[0].window is not None
    assert (facts[0].window.start, facts[0].window.end) == (date(2026, 10, 1), date(2026, 10, 10))
    assert facts[1].duration is not None
    assert facts[1].duration.minimum_days == 7


def test_month_portion_can_resolve_return_and_rolls_passed_named_portion_forward() -> None:
    text = "return during the beginning of October"
    selection = ClarificationTemporalApproximationSelection(
        selected=(
            ClarificationTemporalApproximationBinding(
                approximation_handle="a1",
                span=_span(text, "the beginning of October"),
                month_reference="named_month",
                month_name="october",
            ),
        ),
        complete=True,
    )
    facts = compile_temporal_approximation_selection(
        global_temporal_approximation_projection(), selection,
        context=RequestContext(reference_date=date(2026, 10, 15), timezone="America/Los_Angeles"),
        text=text,
        requirements=(
            BlockingRequirement(
                requirement_id="return_or_duration",
                kind=BlockingRequirementKind.RETURN_OR_DURATION,
                field=EffectiveField.RETURN_OR_DURATION,
            ),
        ),
    )
    assert facts[0].candidate.target.value == "return_or_duration"
    assert facts[0].window is not None
    assert (facts[0].window.start, facts[0].window.end) == (date(2027, 10, 1), date(2027, 10, 10))


def test_candidate_and_disclosure_ids_are_message_scoped() -> None:
    text = "early next month"
    selections = []
    for message_id in ("answer:1", "answer:2"):
        span = _span(text, text).model_copy(update={"message_id": message_id})
        selections.append(
            compile_temporal_approximation_selection(
                global_temporal_approximation_projection(),
                ClarificationTemporalApproximationSelection(
                    selected=(ClarificationTemporalApproximationBinding(
                        approximation_handle="a1", span=span, month_reference="next_month"
                    ),),
                    complete=True,
                ),
                context=_CONTEXT,
                text=text,
                requirements=(_REQUIREMENTS[0],),
            )[0]
    )
    assert selections[0].candidate.candidate_id != selections[1].candidate.candidate_id
    first_disclosure = selections[0].provenance.assumption_disclosure
    second_disclosure = selections[1].provenance.assumption_disclosure
    assert first_disclosure is not None
    assert second_disclosure is not None
    assert (
        first_disclosure.disclosure_id != second_disclosure.disclosure_id
    )


def test_discrete_alternatives_remain_blocked() -> None:
    text = "1. early October or late October"
    selection = ClarificationTemporalApproximationSelection(
        selected=(ClarificationTemporalApproximationBinding(
            approximation_handle="a1", span=_span(text, "early October"), month_reference="named_month", month_name="october"
        ),),
        complete=True,
    )
    with pytest.raises(ClarificationTemporalApproximationError, match="discrete temporal alternative"):
        compile_temporal_approximation_selection(
            global_temporal_approximation_projection(), selection,
            context=_CONTEXT, text=text, requirements=_REQUIREMENTS,
        )
