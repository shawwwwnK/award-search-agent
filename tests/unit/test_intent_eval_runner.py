import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from award_agent.cli import intent_eval as intent_eval_module
from award_agent.cli.intent_eval import (
    DEFAULT_LLM_TRACE_DIR,
    _aggregate_results,
    _combine_usage,
    _parser,
    _score_result,
    _usage_summary,
)
from award_agent.domain import (
    CalendarPeriodSemantics,
    ClarificationAction,
    ClarificationDecision,
    CoarseIntentExtraction,
    Conflict,
    DateResolutionProposal,
    DateWindow,
    DateWindowPrecision,
    InterpretedDuration,
    LocationKind,
    LocationRef,
    ParsedRequest,
    ProposedDateWindow,
    RawRequest,
    RelativeCalendarPeriodConstraint,
    RequestContext,
    RequestUnderstandingResult,
    SearchMode,
    SymbolicContextReference,
    TemporalDirection,
    TemporalRelationGraph,
    TemporalTarget,
    TemporalUnit,
    UnknownField,
    UnknownReason,
)
from award_agent.intent.model_views import NonTemporalIntentExtraction
from award_agent.intent.temporal_selector import TemporalSelectorValidationError
from award_agent.observability.llm_trace import write_eval_llm_trace


def _result() -> RequestUnderstandingResult:
    return RequestUnderstandingResult(
        parsed_request=ParsedRequest(
            raw_text="Two travelers from LAX to Tokyo in October for a week using miles.",
            context=RequestContext(reference_date=date(2026, 8, 29), timezone="UTC"),
            travelers=2,
            origins=[LocationRef(kind=LocationKind.AIRPORT, value="LAX", raw_text="LAX")],
            destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
            departure_expression=None,
            return_expression=None,
            departure_window=DateWindow(
                start=date(2026, 10, 1),
                end=date(2026, 10, 31),
                precision=DateWindowPrecision.MONTH,
                raw_text="in October",
            ),
            return_window=DateWindow(
                start=date(2026, 10, 8),
                end=date(2026, 11, 7),
                precision=DateWindowPrecision.DERIVED,
                raw_text="for a week",
            ),
            duration=None,
            cabins=[],
            search_modes=[SearchMode.AWARD],
            date_flexibility=[],
            repositioning_allowed=None,
            hard_constraints=[],
            unknowns=[
                UnknownField(
                    field="cabin",
                    reason=UnknownReason.MISSING,
                    detail="No cabin preference was stated.",
                )
            ],
            conflicts=[],
            temporal_extraction=CoarseIntentExtraction(travelers=2),
            date_resolution=DateResolutionProposal(
                departure=ProposedDateWindow(
                    start=date(2026, 10, 1),
                    end=date(2026, 10, 31),
                    supporting_text=["October"],
                    interpretation="Whole month.",
                ),
                return_date=ProposedDateWindow(
                    start=date(2026, 10, 8),
                    end=date(2026, 11, 7),
                    supporting_text=["for a week"],
                    interpretation="Seven days.",
                ),
                interpreted_duration=InterpretedDuration(
                    raw_text="for a week", minimum_days=7, maximum_days=7
                ),
            ),
        ),
        clarification=ClarificationDecision(
            action=ClarificationAction.NONE,
            reason="Enough constraints.",
        ),
    )


def test_score_result_checks_supported_golden_expectations() -> None:
    expected = {
        "travelers": 2,
        "origin": {"kind": "airport", "value": "LAX"},
        "destination": {"kind": "city", "value": "Tokyo"},
        "search_modes": ["award"],
        "departure_window": {"start": "2026-10-01", "end": "2026-10-31"},
        "return_window": {"start": "2026-10-08", "end": "2026-11-07"},
        "interpreted_duration": {"minimum_days": 7, "maximum_days": 7},
        "unknowns": ["cabin"],
        "clarification": {"action": "none"},
    }

    checks = _score_result(expected, _result())

    assert checks
    assert all(check["passed"] for check in checks)


