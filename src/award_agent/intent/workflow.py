"""Two-pass request-understanding workflow orchestration."""

from typing import Literal

from award_agent.domain import (
    CoarseIntentExtraction,
    DateResolutionProposal,
    GroundedTemporalEvidence,
    IntentRepairTrace,
    ModelPassRepairTrace,
    ParsedRequest,
    RawRequest,
    RequestUnderstandingResult,
    UnknownField,
    UnknownReason,
)
from award_agent.intent.clarification import decide_clarification
from award_agent.intent.conflicts import detect_conflicts
from award_agent.intent.conformance import validate_temporal_conformance
from award_agent.intent.evidence import (
    TemporalResolutionValidationError,
    assign_stable_anchor_ids,
    ground_temporal_evidence,
    ground_temporal_relation_evidence,
)
from award_agent.intent.extractor import (
    IntentExtractor,
    TemporalCandidateSelector,
    TemporalResolver,
)
from award_agent.intent.holidays import HolidayDateProvider
from award_agent.intent.locations import preserve_explicit_airport_codes
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
    RejectedCoarseExtractionView,
    StructuredValidationErrorView,
    TemporalResolutionResult,
    build_temporal_interpretation_input,
)
from award_agent.intent.temporal import (
    enrich_temporal_anchors,
    evaluate_temporal_relation_graph,
    proposal_window_to_date_window,
    sanitize_temporal_extraction,
)
from award_agent.intent.temporal_candidates import (
    TemporalCandidateCatalog,
    build_temporal_candidates,
)
from award_agent.intent.temporal_compiler import CompiledTemporalIntent, compile_temporal_candidates
from award_agent.intent.temporal_lexing import scan_temporal_request
from award_agent.intent.temporal_selector import (
    DEFAULT_TEMPORAL_SELECTOR_POLICY,
    TemporalSelectorPolicy,
    build_temporal_selector_input,
    plan_temporal_selection,
    restore_selector_output,
    unresolved_selection,
)


def _collect_unknowns(
    extraction: CoarseIntentExtraction,
    proposal: DateResolutionProposal,
) -> list[UnknownField]:
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
    # A known trip duration is a usable return constraint even when the departure
    # window is still unresolved.  Do not report a second ``return_or_duration``
    # unknown in that case: clarification should focus on the missing departure.
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


