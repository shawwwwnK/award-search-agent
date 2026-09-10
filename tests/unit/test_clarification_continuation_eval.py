"""ADR 0014 replacement for the retired raw-semantics continuation evaluator."""

from pathlib import Path

import pytest
import yaml

from award_agent.evaluation.clarification_semantic_guardrails import (
    DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES,
    ClarificationSemanticGuardrailError,
    preflight_clarification_semantic_guardrail_cases,
    run_offline_clarification_semantic_guardrails,
)


def test_typed_semantic_guardrail_fixture_and_hard_gate() -> None:
    cases = preflight_clarification_semantic_guardrail_cases()
    artifact = run_offline_clarification_semantic_guardrails()

    assert len(cases) >= 8
    assert artifact["fixture"] == {
        "corpus": "disclosed_development",
        "case_count": len(cases),
        "redacted": True,
    }
    assert artifact["passed"] is True


def test_typed_semantic_fixture_requires_every_safety_family(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES.read_text())
    payload["cases"] = [
        item for item in payload["cases"] if item["family"] != "accepting_provenance"
    ]
    copied = tmp_path / "semantic-guardrails.yaml"
    copied.write_text(yaml.safe_dump(payload))

    with pytest.raises(ClarificationSemanticGuardrailError, match="miss or add required safety families"):
        preflight_clarification_semantic_guardrail_cases(copied)


def test_typed_semantic_fixture_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES.read_text())
    payload["cases"].append(payload["cases"][0])
    copied = tmp_path / "semantic-guardrails.yaml"
    copied.write_text(yaml.safe_dump(payload))

    with pytest.raises(ClarificationSemanticGuardrailError, match="IDs must be unique"):
        preflight_clarification_semantic_guardrail_cases(copied)


def test_typed_semantic_fixture_must_remain_development_only_and_acknowledge_holdout(
    tmp_path: Path,
) -> None:
    payload = yaml.safe_load(DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES.read_text())
    payload["owner_held_holdout"] = {"status": "available"}
    copied = tmp_path / "semantic-guardrails.yaml"
    copied.write_text(yaml.safe_dump(payload))

    with pytest.raises(ClarificationSemanticGuardrailError, match="inaccessible owner-held holdout"):
        preflight_clarification_semantic_guardrail_cases(copied)