def test_score_result_reports_mismatches() -> None:
    checks = _score_result({"travelers": 3}, _result())

    assert checks == [{"name": "travelers", "passed": False, "expected": 3, "actual": 2}]


def test_score_result_checks_semantic_relations_without_raw_text_segmentation() -> None:
    result = _result()
    relations = TemporalRelationGraph.model_validate(
        {
            "constraints": [
                {
                    "kind": "relative_weekend",
                    "target": "return",
                    "reference": {
                        "kind": "request_field",
                        "field": "departure",
                        "edge": "end",
                    },
                    "direction": "after",
                    "ordinal": 1,
                    "raw_text": "the weekend afterwards",
                }
            ]
        }
    )
    parsed = result.parsed_request.model_copy(update={"temporal_relations": relations})

    checks = _score_result(
        {
            "temporal_relations": [
                {
                    "kind": "relative_weekend",
                    "target": "return",
                    "reference": {"kind": "request_field", "field": "departure"},
                    "direction": "after",
                    "ordinal": 1,
                }
            ]
        },
        result.model_copy(update={"parsed_request": parsed}),
    )

    assert checks[0]["passed"] is True


def test_score_result_checks_context_relative_calendar_period_semantics() -> None:
    result = _result()
    relations = TemporalRelationGraph(
        constraints=[
            RelativeCalendarPeriodConstraint(
                kind="relative_calendar_period",
                target=TemporalTarget.DEPARTURE,
                reference=SymbolicContextReference(
                    kind="symbolic_context",
                    key="context:request_date",
                ),
                direction=TemporalDirection.AFTER,
                unit=TemporalUnit.MONTH,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                raw_text="next month",
            )
        ]
    )
    parsed = result.parsed_request.model_copy(update={"temporal_relations": relations})

    checks = _score_result(
        {
            "temporal_relations": [
                {
                    "kind": "relative_calendar_period",
                    "target": "departure",
                    "reference": {
                        "kind": "symbolic_context",
                        "key": "context:request_date",
                    },
                    "direction": "after",
                    "unit": "month",
                    "ordinal": 1,
                    "period_semantics": "whole",
                }
            ]
        },
        result.model_copy(update={"parsed_request": parsed}),
    )

    assert checks[0]["passed"] is True


def test_score_result_accepts_only_explicit_location_candidate_aliases() -> None:
    expected = {
        "destination": {
            "kind": "city",
            "raw_text": "Tokyo",
            "accepted_values": ["Tokyo", "Tōkyō"],
        }
    }

    checks = _score_result(expected, _result())

    assert checks[0]["passed"] is True


def test_score_result_does_not_fuzzy_match_location_candidates() -> None:
    expected = {
        "destination": {
            "kind": "city",
            "raw_text": "Tokyo",
            "accepted_values": ["Tōkyō"],
        }
    }

    checks = _score_result(expected, _result())

    assert checks[0]["passed"] is False


def test_score_result_still_requires_exact_location_evidence() -> None:
    expected = {
        "destination": {
            "kind": "city",
            "raw_text": "Tokio",
            "accepted_values": ["Tokyo"],
        }
    }

    checks = _score_result(expected, _result())

    assert checks[0]["passed"] is False


def test_score_result_rejects_invalid_location_candidate_alias_contract() -> None:
    expected = {
        "destination": {
            "kind": "city",
            "accepted_values": [],
        }
    }

    try:
        _score_result(expected, _result())
    except ValueError as exc:
        assert str(exc) == "location accepted_values must be a non-empty list of strings"
    else:
        raise AssertionError("invalid accepted_values should fail explicitly")


