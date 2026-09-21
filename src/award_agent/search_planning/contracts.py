"""Immutable, provider-neutral contracts for deterministic search planning.

The planner deliberately consumes the clarification boundary as a value.  These
contracts keep its own derived data isolated so that planning cannot mutate a
session ledger through a nested Pydantic object.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from enum import Enum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from award_agent.domain import (
    CabinClass,
    EffectiveRequest,
    FieldProvenance,
    LocationRef,
)


class PlanningContractModel(BaseModel):
    """Frozen model with copy-isolated nested Pydantic inputs and outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def isolate_nested_models(cls, value: object) -> object:
        return _round_trip_nested_models(value)

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)
        if name in super().__getattribute__("_copy_on_read_fields"):
            return deepcopy(value)
        return value


def _round_trip_nested_models(value: object) -> object:
    if isinstance(value, BaseModel):
        return _round_trip_nested_models(value.model_dump(mode="python", round_trip=True))
    if isinstance(value, dict):
        return {key: _round_trip_nested_models(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_round_trip_nested_models(item) for item in value)
    if isinstance(value, list):
        return [_round_trip_nested_models(item) for item in value]
    return value


class PlanningIssueCode(str, Enum):
    UNRESOLVED_LOCATION = "unresolved_location"
    AMBIGUOUS_LOCATION = "ambiguous_location"
    LOCATION_KIND_MISMATCH = "location_kind_mismatch"
    MISSING_AIRPORT_EVIDENCE = "missing_airport_evidence"
    STALE_KNOWLEDGE = "stale_knowledge"
    MISSING_SELECTION_POLICY = "missing_selection_policy"
    SELECTION_POLICY_CAP_EXCEEDED = "selection_policy_cap_exceeded"
    MODEL_AIRPORT_SELECTION_UNAVAILABLE = "model_airport_selection_unavailable"


class PlanningIssueCategory(str, Enum):
    """Stable class used to validate typed planning failure outcomes."""

    INPUT = "input"
    EVIDENCE = "evidence"
    COVERAGE = "coverage"
    OBSERVATION = "observation"


class FreshnessClass(str, Enum):
    """Deterministic assessment of a snapshot against planning policy."""

    CURRENT = "current"
    STALE = "stale"


class PlanningIssue(PlanningContractModel):
    """A stable, non-success-shaped grounding issue."""

    code: PlanningIssueCode
    message: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    location_value: str = Field(min_length=1)
    candidate_ids: tuple[str, ...] = ()
    category: PlanningIssueCategory | None = None

    @model_validator(mode="after")
    def validate_category(self) -> PlanningIssue:
        expected = {
            PlanningIssueCode.UNRESOLVED_LOCATION: PlanningIssueCategory.INPUT,
            PlanningIssueCode.AMBIGUOUS_LOCATION: PlanningIssueCategory.INPUT,
            PlanningIssueCode.LOCATION_KIND_MISMATCH: PlanningIssueCategory.INPUT,
            PlanningIssueCode.MISSING_AIRPORT_EVIDENCE: PlanningIssueCategory.EVIDENCE,
            PlanningIssueCode.STALE_KNOWLEDGE: PlanningIssueCategory.EVIDENCE,
            PlanningIssueCode.MISSING_SELECTION_POLICY: PlanningIssueCategory.EVIDENCE,
            PlanningIssueCode.SELECTION_POLICY_CAP_EXCEEDED: PlanningIssueCategory.EVIDENCE,
            PlanningIssueCode.MODEL_AIRPORT_SELECTION_UNAVAILABLE: PlanningIssueCategory.EVIDENCE,
        }[self.code]
        if self.category is None:
            object.__setattr__(self, "category", expected)
        elif self.category is not expected:
            raise ValueError(
                f"planning issue {self.code.value} must have category {expected.value}"
            )
        return self


class LocationResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    KIND_MISMATCH = "kind_mismatch"
    EVIDENCE_FAILURE = "evidence_failure"


class ResolvedLocation(PlanningContractModel):
    """A location candidate grounded only by a versioned snapshot."""

    location: LocationRef
    status: LocationResolutionStatus
    normalized_alias: str = Field(min_length=1)
    resolved_entity_id: str | None = None
    resolved_airport_id: str | None = None
    evidence_source_ids: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"location"})

    @model_validator(mode="after")
    def validate_shape(self) -> ResolvedLocation:
        if self.status is LocationResolutionStatus.RESOLVED:
            if (self.resolved_entity_id is None) == (self.resolved_airport_id is None):
                raise ValueError("resolved location requires exactly one entity or airport ID")
            if not self.evidence_source_ids:
                raise ValueError("resolved location requires evidence source IDs")
        elif self.resolved_entity_id is not None or self.resolved_airport_id is not None:
            raise ValueError("unresolved location states cannot contain a resolved ID")
        return self


