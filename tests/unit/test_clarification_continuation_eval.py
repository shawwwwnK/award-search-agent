from pathlib import Path

import pytest
import yaml

from award_agent.evaluation.clarification_continuation import (
    DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES,
    ClarificationContinuationFixtureError,
    preflight_clarification_continuation_cases,
    run_clarification_continuation_eval,
)


def test_offline_continuation_fixture_preflight_and_exact_gate() -> None:
    cases = preflight_clarification_continuation_cases()
    assert len(cases) >= 16

    artifact = run_clarification_continuation_eval()

    assert artifact["fixture"]["path"] == str(DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES)
    assert artifact["fixture"]["redacted"] is True
    assert artifact["summary"]["exact_gate"]["passed"] is True
    assert artifact["summary"]["failed"] == 0
    assert artifact["summary"]["prompt_coverage"]["rate"] == 1.0
    resolution = artifact["summary"]["requirement_resolution"]
    assert resolution["resolved_requirements"] == 36
    assert resolution["linked_amendments"] == 28
    assert 0.0 <= resolution["precision"] <= 1.0
    assert 0.0 <= resolution["recall"] <= 1.0
    acceptance = artifact["summary"]["accepted_amendment_correctness"]
    assert acceptance["expected"] == 38
    assert acceptance["actual"] == 38
    assert acceptance["matched"] == 38
    assert acceptance["precision"] == 1.0
    assert acceptance["recall"] == 1.0
    assert artifact["summary"]["instrumentation"] == {
        "controller_calls": 34,
        "latency_seconds": 0.0,
        "tokens": 0,
        "errors": 8,
    }
    assert artifact["summary"]["privacy_audit"] == {"passed": True, "violations": []}
    assert artifact["summary"]["equivalent_outcomes"]["passed"] is True
    assert all("projection" in record for record in artifact["records"])
    assert all("prompt_coverage" in record for record in artifact["records"])
    assert {record["scenario"] for record in artifact["records"]} >= {
        "all_at_once",
        "subset_multi_turn",
        "replay_and_message_mismatch",
        "conflict_first_then_ready",
    }


def test_continuation_fixture_rejects_private_payload_marker(tmp_path: Path) -> None:
    copied = tmp_path / "cases.yaml"
    copied.write_text(DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES.read_text() + "\napi_key: forbidden\n")

    with pytest.raises(ClarificationContinuationFixtureError, match="privacy lint"):
        preflight_clarification_continuation_cases(copied)


def test_continuation_fixture_requires_independent_acceptance_oracles(tmp_path: Path) -> None:
    copied = tmp_path / "cases.yaml"
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES.read_text())
    del payload["scenarios"][0]["turns"][0]["expect"]["accepted"]
    copied.write_text(yaml.safe_dump(payload))

    with pytest.raises(ClarificationContinuationFixtureError, match="explicit accepted oracle"):
        preflight_clarification_continuation_cases(copied)


def test_continuation_final_projection_fingerprint_is_an_executable_oracle(tmp_path: Path) -> None:
    copied = tmp_path / "cases.yaml"
    copied.write_text(
        DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES.read_text().replace(
                "b40796c1cbd2668ff82b96178b4ee78be82ce45c094c9ca0ac73685ed31a9963",
                "f" * 64,
            1,
        )
    )

    artifact = run_clarification_continuation_eval(copied)

    assert artifact["summary"]["exact_gate"]["passed"] is False
    assert artifact["summary"]["failed"] == 1
    assert artifact["summary"]["prompt_coverage"] == {"runs": 41, "passed": 41, "rate": 1.0}
    assert "final projection fingerprint" in artifact["records"][0]["checks"]["failures"][0]


def test_continuation_acceptance_oracle_compares_normalized_payload_and_correction(tmp_path: Path) -> None:
    copied = tmp_path / "cases.yaml"
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES.read_text())
    accepted = payload["scenarios"][0]["turns"][0]["expect"]["accepted"]
    accepted[0]["payload"]["locations"][0]["value"] = "ZZZ"
    accepted[0]["is_correction"] = True
    copied.write_text(yaml.safe_dump(payload))

    artifact = run_clarification_continuation_eval(copied)

    first_record = artifact["records"][0]
    assert first_record["status"] == "failed"
    assert first_record["accepted_oracle"]["exact"] is False
    assert "is_correction" in first_record["checks"]["failures"][-1]
    assert artifact["summary"]["accepted_amendment_correctness"]["matched"] == 37
