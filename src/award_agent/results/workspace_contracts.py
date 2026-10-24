"""Source-bound factual data for the local Results workspace."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from award_agent.providers.contracts import EvidenceRef, RawField, Sha256
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.search_planning.contracts import PlanningContractModel

from .currency import FxAcquisition, JourneyMoney, MoneyAmount


class WorkspaceSourceBinding(PlanningContractModel):
    source_digest: Sha256
    view_digest: Sha256
    fx_snapshot_digest: Sha256
    provider_run_id: str


class LocalFlightTime(PlanningContractModel):
    instant: datetime | None
    local_iso: str | None
    timezone: str | None
    day_change: int | None


class FlightLegView(PlanningContractModel):
    observation_id: str
    component_kind: Literal["award_summary", "award_itinerary", "cash_itinerary"]
    reported: bool
    origin: str
    destination: str
    departure: LocalFlightTime
    arrival: LocalFlightTime
    carrier: RawField
    flight_number: RawField
    cabin: RawField


class ConnectionView(PlanningContractModel):
    airport: str | None
    arriving_observation_id: str
    departing_observation_id: str
    wait_minutes: int | None
    kind: Literal["award_connection", "cash_connection", "separate_booking"]
    unknown_reason: str | None = None


class ComponentViewV1(PlanningContractModel):
    observation_id: str
    kind: Literal["award_summary", "award_itinerary", "cash_itinerary"]
    provider: str
    backend: str
    provider_version: str
    provider_record_id: str | None
    query_id: str
    retrieved_at: datetime
    provider_updated_at: RawField
    origin: str
    destination: str
    program: RawField
    cabin: RawField
    points: RawField
    taxes_fees: RawField
    taxes_fees_unit: Literal["major", "minor", "unknown"]
    tax_currency: RawField
    cash_amount: RawField
    cash_currency: RawField
    money: MoneyAmount
    price_scope: Literal["per_traveler", "party", "unknown"]
    mixed_cabin_pct: RawField
    airport_sequence: tuple[str, ...]
    stops: RawField
    duration_minutes: RawField
    returned_travelers: RawField
    seats: RawField
    carriers: tuple[str, ...]
    reported_flight_numbers: RawField
    legs: tuple[FlightLegView, ...]
    evidence: tuple[EvidenceRef, ...]


class ComponentView(ComponentViewV1):
    """Current component view also carries a source-known departure date."""

    departure_date: date | None


class JourneyInternal(PlanningContractModel):
    status: Literal["admitted", "conditional"]
    reason_codes: tuple[str, ...]
    reason_details: tuple[str, ...]


class JourneyView(PlanningContractModel):
    candidate_id: Sha256
    group_id: Sha256
    topology: Literal["direct_award", "cash_access_award", "award_cash_egress"]
    origin: str
    destination: str
    original_departure_date: date | None
    departure: LocalFlightTime
    arrival: LocalFlightTime
    elapsed_minutes: Decimal | None
    award_observation_id: str
    cash_observation_id: str | None
    legs: tuple[FlightLegView, ...]
    connections: tuple[ConnectionView, ...]
    award_program: RawField
    award_cabin: RawField
    award_points: RawField
    money: JourneyMoney
    booking_obligation: Literal["single_award", "separate_tickets_unverified"]
    price_completeness: Literal["known", "partial", "unknown"]
    styles: tuple[Literal["time", "cost", "premium"], ...]
    heuristic_cost_usd: Decimal | None
    internal: JourneyInternal


class AwardGroup(PlanningContractModel):
    group_id: Sha256
    member_ids: tuple[Sha256, ...] = Field(min_length=1)
    representative_id: Sha256

    @model_validator(mode="after")
    def representative_is_member(self) -> AwardGroup:
        if self.representative_id not in self.member_ids:
            raise ValueError("group representative must be an actual member")
        return self


class LeadView(PlanningContractModel):
    reference_id: str
    candidate_id: Sha256 | None
    award_observation_id: str | None
    cash_observation_id: str | None
    missing_information: tuple[str, ...]
    explanations: tuple[str, ...]


class WorkspaceEvidence(PlanningContractModel):
    contract_version: Literal[
        "results-workspace-evidence-v1", "results-workspace-evidence-v2"
    ] = "results-workspace-evidence-v2"
    source_binding: WorkspaceSourceBinding
    source: SolutionProjection
    fx_acquisition: FxAcquisition | None = None
    journeys: tuple[JourneyView, ...]
    groups: tuple[AwardGroup, ...]
    components: tuple[ComponentViewV1 | ComponentView, ...]
    direct_cash_benchmark_ids: tuple[str, ...]
    leads: tuple[LeadView, ...]
    availability_guidance: str

    @model_validator(mode="after")
    def versioned_components(self) -> WorkspaceEvidence:
        if self.contract_version == "results-workspace-evidence-v1":
            if any(type(item) is not ComponentViewV1 for item in self.components):
                raise ValueError("workspace v1 requires the original component shape")
        elif any(type(item) is not ComponentView for item in self.components):
            raise ValueError("workspace v2 requires source departure dates")
        return self


class GroupSelection(PlanningContractModel):
    group_id: Sha256
    member_ids: tuple[Sha256, ...]
    representative_id: Sha256
    representative: JourneyView
