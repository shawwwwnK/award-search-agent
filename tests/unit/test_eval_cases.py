from hashlib import sha256
from pathlib import Path

import pytest
import yaml

from award_agent.cli.intent_eval import (
    _REQUIRED_COVERAGE_FAMILIES,
    DEFAULT_ONE_WAY_AWARD_CASES,
    _load_ready_scenarios,
    _preflight_one_way_award_cases,
)


def test_active_one_way_award_eval_cases_have_executable_expectations() -> None:
    payload = yaml.safe_load(DEFAULT_ONE_WAY_AWARD_CASES.read_text())
    scenarios = payload["scenarios"]

    assert payload["contract_version"] == "intent_behavior_v1"
    assert len(scenarios) == 19
    assert len({scenario["id"] for scenario in scenarios}) == len(scenarios)
    assert {scenario["coverage_family"] for scenario in scenarios} == _REQUIRED_COVERAGE_FAMILIES
    assert all(scenario.get("status") == "ready" for scenario in scenarios)
    assert all("oracle" in scenario for scenario in scenarios)
    assert all("acceptable_actions" in scenario["oracle"] for scenario in scenarios)
    assert all("forbidden_outcomes" in scenario["oracle"] for scenario in scenarios)


def test_active_one_way_award_eval_covers_scope_and_eligibility_outcomes() -> None:
    cases = {
        item["id"]: item["oracle"] for item in _load_ready_scenarios(DEFAULT_ONE_WAY_AWARD_CASES)
    }

    assert cases["ready_exact_airports"]["acceptable_actions"] == ["ready"]
    for identifier, missing in {
        "missing_origin": "origin",
        "missing_destination": "destination",
        "missing_departure": "departure",
        "missing_travelers": "travelers",
    }.items():
        assert cases[identifier]["must_remain_blocked"] == [missing]
    for identifier in (
        "explicit_return_unsupported",
        "duration_return_unsupported",
        "relative_return_unsupported",
    ):
        assert cases[identifier]["properties"]["unsupported_codes"] == [
            "return_or_duration_not_supported"
        ]
        assert cases[identifier]["clarification_field"] == "one_way_award_scope"
    assert cases["cash_only_unsupported"]["properties"]["unsupported_codes"] == [
        "cash_only_not_supported"
    ]
    assert cases["mixed_award_cash_eligible"]["properties"]["modes"] == ["award", "cash"]
    assert cases["mixed_award_cash_eligible"]["acceptable_actions"] == ["ready"]


def test_active_one_way_award_corpus_hash_binds_the_exact_fixture() -> None:
    preflighted = _preflight_one_way_award_cases(DEFAULT_ONE_WAY_AWARD_CASES)

    assert (
        preflighted.fixture_sha256 == sha256(DEFAULT_ONE_WAY_AWARD_CASES.read_bytes()).hexdigest()
    )
    assert preflighted.contract_version == "intent_behavior_v1"
    assert len(preflighted.scenarios) == 19


@pytest.mark.parametrize(
    "before, after, match",
    [
        ("contract_version: intent_behavior_v1", "contract_version: old", "contract version"),
        (
            "coverage_family: ready_exact_airports",
            "coverage_family: duplicate",
            "coverage families",
        ),
        ("acceptable_actions: [ready]", "acceptable_actions: []", "acceptable_actions"),
    ],
)
def test_active_one_way_award_preflight_rejects_contract_coverage_and_retired_fields(
    tmp_path: Path, before: str, after: str, match: str
) -> None:
    fixture = tmp_path / "cases.yaml"
    fixture.write_text(DEFAULT_ONE_WAY_AWARD_CASES.read_text().replace(before, after, 1))

    with pytest.raises(ValueError, match=match):
        _preflight_one_way_award_cases(fixture)


def test_historical_round_trip_corpus_remains_present_but_is_not_the_active_default() -> None:
    historical = Path("evals/intent/cases.yaml")

    assert historical.exists()
    assert historical != DEFAULT_ONE_WAY_AWARD_CASES