class AirportSelectionKind(str, Enum):
    EXPLICIT_IATA = "explicit_iata"
    NAMED_AIRPORT = "named_airport"
    GEOGRAPHIC_GROUP = "geographic_group"
    MODEL_PROPOSED = "model_proposed"
    REVIEWED_MAPPING = "reviewed_mapping"


class SelectedAirport(PlanningContractModel):
    airport_id: str = Field(min_length=1)
    airport_iata: str = Field(pattern=r"^[A-Z]{3}$")
    airport_evidence_source_ids: tuple[str, ...] = Field(min_length=1)
    relation_id: str | None = None
    relation_evidence_source_ids: tuple[str, ...] = ()
    selection_policy_id: str | None = None
    selection_policy_evidence_source_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_group_evidence(self) -> SelectedAirport:
        grouped = self.relation_id is not None or self.selection_policy_id is not None
        if grouped and (self.relation_id is None or self.selection_policy_id is None):
            raise ValueError("geographic airport selection requires relation and policy IDs")
        if grouped and (
            not self.relation_evidence_source_ids or not self.selection_policy_evidence_source_ids
        ):
            raise ValueError("geographic airport selection requires relation and policy evidence")
        return self


class AirportSelection(PlanningContractModel):
    kind: AirportSelectionKind
    resolved_location: ResolvedLocation
    airports: tuple[SelectedAirport, ...] = Field(min_length=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"resolved_location", "airports"})


EndpointRole = Literal["origin", "destination"]


class GroundedEndpointResult(PlanningContractModel):
    """The increment-one endpoint result; it intentionally has no search item."""

    role: EndpointRole
    snapshot_id: str = Field(min_length=1)
    freshness: FreshnessClass
    resolution: ResolvedLocation
    selection: AirportSelection | None = None
    issues: tuple[PlanningIssue, ...] = ()
    field_provenance: FieldProvenance | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"resolution", "selection", "issues", "field_provenance"}
    )

    @model_validator(mode="after")
    def validate_outcome(self) -> GroundedEndpointResult:
        if self.selection is not None:
            if self.resolution.status is not LocationResolutionStatus.RESOLVED or self.issues:
                raise ValueError("successful endpoint grounding cannot retain issues")
        elif not self.issues:
            raise ValueError("unsuccessful endpoint grounding requires a typed issue")
        return self


# The contracts below deliberately describe planning intent rather than a
# Seats.aero request.  An adapter is a later boundary and is the only code
# permitted to know provider payload names.


class PlanningSource(PlanningContractModel):
    """Caller-owned identity for a materialized EffectiveRequest."""

    session_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    expected_effective_request_digest: str | None = Field(default=None, min_length=1)


class PlanningInputEnvelope(PlanningContractModel):
    source: PlanningSource
    effective_request: EffectiveRequest
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"source", "effective_request"})



class KnowledgeReceipt(PlanningContractModel):
    """Canonical identity of the exact reviewed knowledge snapshot used."""

    snapshot_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    snapshot_as_of: date
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def canonical_sources(self) -> KnowledgeReceipt:
        if self.source_ids != tuple(sorted(set(self.source_ids))) or any(
            not source_id for source_id in self.source_ids
        ):
            raise ValueError("knowledge receipt source IDs must be sorted, unique, and nonempty")
        return self


