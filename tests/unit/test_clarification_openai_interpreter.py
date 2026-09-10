from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from openai import OpenAI

from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpreterInput,
    ClarificationCalendarProposalIssue,
    ClarificationInterpretationUnavailable,
    ClarificationRepairBudget,
)
from award_agent.clarification.openai_interpreter import (
    OPENAI_CLARIFICATION_INTERPRETER_ADAPTER_VERSION,
    OPENAI_CLARIFICATION_INTERPRETER_RESPONSE_SCHEMA_SHA256,
    OpenAIClarificationAdapterPreflightError,
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationInterpretationError,
    OpenAIClarificationInterpreterConfig,
    _ClarificationAnswerWireOutput,
    _convert_wire_output,
)
from award_agent.domain import BlockingRequirement, BlockingRequirementKind, EffectiveField


class _Responses:
    def __init__(
        self, output: object | Exception | list[object | Exception], usage: object | None = None
    ) -> None:
        self.output, self.usage = output, usage
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        output = self.output.pop(0) if isinstance(self.output, list) else self.output
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(output_parsed=output, usage=self.usage)


class _Client:
    def __init__(
        self, output: object | Exception | list[object | Exception], usage: object | None = None
    ) -> None:
        self.responses = _Responses(output, usage)


def _input() -> ClarificationAnswerInterpreterInput:
    return ClarificationAnswerInterpreterInput(
        message_id="a1",
        text="mid october and about 12 days",
        ordered_requirements=(
            BlockingRequirement(
                requirement_id="departure",
                kind=BlockingRequirementKind.DEPARTURE,
                field=EffectiveField.DEPARTURE,
            ),
            BlockingRequirement(
                requirement_id="return",
                kind=BlockingRequirementKind.RETURN_OR_DURATION,
                field=EffectiveField.RETURN_OR_DURATION,
            ),
        ),
    )


def _wire() -> _ClarificationAnswerWireOutput:
    return _ClarificationAnswerWireOutput.model_validate(
        {
            "discourse_act": "answer",
            "location_facts": [],
            "traveler_facts": [],
            "literal_interval_facts": [
                {
                    "fact_id": "d",
                    "quote": "mid october",
                    "occurrence": 0,
                    "target": "departure_window",
                    "start_year": None,
                    "start_month": 10,
                    "start_day": 11,
                    "end_year": None,
                    "end_month": 10,
                    "end_day": 20,
                    "approximate": False,
                }
            ],
            "recurring_interval_facts": [],
            "offset_interval_facts": [],
            "duration_facts": [
                {
                    "fact_id": "n",
                    "quote": "about 12 days",
                    "occurrence": 0,
                    "target": "duration",
                    "minimum_days": 11,
                    "maximum_days": 13,
                    "approximate": True,
                }
            ],
            "unresolved_fragments": [],
        }
    )


def test_adapter_sends_least_authority_input_and_converts_exact_spans() -> None:
    client = _Client(_wire())
    result = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="gpt-5.6-luna"), client=cast(OpenAI, client)
    ).interpret(_input())
    assert [item.span.text for item in result.facts] == ["mid october", "about 12 days"]
    call = client.responses.calls[0]
    assert call["store"] is False
    payload = json.loads(str(call["input"]))
    assert set(payload) == {
        "message_id",
        "text",
        "ordered_requirements",
        "correction_eligible_targets",
        "calendar_proposal_contract_version",
    }
    assert "reference_date" not in str(payload)
    assert "timezone" not in str(payload)
    schema = cast(Any, call["text_format"]).model_json_schema()
    fact_properties = schema["$defs"]["_WireLiteralIntervalFact"]["properties"]
    assert "operation" not in fact_properties
    assert "requirement_ids" not in fact_properties
    assert {"start_month", "start_day", "end_month", "end_day"} <= set(fact_properties)
    schema_text = json.dumps(schema)
    assert '"oneOf"' not in schema_text
    assert "CalendarCalculationOperation" not in schema_text


