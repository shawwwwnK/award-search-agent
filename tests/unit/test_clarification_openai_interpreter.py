"""One-way OpenAI clarification receiver adapter tests."""

from types import SimpleNamespace
from typing import cast

from openai import OpenAI

from award_agent.clarification.interpreter import ClarificationAnswerInterpreterInput
from award_agent.clarification.openai_interpreter import (
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationInterpreterConfig,
    _ClarificationAnswerWireOutput,
)


class _Responses:
    def __init__(self, output: object | Exception) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return SimpleNamespace(output_parsed=self.output, usage=None)


class _Client:
    def __init__(self, output: object | Exception) -> None:
        self.responses = _Responses(output)


def _input() -> ClarificationAnswerInterpreterInput:
    return ClarificationAnswerInterpreterInput(
        message_id="m1", text="Leave October 6 and return October 15", ordered_requirements=()
    )


def _wire() -> _ClarificationAnswerWireOutput:
    return _ClarificationAnswerWireOutput.model_validate(
        {
            "discourse_act": "answer",
            "location_facts": [],
            "traveler_facts": [],
            "literal_interval_facts": [
                {
                    "fact_id": "departure",
                    "quote": "October 6",
                    "occurrence": 0,
                    "target": "departure_window",
                    "start_year": None,
                    "start_month": 10,
                    "start_day": 6,
                    "end_year": None,
                    "end_month": None,
                    "end_day": None,
                    "approximate": False,
                }
            ],
            "recurring_interval_facts": [],
            "offset_interval_facts": [],
            "unresolved_fragments": [],
            "one_way_scope_notices": [
                {"quote": "return October 15", "occurrence": 0, "kind": "return_or_duration"}
            ],
        }
    )


def test_adapter_emits_departure_and_grounded_return_scope_notice() -> None:
    client = _Client(_wire())
    interpreter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"), client=cast(OpenAI, client)
    )
    result = interpreter.interpret(_input())
    assert not hasattr(result, "code")
    assert len(result.facts) == 1
    assert result.facts[0].target.value == "departure_window"
    assert result.one_way_scope_notices[0].kind.value == "return_or_duration"
    request = client.responses.calls[0]
    assert request["store"] is False
    assert "one_way_scope_notice" in request["instructions"]


def test_adapter_returns_pending_on_provider_schema_rejection() -> None:
    interpreter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"),
        client=cast(OpenAI, _Client(ValueError("Invalid schema for response_format"))),
    )
    result = interpreter.interpret(_input())
    assert result.code == "receiver_provider_schema_unavailable"


def test_wire_schema_rejects_removed_duration_array() -> None:
    payload = _wire().model_dump(mode="python")
    payload["duration_facts"] = []
    try:
        _ClarificationAnswerWireOutput.model_validate(payload)
    except ValueError:
        pass
    else:  # pragma: no cover - explicit regression guard
        raise AssertionError("one-way receiver wire schema accepted duration_facts")
