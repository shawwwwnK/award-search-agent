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
from award_agent.domain import BlockingRequirement, BlockingRequirementKind, EffectiveField


class _Responses:
    def __init__(self, output: object | Exception) -> None:
        self.output, self.calls = output, []

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
            "facts": [
                {
                    "fact_id": "d",
                    "quote": "mid october",
                    "occurrence": 0,
                    "operation": "set",
                    "target": "departure_window",
                    "requirement_ids": ["departure"],
                    "location_kind": None,
                    "location_value": None,
                    "travelers": None,
                    "temporal": {
                        "kind": "month_portion",
                        "year": None,
                        "month": 10,
                        "day": None,
                        "portion": "mid",
                        "weekday": None,
                        "relation": None,
                        "quantity": None,
                        "unit": None,
                        "approximate": False,
                    },
                },
                {
                    "fact_id": "n",
                    "quote": "about 12 days",
                    "occurrence": 0,
                    "operation": "set",
                    "target": "duration",
                    "requirement_ids": ["return"],
                    "location_kind": None,
                    "location_value": None,
                    "travelers": None,
                    "temporal": {
                        "kind": "duration",
                        "year": None,
                        "month": None,
                        "day": None,
                        "portion": None,
                        "weekday": None,
                        "relation": None,
                        "quantity": 12,
                        "unit": "day",
                        "approximate": True,
                    },
                },
            ],
            "unresolved_fragments": [],
        }
    )


def test_adapter_sends_least_authority_input_and_converts_exact_spans() -> None:
    client = _Client(_wire())
    result = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="gpt-5.6-luna"), client=client
    ).interpret(_input())  # type: ignore[arg-type]
    assert [item.span.text for item in result.facts] == ["mid october", "about 12 days"]
    call = client.responses.calls[0]
    assert call["store"] is False
    payload = json.loads(str(call["input"]))
    assert set(payload) == {
        "message_id",
        "text",
        "ordered_requirements",
        "correction_eligible_targets",
        "temporal_affordance_catalog_version",
    }
    assert "reference_date" not in str(payload)
    assert "timezone" not in str(payload)


def test_adapter_fails_closed_for_api_error_and_unmatched_quote() -> None:
    with pytest.raises(OpenAIClarificationInterpretationError, match="failed"):
        OpenAIClarificationAnswerInterpreter(
            OpenAIClarificationInterpreterConfig(model="x"), client=_Client(RuntimeError("offline"))
        ).interpret(_input())  # type: ignore[arg-type]
    bad = _wire().model_copy(
        update={"facts": (_wire().facts[0].model_copy(update={"quote": "missing"}),)}
    )
    with pytest.raises(OpenAIClarificationInterpretationError, match="occurrence"):
        OpenAIClarificationAnswerInterpreter(
            OpenAIClarificationInterpreterConfig(model="x"), client=_Client(bad)
        ).interpret(_input())  # type: ignore[arg-type]