def test_score_result_preserves_conflict_visibility() -> None:
    result = _result()
    conflict = Conflict(
        code="return_before_departure",
        fields=["departure", "return_date"],
        detail="Return precedes departure.",
    )
    parsed = result.parsed_request.model_copy(update={"conflicts": [conflict]})
    result = result.model_copy(update={"parsed_request": parsed})

    checks = _score_result({"conflicts": ["return_before_departure"]}, result)

    assert checks == [
        {
            "name": "conflicts",
            "passed": True,
            "expected": ["return_before_departure"],
            "actual": ["return_before_departure"],
        }
    ]
    assert result.parsed_request.conflicts[0] == conflict


def test_score_result_distinguishes_literal_duration_from_normalized_days() -> None:
    result = _result()
    relations = TemporalRelationGraph.model_validate(
        {
            "constraints": [
                {
                    "kind": "duration",
                    "target": "return",
                    "reference": {
                        "kind": "request_field",
                        "field": "departure",
                        "edge": "end",
                    },
                    "stated_minimum_quantity": 1,
                    "stated_maximum_quantity": 1,
                    "unit": "week",
                    "modifier": "exact",
                    "raw_text": "a week",
                }
            ]
        }
    )
    parsed = result.parsed_request.model_copy(update={"temporal_relations": relations})

    checks = _score_result(
        {
            "literal_duration": {
                "stated_minimum_quantity": 1,
                "stated_maximum_quantity": 1,
                "unit": "week",
                "modifier": "exact",
            },
            "interpreted_duration": {"minimum_days": 7, "maximum_days": 7},
        },
        result.model_copy(update={"parsed_request": parsed}),
    )

    assert [check["name"] for check in checks] == [
        "interpreted_duration",
        "literal_duration",
    ]
    assert all(check["passed"] for check in checks)


def test_score_result_rejects_deictic_month_normalized_as_explicit_month_anchor() -> None:
    result = _result()
    extraction = CoarseIntentExtraction.model_validate(
        {
            "date_anchors": [
                {
                    "kind": "month",
                    "anchor_id": "invented",
                    "applies_to": "departure",
                    "raw_text": "September",
                    "month": 9,
                }
            ]
        }
    )
    parsed = result.parsed_request.model_copy(update={"temporal_extraction": extraction})

    checks = _score_result(
        {"forbidden_date_anchor_kinds": ["month"]},
        result.model_copy(update={"parsed_request": parsed}),
    )

    assert checks == [
        {
            "name": "forbidden_date_anchor_kinds",
            "passed": False,
            "expected": [],
            "actual": ["month"],
        }
    ]


def test_aggregate_results_separates_stages_repairs_and_completion() -> None:
    results: Sequence[Mapping[str, Any]] = [
        {
            "status": "passed",
            "output": {},
            "attempts": {
                "first_attempt_completed": True,
                "repair_attempts": 0,
                "repair_successes": 0,
            },
            "evaluation": {
                "grounding_valid": True,
                "semantic_fields_valid": True,
                "deterministic_outputs_valid": True,
            },
            "checks": [{"name": "clarification", "passed": True}],
        },
        {
            "status": "failed",
            "output": {},
            "attempts": {
                "first_attempt_completed": False,
                "repair_attempts": 1,
                "repair_successes": 1,
            },
            "evaluation": {
                "grounding_valid": True,
                "semantic_fields_valid": True,
                "deterministic_outputs_valid": False,
            },
            "checks": [{"name": "clarification", "passed": False}],
        },
        {
            "status": "error",
            "failure_stage": "pass_two_wire_conversion",
            "attempts": {
                "first_attempt_completed": False,
                "repair_attempts": 1,
                "repair_successes": 0,
            },
        },
        {
            "status": "error",
            "failure_stage": "pass_one_grounding",
            "attempts": {
                "first_attempt_completed": False,
                "repair_attempts": 1,
                "repair_successes": 0,
            },
        },
        {
            "status": "error",
            "failure_stage": "pass_two_conformance",
            "attempts": {
                "first_attempt_completed": False,
                "repair_attempts": 0,
                "repair_successes": 0,
            },
        },
    ]

    summary = _aggregate_results(results)

    assert summary == {
        "first_attempt_completion": {"runs": 1, "rate": 0.2},
        "final_completion": {"runs": 2, "rate": 0.4},
        "repair_attempts": 3,
        "repair_successes": 1,
        "pass_one_failures": 1,
        "selector_failures": 0,
        "pass_two_wire_failures": 1,
        "grounding_failures": 1,
        "semantic_validation_failures": 1,
        "deterministic_output_failures": 1,
        "clarification_failures": 1,
    }


