"""Pure token arithmetic shared by model adapters with adapter-owned capture."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def token_record(payload: Any) -> dict[str, int] | None:
    """Convert an already-extracted SDK payload using the existing token checks."""
    input_tokens, output_tokens = payload.get("input_tokens"), payload.get("output_tokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    total_tokens = payload.get("total_tokens")
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens
        if isinstance(total_tokens, int)
        else input_tokens + output_tokens,
    }


def aggregate_usage(records: Sequence[dict[str, int]], calls: int) -> dict[str, int]:
    """Sum captured records while retaining the caller's attempt count."""
    return {
        "calls": calls,
        "captured_calls": len(records),
        "missing_calls": calls - len(records),
        "input_tokens": sum(item["input_tokens"] for item in records),
        "output_tokens": sum(item["output_tokens"] for item in records),
        "total_tokens": sum(item["total_tokens"] for item in records),
    }
