from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreter,
)
from award_agent.cli.clarification_behavior_live_eval import _parser
from award_agent.evaluation.clarification_behavior_live import (
    DEFAULT_LIVE_BEHAVIOR_FIXTURES,
    ClarificationBehaviorLiveFixtureError,
    _load_cases,
    _string_leaves,
    _value_failures,
    run_live_clarification_behavior_eval,
)


class _FakeInterpreter:
    def __init__(self) -> None:
        self.calls = 0
        self._traces: list[dict[str, object]] = []

    def interpret(self, _input: object) -> ClarificationAnswerInterpretation:
        self.calls += 1
        self._traces.append(
            {
                "stage": "interpreter",
                "latency_seconds": 0.01,
                "error": None,
            }
        )
        return ClarificationAnswerInterpretation()

    def take_usage(self) -> dict[str, int]:
        return {"calls": self.calls, "captured_calls": self.calls, "missing_calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def take_call_traces(self) -> list[dict[str, object]]:
        traces, self._traces = self._traces, []
        return traces


class _FakeComposer:
    def __init__(self) -> None:
        self.calls = 0
        self._traces: list[dict[str, object]] = []

    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        self.calls += 1
        self._traces.append(
            {
                "stage": "composer",
                "latency_seconds": 0.01,
                "error": None,
            }
        )
        return ClarificationPromptComposition(
            question_items=tuple(
                ClarificationQuestionItem(
                    requirement_id=requirement.requirement_id,
                    issue_ids=tuple(
                        issue.issue_id for issue in input.issues if issue.requirement_id == requirement.requirement_id
                    ),
                    question="Could you clarify this detail?",
                )
                for requirement in input.requirements
            )
        )

    def take_usage(self) -> dict[str, int]:
        return {"calls": self.calls, "captured_calls": self.calls, "missing_calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def take_call_traces(self) -> list[dict[str, object]]:
        traces, self._traces = self._traces, []
        return traces


class _ErrorTraceInterpreter(_FakeInterpreter):
    def interpret(self, input: object) -> ClarificationAnswerInterpretation:
        result = super().interpret(input)
        self._traces[-1]["error"] = {"type": "Synthetic", "message": "simulated"}
        return result


class _MissingTraceInterpreter(_FakeInterpreter):
    def take_usage(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "captured_calls": 0,
            "missing_calls": self.calls,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def take_call_traces(self) -> list[dict[str, object]]:
        self._traces = []
        return []


def _failing_interpreter_factory(_model: str) -> ClarificationAnswerInterpreter:
    raise RuntimeError("synthetic constructor failure")


def test_live_behavior_fixture_preflight_has_required_public_coverage() -> None:
    cases, _ = _load_cases(DEFAULT_LIVE_BEHAVIOR_FIXTURES)

    assert len(cases) >= 16
    assert {str(case["family"]) for case in cases} >= {
        "accepting",
        "accepting_paraphrase",
        "paired_boundary",
        "partial_sibling",
        "targeted_composer",
        "correction",
        "no_progress",
        "conflict",
    }


def test_live_behavior_cli_keeps_stage_models_separate_and_defaults_to_luna() -> None:
    args = _parser().parse_args(["--output", "out.json"])

    assert args.interpreter_model == "gpt-5.6-luna"
    assert args.composer_model == "gpt-5.6-luna"
    assert args.trials == 3


def test_live_behavior_public_artifact_is_redacted_and_stage_separated(tmp_path: Path) -> None:
    artifact = run_live_clarification_behavior_eval(
        trials=1,
        trace_dir=tmp_path / "private-traces",
        interpreter_factory=lambda _model: _FakeInterpreter(),
        composer_factory=lambda _model: _FakeComposer(),
    )

    encoded = json.dumps(artifact)
    assert "Early next month" not in encoded
    assert "I want to leave" not in encoded
    assert artifact["fixture"]["redacted"] is True
    assert artifact["summary"]["instrumentation"]["stages"].keys() == {"interpreter", "composer"}
    assert artifact["llm_trace"]["sidecars"] == artifact["fixture"]["scenario_count"]
    assert len(list((tmp_path / "private-traces").rglob("*.json"))) == artifact["fixture"]["scenario_count"]
    assert artifact["summary"]["metadata"]["mode"] == "pilot"
    assert artifact["summary"]["metadata"]["pool"] == "public"
    assert artifact["summary"]["metadata"]["execution"] == "live_openai"
    assert set(artifact["summary"]["metadata"]["slice_metrics"]) >= {"class:conflict", "family:conflict"}
    assert set(artifact["summary"]["behavioral"]) >= {
        "false_blocking",
        "incorrect_acceptance",
        "targeted_question",
        "valid_sibling_retention",
        "property_envelopes",
        "assumption_disclosure",
        "materially_incorrect_assumption",
        "unnecessary_clarification",
        "generic_repeat_rate",
        "turns_to_ready",
        "paired_accept_ask",
        "paraphrase_consistency",
    }
    assert set(artifact["summary"]["instrumentation"]["totals"]) >= {
        "calls",
        "captured_calls",
        "missing_calls",
        "trace_count",
        "reconciled_sessions",
        "unreconciled_sessions",
    }
    assert set(artifact["records"][0]) >= {
        "final_status",
        "stop_reason",
        "safety_passed",
        "behavioral_passed",
        "property_failures",
        "value_failures",
        "turn_metrics",
        "targeted_questions",
        "question_composition",
        "valid_siblings",
        "stages",
    }

    recorded_disclosure_turns = sum(
        bool(turn["disclosure_required"])
        for record in artifact["records"]
        for turn in record["turn_metrics"]
    )
    assert artifact["summary"]["behavioral"]["assumption_disclosure"]["required"] == recorded_disclosure_turns
    assert set(artifact["summary"]["metadata"]["errors"]) == {"model", "system", "evaluator"}


def test_live_behavior_fixture_rejects_private_marker_and_too_few_cases(tmp_path: Path) -> None:
    private = tmp_path / "private.yaml"
    private.write_text(DEFAULT_LIVE_BEHAVIOR_FIXTURES.read_text() + "\napi_key: forbidden\n")
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="privacy"):
        _load_cases(private)

    short = tmp_path / "short.yaml"
    payload = DEFAULT_LIVE_BEHAVIOR_FIXTURES.read_text().replace("  - id:", "  - id:", 1)
    lines = payload.splitlines()
    # Retain only the first scenario so fixture cardinality is rejected before
    # any call factory could be used.
    cut = next(index for index, line in enumerate(lines[1:], start=1) if line.startswith("  - id:"))
    short.write_text("\n".join(lines[:cut]) + "\n")
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="at least 16"):
        _load_cases(short)

    malformed_envelope = tmp_path / "malformed-envelope.yaml"
    malformed_envelope.write_text(
        DEFAULT_LIVE_BEHAVIOR_FIXTURES.read_text().replace("start_day: [1, 3]", "start_day: [1]", 1)
    )
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="departure_window"):
        _load_cases(malformed_envelope)

    missing_conflict = tmp_path / "missing-conflict.yaml"
    missing_conflict.write_text(
        DEFAULT_LIVE_BEHAVIOR_FIXTURES.read_text().replace("family: conflict", "family: another-family", 1)
    )
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="required scenario families"):
        _load_cases(missing_conflict)

    invalid_iso = tmp_path / "invalid-iso.yaml"
    invalid_iso.write_text(
        DEFAULT_LIVE_BEHAVIOR_FIXTURES.read_text().replace(
            '{departure: "2026-10-06"', '{departure: "10/06/2026"', 1
        )
    )
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="ISO date"):
        _load_cases(invalid_iso)

    invalid_sibling = tmp_path / "invalid-sibling.yaml"
    invalid_sibling.write_text(
        DEFAULT_LIVE_BEHAVIOR_FIXTURES.read_text().replace(
            "valid_siblings: [origin, return_or_duration, travelers]",
            "valid_siblings: [origin, departure]",
            1,
        )
    )
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="valid_siblings"):
        _load_cases(invalid_sibling)

    unknown_requirement = tmp_path / "unknown-requirement.yaml"
    unknown_requirement.write_text(
        DEFAULT_LIVE_BEHAVIOR_FIXTURES.read_text().replace(
            "initial_unknowns: [origin, departure, return_or_duration, travelers]",
            "initial_unknowns: [origin, departure, return_or_duration, unknown_field]",
            1,
        )
    )
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="initial_unknowns"):
        _load_cases(unknown_requirement)


