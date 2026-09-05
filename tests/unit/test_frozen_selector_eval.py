from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from award_agent.cli import frozen_selector_eval as frozen_selector_eval_cli
from award_agent.cli.frozen_selector_eval import _parser
from award_agent.evaluation.frozen_selector_cases import frozen_selector_case_registry
from award_agent.evaluation.frozen_selector_eval import (
    DEFAULT_FROZEN_SELECTOR_FIXTURES,
    LEGACY_FROZEN_SELECTOR_FIXTURES,
    FrozenSelectorFixtureError,
    preflight_frozen_selector_cases,
    run_frozen_selector_eval,
)
from award_agent.intent.model_views import TemporalSelectorInput, TemporalSelectorOutput
from award_agent.intent.temporal_selector import plan_temporal_selection


class OracleSelector:
    """Test-only selector that uses the private oracle without invoking any model client."""

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
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
        }

    def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
        self.calls.append(model_input)
        registry = frozen_selector_case_registry()
        candidate_values = set(model_input._candidate_handles.values())
        case = next(
            item
            for item in registry.values()
            if candidate_values
            == {
                candidate.handle
                for candidate in item.catalog.candidates
                if candidate.exclusive_group in plan_temporal_selection(item.catalog).selector_groups
            }
        )
        oracle = set(case.oracle_candidates)
        return TemporalSelectorOutput(
            selected_candidates=[
                public
                for public, private in model_input._candidate_handles.items()
                if private in oracle
            ]
        )


def test_preflight_rebuilds_exact_public_projections_and_discriminator_pairs() -> None:
    prepared = preflight_frozen_selector_cases()

    assert len(prepared) == 12
    assert {item.contract_version for item in prepared} == {"v2"}
    assert {item.fixture.category for item in prepared} == {
        "target",
        "reference",
        "composition",
        "scope",
        "dependency_closure",
        "unsupported",
    }
    assert {item.fixture.pair for item in prepared} == {
        "target",
        "reference",
        "composition",
        "scope",
        "dependency",
        "unsupported",
    }


def test_legacy_v1_fixture_is_preserved_but_v2_is_the_default() -> None:
    legacy = preflight_frozen_selector_cases(LEGACY_FROZEN_SELECTOR_FIXTURES)

    assert len(legacy) == 12
    assert {item.contract_version for item in legacy} == {"v1"}
    assert DEFAULT_FROZEN_SELECTOR_FIXTURES.name == "frozen_cases_v2.yaml"


def test_v2_preflight_rejects_target_choices_without_a_local_explicit_cue(tmp_path: Path) -> None:
    copied = tmp_path / "frozen_cases_v2.yaml"
    payload = yaml.safe_load(DEFAULT_FROZEN_SELECTOR_FIXTURES.read_text())
    target = next(item for item in payload["scenarios"] if item["id"] == "target-forward")
    target["public_input"]["ordered_evidence"][0]["endpoint_cue"] = "unspecified"
    copied.write_text(yaml.safe_dump(payload, sort_keys=False))

    with pytest.raises(FrozenSelectorFixtureError, match="public projection drifted"):
        preflight_frozen_selector_cases(copied)


def test_preflight_rejects_checked_in_public_projection_drift(tmp_path: Path) -> None:
    copied = tmp_path / "frozen_cases.yaml"
    copied.write_text(
        DEFAULT_FROZEN_SELECTOR_FIXTURES.read_text().replace("October 5", "October 6", 1)
    )

    with pytest.raises(FrozenSelectorFixtureError, match="public projection drifted"):
        preflight_frozen_selector_cases(copied)


def test_frozen_selector_runner_uses_only_selector_arms_and_offline_holidays() -> None:
    selectors: dict[str, OracleSelector] = {}

    def factory(model: str) -> OracleSelector:
        selector = OracleSelector()
        selectors[model] = selector
        return selector

    artifact = run_frozen_selector_eval(
        mini_model="explicit-mini-id",
        luna_model="explicit-luna-id",
        trials=2,
        selector_factory=factory,
    )

    assert artifact["evaluation"] == "frozen_temporal_selector_only"
    assert artifact["schema_version"] == 2
    assert artifact["fixture"]["contract_version"] == "v2"
    assert artifact["fixture"]["path"] == str(DEFAULT_FROZEN_SELECTOR_FIXTURES)
    assert len(artifact["fixture"]["sha256"]) == 64
    assert artifact["scenario_count"] == 12
    assert artifact["arms"]["none"] == {"model": None, "selector_calls": 0}
    assert artifact["arms"]["mini"]["model"] == "explicit-mini-id"
    assert artifact["arms"]["luna"]["model"] == "explicit-luna-id"
    assert artifact["summary"]["arms"]["mini"]["semantic_accuracy"] == {
        "runs": 24,
        "passed": 24,
        "rate": 1.0,
    }
    assert artifact["summary"]["arms"]["luna"]["unsupported_to_unresolved_accuracy"] == {
        "runs": 4,
        "passed": 4,
        "rate": 1.0,
    }
    assert artifact["summary"]["arms"]["none"]["parse"] == {
        "runs": 0,
        "passed": 0,
        "rate": 0.0,
    }
    assert artifact["summary"]["repairs"] == {"attempts": 0, "zero_repairs": True}
    assert len(selectors["explicit-mini-id"].calls) == 24
    assert len(selectors["explicit-luna-id"].calls) == 24
    assert all(record["repairs"] == 0 for record in artifact["results"])
    gate = artifact["summary"]["quality_gate"]["arms"]
    assert gate["none"] == {
        "eligible": False,
        "passed": None,
        "reason": "no_selector_control_is_not_gate_eligible",
        "checks": {},
    }
    assert gate["mini"]["eligible"] is True
    assert gate["mini"]["passed"] is True
    assert gate["luna"]["passed"] is True


