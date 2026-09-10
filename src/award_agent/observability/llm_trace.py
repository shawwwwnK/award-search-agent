"""Opt-in local capture of model calls used to diagnose evaluation failures."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any


def _json_compatible(value: Any) -> Any:
    """Best-effort conversion that never makes tracing change model behavior."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return _json_compatible(dump(mode="json"))
        except Exception:  # noqa: BLE001 - tracing must not affect the model call
            return repr(value)
    return repr(value)


def _schema_snapshot(text_format: Any) -> dict[str, Any]:
    schema = getattr(text_format, "model_json_schema", None)
    if callable(schema):
        try:
            return {
                "name": getattr(text_format, "__name__", repr(text_format)),
                "schema": _json_compatible(schema()),
            }
        except Exception:  # noqa: BLE001 - tracing must not affect the model call
            return {"name": getattr(text_format, "__name__", repr(text_format))}
    return {"name": getattr(text_format, "__name__", repr(text_format))}


def response_schema_sha256(text_format: Any) -> str:
    """Stable hash for a Structured Output DTO schema, never model output."""

    snapshot = _schema_snapshot(text_format)
    canonical = json.dumps(snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _response_snapshot(response: Any) -> str:
    """Serialize the SDK response as faithfully as the SDK object permits."""

    for method_name in ("model_dump_json", "to_json"):
        method = getattr(response, method_name, None)
        if not callable(method):
            continue
        try:
            serialized = method()
            if isinstance(serialized, bytes):
                return serialized.decode("utf-8")
            return str(serialized)
        except Exception:  # noqa: BLE001 - fall back without affecting the call
            serialized = None
        if serialized is None:
            continue
    return json.dumps(_json_compatible(response), ensure_ascii=False, separators=(",", ":"))


class LLMCallTraceCollector:
    """Collect exact model-facing call data only when explicitly enabled."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self._traces: list[dict[str, Any]] = []

    def reset(self) -> None:
        self._traces = []

    def record(
        self,
        *,
        stage: str,
        model: str,
        instructions: str,
        payload: str,
        text_format: Any,
        adapter_version: str | None = None,
        provider_stage: str | None = None,
        response: Any | None = None,
        error: BaseException | None = None,
        latency_seconds: float | None = None,
    ) -> None:
        if not self.enabled:
            return
        trace: dict[str, Any] = {
            "sequence": len(self._traces) + 1,
            "stage": stage,
            "adapter": {
                "version": adapter_version,
                "response_schema_sha256": response_schema_sha256(text_format),
                "provider_stage": provider_stage,
            },
            "request": {
                "model": model,
                "instructions": instructions,
                "input": payload,
                "text_format": _schema_snapshot(text_format),
                "store": False,
            },
            "response_json": None if response is None else _response_snapshot(response),
            "parsed_output": (
                None
                if response is None
                else _json_compatible(getattr(response, "output_parsed", None))
            ),
            "latency_seconds": latency_seconds,
            "error": (
                None if error is None else {"type": type(error).__name__, "message": str(error)}
            ),
        }
        self._traces.append(trace)

    def take(self) -> list[dict[str, Any]]:
        traces = self._traces
        self._traces = []
        return traces


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "case"


def write_eval_llm_trace(
    directory: Path,
    *,
    scenario: Mapping[str, Any],
    record: Mapping[str, Any],
    calls: Sequence[Mapping[str, Any]],
) -> Path:
    """Write one private, self-contained evaluation trace sidecar."""

    directory.mkdir(parents=True, exist_ok=True)
    scenario_id = str(scenario["id"])
    trial = int(record["trial"])
    path = directory / f"{_safe_filename(scenario_id)}__trial-{trial}.json"
    trace = {
        "schema_version": 1,
        "scenario": _json_compatible(
            {
                "id": scenario_id,
                "trial": trial,
                "input": scenario.get("input"),
                "context": scenario.get("context"),
            }
        ),
        "evaluation_record": _json_compatible(record),
        "calls": [_json_compatible(call) for call in calls],
    }
    path.write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n")
    return path
