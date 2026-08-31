from datetime import date
from types import SimpleNamespace
from typing import cast

import pytest
from openai import OpenAI

from award_agent.domain import IntentExtraction, RawRequest, RequestContext
from award_agent.intent.openai_extractor import IntentExtractionError, OpenAIIntentExtractor


class FakeResponses:
    def __init__(self, parsed: IntentExtraction | None) -> None:
        self.parsed = parsed
        self.kwargs: dict[str, object] = {}

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(output_parsed=self.parsed)


class FakeClient:
    def __init__(self, parsed: IntentExtraction | None) -> None:
        self.responses = FakeResponses(parsed)


def test_openai_extractor_uses_structured_output_without_storing_response() -> None:
    client = FakeClient(IntentExtraction(travelers=2))
    extractor = OpenAIIntentExtractor(model="test-model", client=cast(OpenAI, client))
    request = RawRequest(
        text="Two people want to travel.",
        context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
    )

    result = extractor.extract(request)

    assert result.travelers == 2
    assert client.responses.kwargs["text_format"] is IntentExtraction
    assert client.responses.kwargs["store"] is False


def test_openai_extractor_fails_explicitly_when_output_is_missing() -> None:
    client = FakeClient(None)
    extractor = OpenAIIntentExtractor(model="test-model", client=cast(OpenAI, client))
    request = RawRequest(
        text="Travel somewhere.",
        context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
    )

    with pytest.raises(IntentExtractionError, match="no parsed intent"):
        extractor.extract(request)
