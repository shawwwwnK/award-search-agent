"""Narrow interface around model-dependent intent extraction."""

from typing import Protocol

from award_agent.domain import CoarseIntentExtraction, TemporalRelationGraph
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
    StructuredValidationErrorView,
    TemporalInterpretationInput,
    TemporalResolutionResult,
    TemporalSelectorInput,
    TemporalSelectorOutput,
)


class IntentExtractor(Protocol):
    def extract(self, model_input: CoarseExtractionInput) -> CoarseIntentExtraction: ...

    def repair_extract(
        self, model_input: CoarseExtractionRepairInput
    ) -> CoarseIntentExtraction: ...


class NonTemporalIntentExtractor(Protocol):
    """Compiler-route model boundary, deliberately unable to author temporal data."""

    def extract_non_temporal(
        self, model_input: NonTemporalExtractionInput
    ) -> NonTemporalIntentExtraction: ...


class TemporalResolver(Protocol):
    def resolve_dates(
        self,
        model_input: TemporalInterpretationInput,
    ) -> TemporalResolutionResult: ...

    def repair_dates(
        self,
        model_input: TemporalInterpretationInput,
        rejected_output: TemporalRelationGraph,
        validation_errors: list[StructuredValidationErrorView],
    ) -> TemporalRelationGraph: ...


class TemporalCandidateSelector(Protocol):
    """Narrow optional model boundary for choosing pre-built temporal candidates."""

    def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput: ...
