"""Immutable contracts for Milestone 2C search-strategy compilation.

This module sits above the existing grounding, selector, and
gateway-discovery contracts.  Keeping the aggregate here avoids an import
cycle: those lower layers already depend on :mod:`contracts`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date, timedelta
from enum import Enum
from typing import Annotated, Any, Literal, cast

from pydantic import Field, model_validator

from award_agent.domain import CabinClass, FieldProvenance
from award_agent.search_planning.airport_selector import AirportSelectionRecord
from award_agent.search_planning.contracts import (
    AirportSelectionKind,
    CatalogKnowledgeReceipt,
    DateBasis,
    DateEnvelope,
    DeferredConstraintObligation,
    EndpointProbe,
    FilterObligation,
    FilterObligationKind,
    FreshnessClass,
    PlanningContractModel,
    PlanningInputEnvelope,
    ResolvedLocation,
    ResultValidationKind,
    ResultValidationObligation,
    SelectedAirport,
)
from award_agent.search_planning.gateway_discovery import (
    GatewayCandidateDecision,
    GatewayDiscoveryGenerationStatus,
    GatewayDiscoveryIssue,
    GatewayDiscoveryOutcome,
    GatewayDiscoveryResult,
    GatewayEndpointAssessmentDecision,
    GatewayMarketComparison,
    GatewayMarketCoverage,
    GatewayScopeDecision,
)
from award_agent.search_planning.market_policy import MarketGenerationGate

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
EndpointRole = Literal["origin", "destination"]
EndpointSourceKind = Literal["direct_grounding", "m2a_replay"]


class DirectGroundingSource(PlanningContractModel):
    source_kind: Literal["direct_grounding"] = "direct_grounding"


class M2ASelectionRecordSource(PlanningContractModel):
    source_kind: Literal["m2a_replay"] = "m2a_replay"
    selection_records: tuple[AirportSelectionRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_record_keys(self) -> M2ASelectionRecordSource:
        keys = tuple(
            (record.role, record.resolved_entity.entity_id)
            for record in self.selection_records
        )
        if len(keys) != len(set(keys)):
            raise ValueError("M2A records must be unique by role and resolved entity")
        return self


EndpointSource = Annotated[
    DirectGroundingSource | M2ASelectionRecordSource,
    Field(discriminator="source_kind"),
]


class SelectionRecordIdBinding(PlanningContractModel):
    upstream_record_id: str = Field(min_length=1)
    record_digest: Sha256


class SearchPlanningInput(PlanningContractModel):
    envelope: PlanningInputEnvelope
    endpoint_source: EndpointSource
    upstream_selection_id_bindings: tuple[SelectionRecordIdBinding, ...] = ()
    gateway_discovery_result: GatewayDiscoveryResult

    @model_validator(mode="after")
    def unique_upstream_ids(self) -> SearchPlanningInput:
        ids = tuple(binding.upstream_record_id for binding in self.upstream_selection_id_bindings)
        if len(ids) != len(set(ids)):
            raise ValueError("upstream selection-record IDs must be unique")
        return self


class PlanningAirportIdentity(PlanningContractModel):
    airport_id: str = Field(min_length=1)
    airport_iata: str = Field(pattern=r"^[A-Z]{3}$")
    timezone: str = Field(min_length=1)
    evidence_source_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def canonical_evidence(self) -> PlanningAirportIdentity:
        if self.evidence_source_ids != tuple(sorted(set(self.evidence_source_ids))):
            raise ValueError("airport evidence source IDs must be sorted and unique")
        return self


class EndpointSelectionProjection(PlanningContractModel):
    role: EndpointRole
    resolution: ResolvedLocation
    airports: tuple[SelectedAirport, ...] = Field(min_length=1)
    source_kind: EndpointSourceKind
    source_record_digest: Sha256 | None = None
    selection_kind: AirportSelectionKind
    freshness: FreshnessClass
    field_provenance: FieldProvenance | None = None

    @model_validator(mode="after")
    def validate_source(self) -> EndpointSelectionProjection:
        if self.source_kind == "direct_grounding" and self.source_record_digest is not None:
            raise ValueError("direct grounding cannot claim a source-record digest")
        if self.source_kind == "direct_grounding" and self.selection_kind not in {
            AirportSelectionKind.EXPLICIT_IATA,
            AirportSelectionKind.NAMED_AIRPORT,
        }:
            raise ValueError("direct grounding is limited to explicit or uniquely named airports")
        elif self.source_kind == "m2a_replay" and self.source_record_digest is None:
            raise ValueError("M2A replay requires its source-record digest")
        elif (
            self.source_kind == "m2a_replay"
            and self.selection_kind is not AirportSelectionKind.MODEL_PROPOSED
        ):
            raise ValueError("M2A replay requires model-proposed selection kind")
        return self


class EndpointSelectionBinding(PlanningContractModel):
    source_kind: EndpointSourceKind
    selected_origin_ids: tuple[str, ...] = Field(min_length=1)
    selected_destination_ids: tuple[str, ...] = Field(min_length=1)
    record_digests: tuple[Sha256, ...] = ()
    cap_policy_version: str | None = None
    cap_policy_digest: Sha256 | None = None
    distance_policy_version: str | None = None
    distance_policy_digest: Sha256 | None = None
    catalog_release_identity: CatalogKnowledgeReceipt
    review_status: Literal[
        "deterministic_approved_policy", "owner_qualified_model_proposed"
    ]

    @model_validator(mode="after")
    def validate_binding(self) -> EndpointSelectionBinding:
        if len(self.selected_origin_ids) != len(set(self.selected_origin_ids)):
            raise ValueError("selected origin IDs must be unique")
        if len(self.selected_destination_ids) != len(set(self.selected_destination_ids)):
            raise ValueError("selected destination IDs must be unique")
        if len(self.record_digests) != len(set(self.record_digests)):
            raise ValueError("record digests must be unique")
        policy_values = (
            self.cap_policy_version,
            self.cap_policy_digest,
            self.distance_policy_version,
            self.distance_policy_digest,
        )
        if self.source_kind == "m2a_replay":
            if any(value is None for value in policy_values) or not self.record_digests:
                raise ValueError("M2A binding requires record and policy identities")
            if self.review_status != "owner_qualified_model_proposed":
                raise ValueError("M2A binding requires owner-qualified-model-proposed status")
        elif any(value is not None for value in policy_values):
            raise ValueError("only M2A binding may carry selector policy identities")
        elif self.record_digests:
            raise ValueError("direct grounding cannot carry selection-record digests")
        elif self.review_status != "deterministic_approved_policy":
            raise ValueError("direct grounding requires deterministic-approved-policy status")
        return self


class CompiledPlanIdentity(PlanningContractModel):
    session_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    effective_request_digest: Sha256
    canonicalization_version: str = Field(min_length=1)
    digest_algorithm_version: str = Field(min_length=1)
    compiler_contract_version: Literal["search-strategy-compilation-v3"] = (
        "search-strategy-compilation-v3"
    )
    policy_version: str = Field(min_length=1)
    policy_digest: Sha256
    catalog_receipt: CatalogKnowledgeReceipt
    endpoint_selection_binding: EndpointSelectionBinding
    gateway_result_digest: Sha256
    gateway_input_digest: Sha256
    market_policy_version: str = Field(min_length=1)
    market_policy_digest: Sha256
    accepted_relationship_ledger_digest: Sha256
    relationship_disposition_digest: Sha256
    route_topology_feature: Literal["absent"] = "absent"
    compilation_binding_digest: Sha256


class EndpointPair(PlanningContractModel):
    origin_airport_fact_id: str = Field(min_length=1)
    destination_airport_fact_id: str = Field(min_length=1)


class LogicalAwardQuery(PlanningContractModel):
    query_id: str = Field(pattern=r"^logical-award:[0-9a-f]{64}$")
    origin_airport_fact_id: str = Field(min_length=1)
    destination_airport_fact_id: str = Field(min_length=1)
    scope: Literal["endpoint_market"] = "endpoint_market"
    date_envelope: DateEnvelope
    requested_cabins: tuple[CabinClass, ...] = ()
    award_mode: Literal["award"] = "award"
    connection_semantics: Literal["provider_returned_connections_allowed"] = (
        "provider_returned_connections_allowed"
    )
    filter_obligations: tuple[FilterObligation, ...] = ()
    result_validation_obligations: tuple[ResultValidationObligation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def enforce_first_slice_semantics(self) -> LogicalAwardQuery:
        cabins = tuple(cabin.value for cabin in self.requested_cabins)
        if cabins != tuple(sorted(set(cabins))):
            raise ValueError("requested cabins must be sorted and unique")
        if any(
            obligation.kind is ResultValidationKind.EXACT_PHYSICAL_COMPONENT_STRUCTURE
            for obligation in self.result_validation_obligations
        ):
            raise ValueError("logical queries cannot claim route-evidenced physical structure")
        cabin_filters = tuple(
            item
            for item in self.filter_obligations
            if item.kind is FilterObligationKind.CABIN_AVAILABLE_IN
        )
        if self.requested_cabins:
            if len(cabin_filters) != 1 or cabin_filters[0].values != cabins:
                raise ValueError("requested cabins require one matching cabin filter")
        elif cabin_filters:
            raise ValueError("cabin filter cannot exist without requested cabins")
        if self.query_id != "logical-award:" + _canonical_digest(
            _logical_query_identity_payload(self)
        ):
            raise ValueError("logical query ID must match complete query semantics")
        return self


class MandatoryQueryUse(PlanningContractModel):
    probe_id: str = Field(min_length=1)
    query_id: str = Field(min_length=1)
    role: Literal["mandatory_endpoint"] = "mandatory_endpoint"


class SupplementalStrategyType(str, Enum):
    ORIGIN_ACCESS = "origin_access"
    DESTINATION_ACCESS = "destination_access"
    SCOPED_HUB = "scoped_hub"


class SupplementalValidationKind(str, Enum):
    ORIGINAL_DEPARTURE_COMPLIANCE = "original_departure_compliance"
    POSITIONING_FEASIBILITY = "positioning_feasibility"
    SEPARATE_TICKET_PERMISSION = "separate_ticket_permission"
    COMPLETE_JOURNEY_VALIDATION = "complete_journey_validation"


class SupplementalValidationObligation(PlanningContractModel):
    kind: SupplementalValidationKind
    responsible_stage: Literal["future_result_or_journey_validation", "owner_review"]
    disposition: Literal["not_verified"] = "not_verified"


class SourceCandidateIdentity(PlanningContractModel):
    gateway_result_digest: Sha256
    pool: Literal["origin_access_gateways", "destination_access_gateways", "intermediate_hubs"]
    candidate_index: int = Field(ge=0)
    airport_iata: str = Field(pattern=r"^[A-Z]{3}$")
    airport_fact_id: str = Field(min_length=1)


class RelationshipIdentity(PlanningContractModel):
    relationship_type: SupplementalStrategyType
    gateway_result_digest: Sha256
    pool: Literal["origin_access_gateways", "destination_access_gateways", "intermediate_hubs"]
    candidate_index: int = Field(ge=0)
    candidate_airport_fact_id: str = Field(min_length=1)
    original_origin_airport_fact_id: str | None = None
    original_destination_airport_fact_id: str | None = None
    scope_index: int | None = Field(default=None, ge=0)
    typed_origin_kind: str | None = None
    typed_origin_iata: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    typed_destination_kind: str | None = None
    typed_destination_iata: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def validate_coordinate(self) -> RelationshipIdentity:
        hub = self.relationship_type is SupplementalStrategyType.SCOPED_HUB
        hub_fields = (
            self.scope_index,
            self.typed_origin_kind,
            self.typed_origin_iata,
            self.typed_destination_kind,
            self.typed_destination_iata,
        )
        endpoint_fields = (
            self.original_origin_airport_fact_id,
            self.original_destination_airport_fact_id,
        )
        if hub and (any(value is None for value in hub_fields) or any(endpoint_fields)):
            raise ValueError("scoped-hub identity requires only its complete typed scope coordinate")
        if not hub and (any(value is not None for value in hub_fields) or any(v is None for v in endpoint_fields)):
            raise ValueError("access identity requires exactly one complete original endpoint pair")
        return self


class SourceScopeIdentity(PlanningContractModel):
    scope_index: int = Field(ge=0)
    typed_origin_kind: str
    typed_origin_iata: str = Field(pattern=r"^[A-Z]{3}$")
    typed_destination_kind: str
    typed_destination_iata: str = Field(pattern=r"^[A-Z]{3}$")


class SupplementalStrategy(PlanningContractModel):
    relationship_id: Sha256
    strategy_id: str = Field(pattern=r"^supplemental:[0-9a-f]{64}$")
    strategy_type: SupplementalStrategyType
    phase: Literal["supplemental"] = "supplemental"
    eligibility: Literal["eligible", "conditional_permission"]
    source_candidate: SourceCandidateIdentity
    source_relationship: RelationshipIdentity
    source_scope: SourceScopeIdentity | None = None
    supported_original_endpoint_pairs: tuple[EndpointPair, ...] = Field(min_length=1)
    reason: str
    material_uncertainty: str | None = None
    market_comparison: GatewayMarketComparison
    query_roles: tuple[Literal["first_component", "later_component", "access_main"], ...]
    deferred_constraint_ids: tuple[str, ...] = ()
    support_alternative_ids: tuple[str, ...] = Field(min_length=1)
    required_validations: tuple[SupplementalValidationObligation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bundle_shape(self) -> SupplementalStrategy:
        expected = 2 if self.strategy_type is SupplementalStrategyType.SCOPED_HUB else 1
        if len(self.query_roles) != expected:
            raise ValueError("strategy query-role count must match its first-slice bundle")
        if (self.source_scope is not None) == (
            self.strategy_type is SupplementalStrategyType.SCOPED_HUB
        ):
            return self
        raise ValueError("only scoped hubs require a source scope")


class StrategyQueryUse(PlanningContractModel):
    query_use_id: Sha256
    strategy_id: str = Field(min_length=1)
    query_id: str = Field(min_length=1)
    role: Literal["access_main", "hub_first", "hub_second"]
    sequence: Literal[1, 2]
    source_relationship_id: Sha256
    date_derivation_id: Sha256


class StrategySupportAlternative(PlanningContractModel):
    support_id: Sha256
    strategy_id: str = Field(min_length=1)
    original_origin_airport_fact_id: str = Field(min_length=1)
    original_destination_airport_fact_id: str = Field(min_length=1)
    query_use_ids: tuple[Sha256, ...] = Field(min_length=1)
    positioning_dependency_ids: tuple[Sha256, ...] = ()
    separate_ticket_tolerance: Literal["unknown"] = "unknown"
    result_status: Literal["research_only_pending_result_validation"] = (
        "research_only_pending_result_validation"
    )


class PositioningDependency(PlanningContractModel):
    dependency_id: Sha256
    support_id: Sha256
    source_access_relationship_id: Sha256
    side: Literal["origin", "destination"]
    from_airport_fact_id: str = Field(min_length=1)
    to_airport_fact_id: str = Field(min_length=1)
    requested_permission: bool | None
    field_provenance: FieldProvenance | None = None
    transport_mode: Literal["unknown"] = "unknown"
    payment_mode: Literal["unknown"] = "unknown"
    feasibility: Literal["not_verified"] = "not_verified"


class PositioningPolicyReceipt(PlanningContractModel):
    relationship_id: Sha256
    dependency_descriptions: tuple[str, ...]
    requested_permission: bool | None
    decision: Literal[
        "not_required", "allowed_research", "conditional_research", "suppressed_explicit_refusal"
    ]


class SupplementalDateDerivation(PlanningContractModel):
    date_derivation_id: Sha256
    strategy_id: str = Field(min_length=1)
    query_role: Literal["access_main", "hub_first", "hub_second"]
    origin_airport_fact_id: str = Field(min_length=1)
    source_window_start: date
    source_window_end: date
    source_window_precision: str = Field(min_length=1)
    field_provenance: FieldProvenance | None = None
    start_offset_days: int
    end_offset_days: int
    derived_start: date
    derived_end: date
    basis: DateBasis
    timezone: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    note: Literal["not_schedule_or_connection_evidence"] = (
        "not_schedule_or_connection_evidence"
    )

    @model_validator(mode="after")
    def validate_derivation(self) -> SupplementalDateDerivation:
        if self.source_window_end < self.source_window_start:
            raise ValueError("source departure window end precedes start")
        if self.derived_start != self.source_window_start + timedelta(
            days=self.start_offset_days
        ) or self.derived_end != self.source_window_end + timedelta(days=self.end_offset_days):
            raise ValueError("derived dates must equal the source window plus their offsets")
        if self.basis is DateBasis.FIRST_ORIGIN_AIRPORT_LOCAL:
            if (self.start_offset_days, self.end_offset_days) != (0, 0):
                raise ValueError("first-origin date basis must preserve the source window")
        elif (self.start_offset_days, self.end_offset_days) != (-1, 2):
            raise ValueError("later-component date basis must use the -1/+2 envelope")
        return self


class IdentifiedDeferredConstraint(PlanningContractModel):
    obligation_id: Sha256
    obligation: DeferredConstraintObligation
    applies_to_query_ids: tuple[str, ...] = Field(min_length=1)


class CompilerStructuralLimitKind(str, Enum):
    ENDPOINT_PAIR_CROSS_PRODUCT = "endpoint_pair_cross_product"


class CompilerStructuralLimitReceipt(PlanningContractModel):
    kind: CompilerStructuralLimitKind
    classification: Literal["compiler_structural_safety"] = "compiler_structural_safety"
    limit: int = Field(ge=0)
    observed: int = Field(ge=0)
    disposition: Literal["within_limit", "exceeded"]

    @model_validator(mode="after")
    def validate_accounting(self) -> CompilerStructuralLimitReceipt:
        if (self.observed <= self.limit) != (self.disposition == "within_limit"):
            raise ValueError("structural-limit disposition must agree with observed and limit")
        return self


class RelationshipDispositionKind(str, Enum):
    COMPILED = "compiled"
    SUPPRESSED_POSITIONING_REFUSAL = "suppressed_positioning_refusal"
    UNSUPPORTED_RULE = "unsupported_rule"


class RelationshipDisposition(PlanningContractModel):
    relationship_id: Sha256
    disposition: RelationshipDispositionKind
    source_relationship: RelationshipIdentity
    source_candidate: SourceCandidateIdentity
    source_scope: SourceScopeIdentity | None = None
    supported_original_endpoint_pairs: tuple[EndpointPair, ...] = Field(min_length=1)
    reason_codes: tuple[str, ...]
    query_ids: tuple[str, ...] = ()


RelationshipLedgerCoordinate = tuple[
    str,
    RelationshipIdentity,
    SourceCandidateIdentity,
    SourceScopeIdentity | None,
    tuple[EndpointPair, ...],
]


def accepted_relationship_ledger_digest(
    coordinates: Iterable[RelationshipLedgerCoordinate],
) -> str:
    """Hash the complete canonical set of accepted 2B relationship coordinates."""

    entries = tuple(
        sorted(
            (
                {
                    "relationship_id": relationship_id,
                    "source_relationship": relationship,
                    "source_candidate": candidate,
                    "source_scope": scope,
                    "supported_original_endpoint_pairs": pairs,
                }
                for relationship_id, relationship, candidate, scope, pairs in coordinates
            ),
            key=lambda item: cast(str, item["relationship_id"]),
        )
    )
    relationship_ids = tuple(cast(str, item["relationship_id"]) for item in entries)
    if len(relationship_ids) != len(set(relationship_ids)):
        raise ValueError("accepted relationship ledger IDs must be unique")
    return _canonical_digest(
        {
            "accepted_relationship_ledger_version": "accepted-relationship-ledger-v1",
            "relationships": entries,
        }
    )


def relationship_disposition_ledger_digest(
    dispositions: Iterable[RelationshipDisposition],
) -> str:
    """Hash the compiler's final disposition for every accepted relationship."""

    entries = tuple(
        sorted(
            (
                {
                    "relationship_id": item.relationship_id,
                    "disposition": item.disposition,
                    "reason_codes": item.reason_codes,
                }
                for item in dispositions
            ),
            key=lambda item: cast(str, item["relationship_id"]),
        )
    )
    relationship_ids = tuple(cast(str, item["relationship_id"]) for item in entries)
    if len(relationship_ids) != len(set(relationship_ids)):
        raise ValueError("relationship disposition ledger IDs must be unique")
    return _canonical_digest(
        {
            "relationship_disposition_ledger_version": (
                "relationship-disposition-ledger-v1"
            ),
            "dispositions": entries,
        }
    )


