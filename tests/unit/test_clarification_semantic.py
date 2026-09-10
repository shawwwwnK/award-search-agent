from datetime import date

import pytest

from award_agent.clarification.semantic import (
    WEEKDAY_ENCODING,
    SemanticTarget,
    SemanticTemporalCompileError,
    TemporalAstKind,
    TemporalSemanticAst,
    compile_temporal_ast,
)
from award_agent.domain import MessageSpan, RequestContext


def _span(text: str) -> MessageSpan:
    return MessageSpan(message_id="a1", start=0, end=len(text), text=text)


def _context() -> RequestContext:
    return RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles")


def test_date_range_compiles_without_model_calculated_dates() -> None:
    result = compile_temporal_ast(
        amendment_id="range",
        target=SemanticTarget.DEPARTURE_WINDOW,
        ast=TemporalSemanticAst(
            kind=TemporalAstKind.DATE_RANGE, month=10, day=12, end_month=10, end_day=18
        ),
        span=_span("October 12 through October 18"),
        context=_context(),
    )
    assert result.contribution.date_window is not None
    assert (result.contribution.date_window.start, result.contribution.date_window.end) == (
        date(2026, 10, 12),
        date(2026, 10, 18),
    )


def test_date_range_rolls_an_unqualified_end_into_the_next_year() -> None:
    result = compile_temporal_ast(
        amendment_id="range",
        target=SemanticTarget.DEPARTURE_WINDOW,
        ast=TemporalSemanticAst(
            kind=TemporalAstKind.DATE_RANGE, month=12, day=30, end_month=1, end_day=2
        ),
        span=_span("December 30 through January 2"),
        context=_context(),
    )
    assert result.contribution.date_window is not None
    assert result.contribution.date_window.end == date(2027, 1, 2)


def test_relative_return_requires_and_uses_a_prior_same_answer_departure_fact() -> None:
    departure = compile_temporal_ast(
        amendment_id="departure",
        target=SemanticTarget.DEPARTURE_WINDOW,
        ast=TemporalSemanticAst(kind=TemporalAstKind.CALENDAR_DATE, month=10, day=12),
        span=_span("October 12"),
        context=_context(),
    )
    returned = compile_temporal_ast(
        amendment_id="return",
        target=SemanticTarget.RETURN_WINDOW,
        ast=TemporalSemanticAst(
            kind=TemporalAstKind.RELATIVE_TO_PRIOR_FACT,
            anchor_fact_id="departure",
            relation="after",
            quantity=12,
            unit="day",
        ),
        span=_span("12 days afterwards"),
        context=_context(),
        prior_compiled_facts={"departure": departure},
    )
    assert returned.contribution.date_window is not None
    assert returned.contribution.date_window.start == date(2026, 10, 24)


def test_relative_return_cannot_reference_missing_or_non_departure_prior_facts() -> None:
    ast = TemporalSemanticAst(
        kind=TemporalAstKind.RELATIVE_TO_PRIOR_FACT,
        anchor_fact_id="departure",
        relation="after",
        quantity=12,
        unit="day",
    )
    with pytest.raises(SemanticTemporalCompileError, match="earlier same-answer fact"):
        compile_temporal_ast(
            amendment_id="return",
            target=SemanticTarget.RETURN_WINDOW,
            ast=ast,
            span=_span("12 days afterwards"),
            context=_context(),
        )


def test_fuzzy_month_and_approximate_duration_have_visible_provenance() -> None:
    month = compile_temporal_ast(
        amendment_id="departure",
        target=SemanticTarget.DEPARTURE_WINDOW,
        ast=TemporalSemanticAst(kind=TemporalAstKind.MONTH_PORTION, month=10, portion="mid"),
        span=_span("mid October"),
        context=_context(),
    )
    duration = compile_temporal_ast(
        amendment_id="duration",
        target=SemanticTarget.DURATION,
        ast=TemporalSemanticAst(
            kind=TemporalAstKind.DURATION, quantity=12, unit="day", approximate=True
        ),
        span=_span("about 12 days"),
        context=_context(),
    )
    assert month.contribution.interpretation_provenance is not None
    assert "2026-10-11 through 2026-10-20" in (
        month.contribution.interpretation_provenance.assumption_disclosure.message  # type: ignore[union-attr]
    )
    assert duration.contribution.interpretation_provenance is not None
    assert "11 to 13 days" in (
        duration.contribution.interpretation_provenance.assumption_disclosure.message  # type: ignore[union-attr]
    )


def test_weekday_encoding_is_explicit_and_stable() -> None:
    assert WEEKDAY_ENCODING == (
        "Use ISO/Python weekday indexes: Monday=0, Tuesday=1, Wednesday=2, "
        "Thursday=3, Friday=4, Saturday=5, Sunday=6."
    )
