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
    CALENDAR_PROPOSAL_CONTRACT_VERSION,
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreter,
    ClarificationInterpretationUnavailable,
)
from award_agent.cli.clarification_behavior_live_eval import _parser
from award_agent.evaluation.clarification_behavior_live import (
    DEFAULT_LIVE_BEHAVIOR_FIXTURES,
    ClarificationBehaviorLiveFixtureError,
    _load_cases,
    _provider_stage_counts,
    _repair_telemetry,
    _string_leaves,
    _v3_outcome_failures,
    _v3_unnecessary_clarification,
    _value_failures,
    run_live_clarification_behavior_eval,
)


class _FakeInterpreter:
    def __init__(self) -> None:
        self.calls = 0
        self._traces: list[dict[str, object]] = []

    def interpret(
        self, _input: object
    ) -> ClarificationAnswerInterpretation | ClarificationInterpretationUnavailable:
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
        assert isinstance(result, ClarificationAnswerInterpretation)
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


class _PendingTraceInterpreter(_FakeInterpreter):
    def interpret(self, input: object) -> ClarificationAnswerInterpretation | ClarificationInterpretationUnavailable:
        super().interpret(input)
        self._traces[-1]["error"] = {"type": "Unavailable", "handled": True}
        return ClarificationInterpretationUnavailable(
            code="receiver_unavailable",
            detail="retryable test receiver outcome",
        )


def _failing_interpreter_factory(_model: str) -> ClarificationAnswerInterpreter:
    raise RuntimeError("synthetic constructor failure")


def test_live_behavior_fixture_preflight_has_required_v3_development_coverage() -> None:
    cases, _ = _load_cases(DEFAULT_LIVE_BEHAVIOR_FIXTURES)

    assert len(cases) >= 8
    assert {str(case["family"]) for case in cases} >= {
        "clear_resolvable",
        "alternatives",
        "endpoint_ambiguity",
        "correction_sibling",
        "sibling_retention",
        "disclosed_approximation",
        "conflict",
    }


def test_v3_sample_fixture_uses_only_behavioral_outcome_oracles() -> None:
    sample = Path("evals/clarification/live_cases_v3_sample.yaml")
    cases, _ = _load_cases(sample)

    oracle = cases[0]["turns"][0]["oracle"]
    assert oracle["expected_action"] == "ask"
    assert "proposal" not in json.dumps(oracle)
    assert "question_intent" in oracle  # typed intent, not literal composed copy
    assert "Could you" not in json.dumps(oracle)


def test_v3_development_corpus_covers_relational_and_acceptance_boundaries() -> None:
    cases, _ = _load_cases(Path("evals/clarification/live_cases_v3_development.yaml"))
    families = {case["family"] for case in cases}
    serialized = json.dumps(cases)

    assert {
        "clear_resolvable",
        "alternatives",
        "endpoint_ambiguity",
        "correction_sibling",
        "sibling_retention",
        "disclosed_approximation",
        "conflict",
    }.issubset(families)
    assert "return_after_departure" in serialized
    assert "proposal" not in serialized

    by_id = {case["id"]: case for case in cases}
    for identifier in ("clear_explicit_dates", "clear_explicit_dates_paraphrase"):
        oracle = by_id[identifier]["turns"][0]["oracle"]
        assert oracle["values"] == {"departure": "2026-10-06", "return": "2026-10-16"}
    sibling_oracle = by_id["valid_siblings_with_ambiguous_departure"]["turns"][0]["oracle"]
    assert sibling_oracle["disclosure"]["required"] is False


def test_v3_development_corpus_cannot_pass_without_required_family_coverage(tmp_path: Path) -> None:
    invalid = tmp_path / "missing-conflict.yaml"
    invalid.write_text(
        DEFAULT_LIVE_BEHAVIOR_FIXTURES.read_text().replace(
            "family: conflict", "family: another-family", 1
        )
    )

    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="required scenario families"):
        _load_cases(invalid)


def test_v3_sample_runs_through_observable_outcome_scorer(tmp_path: Path) -> None:
    artifact = run_live_clarification_behavior_eval(
        trials=1,
        fixture_path=Path("evals/clarification/live_cases_v3_sample.yaml"),
        trace_dir=tmp_path / "private-traces",
        interpreter_factory=lambda _model: _FakeInterpreter(),
        composer_factory=lambda _model: _FakeComposer(),
    )

    assert artifact["schema_version"] == "clarification_behavior_live_eval_v3"
    assert artifact["records"][0]["turn_metrics"][0]["observed_action"] == "ask"
    assert artifact["summary"]["behavioral"]["paired_accept_ask"]["passed"] is False
    assert artifact["summary"]["behavioral"]["paraphrase_consistency"]["passed"] is False