def test_live_behavior_trace_error_is_an_exact_safety_failure(tmp_path: Path) -> None:
    artifact = run_live_clarification_behavior_eval(
        trials=1,
        trace_dir=tmp_path / "private-traces",
        interpreter_factory=lambda _model: _ErrorTraceInterpreter(),
        composer_factory=lambda _model: _FakeComposer(),
    )

    assert artifact["summary"]["exact_safety_gate"]["passed"] is False
    assert any(
        "model trace reconciliation failed" in record["safety_failures"]
        for record in artifact["records"]
    )


def test_live_behavior_missing_trace_is_an_exact_safety_failure(tmp_path: Path) -> None:
    artifact = run_live_clarification_behavior_eval(
        trials=1,
        trace_dir=tmp_path / "private-traces",
        interpreter_factory=lambda _model: _MissingTraceInterpreter(),
        composer_factory=lambda _model: _FakeComposer(),
    )

    assert artifact["summary"]["exact_safety_gate"]["passed"] is False
    assert any(
        not record["stages"]["interpreter"]["reconciled"]
        for record in artifact["records"]
    )


def test_live_behavior_constructor_failure_is_a_complete_private_record(tmp_path: Path) -> None:
    artifact = run_live_clarification_behavior_eval(
        trials=1,
        trace_dir=tmp_path / "private-traces",
        interpreter_factory=_failing_interpreter_factory,
        composer_factory=lambda _model: _FakeComposer(),
    )

    assert artifact["summary"]["exact_safety_gate"]["passed"] is False
    assert all(record["final_status"] == "construction_failed" for record in artifact["records"])
    assert all("system error: RuntimeError" in record["safety_failures"] for record in artifact["records"])
    assert len(list((tmp_path / "private-traces").rglob("*.json"))) == artifact["fixture"]["scenario_count"]


