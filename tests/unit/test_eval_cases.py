from pathlib import Path

import yaml


def test_all_intent_eval_cases_have_executable_expectations() -> None:
    path = Path("evals/intent/cases.yaml")
    payload = yaml.safe_load(path.read_text())
    scenarios = payload["scenarios"]

    assert len(scenarios) == 10
    assert len({scenario["id"] for scenario in scenarios}) == len(scenarios)
    assert all(scenario["status"] == "ready" for scenario in scenarios)
    assert all("clarification" in scenario["expected"] for scenario in scenarios)