class GatewayDiscoveryCompilationReceipt(PlanningContractModel):
    input_digest: Sha256
    result_digest: Sha256
    replay_status: Literal["verified"] = "verified"
    generation_status: GatewayDiscoveryGenerationStatus
    outcome: GatewayDiscoveryOutcome
    market_gate: MarketGenerationGate
    market_coverage: GatewayMarketCoverage
    endpoint_assessment_decisions: tuple[GatewayEndpointAssessmentDecision, ...] = ()
    candidate_decisions: tuple[GatewayCandidateDecision, ...] = ()
    scope_decisions: tuple[GatewayScopeDecision, ...] = ()
    issues: tuple[GatewayDiscoveryIssue, ...] = ()
    limitations: tuple[str, ...] = Field(min_length=1)


class CompilationCoverage(PlanningContractModel):
    mandatory_required_pairs: int = Field(ge=0)
    mandatory_covered_pairs: int = Field(ge=0)
    mandatory_complete: bool
    accepted_relationships: int = Field(ge=0)
    compiled_relationships: int = Field(ge=0)
    suppressed_positioning_refusal_relationships: int = Field(ge=0)
    unsupported_rule_relationships: int = Field(ge=0)
    discovery_outcome: GatewayDiscoveryOutcome
    market_coverage: GatewayMarketCoverage

    @model_validator(mode="after")
    def validate_coverage(self) -> CompilationCoverage:
        if self.mandatory_complete != (
            self.mandatory_required_pairs == self.mandatory_covered_pairs
        ):
            raise ValueError("mandatory-complete flag must agree with pair coverage")
        accounted = (
            self.compiled_relationships
            + self.suppressed_positioning_refusal_relationships
            + self.unsupported_rule_relationships
        )
        if accounted != self.accepted_relationships:
            raise ValueError("every accepted relationship requires exactly one disposition")
        return self