def understand_request(
    request: RawRequest,
    extractor: IntentExtractor,
    temporal_resolver: TemporalResolver | None,
    holiday_provider: HolidayDateProvider | None = None,
    *,
    temporal_strategy: Literal["two_pass", "compiler_select_v1"] = "two_pass",
    temporal_selector: TemporalCandidateSelector | None = None,
    selector_policy: TemporalSelectorPolicy = DEFAULT_TEMPORAL_SELECTOR_POLICY,
    evaluation_temporal_catalog: TemporalCandidateCatalog | None = None,
) -> RequestUnderstandingResult:
    """Understand a request with the rollback resolver or deterministic compiler path.

    ``compiler_select_v1`` deliberately auto-selects only the grammar with one safe
    interpretation under its default ``ambiguous_only`` policy.  It does not invoke a model
    temporal resolver.  The experiment-only ``supported_or_unresolved`` policy instead lets an
    optional selector choose between every supported local interpretation and its opaque
    unresolved alternative.

    ``evaluation_temporal_catalog`` is a test-only hook for exercising the selector path with
    manually constructed ambiguity catalogs.  It is intentionally unavailable to the rollback
    route and must belong to the exact raw request being understood.
    """

    if temporal_strategy not in {"two_pass", "compiler_select_v1"}:
        raise ValueError(f"unsupported temporal strategy: {temporal_strategy}")
    if selector_policy not in {"ambiguous_only", "supported_or_unresolved"}:
        raise ValueError(f"unsupported temporal selector policy: {selector_policy}")
    if (
        temporal_strategy != "compiler_select_v1"
        and selector_policy != DEFAULT_TEMPORAL_SELECTOR_POLICY
    ):
        raise ValueError(
            "selector_policy is only supported by compiler_select_v1"
        )
    if (
        temporal_strategy == "compiler_select_v1"
        and selector_policy == "supported_or_unresolved"
        and temporal_selector is None
    ):
        raise ValueError(
            "supported_or_unresolved selector_policy requires a temporal_selector"
        )
    if evaluation_temporal_catalog is not None and temporal_strategy != "compiler_select_v1":
        raise ValueError(
            "evaluation_temporal_catalog is only supported by compiler_select_v1"
        )
    if (
        evaluation_temporal_catalog is not None
        and evaluation_temporal_catalog.scan.request_text != request.text
    ):
        raise ValueError(
            "evaluation_temporal_catalog request text must exactly match the raw request"
        )
    compiled_temporal: CompiledTemporalIntent | None = None

    def pass_one_checkpoint(
        candidate: CoarseIntentExtraction,
    ) -> tuple[CoarseIntentExtraction, list[GroundedTemporalEvidence]]:
        checked = sanitize_temporal_extraction(request, candidate)
        checked = preserve_explicit_airport_codes(request, checked)
        evidence = ground_temporal_evidence(request, checked)
        checked = assign_stable_anchor_ids(request, checked)
        return checked, evidence

    if temporal_strategy == "compiler_select_v1":
        # This route intentionally has no legacy ``extract`` fallback.  Its model boundary is
        # structurally incapable of authoring temporal facts, which remain scanner/compiler-owned.
        extract_non_temporal = getattr(extractor, "extract_non_temporal", None)
        if not callable(extract_non_temporal):
            raise TypeError(
                "compiler_select_v1 requires an extractor with extract_non_temporal"
            )
        non_temporal = extract_non_temporal(NonTemporalExtractionInput(request_text=request.text))
        if not isinstance(non_temporal, NonTemporalIntentExtraction):
            raise TypeError("extract_non_temporal returned an unexpected output type")
        pass_one_trace = ModelPassRepairTrace(
            first_attempt_valid=True,
            repair_ran=False,
            repair_succeeded=False,
        )
        scan = scan_temporal_request(request)
        catalog = evaluation_temporal_catalog or build_temporal_candidates(scan)
        selection_plan = plan_temporal_selection(catalog, policy=selector_policy)
        if selection_plan.selector_groups:
            if temporal_selector is None:
                selected_candidates = (
                    *selection_plan.auto_selected,
                    *unresolved_selection(catalog, selection_plan),
                )
            else:
                selector_input = build_temporal_selector_input(catalog, selection_plan)
                selector_output = temporal_selector.select_candidates(selector_input)
                selected_candidates = (
                    *selection_plan.auto_selected,
                    *restore_selector_output(selector_input, selector_output),
                )
        else:
            selected_candidates = selection_plan.auto_selected
        compiled_temporal = compile_temporal_candidates(
            request,
            catalog,
            selected_candidates,
            holiday_provider=holiday_provider,
        )
        # Assemble the legacy compatibility shape explicitly.  The model contributes only
        # non-temporal fields; scanner-derived compiler output is the sole temporal authority.
        extraction = CoarseIntentExtraction(
            **non_temporal.model_dump(mode="python"),
            date_anchors=compiled_temporal.extraction.date_anchors,
            temporal_phrases=compiled_temporal.extraction.temporal_phrases,
        )
        extraction = preserve_explicit_airport_codes(request, extraction)
        temporal_relations = compiled_temporal.graph
        proposal = compiled_temporal.proposal
        resolved_anchors = list(compiled_temporal.resolved_anchors)
        temporal_evidence = ground_temporal_evidence(request, compiled_temporal.extraction)
        pass_two_trace = ModelPassRepairTrace(
            first_attempt_valid=True,
            repair_ran=False,
            repair_succeeded=False,
        )
    else:
        if temporal_resolver is None:
            raise ValueError("two_pass requires a temporal resolver")
        coarse_input = CoarseExtractionInput(request_text=request.text)
        first_extraction = extractor.extract(coarse_input)
        try:
            extraction, temporal_evidence = pass_one_checkpoint(first_extraction)
            pass_one_trace = ModelPassRepairTrace(
                first_attempt_valid=True,
                repair_ran=False,
                repair_succeeded=False,
            )
        except TemporalResolutionValidationError as first_error:
            if first_error.details.stage not in {
                "pass_one_grounding",
                "pass_one_anchor_validation",
            }:
                raise
            repair = getattr(extractor, "repair_extract", None)
            if repair is None:
                raise
            try:
                repaired_extraction = repair(
                    CoarseExtractionRepairInput(
                        original_input=coarse_input,
                        rejected_output=RejectedCoarseExtractionView.from_output(first_extraction),
                        validation_errors=[
                            StructuredValidationErrorView.from_details(first_error.details)
                        ],
                    )
                )
            except RuntimeError as repair_error:
                repair_call_failure = TemporalResolutionValidationError(
                    "pass-one repair call failed",
                    stage=first_error.details.stage,
                    error_code="repair_call_failed",
                    validation_cause=type(repair_error).__name__,
                )
                pass_one_trace = ModelPassRepairTrace(
                    first_attempt_valid=False,
                    repair_ran=True,
                    repair_succeeded=False,
                    final_failure=repair_call_failure.as_dict(),
                )
                raise repair_call_failure.attach_repair_trace(
                    pass_one_trace.model_dump(mode="json")
                ) from repair_error
            try:
                extraction, temporal_evidence = pass_one_checkpoint(repaired_extraction)
            except TemporalResolutionValidationError as final_error:
                pass_one_trace = ModelPassRepairTrace(
                    first_attempt_valid=False,
                    repair_ran=True,
                    repair_succeeded=False,
                    final_failure=final_error.as_dict(),
                )
                raise final_error.attach_repair_trace(
                    pass_one_trace.model_dump(mode="json")
                ) from first_error
            pass_one_trace = ModelPassRepairTrace(
                first_attempt_valid=False,
                repair_ran=True,
                repair_succeeded=True,
            )

        resolved_anchors = enrich_temporal_anchors(
            request,
            extraction,
            holiday_provider,
        )
        temporal_input = build_temporal_interpretation_input(
            request.text, extraction, temporal_evidence
        )
        resolution_result = temporal_resolver.resolve_dates(temporal_input)
        if isinstance(resolution_result, TemporalResolutionResult):
            temporal_relations = resolution_result.relations
            pass_two_trace = resolution_result.repair_trace
        else:
            # Deterministic fakes still receive the same catalog-backed conformance gate below.
            temporal_relations = resolution_result
            pass_two_trace = ModelPassRepairTrace(
                first_attempt_valid=True,
                repair_ran=False,
                repair_succeeded=False,
            )
        try:
            validate_temporal_conformance(temporal_input, temporal_relations)
            proposal = evaluate_temporal_relation_graph(
                request,
                extraction,
                temporal_relations,
                resolved_anchors,
            )
        except TemporalResolutionValidationError as first_error:
            if first_error.details.stage not in {
                "pass_two_conformance",
                "pass_two_dependency_validation",
            }:
                raise
            if pass_two_trace.repair_ran:
                exhausted_trace = ModelPassRepairTrace(
                    first_attempt_valid=False,
                    repair_ran=True,
                    repair_succeeded=False,
                    final_failure=first_error.as_dict(),
                )
                raise first_error.attach_repair_trace(exhausted_trace.model_dump(mode="json"))
            repair = getattr(temporal_resolver, "repair_dates", None)
            if repair is None:
                raise
            try:
                repaired_relations = repair(
                    temporal_input,
                    temporal_relations,
                    [StructuredValidationErrorView.from_details(first_error.details)],
                )
            except TemporalResolutionValidationError as repair_validation_failure:
                pass_two_trace = ModelPassRepairTrace(
                    first_attempt_valid=False,
                    repair_ran=True,
                    repair_succeeded=False,
                    final_failure=repair_validation_failure.as_dict(),
                )
                raise repair_validation_failure.attach_repair_trace(
                    pass_two_trace.model_dump(mode="json")
                ) from first_error
            except RuntimeError as repair_error:
                repair_call_failure = TemporalResolutionValidationError(
                    "pass-two repair call failed",
                    stage=first_error.details.stage,
                    error_code="repair_call_failed",
                    validation_cause=type(repair_error).__name__,
                )
                pass_two_trace = ModelPassRepairTrace(
                    first_attempt_valid=False,
                    repair_ran=True,
                    repair_succeeded=False,
                    final_failure=repair_call_failure.as_dict(),
                )
                raise repair_call_failure.attach_repair_trace(
                    pass_two_trace.model_dump(mode="json")
                ) from repair_error
            try:
                validate_temporal_conformance(temporal_input, repaired_relations)
                proposal = evaluate_temporal_relation_graph(
                    request,
                    extraction,
                    repaired_relations,
                    resolved_anchors,
                )
            except TemporalResolutionValidationError as final_error:
                pass_two_trace = ModelPassRepairTrace(
                    first_attempt_valid=False,
                    repair_ran=True,
                    repair_succeeded=False,
                    final_failure=final_error.as_dict(),
                )
                raise final_error.attach_repair_trace(
                    pass_two_trace.model_dump(mode="json")
                ) from first_error
            temporal_relations = repaired_relations
            pass_two_trace = ModelPassRepairTrace(
                first_attempt_valid=False,
                repair_ran=True,
                repair_succeeded=True,
            )
    temporal_evidence = ground_temporal_relation_evidence(
        request, temporal_relations, temporal_evidence
    )

    departure_window = (
        compiled_temporal.departure_window
        if compiled_temporal is not None
        else proposal_window_to_date_window(proposal, "departure")
    )
    return_window = (
        compiled_temporal.return_window
        if compiled_temporal is not None
        else proposal_window_to_date_window(proposal, "return")
    )
    conflicts = detect_conflicts(
        departure_window,
        return_window,
        proposal.interpreted_duration,
        temporal_evidence,
        return_strict_upper_bound=next(
            (
                bound.boundary
                for bound in (compiled_temporal.endpoint_bounds if compiled_temporal else ())
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
        temporal_evidence=temporal_evidence,
        resolved_date_anchors=resolved_anchors,
        temporal_relations=temporal_relations,
        date_resolution=proposal,
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=decide_clarification(parsed),
        repair_trace=IntentRepairTrace(
            pass_one=pass_one_trace,
            pass_two=pass_two_trace,
        ),
    )
