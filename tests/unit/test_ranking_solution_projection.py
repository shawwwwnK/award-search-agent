"""Independent preservation checks for Ranking M2's factual solution export."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from award_agent.providers.contracts import (
    ProviderResultSet,
    RawField,
    ValidationFinding,
    content_digest,
)
from award_agent.ranking.contracts import MatchedJourneySet
from award_agent.ranking.project_solutions import project_solutions
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.ranking.style_contracts import RankedJourneySet, RankingStylePolicy
from award_agent.ranking.styles import assign_journey_styles
from tests.unit.test_ranking_m2 import _snapshot, _synthetic_match

CASES = {
    "mixed_access": (473, 257),
    "exact_business": (396, 106),
    "sfo_to_bkk_positioning": (123, 64),
}


@lru_cache(maxsize=3)
def _projection_for(case: str):
    ranked = RankedJourneySet.model_validate_json(
        (Path("evidence/ranking-stage/m2/styled") / f"{case}.json").read_text()
    )
    return case, ranked, project_solutions(ranked)


@pytest.fixture(scope="module", params=CASES)
def saved_projection(request: pytest.FixtureRequest):
    return _projection_for(request.param)


def test_all_candidate_dispositions_and_source_bindings_survive(saved_projection) -> None:
    case, ranked, projection = saved_projection
    view, receipt = projection.view, projection.receipt
    expected_total, expected_eligible = CASES[case]
    source = ranked.matched
    by_id = {item.candidate_id: item for item in view.alternatives}
    source_by_id = {item.candidate_id: item for item in source.journeys}

    assert len(by_id) == expected_total == len(source_by_id)
    assert receipt.total_candidates == expected_total
    assert receipt.eligible_alternatives == expected_eligible
    assert Counter(item.status for item in by_id.values()) == Counter(
        item.status for item in source_by_id.values()
    )
    assert sum(item.status in {"admitted", "conditional"} for item in by_id.values()) == expected_eligible
    assert {item.candidate_id for item in receipt.candidate_sources} == set(source_by_id)
    receipt_by_id = {item.candidate_id: item for item in receipt.candidate_sources}
    assert receipt.source_digest == content_digest(ranked)
    assert receipt.view_digest == content_digest(view)
    assert receipt.policy_digest == ranked.policy_digest
    assert receipt.fx_snapshot_digest == ranked.fx_snapshot_digest

    for candidate_id, source_journey in source_by_id.items():
        alternative = by_id[candidate_id]
        assert (alternative.option_family_id, alternative.status, alternative.topology) == (
            source_journey.option_family_id, source_journey.status, source_journey.topology
        )
        assert (alternative.award_observation_id, alternative.cash_observation_id) == (
            source_journey.award_observation_id, source_journey.cash_observation_id
        )
        assert (alternative.transfer_airport, alternative.transfer_minutes,
                alternative.booking_obligation, alternative.price_completeness) == (
            source_journey.transfer_airport, source_journey.transfer_minutes,
            source_journey.booking_obligation, source_journey.price_completeness
        )
        mapped = receipt_by_id[candidate_id]
        assert (mapped.award_query_id, mapped.cash_query_id,
                mapped.logical_award_query_ids, mapped.support_id,
                mapped.positioning_dependency_id,
                mapped.activation_observation_ids) == (
            source_journey.award_query_id, source_journey.cash_query_id,
            source_journey.logical_award_query_ids, source_journey.support_id,
            source_journey.positioning_dependency_id,
            source_journey.activation_observation_ids,
        )


def test_component_facts_and_factored_links_survive(saved_projection) -> None:
    _, ranked, projection = saved_projection
    view = projection.view
    source = ranked.matched
    source_observations = {item.observation_id: item for item in source.provider_result.observations}
    components = {item.observation_id: item for item in view.components}
    reasons = {item.reason_set_id: item.reasons for item in view.reason_sets}
    costs = {item.cost_id: item.cost for item in view.costs}
    cost_components = {
        item.cost_component_id: item.component for item in view.cost_components
    }
    assessments = {item.assessment_id: item for item in view.assessments}
    source_features = {item.candidate_id: item for item in ranked.features}
    source_assessments = {
        (item.candidate_id, item.style): item for item in ranked.assessments
    }

    assert set(components) == set(source_observations)
    assert len(view.components) == len(source.provider_result.observations)
    for observation_id, original in source_observations.items():
        component = components[observation_id]
        assert (component.kind, component.query_id, component.origin, component.destination,
                component.airport_sequence, component.price_scope) == (
            original.kind, original.query_id, original.origin, original.destination,
            original.airport_sequence, original.price_scope
        )
        assert (component.points, component.taxes_fees, component.taxes_fees_unit,
                component.tax_currency, component.cash_amount, component.cash_currency,
                component.cabin, component.returned_travelers) == (
            original.points, original.taxes_fees, original.taxes_fees_unit,
            original.tax_currency, original.cash_amount, original.cash_currency,
            original.cabin, original.returned_travelers
        )
        assert len(component.legs) == len(original.legs)
    observation_sources = {
        item.observation_id: item for item in projection.receipt.observation_sources
    }
    assert set(observation_sources) == set(source_observations)
    for observation_id, original in source_observations.items():
        assert observation_sources[observation_id].evidence == original.evidence
    assert len(view.reason_sets) < len(view.alternatives)
    # Cost records retain exact observation IDs, so this corpus has no safe cost aliases.
    assert len(view.costs) <= len(view.alternatives)
    assert len(view.cost_components) < sum(
        len(item.cost.component_ids) for item in view.costs
    )
    assert len(view.assessments) < len(ranked.assessments)
    for alternative in view.alternatives:
        original = next(item for item in source.journeys if item.candidate_id == alternative.candidate_id)
        assert reasons[alternative.reason_set_id] == original.reasons
        projected_cost = costs[alternative.cost_id]
        source_cost = source_features[alternative.candidate_id].cost
        assert tuple(cost_components[item] for item in projected_cost.component_ids) == (
            source_cost.components
        )
        for name in ("known_subtotal_usd", "complete_usd", "exact_subtotal_numerator",
                     "exact_subtotal_denominator", "missing_parts", "completeness"):
            assert getattr(projected_cost, name) == getattr(source_cost, name)
        assert len(alternative.assessment_ids) == 3
        for assessment_id in alternative.assessment_ids:
            projected = assessments[assessment_id]
            original_assessment = source_assessments[alternative.candidate_id, projected.style]
            for name in ("state", "feature_numeric", "feature_label", "reference_value",
                         "threshold", "reasons", "validation_needs"):
                assert getattr(projected, name) == getattr(original_assessment, name)


def test_comparisons_context_and_separate_cash_survive(saved_projection) -> None:
    _, ranked, projection = saved_projection
    source, view = ranked.matched, projection.view
    assert view.request == source.request
    assert view.policy == ranked.policy
    assert view.fx_snapshot == ranked.fx_snapshot
    assert view.provider_status == source.provider_result.status == "partial"
    assert view.comparison_pool_ids == ranked.comparison_pool_ids
    assert view.indexes == ranked.indexes
    assert view.time_reference_minutes == ranked.time_reference_minutes
    assert view.cost_reference_usd is None
    assert view.cost_reference_numerator is None
    assert view.cost_reference_denominator is None
    assert view.direct_cash_observation_ids == source.direct_cash_observation_ids
    assert view.award_summary_observation_ids == source.award_summary_observation_ids
    assert view.unmatched_award_observation_ids == source.unmatched_award_observation_ids
    assert view.unpaired_positioning_observation_ids == source.accounting.unpaired_positioning_observation_ids
    assert view.match_accounting == source.accounting
    assert not set(view.direct_cash_observation_ids) & {
        item.cash_observation_id for item in view.alternatives
    }
    assert all(
        item.state == "undetermined" for item in ranked.assessments
        if item.style == "cost" and item.candidate_id in view.comparison_pool_ids
    )
    assert set(view.comparison_pool_ids) == {
        item.candidate_id for item in view.alternatives
        if item.status in {"admitted", "conditional"}
    }
    assert not set(view.comparison_pool_ids) & {
        item.candidate_id for item in view.alternatives
        if item.status in {"rejected", "research_lead"}
    }
    if len(view.award_summary_observation_ids):
        assert set(view.award_summary_observation_ids) <= {
            item.observation_id for item in view.components if item.kind == "award_summary"
        }


def test_coverage_preserves_partial_and_omitted_without_invented_total(saved_projection) -> None:
    case, ranked, projection = saved_projection
    original = ranked.matched.provider_result.coverage
    groups = projection.view.coverage_groups
    receipt = projection.receipt
    expected_status = {
        "mixed_access": {"completed": 26, "omitted": 128},
        "exact_business": {"completed": 12, "empty": 4, "omitted": 39},
        "sfo_to_bkk_positioning": {"completed": 19, "partial": 1, "omitted": 53},
    }[case]
    assert Counter(item.status for item in original) == expected_status
    assert Counter(status for group in groups for status in [group.status] * len(group.unit_ids)) == expected_status
    assert {item.unit_id for item in receipt.coverage_sources} == {item.unit_id for item in original}
    assert {unit_id for group in groups for unit_id in group.unit_ids} == {
        item.unit_id for item in original
    }
    assert projection.view.planning_coverage == ranked.matched.plan.coverage
    assert projection.view.discovery_limitations == (
        ranked.matched.plan.discovery_receipt.limitations
    )
    assert projection.view.discovery_issues == ranked.matched.plan.discovery_receipt.issues
    assert projection.view.provider_findings == ranked.matched.provider_result.findings
    assert projection.view.execution_findings == (
        ranked.matched.provider_result.execution_plan.findings
    )
    transport_by_id = {
        item.transport_id: item for item in ranked.matched.provider_result.transport_receipts
    }
    assert {item.transport_id for item in projection.view.transport_findings} == set(transport_by_id)
    for item in projection.view.transport_findings:
        assert (item.query_id, item.status, item.findings) == (
            transport_by_id[item.transport_id].query_id,
            transport_by_id[item.transport_id].status,
            transport_by_id[item.transport_id].findings,
        )
    if case == "sfo_to_bkk_positioning":
        omitted = [item for item in original if item.status == "omitted"]
        partial = [item for item in original if item.status == "partial"]
        assert sum(item.unit_id.startswith("detail:") for item in omitted) == 52
        assert len(partial) == 1
        assert not partial[0].stream_complete
        source_units = {
            item.unit_id: item for item in ranked.matched.provider_result.execution_plan.coverage_units
        }
        projected_units = {item.unit_id: item for item in receipt.coverage_sources}
        for item in omitted:
            if not item.unit_id.startswith("detail:"):
                continue
            logical_ids = source_units[item.unit_id].logical_query_ids
            mapping = projected_units[item.unit_id]
            assert mapping.logical_query_ids == logical_ids
            group = groups[mapping.group_index]
            assert group.status == "omitted"
            assert "SFO-BKK:2026-10-05..2026-10-05" in group.routes_and_dates
        assert Counter(item.status for item in projection.view.alternatives) == {
            "admitted": 5, "conditional": 59, "rejected": 58, "research_lead": 1,
        }
    if case == "exact_business":
        assert any(item.status == "empty" and item.pair_coverage == "empty"
                   for item in original)


def test_aeroplan_egress_variants_keep_literal_tradeoff_and_local_time() -> None:
    _, ranked, projection = _projection_for("sfo_to_bkk_positioning")
    view = projection.view
    alternatives = {item.candidate_id: item for item in view.alternatives}
    components = {item.observation_id: item for item in view.components}
    cheap = alternatives["f7d024bb65a87fe25bd14e71dbbf51c35f0a1995e3e9cc22fa112e677ed7eab9"]
    fast = alternatives["89c654f54213139f2dc31c512e185f9b00f88588c61bd4bd963f9a2a25cb8f12"]
    assert cheap.candidate_id != fast.candidate_id
    assert cheap.option_family_id == fast.option_family_id
    assert cheap.award_observation_id == fast.award_observation_id == (
        "2e93cc515d735b0959ce54d64c6b9804334f97982cc26bf4668df1ecee655f6f"
    )
    assert cheap.cash_observation_id != fast.cash_observation_id
    assert (cheap.status, fast.status) == ("admitted", "admitted")
    assert (cheap.elapsed_minutes, fast.elapsed_minutes) == (1790, 1650)
    assert (cheap.transfer_minutes, fast.transfer_minutes) == (380, 230)
    assert (cheap.booking_obligation, fast.booking_obligation) == (
        "separate_tickets_unverified", "separate_tickets_unverified"
    )
    assert (cheap.price_completeness, fast.price_completeness) == ("partial", "partial")
    assert components[cheap.cash_observation_id].cash_amount.value == 196
    assert components[fast.cash_observation_id].cash_amount.value == 290
    assert components[cheap.cash_observation_id].price_scope == "unknown"
    assert components[fast.cash_observation_id].price_scope == "unknown"
    award = components[cheap.award_observation_id]
    assert award.departure.instant.isoformat() == "2026-10-06T06:45:00+00:00"
    assert award.departure.local_iso.startswith("2026-10-05T23:45:00")
    assert award.departure.timezone == "America/Los_Angeles"
    assert award.points.value == 65000
    assert award.taxes_fees.value == 11320
    assert award.taxes_fees_unit == "minor"
    assert award.tax_currency.value == "CAD"
    assert award.cabin.value == "economy"
    assert award.mixed_cabin_pct.state == "absent"
    assert all(leg.cabin.state == "absent" for leg in award.legs)
    assert view.cost_reference_usd is None
    assert cheap.candidate_id in view.indexes.time
    assert fast.candidate_id in view.indexes.time
    raw = {item.observation_id: item for item in ranked.matched.provider_result.observations}
    source_map = {item.observation_id: item for item in projection.receipt.observation_sources}
    assert raw[award.observation_id].departure_local == "2026-10-05T23:45:00Z"
    assert source_map[award.observation_id].raw_departure_local == "2026-10-05T23:45:00Z"
    assert components[cheap.cash_observation_id].departure.local_iso.startswith(
        "2026-10-07T18:15:00"
    )
    assert components[fast.cash_observation_id].departure.local_iso.startswith(
        "2026-10-07T15:45:00"
    )
    fastest = alternatives["5d002456b188f5e55d40d9262efe5ef68e3849b90f50cd7aa09fc78d1a449f84"]
    assert fastest.status == "conditional"
    assert fastest.elapsed_minutes == 1647
    assert fastest.transfer_minutes == 138
    assert fastest.topology == "cash_access_award"
    assert fastest.departure.instant.isoformat() == "2026-10-05T23:13:00+00:00"
    assert fastest.arrival.instant.isoformat() == "2026-10-07T02:40:00+00:00"
    assert view.time_reference_minutes == Decimal(1647)


def test_zero_fee_remains_observed_while_missing_fee_stays_estimated() -> None:
    _, _, saved = _projection_for("mixed_access")
    missing_components = [item.component for item in saved.view.cost_components]
    assert any(
        component.kind == "award_taxes" and component.state == "estimated"
        and component.raw_amount.state == "unknown" and component.per_traveler_usd == Decimal(150)
        for component in missing_components
    )
    ranked = assign_journey_styles(
        _synthetic_match(), policy=RankingStylePolicy(), fx_snapshot=_snapshot()
    )
    projected = project_solutions(ranked)
    components = [item.component for item in projected.view.cost_components]
    assert any(
        component.kind == "award_taxes" and component.state == "observed"
        and component.raw_amount.value == 0 and component.per_traveler_usd == Decimal(0)
        for component in components
    )


def test_reported_mixed_cabin_flights_and_missing_local_zone_are_preserved() -> None:
    matched = _synthetic_match()
    provider = matched.provider_result
    target = next(item for item in provider.observations if item.kind == "award_itinerary")
    changed = target.model_copy(update={
        "raw_fields": {
            **target.raw_fields,
            "flightNumbers": RawField(state="value", value=["UA123"], source_field="flightNumbers"),
            "MixedCabinPct": RawField(state="value", value=25, source_field="MixedCabinPct"),
        },
        "origin_timezone": "Unknown/Zone",
    })
    revised_provider = ProviderResultSet.model_validate(provider.model_copy(update={
        "observations": tuple(changed if item.observation_id == target.observation_id else item
                              for item in provider.observations),
    }).model_dump())
    revised_match = MatchedJourneySet.model_validate(matched.model_copy(update={
        "provider_result": revised_provider,
        "provider_result_digest": content_digest(revised_provider),
    }).model_dump())
    ranked = assign_journey_styles(
        revised_match, policy=RankingStylePolicy(), fx_snapshot=_snapshot()
    )
    projection = project_solutions(ranked)
    components = {item.observation_id: item for item in projection.view.components}
    projected = components[target.observation_id]
    assert projected.reported_flight_numbers == changed.raw_fields["flightNumbers"]
    assert projected.mixed_cabin_pct == changed.raw_fields["MixedCabinPct"]
    assert projected.departure.instant == changed.departure_instant
    assert projected.departure.local_iso is None
    assert projected.departure.timezone == "Unknown/Zone"
    assert any(item.reported_flight_numbers.state == "absent" for item in components.values())


def test_provider_failure_findings_remain_visible_in_partial_run() -> None:
    matched = _synthetic_match()
    original = matched.provider_result
    finding = ValidationFinding(
        code="synthetic_provider_timeout", severity="error",
        message="One provider call timed out after returning other results.",
    )
    transport = original.transport_receipts[0]
    revised_transport = transport.model_copy(update={
        "findings": (*transport.findings, finding),
    })
    revised_provider = ProviderResultSet.model_validate(original.model_copy(update={
        "findings": (*original.findings, finding),
        "transport_receipts": (revised_transport, *original.transport_receipts[1:]),
    }).model_dump())
    revised_match = MatchedJourneySet.model_validate(matched.model_copy(update={
        "provider_result": revised_provider,
        "provider_result_digest": content_digest(revised_provider),
    }).model_dump())
    ranked = assign_journey_styles(
        revised_match, policy=RankingStylePolicy(), fx_snapshot=_snapshot()
    )
    view = project_solutions(ranked).view
    assert view.provider_status == "partial"
    assert finding in view.provider_findings
    projected_transport = next(
        item for item in view.transport_findings if item.transport_id == transport.transport_id
    )
    assert finding in projected_transport.findings


def test_receipt_rejects_wrong_candidate_and_coverage_associations() -> None:
    _, _, projection = _projection_for("sfo_to_bkk_positioning")
    receipt = projection.receipt
    first = receipt.candidate_sources[0]
    other_award = next(item.award_observation_id for item in receipt.candidate_sources
                       if item.award_observation_id != first.award_observation_id)
    wrong_candidate = first.model_copy(update={"award_observation_id": other_award})
    changed = receipt.model_copy(update={
        "candidate_sources": (wrong_candidate, *receipt.candidate_sources[1:]),
    })
    with pytest.raises(ValidationError, match="candidate source map differs"):
        SolutionProjection.model_validate({"view": projection.view, "receipt": changed})

    first_coverage = receipt.coverage_sources[0]
    wrong_index = (first_coverage.group_index + 1) % len(projection.view.coverage_groups)
    wrong_coverage = first_coverage.model_copy(update={"group_index": wrong_index})
    changed = receipt.model_copy(update={
        "coverage_sources": (wrong_coverage, *receipt.coverage_sources[1:]),
    })
    with pytest.raises(ValidationError, match="coverage source map differs"):
        SolutionProjection.model_validate({"view": projection.view, "receipt": changed})


def test_projection_replays_byte_stably_without_booking_tokens(saved_projection) -> None:
    _, ranked, first = saved_projection
    second = project_solutions(ranked)
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.receipt.view_digest == second.receipt.view_digest
    assert "bookingToken" not in first.model_dump_json()
