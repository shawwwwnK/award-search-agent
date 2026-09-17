"""Deterministic endpoint-market search planning.

The module constructs provider-neutral search intent from a ready
``EffectiveRequest``.  It does not call a provider or manufacture an
itinerary, availability, price, or booking assertion.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

from pydantic import ValidationError

from award_agent.domain import (
    EffectiveField,
    EffectiveRequest,
    FieldProvenance,
    LocationRef,
    SearchMode,
)
from award_agent.search_planning.airport_selection_policy import (
    AirportSelectionCapPolicy,
    airport_selection_cap_policy_digest,
    context_for_resolved_location,
)
from award_agent.search_planning.airport_selector import (
    AIRPORT_SELECTOR_ADAPTER_VERSION,
    AIRPORT_SELECTOR_ORIGINAL_SIMPLE_PROMPT_VERSION,
    AIRPORT_SELECTOR_PROMPT_VERSION,
    AIRPORT_SELECTOR_RESPONSE_SCHEMA_SHA256,
    AirportSelectionPlanningInput,
    AirportSelectionPlanningResult,
    AirportSelectionRecord,
    AirportSelectionReplayReceipt,
    airport_selection_distance_policy_digest,
    airport_selection_record_digest,
    validate_airport_selection_proposal,
)
from award_agent.search_planning.capabilities import (
    CachedSearchCapability,
    capability_content_digest,
    default_capability_path,
    load_cached_search_capability,
)
from award_agent.search_planning.contracts import (
    AirportSelection,
    AirportSelectionKind,
    AwardSearchItem,
    BudgetKind,
    BudgetReceipt,
    CapabilityReceipt,
    CapabilitySourceReceipt,
    ComponentPaymentMode,
    DateBasis,
    DateEnvelope,
    DeferredConstraintObligation,
    EndpointProbe,
    ExplicitPathComponent,
    ExplicitPathHypothesis,
    FilterObligation,
    FilterObligationKind,
    FreshnessClass,
    GroundedEndpointResult,
    LocationResolutionStatus,
    ManualCashCheckTemplate,
    ManualCashTemporalValidationKind,
    PathExplorationReceipt,
    PaymentPattern,
    PlanIdentity,
    PlanningInputEnvelope,
    PlanningIssue,
    PlanningIssueCategory,
    PlanningIssueCode,
    RepositioningPolicyReceipt,
    ResolvedLocation,
    ResultValidationKind,
    ResultValidationObligation,
    RouteEdgeEvidenceReceipt,
    SearchPlan,
    SearchPlanningIssue,
    SearchPlanningIssueCode,
    SearchPlanningOutcome,
    SearchPlanningResult,
    SearchScope,
    SelectedAirport,
    TemporalDerivation,
)
from award_agent.search_planning.distance_consistency import CityAirportDistanceConsistency
from award_agent.search_planning.knowledge import (
    DirectedRouteEdge,
    KnowledgeRepository,
    KnowledgeSnapshot,
    PlanningKnowledgeRepository,
    RouteDateApplicability,
)
from award_agent.search_planning.locations import ground_endpoint
from award_agent.search_planning.policy import PlanningPolicy

_CANONICALIZATION_VERSION = "effective-request-canonical-json-v1"
_DIGEST_ALGORITHM_VERSION = "sha256-v1"
_CORE_UNKNOWN_FIELDS = frozenset({"origin", "destination", "departure", "travelers"})


def plan_searches(
    envelope: PlanningInputEnvelope,
    *,
    policy: PlanningPolicy,
    capability: CachedSearchCapability,
    snapshot: KnowledgeSnapshot | None = None,
    repository: PlanningKnowledgeRepository | None = None,
    _grounded_endpoint_overrides: dict[tuple[str, str], GroundedEndpointResult] | None = None,
) -> SearchPlanningResult:
    """Compile one immutable request into endpoint-market award search items.

    The caller owns session revision authority.  This boundary computes (and
    optionally checks) the request digest but never mutates the request or
    attempts clarification.
    """

    if (snapshot is None) == (repository is None):
        raise ValueError("plan_searches requires exactly one of snapshot or repository")

    # ``model_copy(update=...)`` can bypass Pydantic validation.  Re-validating
    # here keeps a caller from smuggling a corrupt capability into the compiler.
    try:
        capability = CachedSearchCapability.model_validate(
            capability.model_dump(mode="python", round_trip=True)
        )
    except ValidationError as exc:
        return _capability_evidence_failure(str(exc))

    digest = effective_request_digest(envelope.effective_request)
    admission_issues = _admission_issues(envelope, policy, digest)
    if admission_issues:
        return SearchPlanningResult(
            outcome=SearchPlanningOutcome.UNPLANNABLE,
            issues=tuple(admission_issues),
            budget_receipts=_admission_budget_receipts(envelope.effective_request, policy),
        )

    if repository is not None:
        active_repository: PlanningKnowledgeRepository = repository
    else:
        assert snapshot is not None
        active_repository = KnowledgeRepository(snapshot)
    origin_results = _ground_all(
        envelope.effective_request.origins,
        "origin",
        active_repository,
        policy,
        _provenance_for(envelope.effective_request, EffectiveField.ORIGIN),
        _grounded_endpoint_overrides,
    )
    destination_results = _ground_all(
        envelope.effective_request.destinations,
        "destination",
        active_repository,
        policy,
        _provenance_for(envelope.effective_request, EffectiveField.DESTINATION),
        _grounded_endpoint_overrides,
    )
    location_results = (*origin_results, *destination_results)
    grounding_issues = tuple(
        issue for result in location_results if result.selection is None for issue in result.issues
    )
    if grounding_issues:
        outcome = (
            SearchPlanningOutcome.EVIDENCE_FAILURE
            if any(issue.category is PlanningIssueCategory.EVIDENCE for issue in grounding_issues)
            else SearchPlanningOutcome.UNPLANNABLE
        )
        return SearchPlanningResult(outcome=outcome, issues=grounding_issues)

    origin_airports = tuple(
        airport
        for result in origin_results
        if result.selection is not None
        for airport in result.selection.airports
    )
    destination_airports = tuple(
        airport
        for result in destination_results
        if result.selection is not None
        for airport in result.selection.airports
    )
    pairs_by_fact_ids: dict[tuple[str, str], tuple[SelectedAirport, SelectedAirport]] = {}
    for origin_airport in origin_airports:
        for destination_airport in destination_airports:
            pairs_by_fact_ids.setdefault(
                (origin_airport.airport_id, destination_airport.airport_id),
                (origin_airport, destination_airport),
            )
    # The input alternatives are canonicalized, while each geographic policy's
    # airport order is an intentional product-priority order and therefore part
    # of the semantic plan rather than incidental fixture ordering.
    pairs = tuple(pairs_by_fact_ids.values())
    input_days = _inclusive_input_days(envelope.effective_request)
    if len(pairs) > policy.max_endpoint_pairs:
        return SearchPlanningResult(
            outcome=SearchPlanningOutcome.UNPLANNABLE,
            issues=(
                SearchPlanningIssue(
                    code=SearchPlanningIssueCode.ENDPOINT_PAIR_BUDGET_EXCEEDED,
                    message="required endpoint airport-pair coverage exceeds the planning budget",
                ),
            ),
            budget_receipts=(
                _budget_receipt(
                    BudgetKind.INPUT_WINDOW_DAYS, input_days, policy.max_input_window_days
                ),
                _budget_receipt(
                    BudgetKind.ENDPOINT_PAIR_COUNT, len(pairs), policy.max_endpoint_pairs
                ),
            ),
        )

    identity = _identity(envelope, policy, active_repository, capability, digest)
    try:
        probes, endpoint_items = _build_endpoint_items(
            pairs,
            envelope.effective_request,
            active_repository,
        )
        if len(endpoint_items) > policy.max_total_award_search_items:
            return SearchPlanningResult(
                outcome=SearchPlanningOutcome.UNPLANNABLE,
                issues=(
                    SearchPlanningIssue(
                        code=SearchPlanningIssueCode.TOTAL_SEARCH_ITEM_BUDGET_EXCEEDED,
                        message="required endpoint searches exceed the total search-item budget",
                    ),
                ),
                budget_receipts=(
                    _budget_receipt(
                        BudgetKind.TOTAL_AWARD_SEARCH_ITEM_COUNT,
                        len(endpoint_items),
                        policy.max_total_award_search_items,
                    ),
                ),
            )
        endpoint_date_work_days = input_days * len(endpoint_items)
        if endpoint_date_work_days > policy.max_date_expanded_work_days:
            return SearchPlanningResult(
                outcome=SearchPlanningOutcome.UNPLANNABLE,
                issues=(
                    SearchPlanningIssue(
                        code=SearchPlanningIssueCode.TOTAL_SEARCH_ITEM_BUDGET_EXCEEDED,
                        message="required endpoint date-expanded work exceeds the planning budget",
                    ),
                ),
                budget_receipts=(
                    _budget_receipt(
                        BudgetKind.DATE_EXPANDED_WORK_DAYS,
                        endpoint_date_work_days,
                        policy.max_date_expanded_work_days,
                    ),
                ),
            )
        (
            path_hypotheses,
            path_items,
            path_exclusions,
            path_receipts,
            path_exploration_receipts,
        ) = _build_explicit_paths(
            pairs,
            envelope.effective_request,
            active_repository,
            policy,
            remaining_item_slots=policy.max_total_award_search_items - len(endpoint_items),
            remaining_date_work_days=(policy.max_date_expanded_work_days - endpoint_date_work_days),
        )
    except ValidationError as exc:
        return _invalid_filter_failure(str(exc))
    except ValueError as exc:
        return _planner_contract_failure(str(exc))
    unsupported_kinds = tuple(
        sorted(
            {
                obligation.kind.value
                for item in (*endpoint_items, *path_items)
                for obligation in item.filter_obligations
                if not capability.supports(obligation.kind)
            }
        )
    )
    if unsupported_kinds:
        return _capability_evidence_failure(
            "capability record does not support generated filters: " + ", ".join(unsupported_kinds)
        )
    try:
        manual_cash_enabled = SearchMode.CASH in envelope.effective_request.search_modes
        payment_patterns = _payment_patterns(
            path_hypotheses, manual_cash_enabled=manual_cash_enabled
        )
        plan = SearchPlan(
            identity=identity,
            capability_id=capability.capability_id,
            capability_version=capability.capability_version,
            location_results=location_results,
            endpoint_probes=probes,
            award_search_items=(*endpoint_items, *path_items),
            explicit_path_hypotheses=path_hypotheses,
            manual_cash_enabled=manual_cash_enabled,
            payment_patterns=payment_patterns,
            manual_cash_check_templates=_manual_cash_check_templates(
                path_hypotheses,
                payment_patterns=payment_patterns,
                request=envelope.effective_request,
            ),
            path_exploration_receipts=path_exploration_receipts,
            deferred_constraints=_deferred_constraints(envelope.effective_request),
            nonblocking_issues=_nonblocking_issues(envelope.effective_request),
            repositioning_policy_receipt=RepositioningPolicyReceipt(
                requested_value=envelope.effective_request.repositioning_allowed,
                field_provenance=_provenance_for(
                    envelope.effective_request, EffectiveField.REPOSITIONING
                ),
            ),
            budget_receipts=_plan_budget_receipts(
                input_days=input_days,
                endpoint_pair_count=len(pairs),
                endpoint_item_count=len(endpoint_items),
                endpoint_date_work_days=endpoint_date_work_days,
                path_receipts=path_receipts,
                policy=policy,
            ),
        )
    except (ValidationError, ValueError) as exc:
        return _planner_contract_failure(str(exc))
    return SearchPlanningResult(
        outcome=(
            SearchPlanningOutcome.REDUCED_COVERAGE
            if path_exclusions
            else SearchPlanningOutcome.PLANNED
        ),
        plan=plan,
        exclusions=path_exclusions,
    )


def plan_searches_with_default_capability(
    envelope: PlanningInputEnvelope,
    *,
    policy: PlanningPolicy,
    snapshot: KnowledgeSnapshot | None = None,
    repository: PlanningKnowledgeRepository | None = None,
    capability_path: Path | None = None,
) -> SearchPlanningResult:
    """Convenience wrapper that turns local capability evidence failures into a typed outcome.

    The compiler itself deliberately requires a validated capability argument;
    this is the only place that reads a default local record.
    """

    try:
        capability = load_cached_search_capability(capability_path or default_capability_path())
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return _capability_evidence_failure(str(exc))
    return plan_searches(
        envelope,
        policy=policy,
        snapshot=snapshot,
        repository=repository,
        capability=capability,
    )


def plan_searches_from_airport_selection_records(
    selection_input: AirportSelectionPlanningInput,
    *,
    selection_cap_policy: AirportSelectionCapPolicy,
    distance_policy: CityAirportDistanceConsistency,
    policy: PlanningPolicy,
    capability: CachedSearchCapability,
    repository: PlanningKnowledgeRepository,
) -> AirportSelectionPlanningResult:
    """Replay model-selected catalog endpoints without an LLM invocation.

    This is deliberately a separate planning input from the frozen Milestone 0
    fixture path. A record supplies an exploratory model selection, while the
    normal ``plan_searches`` path retains its reviewed JSON group behavior.
    """

    receipt = _selection_replay_receipt(selection_input, selection_cap_policy, distance_policy)
    try:
        overrides = _selection_record_overrides(
            selection_input, selection_cap_policy, distance_policy, policy, repository
        )
    except (ValueError, ValidationError) as exc:
        return AirportSelectionPlanningResult(
            planning_result=_planner_contract_failure(str(exc)), replay_receipt=receipt
        )
    return AirportSelectionPlanningResult(
        planning_result=plan_searches(
            selection_input.envelope,
            policy=policy,
            capability=capability,
            repository=repository,
            _grounded_endpoint_overrides=overrides,
        ),
        replay_receipt=receipt,
    )


def _selection_replay_receipt(
    selection_input: AirportSelectionPlanningInput,
    selection_cap_policy: AirportSelectionCapPolicy,
    distance_policy: CityAirportDistanceConsistency,
) -> AirportSelectionReplayReceipt:
    snapshots = {record.catalog_snapshot_id for record in selection_input.selection_records}
    if len(snapshots) != 1:
        raise ValueError("selection replay requires records from exactly one catalog snapshot")
    return AirportSelectionReplayReceipt(
        record_digests=tuple(
            sorted(
                airport_selection_record_digest(record)
                for record in selection_input.selection_records
            )
        ),
        cap_policy_version=selection_cap_policy.policy_version,
        cap_policy_digest=airport_selection_cap_policy_digest(selection_cap_policy),
        distance_policy_version=distance_policy.policy_version,
        distance_policy_digest=airport_selection_distance_policy_digest(distance_policy),
        catalog_snapshot_id=next(iter(snapshots)),
    )


def _selection_record_overrides(
    selection_input: AirportSelectionPlanningInput,
    selection_cap_policy: AirportSelectionCapPolicy,
    distance_policy: CityAirportDistanceConsistency,
    planning_policy: PlanningPolicy,
    repository: PlanningKnowledgeRepository,
) -> dict[tuple[str, str], GroundedEndpointResult]:
    """Make validated record results available to the deterministic compiler."""

    records: dict[tuple[str, str], AirportSelectionRecord] = {
        (record.role, record.resolved_entity.entity_id): record
        for record in selection_input.selection_records
    }
    used_record_keys: set[tuple[str, str]] = set()
    overrides: dict[tuple[str, str], GroundedEndpointResult] = {}
    for role, locations in (
        ("origin", selection_input.envelope.effective_request.origins),
        ("destination", selection_input.envelope.effective_request.destinations),
    ):
        for location in _canonical_locations(locations):
            grounded = ground_endpoint(location, role, repository, planning_policy)
            resolution = grounded.resolution
            if resolution.status is not LocationResolutionStatus.RESOLVED:
                continue
            if resolution.resolved_entity_id is None:
                continue  # Explicit and named airports retain their existing singleton path.
            key = (role, resolution.resolved_entity_id)
            record = records.get(key)
            if record is None:
                raise ValueError(
                    "each resolved geographic endpoint requires a supplied airport-selection record"
                )
            used_record_keys.add(key)
            overrides[(role, _location_override_key(location))] = _selection_record_result(
                role,
                location,
                resolution,
                record,
                selection_cap_policy,
                distance_policy,
                repository,
                planning_policy,
            )
    if set(records) != used_record_keys:
        raise ValueError(
            "selection records must correspond to resolved geographic request endpoints"
        )
    return overrides


def _selection_record_result(
    role: str,
    location: LocationRef,
    resolution: ResolvedLocation,
    record: AirportSelectionRecord,
    selection_cap_policy: AirportSelectionCapPolicy,
    distance_policy: CityAirportDistanceConsistency,
    repository: PlanningKnowledgeRepository,
    planning_policy: PlanningPolicy,
) -> GroundedEndpointResult:
    context = context_for_resolved_location(resolution, repository)
    if record.resolved_entity != context:
        raise ValueError("selection record context does not match resolved catalog entity")
    if (
        record.catalog_snapshot_id != repository.snapshot_id
        or record.catalog_receipt != repository.knowledge_receipt
    ):
        raise ValueError("selection record catalog identity does not match the planning repository")
    cap = selection_cap_policy.applicable_cap_for(context)
    if (
        record.cap_policy_digest != airport_selection_cap_policy_digest(selection_cap_policy)
        or record.applicable_cap != cap
    ):
        raise ValueError("selection record does not match the supplied selection-cap policy")
    if record.distance_policy != distance_policy:
        raise ValueError("selection record does not match the supplied distance policy")
    rebuilt = validate_airport_selection_proposal(
        role=record.role,
        context=context,
        cap_policy=selection_cap_policy,
        distance_policy=distance_policy,
        proposal=record.proposal,
        model=record.model,
        repository=repository,
    )
    if (
        record.candidate_validations != rebuilt.candidate_validations
        or record.accepted_airports != rebuilt.accepted_airports
        or record.applicable_cap != rebuilt.applicable_cap
        or record.selector_adapter_version != AIRPORT_SELECTOR_ADAPTER_VERSION
        or record.prompt_version
        not in {
            AIRPORT_SELECTOR_PROMPT_VERSION,
            AIRPORT_SELECTOR_ORIGINAL_SIMPLE_PROMPT_VERSION,
        }
        or record.response_schema_sha256 != AIRPORT_SELECTOR_RESPONSE_SCHEMA_SHA256
    ):
        raise ValueError("selection record validation does not reproduce against supplied evidence")
    source_ids = set(resolution.evidence_source_ids)
    for selected in record.accepted_airports:
        airport = repository.lookup_airport_iata(selected.airport_iata)
        if airport is None or airport.airport_id != selected.airport_id:
            raise ValueError("selection record cites an airport absent from this catalog snapshot")
        if airport.source_ids != selected.airport_evidence_source_ids:
            raise ValueError(
                "selection record airport evidence does not match this catalog snapshot"
            )
        source_ids.update(airport.source_ids)
    freshness = repository.freshness_for_source_ids(
        source_ids, max_source_evidence_age_days=planning_policy.max_source_evidence_age_days
    )
    if freshness is FreshnessClass.STALE:
        return GroundedEndpointResult(
            role=role,  # type: ignore[arg-type]
            snapshot_id=repository.snapshot_id,
            freshness=freshness,
            resolution=resolution,
            issues=(
                PlanningIssue(
                    code=PlanningIssueCode.STALE_KNOWLEDGE,
                    message="airport-selection record relies on stale snapshot evidence",
                    snapshot_id=repository.snapshot_id,
                    location_value=location.value,
                ),
            ),
        )
    if not record.accepted_airports:
        return GroundedEndpointResult(
            role=role,  # type: ignore[arg-type]
            snapshot_id=repository.snapshot_id,
            freshness=freshness,
            resolution=resolution,
            issues=(
                PlanningIssue(
                    code=PlanningIssueCode.MODEL_AIRPORT_SELECTION_UNAVAILABLE,
                    message="model airport selection produced no accepted exploratory endpoints",
                    snapshot_id=repository.snapshot_id,
                    location_value=location.value,
                    candidate_ids=(record.resolved_entity.entity_id,),
                ),
            ),
        )
    return GroundedEndpointResult(
        role=role,  # type: ignore[arg-type]
        snapshot_id=repository.snapshot_id,
        freshness=freshness,
        resolution=resolution,
        selection=AirportSelection(
            kind=AirportSelectionKind.MODEL_PROPOSED,
            resolved_location=resolution,
            airports=record.accepted_airports,
        ),
    )


def effective_request_digest(effective_request: EffectiveRequest) -> str:
    """Return a stable digest over complete JSON-mode EffectiveRequest data."""

    canonical = json.dumps(
        _canonical_request_payload(effective_request),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_request_payload(effective_request: EffectiveRequest) -> dict[str, object]:
    """Canonicalize unordered alternative sets before calculating plan identity.

    Origin/destination alternatives, cabins, and modes are independent sets at
    this boundary.  Their wire order must not manufacture a different plan.
    """

    payload = effective_request.model_dump(mode="json", round_trip=True)
    for key in ("origins", "destinations"):
        values = payload.get(key)
        if isinstance(values, list):
            payload[key] = sorted(
                values,
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            )
    for key in ("cabins", "search_modes"):
        values = payload.get(key)
        if isinstance(values, list):
            payload[key] = sorted(values)
    return payload


def _admission_issues(
    envelope: PlanningInputEnvelope, policy: PlanningPolicy, digest: str
) -> list[SearchPlanningIssue]:
    request = envelope.effective_request
    issues: list[SearchPlanningIssue] = []
    if envelope.source.expected_effective_request_digest not in {None, digest}:
        issues.append(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.REQUEST_DIGEST_MISMATCH,
                message="caller expected digest does not match the supplied EffectiveRequest",
            )
        )
    if not request.origins:
        issues.append(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.MISSING_ORIGIN,
                message="origin is required",
                field="origin",
            )
        )
    if not request.destinations:
        issues.append(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.MISSING_DESTINATION,
                message="destination is required",
                field="destination",
            )
        )
    if request.travelers is None:
        issues.append(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.MISSING_TRAVELERS,
                message="travelers are required",
                field="travelers",
            )
        )
    if request.departure_window is None:
        issues.append(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.MISSING_DEPARTURE_WINDOW,
                message="a bounded departure window is required",
                field="departure",
            )
        )
    if request.departure_window is not None:
        inclusive_days = (request.departure_window.end - request.departure_window.start).days + 1
        if inclusive_days > policy.max_input_window_days:
            issues.append(
                SearchPlanningIssue(
                    code=SearchPlanningIssueCode.INPUT_WINDOW_EXCEEDS_BUDGET,
                    message="departure window exceeds the configured inclusive planning budget",
                    field="departure",
                )
            )
    for constraint in request.hard_constraints:
        if not constraint.strip():
            issues.append(
                SearchPlanningIssue(
                    code=SearchPlanningIssueCode.INVALID_HARD_CONSTRAINT,
                    message="hard constraints must be nonempty when supplied",
                    field="hard_constraints",
                    preserved_value=constraint,
                )
            )
    for unknown in request.unknowns:
        if unknown.field in _CORE_UNKNOWN_FIELDS:
            issues.append(
                SearchPlanningIssue(
                    code=SearchPlanningIssueCode.CORE_FIELD_UNKNOWN,
                    message="a product-required field remains unknown",
                    field=unknown.field,
                )
            )
    if request.conflicts:
        issues.append(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.ACTIVE_CONFLICT,
                message="active EffectiveRequest conflicts prevent planning",
            )
        )
    if SearchMode.AWARD not in request.search_modes:
        issues.append(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.AWARD_MODE_REQUIRED,
                message="an award search mode is required for automated planning",
                field="search_mode",
            )
        )
    return issues


def _canonical_locations(locations: Iterable[LocationRef]) -> tuple[LocationRef, ...]:
    """Order independent alternatives without attempting semantic pairing."""

    return tuple(
        sorted(
            locations,
            key=lambda location: (
                location.kind.value,
                location.value.casefold(),
                location.raw_text,
            ),
        )
    )


def _ground_all(
    locations: Iterable[LocationRef],
    role: str,
    repository: PlanningKnowledgeRepository,
    policy: PlanningPolicy,
    field_provenance: FieldProvenance | None,
    overrides: dict[tuple[str, str], GroundedEndpointResult] | None,
) -> tuple[GroundedEndpointResult, ...]:
    return tuple(
        (
            (overrides or {}).get((role, _location_override_key(location)))
            or ground_endpoint(location, role, repository, policy)
        ).model_copy(update={"field_provenance": field_provenance})
        for location in _canonical_locations(locations)
    )


def _location_override_key(location: LocationRef) -> str:
    return f"{location.kind.value}\x1f{location.value.casefold()}\x1f{location.raw_text}"


def _identity(
    envelope: PlanningInputEnvelope,
    policy: PlanningPolicy,
    repository: PlanningKnowledgeRepository,
    capability: CachedSearchCapability,
    digest: str,
) -> PlanIdentity:
    return PlanIdentity(
        session_id=envelope.source.session_id,
        revision=envelope.source.revision,
        effective_request_digest=digest,
        canonicalization_version=_CANONICALIZATION_VERSION,
        digest_algorithm_version=_DIGEST_ALGORITHM_VERSION,
        policy_version=policy.policy_version,
        policy_digest=_canonical_digest(policy),
        snapshot_id=repository.snapshot_id,
        snapshot_as_of=repository.snapshot_as_of,
        knowledge_receipt=repository.knowledge_receipt,
        capability_receipt=CapabilityReceipt(
            capability_id=capability.capability_id,
            capability_version=capability.capability_version,
            content_sha256=capability_content_digest(capability),
            source_receipts=tuple(
                CapabilitySourceReceipt(
                    source_id=source.source_id,
                    content_sha256=source.content_sha256,
                )
                for source in capability.sources
            ),
            caveats=capability.caveats,
        ),
    )


def _build_endpoint_items(
    pairs: tuple[tuple[SelectedAirport, SelectedAirport], ...],
    request: EffectiveRequest,
    repository: PlanningKnowledgeRepository,
) -> tuple[tuple[EndpointProbe, ...], tuple[AwardSearchItem, ...]]:
    assert request.departure_window is not None
    assert request.travelers is not None
    cabin_values = tuple(sorted({cabin.value for cabin in request.cabins}))
    requested_cabins = tuple(sorted(set(request.cabins), key=lambda cabin: cabin.value))
    cabin_provenance = _provenance_for(request, EffectiveField.CABIN)
    filters = (
        (
            FilterObligation(
                kind=FilterObligationKind.CABIN_AVAILABLE_IN,
                values=cabin_values,
                origin="user_requirement",
                field_provenance=cabin_provenance,
            ),
        )
        if cabin_values
        else ()
    )
    seat_obligation = ResultValidationObligation(
        kind=ResultValidationKind.MINIMUM_AWARD_SEATS,
        minimum_seats=request.travelers,
        field_provenance=_provenance_for(request, EffectiveField.TRAVELERS),
    )
    probes: list[EndpointProbe] = []
    items: list[AwardSearchItem] = []
    for origin_airport, destination_airport in pairs:
        origin_record = repository.airport(origin_airport.airport_id)
        if origin_record is None:
            raise ValueError("validated selected airport is absent from the knowledge repository")
        date_envelope = DateEnvelope(
            start=request.departure_window.start,
            end=request.departure_window.end,
            basis=DateBasis.FIRST_ORIGIN_AIRPORT_LOCAL,
            timezone=origin_record.timezone,
            effective_window_precision=request.departure_window.precision.value,
            field_provenance=_provenance_for(request, EffectiveField.DEPARTURE),
        )
        semantic_key = {
            "scope": "endpoint_market",
            "origin_airport_fact_id": origin_airport.airport_id,
            "destination_airport_fact_id": destination_airport.airport_id,
            "date_envelope": date_envelope.model_dump(mode="json"),
            "requested_cabins": [cabin.value for cabin in requested_cabins],
        }
        pair_key = _canonical_digest(semantic_key)
        probe_id = f"endpoint-market:{pair_key}"
        probes.append(
            EndpointProbe(
                probe_id=probe_id,
                origin_endpoint=origin_airport,
                destination_endpoint=destination_airport,
                date_envelope=date_envelope,
                requested_cabins=requested_cabins,
                traveler_count=request.travelers,
            )
        )
        items.append(
            AwardSearchItem(
                item_id=f"award:{_canonical_digest({'probe_id': probe_id, 'mode': 'award', 'filters': [item.model_dump(mode='json') for item in filters], 'validation': seat_obligation.model_dump(mode='json')})}",
                probe_id=probe_id,
                origin_airport_fact_id=origin_airport.airport_id,
                destination_airport_fact_id=destination_airport.airport_id,
                date_envelope=date_envelope,
                requested_cabins=requested_cabins,
                filter_obligations=filters,
                result_validation_obligations=(seat_obligation,),
            )
        )
    return tuple(probes), tuple(items)


def _build_explicit_paths(
    pairs: tuple[tuple[SelectedAirport, SelectedAirport], ...],
    request: EffectiveRequest,
    repository: PlanningKnowledgeRepository,
    policy: PlanningPolicy,
    *,
    remaining_item_slots: int,
    remaining_date_work_days: int,
) -> tuple[
    tuple[ExplicitPathHypothesis, ...],
    tuple[AwardSearchItem, ...],
    tuple[str, ...],
    dict[BudgetKind, tuple[int, int]],
    tuple[PathExplorationReceipt, ...],
]:
    """Materialize only directed, evidence-backed two-component hypotheses.

    A topology edge proves only a physical directional possibility.  Every
    component keeps a structural direct-flight prefilter and a later exact-trip
    validation obligation; this code never turns topology into a schedule or a
    protected connection claim.
    """

    assert request.departure_window is not None
    assert request.travelers is not None
    candidates: list[
        tuple[
            SelectedAirport,
            SelectedAirport,
            SelectedAirport,
            DirectedRouteEdge,
            DirectedRouteEdge,
        ]
    ] = []
    pairs_with_topology: set[tuple[str, str]] = set()
    candidate_limit = policy.max_path_candidate_exploration
    candidate_overflow = False
    exclusions: list[str] = []
    exploration_receipts: list[PathExplorationReceipt] = []
    # Geographic endpoint selection order is a product preference.  Within it,
    # repository candidates are sorted, so fixture record order cannot alter
    # the canonical output.
    for origin, destination in pairs:
        outgoing_edges, outgoing_overflow = repository.outgoing_route_edges(
            origin.airport_id,
            limit=policy.max_outgoing_route_edges_per_endpoint_pair,
        )
        available_edges: dict[str, DirectedRouteEdge] = {
            edge.edge_id: edge for edge in outgoing_edges
        }
        pair_candidate_count = 0
        if outgoing_overflow:
            exclusions.append(
                "optional explicit-path outgoing topology exceeded the per-pair edge limit for "
                f"{origin.airport_iata}->{destination.airport_iata}"
            )
        for first_edge in outgoing_edges:
            intermediate_id = first_edge.destination_airport_id
            second_edge = repository.route_edge(intermediate_id, destination.airport_id)
            if second_edge is not None:
                available_edges[second_edge.edge_id] = second_edge
            if second_edge is None:
                continue
            if _route_edge_is_stale(first_edge, repository, policy) or _route_edge_is_stale(
                second_edge, repository, policy
            ):
                exclusions.append(
                    "optional explicit-path topology omitted stale route evidence for "
                    f"{origin.airport_iata}->{destination.airport_iata}"
                )
                continue
            if not _route_edges_cover_path_envelopes(first_edge, second_edge, request):
                exclusions.append(
                    "optional explicit-path topology omitted known-inapplicable route evidence for "
                    f"{origin.airport_iata}->{destination.airport_iata}"
                )
                continue
            pairs_with_topology.add((origin.airport_id, destination.airport_id))
            if len(candidates) >= candidate_limit:
                candidate_overflow = True
                continue
            intermediate_record = repository.airport(intermediate_id)
            if intermediate_record is None:  # KnowledgeSnapshot validation should prevent this.
                raise ValueError("route topology cites an absent intermediate airport")
            intermediate = SelectedAirport(
                airport_id=intermediate_record.airport_id,
                airport_iata=intermediate_record.iata,
                airport_evidence_source_ids=intermediate_record.source_ids,
            )
            candidates.append((origin, intermediate, destination, first_edge, second_edge))
            pair_candidate_count += 1
        exploration_receipts.append(
            PathExplorationReceipt(
                origin_airport_fact_id=origin.airport_id,
                destination_airport_fact_id=destination.airport_id,
                examined_edge_ids=tuple(sorted(edge.edge_id for edge in outgoing_edges)),
                candidate_count=pair_candidate_count,
                outgoing_edge_limit=policy.max_outgoing_route_edges_per_endpoint_pair,
                overflow=outgoing_overflow,
                available_edge_evidence=tuple(
                    _route_edge_evidence(available_edges[edge_id])
                    for edge_id in sorted(available_edges)
                ),
            )
        )

    if not candidates:
        exclusion = (
            "optional explicit-path candidate exploration reached its configured limit"
            if candidate_overflow
            else "optional explicit-path topology is unavailable for the selected endpoint pairs"
        )
        return (
            (),
            (),
            tuple(dict.fromkeys((*exclusions, exclusion))),
            {
                BudgetKind.PATH_CANDIDATE_COUNT: (0, candidate_limit),
                BudgetKind.PATH_HYPOTHESIS_COUNT: (0, policy.max_path_hypotheses),
                BudgetKind.TOTAL_AWARD_SEARCH_ITEM_COUNT: (0, max(0, remaining_item_slots)),
                BudgetKind.DATE_EXPANDED_WORK_DAYS: (0, max(0, remaining_date_work_days)),
            },
            tuple(exploration_receipts),
        )

    missing_pairs = [
        f"{origin.airport_iata}->{destination.airport_iata}"
        for origin, destination in pairs
        if (origin.airport_id, destination.airport_id) not in pairs_with_topology
    ]
    if missing_pairs:
        exclusions.append(
            "optional explicit-path topology is unavailable for endpoint pairs: "
            + ", ".join(missing_pairs)
        )
    if candidate_overflow:
        exclusions.append(
            "optional explicit-path candidate exploration reached its configured limit"
        )
    requested_cabins = tuple(sorted(set(request.cabins), key=lambda cabin: cabin.value))
    cabin_filters = _cabin_filters(request)
    seat_obligation = ResultValidationObligation(
        kind=ResultValidationKind.MINIMUM_AWARD_SEATS,
        minimum_seats=request.travelers,
        field_provenance=_provenance_for(request, EffectiveField.TRAVELERS),
    )
    items_by_id: dict[str, AwardSearchItem] = {}
    hypotheses: list[ExplicitPathHypothesis] = []
    materialized_work_days = 0
    for origin, intermediate, destination, first_edge, second_edge in candidates:
        if len(hypotheses) >= policy.max_path_hypotheses:
            exclusions.append("optional explicit-path hypotheses exceeded the configured limit")
            break
        component_specs: list[
            tuple[
                int,
                SelectedAirport,
                SelectedAirport,
                DirectedRouteEdge,
                DateEnvelope,
                TemporalDerivation,
                AwardSearchItem,
            ]
        ] = []
        for index, component_origin, component_destination, edge in (
            (1, origin, intermediate, first_edge),
            (2, intermediate, destination, second_edge),
        ):
            origin_record = repository.airport(component_origin.airport_id)
            if origin_record is None:
                raise ValueError("route component has an absent origin airport")
            offsets = (0, 0) if index == 1 else (-1, 2)
            date_envelope = DateEnvelope(
                start=request.departure_window.start + timedelta(days=offsets[0]),
                end=request.departure_window.end + timedelta(days=offsets[1]),
                basis=(
                    DateBasis.FIRST_ORIGIN_AIRPORT_LOCAL
                    if index == 1
                    else DateBasis.LATER_COMPONENT_ORIGIN_AIRPORT_LOCAL
                ),
                timezone=origin_record.timezone,
                effective_window_precision=request.departure_window.precision.value,
                field_provenance=_provenance_for(request, EffectiveField.DEPARTURE),
            )
            temporal_derivation = TemporalDerivation(
                component_index=index,
                origin_airport_fact_id=component_origin.airport_id,
                basis=date_envelope.basis,
                timezone=origin_record.timezone,
                start_offset_days=offsets[0],
                end_offset_days=offsets[1],
                source_window_start=request.departure_window.start,
                source_window_end=request.departure_window.end,
                derived_start=date_envelope.start,
                derived_end=date_envelope.end,
            )
            structure_filter = FilterObligation(
                kind=FilterObligationKind.DIRECT_FLIGHT_AVAILABLE,
                values=("true",),
                origin="planner_structure",
            )
            structure_validation = ResultValidationObligation(
                kind=ResultValidationKind.EXACT_PHYSICAL_COMPONENT_STRUCTURE,
                expected_origin_airport_fact_id=component_origin.airport_id,
                expected_destination_airport_fact_id=component_destination.airport_id,
            )
            filters = (*cabin_filters, structure_filter)
            validations = (seat_obligation, structure_validation)
            semantic_key = {
                "scope": SearchScope.EXPLICIT_PHYSICAL_COMPONENT.value,
                "origin_airport_fact_id": component_origin.airport_id,
                "destination_airport_fact_id": component_destination.airport_id,
                "date_envelope": date_envelope.model_dump(mode="json"),
                "requested_cabins": [cabin.value for cabin in requested_cabins],
                "filters": [item.model_dump(mode="json") for item in filters],
                "validations": [item.model_dump(mode="json") for item in validations],
            }
            item_id = f"award:{_canonical_digest(semantic_key)}"
            component_specs.append(
                (
                    index,
                    component_origin,
                    component_destination,
                    edge,
                    date_envelope,
                    temporal_derivation,
                    AwardSearchItem(
                        item_id=item_id,
                        scope=SearchScope.EXPLICIT_PHYSICAL_COMPONENT,
                        origin_airport_fact_id=component_origin.airport_id,
                        destination_airport_fact_id=component_destination.airport_id,
                        date_envelope=date_envelope,
                        requested_cabins=requested_cabins,
                        filter_obligations=filters,
                        result_validation_obligations=validations,
                    ),
                )
            )

        # Budget the full semantic hypothesis before mutating item state.  An
        # item already materialized for another path is deliberately free here
        # because execution reuses it; duplicate items within this hypothesis
        # are counted once as well.
        prospective_items = {
            item.item_id: item for *_, item in component_specs if item.item_id not in items_by_id
        }
        prospective_work_days = sum(
            (item.date_envelope.end - item.date_envelope.start).days + 1
            for item in prospective_items.values()
        )
        if len(items_by_id) + len(prospective_items) > remaining_item_slots:
            exclusions.append(
                "optional explicit-path searches exceeded the total search-item budget"
            )
            continue
        if materialized_work_days + prospective_work_days > remaining_date_work_days:
            exclusions.append("optional explicit-path date-expanded work exceeded its budget")
            continue

        items_by_id.update(prospective_items)
        materialized_work_days += prospective_work_days
        components: list[ExplicitPathComponent] = []
        for (
            index,
            component_origin,
            component_destination,
            edge,
            date_envelope,
            temporal_derivation,
            item,
        ) in component_specs:
            components.append(
                ExplicitPathComponent(
                    component_id=(
                        "component:"
                        + _canonical_digest(
                            {
                                "requested_origin": origin.airport_id,
                                "intermediate": intermediate.airport_id,
                                "requested_destination": destination.airport_id,
                                "edge": edge.edge_id,
                                "item": item.item_id,
                            }
                        )
                    ),
                    component_index=index,
                    origin_endpoint=component_origin,
                    destination_endpoint=component_destination,
                    route_edge_id=edge.edge_id,
                    route_evidence_source_ids=edge.source_ids,
                    route_evidence_kind=edge.evidence_kind.value,
                    route_date_applicability=edge.date_applicability.value,
                    route_applicable_start=edge.applicable_start,
                    route_applicable_end=edge.applicable_end,
                    date_applicability_disclosure=(
                        "date_applicability_unknown"
                        if edge.date_applicability is RouteDateApplicability.UNKNOWN
                        else None
                    ),
                    date_envelope=date_envelope,
                    temporal_derivation=temporal_derivation,
                    award_search_item_id=item.item_id,
                )
            )
        hypothesis_key = {
            "origin": origin.airport_id,
            "intermediate": intermediate.airport_id,
            "destination": destination.airport_id,
            "edge_ids": [first_edge.edge_id, second_edge.edge_id],
            "component_item_ids": [component.award_search_item_id for component in components],
        }
        hypotheses.append(
            ExplicitPathHypothesis(
                hypothesis_id=f"path:{_canonical_digest(hypothesis_key)}",
                requested_origin_endpoint=origin,
                requested_destination_endpoint=destination,
                intermediate_airport_fact_id=intermediate.airport_id,
                components=tuple(components),
            )
        )

    if not hypotheses and not exclusions:
        exclusions.append("optional explicit-path topology could not be materialized within policy")
    return (
        tuple(hypotheses),
        tuple(items_by_id[item_id] for item_id in sorted(items_by_id)),
        tuple(dict.fromkeys(exclusions)),
        {
            BudgetKind.PATH_CANDIDATE_COUNT: (len(candidates), candidate_limit),
            BudgetKind.PATH_HYPOTHESIS_COUNT: (len(hypotheses), policy.max_path_hypotheses),
            BudgetKind.TOTAL_AWARD_SEARCH_ITEM_COUNT: (
                len(items_by_id),
                max(0, remaining_item_slots),
            ),
            BudgetKind.DATE_EXPANDED_WORK_DAYS: (
                materialized_work_days,
                max(0, remaining_date_work_days),
            ),
        },
        tuple(exploration_receipts),
    )


def _route_edge_is_stale(
    edge: DirectedRouteEdge, repository: PlanningKnowledgeRepository, policy: PlanningPolicy
) -> bool:
    """Evaluate only the evidence an optional topology edge actually cites."""

    return (
        repository.freshness_for_source_ids(
            edge.source_ids,
            max_source_evidence_age_days=policy.max_source_evidence_age_days,
        )
        is FreshnessClass.STALE
    )


def _route_edge_evidence(edge: DirectedRouteEdge) -> RouteEdgeEvidenceReceipt:
    """Project one knowledge edge into the plan's auditable receipt."""

    return RouteEdgeEvidenceReceipt(
        edge_id=edge.edge_id,
        origin_airport_fact_id=edge.origin_airport_id,
        destination_airport_fact_id=edge.destination_airport_id,
        route_evidence_source_ids=edge.source_ids,
        route_evidence_kind=edge.evidence_kind.value,
        route_date_applicability=edge.date_applicability.value,
        route_applicable_start=edge.applicable_start,
        route_applicable_end=edge.applicable_end,
    )


