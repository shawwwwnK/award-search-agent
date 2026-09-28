"""Real cash capture replay through the current trace-derived graph, without live calls."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from award_agent.cli.provider_results import ProviderInputBundle, main
from award_agent.providers.contracts import ProviderResultSet
from award_agent.providers.replay import ReplayTape

EVIDENCE = Path("evidence/provider-stage")
MIXED_ACCESS_RUN = EVIDENCE / "saved-searches/runs/mixed_access"


def make_mixed_access_replay() -> tuple[ProviderInputBundle, ReplayTape]:
    """Plan-backed live run with award, access cash, and direct cash captures."""
    return (
        ProviderInputBundle.model_validate_json((MIXED_ACCESS_RUN / "bundle.json").read_text()),
        ReplayTape.model_validate_json((MIXED_ACCESS_RUN / "tape.json").read_text()),
    )


def test_cli_plan_makes_no_provider_calls_and_preserves_full_graph(tmp_path: Path) -> None:
    bundle, _ = make_mixed_access_replay()
    source = tmp_path / "bundle.json"
    output = tmp_path / "plan.json"
    source.write_text(bundle.model_dump_json())
    assert main(["--bundle", str(source), "--output", str(output)]) == 0
    document = json.loads(output.read_text())
    assert len([query for query in document["queries"] if query["provider"] == "seats_aero"]) == len(bundle.plan.logical_queries)


def test_cli_replays_plan_backed_award_and_cash_captures(tmp_path: Path) -> None:
    bundle, tape = make_mixed_access_replay()
    source, tape_path, output = (tmp_path / name for name in ("bundle.json", "tape.json", "result.json"))
    source.write_text(bundle.model_dump_json())
    tape_path.write_text(tape.model_dump_json())
    assert main(["--bundle", str(source), "--tape", str(tape_path),
                 "--output", str(output), "--mode", "replay"]) == 1
    result = ProviderResultSet.model_validate_json(output.read_text())
    assert result.status == "partial"
    assert {observation.provider for observation in result.observations} == {"seats_aero", "gfly"}
    assert len(result.observations) == 315
    assert Counter(item.kind for item in result.observations) == {
        "award_summary": 212,
        "award_itinerary": 23,
        "cash_itinerary": 80,
    }
    assert result.award_usage.attempts == 10
    assert result.cash_usage.attempts == 3
    assert Counter(receipt.status for receipt in result.coverage) == {
        "completed": 26,
        "omitted": 128,
    }
    assert all(receipt.reason == "resource_budget_exhausted"
               for receipt in result.coverage if receipt.status == "omitted")
    assert all(observation.price_scope == "unknown" for observation in result.observations
               if observation.provider == "gfly")
    for field in ("backend", "provider_version"):
        forged = result.model_dump(mode="json")
        forged["observations"][0][field] = "unbound-provider-implementation"
        with pytest.raises(ValidationError, match="backend/version"):
            ProviderResultSet.model_validate(forged)