def test_usage_summary_aggregates_captured_calls_and_keeps_missing_usage_explicit() -> None:
    results: Sequence[Mapping[str, Any]] = [
        {
            "usage": {
                "calls": 3,
                "captured_calls": 2,
                "missing_calls": 1,
                "input_tokens": 30,
                "output_tokens": 6,
                "total_tokens": 36,
            }
        },
        {"usage": None},
    ]

    assert _usage_summary(results) == {
        "captured_runs": 1,
        "missing_runs": 1,
        "input_tokens": 30,
        "output_tokens": 6,
        "total_tokens": 36,
        "calls": 3,
        "captured_calls": 2,
        "missing_calls": 1,
    }
    assert _usage_summary([{"usage": None}]) == ("unavailable: SDK responses did not provide usage")


def test_combine_usage_adds_split_pass_model_calls() -> None:
    assert _combine_usage(
        {
            "calls": 2,
            "captured_calls": 2,
            "missing_calls": 0,
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
        },
        {
            "calls": 1,
            "captured_calls": 1,
            "missing_calls": 0,
            "input_tokens": 50,
            "output_tokens": 5,
            "total_tokens": 55,
        },
    ) == {
        "calls": 3,
        "captured_calls": 3,
        "missing_calls": 0,
        "input_tokens": 150,
        "output_tokens": 15,
        "total_tokens": 165,
    }
    assert _combine_usage(None, None) is None


def test_write_eval_llm_trace_preserves_failure_record_and_call_payload(tmp_path: Path) -> None:
    path = write_eval_llm_trace(
        tmp_path,
        scenario={
            "id": "trace_case",
            "input": "Fly from Seattle to Tokyo.",
            "context": {"reference_date": "2026-08-31", "timezone": "UTC"},
        },
        record={
            "id": "trace_case",
            "trial": 2,
            "status": "error",
            "failure_stage": "pass_two_wire_conversion",
            "failure_code": "unknown_evidence_id",
        },
        calls=[
            {
                "sequence": 1,
                "stage": "pass_two",
                "request": {"input": '{"evidence":"e0"}'},
                "response_json": '{"id":"response-1"}',
                "parsed_output": {"decisions": []},
                "error": None,
            }
        ],
    )

    payload = json.loads(path.read_text())
    assert payload["scenario"]["input"] == "Fly from Seattle to Tokyo."
    assert payload["evaluation_record"]["failure_code"] == "unknown_evidence_id"
    assert payload["calls"][0]["request"]["input"] == '{"evidence":"e0"}'
    assert payload["calls"][0]["response_json"] == '{"id":"response-1"}'


def test_eval_parser_defaults_to_failure_traces_and_allows_opt_out() -> None:
    args = _parser().parse_args(["--model", "test-model", "--output", "result.json"])

    assert args.trace_dir == DEFAULT_LLM_TRACE_DIR
    assert args.no_trace is False

    no_trace_args = _parser().parse_args(
        ["--model", "test-model", "--output", "result.json", "--no-trace"]
    )
    assert no_trace_args.no_trace is True


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            [
                "--model",
                "test-model",
                "--output",
                "result.json",
                "--strategy",
                "compiler_select_v1",
                "--pass-two-model",
                "legacy-model",
            ],
            "--pass-two-model is only compatible with --strategy two_pass",
        ),
        (
            [
                "--model",
                "test-model",
                "--output",
                "result.json",
                "--strategy",
                "two_pass",
                "--selector-model",
                "selector-model",
            ],
            "--selector-model is only compatible with --strategy compiler_select_v1",
        ),
        (
            [
                "--model",
                "test-model",
                "--output",
                "result.json",
                "--strategy",
                "two_pass",
                "--selector-policy",
                "supported_or_unresolved",
            ],
            "--selector-policy is only compatible with --strategy compiler_select_v1",
        ),
        (
            [
                "--model",
                "test-model",
                "--output",
                "result.json",
                "--strategy",
                "one_pass",
                "--selector-policy",
                "supported_or_unresolved",
            ],
            "--selector-policy is only compatible with --strategy compiler_select_v1",
        ),
    ],
)
def test_eval_parser_rejects_strategy_incompatible_model_flags(
    arguments: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit, match="2"):
        _parser().parse_args(arguments)

    assert message in capsys.readouterr().err