def _route_edges_cover_path_envelopes(
    first_edge: DirectedRouteEdge,
    second_edge: DirectedRouteEdge,
    request: EffectiveRequest,
) -> bool:
    """Return whether known topology intervals cover the whole planned envelope.

    Unknown applicability remains exploratory only and is disclosed on the
    resulting component.  A known interval must cover every date placed in a
    reusable search item; otherwise a planner would claim topology support for
    dates outside the evidence.
    """

    assert request.departure_window is not None
    first_start, first_end = request.departure_window.start, request.departure_window.end
    later_start = request.departure_window.start - timedelta(days=1)
    later_end = request.departure_window.end + timedelta(days=2)

    def covers(edge: DirectedRouteEdge, start: date, end: date) -> bool:
        if edge.date_applicability is RouteDateApplicability.UNKNOWN:
            return True
        assert edge.applicable_start is not None
        assert edge.applicable_end is not None
        return edge.applicable_start <= start and edge.applicable_end >= end

    return covers(first_edge, first_start, first_end) and covers(
        second_edge, later_start, later_end
    )


def _cabin_filters(request: EffectiveRequest) -> tuple[FilterObligation, ...]:
    cabin_values = tuple(sorted({cabin.value for cabin in request.cabins}))
    if not cabin_values:
        return ()
    return (
        FilterObligation(
            kind=FilterObligationKind.CABIN_AVAILABLE_IN,
            values=cabin_values,
            origin="user_requirement",
            field_provenance=_provenance_for(request, EffectiveField.CABIN),
        ),
    )


