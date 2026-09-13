from pathlib import Path

import yaml

from award_agent.evaluation.one_way_award_clarification import (
    DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES,
    OneWayAwardClarificationFixtureError,
    preflight_one_way_award_clarification_cases,
    run_offline_one_way_award_clarification_eval,
)


def test_one_way_clarification_fixture_and_public_controller_gate() -> None:
    cases = preflight_one_way_award_clarification_cases()
    artifact = run_offline_one_way_award_clarification_eval()

    assert len(cases) == 2
    assert artifact["passed"] is True
    records = {item["id"]: item for item in artifact["records"]}
    assert records["return_notice_with_outbound_fact_stops_without_mutation"]["checks"] == {
        "status": True,
        "blockers": True,
        "departure": True,
        "scope_notice": True,
        "prompt_scope_notice": True,
        "no_return_state": True,
    }
    assert records["return_notice_without_outbound_fact_stops"]["checks"]["prompt_scope_notice"] is True


def test_one_way_clarification_fixture_rejects_retired_oracle_shape(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES.read_text())
    payload["scenarios"][0]["expected"]["return_window"] = "2026-10-15"
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(yaml.safe_dump(payload))

    try:
        preflight_one_way_award_clarification_cases(invalid)
    except OneWayAwardClarificationFixtureError as exc:
        assert "invalid shape" in str(exc)
    else:
        raise AssertionError("retired return oracle was accepted")
