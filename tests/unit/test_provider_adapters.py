import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from pydantic import JsonValue

from award_agent.providers.contracts import CapturedResponse, EvidenceRef, ProviderQuery
from award_agent.providers.evidence import evidence_sha256
from award_agent.providers.gfly import GflyAdapter
from award_agent.providers.seats_aero import SeatsAeroAdapter
from award_agent.providers.transport import CommandResponse, HttpResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVIDER_FIXTURES = REPO_ROOT / "tests/fixtures/providers"


class FakeHttp:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.params: Mapping[str, str | int | bool] | None = None

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | bool],
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse:
        self.params = params
        assert headers["Partner-Authorization"] == "test-only"
        return HttpResponse(200, json.dumps(self.payload).encode(), 0.1)


class FakeCommand:
    def __init__(self, payload: Any, exit_code: int = 0) -> None:
        self.payload = payload
        self.exit_code = exit_code
        self.argv: Sequence[str] | None = None

    def run(
        self, argv: Sequence[str], *, timeout_seconds: float, max_response_bytes: int
    ) -> CommandResponse:
        self.argv = argv
        content = json.dumps(self.payload).encode()
        return CommandResponse(
            self.exit_code,
            content if self.exit_code == 0 else b"",
            content if self.exit_code else b"",
            0.2,
        )


def _award_query() -> ProviderQuery:
    return ProviderQuery(
        query_id="award-1",
        provider="seats_aero",
        role="mandatory_award",
        origins=("SFO",),
        destinations=("BKK",),
        start_date=date(2027, 5, 12),
        end_date=date(2027, 5, 12),
        travelers=2,
        cabins=("business",),
        page_size=10,
    )


def _cash_query() -> ProviderQuery:
    return ProviderQuery(
        query_id="cash-1",
        provider="gfly",
        role="direct_cash",
        origins=("SFO",),
        destinations=("BKK",),
        start_date=date(2027, 5, 12),
        end_date=date(2027, 5, 12),
        travelers=2,
        cabins=("business",),
    )


def test_seats_cursor_uses_first_response_and_cumulative_skip(tmp_path: Path) -> None:
    row = {
        "ID": "availability-1",
        "Route": {"OriginAirport": "SFO", "DestinationAirport": "BKK"},
        "Date": "2027-05-12",
        "Source": "qatar",
        "JAvailable": True,
        "JMileageCost": "75000",
        "JRemainingSeats": "0",
    }
    transport = FakeHttp({"data": [row], "hasMore": True, "cursor": 123})
    adapter = SeatsAeroAdapter(api_key="test-only", evidence_root=tmp_path, transport=transport)
    capture = adapter.fetch(_award_query(), cursor=None, timeout_seconds=2, max_bytes=10000)
    page = adapter.parse(
        _award_query(),
        capture,
        airport_timezones={"SFO": "America/Los_Angeles", "BKK": "Asia/Bangkok"},
    )
    assert page.next_cursor == '{"first_cursor": 123, "skip": 1}'
    assert page.observations[0].seats.state == "unknown"
    assert page.observations[0].raw_fields["JRemainingSeats"].value == "0"
    assert page.observations[0].taxes_fees.state == "unknown"
    assert any(f.code == "seats_program_unsupported" for f in page.observations[0].findings)
    adapter.fetch(_award_query(), cursor=page.next_cursor, timeout_seconds=2, max_bytes=10000)
    assert transport.params is not None
    assert transport.params["cursor"] == 123
    assert transport.params["skip"] == 1


def test_seats_provider_error_echo_does_not_store_credential(tmp_path: Path) -> None:
    transport = FakeHttp({"message": "test-only was echoed"})
    adapter = SeatsAeroAdapter(api_key="test-only", evidence_root=tmp_path, transport=transport)
    capture = adapter.fetch(_award_query(), cursor=None, timeout_seconds=2, max_bytes=10000)
    assert capture.body == {"message": "[REDACTED] was echoed"}
    assert b"test-only" not in (tmp_path / capture.evidence.relative_path).read_bytes()


