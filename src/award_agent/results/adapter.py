"""One-attempt Responses adapter for Results; orchestration belongs to the API."""

from __future__ import annotations

import json
import time

from openai import APIError, OpenAI
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from .contracts import (
    CheckFinding,
    PreparedResultsInput,
    ResultsConfig,
    ResultsDocument,
    ResultsWriterError,
    WriterReceipt,
)
from .core import authoring_payload


class OpenAIResultsWriter:
    """No default model, automatic retry, tools, or provider access.

    An injected client still receives zero retries and the explicit timeout.
    Caller cancellation (KeyboardInterrupt) propagates; no background job survives it.
    """

    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client
        self._receipt: WriterReceipt | None = None

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self._receipt = self._receipt, None
        return receipt

    def author(
        self,
        prepared: PreparedResultsInput,
        config: ResultsConfig,
        feedback: tuple[CheckFinding, ...] = (),
        previous_document: ResultsDocument | None = None,
    ) -> ResultsDocument:
        self._receipt = None
        # Construct lazily so measurement, replay and source failures need no credentials.
        started = time.perf_counter()
        try:
            client = (self._client or OpenAI(max_retries=0)).with_options(
                max_retries=0, timeout=config.timeout_seconds,
            )
            response = client.responses.create(
                model=config.model,
                instructions=prepared.instructions,
                input=authoring_payload(prepared, feedback, previous_document),
                text={"format": {"type": "json_schema", "name": "ResultsDocument",
                                 "strict": True,
                                 "schema": to_strict_json_schema(ResultsDocument)}},
                max_output_tokens=config.max_output_tokens,
                store=False,
                truncation="disabled",
            )
        except (APIError, ValueError) as exc:
            self._receipt = WriterReceipt(latency_seconds=time.perf_counter() - started)
            raise ResultsWriterError("api_error", "Results writer API request failed.") from exc
        raw = response.model_dump_json()
        usage = response.usage
        self._receipt = WriterReceipt(
            raw_response=raw,
            status=response.status,
            usage={} if usage is None else {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            },
            latency_seconds=time.perf_counter() - started,
        )
        try:
            # Parse after preserving raw response: schema failures retain generation evidence.
            return ResultsDocument.model_validate_json(response.output_text)
        except (ValidationError, json.JSONDecodeError) as exc:
            if response.status == "incomplete":
                raise ResultsWriterError("incomplete", "Writer response was incomplete.", raw) from exc
            if any(item.type == "message" and any(part.type == "refusal" for part in item.content)
                   for item in response.output):
                raise ResultsWriterError("refusal", "Writer declined to produce a document.", raw) from exc
            raise ResultsWriterError("schema_error", "Writer returned no recoverable document.", raw) from exc
