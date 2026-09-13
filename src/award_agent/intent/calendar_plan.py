"""Deterministic evaluator for initial-request generic calendar proposals."""

from __future__ import annotations

from datetime import date, timedelta

from award_agent.domain import DateWindow, DateWindowPrecision, RequestContext
from award_agent.intent.holidays import HolidayDateProvider
from award_agent.intent.semantic import (
    CalendarAnchorKind,
    CalendarComposition,
    CalendarOperationKind,
    CalendarPeriodSlice,
    SemanticTemporalFact,
    SemanticTemporalTarget,
)


class IntentCalendarPlanError(ValueError):
    """A proposal cannot safely be grounded or calculated."""


class IntentCalendarOperationalError(RuntimeError):
    """An external calendar/holiday provider was unavailable or malformed."""


def evaluate_departure_calendar_plan(
    facts: tuple[SemanticTemporalFact, ...],
    context: RequestContext,
    holiday_provider: HolidayDateProvider | None,
) -> tuple[DateWindow | None, tuple[SemanticTemporalFact, ...]]:
    """Evaluate departure operations without looking at their source wording.

    Return/duration facts are deliberately retained for scope policy rather
    than evaluated.  Multiple compatible departure windows are intersected;
    disjoint windows are left for the workflow to expose as a conflict.
    """

    by_id = {item.fact_id: item for item in facts}
    if len(by_id) != len(facts):  # defensive even though proposal validates it
        raise IntentCalendarPlanError("duplicate temporal fact ID")
    resolved: dict[str, DateWindow] = {}
    unresolved: list[SemanticTemporalFact] = []
    remaining = [item for item in facts if item.target is SemanticTemporalTarget.DEPARTURE]
    while remaining:
        progressed = False
        for fact in tuple(remaining):
            if fact.operation is CalendarOperationKind.UNRESOLVED:
                unresolved.append(fact)
                remaining.remove(fact)
                progressed = True
                continue
            if (
                fact.anchor_kind is CalendarAnchorKind.PRIOR_FACT
                and fact.anchor_fact_id not in resolved
            ):
                if fact.anchor_fact_id not in by_id:
                    raise IntentCalendarPlanError(
                        f"proposal {fact.fact_id} references unknown prior fact {fact.anchor_fact_id}"
                    )
                continue
            resolved[fact.fact_id] = _evaluate(fact, context, holiday_provider, resolved)
            remaining.remove(fact)
            progressed = True
        if not progressed:
            raise IntentCalendarPlanError("calendar proposal dependency cycle")
    windows = list(resolved.values())
    if not windows:
        return None, tuple(unresolved)
    union_windows = [
        resolved[item.fact_id]
        for item in facts
        if item.fact_id in resolved and item.composition is CalendarComposition.UNION
    ]
    intersect_windows = [item for item in windows if item not in union_windows]
    start = (
        max(item.start for item in intersect_windows)
        if intersect_windows
        else min(item.start for item in union_windows)
    )
    end = (
        min(item.end for item in intersect_windows)
        if intersect_windows
        else max(item.end for item in union_windows)
    )
    if end < start:
        # The workflow detects this as a user-level temporal conflict; it is
        # not a malformed proposal and must not use the repair budget.
        return None, tuple(unresolved)
    precision = DateWindowPrecision.EXACT if start == end else DateWindowPrecision.WINDOW
    if union_windows:
        start = min(start, *(item.start for item in union_windows))
        end = max(end, *(item.end for item in union_windows))
    return DateWindow(
        start=start,
        end=end,
        precision=precision,
        raw_text="; ".join(item.quote for item in facts if item.fact_id in resolved),
    ), tuple(unresolved)


def departure_windows(
    facts: tuple[SemanticTemporalFact, ...],
    context: RequestContext,
    holiday_provider: HolidayDateProvider | None,
) -> tuple[DateWindow, ...]:
    """Materialize individual windows for deterministic conflict inspection."""
    resolved: dict[str, DateWindow] = {}
    by_id = {item.fact_id: item for item in facts}
    remaining = [
        item
        for item in facts
        if item.target is SemanticTemporalTarget.DEPARTURE
        and item.operation is not CalendarOperationKind.UNRESOLVED
    ]
    while remaining:
        progressed = False
        for fact in tuple(remaining):
            if (
                fact.anchor_kind is CalendarAnchorKind.PRIOR_FACT
                and fact.anchor_fact_id not in resolved
            ):
                if fact.anchor_fact_id not in by_id:
                    raise IntentCalendarPlanError(
                        f"proposal {fact.fact_id} references unknown prior fact {fact.anchor_fact_id}"
                    )
                continue
            resolved[fact.fact_id] = _evaluate(fact, context, holiday_provider, resolved)
            remaining.remove(fact)
            progressed = True
        if not progressed:
            raise IntentCalendarPlanError("calendar proposal dependency cycle")
    return tuple(resolved.values())


