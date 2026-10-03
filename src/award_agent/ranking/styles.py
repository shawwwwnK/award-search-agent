"""Deterministic style assignment over complete M1 award-led journeys."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from fractions import Fraction
from typing import Literal
from zoneinfo import ZoneInfo

from award_agent.providers.contracts import ProviderObservation, RawField, content_digest
from award_agent.search_planning.contracts import PlanningContractModel

from .contracts import MatchedJourney, MatchedJourneySet
from .style_contracts import (
    CostComponent,
    CurrencyConversionSnapshot,
    JourneyCost,
    JourneyFeatures,
    RankedJourneySet,
    RankingStylePolicy,
    StyleAssessment,
    StyleIndexes,
)

_STYLE_CONTEXT = Context(
    prec=50, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)


def _display_ratio(value: Fraction) -> Decimal:
    with localcontext(_STYLE_CONTEXT):
        return Decimal(value.numerator) / Decimal(value.denominator)


def _cost_ratio(cost: JourneyCost) -> Fraction | None:
    if cost.exact_subtotal_numerator is None or cost.exact_subtotal_denominator is None:
        return None
    return Fraction(cost.exact_subtotal_numerator, cost.exact_subtotal_denominator)


def _derived_digest(data: dict[str, object]) -> str:
    def json_value(value: object) -> object:
        if isinstance(value, PlanningContractModel):
            return value.model_dump(mode="json")
        if isinstance(value, tuple):
            return [json_value(item) for item in value]
        if isinstance(value, Decimal):
            return str(value)
        return value

    return content_digest({key: json_value(value) for key, value in data.items()})


def _amount(field: RawField) -> tuple[Decimal | None, str]:
    if field.state != "value":
        return None, f"amount_{field.state}"
    value = field.value
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None, "amount_malformed"
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None, "amount_malformed"
    if not amount.is_finite() or amount < 0:
        return None, "amount_malformed"
    return amount, ""


def _currency(field: RawField, snapshot: CurrencyConversionSnapshot) -> tuple[Decimal | None, str]:
    if field.state != "value":
        return None, f"currency_{field.state}"
    if not isinstance(field.value, str) or field.value not in snapshot.rates_to_usd:
        return None, "currency_unsupported"
    return snapshot.rates_to_usd[field.value], ""


def _scope_divisor(scope: str, travelers: int | None) -> tuple[Decimal | None, str]:
    if scope == "per_traveler":
        return Decimal(1), ""
    if scope == "party" and travelers is not None and travelers > 0:
        return Decimal(travelers), ""
    return None, "scope_unknown"


def _same_instant(left: datetime | None, right: datetime | None) -> bool:
    return left is not None and right is not None and (
        left.astimezone(UTC) == right.astimezone(UTC)
    )


def _verify_timing(
    journey: MatchedJourney, award: ProviderObservation,
    cash: ProviderObservation | None, timezones: dict[str, str],
) -> None:
    if not award.legs or award.legs[0].departure_instant is None or (
        award.legs[-1].arrival_instant is None
    ):
        raise ValueError("eligible journey lacks award component endpoint evidence")
    award_start = award.legs[0].departure_instant
    award_end = award.legs[-1].arrival_instant
    if (award.departure_instant is not None
        and not _same_instant(award_start, award.departure_instant)) or (
        award.arrival_instant is not None
        and not _same_instant(award_end, award.arrival_instant)
    ):
        raise ValueError("eligible award component endpoints disagree with its legs")
    if cash is None:
        expected_start, expected_end = award_start, award_end
        if journey.transfer_minutes is not None or journey.transfer_airport is not None or (
            journey.transfer_local_day_offset is not None
        ):
            raise ValueError("direct award cannot claim transfer timing")
        expected_origin, expected_destination = award.origin, award.destination
    else:
        cash_start, cash_end = cash.departure_instant, cash.arrival_instant
        if cash_start is None or cash_end is None:
            raise ValueError("eligible cash component lacks endpoint evidence")
        if cash.legs and (not _same_instant(cash_start, cash.legs[0].departure_instant)
                          or not _same_instant(cash_end, cash.legs[-1].arrival_instant)):
            raise ValueError("eligible cash component endpoints disagree with its legs")
        if journey.topology == "cash_access_award":
            expected_start, expected_end = cash_start, award_end
            arriving, departing = cash_end, award_start
            expected_origin, expected_destination = cash.origin, award.destination
            transfer_airport = cash.destination
            if transfer_airport != award.origin:
                raise ValueError("eligible transfer airports disagree")
        else:
            expected_start, expected_end = award_start, cash_end
            arriving, departing = award_end, cash_start
            expected_origin, expected_destination = award.origin, cash.destination
            transfer_airport = award.destination
            if transfer_airport != cash.origin:
                raise ValueError("eligible transfer airports disagree")
        transfer = departing.astimezone(UTC) - arriving.astimezone(UTC)
        transfer_microseconds = ((transfer.days * 86400 + transfer.seconds) * 1000000
                                 + transfer.microseconds)
        timezone = timezones.get(transfer_airport)
        if timezone is None or transfer_microseconds < 0:
            raise ValueError("eligible transfer timing lacks source support")
        offset = (departing.astimezone(ZoneInfo(timezone)).date()
                  - arriving.astimezone(ZoneInfo(timezone)).date()).days
        if (journey.transfer_airport != transfer_airport
            or journey.transfer_minutes != transfer_microseconds // 60000000
            or journey.transfer_local_day_offset != offset):
            raise ValueError("matched transfer timing differs from component evidence")
    origin_timezone = timezones.get(expected_origin)
    if origin_timezone is None:
        raise ValueError("eligible origin timezone is unavailable")
    expected_date = expected_start.astimezone(ZoneInfo(origin_timezone)).date()
    if (not _same_instant(journey.departure_instant, expected_start)
        or not _same_instant(journey.arrival_instant, expected_end)
        or (journey.original_origin, journey.original_destination) != (
            expected_origin, expected_destination
        ) or journey.original_departure_date != expected_date):
        raise ValueError("matched journey endpoints differ from component evidence")


def _component(
    kind: Literal["points", "award_taxes", "cash_fare"],
    observation: ProviderObservation, amount_field: RawField,
    currency_field: RawField | None, unit: str, policy: RankingStylePolicy,
    snapshot: CurrencyConversionSnapshot, travelers: int | None,
) -> CostComponent:
    amount, reason = _amount(amount_field)
    if kind == "award_taxes" and amount_field.state in {"absent", "null", "unknown"}:
        estimate = Fraction(policy.unknown_tax_usd)
        return CostComponent(
            kind="award_taxes", state="estimated", observation_id=observation.observation_id,
            raw_amount=amount_field, raw_currency=currency_field, unit=unit,
            scope=observation.price_scope, per_traveler_usd=policy.unknown_tax_usd,
            exact_numerator=estimate.numerator, exact_denominator=estimate.denominator,
            reason="unknown_award_taxes_estimated_per_traveler",
        )
    if amount is None:
        return CostComponent(
            kind=kind, state="unavailable", observation_id=observation.observation_id,
            raw_amount=amount_field, raw_currency=currency_field, unit=unit,
            scope=observation.price_scope, reason=reason,
        )
    divisor, scope_reason = _scope_divisor(observation.price_scope, travelers)
    rate: Decimal | None = Decimal(1)
    if kind == "award_taxes":
        if unit not in {"major", "minor"}:
            reason = "tax_unit_unknown"
        elif (unit == "minor" and currency_field is not None
              and currency_field.state == "value"
              and isinstance(currency_field.value, str)
              and currency_field.value not in {"USD", "CAD"}):
            reason = "tax_minor_scale_unsupported"
        elif currency_field is None:
            reason = "currency_absent"
        else:
            rate, reason = _currency(currency_field, snapshot)
    elif kind == "cash_fare":
        if currency_field is None:
            reason = "currency_absent"
        else:
            rate, reason = _currency(currency_field, snapshot)
    if not reason and scope_reason:
        reason = scope_reason
    if reason or divisor is None or rate is None:
        return CostComponent(
            kind=kind, state="unavailable", observation_id=observation.observation_id,
            raw_amount=amount_field, raw_currency=currency_field, unit=unit,
            scope=observation.price_scope, reason=reason or "normalization_unavailable",
        )
    if kind == "points":
        exact = Fraction(amount) / Fraction(policy.points_per_usd) / Fraction(divisor)
    else:
        major = Fraction(amount) / 100 if kind == "award_taxes" and unit == "minor" else Fraction(amount)
        exact = major * Fraction(rate) / Fraction(divisor)
    normalized = _display_ratio(exact)
    return CostComponent(
        kind=kind, state="observed", observation_id=observation.observation_id,
        raw_amount=amount_field, raw_currency=currency_field, unit=unit,
        scope=observation.price_scope, per_traveler_usd=normalized,
        exact_numerator=exact.numerator, exact_denominator=exact.denominator,
        conversion_snapshot_id=snapshot.snapshot_id if kind != "points" else None,
    )


def _features(
    journey: MatchedJourney, observations: dict[str, ProviderObservation],
    policy: RankingStylePolicy, snapshot: CurrencyConversionSnapshot, travelers: int | None,
    timezones: dict[str, str],
) -> JourneyFeatures:
    award = observations[journey.award_observation_id]
    cash = (observations[journey.cash_observation_id]
            if journey.cash_observation_id is not None else None)
    if journey.status in {"admitted", "conditional"}:
        _verify_timing(journey, award, cash, timezones)
    components = [
        _component("points", award, award.points, None, "points", policy, snapshot, travelers),
        _component("award_taxes", award, award.taxes_fees, award.tax_currency,
                   award.taxes_fees_unit, policy, snapshot, travelers),
    ]
    if cash is not None:
        components.append(_component("cash_fare", cash, cash.cash_amount, cash.cash_currency,
                                     "major", policy, snapshot, travelers))
    known = [Fraction(component.exact_numerator, component.exact_denominator)
             for component in components if component.exact_numerator is not None
             and component.exact_denominator is not None]
    missing = tuple(component.kind for component in components if component.state == "unavailable")
    exact_subtotal = sum(known, Fraction(0)) if known else None
    subtotal = _display_ratio(exact_subtotal) if exact_subtotal is not None else None
    completeness: Literal["complete", "partial", "unavailable"] = (
        "complete" if not missing else "partial" if known else "unavailable"
    )
    elapsed = None
    elapsed_microseconds = None
    if journey.departure_instant is not None and journey.arrival_instant is not None:
        interval = (journey.arrival_instant.astimezone(UTC)
                    - journey.departure_instant.astimezone(UTC))
        if interval.total_seconds() <= 0 and journey.status in {"admitted", "conditional"}:
            raise ValueError("eligible journey has nonpositive elapsed time")
        if interval.total_seconds() > 0:
            elapsed_microseconds = ((interval.days * 86400 + interval.seconds) * 1000000
                                    + interval.microseconds)
            elapsed = _display_ratio(Fraction(elapsed_microseconds, 60000000))
    elif journey.status in {"admitted", "conditional"}:
        raise ValueError("eligible journey requires both endpoint instants")
    return JourneyFeatures(
        candidate_id=journey.candidate_id, option_family_id=journey.option_family_id,
        award_observation_id=journey.award_observation_id,
        cash_observation_id=journey.cash_observation_id, topology=journey.topology,
        status=journey.status, elapsed_minutes=elapsed,
        elapsed_microseconds=elapsed_microseconds,
        transfer_minutes=journey.transfer_minutes,
        booking_obligation=journey.booking_obligation, award_cabin=award.cabin,
        premium_economy_addon=award.cabin.state == "value"
        and award.cabin.value == "premium_economy",
        cost=JourneyCost(
            components=tuple(components), known_subtotal_usd=subtotal,
            complete_usd=subtotal if not missing else None,
            exact_subtotal_numerator=exact_subtotal.numerator if exact_subtotal is not None else None,
            exact_subtotal_denominator=exact_subtotal.denominator if exact_subtotal is not None else None,
            missing_parts=missing, completeness=completeness,
        ),
    )


def _assessment(
    feature: JourneyFeatures, style: Literal["time", "cost", "premium"],
    time_reference: int | None,
    cost_reference: Fraction | None, policy: RankingStylePolicy,
) -> StyleAssessment:
    with localcontext(_STYLE_CONTEXT):
        return _assessment_in_context(feature, style, time_reference, cost_reference, policy)


def _assessment_in_context(
    feature: JourneyFeatures, style: Literal["time", "cost", "premium"],
    time_reference: int | None,
    cost_reference: Fraction | None, policy: RankingStylePolicy,
) -> StyleAssessment:
    candidate_id = feature.candidate_id
    if feature.status not in {"admitted", "conditional"}:
        return StyleAssessment(candidate_id=candidate_id, style=style, state="undetermined",
                               reasons=("excluded_m1_status",))
    if style == "time":
        threshold_exact = (Fraction(time_reference) * Fraction(policy.time_factor)
                           if time_reference is not None else None)
        threshold = (_display_ratio(threshold_exact / 60000000)
                     if threshold_exact is not None else None)
        reference = (_display_ratio(Fraction(time_reference, 60000000))
                     if time_reference is not None else None)
        value = feature.elapsed_minutes
        if value is None or threshold is None or (
            feature.elapsed_microseconds is None or threshold_exact is None
        ):
            return StyleAssessment(candidate_id=candidate_id, style="time", state="undetermined",
                                   feature_numeric=value, reference_value=reference,
                                   threshold=threshold,
                                   exact_threshold_numerator=(threshold_exact.numerator
                                                              if threshold_exact is not None else None),
                                   exact_threshold_denominator=(threshold_exact.denominator
                                                                if threshold_exact is not None else None),
                                   exact_threshold_unit=("microseconds"
                                                         if threshold_exact is not None else None),
                                   reasons=("elapsed_time_unavailable",))
        return StyleAssessment(candidate_id=candidate_id, style="time",
                               state="member" if feature.elapsed_microseconds <= threshold_exact
                               else "not_member",
                               feature_numeric=value, reference_value=reference,
                               threshold=threshold,
                               exact_threshold_numerator=threshold_exact.numerator,
                               exact_threshold_denominator=threshold_exact.denominator,
                               exact_threshold_unit="microseconds")
    if style == "premium":
        raw_cabin = feature.award_cabin.value if feature.award_cabin.state == "value" else None
        cabin = raw_cabin if isinstance(raw_cabin, str) else None
        if cabin in {"business", "first"}:
            state: Literal["member", "possible", "not_member", "undetermined"] = "member"
            reasons: tuple[str, ...] = ()
        elif cabin == "premium_economy":
            state, reasons = "not_member", ("premium_economy_addon",)
        elif cabin is None:
            state, reasons = "undetermined", ("award_cabin_unknown",)
        else:
            state, reasons = "not_member", ()
        return StyleAssessment(candidate_id=candidate_id, style="premium", state=state,
                               feature_label=cabin, reasons=reasons)
    cost = feature.cost
    threshold_exact = (cost_reference * Fraction(policy.cost_factor)
                       if cost_reference is not None else None)
    threshold = _display_ratio(threshold_exact) if threshold_exact is not None else None
    reference = _display_ratio(cost_reference) if cost_reference is not None else None
    value = cost.complete_usd if cost.complete_usd is not None else cost.known_subtotal_usd
    if threshold_exact is None:
        return StyleAssessment(candidate_id=candidate_id, style="cost", state="undetermined",
                               feature_numeric=value, reasons=("no_complete_cost_reference",),
                               validation_needs=cost.missing_parts)
    exact_cost = _cost_ratio(cost)
    if cost.complete_usd is not None and exact_cost is not None:
        state = "member" if exact_cost <= threshold_exact else "not_member"
        reasons = ()
    elif exact_cost is None:
        state, reasons = "undetermined", ("no_normalized_cost_lower_bound",)
    elif exact_cost <= threshold_exact:
        state, reasons = "possible", ("incomplete_cost_lower_bound",)
    else:
        state, reasons = "not_member", ("partial_subtotal_above_threshold",)
    return StyleAssessment(candidate_id=candidate_id, style="cost", state=state,
                           feature_numeric=value, reference_value=reference,
                           threshold=threshold, reasons=reasons,
                           exact_threshold_numerator=threshold_exact.numerator,
                           exact_threshold_denominator=threshold_exact.denominator,
                           exact_threshold_unit="usd",
                           validation_needs=cost.missing_parts)


def _derive_style_data(
    matched: MatchedJourneySet, policy: RankingStylePolicy,
    snapshot: CurrencyConversionSnapshot,
) -> dict[str, object]:
    with localcontext(_STYLE_CONTEXT):
        return _derive_style_data_in_context(matched, policy, snapshot)


def _derive_style_data_in_context(
    matched: MatchedJourneySet, policy: RankingStylePolicy,
    snapshot: CurrencyConversionSnapshot,
) -> dict[str, object]:
    observations = {item.observation_id: item for item in matched.provider_result.observations}
    timezones = {item.airport_iata: item.timezone for item in matched.plan.airport_directory}
    features = tuple(_features(journey, observations, policy, snapshot,
                               matched.request.travelers, timezones)
                     for journey in sorted(matched.journeys, key=lambda item: item.candidate_id))
    eligible = tuple(feature for feature in features
                     if feature.status in {"admitted", "conditional"})
    time_values = [feature.elapsed_microseconds for feature in eligible
                   if feature.elapsed_microseconds is not None]
    cost_values = [Fraction(feature.cost.exact_subtotal_numerator,
                            feature.cost.exact_subtotal_denominator)
                   for feature in eligible if feature.cost.complete_usd is not None
                   and feature.cost.exact_subtotal_numerator is not None
                   and feature.cost.exact_subtotal_denominator is not None]
    time_reference = min(time_values) if time_values else None
    cost_reference = min(cost_values) if cost_values else None
    assessments = tuple(
        _assessment(feature, style, time_reference, cost_reference, policy)
        for feature in features for style in ("time", "cost", "premium")
    )
    by_style = {style: tuple(item.candidate_id for item in assessments
                             if item.style == style and item.state == "member")
                for style in ("time", "cost", "premium")}
    possible_cost = tuple(item.candidate_id for item in assessments
                          if item.style == "cost" and item.state == "possible")
    memberships = {feature.candidate_id: sum(feature.candidate_id in members
                                              for members in by_style.values())
                   for feature in features}
    eligible_ids = {feature.candidate_id for feature in eligible}
    indexes = StyleIndexes(
        **by_style,
        possible_cost=possible_cost,
        premium_economy_addons=tuple(feature.candidate_id for feature in eligible
                                     if feature.premium_economy_addon),
        definite_highlights=tuple(feature.candidate_id for feature in eligible
                                  if memberships[feature.candidate_id] >= 2),
        possible_highlights=tuple(feature.candidate_id for feature in eligible
                                  if memberships[feature.candidate_id] == 1
                                  and feature.candidate_id in possible_cost),
        other_alternatives=tuple(feature.candidate_id for feature in eligible
                                 if memberships[feature.candidate_id] == 0),
        excluded=tuple(feature.candidate_id for feature in features
                       if feature.candidate_id not in eligible_ids),
    )
    return {
        "comparison_pool_ids": tuple(feature.candidate_id for feature in eligible),
        "time_reference_minutes": (_display_ratio(Fraction(time_reference, 60000000))
                                   if time_reference is not None else None),
        "time_reference_microseconds": time_reference,
        "cost_reference_usd": (_display_ratio(cost_reference)
                               if cost_reference is not None else None),
        "cost_reference_numerator": (cost_reference.numerator
                                     if cost_reference is not None else None),
        "cost_reference_denominator": (cost_reference.denominator
                                       if cost_reference is not None else None),
        "features": features,
        "assessments": assessments,
        "indexes": indexes,
    }


def assign_journey_styles(
    matched: MatchedJourneySet, *, policy: RankingStylePolicy,
    fx_snapshot: CurrencyConversionSnapshot,
) -> RankedJourneySet:
    """Assign overlapping M2 styles with exact M1 and FX source attachments."""
    derived = _derive_style_data(matched, policy, fx_snapshot)
    return RankedJourneySet.model_validate({
        "policy": policy, "policy_digest": content_digest(policy),
        "fx_snapshot": fx_snapshot, "fx_snapshot_digest": content_digest(fx_snapshot),
        "matched": matched, "matched_digest": content_digest(matched),
        "derived_digest": _derived_digest(derived), **derived,
    })
