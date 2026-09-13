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


class PlanIdentity(PlanningContractModel):
    session_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    effective_request_digest: str = Field(min_length=1)
    canonicalization_version: str = Field(min_length=1)
    digest_algorithm_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str = Field(min_length=1)
    snapshot_as_of: date
    knowledge_receipt: KnowledgeReceipt
    capability_receipt: CapabilityReceipt
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"knowledge_receipt", "capability_receipt"}
    )


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


class SearchPlanningOutcome(str, Enum):
    PLANNED = "planned"
    REDUCED_COVERAGE = "reduced_coverage"
    UNPLANNABLE = "unplannable"
    EVIDENCE_FAILURE = "evidence_failure"


class SearchPlanningIssueCode(str, Enum):
    MISSING_ORIGIN = "missing_origin"
    MISSING_DESTINATION = "missing_destination"
    MISSING_TRAVELERS = "missing_travelers"
    MISSING_DEPARTURE_WINDOW = "missing_departure_window"
    CORE_FIELD_UNKNOWN = "core_field_unknown"
    ACTIVE_CONFLICT = "active_conflict"
    AWARD_MODE_REQUIRED = "award_mode_required"
    REQUEST_DIGEST_MISMATCH = "request_digest_mismatch"
    INPUT_WINDOW_EXCEEDS_BUDGET = "input_window_exceeds_budget"
    ENDPOINT_PAIR_BUDGET_EXCEEDED = "endpoint_pair_budget_exceeded"
    TOTAL_SEARCH_ITEM_BUDGET_EXCEEDED = "total_search_item_budget_exceeded"
    INVALID_HARD_CONSTRAINT = "invalid_hard_constraint"
    INVALID_FILTER_OBLIGATION = "invalid_filter_obligation"
    CAPABILITY_EVIDENCE_FAILURE = "capability_evidence_failure"
    NONBLOCKING_UNKNOWN = "nonblocking_unknown"
    REPOSITIONING_POLICY_NOT_CONSUMED = "repositioning_policy_not_consumed"
    PLANNER_CONTRACT_FAILURE = "planner_contract_failure"


class SearchPlanningIssue(PlanningContractModel):
    code: SearchPlanningIssueCode
    message: str = Field(min_length=1)
    field: str | None = None
    preserved_value: str | None = None
    category: PlanningIssueCategory | None = None

    @model_validator(mode="after")
    def validate_category(self) -> SearchPlanningIssue:
        expected = {
            SearchPlanningIssueCode.MISSING_ORIGIN: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.MISSING_DESTINATION: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.MISSING_TRAVELERS: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.MISSING_DEPARTURE_WINDOW: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.CORE_FIELD_UNKNOWN: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.ACTIVE_CONFLICT: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.AWARD_MODE_REQUIRED: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.REQUEST_DIGEST_MISMATCH: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.INVALID_HARD_CONSTRAINT: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.INVALID_FILTER_OBLIGATION: PlanningIssueCategory.INPUT,
            SearchPlanningIssueCode.INPUT_WINDOW_EXCEEDS_BUDGET: PlanningIssueCategory.COVERAGE,
            SearchPlanningIssueCode.ENDPOINT_PAIR_BUDGET_EXCEEDED: PlanningIssueCategory.COVERAGE,
            SearchPlanningIssueCode.TOTAL_SEARCH_ITEM_BUDGET_EXCEEDED: PlanningIssueCategory.COVERAGE,
            SearchPlanningIssueCode.CAPABILITY_EVIDENCE_FAILURE: PlanningIssueCategory.EVIDENCE,
            SearchPlanningIssueCode.PLANNER_CONTRACT_FAILURE: PlanningIssueCategory.EVIDENCE,
            SearchPlanningIssueCode.NONBLOCKING_UNKNOWN: PlanningIssueCategory.OBSERVATION,
            SearchPlanningIssueCode.REPOSITIONING_POLICY_NOT_CONSUMED: PlanningIssueCategory.OBSERVATION,
        }[self.code]
        if self.category is None:
            object.__setattr__(self, "category", expected)
        elif self.category is not expected:
            raise ValueError(
                f"search planning issue {self.code.value} must have category {expected.value}"
            )
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
    """A provider-neutral, capability-approved future filter obligation."""

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

    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"available_edge_evidence"}
    )

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
    component_payment_modes: tuple[ComponentPaymentMode, ...] = Field(
        min_length=2, max_length=2
    )

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


