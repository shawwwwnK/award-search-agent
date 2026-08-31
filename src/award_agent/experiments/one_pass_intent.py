"""Naive one-model-call request-understanding experiment."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from award_agent.domain import RawRequest, RequestUnderstandingResult

_INSTRUCTIONS = """Convert the travel request directly into the supplied final request-understanding schema in one pass.

Use the supplied reference date and timezone to resolve dates. Produce inclusive departure and
return windows when the request supports them. Preserve missing information as unknowns and
contradictions as conflicts. Ask at most one focused clarification question using the final
clarification object. Do not invent traveler counts, cabins, locations, dates, flexibility, or
constraints. Do not expand cities into airports. Do not call providers or create a search plan.
Copy the raw request and context into the final parsed request. Use null or empty collections for
schema fields that are not supported by the request.
"""


class OnePassIntentError(RuntimeError):
    """Raised when the naive one-pass experiment cannot produce the final contract."""


class OnePassIntentExperiment:
    """Directly ask one model call for the production workflow's final output type."""

    def __init__(self, model: str, client: OpenAI | None = None) -> None:
        if not model.strip():
            raise ValueError("model must not be empty")
        self.model = model
        self._client = client or OpenAI()

    def run(
        self, request: RawRequest
    ) -> tuple[RequestUnderstandingResult, dict[str, Any] | None]:
        payload = json.dumps(request.model_dump(mode="json"), separators=(",", ":"))
        try:
            response = self._client.responses.parse(
                model=self.model,
                instructions=_INSTRUCTIONS,
                input=payload,
                text_format=RequestUnderstandingResult,
                store=False,
            )
        except Exception as exc:
            raise OnePassIntentError(
                f"one-pass intent generation failed: {type(exc).__name__}: {exc}"
            ) from exc
        parsed = response.output_parsed
        if parsed is None:
            raise OnePassIntentError("OpenAI returned no parsed one-pass result")
        if not isinstance(parsed, RequestUnderstandingResult):
            raise OnePassIntentError("OpenAI returned an unexpected one-pass output type")
        usage = getattr(response, "usage", None)
        usage_payload = usage.model_dump(mode="json") if usage is not None else None
        return parsed, usage_payload