class StrategyCompilationIssueCode(str, Enum):
    GATEWAY_RECORD_MISSING = "gateway_record_missing"
    UNSUPPORTED_KNOWLEDGE_SOURCE = "unsupported_knowledge_source"
    ENDPOINT_SELECTION_BINDING_MISMATCH = "endpoint_selection_binding_mismatch"
    GATEWAY_INPUT_BINDING_MISMATCH = "gateway_input_binding_mismatch"
    GATEWAY_REPLAY_FAILED = "gateway_replay_failed"
    COMPILER_CONTRACT_FAILURE = "compiler_contract_failure"
    ENDPOINT_PAIR_STRUCTURAL_LIMIT_EXCEEDED = "endpoint_pair_structural_limit_exceeded"


class StrategyCompilationIssue(PlanningContractModel):
    code: StrategyCompilationIssueCode | str
    stage: Literal["input", "grounding", "binding", "replay", "compilation"]
    severity: Literal["observation", "reduced_coverage", "unplannable", "evidence_failure"]
    message: str = Field(min_length=1)
    source_relationship_id: Sha256 | None = None
    source_record_ref: str | None = None


class CompiledSearchPlan(PlanningContractModel):
    identity: CompiledPlanIdentity
    location_resolutions: tuple[ResolvedLocation, ...] = Field(min_length=1)
    endpoint_selections: tuple[EndpointSelectionProjection, ...] = Field(min_length=1)
    endpoint_selection_binding: EndpointSelectionBinding
    airport_directory: tuple[PlanningAirportIdentity, ...] = Field(min_length=1)
    mandatory_endpoint_probes: tuple[EndpointProbe, ...] = Field(min_length=1)
    mandatory_query_uses: tuple[MandatoryQueryUse, ...] = Field(min_length=1)
    supplemental_strategies: tuple[SupplementalStrategy, ...] = ()
    logical_queries: tuple[LogicalAwardQuery, ...] = Field(min_length=1)
    strategy_query_uses: tuple[StrategyQueryUse, ...] = ()
    support_alternatives: tuple[StrategySupportAlternative, ...] = ()
    constraint_obligations: tuple[IdentifiedDeferredConstraint, ...] = ()
    temporal_derivations: tuple[SupplementalDateDerivation, ...] = ()
    positioning_dependencies: tuple[PositioningDependency, ...] = ()
    positioning_receipts: tuple[PositioningPolicyReceipt, ...] = ()
    relationship_dispositions: tuple[RelationshipDisposition, ...] = ()
    discovery_receipt: GatewayDiscoveryCompilationReceipt
    coverage: CompilationCoverage
    structural_limit_receipts: tuple[CompilerStructuralLimitReceipt, ...] = Field(
        min_length=1, max_length=1
    )
    issues: tuple[StrategyCompilationIssue, ...] = ()
    plan_digest: Sha256

    @model_validator(mode="after")
    def validate_graph(self) -> CompiledSearchPlan:
        if self.endpoint_selection_binding != self.identity.endpoint_selection_binding:
            raise ValueError("plan endpoint-selection binding must match plan identity")
        query_ids = tuple(query.query_id for query in self.logical_queries)
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("logical query IDs must be unique")
        probe_ids = tuple(probe.probe_id for probe in self.mandatory_endpoint_probes)
        mandatory_probe_ids = tuple(use.probe_id for use in self.mandatory_query_uses)
        if len(probe_ids) != len(set(probe_ids)) or set(probe_ids) != set(mandatory_probe_ids):
            raise ValueError("every mandatory probe requires exactly one mandatory query use")
        if len(mandatory_probe_ids) != len(set(mandatory_probe_ids)):
            raise ValueError("mandatory query uses must be unique by probe")
        known_queries = set(query_ids)
        if any(use.query_id not in known_queries for use in self.mandatory_query_uses):
            raise ValueError("mandatory use references an unknown query")
        strategy_ids = {strategy.strategy_id for strategy in self.supplemental_strategies}
        if len(strategy_ids) != len(self.supplemental_strategies):
            raise ValueError("supplemental strategy IDs must be unique")
        if any(
            use.query_id not in known_queries or use.strategy_id not in strategy_ids
            for use in self.strategy_query_uses
        ):
            raise ValueError("strategy query use has a dangling link")
        used_queries = {use.query_id for use in self.mandatory_query_uses} | {
            use.query_id for use in self.strategy_query_uses
        }
        if used_queries != known_queries:
            raise ValueError("every logical query must be reachable from a plan use")
        expected_limit_kinds = set(CompilerStructuralLimitKind)
        actual_limit_kinds = {receipt.kind for receipt in self.structural_limit_receipts}
        if actual_limit_kinds != expected_limit_kinds:
            raise ValueError("plan requires exactly one receipt for each compiler structural limit")
        if not self.coverage.mandatory_complete:
            raise ValueError("compiled plans require complete mandatory coverage")
        dispositions = tuple(item.relationship_id for item in self.relationship_dispositions)
        if len(dispositions) != len(set(dispositions)):
            raise ValueError("relationship dispositions must be unique")
        if len(dispositions) != self.coverage.accepted_relationships:
            raise ValueError("coverage accepted count must match relationship dispositions")
        disposition_counts = {
            kind: sum(item.disposition is kind for item in self.relationship_dispositions)
            for kind in RelationshipDispositionKind
        }
        if disposition_counts[RelationshipDispositionKind.COMPILED] != (
            self.coverage.compiled_relationships
        ) or disposition_counts[
            RelationshipDispositionKind.SUPPRESSED_POSITIONING_REFUSAL
        ] != self.coverage.suppressed_positioning_refusal_relationships or disposition_counts[
            RelationshipDispositionKind.UNSUPPORTED_RULE
        ] != self.coverage.unsupported_rule_relationships:
            raise ValueError("coverage disposition counts must match relationship receipts")
        _validate_compiled_plan_integrity(self)
        return self


