"""Saved M1 corpus replays Ranking M2 without model or provider calls."""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from award_agent.cli.provider_results import ProviderInputBundle
from award_agent.providers.contracts import ProviderResultSet, content_digest
from award_agent.ranking import (
    CurrencyConversionSnapshot,
    RankingStylePolicy,
    assemble_matched_journeys,
    assign_journey_styles,
)


@pytest.mark.parametrize("case", ["mixed_access", "exact_business", "sfo_to_bkk_positioning"])
def test_saved_matching_corpus_retained_and_stably_styled(case: str) -> None:
    directory = Path("evidence/provider-stage/saved-searches/runs") / case
    bundle = ProviderInputBundle.model_validate_json((directory / "bundle.json").read_text())
    result = ProviderResultSet.model_validate_json((directory / "result.json").read_text())
    matched = assemble_matched_journeys(
        bundle.plan, result, current_session_id=bundle.current_session_id,
        current_revision=bundle.current_revision,
        current_effective_request=bundle.current_effective_request,
        expected_compilation_binding_digest=bundle.expected_compilation_binding_digest,
        policy=bundle.policy, award_capability=bundle.award_capability,
        cash_capability=bundle.cash_capability,
    )
    snapshot = CurrencyConversionSnapshot(
        snapshot_id="synthetic-corpus", as_of=date(2026, 9, 29), source="test-only",
        source_digest="a" * 64, rates_to_usd={"USD": Decimal(1), "CAD": Decimal("0.7")},
    )
    first = assign_journey_styles(matched, policy=RankingStylePolicy(), fx_snapshot=snapshot)
    second = assign_journey_styles(matched, policy=RankingStylePolicy(), fx_snapshot=snapshot)
    assert first == second
    assert first.matched == matched
    assert first.matched_digest == content_digest(matched)
    assert len(first.features) == len(matched.journeys)
    assert len(first.assessments) == 3 * len(matched.journeys)
    assert {feature.candidate_id for feature in first.features} == {
        journey.candidate_id for journey in matched.journeys
    }
    assert first.cost_reference_usd is None
    assert not first.indexes.cost and not first.indexes.possible_cost
    assert not first.indexes.possible_highlights
    assert len(first.comparison_pool_ids) == sum(
        journey.status in {"admitted", "conditional"} for journey in matched.journeys
    )
    assert len(first.indexes.excluded) == sum(
        journey.status in {"rejected", "research_lead"} for journey in matched.journeys
    )
    assert Counter(item.style for item in first.assessments) == {
        "time": len(matched.journeys), "cost": len(matched.journeys),
        "premium": len(matched.journeys),
    }
    assert first.matched.provider_result == matched.provider_result
    assert first.matched.direct_cash_observation_ids == matched.direct_cash_observation_ids
    expected = {
        "mixed_access": (473, 257, 5, 120, 0),
        "exact_business": (396, 106, 34, 106, 34),
        "sfo_to_bkk_positioning": (123, 64, 22, 0, 0),
    }[case]
    assert (len(first.features), len(first.comparison_pool_ids), len(first.indexes.time),
            len(first.indexes.premium), len(first.indexes.definite_highlights)) == expected


def test_captured_fx_snapshot_attaches_without_refresh() -> None:
    snapshot = CurrencyConversionSnapshot.model_validate_json(
        Path("data/ranking/m2/fx-2026-09-29.json").read_text()
    )
    assert snapshot.rates_to_usd == {
        "USD": Decimal(1), "CAD": Decimal("0.7048209754722300535663941359"),
    }
    capture = Path("data/ranking/m2/fx-source-2026-09-29.json").read_bytes()
    assert snapshot.source_digest == sha256(capture).hexdigest()