def test_eval_parser_accepts_experiment_only_compiler_selector_policy() -> None:
    args = _parser().parse_args(
        [
            "--model",
            "test-model",
            "--output",
            "result.json",
            "--strategy",
            "compiler_select_v1",
            "--selector-model",
            "selector-model",
            "--selector-policy",
            "supported_or_unresolved",
        ]
    )

    assert args.selector_policy == "supported_or_unresolved"


def test_eval_parser_requires_selector_for_experiment_only_policy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="2"):
        _parser().parse_args(
            [
                "--model",
                "test-model",
                "--output",
                "result.json",
                "--strategy",
                "compiler_select_v1",
                "--selector-policy",
                "supported_or_unresolved",
            ]
        )

    assert "--selector-model is required" in capsys.readouterr().err


def test_run_eval_rejects_experiment_only_policy_outside_compiler_strategy() -> None:
    with pytest.raises(ValueError, match="only compatible with --strategy compiler_select_v1"):
        intent_eval_module.run_eval(
            "test-model",
            Path("not-read-because-validation-fails.yaml"),
            1,
            strategy="one_pass",
            selector_policy="supported_or_unresolved",
        )


def _single_ready_case(path: Path) -> Path:
    path.write_text(
        """scenarios:
  - id: runner_case
    status: ready
    input: Fly from Seattle to Tokyo.
    context:
      reference_date: "2026-08-31"
      timezone: UTC
    expected: {}
"""
    )
    return path


def test_compiler_eval_constructs_only_non_temporal_pass_one_for_auto_only_ready_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instances: list[Any] = []

    class FakeExtractor:
        def __init__(self, *, config: Any, capture_llm_io: bool) -> None:
            assert capture_llm_io is True
            self.model = config.model
            self.calls: list[dict[str, Any]] = []
            instances.append(self)

        def reset_capture(self) -> None:
            self.calls = []

        def extract_non_temporal(self, _input: Any) -> NonTemporalIntentExtraction:
            self.calls.append({"stage": "compiler_non_temporal_pass_one", "latency_seconds": 0.2})
            return NonTemporalIntentExtraction()

        def take_usage(self) -> dict[str, int] | None:
            return {
                "calls": len(self.calls),
                "captured_calls": len(self.calls),
                "missing_calls": 0,
                "input_tokens": 3,
                "output_tokens": 2,
                "total_tokens": 5,
            }

        def take_call_traces(self) -> list[dict[str, Any]]:
            calls = self.calls
            self.calls = []
            return calls

    def fake_understand(
        _request: RawRequest,
        extractor: FakeExtractor,
        resolver: object | None,
        _holiday_provider: object,
        *,
        temporal_strategy: str,
        temporal_selector: object | None,
        selector_policy: str,
    ) -> RequestUnderstandingResult:
        assert temporal_strategy == "compiler_select_v1"
        assert resolver is None
        assert temporal_selector is None
        assert selector_policy == "ambiguous_only"
        extractor.extract_non_temporal(object())
        return _result()

    monkeypatch.setattr(intent_eval_module, "OpenAIIntentExtractor", FakeExtractor)
    monkeypatch.setattr(intent_eval_module, "understand_request", fake_understand)

    artifact = intent_eval_module.run_eval(
        "base-model",
        _single_ready_case(tmp_path / "cases.yaml"),
        1,
        strategy="compiler_select_v1",
        trace_dir=None,
    )

    assert [instance.model for instance in instances] == ["base-model"]
    telemetry = artifact["results"][0]["stage_telemetry"]
    assert telemetry["pass_one"]["attempts"] == 1
    assert telemetry["selector"]["attempts"] == 0
    assert telemetry["selector"]["enabled"] is False
    assert telemetry["pass_two"]["attempts"] == 0
    assert telemetry["pass_one"]["latency_seconds"] == 0.2
    assert "llm_trace" not in artifact
    assert artifact["stage_telemetry"]["pass_one"]["attempts"] == 1