def _validate_relationship_disposition_sources(plan: CompiledSearchPlan) -> None:
    expected_pool = {
        SupplementalStrategyType.ORIGIN_ACCESS: "origin_access_gateways",
        SupplementalStrategyType.DESTINATION_ACCESS: "destination_access_gateways",
        SupplementalStrategyType.SCOPED_HUB: "intermediate_hubs",
    }
    for disposition in plan.relationship_dispositions:
        relationship = disposition.source_relationship
        candidate = disposition.source_candidate
        if disposition.relationship_id != _canonical_digest(relationship):
            raise ValueError("relationship disposition ID is forged")
        expected_reason_codes = {
            RelationshipDispositionKind.COMPILED: ("compiled",),
            RelationshipDispositionKind.SUPPRESSED_POSITIONING_REFUSAL: (
                "positioning_explicitly_refused",
            ),
            RelationshipDispositionKind.UNSUPPORTED_RULE: (
                "supplemental_date_overflow",
            ),
        }[disposition.disposition]
        if disposition.reason_codes != expected_reason_codes:
            raise ValueError(
                "relationship disposition reason codes must match its finite outcome"
            )
        if disposition.disposition is RelationshipDispositionKind.COMPILED:
            if not disposition.query_ids:
                raise ValueError("compiled relationship disposition requires query IDs")
        elif disposition.query_ids:
            raise ValueError(
                "noncompiled relationship disposition cannot claim materialized query IDs"
            )
        if (
            relationship.gateway_result_digest != plan.identity.gateway_result_digest
            or candidate.gateway_result_digest != relationship.gateway_result_digest
            or relationship.pool != expected_pool[relationship.relationship_type]
            or candidate.pool != relationship.pool
            or candidate.candidate_index != relationship.candidate_index
            or candidate.airport_fact_id != relationship.candidate_airport_fact_id
        ):
            raise ValueError(
                "relationship disposition source candidate coordinates differ"
            )
        matching_decision = next(
            (
                decision
                for decision in plan.discovery_receipt.candidate_decisions
                if decision.accepted
                and decision.pool == candidate.pool
                and decision.candidate_index == candidate.candidate_index
                and decision.proposed_airport_iata == candidate.airport_iata
            ),
            None,
        )
        if matching_decision is None:
            raise ValueError(
                "relationship disposition source candidate is not accepted discovery evidence"
            )
        if relationship.relationship_type is SupplementalStrategyType.SCOPED_HUB:
            scope = disposition.source_scope
            if scope is None or (
                scope.scope_index,
                scope.typed_origin_kind,
                scope.typed_origin_iata,
                scope.typed_destination_kind,
                scope.typed_destination_iata,
            ) != (
                relationship.scope_index,
                relationship.typed_origin_kind,
                relationship.typed_origin_iata,
                relationship.typed_destination_kind,
                relationship.typed_destination_iata,
            ):
                raise ValueError(
                    "relationship disposition source scope coordinates differ"
                )
            if not any(
                item.accepted and item.scope_index == scope.scope_index
                for item in matching_decision.scope_decisions
            ):
                raise ValueError(
                    "relationship disposition scope is not accepted discovery evidence"
                )
        else:
            if disposition.source_scope is not None:
                raise ValueError("access relationship disposition cannot carry a source scope")
            expected_pair = (
                relationship.original_origin_airport_fact_id,
                relationship.original_destination_airport_fact_id,
            )
            actual_pairs = tuple(
                (
                    pair.origin_airport_fact_id,
                    pair.destination_airport_fact_id,
                )
                for pair in disposition.supported_original_endpoint_pairs
            )
            if actual_pairs != (expected_pair,):
                raise ValueError(
                    "access relationship disposition must preserve its original endpoint pair"
                )
        if (
            disposition.disposition is RelationshipDispositionKind.UNSUPPORTED_RULE
            and (
                disposition.reason_codes != ("supplemental_date_overflow",)
                or not _relationship_date_derivation_overflows(plan, disposition)
            )
        ):
            raise ValueError(
                "unsupported relationship disposition must reproduce a finite date overflow"
            )


def _relationship_date_derivation_overflows(
    plan: CompiledSearchPlan,
    disposition: RelationshipDisposition,
) -> bool:
    if (
        disposition.source_relationship.relationship_type
        is SupplementalStrategyType.DESTINATION_ACCESS
    ):
        return False
    pair = disposition.supported_original_endpoint_pairs[0]
    probe = next(
        (
            item
            for item in plan.mandatory_endpoint_probes
            if item.origin_endpoint.airport_id == pair.origin_airport_fact_id
            and item.destination_endpoint.airport_id == pair.destination_airport_fact_id
        ),
        None,
    )
    if probe is None:
        return False
    try:
        probe.date_envelope.start - timedelta(days=1)
        probe.date_envelope.end + timedelta(days=2)
    except OverflowError:
        return True
    return False


