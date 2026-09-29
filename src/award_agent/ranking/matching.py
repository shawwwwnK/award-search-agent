"""Deterministic M1 assembly of intact award itineraries and one cash leg."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from award_agent.domain.clarification_session import EffectiveRequest
from award_agent.providers.contracts import (
    ExecutionPolicy,
    ProviderCapability,
    ProviderObservation,
    ProviderQuery,
    ProviderResultSet,
    RawField,
    content_digest,
)
from award_agent.providers.execution import validate_result_attachment
from award_agent.search_planning.compilation_contracts import (
    CompiledSearchPlan,
    PositioningDependency,
    StrategySupportAlternative,
    SupplementalStrategy,
)
from award_agent.search_planning.contracts import FilterObligationKind, ResultValidationKind

from .contracts import (
    MatchAccounting,
    MatchedJourney,
    MatchedJourneySet,
    MatchReason,
    PairingReceipt,
    classify_match,
)


def _reason(code: str, dimension: str, state: str, detail: str) -> MatchReason:
    return MatchReason(code=code, dimension=dimension, state=state, detail=detail)


def _known_int(field: RawField) -> int | None:
    if field.state != "value" or isinstance(field.value, bool):
        return None
    try:
        value = int(field.value)
    except (TypeError, ValueError):
        return None
    return value if str(field.value) == str(value) else None


def _utc(instant: datetime) -> datetime:
    return instant.astimezone(UTC)


def _timing(observation: ProviderObservation, *, award: bool) -> tuple[
    datetime | None, datetime | None, tuple[MatchReason, ...]
]:
    reasons: list[MatchReason] = []
    if award and not observation.legs:
        reasons.append(_reason("award_legs_missing", "evidence", "unknown",
                               "Provider did not return complete award leg timing."))
        return None, None, tuple(reasons)
    if award:
        legs = observation.legs
        if legs[0].origin != observation.origin or legs[-1].destination != observation.destination:
            reasons.append(_reason("award_endpoint_mismatch", "route", "failed",
                                   "Award leg endpoints differ from the itinerary endpoints."))
        for index, leg in enumerate(legs):
            if index and legs[index - 1].destination != leg.origin:
                reasons.append(_reason("award_internal_airport_gap", "route", "failed",
                                       "Adjacent award legs do not meet at the same airport."))
            if leg.departure_instant is None or leg.arrival_instant is None:
                reasons.append(_reason("award_leg_time_missing", "evidence", "unknown",
                                       "An award leg has no normalized departure or arrival instant."))
                continue
            if _utc(leg.arrival_instant) <= _utc(leg.departure_instant):
                reasons.append(_reason("award_leg_nonpositive", "schedule", "failed",
                                       "An award leg has nonpositive elapsed time."))
            if index and legs[index - 1].arrival_instant is not None and (
                leg.departure_instant is not None and
                _utc(leg.departure_instant) <= _utc(legs[index - 1].arrival_instant)
            ):
                reasons.append(_reason("award_internal_nonpositive_layover", "schedule", "failed",
                                       "Adjacent award legs require a positive layover."))
        first, last = legs[0].departure_instant, legs[-1].arrival_instant
        if observation.departure_instant is not None and first is not None and (
            _utc(first) != _utc(observation.departure_instant)
        ):
            reasons.append(_reason("award_departure_disagreement", "evidence", "unknown",
                                   "Award itinerary departure differs from its first leg."))
        if observation.arrival_instant is not None and last is not None and (
            _utc(last) != _utc(observation.arrival_instant)
        ):
            reasons.append(_reason("award_arrival_disagreement", "evidence", "unknown",
                                   "Award itinerary arrival differs from its last leg."))
    else:
        first, last = observation.departure_instant, observation.arrival_instant
        if observation.legs:
            if observation.legs[0].origin != observation.origin or (
                observation.legs[-1].destination != observation.destination
            ):
                reasons.append(_reason("cash_endpoint_mismatch", "route", "failed",
                                       "Cash leg endpoints differ from the itinerary endpoints."))
            for previous, current in zip(observation.legs, observation.legs[1:], strict=False):
                if previous.destination != current.origin:
                    reasons.append(_reason("cash_internal_airport_gap", "route", "failed",
                                           "Adjacent cash legs do not meet at the same airport."))
                if previous.arrival_instant is not None and current.departure_instant is not None and (
                    _utc(current.departure_instant) <= _utc(previous.arrival_instant)
                ):
                    reasons.append(_reason("cash_internal_nonpositive_layover", "schedule", "failed",
                                           "Adjacent cash legs require a positive layover."))
            for leg in observation.legs:
                if leg.departure_instant is None or leg.arrival_instant is None:
                    reasons.append(_reason("cash_leg_time_missing", "evidence", "unknown",
                                           "A cash leg has no normalized timing."))
                elif _utc(leg.arrival_instant) <= _utc(leg.departure_instant):
                    reasons.append(_reason("cash_leg_nonpositive", "schedule", "failed",
                                           "A cash leg has nonpositive elapsed time."))
            if first is not None and observation.legs[0].departure_instant is not None and (
                _utc(observation.legs[0].departure_instant) != _utc(first)
            ) or (last is not None and observation.legs[-1].arrival_instant is not None and
                  _utc(observation.legs[-1].arrival_instant) != _utc(last)):
                reasons.append(_reason("cash_endpoint_time_disagreement", "evidence", "unknown",
                                       "Cash endpoint times differ from its detailed legs."))
        elif _known_int(observation.stops) != 0 or observation.airport_sequence != (
            observation.origin, observation.destination
        ):
            reasons.append(_reason("cash_internal_legs_unknown", "evidence", "unknown",
                                   "Cash result does not affirm nonstop travel or give timed legs."))
    if first is None or last is None:
        reasons.append(_reason("endpoint_time_missing", "evidence", "unknown",
                               "Complete normalized endpoint instants are unavailable."))
    elif _utc(last) <= _utc(first):
        reasons.append(_reason("nonpositive_itinerary", "schedule", "failed",
                               "Itinerary has nonpositive elapsed time."))
    return first, last, tuple(reasons)


def _local_date(instant: datetime, airport: str, timezones: dict[str, str]) -> date | None:
    timezone = timezones.get(airport)
    if timezone is None:
        return None
    try:
        return instant.astimezone(ZoneInfo(timezone)).date()
    except ZoneInfoNotFoundError:
        return None


def _price_completeness(award: ProviderObservation, cash: ProviderObservation | None) -> str:
    fields = [award.points, award.taxes_fees, award.tax_currency, award.program]
    if cash is not None:
        fields.extend((cash.cash_amount, cash.cash_currency))
    known = sum(field.state == "value" for field in fields)
    scope_known = award.price_scope != "unknown" and (
        cash is None or cash.price_scope != "unknown"
    )
    if known == len(fields) and scope_known and award.taxes_fees_unit != "unknown":
        return "known"
    return "partial" if known else "unknown"


def _award_obligations(
    plan: CompiledSearchPlan, award: ProviderObservation,
    airport: dict[str, str],
) -> list[MatchReason]:
    reasons: list[MatchReason] = []
    queries = {query.query_id: query for query in plan.logical_queries}
    for query_id in award.logical_query_ids:
        query = queries[query_id]
        for obligation in query.filter_obligations:
            kind = obligation.kind
            values = set(obligation.values)
            if kind is FilterObligationKind.CABIN_AVAILABLE_IN:
                value = award.cabin.value if award.cabin.state == "value" else None
                state = "unknown" if value is None else "passed" if value in values else "failed"
            elif kind is FilterObligationKind.DIRECT_FLIGHT_AVAILABLE:
                state = "passed" if len(award.legs) == 1 else "failed" if award.legs else "unknown"
            elif kind is FilterObligationKind.CARRIER_INVOLVEMENT_MATCH:
                carriers = {carrier.casefold() for carrier in award.carriers}
                state = "unknown" if not carriers else "passed" if carriers & values else "failed"
            elif kind is FilterObligationKind.REDEMPTION_PROGRAM_IN:
                value = award.program.value if award.program.state == "value" else None
                state = "unknown" if value is None else (
                    "passed" if str(value).casefold() in values else "failed"
                )
            else:
                state = "unknown"  # cabin distance requires segment-distance evidence
            reasons.append(_reason(f"filter_{kind.value}", "requirement", state,
                                   f"Compiled award filter {kind.value} evaluated from returned evidence."))
        for obligation in query.result_validation_obligations:
            if obligation.kind is ResultValidationKind.MINIMUM_AWARD_SEATS:
                seats = _known_int(award.seats)
                unreliable = any(f.code in {"seats_program_unsupported", "seats_zero_ambiguous"}
                                 for f in award.findings)
                state = "unknown" if seats is None or unreliable or seats == 0 else (
                    "passed" if seats >= obligation.minimum_seats else "failed"
                )
            else:
                expected = (airport[obligation.expected_origin_airport_fact_id],
                            airport[obligation.expected_destination_airport_fact_id])
                state = "passed" if (award.origin, award.destination) == expected else "failed"
            reasons.append(_reason(f"result_validation_{obligation.kind.value}",
                                   "requirement", state,
                                   f"Compiled award result obligation {obligation.kind.value} evaluated."))
    for obligation in plan.constraint_obligations:
        if set(obligation.applies_to_query_ids) & set(award.logical_query_ids):
            reasons.append(_reason("deferred_constraint", "requirement", "unknown",
                                   "A compiled deferred constraint requires a typed result check."))
    return reasons


def _requirements(
    request: EffectiveRequest, award: ProviderObservation,
    cash: ProviderObservation | None, dependency: PositioningDependency | None,
) -> list[MatchReason]:
    reasons: list[MatchReason] = []
    travelers = request.travelers
    if travelers is not None:
        returned = _known_int(award.returned_travelers)
        seats = _known_int(award.seats)
        unreliable = any(f.code in {"seats_program_unsupported", "seats_zero_ambiguous"}
                         for f in award.findings)
        if returned is not None and returned < travelers or (
            seats is not None and not unreliable and 0 < seats < travelers
        ):
            reasons.append(_reason("award_travelers_insufficient", "requirement", "failed",
                                   "Award evidence reports fewer places than requested travelers."))
        elif returned is not None and returned >= travelers or (
            seats is not None and not unreliable and seats >= travelers
        ):
            reasons.append(_reason("award_travelers_supported", "requirement", "passed",
                                   "Award evidence supports the requested traveler count."))
        else:
            reasons.append(_reason("award_travelers_unknown", "requirement", "unknown",
                                   "Requested traveler count is not confirmed by the award result."))
        if cash is not None:
            cash_returned = _known_int(cash.returned_travelers)
            if cash_returned is None:
                reasons.append(_reason("cash_travelers_unknown", "requirement", "unknown",
                                       "Cash result does not confirm party size."))
            elif cash_returned < travelers:
                reasons.append(_reason("cash_travelers_insufficient", "requirement", "failed",
                                       "Cash result reports fewer places than requested."))
    requested_cabins = {c.value for c in request.cabins}
    if requested_cabins:
        if award.cabin.state != "value":
            reasons.append(_reason("award_cabin_unknown", "requirement", "unknown",
                                   "Award result does not confirm the requested cabin."))
        elif award.cabin.value not in requested_cabins:
            reasons.append(_reason("award_cabin_mismatch", "requirement", "failed",
                                   "Award result cabin is outside the requested cabins."))
        else:
            reasons.append(_reason("award_cabin_supported", "requirement", "passed",
                                   "Award result cabin matches the requested cabin."))
        # Owner decision 2026-09-27: a confirmed, matching journey-level cabin is
        # accepted when a leg does not report its own cabin. The unreported leg
        # cabin stays visible as a non-blocking cabin-dimension reason; a leg that
        # does report an out-of-request cabin still fails the journey.
        journey_cabin_confirmed = (
            award.cabin.state == "value" and award.cabin.value in requested_cabins
        )
        for leg in award.legs:
            if leg.cabin.state != "value":
                if journey_cabin_confirmed:
                    reasons.append(_reason("award_leg_cabin_unreported", "cabin", "unknown",
                                           "Award leg does not report a cabin; the confirmed "
                                           "journey-level cabin is accepted under this policy."))
                else:
                    reasons.append(_reason("award_leg_cabin_unknown", "requirement", "unknown",
                                           "An award leg does not confirm its cabin."))
            elif leg.cabin.value not in requested_cabins:
                reasons.append(_reason("award_leg_cabin_mismatch", "requirement", "failed",
                                       "An award leg has a cabin outside the requested cabins."))
    if request.hard_constraints:
        reasons.append(_reason("unstructured_hard_constraints", "requirement", "unknown",
                               "Additional request constraints require a typed validator."))
    if dependency is not None:
        if dependency.requested_permission is False or request.repositioning_allowed is False:
            reasons.append(_reason("positioning_refused", "requirement", "failed",
                                   "The request does not permit separate positioning travel."))
        elif dependency.requested_permission is None or request.repositioning_allowed is None:
            reasons.append(_reason("positioning_permission_unknown", "requirement", "unknown",
                                   "Separate positioning travel permission is unresolved."))
    return reasons


def _build_candidate(
    *, award: ProviderObservation, cash: ProviderObservation | None,
    cash_query: ProviderQuery | None, topology: str,
    request: EffectiveRequest, timezones: dict[str, str],
    plan: CompiledSearchPlan, airport: dict[str, str],
    original_origin: str, original_destination: str,
    strategy: SupplementalStrategy | None = None,
    support: StrategySupportAlternative | None = None,
    dependency: PositioningDependency | None = None,
) -> MatchedJourney:
    reasons: list[MatchReason] = []
    award_start, award_end, award_reasons = _timing(award, award=True)
    reasons.extend(award_reasons)
    cash_start = cash_end = None
    if cash is not None:
        cash_start, cash_end, cash_reasons = _timing(cash, award=False)
        reasons.extend(cash_reasons)
    start = cash_start if topology == "cash_access_award" else award_start
    end = cash_end if topology == "award_cash_egress" else award_end
    first_airport = cash.origin if topology == "cash_access_award" and cash else award.origin
    last_airport = cash.destination if topology == "award_cash_egress" and cash else award.destination
    if first_airport != original_origin or last_airport != original_destination:
        reasons.append(_reason("original_endpoint_mismatch", "route", "failed",
                               "Complete journey does not meet the supported original airport pair."))
    else:
        reasons.append(_reason("original_endpoints_match", "route", "passed",
                               "Complete journey meets its original airport pair."))
    transfer_airport = None
    transfer_minutes = None
    day_offset = None
    if cash is not None:
        if topology == "cash_access_award":
            inbound_airport, outbound_airport = cash.destination, award.origin
            arriving, departing = cash_end, award_start
        else:
            inbound_airport, outbound_airport = award.destination, cash.origin
            arriving, departing = award_end, cash_start
        transfer_airport = inbound_airport
        if inbound_airport != outbound_airport:
            reasons.append(_reason("transfer_airport_mismatch", "route", "failed",
                                   "Separate-ticket components do not meet at one airport."))
        elif arriving is not None and departing is not None:
            elapsed = (departing.astimezone(UTC) - arriving.astimezone(UTC)).total_seconds()
            if elapsed < 0:
                reasons.append(_reason("transfer_negative", "schedule", "failed",
                                       "Onward component leaves before the incoming component arrives."))
            else:
                transfer_minutes = int(elapsed // 60)
                reasons.append(_reason("transfer_at_least_120_minutes" if elapsed >= 7200
                                       else "transfer_under_120_minutes", "schedule",
                                       "passed" if elapsed >= 7200 else "failed",
                                       "Separate-ticket connection requires at least 120 elapsed minutes."))
            arrival_date = _local_date(arriving, inbound_airport, timezones)
            departure_date = _local_date(departing, inbound_airport, timezones)
            if arrival_date is None or departure_date is None:
                reasons.append(_reason("transfer_timezone_unknown", "evidence", "unknown",
                                       "Transfer airport timezone is unavailable."))
            else:
                day_offset = (departure_date - arrival_date).days
                reasons.append(_reason("transfer_same_or_next_local_day" if day_offset in (0, 1)
                                       else "transfer_local_day_outside_rule", "schedule",
                                       "passed" if day_offset in (0, 1) else "failed",
                                       "Onward departure must be on arrival date or the next local date."))
        else:
            reasons.append(_reason("transfer_time_unknown", "evidence", "unknown",
                                   "Transfer timing cannot be checked without both component instants."))
        reasons.append(_reason("separate_ticket_obligation", "booking", "unknown",
                               "Separate-ticket baggage, check-in, terminal, transit, and missed-connection protection remain unverified."))
    original_date = _local_date(start, original_origin, timezones) if start else None
    if request.departure_window is None or original_date is None:
        reasons.append(_reason("original_departure_date_unknown", "evidence", "unknown",
                               "Original departure date cannot be checked against the request."))
    elif not request.departure_window.start <= original_date <= request.departure_window.end:
        reasons.append(_reason("original_departure_outside_window", "schedule", "failed",
                               "Original departure falls outside the requested local date window."))
    else:
        reasons.append(_reason("original_departure_in_window", "schedule", "passed",
                               "Original departure falls within the requested local date window."))
    reasons.extend(_requirements(request, award, cash, dependency))
    reasons.extend(_award_obligations(plan, award, airport))
    price = _price_completeness(award, cash)
    if price != "known":
        reasons.append(_reason("price_incomplete", "price", "unknown",
                               "Observed amounts cannot support an all-in party total."))
    if cash is not None and any(f.severity == "error" for f in cash.findings):
        reasons.append(_reason("cash_provider_error", "evidence", "unknown",
                               "Cash observation carries a provider parsing error."))
    if any(f.severity == "error" for f in award.findings):
        reasons.append(_reason("award_provider_error", "evidence", "unknown",
                               "Award observation carries a provider parsing error."))
    status = classify_match(tuple(reasons))
    identity = {
        "award": award.observation_id, "cash": cash.observation_id if cash else None,
        "support": support.support_id if support else None,
        "dependency": dependency.dependency_id if dependency else None,
        "topology": topology, "origin": original_origin, "destination": original_destination,
    }
    return MatchedJourney(
        candidate_id=content_digest(identity),
        option_family_id=content_digest({key: value for key, value in identity.items()
                                         if key not in {"cash", "dependency"}}),
        topology=topology, status=status,
        award_observation_id=award.observation_id,
        cash_observation_id=cash.observation_id if cash else None,
        award_query_id=award.query_id,
        cash_query_id=cash.query_id if cash else None,
        logical_award_query_ids=award.logical_query_ids,
        strategy_id=strategy.strategy_id if strategy else None,
        support_id=support.support_id if support else None,
        positioning_dependency_id=dependency.dependency_id if dependency else None,
        positioning_reason=strategy.reason if strategy else None,
        activation_observation_ids=cash_query.activation_observation_ids if cash_query else (),
        original_origin=original_origin, original_destination=original_destination,
        departure_instant=start, arrival_instant=end,
        original_departure_date=original_date, transfer_airport=transfer_airport,
        transfer_minutes=transfer_minutes, transfer_local_day_offset=day_offset,
        price_completeness=price,
        booking_obligation="single_award" if cash is None else "separate_tickets_unverified",
        reasons=tuple(reasons),
    )


def assemble_matched_journeys(
    plan: CompiledSearchPlan, result: ProviderResultSet, *,
    current_session_id: str, current_revision: int,
    current_effective_request: EffectiveRequest,
    expected_compilation_binding_digest: str, policy: ExecutionPolicy,
    award_capability: ProviderCapability, cash_capability: ProviderCapability,
    max_combinations: int = 100_000,
) -> MatchedJourneySet:
    """Validate attachment, then enumerate every plan-scoped one-cash combination.

    Raises ValueError before returning any candidates if a source is stale or the
    explicit fanout limit would truncate candidate enumeration.
    """
    if max_combinations < 1:
        raise ValueError("max_combinations must be positive")
    result = validate_result_attachment(
        plan, result, current_session_id=current_session_id,
        current_revision=current_revision,
        current_effective_request=current_effective_request,
        expected_compilation_binding_digest=expected_compilation_binding_digest,
        policy=policy, award_capability=award_capability,
        cash_capability=cash_capability,
    )
    query_by_id = {query.query_id: query for query in result.execution_plan.queries}
    airport = {item.airport_id: item.airport_iata for item in plan.airport_directory}
    timezones = {item.airport_iata: item.timezone for item in plan.airport_directory}
    strategies = {s.strategy_id: s for s in plan.supplemental_strategies}
    uses = {use.query_use_id: use for use in plan.strategy_query_uses}
    dependencies = {d.dependency_id: d for d in plan.positioning_dependencies}
    mandatory_query_pairs: dict[str, set[tuple[str, str]]] = {}
    probe_by_id = {probe.probe_id: probe for probe in plan.mandatory_endpoint_probes}
    for use in plan.mandatory_query_uses:
        probe = probe_by_id[use.probe_id]
        mandatory_query_pairs.setdefault(use.query_id, set()).add((
            probe.origin_endpoint.airport_iata, probe.destination_endpoint.airport_iata
        ))
    observations = result.observations
    awards = tuple(o for o in observations if o.kind == "award_itinerary")
    summaries = tuple(o.observation_id for o in observations if o.kind == "award_summary")
    direct_cash = tuple(o.observation_id for o in observations if
                        query_by_id[o.query_id].role == "direct_cash")
    positioning_cash = tuple(o for o in observations if o.kind == "cash_itinerary" and
                             query_by_id[o.query_id].role in {"cash_access", "cash_egress"})
    cash_by_dependency: dict[str, list[ProviderObservation]] = {}
    for cash in positioning_cash:
        query = query_by_id[cash.query_id]
        for dependency_id in query.positioning_dependency_ids:
            cash_by_dependency.setdefault(dependency_id, []).append(cash)
    journeys: list[MatchedJourney] = []
    pairing_receipts: list[PairingReceipt] = []
    used_cash: set[str] = set()
    paired_awards: set[str] = set()
    scoped_pairs = 0
    for award in awards:
        for query_id in award.logical_query_ids:
            if (award.origin, award.destination) not in mandatory_query_pairs.get(query_id, set()):
                continue
            journeys.append(_build_candidate(
                award=award, cash=None, cash_query=None, topology="direct_award",
                request=current_effective_request, timezones=timezones,
                plan=plan, airport=airport,
                original_origin=award.origin, original_destination=award.destination,
            ))
            paired_awards.add(award.observation_id)
            break
    for support in plan.support_alternatives:
        allowed_queries = {uses[uid].query_id for uid in support.query_use_ids
                           if uid in uses and uses[uid].role == "access_main"}
        strategy = strategies[support.strategy_id]
        if strategy.strategy_type.value not in {"origin_access", "destination_access"}:
            continue
        eligible_awards = [award for award in awards if
                           set(award.logical_query_ids) & allowed_queries and
                           set(query_by_id[award.query_id].logical_query_ids) & allowed_queries]
        origin = airport[support.original_origin_airport_fact_id]
        destination = airport[support.original_destination_airport_fact_id]
        for dependency_id in support.positioning_dependency_ids:
            dependency = dependencies[dependency_id]
            expected_role = "cash_access" if dependency.side == "origin" else "cash_egress"
            scoped_cash = [cash for cash in cash_by_dependency.get(dependency_id, ())
                           if query_by_id[cash.query_id].role == expected_role and
                           strategy.strategy_id in query_by_id[cash.query_id].strategy_ids and
                           (cash.origin, cash.destination) == (
                               airport[dependency.from_airport_fact_id],
                               airport[dependency.to_airport_fact_id],
                           )]
            pairing_receipts.append(PairingReceipt(
                support_id=support.support_id,
                positioning_dependency_id=dependency_id,
                eligible_award_observation_ids=tuple(a.observation_id for a in eligible_awards),
                cash_observation_ids=tuple(c.observation_id for c in scoped_cash),
                enumerated_pairs=len(eligible_awards) * len(scoped_cash),
            ))
            if scoped_pairs + len(eligible_awards) * len(scoped_cash) > max_combinations:
                raise ValueError("M1 matching fanout exceeds max_combinations; no partial result returned")
            for award in eligible_awards:
                for cash in scoped_cash:
                    scoped_pairs += 1
                    journeys.append(_build_candidate(
                        award=award, cash=cash, cash_query=query_by_id[cash.query_id],
                        topology="cash_access_award" if dependency.side == "origin"
                                 else "award_cash_egress",
                        request=current_effective_request, timezones=timezones,
                        plan=plan, airport=airport,
                        original_origin=origin, original_destination=destination,
                        strategy=strategy, support=support, dependency=dependency,
                    ))
                    used_cash.add(cash.observation_id)
                    paired_awards.add(award.observation_id)
    counts = Counter(j.status for j in journeys)
    direct_count = sum(j.topology == "direct_award" for j in journeys)
    accounting = MatchAccounting(
        award_itineraries=len(awards), cash_positioning_observations=len(positioning_cash),
        direct_cash_observations=len(direct_cash), scoped_pairs=scoped_pairs,
        retained_direct=direct_count, retained_mixed=len(journeys) - direct_count,
        admitted=counts["admitted"], conditional=counts["conditional"],
        rejected=counts["rejected"], research_leads=counts["research_lead"],
        unpaired_positioning_observation_ids=tuple(sorted(
            o.observation_id for o in positioning_cash if o.observation_id not in used_cash
        )),
    )
    return MatchedJourneySet(
        current_session_id=current_session_id, current_revision=current_revision,
        effective_request_digest=plan.identity.effective_request_digest,
        compilation_binding_digest=plan.identity.compilation_binding_digest,
        plan_digest=plan.plan_digest,
        provider_run_id=result.execution_plan.binding.run_id,
        provider_policy_digest=result.execution_plan.binding.policy_digest,
        provider_result_digest=content_digest(result),
        max_combinations=max_combinations,
        request=current_effective_request, plan=plan, provider_result=result,
        journeys=tuple(journeys), direct_cash_observation_ids=direct_cash,
        award_summary_observation_ids=summaries,
        unmatched_award_observation_ids=tuple(sorted(
            o.observation_id for o in awards if o.observation_id not in paired_awards
        )), pairing_receipts=tuple(pairing_receipts), accounting=accounting,
    )