def test_seats_z_suffix_is_interpreted_as_airport_local_time(tmp_path: Path) -> None:
    trip = {
        "ID": "trip-1",
        "Source": "qatar",
        "Cabin": "business",
        "MileageCost": 75000,
        "AvailabilityID": "availability-1",
        "OriginAirport": "SFO",
        "DestinationAirport": "BKK",
        "DepartsAt": "2027-05-12T10:00:00Z",
        "ArrivesAt": "2027-05-13T21:00:00Z",
        "AvailabilitySegments": [
            {
                "OriginAirport": "SFO",
                "DestinationAirport": "DOH",
                "DepartsAt": "2027-05-12T10:00:00Z",
                "ArrivesAt": "2027-05-13T09:00:00Z",
            },
            {
                "OriginAirport": "DOH",
                "DestinationAirport": "BKK",
                "DepartsAt": "2027-05-13T11:00:00Z",
                "ArrivesAt": "2027-05-13T21:00:00Z",
            },
        ],
    }
    transport = FakeHttp({"data": [trip]})
    query = _award_query().model_copy(
        update={"role": "award_detail", "detail_id": "availability-1"}
    )
    adapter = SeatsAeroAdapter(api_key="test-only", evidence_root=tmp_path, transport=transport)
    capture = adapter.fetch(query, cursor=None, timeout_seconds=2, max_bytes=10000)
    page = adapter.parse(
        query,
        capture,
        airport_timezones={
            "SFO": "America/Los_Angeles",
            "DOH": "Asia/Qatar",
            "BKK": "Asia/Bangkok",
        },
    )
    assert page.status == "completed"
    assert page.observations[0].legs[0].departure_instant == datetime(2027, 5, 12, 17, tzinfo=UTC)
    assert page.observations[0].taxes_fees.state == "unknown"


def test_seats_tax_and_seat_null_zero_absent_remain_distinct(tmp_path: Path) -> None:
    query = _award_query().model_copy(
        update={"role": "award_detail", "detail_id": "availability-1"}
    )
    base = {
        "Source": "aeroplan",
        "Cabin": "business",
        "AvailabilityID": "availability-1",
        "OriginAirport": "SFO",
        "DestinationAirport": "BKK",
        "DepartsAt": "2027-05-12T10:00:00Z",
        "ArrivesAt": "2027-05-13T12:00:00Z",
        "AvailabilitySegments": [
            {
                "OriginAirport": "SFO",
                "DestinationAirport": "BKK",
                "DepartsAt": "2027-05-12T10:00:00Z",
                "ArrivesAt": "2027-05-13T12:00:00Z",
            }
        ],
    }
    rows = [
        dict(base, ID="null", TotalTaxes=None, RemainingSeats=0),
        dict(base, ID="zero", TotalTaxes=0, RemainingSeats=None),
        dict(base, ID="absent"),
    ]
    transport = FakeHttp({"data": rows})
    adapter = SeatsAeroAdapter(api_key="test-only", evidence_root=tmp_path, transport=transport)
    capture = adapter.fetch(query, cursor=None, timeout_seconds=2, max_bytes=10000)
    page = adapter.parse(
        query, capture, airport_timezones={"SFO": "America/Los_Angeles", "BKK": "Asia/Bangkok"}
    )
    assert page.status == "completed"
    assert [
        (obs.raw_fields["TotalTaxes"].state, obs.raw_fields["TotalTaxes"].value, obs.seats.state)
        for obs in page.observations
    ] == [("null", None, "value"), ("value", 0, "null"), ("absent", None, "absent")]
    assert [obs.taxes_fees.state for obs in page.observations] == ["null", "value", "absent"]


