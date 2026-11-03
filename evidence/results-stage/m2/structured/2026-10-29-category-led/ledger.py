"""Immutable, bounded reservations for the separate category-led campaign."""

from __future__ import annotations

import fcntl
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE / "campaign.json"
CALLS = HERE / "calls"


@contextmanager
def locked_campaign() -> Iterator[None]:
    with (HERE / ".campaign.lock").open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def campaign() -> dict[str, Any]:
    result = read_json(CAMPAIGN)
    if (result.get("contract") != "results-category-campaign-v1" or
            result.get("model") != "gpt-6-luna" or
            result.get("maximum_iterations") != 20 or
            result.get("maximum_generation_calls") != 600 or
            result.get("maximum_input_count_calls") != 600 or
            result.get("per_run_maximum_generations") != 3 or
            result.get("automatic_retries") != 0):
        raise ValueError("category campaign controls differ")
    return result


def remaining(kind: Literal["count", "generation"], settings: dict[str, Any]) -> int:
    key = "maximum_input_count_calls" if kind == "count" else "maximum_generation_calls"
    return settings[key] - len(list(CALLS.glob(f"{kind}-*.json")))


def require_headroom(settings: dict[str, Any]) -> None:
    for kind in ("count", "generation"):
        if remaining(kind, settings) < settings["per_run_maximum_generations"]:
            raise ValueError(f"campaign {kind} lacks three-call headroom")


def reserve(kind: Literal["count", "generation"], settings: dict[str, Any],
            *, run: str, label: str, digest: str) -> int:
    key = "maximum_input_count_calls" if kind == "count" else "maximum_generation_calls"
    existing = [read_json(path) for path in CALLS.glob(f"{kind}-*.json")]
    if sum(item["run_name"] == run for item in existing) >= settings["per_run_maximum_generations"]:
        raise ValueError(f"run {run} exceeded {kind} attempt limit")
    for index in range(1, settings[key] + 1):
        try:
            write_new(CALLS / f"{kind}-{index:03d}.json", {
                "run_name": run, "label": label, "request_digest": digest,
                "reserved_at_utc": datetime.now(UTC).isoformat(),
                "status": "reserved_before_invocation"})
        except FileExistsError:
            continue
        return index
    raise ValueError(f"campaign {kind} bound exhausted")