class CatalogSourceArtifactReceipt(PlanningContractModel):
    """One immutable source-artifact receipt bound into a catalog release."""

    artifact_name: str = Field(min_length=1)
    bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CatalogKnowledgeReceipt(PlanningContractModel):
    """Identity of one validated, read-only SQLite knowledge release.

    This intentionally is not a JSON-snapshot receipt with optional blank
    fields.  A catalog-backed plan says which release and which immutable
    artifacts it actually read.
    """

    release_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    source_date: date
    logical_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    database_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_bundle_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_artifacts: tuple[CatalogSourceArtifactReceipt, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def canonical_source_artifacts(self) -> CatalogKnowledgeReceipt:
        names = tuple(item.artifact_name for item in self.source_artifacts)
        if names != tuple(sorted(set(names))):
            raise ValueError("catalog source artifacts must be sorted and unique")
        return self


class CapabilitySourceReceipt(PlanningContractModel):
    source_id: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CapabilityReceipt(PlanningContractModel):
    """Canonical identity and evidence fingerprints for one capability contract."""

    capability_id: str = Field(min_length=1)
    capability_version: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipts: tuple[CapabilitySourceReceipt, ...] = Field(min_length=1)
    caveats: tuple[str, ...] = Field(min_length=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"source_receipts"})

    @model_validator(mode="after")
    def canonical_source_receipts(self) -> CapabilityReceipt:
        ids = tuple(source.source_id for source in self.source_receipts)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("capability receipt source IDs must be sorted and unique")
        if self.caveats != tuple(sorted(set(self.caveats))) or any(
            not item for item in self.caveats
        ):
            raise ValueError("capability receipt caveats must be sorted, unique, and nonempty")
        return self



class SearchScope(str, Enum):
    ENDPOINT_MARKET = "endpoint_market"
    EXPLICIT_PHYSICAL_COMPONENT = "explicit_physical_component"


class DateBasis(str, Enum):
    FIRST_ORIGIN_AIRPORT_LOCAL = "first_origin_airport_local"
    LATER_COMPONENT_ORIGIN_AIRPORT_LOCAL = "later_component_origin_airport_local"


class DateEnvelope(PlanningContractModel):
    start: date
    end: date
    inclusive: Literal[True] = True
    basis: DateBasis
    timezone: str = Field(min_length=1)
    effective_window_precision: str = Field(min_length=1)
    field_provenance: FieldProvenance | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"field_provenance"})

    @model_validator(mode="after")
    def validate_date_order(self) -> DateEnvelope:
        if self.end < self.start:
            raise ValueError("date envelope end precedes start")
        return self


class TemporalDerivation(PlanningContractModel):
    """Pinned, non-schedule temporal derivation for an explicit component."""

    component_index: int = Field(ge=1, le=2)
    origin_airport_fact_id: str = Field(min_length=1)
    basis: DateBasis
    timezone: str = Field(min_length=1)
    start_offset_days: int
    end_offset_days: int
    source_window_start: date
    source_window_end: date
    derived_start: date
    derived_end: date
    note: Literal["not_connection_or_schedule_evidence"] = "not_connection_or_schedule_evidence"

    @model_validator(mode="after")
    def validate_derivation(self) -> TemporalDerivation:
        if self.source_window_end < self.source_window_start:
            raise ValueError("source departure window end precedes start")
        if self.derived_end < self.derived_start:
            raise ValueError("derived temporal envelope end precedes start")
        if self.component_index == 1:
            if self.basis is not DateBasis.FIRST_ORIGIN_AIRPORT_LOCAL:
                raise ValueError("first component must use the first-origin local date basis")
            if self.start_offset_days != 0 or self.end_offset_days != 0:
                raise ValueError("first component must preserve the source departure window")
        else:
            if self.basis is not DateBasis.LATER_COMPONENT_ORIGIN_AIRPORT_LOCAL:
                raise ValueError("later component must use its origin-local date basis")
            if self.start_offset_days != -1 or self.end_offset_days != 2:
                raise ValueError("later component must use the v1 -1/+2 exploratory envelope")
        expected_start = self.source_window_start + timedelta(days=self.start_offset_days)
        expected_end = self.source_window_end + timedelta(days=self.end_offset_days)
        if (self.derived_start, self.derived_end) != (expected_start, expected_end):
            raise ValueError("derived temporal envelope must equal its source window plus offsets")
        return self


class FilterObligationKind(str, Enum):
    CABIN_AVAILABLE_IN = "cabin_available_in"
    DIRECT_FLIGHT_AVAILABLE = "direct_flight_available"
    CARRIER_INVOLVEMENT_MATCH = "carrier_involvement_match"
    REDEMPTION_PROGRAM_IN = "redemption_program_in"
    MIN_REPORTED_CABIN_DISTANCE_PERCENT = "min_reported_cabin_distance_percent"


