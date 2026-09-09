from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from award_agent.clarification.interpreter import ClarificationAnswerInterpreterInput
from award_agent.clarification.openai_interpreter import (
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationInterpretationError,
    OpenAIClarificationInterpreterConfig,
    _ClarificationAnswerWireOutput,
)
from award_agent.domain import (
    BlockingRequirement,
    BlockingRequirementKind,
    EffectiveField,
    LocationAmendment,
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


def _input(text: str = "SFO and two") -> ClarificationAnswerInterpreterInput:
    return ClarificationAnswerInterpreterInput(
        message_id="answer-1",
        text=text,
        requirements=(
            BlockingRequirement(
                requirement_id="origin",
                kind=BlockingRequirementKind.ORIGIN,
                field=EffectiveField.ORIGIN,
            ),
            BlockingRequirement(
                requirement_id="travelers",
                kind=BlockingRequirementKind.TRAVELERS,
                field=EffectiveField.TRAVELERS,
            ),
        ),
    )


def test_openai_adapter_uses_fixed_wire_schema_disables_storage_and_excludes_context() -> None:
    wire = _ClarificationAnswerWireOutput.model_validate(
        {
            "location_amendments": [
                {
                    "quote": "SFO",
                    "occurrence": 0,
                    "requirement_ids": ["origin"],
                    "is_correction": False,
                    "target": "origin",
                    "kind": "airport",
                    "value_quote": "SFO",
                }
            ],
            "traveler_amendments": [
                {
                    "quote": "two",
                    "occurrence": 0,
                    "requirement_ids": ["travelers"],
                    "is_correction": False,
                    "target": "travelers",
                    "travelers": 2,
                }
            ],
            "temporal_amendments": [],
            "rejected_fragments": [],
        }
    )
    client = _Client(wire)
    adapter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="gpt-5.6-luna"), client=client  # type: ignore[arg-type]
    )

    result = adapter.interpret(_input())

    assert [item.target.value for item in result.amendments] == ["origin", "travelers"]
    assert isinstance(result.amendments[0], LocationAmendment)
    assert result.amendments[0].locations[0].value == "SFO"
    call = client.responses.calls[0]
    assert call["model"] == "gpt-5.6-luna"
    assert call["store"] is False
    assert call["text_format"] is _ClarificationAnswerWireOutput
    payload = json.loads(str(call["input"]))
    assert set(payload) == {"message_id", "text", "requirements"}
    assert "reference_date" not in str(payload)
    assert "timezone" not in str(payload)


def test_openai_adapter_optionally_captures_private_raw_call_trace() -> None:
    wire = _ClarificationAnswerWireOutput.model_validate(
        {
            "location_amendments": [],
            "traveler_amendments": [],
            "temporal_amendments": [],
            "rejected_fragments": [],
        }
    )
    adapter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="model"),
        client=_Client(wire),  # type: ignore[arg-type]
        capture_llm_io=True,
    )

    adapter.interpret(_input())

    traces = adapter.take_call_traces()
    assert len(traces) == 1
    assert traces[0]["request"]["store"] is False
    assert json.loads(traces[0]["request"]["input"])["text"] == "SFO and two"
    assert adapter.take_call_traces() == []


def test_taking_usage_does_not_discard_private_call_traces() -> None:
    wire = _ClarificationAnswerWireOutput.model_validate(
        {
            "location_amendments": [],
            "traveler_amendments": [],
            "temporal_amendments": [],
            "rejected_fragments": [],
        }
    )
    adapter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="model"),
        client=_Client(wire),  # type: ignore[arg-type]
        capture_llm_io=True,
    )

    adapter.interpret(_input())

    assert adapter.take_usage() is None
    assert len(adapter.take_call_traces()) == 1


def test_openai_adapter_fails_closed_for_api_error_wrong_type_and_unmatched_quote() -> None:
    adapter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="model"),
        client=_Client(RuntimeError("offline")),  # type: ignore[arg-type]
    )
    with pytest.raises(OpenAIClarificationInterpretationError, match="failed"):
        adapter.interpret(_input())

    wrong_type = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="model"), client=_Client(object())  # type: ignore[arg-type]
    )
    with pytest.raises(OpenAIClarificationInterpretationError, match="unexpected"):
        wrong_type.interpret(_input())

    unmatched = _ClarificationAnswerWireOutput.model_validate(
        {
            "location_amendments": [],
            "traveler_amendments": [],
            "temporal_amendments": [],
            "rejected_fragments": [
                {"quote": "missing", "occurrence": 0, "reason": "invalid"}
            ],
        }
    )
    invalid = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="model"), client=_Client(unmatched)  # type: ignore[arg-type]
    )
    with pytest.raises(OpenAIClarificationInterpretationError, match="quote occurrence"):
        invalid.interpret(_input())
