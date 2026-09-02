"""Narrow interface around model-dependent intent extraction."""

from typing import Protocol

from award_agent.domain import CoarseIntentExtraction, TemporalRelationGraph
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    StructuredValidationErrorView,
    TemporalInterpretationInput,
    TemporalResolutionResult,
)


class IntentExtractor(Protocol):
    def extract(self, model_input: CoarseExtractionInput) -> CoarseIntentExtraction: ...

    def repair_extract(
        self, model_input: CoarseExtractionRepairInput
    ) -> CoarseIntentExtraction: ...


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
