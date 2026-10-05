"""Pure factual projection of a trusted ranked journey set."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from award_agent.providers.contracts import ProviderObservation, RawField, content_digest

from .projection_contracts import (
    AssessmentRecord,
    CandidateSourceMap,
    CostComponentRecord,
    CostRecord,
    CoverageGroup,
    CoverageSourceMap,
    ObservationSourceMap,
    ProjectedJourneyCost,
    ProjectedLeg,
    ProjectedTime,
    ProjectionReceipt,
    ReasonSet,
    SolutionAlternative,
    SolutionComponent,
    SolutionProjection,
    SolutionView,
    StrategyNote,
    TransportFindingRecord,
)
from .style_contracts import RankedJourneySet, StyleAssessment


def _time(instant: datetime | None, zone: str | None) -> ProjectedTime:
    if instant is None or zone is None:
        return ProjectedTime(instant=instant, timezone=zone)
    try:
        local = instant.astimezone(ZoneInfo(zone)).isoformat()
    except (ZoneInfoNotFoundError, ValueError):
        local = None
    return ProjectedTime(instant=instant, local_iso=local, timezone=zone)


def _component(observation: ProviderObservation, zones: dict[str, str]) -> SolutionComponent:
    def zone(airport: str, supplied: str | None) -> str | None:
        return supplied or zones.get(airport)

    legs = tuple(ProjectedLeg(
        origin=leg.origin,
        destination=leg.destination,
        departure=_time(leg.departure_instant, zone(leg.origin, leg.origin_timezone)),
        arrival=_time(leg.arrival_instant, zone(leg.destination, leg.destination_timezone)),
        carrier=leg.carrier,
        flight_number=leg.flight_number,
        cabin=leg.cabin,
    ) for leg in observation.legs)
    return SolutionComponent(
        observation_id=observation.observation_id,
        kind=observation.kind,
        provider=observation.provider,
        backend=observation.backend,
        provider_version=observation.provider_version,
        provider_record_id=observation.provider_record_id,
        query_id=observation.query_id,
        logical_query_ids=observation.logical_query_ids,
        logical_use_ids=observation.logical_use_ids,
        strategy_ids=observation.strategy_ids,
        origin=observation.origin,
        destination=observation.destination,
        departure_date=observation.departure_date,
        departure=_time(observation.departure_instant,
                        zone(observation.origin, observation.origin_timezone)),
        arrival=_time(observation.arrival_instant,
                      zone(observation.destination, observation.destination_timezone)),
        airport_sequence=observation.airport_sequence,
        legs=legs,
        retrieved_at=observation.retrieved_at,
        provider_updated_at=observation.provider_updated_at,
        requested_travelers=observation.requested_travelers,
        requested_cabins=observation.requested_cabins,
        returned_travelers=observation.returned_travelers,
        cabin=observation.cabin,
        program=observation.program,
        points=observation.points,
        taxes_fees=observation.taxes_fees,
        taxes_fees_unit=observation.taxes_fees_unit,
        tax_currency=observation.tax_currency,
        seats=observation.seats,
        cash_amount=observation.cash_amount,
        cash_currency=observation.cash_currency,
        price_scope=observation.price_scope,
        duration_minutes=observation.duration_minutes,
        stops=observation.stops,
        carriers=observation.carriers,
        mixed_cabin_pct=observation.raw_fields.get("MixedCabinPct", RawField()),
        reported_flight_numbers=observation.raw_fields.get("flightNumbers", RawField()),
        findings=observation.findings,
    )


def _assessment_record(assessment: StyleAssessment) -> AssessmentRecord:
    facts = assessment.model_dump(exclude={"candidate_id"}, mode="python")
    digest_facts = assessment.model_dump(exclude={"candidate_id"}, mode="json")
    return AssessmentRecord(assessment_id=content_digest(digest_facts), **facts)


def _coverage(ranked: RankedJourneySet) -> tuple[tuple[CoverageGroup, ...],
                                                  tuple[CoverageSourceMap, ...]]:
    execution = ranked.matched.provider_result.execution_plan
    by_unit = {unit.unit_id: unit for unit in execution.coverage_units}
    by_query = {query.query_id: query for query in execution.queries}
    plan = ranked.matched.plan
    logical_queries = {query.query_id: query for query in plan.logical_queries}
    airports = {airport.airport_id: airport.airport_iata for airport in plan.airport_directory}
    buckets: dict[tuple[str, str, str, bool, str], list] = defaultdict(list)
    for item in ranked.matched.provider_result.coverage:
        unit = by_unit[item.unit_id]
        bucket_key = (unit.kind, item.status, item.reason, item.stream_complete,
                      item.pair_coverage)
        buckets[bucket_key].append(item)
    groups: list[CoverageGroup] = []
    mappings: list[CoverageSourceMap] = []
    for key, items in sorted(buckets.items()):
        query_ids = tuple(sorted({qid for item in items for qid in item.query_ids}))
        planned_query_ids = tuple(sorted({
            candidate
            for item in items
            for candidate in (item.unit_id.removeprefix("cash:").removeprefix("detail:"),)
            if candidate in by_query
        }))
        logical_ids = tuple(sorted({lid for item in items
                                    for lid in by_unit[item.unit_id].logical_query_ids}))
        strategy_values = [by_unit[item.unit_id].strategy_id for item in items]
        strategy_ids = tuple(sorted(value for value in strategy_values if value is not None))
        observation_ids = tuple(sorted({oid for item in items for oid in item.observation_ids}))
        transport_ids = tuple(sorted({tid for item in items for tid in item.transport_ids}))
        physical_routes = {
            f"{origin}-{destination}:{query.start_date.isoformat()}..{query.end_date.isoformat()}"
            for qid in set(query_ids) | set(planned_query_ids)
            for query in (by_query[qid],)
            for origin in query.origins for destination in query.destinations
        }
        logical_routes = {
            f"{airports[query.origin_airport_fact_id]}-{airports[query.destination_airport_fact_id]}:"
            f"{query.date_envelope.start.isoformat()}..{query.date_envelope.end.isoformat()}"
            for lid in logical_ids for query in (logical_queries[lid],)
        }
        # A rectangle-batched physical query may include unrelated pairs.  For a
        # logical unit, its logical route is the only truthful coverage scope.
        routes = tuple(sorted(logical_routes if logical_ids else physical_routes))
        group_index = len(groups)
        groups.append(CoverageGroup(
            kind=key[0], status=key[1], reason=key[2],
            stream_complete=key[3], pair_coverage=key[4],
            unit_ids=tuple(item.unit_id for item in items),
            logical_query_ids=logical_ids, strategy_ids=strategy_ids,
            planned_query_ids=planned_query_ids,
            query_ids=query_ids, observation_ids=observation_ids,
            transport_ids=transport_ids, routes_and_dates=routes,
        ))
        mappings.extend(CoverageSourceMap(
            unit_id=item.unit_id, group_index=group_index,
            logical_query_ids=by_unit[item.unit_id].logical_query_ids,
            strategy_id=by_unit[item.unit_id].strategy_id,
            query_ids=item.query_ids, observation_ids=item.observation_ids,
            transport_ids=item.transport_ids,
        ) for item in items)
    return tuple(groups), tuple(mappings)


def project_solutions(ranked: RankedJourneySet) -> SolutionProjection:
    """Factor trusted M2 facts without changing candidate identity or ranking policy."""
    matched = ranked.matched
    provider = matched.provider_result
    zones = {airport.airport_iata: airport.timezone for airport in matched.plan.airport_directory}
    features = {feature.candidate_id: feature for feature in ranked.features}
    assessments_by_candidate: dict[str, list[StyleAssessment]] = defaultdict(list)
    assessment_records: dict[str, AssessmentRecord] = {}
    for assessment in ranked.assessments:
        assessments_by_candidate[assessment.candidate_id].append(assessment)
        record = _assessment_record(assessment)
        assessment_records.setdefault(record.assessment_id, record)
    reason_sets: dict[str, ReasonSet] = {}
    cost_components: dict[str, CostComponentRecord] = {}
    costs: dict[str, CostRecord] = {}
    alternatives: list[SolutionAlternative] = []
    sources: list[CandidateSourceMap] = []
    for journey in matched.journeys:
        feature = features[journey.candidate_id]
        reason_id = content_digest([reason.model_dump(mode="json") for reason in journey.reasons])
        reason_sets.setdefault(reason_id, ReasonSet(reason_set_id=reason_id,
                                                      reasons=journey.reasons))
        component_ids = []
        for component in feature.cost.components:
            component_id = content_digest(component)
            component_ids.append(component_id)
            cost_components.setdefault(component_id, CostComponentRecord(
                cost_component_id=component_id, component=component,
            ))
        projected_cost = ProjectedJourneyCost(
            component_ids=tuple(component_ids),
            known_subtotal_usd=feature.cost.known_subtotal_usd,
            complete_usd=feature.cost.complete_usd,
            exact_subtotal_numerator=feature.cost.exact_subtotal_numerator,
            exact_subtotal_denominator=feature.cost.exact_subtotal_denominator,
            missing_parts=feature.cost.missing_parts,
            completeness=feature.cost.completeness,
        )
        cost_id = content_digest(projected_cost)
        costs.setdefault(cost_id, CostRecord(cost_id=cost_id, cost=projected_cost))
        assessment_ids = tuple(_assessment_record(item).assessment_id
                               for item in assessments_by_candidate[journey.candidate_id])
        alternative = SolutionAlternative(
            candidate_id=journey.candidate_id,
            option_family_id=journey.option_family_id,
            topology=journey.topology,
            status=journey.status,
            award_observation_id=journey.award_observation_id,
            cash_observation_id=journey.cash_observation_id,
            strategy_id=journey.strategy_id,
            positioning_reason=journey.positioning_reason,
            original_origin=journey.original_origin,
            original_destination=journey.original_destination,
            departure=_time(journey.departure_instant, zones.get(journey.original_origin)),
            arrival=_time(journey.arrival_instant, zones.get(journey.original_destination)),
            original_departure_date=journey.original_departure_date,
            transfer_airport=journey.transfer_airport,
            transfer_minutes=journey.transfer_minutes,
            transfer_local_day_offset=journey.transfer_local_day_offset,
            price_completeness=journey.price_completeness,
            booking_obligation=journey.booking_obligation,
            reason_set_id=reason_id,
            elapsed_minutes=feature.elapsed_minutes,
            elapsed_microseconds=feature.elapsed_microseconds,
            award_cabin=feature.award_cabin,
            premium_economy_addon=feature.premium_economy_addon,
            cost_id=cost_id,
            assessment_ids=assessment_ids,
        )
        alternatives.append(alternative)
        sources.append(CandidateSourceMap(
            candidate_id=journey.candidate_id,
            status=journey.status,
            award_observation_id=journey.award_observation_id,
            cash_observation_id=journey.cash_observation_id,
            award_query_id=journey.award_query_id,
            cash_query_id=journey.cash_query_id,
            logical_award_query_ids=journey.logical_award_query_ids,
            support_id=journey.support_id,
            positioning_dependency_id=journey.positioning_dependency_id,
            activation_observation_ids=journey.activation_observation_ids,
            reason_set_id=reason_id,
            cost_id=cost_id,
            assessment_ids=assessment_ids,
        ))
    components = tuple(_component(observation, zones) for observation in provider.observations)
    observation_sources = tuple(ObservationSourceMap(
        observation_id=observation.observation_id,
        query_id=observation.query_id,
        evidence=observation.evidence,
        raw_departure_local=observation.departure_local,
        raw_arrival_local=observation.arrival_local,
        origin_timezone=observation.origin_timezone,
        destination_timezone=observation.destination_timezone,
        leg_raw_local_times=tuple((leg.departure_local, leg.arrival_local)
                                  for leg in observation.legs),
        leg_timezones=tuple((leg.origin_timezone, leg.destination_timezone)
                            for leg in observation.legs),
    ) for observation in provider.observations)
    coverage_groups, coverage_sources = _coverage(ranked)
    plan = matched.plan
    notes = tuple(StrategyNote(
        strategy_id=strategy.strategy_id,
        reason=strategy.reason,
        material_uncertainty=strategy.material_uncertainty,
        deferred_constraint_ids=strategy.deferred_constraint_ids,
        support_alternative_ids=strategy.support_alternative_ids,
    ) for strategy in plan.supplemental_strategies)
    view = SolutionView(
        request=matched.request,
        endpoint_selections=plan.endpoint_selections,
        policy=ranked.policy,
        fx_snapshot=ranked.fx_snapshot,
        matching_policy_version=matched.matching_policy_version,
        provider_status=provider.status,
        components=components,
        alternatives=tuple(alternatives),
        reason_sets=tuple(reason_sets.values()),
        cost_components=tuple(cost_components.values()),
        costs=tuple(costs.values()),
        assessments=tuple(assessment_records.values()),
        indexes=ranked.indexes,
        comparison_pool_ids=ranked.comparison_pool_ids,
        time_reference_minutes=ranked.time_reference_minutes,
        time_reference_microseconds=ranked.time_reference_microseconds,
        cost_reference_usd=ranked.cost_reference_usd,
        cost_reference_numerator=ranked.cost_reference_numerator,
        cost_reference_denominator=ranked.cost_reference_denominator,
        direct_cash_observation_ids=matched.direct_cash_observation_ids,
        award_summary_observation_ids=matched.award_summary_observation_ids,
        unmatched_award_observation_ids=matched.unmatched_award_observation_ids,
        unpaired_positioning_observation_ids=(
            matched.accounting.unpaired_positioning_observation_ids),
        pairing_receipts=matched.pairing_receipts,
        match_accounting=matched.accounting,
        coverage_groups=coverage_groups,
        planning_strategy_notes=notes,
        planning_issues=plan.issues,
        planning_deferred_constraints=plan.constraint_obligations,
        planning_coverage=plan.coverage,
        discovery_limitations=plan.discovery_receipt.limitations,
        discovery_issues=plan.discovery_receipt.issues,
        provider_findings=provider.findings,
        execution_findings=provider.execution_plan.findings,
        transport_findings=tuple(TransportFindingRecord(
            transport_id=transport.transport_id,
            query_id=transport.query_id,
            status=transport.status,
            findings=transport.findings,
        ) for transport in provider.transport_receipts),
    )
    receipt = ProjectionReceipt(
        source_digest=content_digest(ranked),
        view_digest=content_digest(view),
        ranked_contract_version=ranked.contract_version,
        matched_contract_version=matched.contract_version,
        provider_contract_version=provider.contract_version,
        plan_digest=plan.plan_digest,
        provider_run_id=matched.provider_run_id,
        policy_digest=ranked.policy_digest,
        fx_snapshot_digest=ranked.fx_snapshot_digest,
        candidate_sources=tuple(sources),
        observation_sources=observation_sources,
        coverage_sources=coverage_sources,
        total_candidates=len(alternatives),
        eligible_alternatives=sum(item.status in {"admitted", "conditional"}
                                  for item in alternatives),
    )
    return SolutionProjection(view=view, receipt=receipt)