class FilterObligation(PlanningContractModel):
    """Provider-neutral required query semantics or deferred structural validation."""

    kind: FilterObligationKind
    values: tuple[str, ...] = Field(min_length=1)
    origin: Literal["user_requirement", "planner_structure"]
    field_provenance: FieldProvenance | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"field_provenance"})

    @model_validator(mode="before")
    @classmethod
    def canonicalize_values(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        copied = dict(value)
        raw_values = copied.get("values")
        if isinstance(raw_values, (list, tuple)):
            values = [str(raw).strip().casefold() for raw in raw_values]
            raw_kind = copied.get("kind")
            kind = getattr(raw_kind, "value", raw_kind)
            if kind == FilterObligationKind.MIN_REPORTED_CABIN_DISTANCE_PERCENT.value:
                values = [str(int(raw)) if raw.isdigit() else raw for raw in values]
            copied["values"] = tuple(sorted(set(values)))
        return copied

    @model_validator(mode="after")
    def validate_operands_and_origin(self) -> FilterObligation:
        if self.origin == "user_requirement" and self.field_provenance is None:
            raise ValueError("user requirement filters require field provenance")
        if self.origin == "planner_structure" and self.field_provenance is not None:
            raise ValueError("planner-structure filters cannot claim user field provenance")
        if (
            self.origin == "planner_structure"
            and self.kind is not FilterObligationKind.DIRECT_FLIGHT_AVAILABLE
        ):
            raise ValueError("only direct-flight filters may originate from planner structure")
        if self.kind is FilterObligationKind.CABIN_AVAILABLE_IN:
            if self.origin != "user_requirement" or any(
                value not in {cabin.value for cabin in CabinClass} for value in self.values
            ):
                raise ValueError("cabin availability requires known cabin values from the user")
        elif self.kind is FilterObligationKind.DIRECT_FLIGHT_AVAILABLE:
            if self.origin != "planner_structure" or self.values != ("true",):
                raise ValueError(
                    "direct-flight structure filter requires the canonical true operand"
                )
        elif self.kind is FilterObligationKind.MIN_REPORTED_CABIN_DISTANCE_PERCENT:
            if (
                self.origin != "user_requirement"
                or self.field_provenance is None
                or len(self.values) != 1
                or not self.values[0].isdigit()
                or not 0 <= int(self.values[0]) <= 100
            ):
                raise ValueError(
                    "minimum cabin-distance percent must be one integer from 0 through 100"
                )
        elif self.kind in {
            FilterObligationKind.CARRIER_INVOLVEMENT_MATCH,
            FilterObligationKind.REDEMPTION_PROGRAM_IN,
        } and (
            self.origin != "user_requirement" or any(not value.strip() for value in self.values)
        ):
            raise ValueError("provider identifiers require nonempty user-supplied operands")
        return self


class ResultValidationKind(str, Enum):
    MINIMUM_AWARD_SEATS = "minimum_award_seats"
    EXACT_PHYSICAL_COMPONENT_STRUCTURE = "exact_physical_component_structure"


class ResultValidationObligation(PlanningContractModel):
    kind: ResultValidationKind
    minimum_seats: int | None = Field(default=None, ge=1)
    expected_origin_airport_fact_id: str | None = None
    expected_destination_airport_fact_id: str | None = None
    field_provenance: FieldProvenance | None = None
    responsible_stage: Literal["provider_result_validation"] = "provider_result_validation"
    disposition: Literal["not_verified"] = "not_verified"
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"field_provenance"})

    @model_validator(mode="after")
    def validate_result_validation(self) -> ResultValidationObligation:
        if self.kind is ResultValidationKind.MINIMUM_AWARD_SEATS:
            if self.minimum_seats is None or (
                self.expected_origin_airport_fact_id is not None
                or self.expected_destination_airport_fact_id is not None
            ):
                raise ValueError("seat validation requires only a minimum seat count")
        elif self.kind is ResultValidationKind.EXACT_PHYSICAL_COMPONENT_STRUCTURE and (
            self.minimum_seats is not None
            or not (
                self.expected_origin_airport_fact_id and self.expected_destination_airport_fact_id
            )
        ):
            raise ValueError("physical structure validation requires its exact airport endpoints")
        return self


