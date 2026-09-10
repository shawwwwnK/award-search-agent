from pathlib import Path

import pytest
import yaml

from award_agent.evaluation.clarification_behavior import (
    DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES,
    ClarificationBehaviorFixtureError,
    preflight_clarification_behavior_cases,
    run_clarification_behavior_eval,
)


def test_behavioral_v2_executes_property_oracles_and_reports_metrics() -> None:
    cases = preflight_clarification_behavior_cases()
    assert {case.payload["answer_class"] for case in cases} == {
        "reasonably_resolvable", "safely_assumable", "ambiguous", "conflict", "nonanswer", "correction"
    }
    artifact = run_clarification_behavior_eval()
    assert artifact["fixture"]["path"] == str(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES)
    assert artifact["summary"]["exact_safety_gate"]["passed"] is True
    behavioral = artifact["summary"]["behavioral"]
    assert behavioral["false_blocking"] == {"count": 0, "denominator": 5, "rate": 0.0}
    assert behavioral["incorrect_acceptance"] == {"count": 0, "denominator": 3, "rate": 0.0}
    assert behavioral["assumption_disclosure"] == {"required": 6, "missing": 0}
    assert behavioral["valid_sibling_retention"] == {"retained": 3, "expected": 3, "scenarios": 1}
    assert behavioral["targeted_question"] == {"required": 3, "targeted": 3, "generic_repeats": 0}
    assert behavioral["paraphrase_consistency"]["passed"] is True
    assert behavioral["paired_accept_ask"]["passed"] is True
    metadata = artifact["summary"]["metadata"]
    assert metadata["evaluator_version"] == "clarification_behavior_eval_v2.1"
    assert metadata["pool"] == "development"
    assert metadata["variance"] == {"kind": "deterministic_single_run", "value": 0.0}
    assert metadata["semantic_family_distribution"] == metadata["scenario_distribution"]
    assert set(metadata["semantic_family_slice_metrics"]) == set(metadata["semantic_family_distribution"])