def test_gfly_preserves_unknown_price_scope_and_detects_truncation(tmp_path: Path) -> None:
    query = _cash_query()
    row = {
        "origin": "SFO",
        "destination": "BKK",
        "departure": "2027-05-12T13:30:00",
        "arrival": "2027-05-14T05:45:00",
        "price": 7667,
        "currency": "USD",
        "stops": 1,
        "layovers": [{"airport": "NRT", "minutes": 530}],
        "airlines": ["JAL"],
    }
    body = {
        "schemaVersion": "1",
        "backend": "google",
        "currency": "USD",
        "count": 1,
        "offset": 0,
        "nextCursor": None,
        "query": {
            "from": "SFO",
            "to": "BKK",
            "depart": "2027-05-12",
            "adults": 2,
            "cabin": "business",
        },
        "itineraries": [row],
    }
    transport = FakeCommand(body)
    adapter = GflyAdapter(evidence_root=tmp_path, transport=transport)
    capture = adapter.fetch(query, cursor=None, timeout_seconds=3, max_bytes=10000)
    assert transport.argv is not None
    assert transport.argv[transport.argv.index("--limit") + 1] == "0"
    page = adapter.parse(
        query, capture, airport_timezones={"SFO": "America/Los_Angeles", "BKK": "Asia/Bangkok"}
    )
    assert page.status == "completed"
    assert page.observations[0].airport_sequence == ("SFO", "NRT", "BKK")
    assert page.observations[0].legs == ()
    assert page.observations[0].price_scope == "unknown"
    assert page.observations[0].returned_travelers.state == "absent"
    assert page.observations[0].departure_instant == datetime(2027, 5, 12, 20, 30, tzinfo=UTC)
    truncated = dict(body, count=2, nextCursor="1")
    ref = EvidenceRef(
        sha256=evidence_sha256(truncated),
        relative_path="truncated.json",
        retrieved_at=datetime.now(UTC),
    )
    partial = adapter.parse(
        query,
        CapturedResponse(
            query_id=query.query_id,
            provider="gfly",
            status="completed",
            evidence=ref,
            body=cast(JsonValue, truncated),
            elapsed_seconds=0,
            byte_count=0,
        ),
        airport_timezones={},
    )
    assert partial.status == "partial"
    assert not partial.pair_coverage_exhaustive


def test_gfly_compatibility_launcher_is_in_command_prefix(tmp_path: Path) -> None:
    transport = FakeCommand({"schemaVersion": "1", "itineraries": [], "count": 0})
    adapter = GflyAdapter(
        evidence_root=tmp_path,
        transport=transport,
        executable="/private/tmp/gfly-live-py312/bin/python",
        wrapper="scripts/gfly_compat.py",
        provider_version="0.3.0+award-search-unpriced-v1",
    )
    adapter.fetch(_cash_query(), cursor=None, timeout_seconds=3, max_bytes=10000)
    assert transport.argv is not None
    assert list(transport.argv[:3]) == [
        "/private/tmp/gfly-live-py312/bin/python", "scripts/gfly_compat.py", "search"
    ]