def test_live_behavior_qualification_mode_keeps_pair_trials_and_trace_totals(tmp_path: Path) -> None:
    artifact = run_live_clarification_behavior_eval(
        trials=2,
        trace_dir=tmp_path / "private-traces",
        interpreter_factory=lambda _model: _FakeInterpreter(),
        composer_factory=lambda _model: _FakeComposer(),
    )

    assert artifact["summary"]["metadata"]["mode"] == "qualification"
    assert artifact["summary"]["behavioral"]["paired_accept_ask"]["trial_runs"] == 4
    assert artifact["llm_trace"]["sidecars"] == 2 * artifact["fixture"]["scenario_count"]
    for stage in artifact["summary"]["instrumentation"]["stages"].values():
        assert set(stage) >= {
            "calls",
            "captured_calls",
            "missing_calls",
            "trace_count",
            "reconciled_sessions",
            "unreconciled_sessions",
            "errors",
        }


def test_live_behavior_value_oracle_checks_each_exact_field() -> None:
    session = SimpleNamespace(
        effective_request=SimpleNamespace(
            origins=[SimpleNamespace(value="SFO")],
            destinations=[SimpleNamespace(value="France")],
            travelers=2,
            departure_window=SimpleNamespace(start=date(2026, 10, 6), end=date(2026, 10, 6)),
            return_window=SimpleNamespace(start=date(2026, 10, 16), end=date(2026, 10, 16)),
        )
    )
    expected = {
        "origin": "SFO",
        "destination": "France",
        "travelers": 2,
        "departure": "2026-10-06",
        "return": "2026-10-16",
    }

    assert _value_failures(session, expected) == []
    assert _value_failures(session, {**expected, "origin": "LAX"}) == ["exact value mismatch: origin"]
    assert _value_failures(session, {**expected, "destination": "Spain"}) == ["exact value mismatch: destination"]
    assert _value_failures(session, {**expected, "travelers": 1}) == ["exact value mismatch: travelers"]
    assert _value_failures(session, {**expected, "departure": "2026-10-07"}) == ["exact value mismatch: departure"]
    assert _value_failures(session, {**expected, "return": "2026-10-17"}) == ["exact value mismatch: return"]


def test_live_behavior_private_holdout_has_aggregate_only_and_no_dynamic_leakage(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout"
    holdout.mkdir()
    fixture = holdout / "cases.yaml"
    fixture.write_text(DEFAULT_LIVE_BEHAVIOR_FIXTURES.read_text())
    cases, _ = _load_cases(fixture)

    artifact = run_live_clarification_behavior_eval(
        trials=1,
        fixture_path=fixture,
        trace_dir=tmp_path / "private-traces",
        interpreter_factory=lambda _model: _FakeInterpreter(),
        composer_factory=lambda _model: _FakeComposer(),
    )

    public_strings = _string_leaves(artifact)
    assert artifact["fixture"]["private_holdout"] is True
    assert artifact["summary"]["metadata"]["pool"] == "private_holdout"
    assert "records" not in artifact
    assert str(fixture) not in public_strings
    assert all(str(case["id"]) not in public_strings for case in cases)
    assert all(str(turn["text"]) not in public_strings for case in cases for turn in case["turns"])
