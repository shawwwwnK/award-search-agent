"""Two-pass request-understanding workflow orchestration."""

from award_agent.domain import (
    CoarseIntentExtraction,
    DateResolutionProposal,
    ParsedRequest,
    RawRequest,
    RequestUnderstandingResult,
    ResolvedTemporalAnchor,
    UnknownField,
    UnknownReason,
)
from award_agent.intent.clarification import decide_clarification
from award_agent.intent.conflicts import detect_conflicts
from award_agent.intent.extractor import IntentExtractor, TemporalResolver
from award_agent.intent.holidays import HolidayDateProvider
from award_agent.intent.temporal import (
    enrich_temporal_anchors,
    proposal_window_to_date_window,
    sanitize_temporal_extraction,
    validate_date_resolution_proposal,
)


def _collect_unknowns(
    extraction: CoarseIntentExtraction,
    proposal: DateResolutionProposal,
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

    unresolved_departure = next(
        (
            item
            for item in proposal.unresolved
            if item.field in {"departure", "dates"}
        ),
        None,
    )
    unresolved_return = next(
        (
            item
            for item in proposal.unresolved
            if item.field in {"return_or_duration", "dates"}
        ),
        None,
    )
    if proposal.departure is None:
        if unresolved_departure is None:
            missing("departure", "No bounded departure timing was stated.")
        else:
            unknowns.append(
                UnknownField(
                    field="departure",
                    reason=UnknownReason.UNRESOLVED,
                    detail=unresolved_departure.reason,
                    raw_text=unresolved_departure.raw_text,
                )
            )
    if proposal.return_date is None:
        if unresolved_return is None:
            missing(
                "return_or_duration",
                "Neither a bounded return date nor a resolvable trip duration was stated.",
            )
        else:
            unknowns.append(
                UnknownField(
                    field="return_or_duration",
                    reason=UnknownReason.UNRESOLVED,
                    detail=unresolved_return.reason,
                    raw_text=unresolved_return.raw_text,
                )
            )

    if not extraction.cabins:
        missing("cabin", "No cabin preference was stated.")
    if not extraction.search_modes:
        missing("search_modes", "Neither award nor cash search was explicitly requested.")

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
    request: RawRequest,
    extractor: IntentExtractor,
    temporal_resolver: TemporalResolver,
    holiday_provider: HolidayDateProvider | None = None,
) -> RequestUnderstandingResult:
    extraction = sanitize_temporal_extraction(request, extractor.extract(request))
    resolved_anchors: list[ResolvedTemporalAnchor] = enrich_temporal_anchors(
        request,
        extraction,
        holiday_provider,
    )
    proposal = validate_date_resolution_proposal(
        request,
        extraction,
        temporal_resolver.resolve_dates(request, extraction, resolved_anchors),
        resolved_anchors,
    )

    departure_window = proposal_window_to_date_window(proposal, "departure")
    return_window = proposal_window_to_date_window(proposal, "return")
    conflicts = detect_conflicts(departure_window, return_window, None)
    parsed = ParsedRequest(
        raw_text=request.text,
        context=request.context,
        travelers=extraction.travelers,
        origins=extraction.origins,
        destinations=extraction.destinations,
        departure_expression=None,
        return_expression=None,
        departure_window=departure_window,
        return_window=return_window,
        duration=None,
        cabins=extraction.cabins,
        search_modes=extraction.search_modes,
        date_flexibility=[],
        repositioning_allowed=extraction.repositioning_allowed,
        hard_constraints=extraction.hard_constraints,
        unknowns=_collect_unknowns(extraction, proposal),
        conflicts=conflicts,
        temporal_extraction=extraction,
        resolved_date_anchors=resolved_anchors,
        date_resolution=proposal,
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=decide_clarification(parsed),
    )
