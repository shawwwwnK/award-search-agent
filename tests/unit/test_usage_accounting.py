"""Characterize adapter-owned usage accounting before sharing its arithmetic."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Protocol, cast

import pytest
from openai import OpenAI
from test_clarification_composer import _requirements
from test_clarification_openai_interpreter import _input as interpreter_input
from test_clarification_openai_interpreter import _wire
from test_gateway_generator import _input as gateway_input

from award_agent.clarification.composer import ClarificationPromptComposerInput
from award_agent.clarification.issues import derive_clarification_issues
from award_agent.clarification.openai_composer import (
    OpenAIClarificationComposerConfig,
    OpenAIClarificationPromptComposer,
    _ClarificationPromptComposerWireOutput,
)
from award_agent.clarification.openai_interpreter import (
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationInterpreterConfig,
)
from award_agent.observability.usage import aggregate_usage, token_record
from award_agent.search_planning.airport_selector import (
    AirportSelectorModelInput,
    OpenAIAirportSelector,
    OpenAIAirportSelectorConfig,
)
from award_agent.search_planning.gateway_generator import (
    GatewayCandidateProposal,
    OpenAIGatewayGenerator,
    OpenAIGatewayGeneratorConfig,
)


class _UsageAdapter(Protocol):
    def take_usage(self) -> dict[str, int] | None: ...

    def reset_capture(self) -> None: ...


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"input_tokens": 2, "output_tokens": 3},
            {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
        ),
        (
            {"input_tokens": True, "output_tokens": -4, "total_tokens": "bad"},
            {"input_tokens": True, "output_tokens": -4, "total_tokens": -3},
        ),
        (
            {"input_tokens": 2, "output_tokens": 3, "total_tokens": 9},
            {"input_tokens": 2, "output_tokens": 3, "total_tokens": 9},
        ),
        ({"input_tokens": "2", "output_tokens": 3}, None),
        ({"input_tokens": 2}, None),
    ],
)
def test_token_record_preserves_existing_int_and_fallback_rules(
    payload: dict[str, object], expected: dict[str, int] | None
) -> None:
    assert token_record(payload) == expected


def test_aggregate_usage_keeps_attempts_separate_from_records() -> None:
    records = [{"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}]
    assert aggregate_usage(records, 3) == {
        "calls": 3,
        "captured_calls": 1,
        "missing_calls": 2,
        "input_tokens": 2,
        "output_tokens": 3,
        "total_tokens": 5,
    }
    assert aggregate_usage([], 0) == {
        "calls": 0,
        "captured_calls": 0,
        "missing_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


class _UsageObject:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def model_dump(self, *, mode: str) -> object:
        assert mode == "json"
        return self.payload


class _Responses:
    def __init__(self, output: object, usages: list[object]) -> None:
        self.output, self.usages = output, usages

    def parse(self, **kwargs: object) -> object:
        usage = self.usages.pop(0)
        if isinstance(usage, Exception):
            raise usage
        return SimpleNamespace(output_parsed=self.output, usage=usage)


def _client(output: object, usages: list[object]) -> OpenAI:
    return cast(OpenAI, SimpleNamespace(responses=_Responses(output, usages)))


def _composer_input() -> ClarificationPromptComposerInput:
    requirements = _requirements()
    return ClarificationPromptComposerInput(
        requirements=requirements, issues=derive_clarification_issues(requirements)
    )


def _composer_output() -> _ClarificationPromptComposerWireOutput:
    return _ClarificationPromptComposerWireOutput.model_validate(
        {
            "question_items": [
                {
                    "requirement_id": "departure",
                    "issue_ids": ["departure:missing"],
                    "question": "When?",
                },
                {
                    "requirement_id": "travelers",
                    "issue_ids": ["travelers:missing"],
                    "question": "How many?",
                },
            ]
        }
    )


def _airport_input() -> AirportSelectorModelInput:
    return AirportSelectorModelInput.model_validate(
        {
            "entity_id": "geonames:2",
            "entity_label": "Test City",
            "entity_kind": "city",
            "category": "city_metropolitan",
            "category_basis": "entity_kind",
            "country_code": "US",
            "applicable_cap": 2,
        }
    )


def _adapters(usages: list[object]) -> list[tuple[_UsageAdapter, Any]]:
    from test_airport_selector import _proposal

    empty_gateway = GatewayCandidateProposal(
        endpoint_market_assessments=(),
        origin_access_gateways=(),
        destination_access_gateways=(),
        intermediate_hubs=(),
    )
    interpreter = OpenAIClarificationAnswerInterpreter(
        OpenAIClarificationInterpreterConfig(model="x"), client=_client(_wire(), usages.copy())
    )
    composer = OpenAIClarificationPromptComposer(
        OpenAIClarificationComposerConfig(model="x"),
        client=_client(_composer_output(), usages.copy()),
    )
    airport = OpenAIAirportSelector(
        OpenAIAirportSelectorConfig(model="x"),
        client=_client(_proposal("TST"), usages.copy()),
    )
    gateway = OpenAIGatewayGenerator(
        OpenAIGatewayGeneratorConfig(model="x"),
        client=_client(empty_gateway, usages.copy()),
    )
    return [
        (interpreter, lambda: interpreter.interpret(interpreter_input())),
        (composer, lambda: composer.compose(_composer_input())),
        (airport, lambda: airport.propose(_airport_input())),
        (gateway, lambda: gateway.propose(gateway_input())),
    ]


@pytest.mark.parametrize("adapter_index", range(4))
def test_adapters_aggregate_attempts_and_drain_usage(adapter_index: int) -> None:
    usages = [
        {"input_tokens": 2, "output_tokens": 3},
        _UsageObject({"input_tokens": True, "output_tokens": -4, "total_tokens": 9}),
        {"input_tokens": "bad", "output_tokens": 4},
    ]
    adapter, call = _adapters(usages)[adapter_index]
    assert adapter.take_usage() is None
    for _ in usages:
        call()
    assert adapter.take_usage() == {
        "calls": 3,
        "captured_calls": 2,
        "missing_calls": 1,
        "input_tokens": 3,
        "output_tokens": -1,
        "total_tokens": 14,
    }
    assert adapter.take_usage() is None


@pytest.mark.parametrize("adapter_index", range(4))
def test_adapters_keep_failed_calls_and_separate_reset_state(adapter_index: int) -> None:
    adapter, call = _adapters([RuntimeError("provider unavailable"), None])[adapter_index]
    if adapter_index == 0:
        call()  # Interpreter converts the SDK error to a pending result.
    else:
        with pytest.raises(Exception, match="failed"):
            call()
    call()
    # The interpreter's failed parse triggers its existing bounded repair.
    expected_calls = 4 if adapter_index == 0 else 2
    assert adapter.take_usage() == {
        "calls": expected_calls,
        "captured_calls": 0,
        "missing_calls": expected_calls,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    assert adapter.take_usage() is None
    reset_adapter, reset_call = _adapters([{"input_tokens": 1, "output_tokens": 2}])[adapter_index]
    reset_call()
    reset_adapter.reset_capture()
    assert reset_adapter.take_usage() is None
    if adapter_index < 2:
        reset_adapter, reset_call = _adapters([{"input_tokens": 1, "output_tokens": 2}])[
            adapter_index
        ]
        reset_call()
        cast(Any, reset_adapter).reset_usage()
        assert reset_adapter.take_usage() is None
    assert adapter.take_usage() is None


@pytest.mark.parametrize("adapter_index", range(4))
def test_missing_model_dump_guard_stays_adapter_local(adapter_index: int) -> None:
    adapter, call = _adapters([object()])[adapter_index]
    if adapter_index < 2:
        call()
        assert adapter.take_usage() == {
            "calls": 1,
            "captured_calls": 0,
            "missing_calls": 1,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
    else:
        with pytest.raises(AttributeError, match="model_dump"):
            call()
        assert adapter.take_usage() == {
            "calls": 1,
            "captured_calls": 0,
            "missing_calls": 1,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }


@pytest.mark.parametrize("adapter_index", range(4))
def test_nonmapping_dump_error_propagates(adapter_index: int) -> None:
    adapter, call = _adapters([_UsageObject(None)])[adapter_index]
    with pytest.raises(AttributeError, match="get"):
        call()
    assert adapter.take_usage() == {
        "calls": 1,
        "captured_calls": 0,
        "missing_calls": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


@pytest.mark.parametrize("adapter_index", range(4))
def test_dump_failure_propagates_after_attempt(adapter_index: int) -> None:
    class _BrokenUsage:
        def model_dump(self, *, mode: str) -> object:
            raise ValueError("dump failed")

    adapter, call = _adapters([_BrokenUsage()])[adapter_index]
    with pytest.raises(ValueError, match="dump failed"):
        call()
    assert adapter.take_usage() == {
        "calls": 1,
        "captured_calls": 0,
        "missing_calls": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


@pytest.mark.parametrize("adapter_index", range(4))
def test_serialization_failure_does_not_count_as_an_attempt(
    adapter_index: int, monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, call = _adapters([{"input_tokens": 2, "output_tokens": 3}])[adapter_index]
    failure = TypeError("injected request serialization failure")

    def fail(*_args: object, **_kwargs: object) -> str:
        raise failure

    with monkeypatch.context() as patch:
        patch.setattr(json, "dumps", fail)
        with pytest.raises(TypeError) as caught:
            call()
        assert caught.value is failure
    assert adapter.take_usage() is None
    call()  # The unused fake response still remains available.
    usage = adapter.take_usage()
    assert usage is not None and usage["calls"] == usage["captured_calls"] == 1


@pytest.mark.parametrize("adapter_index", range(4))
def test_wrong_parsed_output_retains_captured_usage(adapter_index: int) -> None:
    adapter, call = _adapters([
        {"input_tokens": 2, "output_tokens": 3},
        {"input_tokens": 2, "output_tokens": 3},
    ])[adapter_index]
    cast(Any, adapter)._client.responses.output = object()
    if adapter_index == 0:
        call()  # Interpreter attempts one repair, then returns unavailable.
    else:
        with pytest.raises(Exception, match="unexpected"):
            call()
    calls = 2 if adapter_index == 0 else 1
    assert adapter.take_usage() == {
        "calls": calls,
        "captured_calls": calls,
        "missing_calls": 0,
        "input_tokens": 2 * calls,
        "output_tokens": 3 * calls,
        "total_tokens": 5 * calls,
    }