def test_behavioral_v2_rejects_missing_answer_class_coverage(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    payload["scenarios"] = [item for item in payload["scenarios"] if item["answer_class"] != "conflict"]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    with pytest.raises(ClarificationBehaviorFixtureError, match="every answer class"):
        preflight_clarification_behavior_cases(copied)


def test_behavioral_v2_protected_field_violation_fails_exact_gate(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "reported_early_next_month_week")
    scenario["turns"][0]["oracle"]["protected_fields"].append("origin")
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    assert artifact["summary"]["exact_safety_gate"]["passed"] is False
    record = next(item for item in artifact["records"] if item["scenario"] == "reported_early_next_month_week")
    assert "protected fields changed" in record["safety_failures"][0]


def test_behavioral_property_failure_is_reported_without_redefining_exact_safety(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "reported_early_next_month_week")
    scenario["turns"][0]["oracle"]["properties"]["departure_window"]["end_day"] = [1, 2]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    assert artifact["summary"]["exact_safety_gate"]["passed"] is True
    record = next(item for item in artifact["records"] if item["scenario"] == "reported_early_next_month_week")
    assert record["property_failures"] == ["departure window is outside the acceptable bounded envelope"]


def test_behavioral_action_oracle_is_executable(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "ordinary_week_duration")
    scenario["turns"][0]["oracle"]["permitted_statuses"] = ["awaiting_answer"]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    record = next(item for item in artifact["records"] if item["scenario"] == "ordinary_week_duration")
    assert "status 'ready' is not permitted" in record["behavioral_failures"]


def test_behavioral_semantic_action_facet_is_independent_of_status(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "correction_replaces_assumption")
    scenario["turns"][0]["oracle"]["permitted_semantic_actions"] = ["awaiting_answer"]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    record = next(item for item in artifact["records"] if item["scenario"] == "correction_replaces_assumption")
    assert record["status_permitted"] is True
    assert record["semantic_action_permitted"] is False
    assert "action 'correction_applied' is not permitted" in record["behavioral_failures"]


def test_behavioral_false_block_metric_is_sensitive_to_missing_reasonable_interpretation(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "ordinary_week_duration")
    scenario["turns"][0].pop("approximations")
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    assert artifact["summary"]["behavioral"]["false_blocking"]["count"] == 1


def test_behavioral_incorrect_acceptance_metric_uses_oracle_required_blocker(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "discrete_month_alternative")
    scenario["turns"][0]["oracle"]["must_remain_blocked"] = ["return_or_duration"]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    assert artifact["summary"]["exact_safety_gate"]["passed"] is False
    assert artifact["summary"]["behavioral"]["incorrect_acceptance"]["count"] == 1


def test_behavioral_unnecessary_clarification_metric_needs_oracle_complete_resolution(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "ordinary_week_duration")
    scenario["initial_unknowns"].append("departure")
    scenario["turns"][0]["oracle"]["permitted_statuses"].append("awaiting_answer")
    scenario["turns"][0]["oracle"]["permitted_semantic_actions"].append("awaiting_answer")
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    assert artifact["summary"]["behavioral"]["unnecessary_clarification"]["count"] == 1


def test_behavioral_valid_sibling_metric_is_sensitive_to_lost_answer_sibling(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "mixed_valid_siblings_with_ambiguous_date")
    scenario["turns"][0]["amendments"] = scenario["turns"][0]["amendments"][:1]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    sibling = artifact["summary"]["behavioral"]["valid_sibling_retention"]
    assert sibling["retained"] < sibling["expected"]


def test_behavioral_duration_envelope_contains_acceptable_exact_duration(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "ordinary_week_duration")
    scenario["turns"][0]["oracle"]["properties"]["duration_days"] = [6, 8]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    record = next(item for item in artifact["records"] if item["scenario"] == "ordinary_week_duration")
    assert record["property_failures"] == []


def test_behavioral_disclosure_and_material_assumption_metrics_are_sensitive(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    nonanswer = next(item for item in payload["scenarios"] if item["id"] == "nonanswer_preserves_state")
    nonanswer["turns"][0]["oracle"]["disclosure_required"] = True
    assumption = next(item for item in payload["scenarios"] if item["id"] == "reported_early_next_month_week")
    assumption["turns"][0]["oracle"]["properties"]["departure_window"]["end_day"] = [1, 2]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    behavioral = artifact["summary"]["behavioral"]
    assert behavioral["assumption_disclosure"]["missing"] == 1
    assert behavioral["materially_incorrect_assumption"]["count"] == 1


def test_behavioral_targeted_and_generic_repeat_metrics_are_sensitive(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    scenario = next(item for item in payload["scenarios"] if item["id"] == "discrete_month_alternative")
    scenario["force_generic_followup"] = True
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    record = next(item for item in artifact["records"] if item["scenario"] == "discrete_month_alternative")
    assert record["targeted_question"] is False
    assert "generic repeat" in record["behavioral_failures"]
    assert artifact["summary"]["behavioral"]["generic_repeat_rate"] > 0


def test_behavioral_paraphrase_and_pair_checks_are_sensitive(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    paraphrase = next(item for item in payload["scenarios"] if item["id"] == "early_october_paraphrase")
    paraphrase["turns"][0]["approximations"][0]["handle"] = "a2"
    ask = next(item for item in payload["scenarios"] if item["id"] == "discrete_month_alternative")
    ask["force_generic_followup"] = True
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    artifact = run_clarification_behavior_eval(copied)
    assert artifact["summary"]["behavioral"]["paraphrase_consistency"]["passed"] is False
    assert artifact["summary"]["behavioral"]["paired_accept_ask"]["passed"] is False


def test_behavioral_fixture_rejects_invalid_pair_and_unknown_property(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    payload["scenarios"] = [item for item in payload["scenarios"] if item["id"] != "discrete_month_alternative"]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    with pytest.raises(ClarificationBehaviorFixtureError, match="pair_id"):
        preflight_clarification_behavior_cases(copied)
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    payload["scenarios"][0]["turns"][0]["oracle"]["properties"]["invented"] = True
    copied.write_text(yaml.safe_dump(payload))
    with pytest.raises(ClarificationBehaviorFixtureError, match="unknown property"):
        preflight_clarification_behavior_cases(copied)


def test_behavioral_fixture_strictly_validates_unknowns_envelopes_and_siblings(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    payload["scenarios"][0]["initial_unknowns"] = ["cabin"]
    copied = tmp_path / "cases.yaml"
    copied.write_text(yaml.safe_dump(payload))
    with pytest.raises(ClarificationBehaviorFixtureError, match="initial_unknowns"):
        preflight_clarification_behavior_cases(copied)
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    mixed = next(item for item in payload["scenarios"] if item["id"] == "mixed_valid_siblings_with_ambiguous_date")
    mixed["turns"][0]["oracle"]["valid_siblings"].append("departure")
    copied.write_text(yaml.safe_dump(payload))
    with pytest.raises(ClarificationBehaviorFixtureError, match="must_resolve"):
        preflight_clarification_behavior_cases(copied)


def test_private_holdout_artifact_is_aggregate_only(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout"
    holdout.mkdir()
    copied = holdout / "private_cases.yaml"
    copied.write_text(DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES.read_text())
    artifact = run_clarification_behavior_eval(copied)
    assert "records" not in artifact
    assert "path" not in artifact["fixture"]
    assert artifact["fixture"]["private_holdout"] is True


def test_behavioral_v2_has_no_v1_evaluator_dependency() -> None:
    source = Path("src/award_agent/evaluation/clarification_behavior.py").read_text()
    assert "clarification_continuation" not in source
