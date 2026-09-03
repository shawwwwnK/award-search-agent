import json
from datetime import date
from types import SimpleNamespace
from typing import cast

from openai import OpenAI

from award_agent.domain import RawRequest, RequestContext, RequestUnderstandingResult
from award_agent.experiments.one_pass_intent import OnePassIntentExperiment


class FakeResponses:
    def __init__(self, parsed: RequestUnderstandingResult) -> None:
        self.parsed = parsed
        self.kwargs: dict[str, object] = {}

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        usage = SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
            }
        )
        return SimpleNamespace(output_parsed=self.parsed, usage=usage)


class FakeClient:
    def __init__(self, parsed: RequestUnderstandingResult) -> None:
        self.responses = FakeResponses(parsed)


def test_one_pass_experiment_requests_final_contract_once_without_storage() -> None:
    parsed = RequestUnderstandingResult.model_construct()
    client = FakeClient(parsed)
    experiment = OnePassIntentExperiment("test-model", cast(OpenAI, client))
    request = RawRequest(
        text="Fly from Seattle to Tokyo in October.",
        context=RequestContext(reference_date=date(2026, 8, 31), timezone="UTC"),
    )

    result, usage = experiment.run(request)

    assert result is parsed
    assert usage == {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
    assert client.responses.kwargs["model"] == "test-model"
    assert client.responses.kwargs["text_format"] is RequestUnderstandingResult
    assert client.responses.kwargs["store"] is False


def test_one_pass_experiment_captures_model_call_when_enabled() -> None:
    parsed = RequestUnderstandingResult.model_construct()
    client = FakeClient(parsed)
    experiment = OnePassIntentExperiment(
        "test-model",
        cast(OpenAI, client),
        capture_llm_io=True,
    )
    request = RawRequest(
        text="Fly from Seattle to Tokyo in October.",
        context=RequestContext(reference_date=date(2026, 8, 31), timezone="UTC"),
    )

    experiment.run(request)

    trace = experiment.take_call_traces()[0]
    request_payload = trace["request"]
    assert trace["stage"] == "one_pass"
    assert isinstance(request_payload, dict)
    assert request_payload["model"] == "test-model"
    assert json.loads(str(request_payload["input"])) == {
        "text": "Fly from Seattle to Tokyo in October.",
        "context": {"reference_date": "2026-08-31", "timezone": "UTC"},
    }
    assert trace["parsed_output"] == {"repair_trace": None}
    assert experiment.take_call_traces() == []