def _payment_patterns(
    paths: tuple[ExplicitPathHypothesis, ...], *, manual_cash_enabled: bool
) -> tuple[PaymentPattern, ...]:
    """Annotate each materialized two-component path without duplicating it.

    Endpoint-market searches are already intrinsically award-only through
    ``AwardSearchItem.automated_mode``.  Only explicit two-component topology
    paths get payment alternatives, and none creates an automated cash item.
    """

    mode_sets: tuple[tuple[ComponentPaymentMode, ComponentPaymentMode], ...] = (
        (ComponentPaymentMode.AWARD, ComponentPaymentMode.AWARD),
        *(
            (
                (ComponentPaymentMode.AWARD, ComponentPaymentMode.MANUAL_CASH),
                (ComponentPaymentMode.MANUAL_CASH, ComponentPaymentMode.AWARD),
            )
            if manual_cash_enabled
            else ()
        ),
    )
    patterns: list[PaymentPattern] = []
    for path in paths:
        for modes in mode_sets:
            patterns.append(
                PaymentPattern(
                    pattern_id=(
                        "payment-pattern:"
                        + _canonical_digest(
                            {
                                "hypothesis_id": path.hypothesis_id,
                                "component_payment_modes": [mode.value for mode in modes],
                            }
                        )
                    ),
                    hypothesis_id=path.hypothesis_id,
                    component_payment_modes=modes,
                )
            )
    return tuple(patterns)


