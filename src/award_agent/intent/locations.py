"""Deterministic preservation rules for explicitly named locations."""

from __future__ import annotations

import re

from award_agent.domain import CoarseIntentExtraction, LocationKind, LocationRef, RawRequest

_IATA_CODE = re.compile(r"[A-Za-z]{3}")


def _contains_code(request_text: str, code: str) -> bool:
    return (
        re.search(
            rf"(?<![A-Za-z]){re.escape(code)}(?![A-Za-z])",
            request_text,
            flags=re.IGNORECASE,
        )
        is not None
    )


def _preserve_airport_code(request: RawRequest, location: LocationRef) -> LocationRef:
    raw_text = location.raw_text.strip()
    if (
        location.kind is LocationKind.AIRPORT
        and _IATA_CODE.fullmatch(raw_text) is not None
        and _contains_code(request.text, raw_text)
    ):
        return location.model_copy(update={"value": raw_text.upper()})
    return location


def preserve_explicit_airport_codes(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
) -> CoarseIntentExtraction:
    """Keep model-classified, verbatim IATA codes usable by downstream workflows."""

    return extraction.model_copy(
        update={
            "origins": [
                _preserve_airport_code(request, location) for location in extraction.origins
            ],
            "destinations": [
                _preserve_airport_code(request, location) for location in extraction.destinations
            ],
        }
    )
