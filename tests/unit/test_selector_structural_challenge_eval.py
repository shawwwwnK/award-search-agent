from __future__ import annotations

import json
from pathlib import Path

import pytest

from award_agent.cli import selector_structural_challenge_eval as challenge_cli
from award_agent.evaluation.selector_challenge_cases import (
    challenge_surface_registry,
    selector_oracle_candidates,
)
from award_agent.evaluation.selector_structural_challenge_eval import (
    SelectorChallengePricing,
    artifact_privacy_violations,
    payload_sufficiency_audit,
    run_selector_structural_challenge_eval,
)
from award_agent.intent.model_views import TemporalSelectorInput, TemporalSelectorOutput
from award_agent.intent.temporal_selector import plan_temporal_selection


class OracleSelector:
    """Offline fake that finds a challenge surface only through restoration handles."""

    def __init__(self) -> None:
        self.calls: list[TemporalSelectorInput] = []
        self.reset_calls = 0

    def reset_capture(self) -> None:
        self.reset_calls += 1

    def take_usage(self) -> dict[str, int]:
        return {
            "calls": 1,
            "captured_calls": 1,
            "missing_calls": 0,
            "input_tokens": 10,
            "cached_input_tokens": 2,
            "output_tokens": 3,
            "total_tokens": 13,
        }

    def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
        self.calls.append(model_input)
        selected_private = set(model_input._candidate_handles.values())
        surface = next(
            surface
            for surface in challenge_surface_registry().values()
            if selected_private
            == {
                candidate.handle
                for candidate in surface.catalog.candidates
                if candidate.exclusive_group in plan_temporal_selection(surface.catalog).selector_groups
            }
        )
        oracle = set(selector_oracle_candidates(surface))
        return TemporalSelectorOutput(
            selected_candidates=[
                public
                for public, private in model_input._candidate_handles.items()
                if private in oracle
            ]
        )


def _pricing() -> SelectorChallengePricing:
    return SelectorChallengePricing(
        input_usd_per_million=2.0,
        cached_input_usd_per_million=0.2,
        output_usd_per_million=12.0,
        snapshot="test-pricing-2026-09-04",
    )


def test_structural_challenge_runner_has_exact_28_case_redacted_gate() -> None:
    selector = OracleSelector()
    artifact = run_selector_structural_challenge_eval(
        selector_model="test-model",
        trials=2,
        selector_factory=lambda _model: selector,
        pricing=_pricing(),
    )

    assert artifact["evaluation"] == "selector_structural_challenge"
    assert artifact["scope"] == "structural_safety_screen_not_a_generalization_claim"
    assert artifact["fixture"]["scenario_count"] == 28
    assert artifact["fixture"]["surface_count"] == 14
    assert artifact["fixture"]["topology_count"] == 7
    assert len(artifact["results"]) == 56
    assert len(selector.calls) == 56
    assert selector.reset_calls == 56
    assert artifact["summary"]["overall"]["semantic_accuracy"] == {
        "runs": 56,
        "passed": 56,
        "rate": 1.0,
    }
    assert artifact["summary"]["pair_equivalence"] == {"pairs": 28, "passed": 28, "rate": 1.0}
    assert artifact["summary"]["stability"] == {"variants": 28, "passed": 28, "rate": 1.0}
    assert artifact["summary"]["exact_gate"]["passed"] is True
    assert artifact["privacy"] == {"checked": True, "violations": []}
    assert set(artifact["summary"]["by_dimension"]) == {
        "topology",
        "subtype_id",
        "surface_id",
        "order_variant",
    }
    assert len(artifact["summary"]["by_dimension"]["topology"]) == 7
    assert len(artifact["summary"]["by_dimension"]["surface_id"]) == 14
    assert artifact["summary"]["by_dimension"]["order_variant"]["canonical"]["runs"] == 28
    assert artifact["summary"]["overall"]["latency_seconds"]["quantile_method"] == "nearest_rank"
    assert set(artifact["summary"]["overall"]["latency_seconds"]) >= {
        "p50", "p95", "p99", "max"
    }
    assert artifact["summary"]["overall"]["cost"]["status"] == "calculated"
    assert artifact["summary"]["overall"]["cost"]["input_tokens_billed_non_cached"] == 448
    assert artifact["summary"]["overall"]["cost"]["cached_input_tokens_billed"] == 112
    assert "confidence_interval" not in json.dumps(artifact).casefold()
    serialized = json.dumps(artifact)
    assert "manual:" not in serialized
    assert "slot:" not in serialized


def test_structural_challenge_rejects_bad_membership_without_private_error_text() -> None:
    class BadSelector:
        def select_candidates(self, _model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
            return TemporalSelectorOutput(selected_candidates=["not-a-public-handle"])

    artifact = run_selector_structural_challenge_eval(
        selector_model="test-model",
        selector_factory=lambda _model: BadSelector(),
    )

    assert artifact["summary"]["overall"]["membership"] == {
        "runs": 28,
        "passed": 0,
        "rate": 0.0,
    }
    assert artifact["summary"]["exact_gate"]["passed"] is False
    assert {record["error_code"] for record in artifact["results"]} == {
        "selector_selection_validation_failed"
    }
    assert artifact["privacy"]["violations"] == []


def test_payload_audit_is_oracle_free_and_privacy_scanner_is_testable() -> None:
    audit = payload_sufficiency_audit()

    assert audit["oracle_free"] is True
    assert audit["status"] == "manual_checklist_recorded"
    assert audit["manual_checklist"]
    assert artifact_privacy_violations(
        {"results": [{"selected_candidates": ["c0"]}], "summary": {}}
    ) == ()
    assert artifact_privacy_violations(
        {"results": [{"request": "hidden", "detail": "manual:secret"}]}
    )


def test_structural_challenge_cli_returns_nonzero_on_exact_gate_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact = {
        "summary": {"exact_gate": {"passed": False}},
    }
    monkeypatch.setattr(challenge_cli, "run_selector_structural_challenge_eval", lambda **_kwargs: artifact)
    output = tmp_path / "challenge.json"

    assert challenge_cli.main([
        "--selector-model", "test-model",
        "--pricing-snapshot", "test-pricing",
        "--input-usd-per-million", "2",
        "--output-usd-per-million", "12",
        "--output", str(output),
    ]) == 1
    assert json.loads(output.read_text()) == artifact