def test_v3_oracle_rejects_internal_proposal_assertions(tmp_path: Path) -> None:
    sample = Path("evals/clarification/live_cases_v3_sample.yaml")
    invalid = tmp_path / "internal-token.yaml"
    invalid.write_text(
        sample.read_text().replace(
            "          expected_action: ask",
            "          proposal_token: should-not-be-graded\n          expected_action: ask",
        )
    )

    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="observable outcome"):
        _load_cases(invalid)


def _v3_ask_oracle() -> dict[str, object]:
    return {
        "expected_action": "ask",
        "must_resolve": [],
        "must_remain_blocked": ["departure"],
        "protected_fields": ["origin", "destination", "travelers", "departure"],
        "forbidden_outcomes": ["unsafe_ambiguity_acceptance", "protected_field_mutation"],
        "state_envelope": {
            "statuses": ["awaiting_answer"],
            "relations": ["ready_iff_no_blockers", "prompt_covers_remaining_blockers"],
        },
        "question_intent": {
            "required": True,
            "requirement_ids": ["departure"],
            "issue_kinds": ["ambiguous"],
        },
        "disclosure": {"required": False},
        "properties": {},
    }


def test_v3_scores_equivalent_internal_forms_and_question_wording_identically() -> None:
    oracle = _v3_ask_oracle()

    def assess(prompt_message: str) -> tuple[str, list[str], list[str]]:
        return _v3_outcome_failures(
            oracle=oracle,
            answer_class="ambiguous",
            status="awaiting_answer",
            before_blockers=("departure",),
            blockers=("departure",),
            before_values={"departure": None},
            after_values={"departure": None},
            prompt_requirement_ids=("departure",),
            prompt_issue_kinds=("ambiguous",),
            prompt_message=prompt_message,
            disclosure_present=False,
        )

    first = assess("Which October date should I use?")
    second = assess("Could you choose one of those departure dates?")

    assert first == second == ("ask", [], [])


def test_v3_unsafe_ambiguity_acceptance_fails_closed() -> None:
    action, safety, behavioral = _v3_outcome_failures(
        oracle=_v3_ask_oracle(),
        answer_class="ambiguous",
        status="ready",
        before_blockers=("departure",),
        blockers=(),
        before_values={"departure": None},
        after_values={"departure": ("2026-10-03", "2026-10-03")},
        prompt_requirement_ids=None,
        prompt_issue_kinds=(),
        prompt_message=None,
        disclosure_present=False,
    )

    assert action == "resolve"
    assert "unsafe ambiguity acceptance" in safety
    assert "forbidden outcome: unsafe_ambiguity_acceptance" in safety
    assert behavioral