def _manual_cash_check_templates(
    paths: tuple[ExplicitPathHypothesis, ...],
    *,
    payment_patterns: tuple[PaymentPattern, ...],
    request: EffectiveRequest,
) -> tuple[ManualCashCheckTemplate, ...]:
    """Create dormant dependencies for hybrid paths only.

    A template references the existing evidence-backed component and the other
    component's award item.  It is intentionally not an itinerary, price,
    availability observation, or provider request.
    """

    assert request.travelers is not None
    path_by_id = {path.hypothesis_id: path for path in paths}
    requested_cabins = tuple(sorted(set(request.cabins), key=lambda cabin: cabin.value))
    templates: list[ManualCashCheckTemplate] = []
    for pattern in payment_patterns:
        manual_indexes = tuple(
            index
            for index, mode in enumerate(pattern.component_payment_modes, start=1)
            if mode is ComponentPaymentMode.MANUAL_CASH
        )
        if not manual_indexes:
            continue
        # SearchPlan validates this shape again; keeping the guard here makes
        # malformed internal calls fail close before a template can be emitted.
        if len(manual_indexes) != 1:
            raise ValueError("a hybrid payment pattern must have exactly one manual component")
        path = path_by_id[pattern.hypothesis_id]
        manual_index = manual_indexes[0]
        manual_component = path.components[manual_index - 1]
        award_component = path.components[0 if manual_index == 2 else 1]
        temporal_kind = (
            ManualCashTemporalValidationKind.FIRST_COMPONENT_WITHIN_ORIGINAL_WINDOW
            if manual_index == 1
            else ManualCashTemporalValidationKind.LATER_COMPONENT_REQUIRES_ASSEMBLED_JOURNEY_VALIDATION
        )
        templates.append(
            ManualCashCheckTemplate(
                template_id=(
                    "manual-cash-check:"
                    + _canonical_digest(
                        {
                            "payment_pattern_id": pattern.pattern_id,
                            "manual_component_id": manual_component.component_id,
                            "relevant_award_search_item_id": award_component.award_search_item_id,
                        }
                    )
                ),
                payment_pattern_id=pattern.pattern_id,
                hypothesis_id=path.hypothesis_id,
                manual_component_id=manual_component.component_id,
                manual_component_index=manual_index,
                relevant_award_search_item_id=award_component.award_search_item_id,
                traveler_count=request.travelers,
                requested_cabins=requested_cabins,
                temporal_validation_kind=temporal_kind,
            )
        )
    return tuple(templates)