def _evaluate(
    fact: SemanticTemporalFact,
    context: RequestContext,
    provider: HolidayDateProvider | None,
    resolved: dict[str, DateWindow],
) -> DateWindow:
    if fact.operation is CalendarOperationKind.LITERAL_INTERVAL:
        assert fact.start_month is not None and fact.start_day is not None
        start = _next_occurrence(
            fact.start_year, fact.start_month, fact.start_day, context.reference_date
        )
        if fact.end_month is None:
            end = start
        else:
            assert fact.end_day is not None
            end_year = fact.end_year if fact.end_year is not None else start.year
            end = _make_date(end_year, fact.end_month, fact.end_day)
            if end < start and fact.end_year is None:
                end = _make_date(end.year + 1, fact.end_month, fact.end_day)
        return _window(start, end, fact.quote)
    if fact.operation is CalendarOperationKind.CALENDAR_PERIOD:
        assert fact.period_slice is not None
        if fact.period_offset_months is not None:
            start, end = _relative_period_bounds(
                fact.period_offset_months, fact.period_slice, context.reference_date
            )
        else:
            assert fact.period_month is not None
            start, end = _period_bounds(
                fact.period_year, fact.period_month, fact.period_slice, context.reference_date
            )
        return _window(start, end, fact.quote)
    anchor = _anchor_date(fact, context, provider, resolved)
    if fact.operation is CalendarOperationKind.RECURRING_INTERVAL:
        assert fact.weekday is not None
        base = anchor + timedelta(days=1 if fact.strictly_after else 0)
        start = base + timedelta(
            days=(fact.weekday - base.weekday()) % 7 + 7 * (fact.cycles_after_anchor or 0)
        )
        return _window(start, start + timedelta(days=(fact.span_days or 1) - 1), fact.quote)
    if fact.operation is CalendarOperationKind.OFFSET_INTERVAL:
        assert fact.start_offset_days is not None
        start = anchor + timedelta(days=fact.start_offset_days)
        end = anchor + timedelta(
            days=fact.end_offset_days
            if fact.end_offset_days is not None
            else fact.start_offset_days
        )
        return _window(start, end, fact.quote)
    raise IntentCalendarPlanError("unresolved operation cannot be evaluated")


def _anchor_date(
    fact: SemanticTemporalFact,
    context: RequestContext,
    provider: HolidayDateProvider | None,
    resolved: dict[str, DateWindow],
) -> date:
    if fact.anchor_kind is CalendarAnchorKind.REQUEST_DATE:
        return context.reference_date
    if fact.anchor_kind is CalendarAnchorKind.PRIOR_FACT:
        assert fact.anchor_fact_id is not None
        prior = resolved.get(fact.anchor_fact_id)
        if prior is None:
            raise IntentCalendarPlanError(f"unknown prior fact {fact.anchor_fact_id}")
        return prior.start if fact.anchor_edge == "start" else prior.end
    if fact.anchor_kind is CalendarAnchorKind.HOLIDAY:
        if provider is None:
            raise IntentCalendarPlanError("holiday calculation requires a holiday provider")
        assert fact.anchor_holiday is not None
        year = fact.anchor_year or context.reference_date.year
        try:
            anchor = provider.holiday_date(fact.anchor_holiday, year)
        except Exception as exc:  # provider failures are operational, never semantic repair work
            raise IntentCalendarOperationalError("holiday provider unavailable") from exc
        # An unstated year follows the project's next-occurrence convention.
        if fact.anchor_year is None and anchor < context.reference_date:
            try:
                anchor = provider.holiday_date(fact.anchor_holiday, year + 1)
            except (
                Exception
            ) as exc:  # provider failures are operational, never semantic repair work
                raise IntentCalendarOperationalError("holiday provider unavailable") from exc
        return anchor
    raise IntentCalendarPlanError("calendar operation has no executable anchor")


def _next_occurrence(year: int | None, month: int, day: int, reference: date) -> date:
    if year is not None:
        return _make_date(year, month, day)
    candidate = _make_date(reference.year, month, day)
    return candidate if candidate >= reference else _make_date(reference.year + 1, month, day)


def _period_start(year: int | None, month: int, reference: date) -> date:
    candidate = _make_date(year or reference.year, month, 1)
    if year is None and candidate < _make_date(reference.year, reference.month, 1):
        candidate = _make_date(reference.year + 1, month, 1)
    return candidate


def _period_bounds(
    year: int | None, month: int, slice: CalendarPeriodSlice, reference: date
) -> tuple[date, date]:
    start = _period_start(year, month, reference)
    next_month = _make_date(
        start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1
    )
    month_end = next_month - timedelta(days=1)
    if slice is CalendarPeriodSlice.WHOLE:
        return start, month_end
    if slice in {CalendarPeriodSlice.FIRST_WEEK, CalendarPeriodSlice.EARLY}:
        return start, min(
            month_end, start + timedelta(days=6 if slice is CalendarPeriodSlice.FIRST_WEEK else 9)
        )
    if slice is CalendarPeriodSlice.MID:
        return start + timedelta(days=10), min(month_end, start + timedelta(days=19))
    return start + timedelta(days=20), month_end


def _relative_period_bounds(
    offset: int, slice: CalendarPeriodSlice, reference: date
) -> tuple[date, date]:
    month_index = reference.year * 12 + reference.month - 1 + offset
    year, month_zero = divmod(month_index, 12)
    return _period_bounds(year, month_zero + 1, slice, reference)


def _make_date(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise IntentCalendarPlanError(
            f"invalid calendar date {year:04d}-{month:02d}-{day:02d}"
        ) from exc


def _window(start: date, end: date, raw_text: str) -> DateWindow:
    if end < start:
        raise IntentCalendarPlanError("calendar interval end precedes start")
    return DateWindow(
        start=start,
        end=end,
        precision=DateWindowPrecision.EXACT if start == end else DateWindowPrecision.WINDOW,
        raw_text=raw_text,
    )
