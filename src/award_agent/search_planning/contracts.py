"""Immutable, provider-neutral contracts for deterministic search planning.

The planner deliberately consumes the clarification boundary as a value.  These
contracts keep its own derived data isolated so that planning cannot mutate a
session ledger through a nested Pydantic object.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from enum import Enum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    M2A_SELECTION_REQUIRED = "m2a_selection_required"
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
            PlanningIssueCode.M2A_SELECTION_REQUIRED: PlanningIssueCategory.COVERAGE,
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
    MODEL_PROPOSED = "model_proposed"


class SelectedAirport(PlanningContractModel):
    airport_id: str = Field(min_length=1)
    airport_iata: str = Field(pattern=r"^[A-Z]{3}$")
    airport_evidence_source_ids: tuple[str, ...] = Field(min_length=1)


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
    scope: Literal["endpoint_market"] = "endpoint_market"
    origin_endpoint: SelectedAirport
    destination_endpoint: SelectedAirport
    date_envelope: DateEnvelope
    requested_cabins: tuple[CabinClass, ...] = ()
    traveler_count: int = Field(ge=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"origin_endpoint", "destination_endpoint", "date_envelope"}
    )
