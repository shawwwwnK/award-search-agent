from types import SimpleNamespace

import pytest

from award_agent.intent.model_views import (
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
    TemporalSelectorInput,
    TemporalSelectorOutput,
)
from award_agent.intent.openai_extractor import (
    NonTemporalExtractionError,
    OpenAIExtractorConfig,
    OpenAIIntentExtractor,
    TemporalSelectionError,
)


class _Responses:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.outputs.pop(0), usage=None)


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.responses = _Responses(outputs)


def test_adapter_uses_strict_non_temporal_schema_and_disables_response_storage() -> None:
    client = _Client([NonTemporalIntentExtraction(travelers=1)])
    adapter = OpenAIIntentExtractor(OpenAIExtractorConfig(model="pass-one"), client=client)  # type: ignore[arg-type]

    output = adapter.extract_non_temporal(NonTemporalExtractionInput(request_text="I can go."))

    assert output.travelers == 1
    call = client.responses.calls[0]
    assert call["model"] == "pass-one"
    assert call["store"] is False
    assert call["text_format"] is NonTemporalIntentExtraction


def test_adapter_selects_opaque_candidates_and_rejects_wrong_output_type() -> None:
    selector_input = TemporalSelectorInput()
    client = _Client([TemporalSelectorOutput(selected_candidates=[])])
    adapter = OpenAIIntentExtractor(OpenAIExtractorConfig(model="selector"), client=client)  # type: ignore[arg-type]

    assert adapter.select_candidates(selector_input).selected_candidates == []
    # Empty groups are deterministic and make no provider call.
    assert client.responses.calls == []

    with pytest.raises(NonTemporalExtractionError):
        adapter.extract_non_temporal(NonTemporalExtractionInput(request_text="request"))


def test_selector_rejects_unexpected_structured_output() -> None:
    from award_agent.intent.model_views import TemporalSelectorCandidate, TemporalSelectorGroup

    client = _Client([NonTemporalIntentExtraction()])
    adapter = OpenAIIntentExtractor(OpenAIExtractorConfig(model="selector"), client=client)  # type: ignore[arg-type]
    selector_input = TemporalSelectorInput(
        candidate_groups=(
            TemporalSelectorGroup(
                handle="g0",
                candidates=(
                    TemporalSelectorCandidate(
                        handle="c0", summary="choice", covers=(), requires=(), produces=()
                    ),
                ),
            ),
        )
    )

    with pytest.raises(TemporalSelectionError):
        adapter.select_candidates(selector_input)