class RepositioningPolicyReceipt(PlanningContractModel):
    requested_value: bool | None
    decision: Literal["enabled_not_consumed_v1"] = "enabled_not_consumed_v1"
    field_provenance: FieldProvenance | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"field_provenance"})


class BudgetKind(str, Enum):
    INPUT_WINDOW_DAYS = "input_window_days"
    ENDPOINT_PAIR_COUNT = "endpoint_pair_count"
    PATH_CANDIDATE_COUNT = "path_candidate_count"
    PATH_HYPOTHESIS_COUNT = "path_hypothesis_count"
    TOTAL_AWARD_SEARCH_ITEM_COUNT = "total_award_search_item_count"
    DATE_EXPANDED_WORK_DAYS = "date_expanded_work_days"


class BudgetReceipt(PlanningContractModel):
    kind: BudgetKind
    observed: int = Field(ge=0)
    # A zero optional-path budget is meaningful: it explicitly disables
    # optional expansion while preserving endpoint probes.
    limit: int = Field(ge=0)
    disposition: Literal["within_limit", "exceeded"]

    @model_validator(mode="after")
    def validate_disposition(self) -> BudgetReceipt:
        if (self.observed <= self.limit) != (self.disposition == "within_limit"):
            raise ValueError("budget disposition must agree with observed value and limit")
        return self


class RouteEdgeEvidenceReceipt(PlanningContractModel):
    """The route fact bound to a path-exploration receipt.

    Keeping the directed endpoints and applicability alongside the edge ID
    lets a materialized component be validated against the exact evidence
    that was available during bounded exploration.  This remains topology
    evidence only; it is not schedule or availability evidence.
    """

    edge_id: str = Field(min_length=1)
    origin_airport_fact_id: str = Field(min_length=1)
    destination_airport_fact_id: str = Field(min_length=1)
    route_evidence_source_ids: tuple[str, ...] = Field(min_length=1)
    route_evidence_kind: Literal["synthetic_test_fixture", "reviewed_topology"]
    route_date_applicability: Literal["known_inclusive_interval", "unknown"]
    route_applicable_start: date | None = None
    route_applicable_end: date | None = None

    @field_validator("route_evidence_source_ids")
    @classmethod
    def canonicalize_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value)
        if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("route evidence source IDs must be nonempty and unique")
        return tuple(sorted(cleaned))

    @model_validator(mode="after")
    def validate_applicability(self) -> RouteEdgeEvidenceReceipt:
        known_interval = self.route_date_applicability == "known_inclusive_interval"
        if known_interval != (
            self.route_applicable_start is not None and self.route_applicable_end is not None
        ):
            raise ValueError("route applicability must be a complete interval or explicit unknown")
        if (
            self.route_applicable_start is not None
            and self.route_applicable_end is not None
            and self.route_applicable_end < self.route_applicable_start
        ):
            raise ValueError("route applicability end precedes start")
        return self


class PathExplorationReceipt(PlanningContractModel):
    """Bounded outgoing-edge retrieval evidence for one endpoint pair.

    Path expansion is optional, but the planner must make its omitted coverage
    auditable.  This receipt records the exact deterministic retrieval bound
    applied to each requested airport pair without claiming an edge is a
    schedule or availability observation.
    """

    origin_airport_fact_id: str = Field(min_length=1)
    destination_airport_fact_id: str = Field(min_length=1)
    examined_edge_ids: tuple[str, ...] = ()
    candidate_count: int = Field(default=0, ge=0)
    outgoing_edge_limit: int = Field(ge=0, le=20)
    overflow: bool = False
    available_edge_evidence: tuple[RouteEdgeEvidenceReceipt, ...] = ()

    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"available_edge_evidence"})

    @model_validator(mode="after")
    def validate_examined_edges(self) -> PathExplorationReceipt:
        if self.examined_edge_ids != tuple(sorted(set(self.examined_edge_ids))):
            raise ValueError("examined route edge IDs must be sorted and unique")
        if len(self.examined_edge_ids) > self.outgoing_edge_limit:
            raise ValueError("examined route edges cannot exceed the retrieval limit")
        evidence_ids = tuple(item.edge_id for item in self.available_edge_evidence)
        if evidence_ids != tuple(sorted(set(evidence_ids))):
            raise ValueError("available route evidence IDs must be sorted and unique")
        if not set(self.examined_edge_ids).issubset(evidence_ids):
            raise ValueError("every examined route edge must have available edge evidence")
        return self


