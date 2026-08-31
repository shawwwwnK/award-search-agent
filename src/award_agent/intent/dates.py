"""Deterministic temporal-expression resolution."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from award_agent.domain import (
    DateExpression,
    DateExpressionKind,
    DateFlexibility,
    DateFlexibilityTarget,
    DateWindow,
    DateWindowPrecision,
    DurationConstraint,
    Holiday,
    RequestContext,
    Weekday,
)
from award_agent.intent.holidays import (
    HolidayDateProvider,
    HolidayDateResolutionError,
)


def _next_occurrence(month: int, day: int, year: int | None, reference: date) -> date:
    if year is not None:
        return date(year, month, day)
    candidate = date(reference.year, month, day)
    if candidate < reference:
        candidate = date(reference.year + 1, month, day)
    return candidate


def _holiday_year(
    holiday: Holiday,
    year: int | None,
    reference: date,
    holiday_provider: HolidayDateProvider,
) -> int:
    if year is not None:
        return year
    candidate = holiday_provider.holiday_date(holiday, reference.year)
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


def _resolve_holiday(
    expression: DateExpression,
    context: RequestContext,
    holiday_provider: HolidayDateProvider,
) -> DateWindow:
    assert expression.holiday is not None
    year = _holiday_year(
        expression.holiday,
        expression.year,
        context.reference_date,
        holiday_provider,
    )
    holiday = holiday_provider.holiday_date(expression.holiday, year)
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


def _resolve_relative_weekend(
    expression: DateExpression,
    context: RequestContext,
    holiday_provider: HolidayDateProvider | None,
    relative_anchor: DateWindow | None,
) -> DateWindow:
    assert expression.count is not None
    if expression.holiday is not None:
        assert holiday_provider is not None
        year = _holiday_year(
            expression.holiday,
            expression.year,
            context.reference_date,
            holiday_provider,
        )
        anchor = holiday_provider.holiday_date(expression.holiday, year)
    else:
        if relative_anchor is None:
            raise ValueError("departure-relative weekend requires a departure window")
        anchor = relative_anchor.end
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


_WEEKDAY_INDEX = {
    Weekday.MONDAY: calendar.MONDAY,
    Weekday.TUESDAY: calendar.TUESDAY,
    Weekday.WEDNESDAY: calendar.WEDNESDAY,
    Weekday.THURSDAY: calendar.THURSDAY,
    Weekday.FRIDAY: calendar.FRIDAY,
    Weekday.SATURDAY: calendar.SATURDAY,
    Weekday.SUNDAY: calendar.SUNDAY,
}


class DateFlexibilityResolutionError(ValueError):
    """Raised when flexibility cannot be represented by one continuous date window."""


def _resolve_relative_weekday(
    expression: DateExpression,
    base_window: DateWindow,
) -> DateWindow:
    assert expression.weekday is not None
    target_weekday = _WEEKDAY_INDEX[expression.weekday]
    if expression.kind is DateExpressionKind.PRECEDING_WEEKDAY:
        days = (base_window.start.weekday() - target_weekday) % 7 or 7
        resolved = base_window.start - timedelta(days=days)
    else:
        days = (target_weekday - base_window.end.weekday()) % 7 or 7
        resolved = base_window.end + timedelta(days=days)
    return DateWindow(
        start=resolved,
        end=resolved,
        precision=DateWindowPrecision.EXACT,
        raw_text=expression.raw_text,
    )


def resolve_date_expression(
    expression: DateExpression | None,
    context: RequestContext,
    holiday_provider: HolidayDateProvider | None = None,
    relative_anchor: DateWindow | None = None,
) -> DateWindow | None:
    if expression is None or expression.kind is DateExpressionKind.UNRESOLVED:
        return None
    if expression.kind is DateExpressionKind.EXACT:
        return _resolve_exact(expression, context)
    if expression.kind is DateExpressionKind.RANGE:
        return _resolve_range(expression, context)
    if expression.kind is DateExpressionKind.HOLIDAY_WINDOW:
        if holiday_provider is None:
            raise HolidayDateResolutionError(
                "holiday date expressions require a HolidayDateProvider"
            )
        return _resolve_holiday(expression, context, holiday_provider)
    if expression.kind is DateExpressionKind.RELATIVE_WEEKEND:
        if expression.holiday is not None and holiday_provider is None:
            raise HolidayDateResolutionError(
                "holiday date expressions require a HolidayDateProvider"
            )
        return _resolve_relative_weekend(
            expression,
            context,
            holiday_provider,
            relative_anchor,
        )
    if expression.kind is DateExpressionKind.MONTH:
        return _resolve_month(expression, context)
    if expression.kind is DateExpressionKind.RELATIVE_MONTH:
        return _resolve_relative_month(expression, context)
    if expression.kind in {
        DateExpressionKind.PRECEDING_WEEKDAY,
        DateExpressionKind.FOLLOWING_WEEKDAY,
    }:
        raise ValueError(f"{expression.kind.value} requires a base date window")
    if expression.kind is DateExpressionKind.BOUND:
        return _resolve_bound(expression, context)
    raise TypeError(f"unsupported date expression kind: {expression.kind}")


def apply_date_flexibility(
    base_window: DateWindow | None,
    flexibility: list[DateFlexibility],
    applies_to: DateFlexibilityTarget,
    context: RequestContext,
    holiday_provider: HolidayDateProvider | None = None,
) -> DateWindow | None:
    if base_window is None:
        return None
    resolved_window = base_window
    supporting_text = [base_window.raw_text]
    for modifier in flexibility:
        if modifier.applies_to is not applies_to:
            continue
        expression = modifier.expression
        included: DateWindow | None
        is_directional_extension = expression.kind in {
            DateExpressionKind.PRECEDING_WEEKDAY,
            DateExpressionKind.FOLLOWING_WEEKDAY,
        }
        if is_directional_extension:
            included = _resolve_relative_weekday(expression, resolved_window)
        else:
            included = resolve_date_expression(expression, context, holiday_provider)
        if included is None:
            continue
        is_disjoint = (
            included.end < resolved_window.start - timedelta(days=1)
            or included.start > resolved_window.end + timedelta(days=1)
        )
        if is_disjoint and not is_directional_extension:
            raise DateFlexibilityResolutionError(
                "non-contiguous date alternatives cannot be represented as one date window"
            )
        resolved_window = DateWindow(
            start=min(resolved_window.start, included.start),
            end=max(resolved_window.end, included.end),
            precision=DateWindowPrecision.WINDOW,
            raw_text="; ".join([*supporting_text, expression.raw_text]),
        )
        supporting_text.append(expression.raw_text)
    return resolved_window


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