def test_adapter_returns_retryable_unavailable_for_api_error_and_unmatched_quote() -> None:
    unavailable = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"),
        client=cast(OpenAI, _Client(RuntimeError("offline"))),
    ).interpret(_input())
    assert isinstance(unavailable, ClarificationInterpretationUnavailable)
    assert unavailable.code == "receiver_repair_unavailable"
    assert unavailable.repair_attempted is True
    bad = _wire().model_copy(
        update={
            "literal_interval_facts": (
                _wire().literal_interval_facts[0].model_copy(update={"quote": "missing"}),
            )
        }
    )
    unmatched = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"), client=cast(OpenAI, _Client(bad))
    ).interpret(_input())
    assert isinstance(unmatched, ClarificationInterpretationUnavailable)
    assert unmatched.code == "receiver_repair_invalid"
    assert unmatched.repair_attempted is True


def test_provider_schema_rejection_is_adapter_preflight_not_model_repair() -> None:
    client = _Client(ValueError("Invalid schema for response_format"))
    interpreter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"), client=cast(OpenAI, client)
    )

    with pytest.raises(OpenAIClarificationAdapterPreflightError, match="response schema"):
        interpreter.interpret(_input())

    assert len(client.responses.calls) == 1
    assert interpreter.repair_budget_consumed() is False


def test_adapter_aggregates_attempted_and_usage_less_calls_without_last_response_loss() -> None:
    interpreter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"),
        client=cast(
            OpenAI, _Client(_wire(), {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8})
        ),
    )

    interpreter.interpret(_input())
    interpreter.interpret(_input())

    assert interpreter.take_usage() == {
        "calls": 2,
        "captured_calls": 2,
        "missing_calls": 0,
        "input_tokens": 6,
        "output_tokens": 10,
        "total_tokens": 16,
    }
    assert interpreter.take_usage() is None

    failed = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"),
        client=cast(OpenAI, _Client(RuntimeError("offline"))),
    )
    unavailable = failed.interpret(_input())
    assert isinstance(unavailable, ClarificationInterpretationUnavailable)
    assert failed.take_usage() == {
        "calls": 2,
        "captured_calls": 0,
        "missing_calls": 2,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def test_adapter_repairs_an_unavailable_structured_response_once_with_traceable_telemetry() -> None:
    interpreter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"),
        client=cast(
            OpenAI,
            _Client(
                [RuntimeError("temporary"), _wire()],
                {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8},
            ),
        ),
        capture_llm_io=True,
    )
    recovered = interpreter.interpret(_input())

    assert not isinstance(recovered, ClarificationInterpretationUnavailable)
    assert interpreter.repair_budget_consumed() is True
    assert interpreter.take_usage() == {
        "calls": 2,
        "captured_calls": 1,
        "missing_calls": 1,
        "input_tokens": 3,
        "output_tokens": 5,
        "total_tokens": 8,
    }
    traces = interpreter.take_call_traces()
    assert [item["stage"] for item in traces] == [
        "interpreter",
        "interpreter_repair",
    ]
    assert all(
        item["adapter"]
        == {
            "version": OPENAI_CLARIFICATION_INTERPRETER_ADAPTER_VERSION,
            "response_schema_sha256": OPENAI_CLARIFICATION_INTERPRETER_RESPONSE_SCHEMA_SHA256,
        }
        for item in traces
    )


def test_repair_budget_is_an_explicit_optional_receiver_capability() -> None:
    interpreter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"), client=cast(OpenAI, _Client(_wire()))
    )

    class PlainFake:
        pass

    assert isinstance(interpreter, ClarificationRepairBudget)
    assert not isinstance(PlainFake(), ClarificationRepairBudget)


