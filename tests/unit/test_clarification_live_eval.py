from pathlib import Path

import pytest

from award_agent.evaluation.clarification_live import (
    DEFAULT_LIVE_CLARIFICATION_FIXTURES,
    ClarificationLiveFixtureError,
    _load_cases,
    _required_terminal_correct,
)


def test_live_fixture_preflight_is_synthetic_and_has_qualification_coverage() -> None:
    cases, _ = _load_cases(DEFAULT_LIVE_CLARIFICATION_FIXTURES)

    assert len(cases) >= 16
    assert {str(case["id"]) for case in cases} >= {
        "all_at_once",
        "bare_date_recovery",
        "departure_correction",
        "no_progress_limit",
        "numbered_next_weekend_afterwards_and_solo",
        "numbered_next_friday_and_date_and_solo",
        "numbered_this_weekend_and_monday",
        "ambiguous_disjunctive_relative_dates",
    }
    assert {
        str(case["id"])
        for case in cases
        if case.get("qualification_target") is True
    } == {
        "numbered_next_weekend_afterwards_and_solo",
        "numbered_next_friday_and_date_and_solo",
        "departure_only",
    }


def test_live_fixture_rejects_private_marker(tmp_path: Path) -> None:
    path = tmp_path / "live.yaml"
    path.write_text(DEFAULT_LIVE_CLARIFICATION_FIXTURES.read_text() + "\napi_key: forbidden\n")

    with pytest.raises(ClarificationLiveFixtureError, match="privacy"):
        _load_cases(path)


def test_live_gate_terminal_threshold_scales_with_session_count() -> None:
    assert _required_terminal_correct(36) == 35
    assert _required_terminal_correct(48) == 46
