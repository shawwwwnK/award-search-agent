"""Resolve trusted Ranking facts for structured Results and local exploration."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from itertools import pairwise
from typing import Literal

from award_agent.providers.contracts import RawField
from award_agent.ranking.contracts import MatchReason
from award_agent.ranking.projection_contracts import (
    AssessmentRecord,
    ProjectedJourneyCost,
    ProjectedLeg,
    ProjectedTime,
    SolutionAlternative,
    SolutionComponent,
    SolutionProjection,
)

from .currency import FxAcquisition, journey_money, observed_money
from .workspace_contracts import (
    AwardGroup,
    ComponentView,
    ComponentViewV1,
    ConnectionView,
    FlightLegView,
    GroupSelection,
    JourneyInternal,
    JourneyView,
    LeadView,
    LocalFlightTime,
    WorkspaceEvidence,
    WorkspaceSourceBinding,
)

AVAILABILITY_GUIDANCE = (
    "Some results aren't real-time. Confirm availability and current prices "
    "on the official booking sites before booking."
)
SortKey = Literal["shortest", "departure", "lowest_cash", "fewest_points", "comparison_cost"]


def _local_date(value: ProjectedTime) -> datetime | None:
    if value.local_iso is None or value.timezone is None:
        return None
    try:
        return datetime.fromisoformat(value.local_iso)
    except ValueError:
        return None


def _time(value: ProjectedTime, initial_date: datetime | None) -> LocalFlightTime:
    local = _local_date(value)
    day_change = (local.date() - initial_date.date()).days if (
        local is not None and initial_date is not None
    ) else None
    return LocalFlightTime(
        instant=value.instant, local_iso=value.local_iso,
        timezone=value.timezone, day_change=day_change,
    )


def _leg(source: ProjectedLeg, observation_id: str,
         component_kind: Literal["award_summary", "award_itinerary", "cash_itinerary"],
         reported: bool,
         initial_date: datetime | None) -> FlightLegView:
    return FlightLegView(
        observation_id=observation_id, component_kind=component_kind,
        reported=reported,
        origin=source.origin, destination=source.destination,
        departure=_time(source.departure, initial_date),
        arrival=_time(source.arrival, initial_date),
        carrier=source.carrier, flight_number=source.flight_number, cabin=source.cabin,
    )


def _component_legs(component: SolutionComponent,
                    initial_date: datetime | None) -> tuple[FlightLegView, ...]:
    if component.legs:
        return tuple(_leg(leg, component.observation_id, component.kind, True, initial_date)
                     for leg in component.legs)
    # A component with no leg report still has an overall route. This is one
    # opaque segment; it never fabricates a nonstop flight or its carrier.
    return (_leg(ProjectedLeg(
        origin=component.origin, destination=component.destination,
        departure=component.departure, arrival=component.arrival,
        carrier=RawField(), flight_number=RawField(), cabin=component.cabin,
    ), component.observation_id, component.kind, False, initial_date),)


def _connection(arriving: FlightLegView, departing: FlightLegView) -> ConnectionView:
    airport = arriving.destination if arriving.destination == departing.origin else None
    kind: Literal["award_connection", "cash_connection", "separate_booking"] = (
        "separate_booking" if arriving.observation_id != departing.observation_id
        else "cash_connection" if arriving.component_kind == "cash_itinerary"
        else "award_connection"
    )
    wait: int | None = None
    reason: str | None = None
    if airport is None:
        reason = "airport_continuity_unknown"
    elif arriving.arrival.instant is None or departing.departure.instant is None:
        reason = "timing_unknown"
    elif (arriving.arrival.instant.tzinfo is None
          or departing.departure.instant.tzinfo is None):
        reason = "timezone_unknown"
    else:
        seconds = (departing.departure.instant - arriving.arrival.instant).total_seconds()
        if seconds < 0:
            reason = "chronology_inconsistent"
        elif seconds % 60:
            reason = "subminute_precision"
        else:
            wait = int(seconds // 60)
    return ConnectionView(
        airport=airport, arriving_observation_id=arriving.observation_id,
        departing_observation_id=departing.observation_id,
        wait_minutes=wait, kind=kind, unknown_reason=reason,
    )


def _journey(alternative: SolutionAlternative,
             components: Mapping[str, SolutionComponent],
             reasons: Mapping[str, tuple[MatchReason, ...]],
             costs: Mapping[str, ProjectedJourneyCost],
             assessments: Mapping[str, AssessmentRecord],
             projection: SolutionProjection) -> JourneyView:
    assert alternative.status in {"admitted", "conditional"}
    award = components[alternative.award_observation_id]
    cash = (components[alternative.cash_observation_id]
            if alternative.cash_observation_id is not None else None)
    ordered = ((cash, award) if alternative.topology == "cash_access_award" else
               (award, cash) if alternative.topology == "award_cash_egress" else
               (award,))
    initial_date = _local_date(alternative.departure)
    legs = tuple(leg for component in ordered if component is not None
                 for leg in _component_legs(component, initial_date))
    connections = tuple(_connection(first, second)
                        for first, second in pairwise(legs))
    reason_rows = reasons[alternative.reason_set_id]
    cost = costs.get(alternative.cost_id) if alternative.cost_id is not None else None
    heuristic_cost_usd = (cost.complete_usd if cost is not None
                          and cost.completeness == "complete" else None)
    all_styles: tuple[Literal["time", "cost", "premium"], ...] = (
        "time", "cost", "premium",
    )
    styles = tuple(style for style in all_styles if any(
        assessments[item].style == style and assessments[item].state == "member"
        for item in alternative.assessment_ids
    ))
    travelers = projection.view.request.travelers
    if travelers is None:
        raise ValueError("workspace monetary scope requires known traveler count")
    return JourneyView(
        candidate_id=alternative.candidate_id,
        group_id=alternative.option_family_id, topology=alternative.topology,
        origin=alternative.original_origin, destination=alternative.original_destination,
        original_departure_date=alternative.original_departure_date,
        departure=_time(alternative.departure, initial_date),
        arrival=_time(alternative.arrival, initial_date),
        elapsed_minutes=alternative.elapsed_minutes,
        award_observation_id=alternative.award_observation_id,
        cash_observation_id=alternative.cash_observation_id,
        legs=legs, connections=connections,
        award_program=award.program, award_cabin=alternative.award_cabin,
        award_points=award.points,
        money=journey_money(award, cash, projection.view.fx_snapshot, travelers),
        booking_obligation=alternative.booking_obligation,
        price_completeness=alternative.price_completeness,
        styles=styles,
        heuristic_cost_usd=heuristic_cost_usd,
        internal=JourneyInternal(
            status=alternative.status,
            reason_codes=tuple(reason.code for reason in reason_rows),
            reason_details=tuple(reason.detail for reason in reason_rows),
        ),
    )


def resolve_workspace(projection: SolutionProjection, *,
                      fx_acquisition: FxAcquisition | None = None,
                      version: Literal["v1", "v2"] = "v2") -> WorkspaceEvidence:
    """Expose every exact eligible journey independently of writer outcomes."""
    # The projection's own contract verifies all source identities and its view
    # digest. Results deliberately does not repeat Ranking eligibility policy.
    trusted = SolutionProjection.model_validate(projection.model_dump(mode="json"))
    view, receipt = trusted.view, trusted.receipt
    if fx_acquisition is not None and fx_acquisition.snapshot != view.fx_snapshot:
        raise ValueError("FX acquisition snapshot differs from the projected run")
    if version not in {"v1", "v2"}:
        raise ValueError("unsupported workspace evidence version")
    components = {item.observation_id: item for item in view.components}
    sources = {item.observation_id: item for item in receipt.observation_sources}
    reasons = {item.reason_set_id: item.reasons for item in view.reason_sets}
    costs = {item.cost_id: item.cost for item in view.costs}
    assessments = {item.assessment_id: item for item in view.assessments}
    eligible = tuple(item for item in view.alternatives
                     if item.status in {"admitted", "conditional"})
    journeys = tuple(_journey(item, components, reasons, costs, assessments, trusted)
                     for item in eligible)
    groups_by_id: dict[str, list[JourneyView]] = defaultdict(list)
    for journey in journeys:
        groups_by_id[journey.group_id].append(journey)
    groups = tuple(AwardGroup(
        group_id=group_id,
        member_ids=tuple(sorted(item.candidate_id for item in members)),
        representative_id=min(members, key=lambda item: (
            item.elapsed_minutes is None,
            item.elapsed_minutes if item.elapsed_minutes is not None else Decimal(0),
            item.candidate_id,
        )).candidate_id,
    ) for group_id, members in sorted(groups_by_id.items()))
    travelers = view.request.travelers
    if travelers is None:
        raise ValueError("workspace monetary scope requires known traveler count")
    component_views_v1 = tuple(ComponentViewV1(
        observation_id=item.observation_id, kind=item.kind,
        provider=item.provider, backend=item.backend,
        provider_version=item.provider_version,
        provider_record_id=item.provider_record_id, query_id=item.query_id,
        retrieved_at=item.retrieved_at, provider_updated_at=item.provider_updated_at,
        origin=item.origin, destination=item.destination,
        program=item.program, cabin=item.cabin, points=item.points,
        taxes_fees=item.taxes_fees, taxes_fees_unit=item.taxes_fees_unit,
        tax_currency=item.tax_currency, cash_amount=item.cash_amount,
        cash_currency=item.cash_currency,
        money=observed_money(
            item, "cash_fare" if item.kind == "cash_itinerary" else "award_taxes",
            view.fx_snapshot, travelers,
        ),
        price_scope=item.price_scope,
        mixed_cabin_pct=item.mixed_cabin_pct,
        airport_sequence=item.airport_sequence,
        stops=item.stops,
        duration_minutes=item.duration_minutes,
        returned_travelers=item.returned_travelers, seats=item.seats,
        carriers=item.carriers,
        reported_flight_numbers=item.reported_flight_numbers,
        legs=_component_legs(item, _local_date(item.departure)),
        evidence=sources[item.observation_id].evidence,
    ) for item in view.components)
    component_views: tuple[ComponentViewV1 | ComponentView, ...] = (
        component_views_v1 if version == "v1" else
        tuple(ComponentView.model_validate(
            component.model_dump(mode="python") | {"departure_date": source.departure_date}
        ) for source, component in zip(view.components, component_views_v1, strict=True))
    )
    candidate_leads = tuple(LeadView(
        reference_id=item.candidate_id, candidate_id=item.candidate_id,
        award_observation_id=item.award_observation_id,
        cash_observation_id=item.cash_observation_id,
        missing_information=tuple(reason.code for reason in reasons[item.reason_set_id]
                                  if reason.state != "passed"),
        explanations=tuple(reason.detail for reason in reasons[item.reason_set_id]
                           if reason.state != "passed"),
    ) for item in view.alternatives if item.status == "research_lead")
    unmatched_awards = tuple(LeadView(
        reference_id=observation_id, candidate_id=None,
        award_observation_id=observation_id, cash_observation_id=None,
        missing_information=("no_complete_matched_journey",),
        explanations=("No complete award-led journey was established from this observation.",),
    ) for observation_id in view.unmatched_award_observation_ids)
    unmatched_ids = set(view.unmatched_award_observation_ids)
    award_summaries = tuple(LeadView(
        reference_id=observation_id, candidate_id=None,
        award_observation_id=observation_id, cash_observation_id=None,
        missing_information=("itinerary_schedule_incomplete",),
        explanations=("This award observation lacks a complete itinerary schedule.",),
    ) for observation_id in view.award_summary_observation_ids
       if observation_id not in unmatched_ids)
    unpaired_cash = tuple(LeadView(
        reference_id=observation_id, candidate_id=None,
        award_observation_id=None, cash_observation_id=observation_id,
        missing_information=("no_complete_matched_journey",),
        explanations=("No complete award-led journey was established from this observation.",),
    ) for observation_id in view.unpaired_positioning_observation_ids
       if observation_id not in view.direct_cash_observation_ids)
    return WorkspaceEvidence(
        contract_version=("results-workspace-evidence-v1" if version == "v1"
                          else "results-workspace-evidence-v2"),
        source_binding=WorkspaceSourceBinding(
            source_digest=receipt.source_digest, view_digest=receipt.view_digest,
            fx_snapshot_digest=receipt.fx_snapshot_digest,
            provider_run_id=receipt.provider_run_id,
        ),
        source=trusted, fx_acquisition=fx_acquisition,
        journeys=journeys, groups=groups, components=component_views,
        direct_cash_benchmark_ids=view.direct_cash_observation_ids,
        leads=candidate_leads + unmatched_awards + award_summaries + unpaired_cash,
        availability_guidance=AVAILABILITY_GUIDANCE,
    )


def select_groups(evidence: WorkspaceEvidence, *,
                  candidate_ids: set[str] | None = None,
                  sort: SortKey = "shortest",
                  program: str | None = None) -> tuple[GroupSelection, ...]:
    """Choose one whole surviving journey per group, without changing evidence."""
    journey_by_id = {item.candidate_id: item for item in evidence.journeys}
    if candidate_ids is not None and not candidate_ids <= journey_by_id.keys():
        raise ValueError("filter references an unavailable eligible journey")
    if sort == "fewest_points" and not program:
        raise ValueError("fewest-points sort requires one award program")

    def key(item: JourneyView) -> tuple[bool, Decimal | float, str]:
        if sort == "shortest":
            value: Decimal | float | None = item.elapsed_minutes
        elif sort == "departure":
            instant = item.departure.instant
            value = instant.timestamp() if instant is not None and instant.tzinfo else None
        elif sort == "comparison_cost":
            value = item.heuristic_cost_usd
        elif sort == "lowest_cash":
            value = item.money.observed_cash_per_traveler_usd
        elif sort == "fewest_points":
            value = (item.money.points_per_traveler
                     if item.money.points_program == program else None)
        else:
            raise ValueError(f"unsupported workspace sort: {sort}")
        return (value is None, value if value is not None else Decimal(0), item.candidate_id)

    selected: list[GroupSelection] = []
    for group in evidence.groups:
        members = tuple(journey_by_id[member] for member in group.member_ids
                        if candidate_ids is None or member in candidate_ids)
        if not members:
            continue
        representative = min(members, key=key)
        selected.append(GroupSelection(
            group_id=group.group_id,
            member_ids=tuple(member.candidate_id for member in members),
            representative_id=representative.candidate_id,
            representative=representative,
        ))
    return tuple(sorted(selected, key=lambda group: key(group.representative)))