def test_frozen_selector_runner_keeps_bad_selector_output_as_explicit_error() -> None:
    class BadSelector:
        def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
            return TemporalSelectorOutput(selected_candidates=["unknown"])

    artifact = run_frozen_selector_eval(
        mini_model="explicit-mini-id",
        luna_model="explicit-luna-id",
        selector_factory=lambda _model: BadSelector(),
    )

    mini = artifact["summary"]["arms"]["mini"]
    assert mini["errors"] == 12
    assert mini["membership"] == {"runs": 12, "passed": 0, "rate": 0.0}
    assert mini["semantic_accuracy"] == {"runs": 12, "passed": 0, "rate": 0.0}
    assert mini["per_class_accuracy"] == {
        category: {"runs": 2, "passed": 0, "rate": 0.0}
        for category in (
            "composition",
            "dependency_closure",
            "reference",
            "scope",
            "target",
            "unsupported",
        )
    }
    assert mini["unsupported_to_unresolved_accuracy"] == {
        "runs": 2,
        "passed": 0,
        "rate": 0.0,
    }
    assert all(
        result["error_stage"] == "selection_validation"
        and result["error_code"] == "selector_selection_validation_failed"
        for result in artifact["results"]
        if result["arm"] == "mini"
    )
    assert artifact["summary"]["quality_gate"]["arms"]["mini"]["passed"] is False


def test_selector_failure_is_a_parse_failure_and_artifact_never_keeps_private_error_text() -> None:
    class FailingSelector:
        def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
            raise RuntimeError("private candidate manual:target:departure requires slot:private")

    artifact = run_frozen_selector_eval(
        mini_model="explicit-mini-id",
        luna_model="explicit-luna-id",
        selector_factory=lambda _model: FailingSelector(),
    )

    mini = artifact["summary"]["arms"]["mini"]
    assert mini["parse"] == {"runs": 12, "passed": 0, "rate": 0.0}
    assert mini["usage"]["selector_call_attempts"] == 12
    assert mini["usage"]["sdk_usage_captured_attempts"] == 0
    assert mini["usage"]["sdk_usage_missing_attempts"] == 12
    assert all(
        result["error_stage"] == "selector"
        and result["error_code"] == "selector_call_failed"
        and result["parse_valid"] is False
        for result in artifact["results"]
        if result["arm"] == "mini"
    )
    serialized = json.dumps(artifact)
    assert "manual:" not in serialized
    assert "slot:private" not in serialized


def test_invalid_selector_schema_is_parse_failure_not_call_failure() -> None:
    class InvalidSchemaSelector:
        def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
            return {"selected_candidates": "c0"}  # type: ignore[return-value]

    artifact = run_frozen_selector_eval(
        mini_model="explicit-mini-id",
        luna_model="explicit-luna-id",
        selector_factory=lambda _model: InvalidSchemaSelector(),
    )

    mini_records = [result for result in artifact["results"] if result["arm"] == "mini"]
    assert all(result["parse_valid"] is False for result in mini_records)
    assert {result["error_code"] for result in mini_records} == {"selector_parse_failed"}


def test_frozen_selector_cli_returns_nonzero_when_quality_gate_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class WrongButSchemaValidSelector:
        def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
            return TemporalSelectorOutput(
                selected_candidates=[
                    next(
                        candidate.handle
                        for candidate in group.candidates
                        if candidate.interpretation_kind == "unresolved"
                    )
                    for group in model_input.candidate_groups
                ]
            )

    artifact = run_frozen_selector_eval(
        mini_model="explicit-mini-id",
        luna_model="explicit-luna-id",
        selector_factory=lambda _model: WrongButSchemaValidSelector(),
    )
    assert artifact["summary"]["arms"]["mini"]["errors"] == 0
    assert artifact["summary"]["quality_gate"]["arms"]["mini"]["passed"] is False
    monkeypatch.setattr(frozen_selector_eval_cli, "run_frozen_selector_eval", lambda **_kwargs: artifact)
    output = tmp_path / "selector-study.json"

    assert (
        frozen_selector_eval_cli.main(
            [
                "--mini-model",
                "mini-id",
                "--luna-model",
                "luna-id",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert json.loads(output.read_text())["summary"]["quality_gate"]["arms"]["mini"]["passed"] is False


def test_frozen_selector_cli_requires_explicit_model_ids_and_output() -> None:
    parser = _parser()
    args = parser.parse_args(
        [
            "--mini-model",
            "mini-id",
            "--luna-model",
            "luna-id",
            "--output",
            "artifact.json",
        ]
    )

    assert args.mini_model == "mini-id"
    assert args.luna_model == "luna-id"
    assert args.output == Path("artifact.json")