class SearchPlan(PlanningContractModel):
    identity: PlanIdentity
    capability_id: str = Field(min_length=1)
    capability_version: str = Field(min_length=1)
    location_results: tuple[GroundedEndpointResult, ...] = Field(min_length=1)
    endpoint_probes: tuple[EndpointProbe, ...] = Field(min_length=1)
    award_search_items: tuple[AwardSearchItem, ...] = Field(min_length=1)
    explicit_path_hypotheses: tuple[ExplicitPathHypothesis, ...] = ()
    manual_cash_enabled: bool = False
    payment_patterns: tuple[PaymentPattern, ...] = ()
    manual_cash_check_templates: tuple[ManualCashCheckTemplate, ...] = ()
    path_exploration_receipts: tuple[PathExplorationReceipt, ...] = ()
    deferred_constraints: tuple[DeferredConstraintObligation, ...] = ()
    nonblocking_issues: tuple[SearchPlanningIssue, ...] = ()
    repositioning_policy_receipt: RepositioningPolicyReceipt
    budget_receipts: tuple[BudgetReceipt, ...] = Field(min_length=2)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "identity",
            "location_results",
            "endpoint_probes",
            "award_search_items",
            "explicit_path_hypotheses",
            "payment_patterns",
            "manual_cash_check_templates",
            "path_exploration_receipts",
            "deferred_constraints",
            "nonblocking_issues",
            "repositioning_policy_receipt",
            "budget_receipts",
        }
    )

    @model_validator(mode="after")
    def validate_search_links(self) -> SearchPlan:
        if self.capability_id != self.identity.capability_receipt.capability_id:
            raise ValueError("plan capability ID must match its capability receipt")
        if self.capability_version != self.identity.capability_receipt.capability_version:
            raise ValueError("plan capability version must match its capability receipt")
        if self.identity.snapshot_id != self.identity.knowledge_receipt.snapshot_id:
            raise ValueError("plan snapshot ID must match its knowledge receipt")
        if self.identity.snapshot_as_of != self.identity.knowledge_receipt.snapshot_as_of:
            raise ValueError("plan snapshot as-of must match its knowledge receipt")
        probe_ids = tuple(probe.probe_id for probe in self.endpoint_probes)
        probe_pairs = tuple(
            (probe.origin_endpoint.airport_id, probe.destination_endpoint.airport_id)
            for probe in self.endpoint_probes
        )
        endpoint_items = tuple(
            item for item in self.award_search_items if item.scope is SearchScope.ENDPOINT_MARKET
        )
        item_probe_ids = tuple(item.probe_id for item in endpoint_items)
        if len(probe_ids) != len(set(probe_ids)):
            raise ValueError("endpoint probe IDs must be unique")
        if len(probe_pairs) != len(set(probe_pairs)):
            raise ValueError("endpoint probe airport pairs must be unique")
        global_requested_cabins = self.endpoint_probes[0].requested_cabins
        global_traveler_count = self.endpoint_probes[0].traveler_count
        if any(
            probe.requested_cabins != global_requested_cabins
            or probe.traveler_count != global_traveler_count
            for probe in self.endpoint_probes
        ):
            raise ValueError(
                "endpoint probes must agree on requested cabins and traveler count"
            )
        if any(probe_id is None for probe_id in item_probe_ids):
            raise ValueError("endpoint award items must link to an endpoint probe")
        if len(item_probe_ids) != len(set(item_probe_ids)):
            raise ValueError("award item probe links must be unique in endpoint planning")
        if set(item_probe_ids) != set(probe_ids):
            raise ValueError("each endpoint probe requires exactly one atomic award search item")
        probe_by_id = {probe.probe_id: probe for probe in self.endpoint_probes}
        for item in endpoint_items:
            assert item.probe_id is not None
            probe = probe_by_id.get(item.probe_id)
            if probe is None:
                raise ValueError("endpoint award item must reference an existing endpoint probe")
            if (
                item.origin_airport_fact_id != probe.origin_endpoint.airport_id
                or item.destination_airport_fact_id != probe.destination_endpoint.airport_id
                or item.date_envelope != probe.date_envelope
                or item.requested_cabins != probe.requested_cabins
            ):
                raise ValueError(
                    "endpoint award item must match its linked probe endpoints, dates, and cabins"
                )
            seat_obligations = tuple(
                obligation
                for obligation in item.result_validation_obligations
                if obligation.kind is ResultValidationKind.MINIMUM_AWARD_SEATS
            )
            if len(seat_obligations) != 1 or seat_obligations[0].minimum_seats != probe.traveler_count:
                raise ValueError(
                    "endpoint award item minimum-seat obligation must match its linked probe"
                )
        for item in self.award_search_items:
            if item.requested_cabins != global_requested_cabins:
                raise ValueError(
                    "every award search item must preserve the global requested cabins"
                )
            seat_obligations = tuple(
                obligation
                for obligation in item.result_validation_obligations
                if obligation.kind is ResultValidationKind.MINIMUM_AWARD_SEATS
            )
            if (
                len(seat_obligations) != 1
                or seat_obligations[0].minimum_seats != global_traveler_count
            ):
                raise ValueError(
                    "every award search item must have exactly one matching minimum-seat obligation"
                )
        item_ids = {item.item_id for item in self.award_search_items}
        if len(item_ids) != len(self.award_search_items):
            raise ValueError("award search item IDs must be unique")
        hypothesis_ids = tuple(path.hypothesis_id for path in self.explicit_path_hypotheses)
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise ValueError("explicit path hypothesis IDs must be unique")
        path_semantic_keys = tuple(
            (
                path.requested_origin_endpoint.airport_id,
                path.intermediate_airport_fact_id,
                path.requested_destination_endpoint.airport_id,
                tuple(
                    (
                        component.route_edge_id,
                        component.origin_endpoint.airport_id,
                        component.destination_endpoint.airport_id,
                        component.date_envelope.start,
                        component.date_envelope.end,
                    )
                    for component in path.components
                ),
            )
            for path in self.explicit_path_hypotheses
        )
        if len(path_semantic_keys) != len(set(path_semantic_keys)):
            raise ValueError("explicit paths must be semantically deduplicated before payment annotation")
        component_ids: list[str] = []
        item_by_id = {item.item_id: item for item in self.award_search_items}
        knowledge_source_ids = set(self.identity.knowledge_receipt.source_ids)
        edge_evidence_by_id: dict[str, RouteEdgeEvidenceReceipt] = {}
        for receipt in self.path_exploration_receipts:
            for available_edge in receipt.available_edge_evidence:
                if not set(available_edge.route_evidence_source_ids).issubset(
                    knowledge_source_ids
                ):
                    raise ValueError(
                        "route evidence source IDs must be present in the knowledge receipt"
                    )
                prior = edge_evidence_by_id.get(available_edge.edge_id)
                if prior is not None and prior != available_edge:
                    raise ValueError("a route edge ID cannot bind conflicting evidence records")
                edge_evidence_by_id[available_edge.edge_id] = available_edge
        for path in self.explicit_path_hypotheses:
            for component in path.components:
                component_ids.append(component.component_id)
                if component.award_search_item_id not in item_ids:
                    raise ValueError(
                        "path component must reference a materialized award search item"
                    )
                item = item_by_id[component.award_search_item_id]
                if (
                    item.scope is not SearchScope.EXPLICIT_PHYSICAL_COMPONENT
                    or item.probe_id is not None
                ):
                    raise ValueError(
                        "path component must link to a probe-free physical-component item"
                    )
                if (
                    item.origin_airport_fact_id != component.origin_endpoint.airport_id
                    or item.destination_airport_fact_id != component.destination_endpoint.airport_id
                    or item.date_envelope != component.date_envelope
                ):
                    raise ValueError(
                        "component item must exactly match its physical scope and envelope"
                    )
                if not set(component.route_evidence_source_ids).issubset(knowledge_source_ids):
                    raise ValueError(
                        "component route evidence source IDs must be present in the knowledge receipt"
                    )
                bound_edge_evidence = edge_evidence_by_id.get(component.route_edge_id)
                if bound_edge_evidence is None:
                    raise ValueError(
                        "path component must reference route evidence available in exploration receipts"
                    )
                if (
                    bound_edge_evidence.origin_airport_fact_id
                    != component.origin_endpoint.airport_id
                    or bound_edge_evidence.destination_airport_fact_id
                    != component.destination_endpoint.airport_id
                    or bound_edge_evidence.route_evidence_source_ids
                    != component.route_evidence_source_ids
                    or bound_edge_evidence.route_evidence_kind != component.route_evidence_kind
                    or bound_edge_evidence.route_date_applicability
                    != component.route_date_applicability
                    or bound_edge_evidence.route_applicable_start
                    != component.route_applicable_start
                    or bound_edge_evidence.route_applicable_end != component.route_applicable_end
                ):
                    raise ValueError(
                        "path component must match the bound directed route evidence"
                    )
                if not any(
                    filter_.kind is FilterObligationKind.DIRECT_FLIGHT_AVAILABLE
                    and filter_.origin == "planner_structure"
                    and filter_.values == ("true",)
                    for filter_ in item.filter_obligations
                ):
                    raise ValueError(
                        "physical component item requires a structural direct-flight filter"
                    )
                if not any(
                    obligation.kind is ResultValidationKind.EXACT_PHYSICAL_COMPONENT_STRUCTURE
                    and obligation.expected_origin_airport_fact_id
                    == component.origin_endpoint.airport_id
                    and obligation.expected_destination_airport_fact_id
                    == component.destination_endpoint.airport_id
                    for obligation in item.result_validation_obligations
                ):
                    raise ValueError(
                        "physical component item requires exact endpoint structure validation"
                    )
        pattern_ids = tuple(pattern.pattern_id for pattern in self.payment_patterns)
        if len(pattern_ids) != len(set(pattern_ids)):
            raise ValueError("payment pattern IDs must be unique")
        patterns_by_hypothesis: dict[str, list[PaymentPattern]] = {
            path.hypothesis_id: [] for path in self.explicit_path_hypotheses
        }
        for pattern in self.payment_patterns:
            if pattern.hypothesis_id not in patterns_by_hypothesis:
                raise ValueError("payment pattern must reference an explicit path hypothesis")
            patterns_by_hypothesis[pattern.hypothesis_id].append(pattern)
        expected_modes = {
            (ComponentPaymentMode.AWARD, ComponentPaymentMode.AWARD),
            *(
                {
                    (ComponentPaymentMode.AWARD, ComponentPaymentMode.MANUAL_CASH),
                    (ComponentPaymentMode.MANUAL_CASH, ComponentPaymentMode.AWARD),
                }
                if self.manual_cash_enabled
                else set()
            ),
        }
        patterns_by_id = {pattern.pattern_id: pattern for pattern in self.payment_patterns}
        for patterns in patterns_by_hypothesis.values():
            observed_modes = {pattern.component_payment_modes for pattern in patterns}
            if len(patterns) != len(observed_modes) or observed_modes != expected_modes:
                raise ValueError(
                    "each explicit path requires exactly the payment patterns allowed by the request"
                )
        template_ids = tuple(template.template_id for template in self.manual_cash_check_templates)
        if len(template_ids) != len(set(template_ids)):
            raise ValueError("manual cash-check template IDs must be unique")
        components_by_id = {
            component.component_id: component
            for path in self.explicit_path_hypotheses
            for component in path.components
        }
        templates_by_pattern: dict[str, list[ManualCashCheckTemplate]] = {}
        for template in self.manual_cash_check_templates:
            template_pattern = patterns_by_id.get(template.payment_pattern_id)
            if template_pattern is None:
                raise ValueError("manual cash-check template must reference a payment pattern")
            if template.hypothesis_id != template_pattern.hypothesis_id:
                raise ValueError("manual cash-check template must match its pattern hypothesis")
            manual_indexes = tuple(
                index
                for index, mode in enumerate(template_pattern.component_payment_modes, start=1)
                if mode is ComponentPaymentMode.MANUAL_CASH
            )
            if len(manual_indexes) != 1 or template.manual_component_index != manual_indexes[0]:
                raise ValueError("manual cash-check template must bind the pattern's only cash component")
            manual_component = components_by_id.get(template.manual_component_id)
            if (
                manual_component is None
                or manual_component.component_index != template.manual_component_index
            ):
                raise ValueError("manual cash-check template must reference its explicit component")
            path = next(
                item
                for item in self.explicit_path_hypotheses
                if item.hypothesis_id == template.hypothesis_id
            )
            if manual_component not in path.components:
                raise ValueError("manual cash-check component must belong to its path hypothesis")
            if (
                template.manual_component_award_search_item_id is not None
                and template.manual_component_award_search_item_id
                != manual_component.award_search_item_id
            ):
                raise ValueError(
                    "manual cash-check template's optional component item must match its path"
                )
            award_index = 1 if template.manual_component_index == 2 else 2
            award_component = path.components[award_index - 1]
            award_item = item_by_id.get(template.relevant_award_search_item_id)
            if award_item is None or award_item.item_id != award_component.award_search_item_id:
                raise ValueError(
                    "manual cash-check template must activate from its path's other award item"
                )
            if (
                template.requested_cabins != global_requested_cabins
                or template.traveler_count != global_traveler_count
            ):
                raise ValueError(
                    "manual cash-check template must preserve global cabin and traveler requirements"
                )
            if template.requested_cabins != award_item.requested_cabins:
                raise ValueError("manual cash-check template must preserve award cabin requirements")
            seat_obligations = tuple(
                obligation
                for obligation in award_item.result_validation_obligations
                if obligation.kind is ResultValidationKind.MINIMUM_AWARD_SEATS
            )
            if (
                len(seat_obligations) != 1
                or seat_obligations[0].minimum_seats != global_traveler_count
            ):
                raise ValueError("manual cash-check template must preserve traveler requirements")
            expected_temporal_kind = (
                ManualCashTemporalValidationKind.FIRST_COMPONENT_WITHIN_ORIGINAL_WINDOW
                if template.manual_component_index == 1
                else ManualCashTemporalValidationKind.LATER_COMPONENT_REQUIRES_ASSEMBLED_JOURNEY_VALIDATION
            )
            if template.temporal_validation_kind is not expected_temporal_kind:
                raise ValueError(
                    "manual cash-check template must carry the component-specific temporal obligation"
                )
            if template.manual_component_index == 1 and (
                manual_component.temporal_derivation.start_offset_days != 0
                or manual_component.temporal_derivation.end_offset_days != 0
            ):
                raise ValueError(
                    "cash-first manual component must preserve the original departure window"
                )
            templates_by_pattern.setdefault(template.payment_pattern_id, []).append(template)
        hybrid_pattern_ids = {
            pattern.pattern_id
            for pattern in self.payment_patterns
            if ComponentPaymentMode.MANUAL_CASH in pattern.component_payment_modes
        }
        if set(templates_by_pattern) != hybrid_pattern_ids or any(
            len(templates) != 1 for templates in templates_by_pattern.values()
        ):
            raise ValueError(
                "each hybrid payment pattern requires exactly one dormant manual cash-check template"
            )
        all_ids = (
            *probe_ids,
            *(item.item_id for item in self.award_search_items),
            *hypothesis_ids,
            *component_ids,
            *pattern_ids,
            *template_ids,
        )
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("probe, item, hypothesis, and component IDs must be globally unique")
        receipt_pairs = tuple(
            (receipt.origin_airport_fact_id, receipt.destination_airport_fact_id)
            for receipt in self.path_exploration_receipts
        )
        if len(receipt_pairs) != len(set(receipt_pairs)):
            raise ValueError("path exploration receipts must be unique per endpoint pair")
        if set(receipt_pairs) != set(probe_pairs):
            raise ValueError(
                "path exploration receipts must cover exactly the endpoint probe airport pairs"
            )
        explicit_item_ids = {
            item.item_id
            for item in self.award_search_items
            if item.scope is SearchScope.EXPLICIT_PHYSICAL_COMPONENT
        }
        referenced_item_ids = {
            component.award_search_item_id
            for path in self.explicit_path_hypotheses
            for component in path.components
        }
        if explicit_item_ids != referenced_item_ids:
            raise ValueError(
                "every physical-component award item must be linked by an explicit path component"
            )
        budget_kinds = {receipt.kind for receipt in self.budget_receipts}
        required_budget_kinds = {
            BudgetKind.INPUT_WINDOW_DAYS,
            BudgetKind.ENDPOINT_PAIR_COUNT,
            BudgetKind.PATH_CANDIDATE_COUNT,
            BudgetKind.PATH_HYPOTHESIS_COUNT,
            BudgetKind.TOTAL_AWARD_SEARCH_ITEM_COUNT,
            BudgetKind.DATE_EXPANDED_WORK_DAYS,
        }
        if (
            len(self.budget_receipts) != len(required_budget_kinds)
            or budget_kinds != required_budget_kinds
        ):
            raise ValueError(
                "search plan requires exactly one receipt for each required budget kind"
            )
        if any(receipt.disposition == "exceeded" for receipt in self.budget_receipts):
            raise ValueError("successful search plans cannot contain exceeded budget receipts")
        budget_by_kind = {receipt.kind: receipt for receipt in self.budget_receipts}
        endpoint_window = (
            self.endpoint_probes[0].date_envelope.start,
            self.endpoint_probes[0].date_envelope.end,
        )
        if any(
            (probe.date_envelope.start, probe.date_envelope.end) != endpoint_window
            for probe in self.endpoint_probes
        ):
            raise ValueError("endpoint probes must preserve one common input date window")
        expected_budget_observed = {
            BudgetKind.INPUT_WINDOW_DAYS: (endpoint_window[1] - endpoint_window[0]).days + 1,
            BudgetKind.ENDPOINT_PAIR_COUNT: len(probe_pairs),
            BudgetKind.PATH_CANDIDATE_COUNT: sum(
                receipt.candidate_count for receipt in self.path_exploration_receipts
            ),
            BudgetKind.PATH_HYPOTHESIS_COUNT: len(self.explicit_path_hypotheses),
            BudgetKind.TOTAL_AWARD_SEARCH_ITEM_COUNT: len(self.award_search_items),
            BudgetKind.DATE_EXPANDED_WORK_DAYS: sum(
                (item.date_envelope.end - item.date_envelope.start).days + 1
                for item in self.award_search_items
            ),
        }
        if any(
            budget_by_kind[kind].observed != observed
            for kind, observed in expected_budget_observed.items()
        ):
            raise ValueError("budget receipt observed values must match plan-derived metrics")
        if budget_by_kind[BudgetKind.PATH_CANDIDATE_COUNT].observed < len(
            self.explicit_path_hypotheses
        ):
            raise ValueError("path candidate count cannot be below materialized hypotheses")
        return self


