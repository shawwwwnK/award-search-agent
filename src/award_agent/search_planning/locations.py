"""Ground ``LocationRef`` candidates using only reviewed snapshot evidence."""

from __future__ import annotations

import re

from award_agent.domain import LocationKind, LocationRef
from award_agent.search_planning.contracts import (
    AirportSelection,
    AirportSelectionKind,
    FreshnessClass,
    GroundedEndpointResult,
    LocationResolutionStatus,
    PlanningIssue,
    PlanningIssueCode,
    ResolvedLocation,
    SelectedAirport,
)
from award_agent.search_planning.knowledge import (
    Airport,
    GeoEntity,
    KnowledgeRepository,
    normalize_location_alias,
)
from award_agent.search_planning.policy import PlanningPolicy

_EXPLICIT_IATA = re.compile(r"^[A-Za-z]{3}$")


def ground_endpoint(
    location: LocationRef,
    role: str,
    repository: KnowledgeRepository,
    policy: PlanningPolicy,
) -> GroundedEndpointResult:
    """Resolve and select one endpoint without changing the source LocationRef.

    ``role`` is deliberately checked by the contract rather than inferred from
    request wording.  This increment does not pair origins and destinations or
    build a provider search item.
    """

    if role not in {"origin", "destination"}:
        raise ValueError("role must be origin or destination")
    normalized = normalize_location_alias(location.value)
    resolution = _resolve_location(location, normalized, repository)
    freshness = repository.freshness_for_source_ids(
        resolution.evidence_source_ids,
        max_source_evidence_age_days=policy.max_source_evidence_age_days,
    )
    if resolution.status is not LocationResolutionStatus.RESOLVED:
        return GroundedEndpointResult(
            role=role,  # type: ignore[arg-type]
            snapshot_id=repository.snapshot_id,
            freshness=freshness,
            resolution=resolution,
            issues=(_issue_for_resolution(resolution, repository),),
        )
    if freshness is FreshnessClass.STALE:
        return _stale_evidence_failure(role, resolution, repository, freshness)
    if resolution.resolved_airport_id is not None:
        airport = repository.airport(resolution.resolved_airport_id)
        if airport is None:  # defensive: snapshot integrity already rejects this.
            return _missing_airport(role, resolution, repository, freshness)
        freshness = repository.freshness_for_source_ids(
            airport.source_ids,
            max_source_evidence_age_days=policy.max_source_evidence_age_days,
        )
        if freshness is FreshnessClass.STALE:
            return _stale_evidence_failure(role, resolution, repository, freshness)
        selection_kind = (
            AirportSelectionKind.EXPLICIT_IATA
            if _is_preserved_explicit_iata(location)
            else AirportSelectionKind.NAMED_AIRPORT
        )
        return GroundedEndpointResult(
            role=role,  # type: ignore[arg-type]
            snapshot_id=repository.snapshot_id,
            freshness=freshness,
            resolution=resolution,
            selection=AirportSelection(
                kind=selection_kind,
                resolved_location=resolution,
                airports=(_select_single_airport(airport),),
            ),
        )
    return _select_geographic_group(role, resolution, repository, policy)


def _resolve_location(
    location: LocationRef, normalized: str, repository: KnowledgeRepository
) -> ResolvedLocation:
    if location.kind is LocationKind.AIRPORT:
        if _is_preserved_explicit_iata(location):
            airport = repository.lookup_airport_iata(location.value.upper())
            if airport is None:
                return ResolvedLocation(
                    location=location,
                    status=LocationResolutionStatus.EVIDENCE_FAILURE,
                    normalized_alias=normalized,
                    candidate_ids=(location.value,),
                )
            return _resolved_airport(location, normalized, airport)
        candidates = repository.resolve_airports_by_alias(normalized)
        return _resolve_airport_candidates(location, normalized, candidates, repository)

    entity_candidates = repository.resolve_entities(location.kind, normalized)
    if len(entity_candidates) == 1:
        return _resolved_entity(location, normalized, entity_candidates[0])
    if len(entity_candidates) > 1:
        return ResolvedLocation(
            location=location,
            status=LocationResolutionStatus.AMBIGUOUS,
            normalized_alias=normalized,
            candidate_ids=tuple(candidate.entity_id for candidate in entity_candidates),
        )
    status = (
        LocationResolutionStatus.KIND_MISMATCH
        if repository.alias_exists_for_other_kind(location.kind, normalized)
        else LocationResolutionStatus.UNRESOLVED
    )
    return ResolvedLocation(location=location, status=status, normalized_alias=normalized)


