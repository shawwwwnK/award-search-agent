from datetime import date

from award_agent.domain import (
    DateExpression,
    DateExpressionKind,
    DurationConstraint,
    Holiday,
    RequestContext,
)
from award_agent.intent.dates import derive_return_window, resolve_date_expression

CONTEXT = RequestContext(
    reference_date=date(2026, 8, 30),
    timezone="America/Los_Angeles",
)


def test_exact_date_without_year_uses_next_occurrence() -> None:
    future = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="October 5",
            month=10,
            day=5,
        ),
        CONTEXT,
    )
    past = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="January 5",
            month=1,
            day=5,
        ),
        CONTEXT,
    )

    assert future is not None and future.start == date(2026, 10, 5)
    assert past is not None and past.start == date(2027, 1, 5)


def test_labor_day_weekend_is_resolved_by_deterministic_policy() -> None:
    window = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.HOLIDAY_WINDOW,
            raw_text="Labor Day weekend",
            holiday=Holiday.LABOR_DAY,
        ),
        CONTEXT,
    )

    assert window is not None
    assert window.start == date(2026, 9, 4)
    assert window.end == date(2026, 9, 7)


def test_christmas_window_is_resolved_without_airport_or_search_expansion() -> None:
    window = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.HOLIDAY_WINDOW,
            raw_text="over Christmas",
            holiday=Holiday.CHRISTMAS,
        ),
        CONTEXT,
    )

    assert window is not None
    assert (window.start, window.end) == (date(2026, 12, 24), date(2026, 12, 26))


def test_relative_weekend_after_thanksgiving_is_arithmetic_not_model_reasoning() -> None:
    window = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.RELATIVE_WEEKEND,
            raw_text="two weekends after Thanksgiving",
            holiday=Holiday.THANKSGIVING,
            count=2,
            year=2026,
        ),
        CONTEXT,
    )

    assert window is not None
    assert window.start == date(2026, 12, 5)
    assert window.end == date(2026, 12, 6)


def test_approximate_duration_derives_bounded_return_window() -> None:
    departure = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.HOLIDAY_WINDOW,
            raw_text="Labor Day weekend",
            holiday=Holiday.LABOR_DAY,
        ),
        CONTEXT,
    )
    result = derive_return_window(
        departure,
        None,
        DurationConstraint(raw_text="about 10 days", days=10, approximate=True),
    )

    assert result is not None
    assert result.start == date(2026, 9, 13)
    assert result.end == date(2026, 9, 18)


def test_month_and_relative_month_resolution() -> None:
    first_week = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.MONTH,
            raw_text="first week of June",
            month=6,
            portion="first_week",
        ),
        CONTEXT,
    )
    next_month = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.RELATIVE_MONTH,
            raw_text="next month",
            offset_months=1,
        ),
        CONTEXT,
    )

    assert first_week is not None
    assert (first_week.start, first_week.end) == (date(2027, 6, 1), date(2027, 6, 7))
    assert next_month is not None
    assert (next_month.start, next_month.end) == (date(2026, 9, 1), date(2026, 9, 30))