def _provenance_for(request: EffectiveRequest, field: EffectiveField) -> FieldProvenance | None:
    return next((item for item in request.field_provenance if item.field is field), None)


def _deferred_constraints(request: EffectiveRequest) -> tuple[DeferredConstraintObligation, ...]:
    provenance = _provenance_for(request, EffectiveField.HARD_CONSTRAINTS)
    return tuple(
        DeferredConstraintObligation(text=constraint, field_provenance=provenance)
        for constraint in request.hard_constraints
    )


def _nonblocking_issues(request: EffectiveRequest) -> tuple[SearchPlanningIssue, ...]:
    observations = [
        SearchPlanningIssue(
            code=SearchPlanningIssueCode.NONBLOCKING_UNKNOWN,
            message=unknown.detail.strip() or "nonblocking unknown preserved without detail",
            field=unknown.field,
            preserved_value=unknown.detail,
        )
        for unknown in request.unknowns
        if unknown.field not in _CORE_UNKNOWN_FIELDS
    ]
    observations.append(
        SearchPlanningIssue(
            code=SearchPlanningIssueCode.REPOSITIONING_POLICY_NOT_CONSUMED,
            message="v1 policy enables repositioning research without consuming repositioning_allowed",
            field="repositioning",
        )
    )
    return tuple(observations)