def test_live_captured_gfly_success_and_schema_drift_replay(tmp_path: Path) -> None:
    success_path = PROVIDER_FIXTURES / "japan_sample.json"
    body = json.loads(success_path.read_text())
    query = _cash_query().model_copy(
        update={
            "origins": ("SFO",),
            "destinations": ("NRT",),
            "start_date": date(2027, 3, 10),
            "end_date": date(2027, 3, 10),
            "travelers": 2,
            "cabins": ("business",),
        }
    )
    evidence = EvidenceRef(
        sha256=evidence_sha256(body),
        relative_path=success_path.name,
        retrieved_at=datetime.now(UTC),
    )
    capture = CapturedResponse(
        query_id=query.query_id,
        provider="gfly",
        status="completed",
        evidence=evidence,
        body=cast(JsonValue, body),
        elapsed_seconds=1.398,
        byte_count=success_path.stat().st_size,
    )
    page = GflyAdapter(evidence_root=tmp_path).parse(
        query, capture, airport_timezones={"SFO": "America/Los_Angeles", "NRT": "Asia/Tokyo"}
    )
    assert page.status == "completed"
    assert len(page.observations) == body["count"] == 5
    assert all(item.price_scope == "unknown" for item in page.observations)

    # Exercise adapter handling of a provider schema change without retaining
    # the historical failing provider response in the reusable saved-search corpus.
    drift = {"schemaVersion": "unexpected", "backend": "google", "itineraries": []}
    drift_query = _cash_query().model_copy(
        update={
            "start_date": date(2027, 5, 15),
            "end_date": date(2027, 5, 15),
            "travelers": 1,
            "cabins": ("economy",),
        }
    )
    drift_capture = CapturedResponse(
        query_id=drift_query.query_id,
        provider="gfly",
        status="schema_drift",
        evidence=EvidenceRef(
            sha256=evidence_sha256(drift),
            relative_path="synthetic-schema-drift.json",
            retrieved_at=datetime.now(UTC),
        ),
        body=drift,
        elapsed_seconds=0.0,
        byte_count=len(json.dumps(drift).encode()),
    )
    drift_page = GflyAdapter(evidence_root=tmp_path).parse(
        drift_query, drift_capture, airport_timezones={}
    )
    assert drift_page.status == "schema_drift"
    assert not drift_page.observations


def test_live_captured_seats_business_scope_and_qatar_tax_state(tmp_path: Path) -> None:
    root = PROVIDER_FIXTURES
    adapter = SeatsAeroAdapter(api_key="test-only", evidence_root=tmp_path)
    mixed = json.loads((root / "mixed_exact__call-01.json").read_text())
    mixed_query = _award_query().model_copy(
        update={
            "start_date": date(2026, 10, 5),
            "end_date": date(2026, 10, 5),
            "travelers": 1,
            "cabins": (),
        }
    )
    mixed_capture = CapturedResponse(
        query_id=mixed_query.query_id,
        provider="seats_aero",
        status="completed",
        evidence=EvidenceRef(
            sha256=evidence_sha256(mixed),
            relative_path="mixed_exact__call-01.json",
            retrieved_at=datetime.now(UTC),
        ),
        body=mixed,
        elapsed_seconds=0.2,
        byte_count=100,
    )
    mixed_page = adapter.parse(mixed_query, mixed_capture, airport_timezones={})
    assert mixed_page.status == "completed"
    assert mixed_page.returned_row_count == 3
    assert mixed_page.observations
    assert {item.cabin.value for item in mixed_page.observations} == {"economy", "premium_economy"}

    qatar = json.loads((root / "qatar_jfk_doh__call-01.json").read_text())
    qatar_query = _award_query().model_copy(
        update={
            "origins": ("JFK",),
            "destinations": ("DOH",),
            "start_date": date(2027, 5, 12),
            "end_date": date(2027, 5, 14),
        }
    )
    qatar_capture = CapturedResponse(
        query_id=qatar_query.query_id,
        provider="seats_aero",
        status="completed",
        evidence=EvidenceRef(
            sha256=evidence_sha256(qatar),
            relative_path="qatar_jfk_doh__call-01.json",
            retrieved_at=datetime.now(UTC),
        ),
        body=qatar,
        elapsed_seconds=0.2,
        byte_count=100,
    )
    qatar_page = adapter.parse(qatar_query, qatar_capture, airport_timezones={})
    assert qatar_page.status == "completed"
    assert len(qatar_page.observations) == 2
    first = qatar_page.observations[0]
    assert first.program.value == "qatar"
    assert first.taxes_fees.state == "unknown"
    assert first.raw_fields["JTotalTaxes"].state == "value"
    assert first.raw_fields["JTotalTaxes"].value == 0
    assert first.points.value == 140000
    assert first.raw_fields["JMileageCost"].value == "140000"
    assert first.seats.state == "unknown"
    assert first.raw_fields["JRemainingSeats"].value == 5
    assert any(f.code == "seats_program_unsupported" for f in first.findings)
    assert any(f.code == "taxes_program_unavailable" for f in first.findings)

    japan = json.loads((root / "japan_lax_hnd__call-01.json").read_text())
    japan_query = _award_query().model_copy(
        update={
            "origins": ("LAX",),
            "destinations": ("HND",),
            "start_date": date(2027, 3, 10),
            "end_date": date(2027, 3, 12),
        }
    )
    japan_capture = CapturedResponse(
        query_id=japan_query.query_id,
        provider="seats_aero",
        status="completed",
        evidence=EvidenceRef(
            sha256=evidence_sha256(japan),
            relative_path="japan_lax_hnd__call-01.json",
            retrieved_at=datetime.now(UTC),
        ),
        body=japan,
        elapsed_seconds=0.2,
        byte_count=100,
    )
    japan_page = adapter.parse(japan_query, japan_capture, airport_timezones={})
    assert japan_page.status == "completed"
    assert len(japan_page.observations) == 3
    assert japan_page.observations[0].taxes_fees.value == 125400
    assert japan_page.observations[0].taxes_fees_unit == "minor"
    assert japan_page.observations[0].tax_currency.value == "USD"


