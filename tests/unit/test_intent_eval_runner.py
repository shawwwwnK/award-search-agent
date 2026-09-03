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