def _canonical_digest(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", round_trip=True)
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _inclusive_input_days(request: EffectiveRequest) -> int:
    if request.departure_window is None:
        return 0
    return (request.departure_window.end - request.departure_window.start).days + 1


def _budget_receipt(kind: BudgetKind, observed: int, limit: int) -> BudgetReceipt:
    return BudgetReceipt(
        kind=kind,
        observed=observed,
        limit=limit,
        disposition="within_limit" if observed <= limit else "exceeded",
    )


def _plan_budget_receipts(
    *,
    input_days: int,
    endpoint_pair_count: int,
    endpoint_item_count: int,
    endpoint_date_work_days: int,
    path_receipts: dict[BudgetKind, tuple[int, int]],
    policy: PlanningPolicy,
) -> tuple[BudgetReceipt, ...]:
    """Return all successful-plan work receipts in a stable enum order."""

    values: dict[BudgetKind, tuple[int, int]] = {
        BudgetKind.INPUT_WINDOW_DAYS: (input_days, policy.max_input_window_days),
        BudgetKind.ENDPOINT_PAIR_COUNT: (endpoint_pair_count, policy.max_endpoint_pairs),
        BudgetKind.PATH_CANDIDATE_COUNT: path_receipts[BudgetKind.PATH_CANDIDATE_COUNT],
        BudgetKind.PATH_HYPOTHESIS_COUNT: path_receipts[BudgetKind.PATH_HYPOTHESIS_COUNT],
        BudgetKind.TOTAL_AWARD_SEARCH_ITEM_COUNT: (
            endpoint_item_count + path_receipts[BudgetKind.TOTAL_AWARD_SEARCH_ITEM_COUNT][0],
            policy.max_total_award_search_items,
        ),
        BudgetKind.DATE_EXPANDED_WORK_DAYS: (
            endpoint_date_work_days + path_receipts[BudgetKind.DATE_EXPANDED_WORK_DAYS][0],
            policy.max_date_expanded_work_days,
        ),
    }
    return tuple(_budget_receipt(kind, *values[kind]) for kind in BudgetKind)


def _admission_budget_receipts(
    request: EffectiveRequest, policy: PlanningPolicy
) -> tuple[BudgetReceipt, ...]:
    """Expose an input-window overflow as structured evidence on failure."""

    if request.departure_window is None:
        return ()
    return (
        _budget_receipt(
            BudgetKind.INPUT_WINDOW_DAYS,
            _inclusive_input_days(request),
            policy.max_input_window_days,
        ),
    )


def _capability_evidence_failure(detail: str) -> SearchPlanningResult:
    return SearchPlanningResult(
        outcome=SearchPlanningOutcome.EVIDENCE_FAILURE,
        issues=(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.CAPABILITY_EVIDENCE_FAILURE,
                message="cached-search capability evidence is unavailable or invalid",
                field="capability",
                preserved_value=detail,
            ),
        ),
    )


def _invalid_filter_failure(detail: str) -> SearchPlanningResult:
    return SearchPlanningResult(
        outcome=SearchPlanningOutcome.UNPLANNABLE,
        issues=(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.INVALID_FILTER_OBLIGATION,
                message="a user filter obligation could not be materialized from EffectiveRequest",
                field="hard_constraints",
                preserved_value=detail,
            ),
        ),
    )


def _planner_contract_failure(detail: str) -> SearchPlanningResult:
    return SearchPlanningResult(
        outcome=SearchPlanningOutcome.EVIDENCE_FAILURE,
        issues=(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.PLANNER_CONTRACT_FAILURE,
                message="planner could not materialize a valid typed search contract",
                field="planner",
                preserved_value=detail,
            ),
        ),
    )
