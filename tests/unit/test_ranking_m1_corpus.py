"""Plan-linked live records exercise M1 assembly without provider calls."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from award_agent.cli.provider_results import ProviderInputBundle
from award_agent.providers.contracts import ProviderResultSet, content_digest
from award_agent.ranking import assemble_matched_journeys

RUNS = Path("evidence/provider-stage/saved-searches/runs")


def _saved_run(case: str) -> tuple[ProviderInputBundle, ProviderResultSet]:
    directory = RUNS / case
    return (
        ProviderInputBundle.model_validate_json((directory / "bundle.json").read_text()),
        ProviderResultSet.model_validate_json((directory / "result.json").read_text()),
    )


def _assemble(bundle: ProviderInputBundle, result: ProviderResultSet):
    return assemble_matched_journeys(
        bundle.plan,
        result,
        current_session_id=bundle.current_session_id,
        current_revision=bundle.current_revision,
        current_effective_request=bundle.current_effective_request,
        expected_compilation_binding_digest=bundle.expected_compilation_binding_digest,
        policy=bundle.policy,
        award_capability=bundle.award_capability,
        cash_capability=bundle.cash_capability,
    )


@pytest.mark.parametrize(
    ("case", "expected_awards", "expected_cash", "expected_benchmark", "expected_pairs"),
    [
        ("mixed_access", 23, 76, 4, 456),
        ("exact_business", 6, 66, 6, 396),
        ("sfo_to_bkk_positioning", 4, 49, 8, 123),
    ],
)
def test_plan_linked_matching_accounts_for_every_observed_component(
    case: str, expected_awards: int, expected_cash: int,
    expected_benchmark: int, expected_pairs: int,
) -> None:
    bundle, result = _saved_run(case)
    first = _assemble(bundle, result)
    second = _assemble(bundle, result)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")

    # The output carries the full authoritative sources, not reconstructed snippets.
    assert first.plan == bundle.plan
    assert first.request == bundle.current_effective_request
    assert first.provider_result == result
    assert first.provider_result_digest == content_digest(result)
    assert first.plan_digest == bundle.plan.plan_digest
    assert first.provider_run_id == result.execution_plan.binding.run_id

    observations = {item.observation_id: item for item in result.observations}
    queries = {item.query_id: item for item in result.execution_plan.queries}
    award_ids = {oid for oid, item in observations.items() if item.kind == "award_itinerary"}
    positioning_ids = {
        oid for oid, item in observations.items()
        if item.kind == "cash_itinerary"
        and queries[item.query_id].role in {"cash_access", "cash_egress"}
    }
    benchmark_ids = {
        oid for oid, item in observations.items()
        if item.kind == "cash_itinerary" and queries[item.query_id].role == "direct_cash"
    }
    summary_ids = {oid for oid, item in observations.items() if item.kind == "award_summary"}
    assert (len(award_ids), len(positioning_ids), len(benchmark_ids)) == (
        expected_awards, expected_cash, expected_benchmark,
    )
    assert set(first.award_summary_observation_ids) == summary_ids
    assert set(first.direct_cash_observation_ids) == benchmark_ids
    assert not any(j.cash_observation_id in benchmark_ids for j in first.journeys)

    # Derive the expected cross product from the source plan and physical cash queries,
    # independently of the matching result's own pairing receipts.
    uses = {use.query_use_id: use.query_id for use in bundle.plan.strategy_query_uses}
    expected: set[tuple[str, str, str, str]] = set()
    for support in bundle.plan.support_alternatives:
        if not support.positioning_dependency_ids:
            continue
        logical_queries = {uses[uid] for uid in support.query_use_ids}
        for dependency_id in support.positioning_dependency_ids:
            dependency = next(d for d in bundle.plan.positioning_dependencies
                              if d.dependency_id == dependency_id)
            role = "cash_access" if dependency.side == "origin" else "cash_egress"
            awards = [item for item in result.observations
                      if item.kind == "award_itinerary"
                      and support.strategy_id in item.strategy_ids
                      and logical_queries.intersection(item.logical_query_ids)]
            cash = [item for item in result.observations
                    if item.observation_id in positioning_ids
                    and queries[item.query_id].role == role
                    and dependency_id in queries[item.query_id].positioning_dependency_ids]
            expected.update((support.support_id, dependency_id,
                             award.observation_id, item.observation_id)
                            for award in awards for item in cash)
    actual = {
        (j.support_id, j.positioning_dependency_id,
         j.award_observation_id, j.cash_observation_id)
        for j in first.journeys if j.cash_observation_id is not None
    }
    assert actual == expected
    assert len(actual) == first.accounting.scoped_pairs == expected_pairs
    assert first.accounting.retained_mixed == expected_pairs
    assert sum(receipt.enumerated_pairs for receipt in first.pairing_receipts) == expected_pairs
    assert Counter(j.status for j in first.journeys)["conditional"] > 0
    for journey in first.journeys:
        assert journey.award_observation_id in award_ids
        if journey.cash_observation_id is not None:
            assert journey.cash_observation_id in positioning_ids
            assert journey.positioning_reason
            assert journey.booking_obligation == "separate_tickets_unverified"
            assert journey.price_completeness != "known"


def test_exact_business_rejects_october_4_awards_joined_to_october_5_cash() -> None:
    bundle, result = _saved_run("exact_business")
    matched = _assemble(bundle, result)
    off_window = {
        item.observation_id for item in result.observations
        if item.kind == "award_itinerary" and item.departure_date.isoformat() == "2026-10-04"
    }
    assert len(off_window) == 3
    off_window_journeys = [j for j in matched.journeys if j.award_observation_id in off_window]
    assert len(off_window_journeys) == 3 * 66
    assert all(j.status == "rejected" for j in off_window_journeys)
    # The complete journey starts on October 5 with cash access, so the original
    # departure window passes; the prior-day award fails chronological transfer.
    assert all(j.original_departure_date.isoformat() == "2026-10-05"
               for j in off_window_journeys)
    assert all(any(reason.code == "transfer_negative"
                   for reason in j.reasons) for j in off_window_journeys)
