"""One-attempt Responses adapter for Results; orchestration belongs to the API."""

from __future__ import annotations

import json
import time
from typing import Any, cast

from openai import APIError, OpenAI
from pydantic import ValidationError

from .contracts import (
    CheckFinding,
    InputTokenReceipt,
    PreparedResultsInput,
    ResultsConfig,
    ResultsDocument,
    ResultsWriterError,
    WriterReceipt,
)
from .core import authoring_payload
from .request import token_request, token_request_digest


class OpenAIResultsInputMeasurer:
    """Count the exact token-bearing Responses request, without automatic retries."""

    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client

    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
        try:
            client = (self._client or OpenAI(max_retries=0)).with_options(
                max_retries=0, timeout=config.timeout_seconds)
            raw = client.post("/responses/input_tokens", body=request,
                              cast_to=dict[str, object])
            if not isinstance(raw, dict):
                raise TypeError("invalid input token response")
            if raw.get("object") != "response.input_tokens":
                raise ValueError("invalid input token response object")
            count = raw.get("input_tokens")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("invalid input token count")
            return InputTokenReceipt(request_digest=token_request_digest(request),
                                     input_tokens=count, raw_response=raw)
        except (APIError, TypeError, ValueError) as exc:
            raise ResultsWriterError("api_error", "Results input token measurement failed.") from exc


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
            request = token_request(prepared, config,
                                    authoring_payload(prepared, feedback, previous_document))
            response = client.responses.create(
                **cast(Any, request),
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