def test_live_seats_first_page_advances_skip_with_original_cursor(tmp_path: Path) -> None:
    path = PROVIDER_FIXTURES / "whole_month_pages__call-01.json"
    body = json.loads(path.read_text())
    query = _award_query().model_copy(
        update={
            "start_date": date(2027, 5, 1),
            "end_date": date(2027, 5, 31),
            "cabins": (),
            "travelers": 1,
            "page_size": 20,
        }
    )
    capture = CapturedResponse(
        query_id=query.query_id,
        provider="seats_aero",
        status="completed",
        evidence=EvidenceRef(
            sha256=evidence_sha256(body), relative_path=path.name, retrieved_at=datetime.now(UTC)
        ),
        body=body,
        elapsed_seconds=0.185,
        byte_count=63569,
    )
    page = SeatsAeroAdapter(api_key="test-only", evidence_root=tmp_path).parse(
        query, capture, airport_timezones={}
    )
    assert page.status == "completed"
    assert page.more
    assert page.returned_row_count == 20
    assert page.next_cursor is not None
    assert json.loads(page.next_cursor) == {"first_cursor": body["cursor"], "skip": 20}
    assert "skip=20" in body["moreURL"]


def test_live_qatar_inline_is_summary_only_and_get_trips_has_segments(tmp_path: Path) -> None:
    root = PROVIDER_FIXTURES
    inline = json.loads((root / "qatar_inline_trips__call-01.json").read_text())
    query = _award_query().model_copy(
        update={
            "origins": ("JFK",),
            "destinations": ("DOH",),
            "start_date": date(2027, 5, 12),
            "end_date": date(2027, 5, 14),
            "include_trips": True,
        }
    )
    adapter = SeatsAeroAdapter(api_key="test-only", evidence_root=tmp_path)
    inline_capture = CapturedResponse(
        query_id=query.query_id,
        provider="seats_aero",
        status="completed",
        evidence=EvidenceRef(
            sha256=evidence_sha256(inline),
            relative_path="qatar_inline_trips__call-01.json",
            retrieved_at=datetime.now(UTC),
        ),
        body=inline,
        elapsed_seconds=0.2,
        byte_count=100,
    )
    inline_page = adapter.parse(
        query, inline_capture, airport_timezones={"JFK": "America/New_York", "DOH": "Asia/Qatar"}
    )
    assert inline_page.status == "completed"
    assert len(inline_page.observations) == 2
    assert all(item.kind == "award_summary" for item in inline_page.observations)
    assert all(
        any(f.code == "inline_trip_segments_unavailable" for f in item.findings)
        for item in inline_page.observations
    )

    detail = json.loads((root / "qatar_get_trips__call-01.json").read_text())
    detail_query = query.model_copy(
        update={
            "role": "award_detail",
            "detail_id": inline["data"][0]["ID"],
            "include_trips": False,
        }
    )
    detail_capture = CapturedResponse(
        query_id=detail_query.query_id,
        provider="seats_aero",
        status="completed",
        evidence=EvidenceRef(
            sha256=evidence_sha256(detail),
            relative_path="qatar_get_trips__call-01.json",
            retrieved_at=datetime.now(UTC),
        ),
        body=detail,
        elapsed_seconds=0.2,
        byte_count=100,
    )
    detail_page = adapter.parse(
        detail_query,
        detail_capture,
        airport_timezones={"JFK": "America/New_York", "DOH": "Asia/Qatar"},
    )
    assert detail_page.status == "completed"
    assert detail_page.returned_row_count == 3
    assert len(detail_page.observations) == 1  # Two economy trips are outside requested cabin.
    business = detail_page.observations[0]
    assert business.cabin.value == "business"
    assert len(business.legs) == 1
    assert business.legs[0].flight_number.value == "QR704"
    assert business.taxes_fees.state == "unknown"
    assert business.raw_fields["TotalTaxes"].value == 0

    mismatched = json.loads(json.dumps(detail))
    mismatched["data"][2]["AvailabilityID"] = "other-availability"
    mismatch_capture = detail_capture.model_copy(
        update={
            "body": mismatched,
            "evidence": detail_capture.evidence.model_copy(
                update={"sha256": evidence_sha256(mismatched)}
            ),
        }
    )
    mismatch_page = adapter.parse(
        detail_query,
        mismatch_capture,
        airport_timezones={"JFK": "America/New_York", "DOH": "Asia/Qatar"},
    )
    assert mismatch_page.status == "partial"
    assert mismatch_page.observations == ()
    assert any("parent availability" in f.message for f in mismatch_page.findings)