def _resolve_airport_candidates(
    location: LocationRef,
    normalized: str,
    candidates: tuple[Airport, ...],
    repository: KnowledgeRepository,
) -> ResolvedLocation:
    if len(candidates) == 1:
        return _resolved_airport(location, normalized, candidates[0])
    if len(candidates) > 1:
        return ResolvedLocation(
            location=location,
            status=LocationResolutionStatus.AMBIGUOUS,
            normalized_alias=normalized,
            candidate_ids=tuple(candidate.airport_id for candidate in candidates),
        )
    status = (
        LocationResolutionStatus.KIND_MISMATCH
        if repository.alias_exists_for_other_kind(LocationKind.AIRPORT, normalized)
        else LocationResolutionStatus.UNRESOLVED
    )
    return ResolvedLocation(location=location, status=status, normalized_alias=normalized)


def _resolved_entity(location: LocationRef, normalized: str, entity: GeoEntity) -> ResolvedLocation:
    return ResolvedLocation(
        location=location,
        status=LocationResolutionStatus.RESOLVED,
        normalized_alias=normalized,
        resolved_entity_id=entity.entity_id,
        evidence_source_ids=entity.source_ids,
        candidate_ids=(entity.entity_id,),
    )


def _resolved_airport(location: LocationRef, normalized: str, airport: Airport) -> ResolvedLocation:
    return ResolvedLocation(
        location=location,
        status=LocationResolutionStatus.RESOLVED,
        normalized_alias=normalized,
        resolved_airport_id=airport.airport_id,
        evidence_source_ids=airport.source_ids,
        candidate_ids=(airport.airport_id,),
    )


def _is_preserved_explicit_iata(location: LocationRef) -> bool:
    """Accept only a raw, upstream-classified IATA identifier as explicit.

    ``LocationRef.value`` is normally a resolver candidate.  A model proposing
    ``SFO`` for wording such as ``San Francisco`` therefore remains a narrow
    alias lookup and cannot receive explicit-airport treatment.
    """

    raw_identifier = location.raw_text.strip()
    return (
        location.kind is LocationKind.AIRPORT
        and _EXPLICIT_IATA.fullmatch(raw_identifier) is not None
        and raw_identifier.casefold() == location.value.casefold()
    )


def _select_geographic_group(
    role: str,
    resolution: ResolvedLocation,
    repository: KnowledgeRepository,
    policy: PlanningPolicy,
) -> GroundedEndpointResult:
    assert resolution.resolved_entity_id is not None
    entity = repository.get_entity(resolution.resolved_entity_id)
    assert entity is not None
    freshness = repository.freshness_for_source_ids(
        entity.source_ids,
        max_source_evidence_age_days=policy.max_source_evidence_age_days,
    )
    selection_policy = repository.policy_for(entity.entity_id, entity.kind)
    if selection_policy is None:
        return GroundedEndpointResult(
            role=role,  # type: ignore[arg-type]
            snapshot_id=repository.snapshot_id,
            freshness=freshness,
            resolution=resolution,
            issues=(
                PlanningIssue(
                    code=PlanningIssueCode.MISSING_SELECTION_POLICY,
                    message="grounded geography has no reviewed airport-selection policy",
                    snapshot_id=repository.snapshot_id,
                    location_value=resolution.location.value,
                    candidate_ids=(entity.entity_id,),
                ),
            ),
        )
    relevant_source_ids = set(entity.source_ids) | set(selection_policy.source_ids)
    freshness = repository.freshness_for_source_ids(
        relevant_source_ids,
        max_source_evidence_age_days=policy.max_source_evidence_age_days,
    )
    if freshness is FreshnessClass.STALE:
        return _stale_evidence_failure(role, resolution, repository, freshness)
    effective_cap = policy.effective_group_cap(selection_policy.cap)
    if len(selection_policy.airport_ids) > effective_cap:
        return GroundedEndpointResult(
            role=role,  # type: ignore[arg-type]
            snapshot_id=repository.snapshot_id,
            freshness=freshness,
            resolution=resolution,
            issues=(
                PlanningIssue(
                    code=PlanningIssueCode.SELECTION_POLICY_CAP_EXCEEDED,
                    message="selection policy exceeds the configured automatic-airport cap",
                    snapshot_id=repository.snapshot_id,
                    location_value=resolution.location.value,
                    candidate_ids=(selection_policy.policy_id,),
                ),
            ),
        )
    selected: list[SelectedAirport] = []
    for airport_id in selection_policy.airport_ids:
        airport = repository.airport(airport_id)
        relation = repository.relation_for(entity.entity_id, airport_id)
        if airport is None or relation is None:  # defensive: snapshot validation rejects this.
            return _missing_airport(role, resolution, repository, freshness)
        relevant_source_ids.update(airport.source_ids)
        relevant_source_ids.update(relation.source_ids)
        selected.append(
            SelectedAirport(
                airport_id=airport.airport_id,
                airport_iata=airport.iata,
                airport_evidence_source_ids=airport.source_ids,
                relation_id=relation.relation_id,
                relation_evidence_source_ids=relation.source_ids,
                selection_policy_id=selection_policy.policy_id,
                selection_policy_evidence_source_ids=selection_policy.source_ids,
            )
        )
    freshness = repository.freshness_for_source_ids(
        relevant_source_ids,
        max_source_evidence_age_days=policy.max_source_evidence_age_days,
    )
    if freshness is FreshnessClass.STALE:
        return _stale_evidence_failure(role, resolution, repository, freshness)
    return GroundedEndpointResult(
        role=role,  # type: ignore[arg-type]
        snapshot_id=repository.snapshot_id,
        freshness=freshness,
        resolution=resolution,
        selection=AirportSelection(
            kind=AirportSelectionKind.GEOGRAPHIC_GROUP,
            resolved_location=resolution,
            airports=tuple(selected),
        ),
    )


