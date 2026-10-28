"""Streaming Responses adapter for explicit interactive Results requests."""

from __future__ import annotations

import json
import re
import time
from typing import Any, cast

import httpx
from openai import APIError, OpenAI

from .contracts import ResultsConfig, ResultsWriterError, WriterReceipt
from .interactive_contracts import InteractiveSettings

_SAFE_CODE = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")


def _safe_api_error_message(exc: Exception) -> str:
    """Keep diagnostic identifiers without copying provider text or headers."""
    name = type(exc).__name__
    parts = ["Interactive Results writer request failed.",
             f"exception={name if _SAFE_CODE.fullmatch(name) else 'Exception'}"]
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
        parts.append(f"status={status}")
    code = getattr(exc, "code", None)
    if code is None:
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            code = body.get("code")
            if code is None and isinstance(body.get("error"), dict):
                code = body["error"].get("code")
    if isinstance(code, str) and _SAFE_CODE.fullmatch(code):
        parts.append(f"code={code}")
    return " ".join(parts)


class OpenAIInteractiveResultsWriter:
    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client
        self._receipt: WriterReceipt | None = None

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self._receipt = self._receipt, None
        return receipt

    def author(self, request: dict[str, object], config: ResultsConfig,
               settings: InteractiveSettings) -> str:
        self._receipt = None
        started = time.perf_counter()
        first_event: float | None = None
        first_text: float | None = None
        response: Any = None
        terminal_response: Any = None
        full_request = dict(request)
        if settings.service_tier == "fast":
            full_request["service_tier"] = "fast"
        try:
            client = (self._client or OpenAI(max_retries=0)).with_options(
                max_retries=0, timeout=config.timeout_seconds)
            # The installed SDK may lag the Responses service_tier typing.
            with client.responses.stream(**cast(Any, full_request),
                    max_output_tokens=config.max_output_tokens,
                    store=False, truncation="disabled") as stream:
                for event in stream:
                    elapsed = time.perf_counter() - started
                    if first_event is None:
                        first_event = elapsed
                    if getattr(event, "type", None) == "response.output_text.delta" and first_text is None:
                        first_text = elapsed
                    if getattr(event, "type", None) in {
                            "response.completed", "response.incomplete", "response.failed"}:
                        terminal_response = getattr(event, "response", None)
                if terminal_response is not None:
                    response = terminal_response
                else:
                    try:
                        response = stream.get_final_response()
                    except RuntimeError as exc:
                        # The SDK uses this exact message when EOF arrives without
                        # a response.completed event. Preserve the failure as a
                        # Results artifact instead of letting it escape the runner.
                        if str(exc) != "Didn't receive a `response.completed` event.":
                            raise
                        usage: dict[str, int] = {}
                        if first_event is not None:
                            usage["first_event_ms"] = round(first_event * 1000)
                        if first_text is not None:
                            usage["first_text_ms"] = round(first_text * 1000)
                        self._receipt = WriterReceipt(
                            latency_seconds=time.perf_counter() - started, usage=usage)
                        raise ResultsWriterError(
                            "api_error", _safe_api_error_message(exc)) from exc
        except (APIError, httpx.HTTPError, ValueError) as exc:
            usage = {}
            if first_event is not None:
                usage["first_event_ms"] = round(first_event * 1000)
            if first_text is not None:
                usage["first_text_ms"] = round(first_text * 1000)
            self._receipt = WriterReceipt(latency_seconds=time.perf_counter() - started,
                                          usage=usage)
            raise ResultsWriterError("api_error", _safe_api_error_message(exc)) from exc
        raw = response.model_dump(mode="json")
        usage = raw.get("usage") or {}
        # Extra timing/tier keys are kept in usage to avoid altering historical receipt shapes.
        numeric_usage = {key: value for key, value in usage.items()
                         if isinstance(value, int) and not isinstance(value, bool)}
        if first_event is not None:
            numeric_usage["first_event_ms"] = round(first_event * 1000)
        if first_text is not None:
            numeric_usage["first_text_ms"] = round(first_text * 1000)
        self._receipt = WriterReceipt(raw_response=json.dumps(raw, ensure_ascii=False),
            status=raw.get("status"), usage=numeric_usage,
            latency_seconds=time.perf_counter() - started)
        # Requested/actual service tier are retained by the raw response and settings.
        if raw.get("status") == "incomplete":
            raise ResultsWriterError("incomplete", "Interactive writer response was incomplete.",
                                     self._receipt.raw_response)
        if raw.get("status") == "failed":
            raise ResultsWriterError("api_error", "Interactive Results service reported failure.",
                                     self._receipt.raw_response)
        for item in raw.get("output", []):
            if item.get("type") == "message" and any(part.get("type") == "refusal"
                    for part in item.get("content", [])):
                raise ResultsWriterError("refusal", "Interactive writer refused the request.",
                                         self._receipt.raw_response)
        if raw.get("status") != "completed":
            raise ResultsWriterError("schema_error", "Interactive writer did not complete.",
                                     self._receipt.raw_response)
        output_text = response.output_text
        if not output_text:
            raise ResultsWriterError("schema_error", "Interactive writer returned no wire document.",
                                     self._receipt.raw_response)
        return cast(str, output_text)
