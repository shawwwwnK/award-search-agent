"""Deterministic temporal-expression resolution."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from award_agent.domain import (
    DateExpression,
    DateExpressionKind,
    DateWindow,
    DateWindowPrecision,
    DurationConstraint,
    Holiday,
    RequestContext,
)


def _next_occurrence(month: int, day: int, year: int | None, reference: date) -> date:
    if year is not None:
        return date(year, month, day)
    candidate = date(reference.year, month, day)
    if candidate < reference:
        candidate = date(reference.year + 1, month, day)
    return candidate


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (occurrence - 1))


def _holiday_date(holiday: Holiday, year: int) -> date:
    if holiday is Holiday.CHRISTMAS:
        return date(year, 12, 25)
    if holiday is Holiday.LABOR_DAY:
        return _nth_weekday(year, 9, calendar.MONDAY, 1)
    if holiday is Holiday.THANKSGIVING:
        return _nth_weekday(year, 11, calendar.THURSDAY, 4)
    raise ValueError(f"unsupported holiday: {holiday}")


def _holiday_year(holiday: Holiday, year: int | None, reference: date) -> int:
    if year is not None:
        return year
    candidate = _holiday_date(holiday, reference.year)
    return reference.year + 1 if candidate < reference else reference.year


def _resolve_exact(expression: DateExpression, context: RequestContext) -> DateWindow:
    assert expression.month is not None and expression.day is not None
    resolved = _next_occurrence(
        expression.month,
        expression.day,
        expression.year,
        context.reference_date,
    )
    return DateWindow(
        start=resolved,
        end=resolved,
        precision=DateWindowPrecision.EXACT,
        raw_text=expression.raw_text,
    )


def _resolve_range(expression: DateExpression, context: RequestContext) -> DateWindow:
    assert expression.start_month is not None and expression.start_day is not None
    assert expression.end_month is not None and expression.end_day is not None
    start = _next_occurrence(
        expression.start_month,
        expression.start_day,
        expression.start_year,
        context.reference_date,
    )
    end_year = expression.end_year if expression.end_year is not None else start.year
    end = date(end_year, expression.end_month, expression.end_day)
    if expression.end_year is None and end < start:
        end = date(start.year + 1, expression.end_month, expression.end_day)
    return DateWindow(
        start=start,
        end=end,
        precision=DateWindowPrecision.WINDOW,
        raw_text=expression.raw_text,
    )


def _resolve_holiday(expression: DateExpression, context: RequestContext) -> DateWindow:
    assert expression.holiday is not None
    year = _holiday_year(expression.holiday, expression.year, context.reference_date)
    holiday = _holiday_date(expression.holiday, year)
    if expression.holiday is Holiday.LABOR_DAY:
        start, end = holiday - timedelta(days=3), holiday
    elif expression.holiday is Holiday.CHRISTMAS:
        start, end = holiday - timedelta(days=1), holiday + timedelta(days=1)
    else:
        start, end = holiday, holiday + timedelta(days=3)
    return DateWindow(
        start=start,
        end=end,
        precision=DateWindowPrecision.WINDOW,
        raw_text=expression.raw_text,
    )


def _resolve_relative_weekend(expression: DateExpression, context: RequestContext) -> DateWindow:
    assert expression.holiday is not None and expression.count is not None
    year = _holiday_year(expression.holiday, expression.year, context.reference_date)
    anchor = _holiday_date(expression.holiday, year)
    days_to_saturday = (calendar.SATURDAY - anchor.weekday()) % 7 or 7
    first_weekend = anchor + timedelta(days=days_to_saturday)
    start = first_weekend + timedelta(weeks=expression.count - 1)
    return DateWindow(
        start=start,
        end=start + timedelta(days=1),
        precision=DateWindowPrecision.WINDOW,
        raw_text=expression.raw_text,
    )


def _resolve_month(expression: DateExpression, context: RequestContext) -> DateWindow:
    assert expression.month is not None
    year = expression.year or context.reference_date.year
    month_end = date(year, expression.month, calendar.monthrange(year, expression.month)[1])
    if expression.year is None and month_end < context.reference_date:
        year += 1
    start = date(year, expression.month, 1)
    end_day = 7 if expression.portion == "first_week" else calendar.monthrange(year, expression.month)[1]
    return DateWindow(
        start=start,
        end=date(year, expression.month, end_day),
        precision=(
            DateWindowPrecision.WINDOW
            if expression.portion == "first_week"
            else DateWindowPrecision.MONTH
        ),
        raw_text=expression.raw_text,
    )


def _resolve_relative_month(expression: DateExpression, context: RequestContext) -> DateWindow:
    assert expression.offset_months is not None
    month_index = context.reference_date.month - 1 + expression.offset_months
    year = context.reference_date.year + month_index // 12
    month = month_index % 12 + 1
    return DateWindow(
        start=date(year, month, 1),
        end=date(year, month, calendar.monthrange(year, month)[1]),
        precision=DateWindowPrecision.MONTH,
        raw_text=expression.raw_text,
    )


def _resolve_bound(expression: DateExpression, context: RequestContext) -> DateWindow:
    assert expression.month is not None and expression.day is not None
    assert expression.boundary is not None
    boundary = _next_occurrence(
        expression.month,
        expression.day,
        expression.year,
        context.reference_date,
    )
    if expression.boundary == "before":
        return DateWindow(
            start=context.reference_date,
            end=boundary - timedelta(days=1),
            precision=DateWindowPrecision.BOUND,
            raw_text=expression.raw_text,
        )
    start = boundary + timedelta(days=1)
    return DateWindow(
        start=start,
        end=date(start.year, 12, 31),
        precision=DateWindowPrecision.BOUND,
        raw_text=expression.raw_text,
    )


def resolve_date_expression(
    expression: DateExpression | None, context: RequestContext
) -> DateWindow | None:
    if expression is None or expression.kind is DateExpressionKind.UNRESOLVED:
        return None
    if expression.kind is DateExpressionKind.EXACT:
        return _resolve_exact(expression, context)
    if expression.kind is DateExpressionKind.RANGE:
        return _resolve_range(expression, context)
    if expression.kind is DateExpressionKind.HOLIDAY_WINDOW:
        return _resolve_holiday(expression, context)
    if expression.kind is DateExpressionKind.RELATIVE_WEEKEND:
        return _resolve_relative_weekend(expression, context)
    if expression.kind is DateExpressionKind.MONTH:
        return _resolve_month(expression, context)
    if expression.kind is DateExpressionKind.RELATIVE_MONTH:
        return _resolve_relative_month(expression, context)
    if expression.kind is DateExpressionKind.BOUND:
        return _resolve_bound(expression, context)
    raise TypeError(f"unsupported date expression kind: {expression.kind}")


def derive_return_window(
    departure: DateWindow | None,
    return_window: DateWindow | None,
    duration: DurationConstraint | None,
) -> DateWindow | None:
    if return_window is not None or departure is None or duration is None:
        return return_window
    tolerance = 1 if duration.approximate else 0
    return DateWindow(
        start=departure.start + timedelta(days=duration.days - tolerance),
        end=departure.end + timedelta(days=duration.days + tolerance),
        precision=DateWindowPrecision.DERIVED,
        raw_text=duration.raw_text,
    )