class DeferredConstraintObligation(PlanningContractModel):
    """A supplied free-text requirement retained without planner interpretation."""

    text: str = Field(min_length=1)
    field_provenance: FieldProvenance | None = None
    provenance_granularity: Literal["field"] = "field"
    disposition: Literal["deferred_after_search"] = "deferred_after_search"
    responsible_stage: Literal["result_or_assembled_journey_validation"] = (
        "result_or_assembled_journey_validation"
    )
    evidence_status: Literal["not_verified"] = "not_verified"
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"field_provenance"})


class EndpointProbe(PlanningContractModel):
    probe_id: str = Field(min_length=1)
    scope: Literal[SearchScope.ENDPOINT_MARKET] = SearchScope.ENDPOINT_MARKET
    origin_endpoint: SelectedAirport
    destination_endpoint: SelectedAirport
    date_envelope: DateEnvelope
    requested_cabins: tuple[CabinClass, ...] = ()
    traveler_count: int = Field(ge=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"origin_endpoint", "destination_endpoint", "date_envelope"}
    )


class ExplicitPathComponent(PlanningContractModel):
    """One evidence-backed physical leg in a planner-generated two-leg path."""

    component_id: str = Field(min_length=1)
    component_index: int = Field(ge=1, le=2)
    origin_endpoint: SelectedAirport
    destination_endpoint: SelectedAirport
    route_edge_id: str = Field(min_length=1)
    route_evidence_source_ids: tuple[str, ...] = Field(min_length=1)
    route_evidence_kind: Literal["synthetic_test_fixture", "reviewed_topology"]
    route_date_applicability: Literal["known_inclusive_interval", "unknown"]
    route_applicable_start: date | None = None
    route_applicable_end: date | None = None
    date_applicability_disclosure: Literal["date_applicability_unknown"] | None = None
    date_envelope: DateEnvelope
    temporal_derivation: TemporalDerivation
    award_search_item_id: str = Field(min_length=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"origin_endpoint", "destination_endpoint", "date_envelope", "temporal_derivation"}
    )

    @field_validator("route_evidence_source_ids")
    @classmethod
    def canonicalize_route_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value)
        if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("route evidence source IDs must be nonempty and unique")
        return tuple(sorted(cleaned))

    @model_validator(mode="after")
    def validate_component_shape(self) -> ExplicitPathComponent:
        if self.temporal_derivation.component_index != self.component_index:
            raise ValueError("component temporal derivation must have matching index")
        if self.temporal_derivation.origin_airport_fact_id != self.origin_endpoint.airport_id:
            raise ValueError("component temporal derivation must use its origin airport")
        if (
            self.date_envelope.start != self.temporal_derivation.derived_start
            or self.date_envelope.end != self.temporal_derivation.derived_end
            or self.date_envelope.basis is not self.temporal_derivation.basis
            or self.date_envelope.timezone != self.temporal_derivation.timezone
        ):
            raise ValueError("component date envelope must exactly match its temporal derivation")
        known_interval = self.route_date_applicability == "known_inclusive_interval"
        if known_interval != (
            self.route_applicable_start is not None and self.route_applicable_end is not None
        ):
            raise ValueError("route applicability must be a complete interval or explicit unknown")
        if known_interval:
            assert self.route_applicable_start is not None
            assert self.route_applicable_end is not None
            if self.route_applicable_end < self.route_applicable_start:
                raise ValueError("route applicability end precedes start")
            if (
                self.route_applicable_start > self.date_envelope.start
                or self.route_applicable_end < self.date_envelope.end
            ):
                raise ValueError(
                    "known route applicability must cover the complete component date envelope"
                )
            if self.date_applicability_disclosure is not None:
                raise ValueError("known route applicability cannot carry unknown-date disclosure")
        elif self.date_applicability_disclosure != "date_applicability_unknown":
            raise ValueError("unknown route applicability requires an explicit disclosure")
        return self


