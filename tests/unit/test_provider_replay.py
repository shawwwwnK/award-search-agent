"""Replay rejects mismatched acquisition scope and altered immutable evidence."""

from datetime import UTC, date, datetime

import pytest
from pydantic import JsonValue, ValidationError

from award_agent.providers.contracts import (
    CapturedResponse,
    EvidenceRef,
    ParsedProviderPage,
    ProviderQuery,
)
from award_agent.providers.evidence import evidence_sha256
from award_agent.providers.replay import ReplayAdapter, ReplayEntry, ReplayTape


class NeverLive:
    def fetch(self, *args: object, **kwargs: object) -> CapturedResponse:
        raise AssertionError("replay must never invoke a live fetch")

    def parse(self, *args: object, **kwargs: object) -> ParsedProviderPage:
        raise AssertionError("unused parser")


def entry() -> ReplayEntry:
    query = ProviderQuery(
        query_id="capture", provider="gfly", role="direct_cash", origins=("SFO",),
        destinations=("BKK",), start_date=date(2026, 10, 5), end_date=date(2026, 10, 5),
        travelers=2, cabins=("business",),
    )
    body: JsonValue = {"itineraries": []}
    response = CapturedResponse(
        query_id=query.query_id, provider="gfly", status="completed", body=body,
        elapsed_seconds=1, byte_count=20,
        evidence=EvidenceRef(sha256=evidence_sha256(body), relative_path="capture.json",
                             retrieved_at=datetime(2026, 9, 22, tzinfo=UTC)),
    )
    return ReplayEntry(query=query, response=response)


def test_replay_requires_exact_scope_and_cannot_fall_through() -> None:
    fixture = entry()
    replay = ReplayAdapter(NeverLive(), ReplayTape(entries=(fixture,)))
    for changes in ({"travelers": 1}, {"cabins": ("economy",)}, {"currency": "EUR"}):
        with pytest.raises(LookupError, match="no exact"):
            replay.fetch(fixture.query.model_copy(update=changes), cursor=None,
                         timeout_seconds=2, max_bytes=100)
    query = fixture.query.model_copy(update={"query_id": "new-attribution"})
    assert replay.fetch(query, cursor=None, timeout_seconds=2, max_bytes=100).query_id == query.query_id
    with pytest.raises(LookupError):
        replay.fetch(query, cursor=None, timeout_seconds=2, max_bytes=100)
    assert replay.consumed == 1


def test_replay_refuses_tampered_body_and_resource_overflow() -> None:
    fixture = entry()
    payload = fixture.model_dump(mode="json")
    payload["response"]["body"] = {"itineraries": [{"price": 0}]}
    with pytest.raises(ValidationError, match="immutable evidence digest"):
        ReplayEntry.model_validate(payload)
    replay = ReplayAdapter(NeverLive(), ReplayTape(entries=(fixture,)))
    with pytest.raises(ValueError, match="byte budget"):
        replay.fetch(fixture.query, cursor=None, timeout_seconds=2, max_bytes=1)
    with pytest.raises(TimeoutError, match="time budget"):
        replay.fetch(fixture.query, cursor=None, timeout_seconds=0.5, max_bytes=100)
    assert replay.consumed == 0


@pytest.mark.parametrize("status", ["budget_exhausted", "completed"])
def test_replay_preserves_recorded_budget_failure_under_identical_limits(status: str) -> None:
    fixture = entry()
    response = fixture.response.model_copy(update={"status": status, "byte_count": 101})
    recorded = ReplayEntry(query=fixture.query, response=response,
                           max_bytes=100, timeout_seconds=2)
    replay = ReplayAdapter(NeverLive(), ReplayTape(entries=(recorded,)))
    observed = replay.fetch(fixture.query, cursor=None, max_bytes=100, timeout_seconds=2)
    assert observed.status == status
    assert observed.byte_count == 101
    changed_limit = ReplayAdapter(NeverLive(), ReplayTape(entries=(recorded,)))
    with pytest.raises(ValueError, match="byte budget"):
        changed_limit.fetch(fixture.query, cursor=None, max_bytes=50, timeout_seconds=2)


def test_replay_binds_capture_cursor() -> None:
    fixture = entry()
    with pytest.raises(ValidationError, match="cursors differ"):
        ReplayEntry(query=fixture.query, cursor="wrong", response=fixture.response)