def test_compiler_eval_uses_independently_configured_selector_once_for_ambiguity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instances: list[Any] = []

    class FakeExtractor:
        def __init__(self, *, config: Any, capture_llm_io: bool) -> None:
            self.model = config.model
            self.calls: list[dict[str, Any]] = []
            instances.append(self)

        def reset_capture(self) -> None:
            self.calls = []

        def extract_non_temporal(self, _input: Any) -> NonTemporalIntentExtraction:
            self.calls.append({"stage": "compiler_non_temporal_pass_one", "latency_seconds": 0.1})
            return NonTemporalIntentExtraction()

        def select_candidates(self, _input: object) -> object:
            self.calls.append({"stage": "temporal_candidate_selector", "latency_seconds": 0.3})
            return object()

        def take_usage(self) -> None:
            return None

        def take_call_traces(self) -> list[dict[str, Any]]:
            calls = self.calls
            self.calls = []
            return calls

    def fake_understand(
        _request: RawRequest,
        extractor: FakeExtractor,
        resolver: object | None,
        _holiday_provider: object,
        *,
        temporal_strategy: str,
        temporal_selector: FakeExtractor | None,
        selector_policy: str,
    ) -> RequestUnderstandingResult:
        assert temporal_strategy == "compiler_select_v1"
        assert resolver is None
        assert temporal_selector is not None
        assert selector_policy == "ambiguous_only"
        extractor.extract_non_temporal(object())
        temporal_selector.select_candidates(object())
        return _result()

    monkeypatch.setattr(intent_eval_module, "OpenAIIntentExtractor", FakeExtractor)
    monkeypatch.setattr(intent_eval_module, "understand_request", fake_understand)

    artifact = intent_eval_module.run_eval(
        "base-model",
        _single_ready_case(tmp_path / "cases.yaml"),
        1,
        strategy="compiler_select_v1",
        pass_one_model="pass-one-model",
        selector_model="selector-model",
        trace_dir=None,
    )

    assert [instance.model for instance in instances] == ["pass-one-model", "selector-model"]
    telemetry = artifact["results"][0]["stage_telemetry"]
    assert telemetry["pass_one"]["model"] == "pass-one-model"
    assert telemetry["selector"] == {
        "enabled": True,
        "configured": True,
        "model": "selector-model",
        "selector_policy": "ambiguous_only",
        "attempts": 1,
        "latency_seconds": 0.3,
        "usage": None,
    }
    assert telemetry["pass_two"]["attempts"] == 0