def test_live_seats_five_page_stream_has_complete_unique_rows(tmp_path: Path) -> None:
    root = PROVIDER_FIXTURES
    query = _award_query().model_copy(
        update={
            "start_date": date(2027, 5, 1),
            "end_date": date(2027, 5, 31),
            "cabins": (),
            "travelers": 1,
            "page_size": 20,
        }
    )
    adapter = SeatsAeroAdapter(api_key="test-only", evidence_root=tmp_path)
    cursor: str | None = None
    all_ids: list[str] = []
    sizes: list[int] = []
    first_cursor: int | None = None
    for page_number in range(1, 6):
        path = root / f"whole_month_pages__call-{page_number:02d}.json"
        body = json.loads(path.read_text())
        capture = CapturedResponse(
            query_id=query.query_id,
            provider="seats_aero",
            status="completed",
            evidence=EvidenceRef(
                sha256=evidence_sha256(body),
                relative_path=path.name,
                retrieved_at=datetime.now(UTC),
            ),
            body=body,
            elapsed_seconds=0.2,
            byte_count=path.stat().st_size,
            cursor=cursor,
        )
        page = adapter.parse(query, capture, airport_timezones={})
        assert page.status == "completed"
        sizes.append(page.returned_row_count)
        all_ids.extend(page.provider_row_ids)
        if page_number == 1:
            first_cursor = body["cursor"]
        if page_number < 5:
            assert page.more
            assert page.next_cursor is not None
            assert json.loads(page.next_cursor) == {
                "first_cursor": first_cursor,
                "skip": 20 * page_number,
            }
            cursor = page.next_cursor
        else:
            assert not page.more
            assert page.pair_coverage_exhaustive
    assert sizes == [20, 20, 20, 20, 13]
    assert len(all_ids) == len(set(all_ids)) == 93