class ExplicitPathHypothesis(PlanningContractModel):
    """A requested endpoint pair preserved through one intermediate airport."""

    hypothesis_id: str = Field(min_length=1)
    requested_origin_endpoint: SelectedAirport
    requested_destination_endpoint: SelectedAirport
    intermediate_airport_fact_id: str = Field(min_length=1)
    components: tuple[ExplicitPathComponent, ...] = Field(min_length=2, max_length=2)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"requested_origin_endpoint", "requested_destination_endpoint", "components"}
    )

    @model_validator(mode="after")
    def validate_connected_directed_path(self) -> ExplicitPathHypothesis:
        first, second = self.components
        if (first.component_index, second.component_index) != (1, 2):
            raise ValueError("explicit path components must be ordered one then two")
        if first.origin_endpoint.airport_id != self.requested_origin_endpoint.airport_id:
            raise ValueError("explicit path must preserve the requested origin")
        if second.destination_endpoint.airport_id != self.requested_destination_endpoint.airport_id:
            raise ValueError("explicit path must preserve the requested destination")
        if (
            first.destination_endpoint.airport_id != self.intermediate_airport_fact_id
            or second.origin_endpoint.airport_id != self.intermediate_airport_fact_id
        ):
            raise ValueError(
                "explicit path components must meet at the declared intermediate airport"
            )
        return self


class AwardSearchItem(PlanningContractModel):
    item_id: str = Field(min_length=1)
    probe_id: str | None = None
    scope: SearchScope = SearchScope.ENDPOINT_MARKET
    origin_airport_fact_id: str = Field(min_length=1)
    destination_airport_fact_id: str = Field(min_length=1)
    date_envelope: DateEnvelope
    automated_mode: Literal["award"] = "award"
    requested_cabins: tuple[CabinClass, ...] = ()
    filter_obligations: tuple[FilterObligation, ...] = ()
    result_validation_obligations: tuple[ResultValidationObligation, ...] = Field(min_length=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"date_envelope", "filter_obligations", "result_validation_obligations"}
    )


class ComponentPaymentMode(str, Enum):
    """How one explicitly planned physical component is paid for.

    ``manual_cash`` is deliberately an annotation, not an executable search
    mode.  There is no cash search item anywhere in this contract.
    """

    AWARD = "award"
    MANUAL_CASH = "manual_cash"


class PaymentPattern(PlanningContractModel):
    """One permitted way to pay for a two-component path hypothesis.

    The components are referenced by order on ``ExplicitPathHypothesis``.
    Keeping the pattern path-level avoids duplicating topology or award search
    items for every payment possibility.
    """

    pattern_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    component_payment_modes: tuple[ComponentPaymentMode, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_award_backed_pattern(self) -> PaymentPattern:
        if not any(mode is ComponentPaymentMode.AWARD for mode in self.component_payment_modes):
            raise ValueError("payment pattern must retain at least one award component")
        return self


class ManualCashTemporalValidationKind(str, Enum):
    """The later validation needed for an unautomated cash dependency."""

    FIRST_COMPONENT_WITHIN_ORIGINAL_WINDOW = "first_component_within_original_window"
    LATER_COMPONENT_REQUIRES_ASSEMBLED_JOURNEY_VALIDATION = (
        "later_component_requires_assembled_journey_validation"
    )


class ManualCashCheckTemplate(PlanningContractModel):
    """A dormant manual cash-check dependency, not a cash flight or query.

    It becomes relevant only if the referenced award item yields an observation
    worth combining with the manually checked component.  Price, availability,
    schedule, and bookability intentionally remain unknown here.
    """

    template_id: str = Field(min_length=1)
    payment_pattern_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    manual_component_id: str = Field(min_length=1)
    manual_component_index: int = Field(ge=1, le=2)
    # A manually paid component normally has no executable search item.  A
    # caller may nevertheless retain the path component's linked item for
    # traceability; when supplied, it must agree with that component.
    manual_component_award_search_item_id: str | None = Field(default=None, min_length=1)
    relevant_award_search_item_id: str = Field(min_length=1)
    traveler_count: int = Field(ge=1)
    requested_cabins: tuple[CabinClass, ...] = ()
    temporal_validation_kind: ManualCashTemporalValidationKind
    temporal_responsible_stage: Literal["manual_cash_check_and_assembled_journey_validation"] = (
        "manual_cash_check_and_assembled_journey_validation"
    )
    activation: Literal["after_relevant_award_observation"] = "after_relevant_award_observation"
    automation: Literal["manual_only"] = "manual_only"
    pricing_status: Literal["unpriced"] = "unpriced"
    verification_status: Literal["not_verified"] = "not_verified"
