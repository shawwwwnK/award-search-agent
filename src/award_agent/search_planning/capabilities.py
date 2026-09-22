"""Versioned local evidence for the supported Cached Search planning capability.

This module is deliberately not a provider client.  It only verifies the
small, reviewed capability record that allows the planner to distinguish a
supported planning obligation from a deferred one.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from award_agent.search_planning.contracts import (
    CapabilityReceipt,
    FilterObligationKind,
    PlanningContractModel,
)


class CapabilitySource(PlanningContractModel):
    source_id: str = Field(min_length=1)
    local_path: str = Field(min_length=1)
    captured_on: date
    reference_updated_on: date | None = None
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CachedSearchCapability(PlanningContractModel):
    """Evidence-backed capability record, with no executable provider details."""

    capability_id: Literal["seats_aero.cached_search.v1"]
    capability_version: str = Field(min_length=1)
    provider: Literal["seats_aero"]
    operation: Literal["cached_search"]
    required_dimensions: tuple[str, ...] = Field(min_length=1)
    supported_filters: tuple[FilterObligationKind, ...] = Field(min_length=1)
    sources: tuple[CapabilitySource, ...] = Field(min_length=1)
    caveats: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def canonicalize_record_order(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        copied = dict(value)
        if isinstance(copied.get("sources"), (list, tuple)):
            copied["sources"] = sorted(
                copied["sources"],
                key=lambda item: (
                    str(item.get("source_id", "")) if isinstance(item, dict) else str(item)
                ),
            )
        if isinstance(copied.get("supported_filters"), (list, tuple)):
            copied["supported_filters"] = sorted(copied["supported_filters"], key=str)
        return copied

    @field_validator("required_dimensions", "caveats")
    @classmethod
    def unique_nonempty_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(value.strip() for value in values)
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("capability values must be unique and nonempty")
        return tuple(sorted(cleaned))

    @model_validator(mode="after")
    def validate_v1_boundary(self) -> CachedSearchCapability:
        expected = frozenset(FilterObligationKind)
        if frozenset(self.supported_filters) != expected:
            raise ValueError("cached-search v1 record must declare exactly the reviewed filter set")
        if len(self.supported_filters) != len(set(self.supported_filters)):
            raise ValueError("supported filters must be unique")
        source_ids = tuple(source.source_id for source in self.sources)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("capability source IDs must be unique")
        if set(self.required_dimensions) != {"destination_airport_list", "origin_airport_list"}:
            raise ValueError(
                "cached-search v1 must require resolved origin and destination airport lists"
            )
        return self

    def supports(self, kind: FilterObligationKind) -> bool:
        return kind in self.supported_filters


def capability_content_digest(capability: CachedSearchCapability) -> str:
    """Return the canonical content fingerprint used in a plan identity."""

    rendered = json.dumps(
        capability.model_dump(mode="json", round_trip=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def capability_receipt_matches(
    capability: CachedSearchCapability, receipt: CapabilityReceipt
) -> bool:
    """Verify that a plan receipt still names this exact reviewed capability."""

    return (
        receipt.capability_id == capability.capability_id
        and receipt.capability_version == capability.capability_version
        and receipt.content_sha256 == capability_content_digest(capability)
        and tuple((source.source_id, source.content_sha256) for source in receipt.source_receipts)
        == tuple((source.source_id, source.content_sha256) for source in capability.sources)
        and receipt.caveats == capability.caveats
    )


def verify_capability_source_artifacts(capability: CachedSearchCapability) -> None:
    """Verify the local source bytes named by a reviewed capability record.

    A capability record is evidence rather than an executable provider adapter.
    Its source reference nevertheless has to resolve inside this repository and
    match the recorded SHA-256 before a qualification corpus may claim it used
    that evidence.  In particular, never let a fixture-controlled ``local_path``
    escape the checkout through ``..`` or an absolute path.
    """

    repository_root = Path(__file__).resolve().parents[3]
    for source in capability.sources:
        source_path = Path(source.local_path)
        if source_path.is_absolute():
            raise ValueError(
                f"capability source {source.source_id!r} must use a repository-relative path"
            )
        resolved = (repository_root / source_path).resolve()
        if not resolved.is_relative_to(repository_root):
            raise ValueError(
                f"capability source {source.source_id!r} resolves outside the repository"
            )
        if not resolved.is_file():
            raise ValueError(
                f"capability source {source.source_id!r} does not name a local regular file"
            )
        actual_sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual_sha256 != source.content_sha256:
            raise ValueError(
                f"capability source {source.source_id!r} content SHA-256 does not match"
            )


def default_capability_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "data"
        / "provider_capabilities"
        / "seats-aero-cached-search-v1.json"
    )


def load_cached_search_capability(path: Path) -> CachedSearchCapability:
    with path.open(encoding="utf-8") as file:
        return CachedSearchCapability.model_validate(json.load(file))


def load_default_cached_search_capability() -> CachedSearchCapability:
    return load_cached_search_capability(default_capability_path())
