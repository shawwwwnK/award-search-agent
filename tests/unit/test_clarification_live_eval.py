from pathlib import Path

import pytest

from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.clarification.interpreter import ClarificationAnswerInterpretation
from award_agent.evaluation.clarification_live import (
    DEFAULT_LIVE_CLARIFICATION_FIXTURES,
    ClarificationLiveFixtureError,
    _load_cases,
    _required_terminal_correct,
    run_live_clarification_eval,
)


class _UsageLessInterpreter:
    def __init__(self) -> None:
        self.calls = 0
        self._traces: list[dict[str, object]] = []

    def interpret(self, _input: object) -> ClarificationAnswerInterpretation:
        self.calls += 1
        self._traces.append({"stage": "interpreter", "latency_seconds": 0.01, "error": None})
        return ClarificationAnswerInterpretation()

    def take_usage(self) -> dict[str, int] | None:
        calls, self.calls = self.calls, 0
        if not calls:
            return None
        return {
            "calls": calls,
            "captured_calls": 0,
            "missing_calls": calls,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def take_call_traces(self) -> list[dict[str, object]]:
        traces, self._traces = self._traces, []
        return traces


class _UsageLessComposer:
    def __init__(self) -> None:
        self.calls = 0
        self._traces: list[dict[str, object]] = []

    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        self.calls += 1
        self._traces.append({"stage": "composer", "latency_seconds": 0.01, "error": None})
        return ClarificationPromptComposition(
            question_items=tuple(
                ClarificationQuestionItem(
                    requirement_id=requirement.requirement_id,
                    issue_ids=tuple(
                        issue.issue_id
                        for issue in input.issues
                        if issue.requirement_id == requirement.requirement_id
                    ),
                    question="Could you clarify this detail?",
                )
                for requirement in input.requirements
            )
        )

    def take_usage(self) -> dict[str, int] | None:
        calls, self.calls = self.calls, 0
        if not calls:
            return None
        return {
            "calls": calls,
            "captured_calls": 0,
            "missing_calls": calls,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def take_call_traces(self) -> list[dict[str, object]]:
        traces, self._traces = self._traces, []
        return traces


class _FailingUsageLessComposer(_UsageLessComposer):
    def __init__(self, fail_on_call: int) -> None:
        super().__init__()
        self._fail_on_call = fail_on_call

    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        self.calls += 1
        failing = self.calls == self._fail_on_call
        self._traces.append(
            {
                "stage": "composer",
                "latency_seconds": 0.01,
                "error": {"type": "Synthetic"} if failing else None,
            }
        )
        if failing:
            raise RuntimeError("synthetic composer failure")
        return ClarificationPromptComposition(
            question_items=tuple(
                ClarificationQuestionItem(
                    requirement_id=requirement.requirement_id,
                    issue_ids=tuple(
                        issue.issue_id
                        for issue in input.issues
                        if issue.requirement_id == requirement.requirement_id
                    ),
                    question="Could you clarify this detail?",
                )
                for requirement in input.requirements
            )
        )


class _TraceDrainFailingInterpreter(_UsageLessInterpreter):
    def take_call_traces(self) -> list[dict[str, object]]:
        raise RuntimeError("synthetic trace drain failure")


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


def test_live_runner_aggregates_usage_less_attempts_and_reconciles_stage_traces(tmp_path: Path) -> None:
    artifact = run_live_clarification_eval(
        trials=1,
        trace_dir=tmp_path / "traces",
        interpreter_factory=lambda _model: _UsageLessInterpreter(),
        composer_factory=lambda _model: _UsageLessComposer(),
    )

    assert artifact["summary"]["instrumentation"]["calls"] > 0
    assert artifact["summary"]["instrumentation"]["composer_calls"] > 0
    assert artifact["summary"]["instrumentation"]["reconciled_sessions"] == len(
        artifact["records"]
    )
    assert artifact["summary"]["instrumentation"]["unreconciled_sessions"] == 0
    assert artifact["summary"]["instrumentation"]["wall_latency_seconds"] >= 0
    assert artifact["summary"]["instrumentation"]["interpreter_latency_seconds"] > 0
    assert artifact["summary"]["instrumentation"]["composer_latency_seconds"] > 0
    assert all(
        record["stages"][stage]["reconciled"]
        and record["stages"][stage]["missing_calls"] == record["stages"][stage]["calls"]
        for record in artifact["records"]
        for stage in ("interpreter", "composer")
    )


@pytest.mark.parametrize("fail_on_call", [1, 2], ids=["initial_composition", "post_answer_composition"])
def test_live_runner_records_composer_failures_and_continues_matrix(
    tmp_path: Path, fail_on_call: int
) -> None:
    artifact = run_live_clarification_eval(
        trials=1,
        trace_dir=tmp_path / f"traces-{fail_on_call}",
        interpreter_factory=lambda _model: _UsageLessInterpreter(),
        composer_factory=lambda _model: _FailingUsageLessComposer(fail_on_call),
    )

    assert len(artifact["records"]) == 16
    failed = [record for record in artifact["records"] if record["system_error"]]
    assert failed
    assert artifact["summary"]["system_errors"] == len(failed)
    assert all(record["stages"]["composer"]["errors"] == 1 for record in failed)
    assert all(record["stages"]["composer"]["reconciled"] for record in failed)
    assert all(
        record["stages"]["composer"]["calls"]
        == record["stages"]["composer"]["trace_count"]
        for record in failed
    )
    if fail_on_call == 1:
        assert all(record["processed_turns"] == 0 for record in failed)
        assert all(record["final_status"] == "system_error" for record in failed)
    else:
        assert any(record["stages"]["composer"]["calls"] == 2 for record in failed)
        assert any(record["stages"]["interpreter"]["calls"] == 1 for record in failed)


def test_live_runner_fails_closed_when_telemetry_drain_raises(tmp_path: Path) -> None:
    artifact = run_live_clarification_eval(
        trials=1,
        trace_dir=tmp_path / "traces-drain-failure",
        interpreter_factory=lambda _model: _TraceDrainFailingInterpreter(),
        composer_factory=lambda _model: _UsageLessComposer(),
    )

    assert len(artifact["records"]) == 16
    assert artifact["summary"]["system_errors"] == len(artifact["records"])
    assert artifact["summary"]["instrumentation"]["unreconciled_sessions"] == len(
        artifact["records"]
    )
    assert artifact["summary"]["live_gate"]["passed"] is False
    assert all(record["system_error"] for record in artifact["records"])
    assert all(
        record["stages"]["interpreter"]["reconciled"] is False
        and record["stages"]["interpreter"]["evaluator_error"] is True
        and record["stages"]["interpreter"]["errors"] == 1
        for record in artifact["records"]
    )
