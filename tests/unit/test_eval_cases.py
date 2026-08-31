from pathlib import Path

import yaml


def test_all_intent_eval_cases_have_executable_expectations() -> None:
    path = Path("evals/intent/cases.yaml")
    payload = yaml.safe_load(path.read_text())
    scenarios = payload["scenarios"]

    assert len(scenarios) == 138
    assert len({scenario["id"] for scenario in scenarios}) == len(scenarios)
    assert all("clarification" in scenario["expected"] for scenario in scenarios)

    ready_scenarios = [scenario for scenario in scenarios if scenario.get("status") == "ready"]
    candidate_scenarios = [scenario for scenario in scenarios if "status" not in scenario]

    assert len(ready_scenarios) == 16
    assert len(candidate_scenarios) == 122
    assert all("layer" in scenario for scenario in candidate_scenarios)
    assert all(
        scenario.get("evaluator", {}).get("type")
        in {"exact", "invariant", "repeated_live_run"}
        for scenario in candidate_scenarios
    )


def test_ready_location_aliases_are_explicit_nonempty_string_lists() -> None:
    payload = yaml.safe_load(Path("evals/intent/cases.yaml").read_text())
    ready_scenarios = [
        scenario
        for scenario in payload["scenarios"]
        if scenario.get("status") == "ready"
    ]

    aliased_locations = []
    for scenario in ready_scenarios:
        expected = scenario["expected"]
        for field in ("origin", "destination"):
            location = expected.get(field)
            if isinstance(location, dict) and "accepted_values" in location:
                aliased_locations.append(location)

    assert aliased_locations
    assert all(
        isinstance(location["accepted_values"], list)
        and location["accepted_values"]
        and all(
            isinstance(value, str) and value
            for value in location["accepted_values"]
        )
        and isinstance(location.get("raw_text"), str)
        and location["raw_text"]
        for location in aliased_locations
    )
