"""Selector-only request-understanding workflow orchestration."""

from award_agent.domain import (
    CoarseIntentExtraction,
    DateResolutionProposal,
    GroundedTemporalEvidence,
    ParsedRequest,
    RawRequest,
    RequestUnderstandingResult,
    UnknownField,
    UnknownReason,
)
from award_agent.intent.clarification import decide_clarification
from award_agent.intent.conflicts import detect_conflicts
from award_agent.intent.evidence import (
    ground_temporal_evidence,
    ground_temporal_relation_evidence,
)
from award_agent.intent.extractor import NonTemporalIntentExtractor, TemporalCandidateSelector
from award_agent.intent.holidays import HolidayDateProvider
from award_agent.intent.locations import preserve_explicit_airport_codes
from award_agent.intent.model_views import (
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
)
from award_agent.intent.temporal_candidates import (
    TemporalCandidateCatalog,
    build_temporal_candidates,
)
from award_agent.intent.temporal_compiler import compile_temporal_candidates
from award_agent.intent.temporal_lexing import scan_temporal_request
from award_agent.intent.temporal_selector import (
    DEFAULT_TEMPORAL_SELECTOR_POLICY,
    build_temporal_selector_input,
    plan_temporal_selection,
    restore_selector_output,
)


def _collect_unknowns(
    extraction: CoarseIntentExtraction,
    proposal: DateResolutionProposal,
) -> list[UnknownField]:
    """Turn compiled temporal state and non-temporal extraction into explicit unknowns."""

    unknowns: list[UnknownField] = []

    def missing(field: str, detail: str) -> None:
        unknowns.append(UnknownField(field=field, reason=UnknownReason.MISSING, detail=detail))

    if extraction.travelers is None:
        missing("travelers", "The number of travelers was not stated.")
    if not extraction.origins:
        missing("origin", "No departure location was stated.")
    if not extraction.destinations:
        missing("destination", "No destination was stated.")

    unresolved_departure = next(
        (item for item in proposal.unresolved if item.field in {"departure", "dates"}),
        None,
    )
    unresolved_return = next(
        (item for item in proposal.unresolved if item.field in {"return_or_duration", "dates"}),
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
    if proposal.return_date is None and proposal.interpreted_duration is None:
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


def _understand_request_with_catalog(
    request: RawRequest,
    extractor: NonTemporalIntentExtractor,
    temporal_selector: TemporalCandidateSelector,
    holiday_provider: HolidayDateProvider | None = None,
    *,
    evaluation_catalog: TemporalCandidateCatalog | None = None,
) -> RequestUnderstandingResult:
    """Implementation shared by the public workflow and private frozen-fixture harness."""

    select_candidates = getattr(temporal_selector, "select_candidates", None)
    if not callable(select_candidates):
        raise TypeError("selector-only workflow requires callable select_candidates")

    extract_non_temporal = getattr(extractor, "extract_non_temporal", None)
    if not callable(extract_non_temporal):
        raise TypeError("selector-only workflow requires extract_non_temporal")
    non_temporal = extract_non_temporal(NonTemporalExtractionInput(request_text=request.text))
    if not isinstance(non_temporal, NonTemporalIntentExtraction):
        raise TypeError("extract_non_temporal returned an unexpected output type")

    scan = scan_temporal_request(request)
    catalog = evaluation_catalog or build_temporal_candidates(scan)
    # Frozen manual catalogs predate the runtime policy and intentionally omit unresolved
    # alternatives for deterministic fixture groups. Keep that private harness on its historical
    # planner solely so it can test projection/restoration; normal requests always use the
    # selector-only production policy.
    selection_plan = plan_temporal_selection(
        catalog,
        policy=(
            DEFAULT_TEMPORAL_SELECTOR_POLICY
            if evaluation_catalog is not None
            else "supported_or_unresolved"
        ),
    )
    selected_candidates = list(selection_plan.auto_selected)
    if selection_plan.selector_groups:
        selector_input = build_temporal_selector_input(catalog, selection_plan)
        selector_output = select_candidates(selector_input)
        selected_candidates.extend(restore_selector_output(selector_input, selector_output))
    compiled = compile_temporal_candidates(
        request,
        catalog,
        selected_candidates,
        holiday_provider=holiday_provider,
    )

    extraction = CoarseIntentExtraction(
        **non_temporal.model_dump(mode="python"),
        date_anchors=compiled.extraction.date_anchors,
        temporal_phrases=compiled.extraction.temporal_phrases,
    )
    extraction = preserve_explicit_airport_codes(request, extraction)
    temporal_evidence: list[GroundedTemporalEvidence] = ground_temporal_evidence(
        request, compiled.extraction
    )
    temporal_evidence = ground_temporal_relation_evidence(
        request, compiled.graph, temporal_evidence
    )
    conflicts = detect_conflicts(
        compiled.departure_window,
        compiled.return_window,
        compiled.proposal.interpreted_duration,
        temporal_evidence,
        return_strict_upper_bound=next(
            (
                bound.boundary
                for bound in compiled.endpoint_bounds
                if bound.target.value == "return" and bound.direction == "before"
            ),
            None,
        ),
    )
    parsed = ParsedRequest(
        raw_text=request.text,
        context=request.context,
        travelers=extraction.travelers,
        origins=extraction.origins,
        destinations=extraction.destinations,
        departure_expression=None,
        return_expression=None,
        departure_window=compiled.departure_window,
        return_window=compiled.return_window,
        duration=None,
        cabins=extraction.cabins,
        search_modes=extraction.search_modes,
        date_flexibility=[],
        repositioning_allowed=extraction.repositioning_allowed,
        hard_constraints=extraction.hard_constraints,
        unknowns=_collect_unknowns(extraction, compiled.proposal),
        conflicts=conflicts,
        temporal_extraction=extraction,
        temporal_evidence=temporal_evidence,
        resolved_date_anchors=list(compiled.resolved_anchors),
        temporal_relations=compiled.graph,
        date_resolution=compiled.proposal,
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=decide_clarification(parsed),
    )


def understand_request(
    request: RawRequest,
    extractor: NonTemporalIntentExtractor,
    temporal_selector: TemporalCandidateSelector,
    holiday_provider: HolidayDateProvider | None = None,
) -> RequestUnderstandingResult:
    """Understand a request through the deterministic compiler and required selector.

    Temporal facts are scanner/compiler-owned. The first model boundary can only extract
    non-temporal semantics; the second can only select opaque, locally scoped compiler
    candidates. A selector is required before any Pass-1 call, even when a request later has
    no ambiguous candidate groups. The public boundary accepts no test catalog, strategy, policy,
    resolver, or fallback configuration.
    """

    return _understand_request_with_catalog(
        request,
        extractor,
        temporal_selector,
        holiday_provider,
    )


def _understand_request_with_frozen_catalog(
    request: RawRequest,
    extractor: NonTemporalIntentExtractor,
    temporal_selector: TemporalCandidateSelector,
    holiday_provider: HolidayDateProvider | None,
    *,
    catalog: TemporalCandidateCatalog,
) -> RequestUnderstandingResult:
    """Private evaluation-only entry point for frozen manual selector catalogs."""

    if catalog.scan.request_text != request.text:
        raise ValueError("frozen selector catalog request text must exactly match raw request")
    return _understand_request_with_catalog(
        request,
        extractor,
        temporal_selector,
        holiday_provider,
        evaluation_catalog=catalog,
    )
