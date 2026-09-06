"""OpenAI adapters for selector-only request understanding."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from award_agent.intent.model_views import (
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
    TemporalSelectorInput,
    TemporalSelectorOutput,
)
from award_agent.observability.llm_trace import LLMCallTraceCollector

_SHARED_NON_TEMPORAL_SEMANTIC_RULES = """- A named city is sufficient at city granularity. Do not create ambiguity merely because no airport is named, and never expand a city into airports.
- Preserve geographic ambiguity only when the wording has multiple materially plausible identities and no conventional dominant reading.
- Explicit destination alternatives are valid search options, not ambiguity. A broad destination tentatively narrowed to a nested place keeps the nested place in destinations and uses destination_preference rather than destination ambiguity.
- Count I or we only when they are the travel subject: “I can go” means one traveler. Booking, helping, or searching for someone else does not.
"""

_NON_TEMPORAL_EXTRACTION_INSTRUCTIONS = f"""Extract only non-temporal travel-request semantics.

Do not extract, interpret, quote, or infer dates, durations, date anchors, date flexibility, or temporal ambiguity. A deterministic compiler owns all temporal facts outside this boundary.

{_SHARED_NON_TEMPORAL_SEMANTIC_RULES}
Return only the supplied structured schema. Preserve hard constraints and explicit ambiguity; do not invent missing facts."""

_TEMPORAL_SELECTOR_INSTRUCTIONS = """Select the best supplied temporal candidate from every candidate group.

The input is a finite, date-free catalog of complete, pre-authored interpretations. Return only selected_candidates: exactly one opaque candidate handle from each group, with no duplicates or handles outside candidate_groups. Do not invent, alter, combine, or explain candidates, and do not calculate calendar dates.

For each group, select the non-unresolved candidate whose summary and catalog constraints best match the covered local wording. Select unresolved only when no non-unresolved candidate in that group is supported by the wording and satisfiable from available_productions plus productions from the other selected candidates. Do not treat endpoint_cue=unspecified as evidence against an otherwise supported candidate.

When endpoint_cue is departure or return, a selected candidate covering that evidence must agree. Anchor-use modes are exact: direct_window uses the anchor as the selected period; reference_only uses it only as the stated relation’s reference; unresolved_support preserves the wording without resolving it. Honor relation_ordinal, requires and produces, and an exact composition_operand. A duration describes trip length, not a departure or return endpoint assertion."""


class NonTemporalExtractionError(RuntimeError):
    """Raised when non-temporal Pass 1 has no usable structured output."""


class TemporalSelectionError(RuntimeError):
    """Raised when the temporal selector has no usable structured output."""


@dataclass(frozen=True, slots=True)
class OpenAIExtractorConfig:
    """Configuration for one independently observable model boundary."""

    model: str

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model must not be empty")


class OpenAIIntentExtractor:
    """One adapter instance, usable as Pass 1 or selector with separate capture state."""

    def __init__(
        self,
        config: OpenAIExtractorConfig,
        client: OpenAI | None = None,
        *,
        capture_llm_io: bool = False,
    ) -> None:
        self.config = config
        self._client = client or OpenAI()
        self._usage_call_count = 0
        self._usage_records: list[dict[str, int]] = []
        self._llm_trace = LLMCallTraceCollector(enabled=capture_llm_io)

    def reset_capture(self) -> None:
        self._usage_call_count = 0
        self._usage_records = []
        self._llm_trace.reset()

    def take_call_traces(self) -> list[dict[str, Any]]:
        return self._llm_trace.take()

    def take_usage(self) -> dict[str, int] | None:
        call_count = self._usage_call_count
        records = self._usage_records
        self._usage_call_count = 0
        self._usage_records = []
        if not records:
            return None
        return {
            "calls": call_count,
            "captured_calls": len(records),
            "missing_calls": call_count - len(records),
            "input_tokens": sum(item["input_tokens"] for item in records),
            "output_tokens": sum(item["output_tokens"] for item in records),
            "total_tokens": sum(item["total_tokens"] for item in records),
        }

    def _capture_usage(self, response: Any) -> None:
        self._usage_call_count += 1
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        payload = usage if isinstance(usage, dict) else usage.model_dump(mode="json")
        input_tokens = payload.get("input_tokens")
        output_tokens = payload.get("output_tokens")
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
            return
        total_tokens = payload.get("total_tokens")
        self._usage_records.append(
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens
                if isinstance(total_tokens, int)
                else input_tokens + output_tokens,
            }
        )

    def _parse_response(
        self, *, stage: str, instructions: str, payload: str, text_format: Any
    ) -> Any:
        started = time.perf_counter()
        try:
            response = self._client.responses.parse(
                model=self.config.model,
                instructions=instructions,
                input=payload,
                text_format=text_format,
                store=False,
            )
        except Exception as exc:
            self._llm_trace.record(
                stage=stage,
                model=self.config.model,
                instructions=instructions,
                payload=payload,
                text_format=text_format,
                error=exc,
                latency_seconds=time.perf_counter() - started,
            )
            raise
        self._llm_trace.record(
            stage=stage,
            model=self.config.model,
            instructions=instructions,
            payload=payload,
            text_format=text_format,
            response=response,
            latency_seconds=time.perf_counter() - started,
        )
        return response

    def extract_non_temporal(
        self, model_input: NonTemporalExtractionInput
    ) -> NonTemporalIntentExtraction:
        payload = json.dumps(model_input.model_dump(mode="json"), separators=(",", ":"))
        try:
            response = self._parse_response(
                stage="compiler_non_temporal_pass_one",
                instructions=_NON_TEMPORAL_EXTRACTION_INSTRUCTIONS,
                payload=payload,
                text_format=NonTemporalIntentExtraction,
            )
        except Exception as exc:
            raise NonTemporalExtractionError("OpenAI non-temporal intent extraction failed") from exc
        self._capture_usage(response)
        parsed = response.output_parsed
        if not isinstance(parsed, NonTemporalIntentExtraction):
            raise NonTemporalExtractionError(
                "OpenAI returned an unexpected non-temporal extraction output type"
            )
        return parsed

    def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
        if not model_input.candidate_groups:
            return TemporalSelectorOutput(selected_candidates=[])
        payload = json.dumps(model_input.model_dump(mode="json"), separators=(",", ":"))
        try:
            response = self._parse_response(
                stage="temporal_candidate_selector",
                instructions=_TEMPORAL_SELECTOR_INSTRUCTIONS,
                payload=payload,
                text_format=TemporalSelectorOutput,
            )
        except Exception as exc:
            raise TemporalSelectionError("OpenAI temporal candidate selection failed") from exc
        self._capture_usage(response)
        parsed = response.output_parsed
        if not isinstance(parsed, TemporalSelectorOutput):
            raise TemporalSelectionError("OpenAI returned an unexpected temporal selector output type")
        return parsed