def test_compiler_eval_records_and_propagates_experiment_selector_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[str] = []

    class FakeExtractor:
        def __init__(self, *, config: Any, **_kwargs: Any) -> None:
            self.model = config.model

        def reset_capture(self) -> None:
            return None

        def take_usage(self) -> None:
            return None

        def take_call_traces(self) -> list[dict[str, Any]]:
            return []

    def fake_understand(
        _request: RawRequest,
        _extractor: FakeExtractor,
        _resolver: object | None,
        _holiday_provider: object,
        *,
        temporal_strategy: str,
        temporal_selector: FakeExtractor | None,
        selector_policy: str,
    ) -> RequestUnderstandingResult:
        assert temporal_strategy == "compiler_select_v1"
        assert temporal_selector is not None
        captured.append(selector_policy)
        return _result()

    monkeypatch.setattr(intent_eval_module, "OpenAIIntentExtractor", FakeExtractor)
    monkeypatch.setattr(intent_eval_module, "understand_request", fake_understand)

    artifact = intent_eval_module.run_eval(
        "base-model",
        _single_ready_case(tmp_path / "cases.yaml"),
        1,
        strategy="compiler_select_v1",
        selector_model="selector-model",
        selector_policy="supported_or_unresolved",
        trace_dir=None,
    )

    assert captured == ["supported_or_unresolved"]
    assert artifact["selector_policy"] == "supported_or_unresolved"
    assert artifact["stage_telemetry"]["selector"]["selector_policy"] == (
        "supported_or_unresolved"
    )


def test_compiler_selector_failure_is_redacted_and_never_classified_as_pass_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeExtractor:
        def __init__(self, *, config: Any, **_kwargs: Any) -> None:
            self.model = config.model
            self.calls: list[dict[str, Any]] = []

        def reset_capture(self) -> None:
            self.calls = []

        def extract_non_temporal(self, _input: Any) -> NonTemporalIntentExtraction:
            self.calls.append({"stage": "compiler_non_temporal_pass_one", "latency_seconds": 0.1})
            return NonTemporalIntentExtraction()

        def select_candidates(self, _input: object) -> object:
            self.calls.append({"stage": "temporal_candidate_selector", "latency_seconds": 0.2})
            raise TemporalSelectorValidationError("unknown private candidate c31 and slot p42")

        def take_usage(self) -> None:
            return None

        def take_call_traces(self) -> list[dict[str, Any]]:
            calls = self.calls
            self.calls = []
            return calls

    def fake_understand(
        _request: RawRequest,
        extractor: FakeExtractor,
        _resolver: object | None,
        _holiday_provider: object,
        *,
        temporal_strategy: str,
        temporal_selector: FakeExtractor | None,
        selector_policy: str,
    ) -> RequestUnderstandingResult:
        assert temporal_strategy == "compiler_select_v1"
        assert temporal_selector is not None
        assert selector_policy == "ambiguous_only"
        extractor.extract_non_temporal(object())
        temporal_selector.select_candidates(object())
        raise AssertionError("selector error should have stopped the run")

    monkeypatch.setattr(intent_eval_module, "OpenAIIntentExtractor", FakeExtractor)
    monkeypatch.setattr(intent_eval_module, "understand_request", fake_understand)

    artifact = intent_eval_module.run_eval(
        "base-model",
        _single_ready_case(tmp_path / "cases.yaml"),
        1,
        strategy="compiler_select_v1",
        selector_model="selector-model",
        trace_dir=None,
    )

    result = artifact["results"][0]
    assert result["failure_stage"] == "temporal_candidate_selector"
    assert result["failure_code"] == "selector_validation"
    assert result["error"] == "temporal candidate selection failed"
    assert "private" not in json.dumps(result)
    assert "pass_two_wire_failures" not in result["failure_categories"]
    assert result["stage_telemetry"]["selector"]["attempts"] == 1