class SearchPlanningResult(PlanningContractModel):
    outcome: SearchPlanningOutcome
    plan: SearchPlan | None = None
    issues: tuple[SearchPlanningIssue | PlanningIssue, ...] = ()
    exclusions: tuple[str, ...] = ()
    budget_receipts: tuple[BudgetReceipt, ...] = ()
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"plan", "issues"})

    @model_validator(mode="after")
    def validate_result_shape(self) -> SearchPlanningResult:
        if self.outcome is SearchPlanningOutcome.PLANNED:
            if self.plan is None:
                raise ValueError("planned outcome requires a plan")
            if self.issues or self.exclusions:
                raise ValueError("planned outcome cannot carry issues or exclusions")
        elif self.outcome is SearchPlanningOutcome.REDUCED_COVERAGE:
            if self.plan is None or not self.exclusions:
                raise ValueError("reduced-coverage outcome requires a plan and exclusions")
            if self.issues:
                raise ValueError("reduced-coverage outcome cannot carry blocking issues")
        elif self.outcome in {
            SearchPlanningOutcome.UNPLANNABLE,
            SearchPlanningOutcome.EVIDENCE_FAILURE,
        }:
            if self.plan is not None or not self.issues or self.exclusions:
                raise ValueError("failure outcomes require issues only and no plan or exclusions")
            categories = {issue.category for issue in self.issues}
            if self.outcome is SearchPlanningOutcome.UNPLANNABLE and not categories.issubset(
                {PlanningIssueCategory.INPUT, PlanningIssueCategory.COVERAGE}
            ):
                raise ValueError("unplannable outcomes may contain only input or coverage issues")
            if self.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE:
                allowed_categories = {
                    PlanningIssueCategory.EVIDENCE,
                    PlanningIssueCategory.INPUT,
                    PlanningIssueCategory.COVERAGE,
                }
                if PlanningIssueCategory.EVIDENCE not in categories or not categories.issubset(
                    allowed_categories
                ):
                    raise ValueError(
                        "evidence-failure outcomes require at least one evidence issue and "
                        "may include only input or coverage issues alongside it"
                    )
        else:  # pragma: no cover - enum exhaustiveness guard
            raise ValueError("unknown search planning outcome")
        return self
