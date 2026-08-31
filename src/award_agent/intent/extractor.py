"""Narrow interface around model-dependent intent extraction."""

from typing import Protocol

from award_agent.domain import IntentExtraction, RawRequest


class IntentExtractor(Protocol):
    def extract(self, request: RawRequest) -> IntentExtraction: ...
