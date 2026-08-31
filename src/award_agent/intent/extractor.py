"""Narrow interface around model-dependent intent extraction."""

from typing import Protocol

from award_agent.domain import (
    CoarseIntentExtraction,
    DateResolutionProposal,
    RawRequest,
    ResolvedTemporalAnchor,
)


class IntentExtractor(Protocol):
    def extract(self, request: RawRequest) -> CoarseIntentExtraction: ...


class TemporalResolver(Protocol):
    def resolve_dates(
        self,
        request: RawRequest,
        extraction: CoarseIntentExtraction,
        resolved_anchors: list[ResolvedTemporalAnchor],
    ) -> DateResolutionProposal: ...
