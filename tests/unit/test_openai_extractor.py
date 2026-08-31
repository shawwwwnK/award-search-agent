import json
from datetime import date
from types import SimpleNamespace
from typing import cast

import pytest
from openai import OpenAI

from award_agent.domain import (
    CoarseIntentExtraction,
    DateResolutionProposal,
    MonthAnchor,
    RawRequest,
    RequestContext,
    ResolvedTemporalAnchor,
    TemporalTarget,
)
from award_agent.intent.openai_extractor import (
    DateResolutionError,
    IntentExtractionError,
    OpenAIExtractorConfig,
    OpenAIIntentExtractor,
)


class FakeResponses:
    def __init__(self, outputs: list[object | None]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.outputs.pop(0))


class FakeClient:
    def __init__(self, outputs: list[object | None]) -> None:
        self.responses = FakeResponses(outputs)


def request() -> RawRequest:
    return RawRequest(
        text="Travel in May.",
        context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
    )


def test_openai_extractor_uses_coarse_structured_output_without_storing_response() -> None:
    client = FakeClient([CoarseIntentExtraction(travelers=2)])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    result = extractor.extract(request())

    call = client.responses.calls[0]
    assert result.travelers == 2
    assert call["model"] == "test-model"
    assert "preserve" in str(call["instructions"]).casefold()
    assert "normalized semantic-name candidate" in str(call["instructions"]).casefold()
    assert "never expand a city into airports" in str(call["instructions"]).casefold()
    assert call["text_format"] is CoarseIntentExtraction
    assert call["store"] is False


def test_openai_resolver_receives_coarse_extraction_and_resolved_anchors() -> None:
    proposal = DateResolutionProposal()
    client = FakeClient([proposal])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )
    extraction = CoarseIntentExtraction(
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="month_1",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="May",
                month=5,
            )
        ]
    )
    anchors = [
        ResolvedTemporalAnchor(
            anchor=extraction.date_anchors[0],
            start=date(2027, 5, 1),
            end=date(2027, 5, 31),
            source="calendar",
            source_detail="test",
        )
    ]

    result = extractor.resolve_dates(request(), extraction, anchors)

    call = client.responses.calls[0]
    payload = json.loads(str(call["input"]))
    assert result is proposal
    assert payload["resolved_anchors"][0]["start"] == "2027-05-01"
    assert call["text_format"] is DateResolutionProposal
    assert call["store"] is False


def test_openai_resolver_instructions_define_holiday_windows() -> None:
    client = FakeClient([DateResolutionProposal()])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    extractor.resolve_dates(request(), CoarseIntentExtraction(), [])

    instructions = str(client.responses.calls[0]["instructions"])
    assert "Labor Day weekend Friday through Monday" in instructions
    assert "2026-09-04 through 2026-09-07" in instructions
    assert '"Christmas weekend"' in instructions
    assert "Thursday 2026-12-24 through Sunday 2026-12-27" in instructions
    assert "2026-12-24 through 2026-12-26" in instructions
    assert 'Never apply the "over Christmas" rule' in instructions
    assert "Deterministic code will enforce" in instructions


def test_openai_extractor_fails_explicitly_when_output_is_missing() -> None:
    client = FakeClient([None])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    with pytest.raises(IntentExtractionError, match="no parsed coarse intent"):
        extractor.extract(request())


def test_openai_resolver_fails_explicitly_when_output_is_missing() -> None:
    client = FakeClient([None])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model="test-model"),
        client=cast(OpenAI, client),
    )

    with pytest.raises(DateResolutionError, match="no parsed date-resolution"):
        extractor.resolve_dates(request(), CoarseIntentExtraction(), [])


@pytest.mark.parametrize("model", ["gpt-4o-mini", "gpt-5-mini", "intent-eval-candidate"])
def test_model_candidates_are_forwarded_without_environment_state(model: str) -> None:
    client = FakeClient([CoarseIntentExtraction()])
    extractor = OpenAIIntentExtractor(
        config=OpenAIExtractorConfig(model=model),
        client=cast(OpenAI, client),
    )

    extractor.extract(request())

    assert extractor.config.model == model
    assert client.responses.calls[0]["model"] == model


def test_model_config_rejects_blank_model() -> None:
    with pytest.raises(ValueError, match="model must not be empty"):
        OpenAIExtractorConfig(model="  ")