def _suppressed_positioning_descriptions(
    disposition: RelationshipDisposition,
    dispositions: tuple[RelationshipDisposition, ...],
) -> tuple[str, ...]:
    relationship = disposition.source_relationship
    if relationship.relationship_type is SupplementalStrategyType.ORIGIN_ACCESS:
        return (
            (
                "origin:"
                f"{relationship.original_origin_airport_fact_id}->"
                f"{relationship.candidate_airport_fact_id}"
            ),
        )
    if relationship.relationship_type is SupplementalStrategyType.DESTINATION_ACCESS:
        return (
            (
                "destination:"
                f"{relationship.candidate_airport_fact_id}->"
                f"{relationship.original_destination_airport_fact_id}"
            ),
        )
    descriptions: list[str] = []
    for pair in disposition.supported_original_endpoint_pairs:
        if relationship.typed_origin_kind == "origin_access_gateway":
            access = next(
                (
                    item.source_relationship
                    for item in dispositions
                    if item.source_relationship.relationship_type
                    is SupplementalStrategyType.ORIGIN_ACCESS
                    and item.source_relationship.original_origin_airport_fact_id
                    == pair.origin_airport_fact_id
                    and item.source_relationship.original_destination_airport_fact_id
                    == pair.destination_airport_fact_id
                    and item.source_candidate.airport_iata
                    == relationship.typed_origin_iata
                ),
                None,
            )
            if access is None:
                raise ValueError(
                    "suppressed hub positioning receipt lacks its origin access relationship"
                )
            descriptions.append(
                f"origin:{pair.origin_airport_fact_id}->{access.candidate_airport_fact_id}"
            )
        if relationship.typed_destination_kind == "destination_access_gateway":
            access = next(
                (
                    item.source_relationship
                    for item in dispositions
                    if item.source_relationship.relationship_type
                    is SupplementalStrategyType.DESTINATION_ACCESS
                    and item.source_relationship.original_origin_airport_fact_id
                    == pair.origin_airport_fact_id
                    and item.source_relationship.original_destination_airport_fact_id
                    == pair.destination_airport_fact_id
                    and item.source_candidate.airport_iata
                    == relationship.typed_destination_iata
                ),
                None,
            )
            if access is None:
                raise ValueError(
                    "suppressed hub positioning receipt lacks its destination access relationship"
                )
            descriptions.append(
                "destination:"
                f"{access.candidate_airport_fact_id}->{pair.destination_airport_fact_id}"
            )
    return tuple(dict.fromkeys(descriptions))