def test_two_pass_eval_retains_legacy_boundaries_and_totals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instances: list[Any] = []

    class FakeExtractor:
        def __init__(self, *, config: Any, **_kwargs: Any) -> None:
            self.model = config.model
            self.calls: list[dict[str, Any]] = []
            instances.append(self)

        def reset_capture(self) -> None:
            self.calls = []

        def extract(self, _input: object) -> object:
            self.calls.append({"stage": "pass_one", "latency_seconds": 0.1})
            return object()

        def resolve_dates(self, _input: object) -> object:
            self.calls.append({"stage": "pass_two", "latency_seconds": 0.2})
            return object()

        def take_usage(self) -> dict[str, int]:
            return {
                "calls": len(self.calls),
                "captured_calls": len(self.calls),
                "missing_calls": 0,
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
            }

        def take_call_traces(self) -> list[dict[str, Any]]:
            calls = self.calls
            self.calls = []
            return calls

    def fake_understand(
        _request: RawRequest,
        pass_one: FakeExtractor,
        pass_two: FakeExtractor,
        _holiday_provider: object,
    ) -> RequestUnderstandingResult:
        assert pass_one is not pass_two
        pass_one.extract(object())
        pass_two.resolve_dates(object())
        return _result()

    monkeypatch.setattr(intent_eval_module, "OpenAIIntentExtractor", FakeExtractor)
    monkeypatch.setattr(intent_eval_module, "understand_request", fake_understand)

    artifact = intent_eval_module.run_eval(
        "base-model",
        _single_ready_case(tmp_path / "cases.yaml"),
        1,
        pass_one_model="pass-one-model",
        pass_two_model="pass-two-model",
        trace_dir=None,
    )

    assert [instance.model for instance in instances] == ["pass-one-model", "pass-two-model"]
    assert artifact["schema_version"] == 5
    assert artifact["summary"]["runs"] == 1
    assert artifact["summary"]["passed"] == 1
    assert artifact["summary"]["usage"]["calls"] == 2
    telemetry = artifact["results"][0]["stage_telemetry"]
    assert telemetry["pass_one"]["attempts"] == 1
    assert telemetry["pass_two"]["attempts"] == 1
    assert telemetry["selector"]["attempts"] == 0


def test_run_eval_links_non_passing_case_to_llm_trace_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeExtractor:
        def __init__(self, *, capture_llm_io: bool, **_kwargs: Any) -> None:
            assert capture_llm_io is True

        def reset_capture(self) -> None:
            return None

        def take_usage(self) -> None:
            return None

        def take_call_traces(self) -> list[dict[str, Any]]:
            return []

    class FakeOnePass:
        def __init__(self, *, capture_llm_io: bool, **_kwargs: Any) -> None:
            assert capture_llm_io is True

        def run(
            self, _request: RawRequest
        ) -> tuple[RequestUnderstandingResult, dict[str, Any] | None]:
            return _result(), None

        def take_call_traces(self) -> list[dict[str, Any]]:
            return [
                {
                    "sequence": 1,
                    "stage": "one_pass",
                    "request": {
                        "model": "test-model",
                        "instructions": "exact instructions",
                        "input": '{"text":"Fly"}',
                        "text_format": {"name": "RequestUnderstandingResult"},
                        "store": False,
                    },
                    "response_json": '{"id":"response-1"}',
                    "parsed_output": {"travelers": 2},
                    "error": None,
                }
            ]

    monkeypatch.setattr(intent_eval_module, "OpenAIIntentExtractor", FakeExtractor)
    monkeypatch.setattr(intent_eval_module, "OnePassIntentExperiment", FakeOnePass)
    cases_path = tmp_path / "cases.yaml"
    cases_path.write_text(
        """scenarios:
  - id: trace_case
    status: ready
    input: Fly from Seattle to Tokyo.
    context:
      reference_date: "2026-08-31"
      timezone: UTC
    expected:
      travelers: 3
"""
    )

    artifact = intent_eval_module.run_eval(
        "test-model",
        cases_path,
        1,
        strategy="one_pass",
        trace_dir=tmp_path / "traces",
    )

    result = artifact["results"][0]
    assert result["status"] == "failed"
    trace_reference = result["llm_trace"]
    assert isinstance(trace_reference, dict)
    trace_path = Path(str(trace_reference["path"]))
    assert trace_path.exists()
    trace_payload = json.loads(trace_path.read_text())
    assert trace_payload["evaluation_record"]["checks"][0]["actual"] == 2
    assert trace_payload["calls"][0]["request"]["input"] == '{"text":"Fly"}'
    assert artifact["llm_trace"]["case_count"] == 1