def test_seats_off_query_and_bad_record_trigger_schema_drift(tmp_path: Path) -> None:
    valid = {
        "ID": "a",
        "Route": {"OriginAirport": "SFO", "DestinationAirport": "BKK"},
        "Date": "2027-05-12",
        "Source": "aeroplan",
        "JAvailable": True,
        "JMileageCost": "75000",
        "JRemainingSeats": 1,
    }
    invalid = dict(valid, ID="b", Date="2027-05-13")
    transport = FakeHttp({"data": [valid, invalid, {"ID": "c"}], "hasMore": False})
    adapter = SeatsAeroAdapter(api_key="test-only", evidence_root=tmp_path, transport=transport)
    query = _award_query()
    page = adapter.parse(
        query,
        adapter.fetch(query, cursor=None, timeout_seconds=2, max_bytes=10000),
        airport_timezones={},
    )
    assert page.status == "schema_drift"
    assert page.returned_row_count == 3
    assert len(page.observations) == 1
    assert not page.pair_coverage_exhaustive
    assert any(f.code == "seats_below_travelers" for f in page.observations[0].findings)
    assert len(page.findings) == 2


def test_nonfinite_provider_numbers_fail_explicitly(tmp_path: Path) -> None:
    row = {
        "ID": "bad-price",
        "Route": {"OriginAirport": "SFO", "DestinationAirport": "BKK"},
        "Date": "2027-05-12",
        "Source": "aeroplan",
        "JAvailable": True,
        "JMileageCost": "NaN",
        "JRemainingSeats": 2,
    }
    adapter = SeatsAeroAdapter(
        api_key="test-only",
        evidence_root=tmp_path,
        transport=FakeHttp({"data": [row], "hasMore": False}),
    )
    query = _award_query()
    page = adapter.parse(
        query,
        adapter.fetch(query, cursor=None, timeout_seconds=2, max_bytes=10000),
        airport_timezones={},
    )
    assert page.status == "schema_drift"
    assert page.observations == ()

    cash = GflyAdapter(evidence_root=tmp_path, transport=FakeCommand({"price": float("nan")}))
    capture = cash.fetch(_cash_query(), cursor=None, timeout_seconds=2, max_bytes=10000)
    assert capture.status == "malformed"
    assert isinstance(capture.body, dict)
    assert "unparsed_response_sample" in capture.body


def test_gfly_dst_ambiguity_keeps_local_time_without_inventing_instant(tmp_path: Path) -> None:
    query = ProviderQuery(
        query_id="dst",
        provider="gfly",
        role="direct_cash",
        origins=("JFK",),
        destinations=("LAX",),
        start_date=date(2027, 11, 7),
        end_date=date(2027, 11, 7),
        travelers=1,
        cabins=("economy",),
    )
    body = {
        "schemaVersion": "1",
        "backend": "google",
        "currency": "USD",
        "count": 1,
        "offset": 0,
        "nextCursor": None,
        "query": {
            "from": "JFK",
            "to": "LAX",
            "depart": "2027-11-07",
            "adults": 1,
            "cabin": "economy",
        },
        "itineraries": [
            {
                "origin": "JFK",
                "destination": "LAX",
                "departure": "2027-11-07T01:30:00",
                "arrival": "2027-11-07T06:00:00",
                "price": 100,
                "currency": "USD",
            }
        ],
    }
    evidence = EvidenceRef(
        sha256=evidence_sha256(body), relative_path="dst.json", retrieved_at=datetime.now(UTC)
    )
    capture = CapturedResponse(
        query_id="dst",
        provider="gfly",
        status="completed",
        evidence=evidence,
        body=cast(JsonValue, body),
        elapsed_seconds=1,
        byte_count=100,
    )
    page = GflyAdapter(evidence_root=tmp_path).parse(
        query, capture, airport_timezones={"JFK": "America/New_York", "LAX": "America/Los_Angeles"}
    )
    assert page.status == "completed"
    assert page.observations[0].departure_local == "2027-11-07T01:30:00"
    assert page.observations[0].departure_instant is None
    assert any(f.code == "gfly_time_unknown" for f in page.observations[0].findings)