def test_flat_recurring_and_offset_anchor_forms_convert_without_text_inference() -> None:
    input = ClarificationAnswerInterpreterInput(
        message_id="anchor-answer",
        text="Saturday then seven later",
        ordered_requirements=(),
    )
    recurring = _ClarificationAnswerWireOutput.model_validate(
        {
            "discourse_act": "answer",
            "location_facts": [],
            "traveler_facts": [],
            "literal_interval_facts": [],
            "offset_interval_facts": [],
            "duration_facts": [],
            "unresolved_fragments": [],
            "recurring_interval_facts": [
                {
                    "fact_id": "departure",
                    "quote": "Saturday",
                    "occurrence": 0,
                    "target": "departure_window",
                    "anchor_kind": "request_date",
                    "anchor_fact_id": None,
                    "anchor_edge": None,
                    "weekday": 5,
                    "inclusion": "on_or_after",
                    "cycles_after_anchor": 0,
                    "span_days": 1,
                    "approximate": False,
                }
            ],
        }
    )
    offset = _ClarificationAnswerWireOutput.model_validate(
        {
            **recurring.model_dump(mode="python"),
            "recurring_interval_facts": (),
            "offset_interval_facts": [
                {
                    "fact_id": "return",
                    "quote": "seven later",
                    "occurrence": 0,
                    "target": "return_window",
                    "anchor_kind": "prior_fact",
                    "anchor_fact_id": "departure",
                    "anchor_edge": "start",
                    "start_offset_days": 7,
                    "end_offset_days": None,
                    "approximate": False,
                }
            ],
        }
    )

    first = _convert_wire_output(recurring, input).facts[0]
    second = _convert_wire_output(offset, input).facts[0]
    assert first.calendar_operation is not None
    assert second.calendar_operation is not None
    assert first.calendar_operation.kind == "recurring_interval"
    assert second.calendar_operation.kind == "offset_interval"


@pytest.mark.parametrize(
    "update",
    [
        {
            "literal_interval_facts": [
                {
                    "fact_id": "x",
                    "quote": "mid october",
                    "occurrence": 0,
                    "target": "departure_window",
                    "start_year": None,
                    "start_month": 10,
                    "start_day": 11,
                    "end_year": None,
                    "end_month": 10,
                    "end_day": None,
                    "approximate": False,
                }
            ]
        },
        {
            "duration_facts": [
                {
                    "fact_id": "d",
                    "quote": "about 12 days",
                    "occurrence": 0,
                    "target": "departure_window",
                    "minimum_days": 11,
                    "maximum_days": 13,
                    "approximate": True,
                }
            ]
        },
    ],
)
def test_flat_invalid_shapes_are_converter_failures(update: dict[str, object]) -> None:
    wire = _ClarificationAnswerWireOutput.model_validate(
        {**_wire().model_dump(mode="python"), **update}
    )
    with pytest.raises(OpenAIClarificationInterpretationError):
        _convert_wire_output(wire, _input())


def test_adapter_repairs_only_requested_calendar_facts_with_separate_trace_and_usage() -> None:
    initial_wire = _wire()
    repair_wire = _wire().model_copy(
        update={
            "literal_interval_facts": (_wire().literal_interval_facts[0],),
            "duration_facts": (),
        }
    )
    interpreter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"),
        client=cast(
            OpenAI,
            _Client(
                [initial_wire, repair_wire],
                {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8},
            ),
        ),
        capture_llm_io=True,
    )
    initial = interpreter.interpret(_input())
    assert not isinstance(initial, ClarificationInterpretationUnavailable)

    repaired = interpreter.repair_calendar_proposals(
        _input(),
        facts=(initial.facts[0],),
        issues=(
            ClarificationCalendarProposalIssue(
                fact_id="d",
                code="calendar_plan_evaluation_failed",
                path=("facts", "d", "calendar_operation"),
                detail="invalid date",
            ),
        ),
    )

    assert not isinstance(repaired, ClarificationInterpretationUnavailable)
    assert [item.fact_id for item in repaired.facts] == ["d"]
    assert interpreter.take_usage() == {
        "calls": 2,
        "captured_calls": 2,
        "missing_calls": 0,
        "input_tokens": 6,
        "output_tokens": 10,
        "total_tokens": 16,
    }
    assert [item["stage"] for item in interpreter.take_call_traces()] == [
        "interpreter",
        "interpreter_repair",
    ]
