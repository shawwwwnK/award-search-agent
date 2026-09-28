"""Sanitized, content-addressed provider response evidence.

Evidence files contain provider data only. Credentials and provider booking URLs are
never copied into replay fixtures. A digest always describes the sanitized bytes,
so a replay cannot silently attach different response data to an old receipt.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

_SECRET_KEYS = frozenset(
    {
        "authorization",
        "partner-authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "cookie",
        "set-cookie",
        "password",
        "booking_links",
        "booking_url",
        "booking_link",
        "bookingtoken",
        "booking_token",
    }
)


def sanitize_provider_payload(value: Any, *, secret_values: tuple[str, ...] = ()) -> Any:
    """Return a detached JSON value with credential and booking-link fields removed."""
    if isinstance(value, dict):
        return {
            str(key): sanitize_provider_payload(child, secret_values=secret_values)
            for key, child in value.items()
            if str(key).lower() not in _SECRET_KEYS
        }
    if isinstance(value, list):
        return [sanitize_provider_payload(child, secret_values=secret_values) for child in value]
    if isinstance(value, str):
        for secret in secret_values:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("provider evidence contains a nonfinite number")
    if value is None or isinstance(value, (int, float, bool)):
        return value
    raise TypeError(f"provider evidence contains unsupported value type {type(value).__name__}")


def canonical_evidence_bytes(value: Any) -> bytes:
    """Serialize a sanitized response deterministically for digest and replay."""
    return json.dumps(
        sanitize_provider_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def evidence_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_evidence_bytes(value)).hexdigest()


def sanitized_failure_sample(contents: bytes, *, truncated: bool) -> dict[str, Any]:
    """Retain bounded malformed-response context without copying common secrets."""
    decoded = contents[:4096].decode("utf-8", "replace")
    decoded = re.sub(
        r'(?i)("(?:authorization|partner-authorization|api[_-]?key|access_token|refresh_token|bookingtoken|cookie|password)"\s*:\s*)"(?:\\.|[^"\\])*"',
        r'\1"[REDACTED]"',
        decoded,
    )
    decoded = re.sub(
        r"(?i)(authorization|api[_-]?key|token|cookie|password)\s*[:=]\s*[^\s,\"}]+",
        r"\1=[REDACTED]",
        decoded,
    )
    decoded = re.sub(r"https?://[^\s\"']+", "[URL REDACTED]", decoded)
    return {
        "unparsed_response_sample": decoded,
        "sample_truncated": truncated or len(contents) > 4096,
        "sample_bytes": min(len(contents), 4096),
        "raw_sha256": hashlib.sha256(contents).hexdigest() if not truncated else None,
    }


def write_immutable_evidence(directory: Path, value: Any) -> tuple[Path, str]:
    """Store a sanitized response under its digest; reject any conflicting bytes."""
    contents = canonical_evidence_bytes(value)
    digest = hashlib.sha256(contents).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.json"
    if path.exists():
        if path.read_bytes() != contents:
            raise ValueError(f"evidence digest collision or mutation: {path}")
    else:
        try:
            with path.open("xb") as output:
                output.write(contents)
        except FileExistsError:
            if path.read_bytes() != contents:
                raise ValueError(f"evidence digest collision or mutation: {path}") from None
    return path, digest


def read_verified_evidence(path: Path, expected_sha256: str) -> Any:
    contents = path.read_bytes()
    actual = hashlib.sha256(contents).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"evidence digest mismatch: {path}")
    value = json.loads(contents)
    if canonical_evidence_bytes(value) != contents:
        raise ValueError(f"evidence is not canonical sanitized JSON: {path}")
    return value
