"""Request-understanding workflow orchestration."""

from datetime import date

from award_agent.domain import (
    DateExpressionKind,
    IntentExtraction,
    ParsedRequest,
    RawRequest,
    RequestUnderstandingResult,
    SearchMode,
    UnknownField,
    UnknownReason,
)
from award_agent.intent.clarification import decide_clarification
from award_agent.intent.conflicts import detect_conflicts
from award_agent.intent.dates import derive_return_window, resolve_date_expression
from award_agent.intent.extractor import IntentExtractor


def _collect_unknowns(
    extraction: IntentExtraction,
    departure_resolved: bool,
    return_resolved: bool,
) -> list[UnknownField]:
    unknowns: list[UnknownField] = []

    def missing(field: str, detail: str) -> None:
        unknowns.append(
            UnknownField(field=field, reason=UnknownReason.MISSING, detail=detail)
        )

    if extraction.travelers is None:
        missing("travelers", "The number of travelers was not stated.")
    if not extraction.origins:
        missing("origin", "No departure location was stated.")
    if not extraction.destinations:
        missing("destination", "No destination was stated.")
    if extraction.departure is None:
        missing("departure", "No departure timing was stated.")
    elif not departure_resolved:
        raw_text = extraction.departure.raw_text
        detail = (
            extraction.departure.reason or "The departure expression could not be resolved."
            if extraction.departure.kind is DateExpressionKind.UNRESOLVED
            else "The departure expression could not be resolved."
        )
        unknowns.append(
            UnknownField(
                field="departure",
                reason=UnknownReason.UNRESOLVED,
                detail=detail,
                raw_text=raw_text,
            )
        )
    if extraction.return_date is None and extraction.duration is None:
        missing("return_or_duration", "Neither a return date nor trip duration was stated.")
    elif extraction.return_date is not None and not return_resolved:
        raw_text = extraction.return_date.raw_text
        detail = (
            extraction.return_date.reason or "The return expression could not be resolved."
            if extraction.return_date.kind is DateExpressionKind.UNRESOLVED
            else "The return expression could not be resolved."
        )
        unknowns.append(
            UnknownField(
                field="return_or_duration",
                reason=UnknownReason.UNRESOLVED,
                detail=detail,
                raw_text=raw_text,
            )
        )
    if not extraction.cabins:
        missing("cabin", "No cabin preference was stated.")
    if not extraction.search_modes:
        missing("search_modes", "Neither award nor cash search was explicitly requested.")
    if SearchMode.AWARD in extraction.search_modes and not extraction.points_balances:
        missing("points_balances", "No loyalty-program point balances were stated.")

    unknowns.extend(
        UnknownField(
            field=ambiguity.field,
            reason=UnknownReason.AMBIGUOUS,
            detail=ambiguity.detail,
            raw_text=ambiguity.raw_text,
        )
        for ambiguity in extraction.ambiguities
    )
    return unknowns


def understand_request(
    request: RawRequest, extractor: IntentExtractor
) -> RequestUnderstandingResult:
    extraction = extractor.extract(request)
    departure_window = resolve_date_expression(extraction.departure, request.context)
    return_context = (
        request.context.model_copy(
            update={
                "reference_date": date(
                    departure_window.start.year,
                    departure_window.start.month,
                    1,
                )
            }
        )
        if departure_window is not None
        else request.context
    )
    explicit_return_window = resolve_date_expression(extraction.return_date, return_context)
    return_window = derive_return_window(
        departure_window,
        explicit_return_window,
        extraction.duration,
    )
    conflicts = detect_conflicts(
        departure_window,
        explicit_return_window,
        extraction.duration,
    )
    unknowns = _collect_unknowns(
        extraction,
        departure_resolved=departure_window is not None,
        return_resolved=return_window is not None,
    )
    parsed = ParsedRequest(
        raw_text=request.text,
        context=request.context,
        travelers=extraction.travelers,
        origins=extraction.origins,
        destinations=extraction.destinations,
        departure_expression=extraction.departure,
        return_expression=extraction.return_date,
        departure_window=departure_window,
        return_window=return_window,
        duration=extraction.duration,
        cabins=extraction.cabins,
        search_modes=extraction.search_modes,
        points_balances=extraction.points_balances,
        cash_budget_usd=extraction.cash_budget_usd,
        date_flexibility_days=extraction.date_flexibility_days,
        repositioning_allowed=extraction.repositioning_allowed,
        hard_constraints=extraction.hard_constraints,
        unknowns=unknowns,
        conflicts=conflicts,
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=decide_clarification(parsed),
    )
