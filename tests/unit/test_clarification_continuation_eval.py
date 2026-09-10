from pathlib import Path

import pytest
import yaml

from award_agent.evaluation.clarification_continuation import (
    DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES,
    ClarificationContinuationFixtureError,
    _initial,
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
    assert resolution["resolved_requirements"] == 46
    assert resolution["linked_amendments"] == 38
    assert 0.0 <= resolution["precision"] <= 1.0
    assert 0.0 <= resolution["recall"] <= 1.0
    acceptance = artifact["summary"]["accepted_amendment_correctness"]
    assert acceptance["expected"] == 48
    assert acceptance["actual"] == 48
    assert acceptance["matched"] == 48
    assert acceptance["precision"] == 1.0
    assert acceptance["recall"] == 1.0
    template_coverage = artifact["summary"]["template_coverage"]
    assert template_coverage["exact"] is True
    assert template_coverage["expected"] == 13
    assert template_coverage["actual"] == 13
    assert template_coverage["matched"] == 13
    assert set(template_coverage["per_template"]) == {
        "next_weekday",
        "next_weekend",
        "on_weekday",
        "this_weekday",
        "this_weekend",
        "weekday_afterwards",
    }
    assert template_coverage["per_target_template"]["departure:next_weekend"]["exact"] is True
    assert template_coverage["per_target_template"]["return_or_duration:weekday_afterwards"]["exact"] is True
    assert artifact["summary"]["scenario_groups"] == {
        "fresh_generated_registry": {"scenarios": 4, "turns": 8, "passed": 8, "failed": 0},
        "registry_baseline": {"scenarios": 4, "turns": 5, "passed": 5, "failed": 0},
    }
    assert artifact["summary"]["instrumentation"] == {
        "controller_calls": 39,
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
        "numbered_next_weekend_afterwards_and_solo",
        "numbered_next_friday_and_date_and_solo",
        "numbered_this_weekend_and_monday",
        "ambiguous_disjunctive_relative_dates",
    }


def test_continuation_fixture_reference_date_is_explicit_or_defaults_for_existing_cases() -> None:
    cases = {case.identifier: case for case in preflight_clarification_continuation_cases()}

    assert (
        _initial(cases["all_at_once"].payload).parsed_request.context.reference_date.isoformat()
        == "2026-09-08"
    )
    assert (
        _initial(cases["numbered_next_weekend_afterwards_and_solo"].payload)
        .parsed_request.context.reference_date.isoformat()
        == "2026-09-09"
    )


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


def test_continuation_scripted_adapter_requires_explicit_template_selection(tmp_path: Path) -> None:
    copied = tmp_path / "cases.yaml"
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES.read_text())
    all_at_once = next(scenario for scenario in payload["scenarios"] if scenario["id"] == "all_at_once")
    del all_at_once["turns"][0]["template_selection"]
    copied.write_text(yaml.safe_dump(payload))

    with pytest.raises(ClarificationContinuationFixtureError, match="template_selection is required"):
        run_clarification_continuation_eval(copied)


def test_continuation_final_projection_fingerprint_is_an_executable_oracle(tmp_path: Path) -> None:
    copied = tmp_path / "cases.yaml"
    original_sha = next(
        scenario["final_projection_sha256"]
        for scenario in yaml.safe_load(DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES.read_text())["scenarios"]
        if scenario["id"] == "all_at_once"
    )
    copied.write_text(
        DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES.read_text().replace(
                original_sha,
                "f" * 64,
            1,
        )
    )

    artifact = run_clarification_continuation_eval(copied)

    assert artifact["summary"]["exact_gate"]["passed"] is False
    assert artifact["summary"]["failed"] == 1
    assert artifact["summary"]["prompt_coverage"] == {"runs": 46, "passed": 46, "rate": 1.0}
    all_at_once = next(record for record in artifact["records"] if record["scenario"] == "all_at_once")
    assert "final projection fingerprint" in all_at_once["checks"]["failures"][0]


def test_continuation_acceptance_oracle_compares_normalized_payload_and_correction(tmp_path: Path) -> None:
    copied = tmp_path / "cases.yaml"
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES.read_text())
    all_at_once = next(scenario for scenario in payload["scenarios"] if scenario["id"] == "all_at_once")
    accepted = all_at_once["turns"][0]["expect"]["accepted"]
    accepted[0]["payload"]["locations"][0]["value"] = "ZZZ"
    accepted[0]["is_correction"] = True
    copied.write_text(yaml.safe_dump(payload))

    artifact = run_clarification_continuation_eval(copied)

    first_record = next(record for record in artifact["records"] if record["scenario"] == "all_at_once")
    assert first_record["status"] == "failed"
    assert first_record["accepted_oracle"]["exact"] is False
    assert "is_correction" in first_record["checks"]["failures"][-1]
    assert artifact["summary"]["accepted_amendment_correctness"]["matched"] == 47
