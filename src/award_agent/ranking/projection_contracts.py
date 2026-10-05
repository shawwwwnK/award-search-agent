"""Compact, immutable factual export from the trusted Ranking M2 result."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from award_agent.domain.clarification_session import EffectiveRequest
from award_agent.providers.contracts import (
    EvidenceRef,
    RawField,
    Sha256,
    ValidationFinding,
)
from award_agent.search_planning.compilation_contracts import (
    CompilationCoverage,
    EndpointSelectionProjection,
    IdentifiedDeferredConstraint,
    StrategyCompilationIssue,
)
from award_agent.search_planning.contracts import PlanningContractModel
from award_agent.search_planning.gateway_discovery import GatewayDiscoveryIssue

from .contracts import MatchAccounting, MatchReason, PairingReceipt
from .style_contracts import (
    CostComponent,
    CurrencyConversionSnapshot,
    RankingStylePolicy,
    StyleIndexes,
)


class ProjectedTime(PlanningContractModel):
    instant: datetime | None = None
    local_iso: str | None = None
    timezone: str | None = None


class ProjectedLeg(PlanningContractModel):
    origin: str
    destination: str
    departure: ProjectedTime
    arrival: ProjectedTime
    carrier: RawField
    flight_number: RawField
    cabin: RawField


class SolutionComponent(PlanningContractModel):
    observation_id: str
    kind: Literal["award_summary", "award_itinerary", "cash_itinerary"]
    provider: str
    backend: str
    provider_version: str
    provider_record_id: str | None
    query_id: str
    logical_query_ids: tuple[str, ...]
    logical_use_ids: tuple[str, ...]
    strategy_ids: tuple[str, ...]
    origin: str
    destination: str
    departure_date: date | None
    departure: ProjectedTime
    arrival: ProjectedTime
    airport_sequence: tuple[str, ...]
    legs: tuple[ProjectedLeg, ...]
    retrieved_at: datetime
    provider_updated_at: RawField
    requested_travelers: int
    requested_cabins: tuple[str, ...]
    returned_travelers: RawField
    cabin: RawField
    program: RawField
    points: RawField
    taxes_fees: RawField
    taxes_fees_unit: Literal["major", "minor", "unknown"]
    tax_currency: RawField
    seats: RawField
    cash_amount: RawField
    cash_currency: RawField
    price_scope: Literal["per_traveler", "party", "unknown"]
    duration_minutes: RawField
    stops: RawField
    carriers: tuple[str, ...]
    mixed_cabin_pct: RawField
    reported_flight_numbers: RawField
    findings: tuple[ValidationFinding, ...]


class ReasonSet(PlanningContractModel):
    reason_set_id: Sha256
    reasons: tuple[MatchReason, ...]


class CostComponentRecord(PlanningContractModel):
    cost_component_id: Sha256
    component: CostComponent


class ProjectedJourneyCost(PlanningContractModel):
    component_ids: tuple[Sha256, ...]
    known_subtotal_usd: Decimal | None
    complete_usd: Decimal | None
    exact_subtotal_numerator: int | None
    exact_subtotal_denominator: int | None
    missing_parts: tuple[str, ...]
    completeness: Literal["complete", "partial", "unavailable"]


class CostRecord(PlanningContractModel):
    cost_id: Sha256
    cost: ProjectedJourneyCost


class AssessmentRecord(PlanningContractModel):
    assessment_id: Sha256
    style: Literal["time", "cost", "premium"]
    state: Literal["member", "possible", "not_member", "undetermined"]
    feature_numeric: Decimal | None = None
    feature_label: str | None = None
    reference_value: Decimal | None = None
    threshold: Decimal | None = None
    exact_threshold_numerator: int | None = None
    exact_threshold_denominator: int | None = None
    exact_threshold_unit: Literal["microseconds", "usd"] | None = None
    reasons: tuple[str, ...] = ()
    validation_needs: tuple[str, ...] = ()


class SolutionAlternative(PlanningContractModel):
    candidate_id: Sha256
    option_family_id: Sha256
    topology: Literal["direct_award", "cash_access_award", "award_cash_egress"]
    status: Literal["admitted", "conditional", "rejected", "research_lead"]
    award_observation_id: str
    cash_observation_id: str | None
    strategy_id: str | None
    positioning_reason: str | None
    original_origin: str
    original_destination: str
    departure: ProjectedTime
    arrival: ProjectedTime
    original_departure_date: date | None
    transfer_airport: str | None
    transfer_minutes: int | None
    transfer_local_day_offset: int | None
    price_completeness: Literal["known", "partial", "unknown"]
    booking_obligation: Literal["single_award", "separate_tickets_unverified"]
    reason_set_id: Sha256
    elapsed_minutes: Decimal | None = None
    elapsed_microseconds: int | None = None
    award_cabin: RawField
    premium_economy_addon: bool
    cost_id: Sha256 | None = None
    assessment_ids: tuple[Sha256, ...] = ()


class CoverageGroup(PlanningContractModel):
    kind: str
    status: str
    reason: str
    stream_complete: bool
    pair_coverage: str
    unit_ids: tuple[str, ...]
    logical_query_ids: tuple[str, ...]
    strategy_ids: tuple[str, ...]
    planned_query_ids: tuple[str, ...]
    query_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    transport_ids: tuple[str, ...]
    routes_and_dates: tuple[str, ...]


class StrategyNote(PlanningContractModel):
    strategy_id: str
    reason: str
    material_uncertainty: str | None
    deferred_constraint_ids: tuple[str, ...]
    support_alternative_ids: tuple[str, ...]


class TransportFindingRecord(PlanningContractModel):
    transport_id: str
    query_id: str
    status: str
    findings: tuple[ValidationFinding, ...]


class SolutionView(PlanningContractModel):
    contract_version: Literal["solution-view-v1"] = "solution-view-v1"
    request: EffectiveRequest
    endpoint_selections: tuple[EndpointSelectionProjection, ...]
    policy: RankingStylePolicy
    fx_snapshot: CurrencyConversionSnapshot
    matching_policy_version: str
    provider_status: str
    components: tuple[SolutionComponent, ...]
    alternatives: tuple[SolutionAlternative, ...]
    reason_sets: tuple[ReasonSet, ...]
    cost_components: tuple[CostComponentRecord, ...]
    costs: tuple[CostRecord, ...]
    assessments: tuple[AssessmentRecord, ...]
    indexes: StyleIndexes
    comparison_pool_ids: tuple[Sha256, ...]
    time_reference_minutes: Decimal | None
    time_reference_microseconds: int | None
    cost_reference_usd: Decimal | None
    cost_reference_numerator: int | None
    cost_reference_denominator: int | None
    direct_cash_observation_ids: tuple[str, ...]
    award_summary_observation_ids: tuple[str, ...]
    unmatched_award_observation_ids: tuple[str, ...]
    unpaired_positioning_observation_ids: tuple[str, ...]
    pairing_receipts: tuple[PairingReceipt, ...]
    match_accounting: MatchAccounting
    coverage_groups: tuple[CoverageGroup, ...]
    planning_strategy_notes: tuple[StrategyNote, ...]
    planning_issues: tuple[StrategyCompilationIssue, ...]
    planning_deferred_constraints: tuple[IdentifiedDeferredConstraint, ...]
    planning_coverage: CompilationCoverage
    discovery_limitations: tuple[str, ...]
    discovery_issues: tuple[GatewayDiscoveryIssue, ...]
    provider_findings: tuple[ValidationFinding, ...]
    execution_findings: tuple[ValidationFinding, ...]
    transport_findings: tuple[TransportFindingRecord, ...]


class CandidateSourceMap(PlanningContractModel):
    candidate_id: Sha256
    status: str
    award_observation_id: str
    cash_observation_id: str | None
    award_query_id: str
    cash_query_id: str | None
    logical_award_query_ids: tuple[str, ...]
    support_id: str | None
    positioning_dependency_id: str | None
    activation_observation_ids: tuple[str, ...]
    reason_set_id: Sha256
    cost_id: Sha256 | None
    assessment_ids: tuple[Sha256, ...]


class ObservationSourceMap(PlanningContractModel):
    observation_id: str
    query_id: str
    evidence: tuple[EvidenceRef, ...]
    raw_departure_local: str | None
    raw_arrival_local: str | None
    origin_timezone: str | None
    destination_timezone: str | None
    leg_raw_local_times: tuple[tuple[str | None, str | None], ...]
    leg_timezones: tuple[tuple[str | None, str | None], ...]


class CoverageSourceMap(PlanningContractModel):
    unit_id: str
    group_index: int = Field(ge=0)
    logical_query_ids: tuple[str, ...]
    strategy_id: str | None
    query_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    transport_ids: tuple[str, ...]


class ProjectionReceipt(PlanningContractModel):
    contract_version: Literal["solution-projection-receipt-v1"] = "solution-projection-receipt-v1"
    source_digest: Sha256
    view_digest: Sha256
    ranked_contract_version: str
    matched_contract_version: str
    provider_contract_version: str
    plan_digest: Sha256
    provider_run_id: str
    policy_digest: Sha256
    fx_snapshot_digest: Sha256
    candidate_sources: tuple[CandidateSourceMap, ...]
    observation_sources: tuple[ObservationSourceMap, ...]
    coverage_sources: tuple[CoverageSourceMap, ...]
    total_candidates: int = Field(ge=0)
    eligible_alternatives: int = Field(ge=0)


class SolutionProjection(PlanningContractModel):
    view: SolutionView
    receipt: ProjectionReceipt

    @model_validator(mode="after")
    def reference_integrity(self) -> SolutionProjection:
        from award_agent.providers.contracts import content_digest

        view = self.view
        receipt = self.receipt
        alternatives = {item.candidate_id: item for item in view.alternatives}
        components = {item.observation_id for item in view.components}
        reasons = {item.reason_set_id for item in view.reason_sets}
        costs = {item.cost_id for item in view.costs}
        assessments = {item.assessment_id for item in view.assessments}
        if len(alternatives) != len(view.alternatives) or len(components) != len(view.components):
            raise ValueError("duplicate projected candidate or observation")
        if any(len({getattr(item, field) for item in table}) != len(table)
               for table, field in (
                   (view.reason_sets, "reason_set_id"),
                   (view.cost_components, "cost_component_id"),
                   (view.costs, "cost_id"),
                   (view.assessments, "assessment_id"),
               )):
            raise ValueError("duplicate projected fact identity")
        if any(item.award_observation_id not in components or (
            item.cash_observation_id is not None and item.cash_observation_id not in components
        ) or item.reason_set_id not in reasons or (
            item.cost_id is not None and item.cost_id not in costs
        ) or not set(item.assessment_ids) <= assessments for item in view.alternatives):
            raise ValueError("projected alternative has a missing fact reference")
        cost_component_ids = {item.cost_component_id for item in view.cost_components}
        if any(not set(record.cost.component_ids) <= cost_component_ids
               for record in view.costs):
            raise ValueError("projected cost has a missing component reference")
        if len({item.candidate_id for item in receipt.candidate_sources}) != len(
            receipt.candidate_sources
        ) or {item.candidate_id for item in receipt.candidate_sources} != set(alternatives) or (
            {item.observation_id for item in receipt.observation_sources} != components
            or len({item.observation_id for item in receipt.observation_sources}) != len(
                receipt.observation_sources
            )
            or receipt.total_candidates != len(view.alternatives)
            or receipt.eligible_alternatives != sum(
                item.status in {"admitted", "conditional"} for item in view.alternatives
            )
            or receipt.view_digest != content_digest(view)
        ):
            raise ValueError("projection receipt does not bind the complete view")
        if any(
            (source.status, source.award_observation_id, source.cash_observation_id,
             source.reason_set_id, source.cost_id, source.assessment_ids)
            != (alternative.status, alternative.award_observation_id,
                alternative.cash_observation_id, alternative.reason_set_id,
                alternative.cost_id, alternative.assessment_ids)
            for source in receipt.candidate_sources
            for alternative in (alternatives[source.candidate_id],)
        ):
            raise ValueError("candidate source map differs from projected alternative")
        observation_queries = {
            item.observation_id: item.query_id for item in receipt.observation_sources
        }
        if any(source.award_query_id != observation_queries[source.award_observation_id]
               or (source.cash_observation_id is not None and
                   source.cash_query_id != observation_queries[source.cash_observation_id])
               for source in receipt.candidate_sources):
            raise ValueError("candidate source query differs from observation source")
        expected_coverage = {
            unit_id: group_index
            for group_index, group in enumerate(view.coverage_groups)
            for unit_id in group.unit_ids
        }
        actual_coverage = {
            source.unit_id: source.group_index for source in receipt.coverage_sources
        }
        if len(expected_coverage) != sum(len(group.unit_ids) for group in view.coverage_groups) or (
            len(actual_coverage) != len(receipt.coverage_sources)
            or actual_coverage != expected_coverage
        ):
            raise ValueError("coverage source map differs from projected groups")
        for source in receipt.coverage_sources:
            group = view.coverage_groups[source.group_index]
            if (
                not set(source.query_ids) <= set(group.query_ids)
                or not set(source.observation_ids) <= set(group.observation_ids)
                or not set(source.transport_ids) <= set(group.transport_ids)
                or not set(source.logical_query_ids) <= set(group.logical_query_ids)
                or (source.strategy_id is not None
                    and source.strategy_id not in group.strategy_ids)
            ):
                raise ValueError("coverage source details differ from projected group")
        return self