def _validate_compiled_plan_integrity(plan: CompiledSearchPlan) -> None:
    if plan.plan_digest != _canonical_digest(
        plan.model_dump(mode="json", round_trip=True, exclude={"plan_digest"})
    ):
        raise ValueError("plan digest must match the complete canonical plan payload")
    if (
        plan.identity.gateway_input_digest != plan.discovery_receipt.input_digest
        or plan.identity.gateway_result_digest != plan.discovery_receipt.result_digest
    ):
        raise ValueError("plan identity gateway digests must match the discovery receipt")
    _validate_relationship_disposition_sources(plan)
    if plan.issues != _expected_plan_issues(plan):
        raise ValueError(
            "plan issues must exactly derive from discovery outcome and relationship dispositions"
        )
    expected_relationship_ledger_digest = accepted_relationship_ledger_digest(
        (
            item.relationship_id,
            item.source_relationship,
            item.source_candidate,
            item.source_scope,
            item.supported_original_endpoint_pairs,
        )
        for item in plan.relationship_dispositions
    )
    if (
        plan.identity.accepted_relationship_ledger_digest
        != expected_relationship_ledger_digest
    ):
        raise ValueError("accepted relationship ledger digest is forged")
    expected_disposition_digest = relationship_disposition_ledger_digest(
        plan.relationship_dispositions
    )
    if plan.identity.relationship_disposition_digest != expected_disposition_digest:
        raise ValueError("relationship disposition digest is forged")
    expected_compilation_binding = _canonical_digest(
        {
            "compilation_binding_version": "search-strategy-compilation-binding-v2",
            "request": plan.identity.effective_request_digest,
            "endpoint": _canonical_digest(plan.endpoint_selection_binding),
            "gateway_input": plan.identity.gateway_input_digest,
            "gateway_result": plan.identity.gateway_result_digest,
            "compiler_contract_version": plan.identity.compiler_contract_version,
            "canonicalization_version": plan.identity.canonicalization_version,
            "digest_algorithm_version": plan.identity.digest_algorithm_version,
            "policy": plan.identity.policy_digest,
            "catalog": plan.identity.catalog_receipt,
            "market_policy_version": plan.identity.market_policy_version,
            "market_policy_digest": plan.identity.market_policy_digest,
            "accepted_relationship_ledger": (
                plan.identity.accepted_relationship_ledger_digest
            ),
            "relationship_dispositions": plan.identity.relationship_disposition_digest,
            "route_topology_feature": plan.identity.route_topology_feature,
        }
    )
    if plan.identity.compilation_binding_digest != expected_compilation_binding:
        raise ValueError("compilation binding digest is forged")

    origins = tuple(
        dict.fromkeys(
            airport.airport_id
            for selection in plan.endpoint_selections
            if selection.role == "origin"
            for airport in selection.airports
        )
    )
    destinations = tuple(
        dict.fromkeys(
            airport.airport_id
            for selection in plan.endpoint_selections
            if selection.role == "destination"
            for airport in selection.airports
        )
    )
    if origins != plan.endpoint_selection_binding.selected_origin_ids or destinations != (
        plan.endpoint_selection_binding.selected_destination_ids
    ):
        raise ValueError("endpoint projections must reproduce the endpoint-selection binding")
    projection_digests = tuple(
        sorted(
            projection.source_record_digest
            for projection in plan.endpoint_selections
            if projection.source_record_digest is not None
        )
    )
    if projection_digests != tuple(sorted(plan.endpoint_selection_binding.record_digests)):
        raise ValueError("endpoint projection record digests must reproduce the binding")

    query_by_id = {query.query_id: query for query in plan.logical_queries}
    probe_by_id = {probe.probe_id: probe for probe in plan.mandatory_endpoint_probes}
    mandatory_query_ids: set[str] = set()
    mandatory_pairs: set[tuple[str, str]] = set()
    for mandatory_use in plan.mandatory_query_uses:
        probe = probe_by_id[mandatory_use.probe_id]
        query = query_by_id[mandatory_use.query_id]
        if (
            query.origin_airport_fact_id != probe.origin_endpoint.airport_id
            or query.destination_airport_fact_id != probe.destination_endpoint.airport_id
            or query.date_envelope != probe.date_envelope
            or query.requested_cabins != probe.requested_cabins
        ):
            raise ValueError("mandatory query use must preserve complete probe semantics")
        if not any(
            item.kind is ResultValidationKind.MINIMUM_AWARD_SEATS
            and item.minimum_seats == probe.traveler_count
            for item in query.result_validation_obligations
        ):
            raise ValueError("mandatory query must validate the probe traveler count")
        mandatory_query_ids.add(query.query_id)
        mandatory_pairs.add(
            (probe.origin_endpoint.airport_id, probe.destination_endpoint.airport_id)
        )
    expected_pairs = {(origin, destination) for origin in origins for destination in destinations}
    if mandatory_pairs != expected_pairs or plan.coverage.mandatory_required_pairs != len(
        expected_pairs
    ) or plan.coverage.mandatory_covered_pairs != len(mandatory_pairs):
        raise ValueError("mandatory probes must exactly cover the selected endpoint cross-product")
    original_query = query_by_id[next(iter(mandatory_query_ids))]
    original_window_start = original_query.date_envelope.start
    original_window_end = original_query.date_envelope.end
    original_window_precision = original_query.date_envelope.effective_window_precision
    original_window_provenance = original_query.date_envelope.field_provenance

    airport_by_id = {item.airport_id: item for item in plan.airport_directory}
    airport_by_iata = {item.airport_iata: item for item in plan.airport_directory}
    if len(airport_by_id) != len(plan.airport_directory):
        raise ValueError("airport-directory IDs must be unique")
    if len(airport_by_iata) != len(plan.airport_directory):
        raise ValueError("airport-directory IATA codes must be unique")
    query_airport_ids = {
        airport_id
        for query in plan.logical_queries
        for airport_id in (
            query.origin_airport_fact_id,
            query.destination_airport_fact_id,
        )
    }
    if query_airport_ids != set(airport_by_id) or any(
        query.date_envelope.timezone != airport_by_id[query.origin_airport_fact_id].timezone
        for query in plan.logical_queries
    ):
        raise ValueError("airport directory must exactly ground every logical query endpoint")

    strategy_by_id = {item.strategy_id: item for item in plan.supplemental_strategies}
    positioning_receipt_by_relationship = {
        item.relationship_id: item for item in plan.positioning_receipts
    }
    if len(positioning_receipt_by_relationship) != len(plan.positioning_receipts):
        raise ValueError("positioning policy receipt relationship IDs must be unique")
    expected_positioning_receipt_ids = {
        item.relationship_id
        for item in plan.relationship_dispositions
        if item.disposition
        in {
            RelationshipDispositionKind.COMPILED,
            RelationshipDispositionKind.SUPPRESSED_POSITIONING_REFUSAL,
        }
    }
    if set(positioning_receipt_by_relationship) != expected_positioning_receipt_ids:
        raise ValueError(
            "positioning policy receipts must exactly cover compiled and suppressed relationships"
        )
    for disposition in plan.relationship_dispositions:
        if (
            disposition.disposition
            is not RelationshipDispositionKind.SUPPRESSED_POSITIONING_REFUSAL
        ):
            continue
        receipt = positioning_receipt_by_relationship[disposition.relationship_id]
        expected_descriptions = _suppressed_positioning_descriptions(
            disposition, plan.relationship_dispositions
        )
        if (
            receipt.requested_permission is not False
            or receipt.decision != "suppressed_explicit_refusal"
            or len(receipt.dependency_descriptions)
            != len(set(receipt.dependency_descriptions))
            or set(receipt.dependency_descriptions) != set(expected_descriptions)
        ):
            raise ValueError(
                "suppressed relationship positioning receipt does not match its requirements"
            )
    derivation_by_id = {item.date_derivation_id: item for item in plan.temporal_derivations}
    if len(derivation_by_id) != len(plan.temporal_derivations):
        raise ValueError("temporal derivation IDs must be unique")
    uses_by_strategy: dict[str, list[StrategyQueryUse]] = {}
    for strategy_use in plan.strategy_query_uses:
        strategy = strategy_by_id[strategy_use.strategy_id]
        if strategy_use.source_relationship_id != strategy.relationship_id:
            raise ValueError("strategy query use must preserve its relationship identity")
        expected_use_id = _canonical_digest(
            {
                "strategy": strategy_use.strategy_id,
                "query": strategy_use.query_id,
                "role": strategy_use.role,
                "relationship": strategy_use.source_relationship_id,
            }
        )
        if strategy_use.query_use_id != expected_use_id:
            raise ValueError("strategy query-use ID is forged")
        derivation = derivation_by_id.get(strategy_use.date_derivation_id)
        if derivation is None or derivation.strategy_id != strategy_use.strategy_id:
            raise ValueError("strategy query use has an invalid temporal derivation")
        if derivation.query_role != strategy_use.role:
            raise ValueError("temporal derivation role must match its strategy query use")
        query = query_by_id[strategy_use.query_id]
        if (
            derivation.origin_airport_fact_id != query.origin_airport_fact_id
            or derivation.derived_start != query.date_envelope.start
            or derivation.derived_end != query.date_envelope.end
            or derivation.timezone != query.date_envelope.timezone
            or derivation.basis != query.date_envelope.basis
        ):
            raise ValueError("temporal derivation must reproduce its logical query envelope")
        expected_derivation_id = _canonical_digest(
            {
                "strategy": strategy.relationship_id,
                "role": derivation.query_role,
                "origin": derivation.origin_airport_fact_id,
                "start": derivation.derived_start,
                "end": derivation.derived_end,
                "policy": derivation.policy_version,
            }
        )
        if derivation.date_derivation_id != expected_derivation_id:
            raise ValueError("temporal derivation ID is forged")
        uses_by_strategy.setdefault(strategy_use.strategy_id, []).append(strategy_use)
    for strategy in plan.supplemental_strategies:
        if strategy.relationship_id != _canonical_digest(strategy.source_relationship):
            raise ValueError("strategy relationship ID is forged")
        source = strategy.source_relationship
        candidate = strategy.source_candidate
        if (
            candidate.gateway_result_digest != source.gateway_result_digest
            or candidate.pool != source.pool
            or candidate.candidate_index != source.candidate_index
            or candidate.airport_fact_id != source.candidate_airport_fact_id
        ):
            raise ValueError("strategy source candidate and relationship coordinates differ")
        expected_strategy_id = "supplemental:" + _canonical_digest(
            {
                "relationship_id": strategy.relationship_id,
                "policy": plan.identity.policy_digest,
            }
        )
        if strategy.strategy_id != expected_strategy_id:
            raise ValueError("supplemental strategy ID is forged")
        matching_decision = next(
            (
                decision
                for decision in plan.discovery_receipt.candidate_decisions
                if decision.pool == strategy.source_candidate.pool
                and decision.candidate_index == strategy.source_candidate.candidate_index
                and decision.proposed_airport_iata == strategy.source_candidate.airport_iata
                and decision.accepted
            ),
            None,
        )
        if matching_decision is None:
            raise ValueError("strategy source candidate is not accepted discovery evidence")
        if strategy.source_scope is not None and not any(
            scope.accepted
            and scope.scope_index == strategy.source_scope.scope_index
            for scope in matching_decision.scope_decisions
        ):
            raise ValueError("strategy source scope is not an accepted source coordinate")
        if strategy.strategy_type is SupplementalStrategyType.SCOPED_HUB and not any(
            item.kind is SupplementalValidationKind.SEPARATE_TICKET_PERMISSION
            for item in strategy.required_validations
        ):
            raise ValueError("scoped-hub strategies require separate-ticket validation")
        uses = sorted(uses_by_strategy.get(strategy.strategy_id, ()), key=lambda item: item.sequence)
        expected_roles = (
            ("access_main",)
            if strategy.strategy_type is not SupplementalStrategyType.SCOPED_HUB
            else ("hub_first", "hub_second")
        )
        if tuple(item.role for item in uses) != expected_roles or tuple(
            item.sequence for item in uses
        ) != tuple(range(1, len(expected_roles) + 1)):
            raise ValueError("supplemental strategy uses must form one complete atomic bundle")
        role_queries = {item.role: query_by_id[item.query_id] for item in uses}
        if strategy.strategy_type is SupplementalStrategyType.ORIGIN_ACCESS:
            access_query = role_queries["access_main"]
            expected_endpoints = (
                source.candidate_airport_fact_id,
                source.original_destination_airport_fact_id,
            )
            actual_endpoints = (
                access_query.origin_airport_fact_id,
                access_query.destination_airport_fact_id,
            )
            if actual_endpoints != expected_endpoints:
                raise ValueError("origin-access query must be gateway to original destination")
        elif strategy.strategy_type is SupplementalStrategyType.DESTINATION_ACCESS:
            access_query = role_queries["access_main"]
            if (
                access_query.origin_airport_fact_id
                != source.original_origin_airport_fact_id
                or access_query.destination_airport_fact_id
                != source.candidate_airport_fact_id
            ):
                raise ValueError("destination-access query must be original origin to gateway")
        else:
            origin_airport = airport_by_iata.get(source.typed_origin_iata or "")
            destination_airport = airport_by_iata.get(source.typed_destination_iata or "")
            if origin_airport is None or destination_airport is None:
                raise ValueError("scoped-hub typed references require directory airports")
            first = role_queries["hub_first"]
            second = role_queries["hub_second"]
            if (
                first.origin_airport_fact_id != origin_airport.airport_id
                or first.destination_airport_fact_id != source.candidate_airport_fact_id
                or second.origin_airport_fact_id != source.candidate_airport_fact_id
                or second.destination_airport_fact_id != destination_airport.airport_id
            ):
                raise ValueError("scoped-hub queries must preserve typed reference endpoints")
        for use in uses:
            derivation = derivation_by_id[use.date_derivation_id]
            if strategy.strategy_type is SupplementalStrategyType.DESTINATION_ACCESS:
                later_component = False
            elif strategy.strategy_type is SupplementalStrategyType.ORIGIN_ACCESS:
                later_component = True
            else:
                later_component = use.role == "hub_second" or (
                    use.role == "hub_first"
                    and source.typed_origin_kind == "origin_access_gateway"
                )
            expected_basis = (
                DateBasis.LATER_COMPONENT_ORIGIN_AIRPORT_LOCAL
                if later_component
                else DateBasis.FIRST_ORIGIN_AIRPORT_LOCAL
            )
            expected_offsets = (-1, 2) if later_component else (0, 0)
            if (
                derivation.source_window_start != original_window_start
                or derivation.source_window_end != original_window_end
                or derivation.source_window_precision != original_window_precision
                or derivation.field_provenance != original_window_provenance
                or derivation.basis is not expected_basis
                or (derivation.start_offset_days, derivation.end_offset_days)
                != expected_offsets
            ):
                raise ValueError(
                    "supplemental date derivation must preserve the original departure window rule"
                )
        strategy_dependencies = tuple(
            dependency
            for support in plan.support_alternatives
            if support.strategy_id == strategy.strategy_id
            for dependency_id in support.positioning_dependency_ids
            if (dependency := next(
                (
                    item
                    for item in plan.positioning_dependencies
                    if item.dependency_id == dependency_id
                ),
                None,
            ))
            is not None
        )
        has_positioning = bool(strategy_dependencies)
        expected_validations = {
            SupplementalValidationKind.ORIGINAL_DEPARTURE_COMPLIANCE:
                "future_result_or_journey_validation",
            SupplementalValidationKind.COMPLETE_JOURNEY_VALIDATION:
                "future_result_or_journey_validation",
            SupplementalValidationKind.SEPARATE_TICKET_PERMISSION: "owner_review",
        }
        if has_positioning:
            expected_validations[SupplementalValidationKind.POSITIONING_FEASIBILITY] = (
                "future_result_or_journey_validation"
            )
        actual_validations = {
            item.kind: item.responsible_stage for item in strategy.required_validations
        }
        if len(actual_validations) != len(strategy.required_validations) or (
            actual_validations != expected_validations
        ):
            raise ValueError("supplemental strategy validation obligations are incomplete")
        positioning_receipt = positioning_receipt_by_relationship.get(strategy.relationship_id)
        if positioning_receipt is None:
            raise ValueError("compiled strategy requires one positioning policy receipt")
        if has_positioning:
            permissions = {item.requested_permission for item in strategy_dependencies}
            if False in permissions or len(permissions) != 1:
                raise ValueError("compiled positioning dependencies cannot be explicitly refused")
            permission = next(iter(permissions))
            expected_eligibility = "conditional_permission" if permission is None else "eligible"
            expected_decision = "conditional_research" if permission is None else "allowed_research"
            if (
                strategy.eligibility != expected_eligibility
                or positioning_receipt.requested_permission is not permission
                or positioning_receipt.decision != expected_decision
            ):
                raise ValueError("positioning eligibility and receipt must match typed permission")
        elif strategy.eligibility != "eligible" or positioning_receipt.decision != "not_required":
            raise ValueError("strategy without positioning must be eligible and marked not required")
        compiled_expected_descriptions = {
            f"{item.side}:{item.from_airport_fact_id}->{item.to_airport_fact_id}"
            for item in strategy_dependencies
        }
        if (
            len(positioning_receipt.dependency_descriptions)
            != len(set(positioning_receipt.dependency_descriptions))
            or set(positioning_receipt.dependency_descriptions)
            != compiled_expected_descriptions
        ):
            raise ValueError(
                "compiled relationship positioning receipt does not match its dependencies"
            )
        compiled_disposition = next(
            (
                item
                for item in plan.relationship_dispositions
                if item.relationship_id == strategy.relationship_id
            ),
            None,
        )
        if (
            compiled_disposition is None
            or compiled_disposition.disposition is not RelationshipDispositionKind.COMPILED
            or compiled_disposition.query_ids != tuple(item.query_id for item in uses)
            or compiled_disposition.source_relationship != strategy.source_relationship
            or compiled_disposition.source_candidate != strategy.source_candidate
            or compiled_disposition.source_scope != strategy.source_scope
            or compiled_disposition.supported_original_endpoint_pairs
            != strategy.supported_original_endpoint_pairs
        ):
            raise ValueError("compiled strategy must match one compiled relationship disposition")

    if {item.date_derivation_id for item in plan.strategy_query_uses} != set(derivation_by_id):
        raise ValueError("every temporal derivation must be reachable from exactly one query use")
    if {
        item.relationship_id
        for item in plan.relationship_dispositions
        if item.disposition is RelationshipDispositionKind.COMPILED
    } != {item.relationship_id for item in plan.supplemental_strategies}:
        raise ValueError("compiled dispositions and supplemental strategies must be bijective")

    obligation_ids = {item.obligation_id for item in plan.constraint_obligations}
    if len(obligation_ids) != len(plan.constraint_obligations):
        raise ValueError("deferred-constraint obligation IDs must be unique")
    if any(
        set(strategy.deferred_constraint_ids) != obligation_ids
        for strategy in plan.supplemental_strategies
    ):
        raise ValueError("every supplemental strategy must link all deferred constraints")

    support_by_id = {item.support_id: item for item in plan.support_alternatives}
    if len(support_by_id) != len(plan.support_alternatives):
        raise ValueError("support-alternative IDs must be unique")
    use_by_id = {item.query_use_id: item for item in plan.strategy_query_uses}
    dependency_by_id = {item.dependency_id: item for item in plan.positioning_dependencies}
    disposition_by_relationship = {
        item.relationship_id: item for item in plan.relationship_dispositions
    }
    if len(dependency_by_id) != len(plan.positioning_dependencies):
        raise ValueError("positioning dependency IDs must be unique")
    for strategy in plan.supplemental_strategies:
        if set(strategy.support_alternative_ids) != {
            item.support_id
            for item in plan.support_alternatives
            if item.strategy_id == strategy.strategy_id
        }:
            raise ValueError("strategy support-alternative links are incomplete")
        expected_support_pairs = {
            (item.origin_airport_fact_id, item.destination_airport_fact_id)
            for item in strategy.supported_original_endpoint_pairs
        }
        actual_support_pairs = {
            (
                item.original_origin_airport_fact_id,
                item.original_destination_airport_fact_id,
            )
            for item in plan.support_alternatives
            if item.strategy_id == strategy.strategy_id
        }
        if actual_support_pairs != expected_support_pairs:
            raise ValueError("strategy supports must exactly cover its declared endpoint pairs")
    for support in plan.support_alternatives:
        support_strategy = strategy_by_id.get(support.strategy_id)
        if support_strategy is None:
            raise ValueError("support alternative references an unknown strategy")
        expected_support = _canonical_digest(
            {
                "strategy": support.strategy_id,
                "pair": EndpointPair(
                    origin_airport_fact_id=support.original_origin_airport_fact_id,
                    destination_airport_fact_id=support.original_destination_airport_fact_id,
                ).model_dump(mode="json", round_trip=True),
            }
        )
        if support.support_id != expected_support:
            raise ValueError("support-alternative ID is forged")
        expected_query_use_ids = {
            item.query_use_id
            for item in plan.strategy_query_uses
            if item.strategy_id == support.strategy_id
        }
        if set(support.query_use_ids) != expected_query_use_ids or any(
            use_id not in use_by_id
            or use_by_id[use_id].strategy_id != support.strategy_id
            for use_id in support.query_use_ids
        ):
            raise ValueError("support alternative must link the complete atomic query-use bundle")
        expected_dependency_sides: set[str] = set()
        if support_strategy.strategy_type is SupplementalStrategyType.ORIGIN_ACCESS or (
            support_strategy.strategy_type is SupplementalStrategyType.SCOPED_HUB
            and support_strategy.source_relationship.typed_origin_kind == "origin_access_gateway"
        ):
            expected_dependency_sides.add("origin")
        if support_strategy.strategy_type is SupplementalStrategyType.DESTINATION_ACCESS or (
            support_strategy.strategy_type is SupplementalStrategyType.SCOPED_HUB
            and support_strategy.source_relationship.typed_destination_kind
            == "destination_access_gateway"
        ):
            expected_dependency_sides.add("destination")
        actual_dependencies = tuple(
            dependency_by_id[dependency_id]
            for dependency_id in support.positioning_dependency_ids
            if dependency_id in dependency_by_id
        )
        if (
            {item.side for item in actual_dependencies} != expected_dependency_sides
            or len(actual_dependencies) != len(expected_dependency_sides)
        ):
            raise ValueError(
                "support alternative must preserve every required positioning dependency"
            )
        for dependency_id in support.positioning_dependency_ids:
            dependency = dependency_by_id.get(dependency_id)
            if dependency is None or dependency.support_id != support.support_id:
                raise ValueError("support alternative has an invalid positioning dependency")
            expected_dependency = _canonical_digest(
                {
                    "support": support.support_id,
                    "side": dependency.side,
                    "from": dependency.from_airport_fact_id,
                    "to": dependency.to_airport_fact_id,
                    "access": dependency.source_access_relationship_id,
                }
            )
            if dependency.dependency_id != expected_dependency:
                raise ValueError("positioning dependency ID is forged")
            if dependency.side == "origin" and dependency.from_airport_fact_id != (
                support.original_origin_airport_fact_id
            ):
                raise ValueError("origin positioning must start at the support origin")
            if dependency.side == "destination" and dependency.to_airport_fact_id != (
                support.original_destination_airport_fact_id
            ):
                raise ValueError("destination positioning must end at the support destination")
            source_disposition = disposition_by_relationship.get(
                dependency.source_access_relationship_id
            )
            if source_disposition is None:
                raise ValueError("positioning dependency cites an unknown access relationship")
            source = source_disposition.source_relationship
            if dependency.side == "origin":
                valid_source = (
                    source.relationship_type is SupplementalStrategyType.ORIGIN_ACCESS
                    and source.original_origin_airport_fact_id
                    == support.original_origin_airport_fact_id
                    and source.original_destination_airport_fact_id
                    == support.original_destination_airport_fact_id
                    and source.candidate_airport_fact_id == dependency.to_airport_fact_id
                )
            else:
                valid_source = (
                    source.relationship_type is SupplementalStrategyType.DESTINATION_ACCESS
                    and source.original_origin_airport_fact_id
                    == support.original_origin_airport_fact_id
                    and source.original_destination_airport_fact_id
                    == support.original_destination_airport_fact_id
                    and source.candidate_airport_fact_id == dependency.from_airport_fact_id
                )
            if not valid_source:
                raise ValueError(
                    "positioning dependency must cite the exact support-pair access relationship"
                )
    linked_dependencies = {
        dependency_id
        for support in plan.support_alternatives
        for dependency_id in support.positioning_dependency_ids
    }
    if linked_dependencies != set(dependency_by_id):
        raise ValueError("every positioning dependency must be linked from one support")

    receipt_by_kind = {receipt.kind: receipt for receipt in plan.structural_limit_receipts}
    expected_limits = {
        CompilerStructuralLimitKind.ENDPOINT_PAIR_CROSS_PRODUCT: len(expected_pairs),
    }
    for kind, observed in expected_limits.items():
        limit_receipt = receipt_by_kind[kind]
        if (
            limit_receipt.observed != observed
            or limit_receipt.disposition != "within_limit"
            or limit_receipt.observed > limit_receipt.limit
        ):
            raise ValueError(f"{kind.value} structural-limit receipt does not recompute from plan input")


