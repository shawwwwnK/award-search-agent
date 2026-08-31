from datetime import date
from typing import ClassVar

from award_agent.domain import (
    DateExpression,
    DateExpressionAnchor,
    DateExpressionKind,
    DateFlexibility,
    DateFlexibilityMode,
    DateFlexibilityTarget,
    DurationConstraint,
    Holiday,
    RequestContext,
    Weekday,
)
from award_agent.intent.dates import (
    DateFlexibilityResolutionError,
    apply_date_flexibility,
    derive_return_window,
    resolve_date_expression,
)
from award_agent.intent.holidays import HolidayDateResolutionError

CONTEXT = RequestContext(
    reference_date=date(2026, 8, 30),
    timezone="America/Los_Angeles",
)


class FakeHolidayProvider:
    DATES: ClassVar[dict[tuple[Holiday, int], date]] = {
        (Holiday.LABOR_DAY, 2026): date(2026, 9, 7),
        (Holiday.CHRISTMAS, 2026): date(2026, 12, 25),
        (Holiday.THANKSGIVING, 2026): date(2026, 11, 26),
    }

    def holiday_date(self, holiday: Holiday, year: int) -> date:
        return self.DATES[(holiday, year)]


HOLIDAYS = FakeHolidayProvider()


def test_exact_date_without_year_uses_next_occurrence() -> None:
    future = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="October 5",
            month=10,
            day=5,
        ),
        CONTEXT,
        HOLIDAYS,
    )
    past = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="January 5",
            month=1,
            day=5,
        ),
        CONTEXT,
        HOLIDAYS,
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
        HOLIDAYS,
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
        HOLIDAYS,
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
        HOLIDAYS,
    )

    assert window is not None
    assert window.start == date(2026, 12, 5)
    assert window.end == date(2026, 12, 6)


def test_return_weekend_after_departure_is_anchored_to_departure_window() -> None:
    departure = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.HOLIDAY_WINDOW,
            raw_text="Labor Day weekend",
            holiday=Holiday.LABOR_DAY,
        ),
        CONTEXT,
        HOLIDAYS,
    )
    result = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.RELATIVE_WEEKEND,
            raw_text="the weekend afterwards",
            count=1,
            relative_to=DateExpressionAnchor.DEPARTURE,
        ),
        CONTEXT,
        relative_anchor=departure,
    )

    assert result is not None
    assert (result.start, result.end) == (date(2026, 9, 12), date(2026, 9, 13))


def test_approximate_duration_derives_bounded_return_window() -> None:
    departure = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.HOLIDAY_WINDOW,
            raw_text="Labor Day weekend",
            holiday=Holiday.LABOR_DAY,
        ),
        CONTEXT,
        HOLIDAYS,
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


def test_holiday_expression_requires_an_explicit_provider() -> None:
    expression = DateExpression(
        kind=DateExpressionKind.HOLIDAY_WINDOW,
        raw_text="Labor Day weekend",
        holiday=Holiday.LABOR_DAY,
    )

    try:
        resolve_date_expression(expression, CONTEXT)
    except HolidayDateResolutionError as exc:
        assert str(exc) == "holiday date expressions require a HolidayDateProvider"
    else:
        raise AssertionError("expected missing holiday provider to fail explicitly")


def test_preceding_weekday_flexibility_extends_a_resolved_window() -> None:
    base = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.HOLIDAY_WINDOW,
            raw_text="Labor Day weekend",
            holiday=Holiday.LABOR_DAY,
        ),
        CONTEXT,
        HOLIDAYS,
    )
    flexibility = [
        DateFlexibility(
            applies_to=DateFlexibilityTarget.DEPARTURE,
            mode=DateFlexibilityMode.INCLUDE,
            expression=DateExpression(
                kind=DateExpressionKind.PRECEDING_WEEKDAY,
                raw_text="the Thursday as well",
                weekday=Weekday.THURSDAY,
            ),
        )
    ]

    result = apply_date_flexibility(
        base,
        flexibility,
        DateFlexibilityTarget.DEPARTURE,
        CONTEXT,
        HOLIDAYS,
    )

    assert result is not None
    assert (result.start, result.end) == (date(2026, 9, 3), date(2026, 9, 7))
    assert result.raw_text == "Labor Day weekend; the Thursday as well"


def test_following_weekday_flexibility_can_extend_an_exact_date() -> None:
    base = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="September 4",
            month=9,
            day=4,
        ),
        CONTEXT,
    )
    flexibility = [
        DateFlexibility(
            applies_to=DateFlexibilityTarget.DEPARTURE,
            mode=DateFlexibilityMode.INCLUDE,
            expression=DateExpression(
                kind=DateExpressionKind.FOLLOWING_WEEKDAY,
                raw_text="through Monday",
                weekday=Weekday.MONDAY,
            ),
        )
    ]

    result = apply_date_flexibility(
        base,
        flexibility,
        DateFlexibilityTarget.DEPARTURE,
        CONTEXT,
    )

    assert result is not None
    assert (result.start, result.end) == (date(2026, 9, 4), date(2026, 9, 7))


def test_non_contiguous_exact_alternatives_are_not_silently_merged() -> None:
    base = resolve_date_expression(
        DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="October 5",
            month=10,
            day=5,
        ),
        CONTEXT,
    )
    flexibility = [
        DateFlexibility(
            applies_to=DateFlexibilityTarget.DEPARTURE,
            mode=DateFlexibilityMode.INCLUDE,
            expression=DateExpression(
                kind=DateExpressionKind.EXACT,
                raw_text="October 8 as well",
                month=10,
                day=8,
            ),
        )
    ]

    try:
        apply_date_flexibility(
            base,
            flexibility,
            DateFlexibilityTarget.DEPARTURE,
            CONTEXT,
        )
    except DateFlexibilityResolutionError as exc:
        assert "non-contiguous" in str(exc)
    else:
        raise AssertionError("expected disjoint alternatives to fail explicitly")