def test_v3_unnecessary_clarification_uses_structured_outcome_not_copy() -> None:
    resolve_oracle = _v3_ask_oracle() | {"expected_action": "resolve"}

    assert _v3_unnecessary_clarification(
        action="ask",
        oracle=resolve_oracle,
        behavioral_failures=("false blocking", "outcome action outside expected envelope"),
    )
    assert _v3_unnecessary_clarification(
        action="ask",
        oracle=resolve_oracle,
        behavioral_failures=("forbidden outcome: unnecessary_ask",),
    )
    assert not _v3_unnecessary_clarification(
        action="ask", oracle=_v3_ask_oracle(), behavioral_failures=()
    )


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
    adapter_metadata = artifact["summary"]["metadata"]["adapter"]
    assert set(adapter_metadata) == {"interpreter", "composer"}
    assert all(
        isinstance(item["version"], str)
        and len(item["response_schema_sha256"]) == 64
        for item in adapter_metadata.values()
    )
    assert (
        artifact["summary"]["metadata"]["proposal_contract_version"]
        == CALENDAR_PROPOSAL_CONTRACT_VERSION
    )
    assert artifact["summary"]["metadata"]["provider_stage_counts"] == {
        "preflight_rejected": 0,
        "inference_reached": 0,
        "structured_result_returned": 0,
    }
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
    legacy = Path("evals/clarification/live_cases_v2.yaml")
    private = tmp_path / "private.yaml"
    private.write_text(legacy.read_text() + "\napi_key: forbidden\n")
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="privacy"):
        _load_cases(private)

    short = tmp_path / "short.yaml"
    payload = legacy.read_text().replace("  - id:", "  - id:", 1)
    lines = payload.splitlines()
    # Retain only the first scenario so fixture cardinality is rejected before
    # any call factory could be used.
    cut = next(index for index, line in enumerate(lines[1:], start=1) if line.startswith("  - id:"))
    short.write_text("\n".join(lines[:cut]) + "\n")
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="at least 16"):
        _load_cases(short)

    malformed_envelope = tmp_path / "malformed-envelope.yaml"
    malformed_envelope.write_text(
        legacy.read_text().replace("start_day: [1, 3]", "start_day: [1]", 1)
    )
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="departure_window"):
        _load_cases(malformed_envelope)

    missing_conflict = tmp_path / "missing-conflict.yaml"
    missing_conflict.write_text(
        legacy.read_text().replace("family: conflict", "family: another-family", 1)
    )
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="required scenario families"):
        _load_cases(missing_conflict)

    invalid_iso = tmp_path / "invalid-iso.yaml"
    invalid_iso.write_text(
        legacy.read_text().replace(
            '{departure: "2026-10-06"', '{departure: "10/06/2026"', 1
        )
    )
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="ISO date"):
        _load_cases(invalid_iso)

    invalid_sibling = tmp_path / "invalid-sibling.yaml"
    invalid_sibling.write_text(
        legacy.read_text().replace(
            "valid_siblings: [origin, return_or_duration, travelers]",
            "valid_siblings: [origin, departure]",
            1,
        )
    )
    with pytest.raises(ClarificationBehaviorLiveFixtureError, match="valid_siblings"):
        _load_cases(invalid_sibling)

    unknown_requirement = tmp_path / "unknown-requirement.yaml"
    unknown_requirement.write_text(
        legacy.read_text().replace(
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
        "unhandled model trace error" in record["safety_failures"]
        for record in artifact["records"]
    )


def test_v3_pending_receiver_is_reported_without_trace_reconciliation_failure(tmp_path: Path) -> None:
    fixture = tmp_path / "pending.yaml"
    fixture.write_text(
        Path("evals/clarification/live_cases_v3_sample.yaml")
        .read_text()
        .replace("expected_action: ask", "expected_action: pending_retryable")
    )
    artifact = run_live_clarification_behavior_eval(
        trials=1,
        fixture_path=fixture,
        trace_dir=tmp_path / "private-traces",
        interpreter_factory=lambda _model: _PendingTraceInterpreter(),
        composer_factory=lambda _model: _FakeComposer(),
    )

    record = artifact["records"][0]
    assert record["turn_metrics"][0]["observed_action"] == "pending_retryable"
    assert record["repair_telemetry"]["pending_receiver"] == 1
    assert "model trace reconciliation failed" not in record["safety_failures"]
    assert artifact["summary"]["exact_safety_gate"]["passed"] is True


def test_repair_telemetry_does_not_count_pending_repair_as_workflow_success() -> None:
    telemetry = _repair_telemetry(
        (
            {"stage": "interpreter", "latency_seconds": 0.1, "error": None},
            {"stage": "interpreter_repair", "latency_seconds": 0.2, "error": None},
            {"stage": "interpreter_repair", "latency_seconds": 0.3, "error": {"type": "bad"}},
        ),
        pending_retryable=1,
        pending_receiver=1,
        pending_composer=0,
    )

    assert telemetry == {
        "first_pass_calls": 1,
        "repair_calls": 2,
        "repair_errors": 1,
        "repaired_workflows": 0,
        "repair_latency_seconds": 0.5,
        "pending_retryable": 1,
        "pending_receiver": 1,
        "pending_composer": 0,
    }


def test_repair_telemetry_counts_completed_nonpending_repair_workflow() -> None:
    telemetry = _repair_telemetry(
        (
            {"stage": "interpreter", "latency_seconds": 0.1, "error": None},
            {"stage": "interpreter_repair", "latency_seconds": 0.2, "error": None},
        ),
        pending_retryable=0,
        pending_receiver=0,
        pending_composer=0,
    )

    assert telemetry["repaired_workflows"] == 1


def test_provider_stage_counts_are_exact_and_nonexclusive() -> None:
    counts = _provider_stage_counts(
        (
            {"adapter": {"provider_stage": "preflight_rejected"}},
            {"adapter": {"provider_stage": "inference_reached"}},
            {"adapter": {"provider_stage": "structured_result_returned"}},
            {"adapter": {"provider_stage": "structured_result_returned"}},
        )
    )

    assert counts == {
        "preflight_rejected": 1,
        "inference_reached": 3,
        "structured_result_returned": 2,
    }


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
    assert artifact["summary"]["behavioral"]["paired_accept_ask"]["trial_runs"] == 2
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
