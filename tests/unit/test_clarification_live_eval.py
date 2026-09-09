from pathlib import Path

import pytest

from award_agent.evaluation.clarification_live import (
    DEFAULT_LIVE_CLARIFICATION_FIXTURES,
    ClarificationLiveFixtureError,
    _load_cases,
)


def test_live_fixture_preflight_is_synthetic_and_has_qualification_coverage() -> None:
    cases, _ = _load_cases(DEFAULT_LIVE_CLARIFICATION_FIXTURES)

    assert len(cases) >= 12
    assert {str(case["id"]) for case in cases} >= {
        "all_at_once",
        "bare_date_recovery",
        "departure_correction",
        "no_progress_limit",
    }


def test_live_fixture_rejects_private_marker(tmp_path: Path) -> None:
    path = tmp_path / "live.yaml"
    path.write_text(DEFAULT_LIVE_CLARIFICATION_FIXTURES.read_text() + "\napi_key: forbidden\n")

    with pytest.raises(ClarificationLiveFixtureError, match="privacy"):
        _load_cases(path)