def _select_single_airport(airport: Airport) -> SelectedAirport:
    return SelectedAirport(
        airport_id=airport.airport_id,
        airport_iata=airport.iata,
        airport_evidence_source_ids=airport.source_ids,
    )


def _missing_airport(
    role: str,
    resolution: ResolvedLocation,
    repository: KnowledgeRepository,
    freshness: FreshnessClass,
) -> GroundedEndpointResult:
    return GroundedEndpointResult(
        role=role,  # type: ignore[arg-type]
        snapshot_id=repository.snapshot_id,
        freshness=freshness,
        resolution=ResolvedLocation(
            location=resolution.location,
            status=LocationResolutionStatus.EVIDENCE_FAILURE,
            normalized_alias=resolution.normalized_alias,
            candidate_ids=resolution.candidate_ids,
        ),
        issues=(
            PlanningIssue(
                code=PlanningIssueCode.MISSING_AIRPORT_EVIDENCE,
                message="required airport evidence is missing from the snapshot",
                snapshot_id=repository.snapshot_id,
                location_value=resolution.location.value,
                candidate_ids=resolution.candidate_ids,
            ),
        ),
    )


def _stale_evidence_failure(
    role: str,
    resolution: ResolvedLocation,
    repository: KnowledgeRepository,
    freshness: FreshnessClass,
) -> GroundedEndpointResult:
    return GroundedEndpointResult(
        role=role,  # type: ignore[arg-type]
        snapshot_id=repository.snapshot_id,
        freshness=freshness,
        resolution=ResolvedLocation(
            location=resolution.location,
            status=LocationResolutionStatus.EVIDENCE_FAILURE,
            normalized_alias=resolution.normalized_alias,
            candidate_ids=resolution.candidate_ids,
        ),
        issues=(
            PlanningIssue(
                code=PlanningIssueCode.STALE_KNOWLEDGE,
                message="required location knowledge is explicitly marked stale",
                snapshot_id=repository.snapshot_id,
                location_value=resolution.location.value,
                candidate_ids=resolution.candidate_ids,
            ),
        ),
    )


def _issue_for_resolution(
    resolution: ResolvedLocation, repository: KnowledgeRepository
) -> PlanningIssue:
    code = {
        LocationResolutionStatus.UNRESOLVED: PlanningIssueCode.UNRESOLVED_LOCATION,
        LocationResolutionStatus.AMBIGUOUS: PlanningIssueCode.AMBIGUOUS_LOCATION,
        LocationResolutionStatus.KIND_MISMATCH: PlanningIssueCode.LOCATION_KIND_MISMATCH,
        LocationResolutionStatus.EVIDENCE_FAILURE: PlanningIssueCode.MISSING_AIRPORT_EVIDENCE,
    }.get(resolution.status)
    if code is None:
        raise ValueError("a resolved location cannot be converted to an issue")
    return PlanningIssue(
        code=code,
        message=f"location could not be grounded: {resolution.status.value}",
        snapshot_id=repository.snapshot_id,
        location_value=resolution.location.value,
        candidate_ids=resolution.candidate_ids,
    )
