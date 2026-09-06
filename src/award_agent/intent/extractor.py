"""Narrow model boundaries for selector-only request understanding."""

from typing import Protocol

from award_agent.intent.model_views import (
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
    TemporalSelectorInput,
    TemporalSelectorOutput,
)


class NonTemporalIntentExtractor(Protocol):
    """Extract only non-temporal request semantics."""

    def extract_non_temporal(
        self, model_input: NonTemporalExtractionInput
    ) -> NonTemporalIntentExtraction: ...


class TemporalCandidateSelector(Protocol):
    """Choose supplied opaque temporal candidates; never author temporal facts."""

    def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput: ...
