"""Exact-query offline replay of captured provider responses.

Replay never falls through to a live transport. A missing capture is an explicit
error, so a fixture cannot fabricate an empty provider result.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field, model_validator

from award_agent.providers.contracts import (
    CapturedResponse,
    ParsedProviderPage,
    ProviderAdapter,
    ProviderQuery,
    content_digest,
)
from award_agent.providers.evidence import evidence_sha256
from award_agent.search_planning.contracts import PlanningContractModel


def acquisition_key(query: ProviderQuery, cursor: str | None) -> str:
    """Bind every acquisition dimension, excluding downstream attribution only."""
    payload = query.model_dump(mode="json", exclude={
        "query_id", "logical_query_ids", "logical_use_ids", "strategy_ids",
        "positioning_dependency_ids", "activation_observation_ids",
        "result_validation_obligations",
    })
    return content_digest({"query": payload, "cursor": cursor})


class ReplayEntry(PlanningContractModel):
    query: ProviderQuery
    cursor: str | None = None
    response: CapturedResponse
    timeout_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    max_bytes: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def captured_identity(self) -> ReplayEntry:
        if self.query.provider != self.response.provider:
            raise ValueError("replay query and response providers differ")
        if self.query.query_id != self.response.query_id:
            raise ValueError("replay query and response identities differ")
        if self.cursor != self.response.cursor:
            raise ValueError("replay request and capture cursors differ")
        if evidence_sha256(self.response.body) != self.response.evidence.sha256:
            raise ValueError("replay body does not match its immutable evidence digest")
        return self


class ReplayTape(PlanningContractModel):
    entries: tuple[ReplayEntry, ...]


class ReplayAdapter:
    """Reuse real provider parsers with an immutable, finite capture tape."""

    def __init__(self, parser: ProviderAdapter, tape: ReplayTape) -> None:
        self._parser = parser
        self._entries = list(tape.entries)
        self.consumed = 0

    def fetch(
        self, query: ProviderQuery, *, cursor: str | None,
        timeout_seconds: float, max_bytes: int,
    ) -> CapturedResponse:
        key = acquisition_key(query, cursor)
        for index, entry in enumerate(self._entries):
            if acquisition_key(entry.query, entry.cursor) != key:
                continue
            same_limits = (
                entry.max_bytes == max_bytes and entry.timeout_seconds is not None
                and abs(entry.timeout_seconds - timeout_seconds) < 1e-6
            )
            # A completed physical response can cross a limit at its final read;
            # the executor must replay the same observed overrun as partial work.
            captured_overrun = same_limits
            if entry.response.byte_count > max_bytes and not captured_overrun:
                raise ValueError("captured response exceeds remaining replay byte budget")
            if entry.response.elapsed_seconds > timeout_seconds and not captured_overrun:
                raise TimeoutError("captured response exceeds replay time budget")
            self._entries.pop(index)
            self.consumed += 1
            return entry.response.model_copy(update={"query_id": query.query_id})
        raise LookupError("no exact provider capture matches this query and cursor")

    def parse(
        self, query: ProviderQuery, capture: CapturedResponse, *,
        airport_timezones: Mapping[str, str],
    ) -> ParsedProviderPage:
        return self._parser.parse(query, capture, airport_timezones=airport_timezones)


class RecordingAdapter:
    """Capture an execution tape without changing adapter or executor behavior."""

    def __init__(self, adapter: ProviderAdapter) -> None:
        self._adapter = adapter
        self.entries: list[ReplayEntry] = []

    def fetch(
        self, query: ProviderQuery, *, cursor: str | None,
        timeout_seconds: float, max_bytes: int,
    ) -> CapturedResponse:
        response = self._adapter.fetch(
            query, cursor=cursor, timeout_seconds=timeout_seconds, max_bytes=max_bytes,
        )
        self.entries.append(ReplayEntry(
            query=query, cursor=cursor, response=response,
            timeout_seconds=timeout_seconds, max_bytes=max_bytes,
        ))
        return response

    def parse(
        self, query: ProviderQuery, capture: CapturedResponse, *,
        airport_timezones: Mapping[str, str],
    ) -> ParsedProviderPage:
        return self._adapter.parse(query, capture, airport_timezones=airport_timezones)