def _expected_plan_issues(
    plan: CompiledSearchPlan,
) -> tuple[StrategyCompilationIssue, ...]:
    issues: list[StrategyCompilationIssue] = []
    if plan.discovery_receipt.outcome in {
        GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE,
        GatewayDiscoveryOutcome.REJECTED_ALL,
        GatewayDiscoveryOutcome.GENERATION_FAILURE,
        GatewayDiscoveryOutcome.VALIDATION_FAILURE,
    }:
        outcome = plan.discovery_receipt.outcome.value
        issues.append(
            StrategyCompilationIssue(
                code=f"gateway_{outcome}",
                stage="compilation",
                severity="reduced_coverage",
                message=(
                    f"gateway discovery ended with {outcome}; mandatory coverage is retained"
                ),
            )
        )
    issues.extend(
        StrategyCompilationIssue(
            code=item.reason_codes[0],
            stage="compilation",
            severity="reduced_coverage",
            message="accepted supplemental relationship was not materialized",
            source_relationship_id=item.relationship_id,
        )
        for item in plan.relationship_dispositions
        if item.disposition is RelationshipDispositionKind.UNSUPPORTED_RULE
    )
    return tuple(issues)


def _canonical_digest(value: object) -> str:
    value = _canonical_json_value(value)
    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _canonical_json_value(value: object) -> object:
    if hasattr(value, "model_dump"):
        return cast(Any, value).model_dump(mode="json", round_trip=True)
    if isinstance(value, dict):
        return {str(key): _canonical_json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_json_value(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _logical_query_identity_payload(query: LogicalAwardQuery) -> dict[str, object]:
    envelope = query.date_envelope.model_dump(mode="json", round_trip=True)

    def without_provenance(item: object) -> dict[str, object]:
        value = cast(
            dict[str, object],
            cast(Any, item).model_dump(mode="json", round_trip=True),
        )
        value.pop("field_provenance", None)
        return value

    return {
        "query_identity_version": "logical-award-query-semantics-v1",
        "origin_airport_fact_id": query.origin_airport_fact_id,
        "destination_airport_fact_id": query.destination_airport_fact_id,
        "scope": query.scope,
        "date_envelope": {
            key: envelope[key]
            for key in ("start", "end", "inclusive", "basis", "timezone")
        },
        "requested_cabins": [item.value for item in query.requested_cabins],
        "award_mode": query.award_mode,
        "connection_semantics": query.connection_semantics,
        "filter_obligations": [without_provenance(item) for item in query.filter_obligations],
        "result_validation_obligations": [
            without_provenance(item) for item in query.result_validation_obligations
        ],
    }


class SearchPlanningOutcome(str, Enum):
    PLANNED = "planned"
    REDUCED_COVERAGE = "reduced_coverage"
    UNPLANNABLE = "unplannable"
    EVIDENCE_FAILURE = "evidence_failure"


class SearchPlanningResult(PlanningContractModel):
    outcome: SearchPlanningOutcome
    plan: CompiledSearchPlan | None = None
    issues: tuple[StrategyCompilationIssue, ...] = ()
    structural_limit_receipts: tuple[CompilerStructuralLimitReceipt, ...] = ()

    @model_validator(mode="after")
    def validate_outcome(self) -> SearchPlanningResult:
        has_plan = self.plan is not None
        if has_plan != (
            self.outcome
            in {
            SearchPlanningOutcome.PLANNED,
            SearchPlanningOutcome.REDUCED_COVERAGE,
            }
        ):
            raise ValueError("only planned outcomes may carry a compiled plan")
        if self.plan is not None:
            if self.structural_limit_receipts != self.plan.structural_limit_receipts:
                raise ValueError("result and plan structural-limit receipts must match exactly")
            if self.issues != self.plan.issues:
                raise ValueError("result issues must exactly match plan issues")
            expected_outcome = (
                SearchPlanningOutcome.REDUCED_COVERAGE
                if any(issue.severity == "reduced_coverage" for issue in self.plan.issues)
                else SearchPlanningOutcome.PLANNED
            )
            if self.outcome is not expected_outcome:
                raise ValueError("plan-bearing outcome must derive from plan issues")
        else:
            if not self.issues:
                raise ValueError("no-plan outcomes require at least one typed issue")
            expected_severity = (
                "unplannable"
                if self.outcome is SearchPlanningOutcome.UNPLANNABLE
                else "evidence_failure"
            )
            if any(issue.severity != expected_severity for issue in self.issues):
                raise ValueError("no-plan outcome and issue severities must agree")
            if self.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE and (
                self.structural_limit_receipts
            ):
                raise ValueError("evidence failures cannot carry structural-limit receipts")
            if any(
                receipt.disposition != "exceeded"
                for receipt in self.structural_limit_receipts
            ):
                raise ValueError(
                    "no-plan structural-limit receipts must record exceeded boundaries"
                )
        return self
