"""Seats.aero Cached Search and Get Trips adapter.

One fetch is one HTTP request. The caller owns pagination, resource accounting,
and any decision to retrieve trip details.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from pydantic import JsonValue

from award_agent.providers.contracts import (
    CapturedResponse,
    EvidenceRef,
    ObservedLeg,
    Outcome,
    ParsedProviderPage,
    ProviderObservation,
    ProviderQuery,
    RawField,
    ValidationFinding,
    content_digest,
)
from award_agent.providers.evidence import (
    sanitize_provider_payload,
    sanitized_failure_sample,
    write_immutable_evidence,
)
from award_agent.providers.transport import HttpTransport, HttpxTransport, TransportLimitError
from award_agent.search_planning.contracts import FilterObligationKind

_BASE_URL = "https://seats.aero/partnerapi"
_CABINS = {"economy": "Y", "premium_economy": "W", "business": "J", "first": "F"}
_TAX_UNAVAILABLE_PROGRAMS = frozenset({"qatar", "turkish", "singapore"})
_SEAT_UNSUPPORTED_PROGRAMS = frozenset(
    {"emirates", "qantas", "connectmiles", "azul", "qatar", "turkish", "singapore", "frontier"}
)


def _field(row: Mapping[str, Any], key: str) -> RawField:
    value = RawField.from_mapping(row, key)
    if value.state == "value" and value.value in ("", "unknown", "Unknown"):
        return RawField(state="unknown", source_field=key)
    return value


def _split_carriers(value: Any) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _nonnegative_field(row: Mapping[str, Any], key: str) -> RawField:
    field = _field(row, key)
    if field.state != "value":
        return field
    value = field.value
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError(f"{key} must be a nonnegative number")
    try:
        numeric = Decimal(str(value))
    except InvalidOperation as exc:
        raise TypeError(f"{key} must be a nonnegative number") from exc
    if not numeric.is_finite() or numeric != numeric.to_integral_value():
        raise TypeError(f"{key} must be a finite integer")
    if numeric < 0:
        raise ValueError(f"{key} must be nonnegative")
    return RawField(state="value", value=int(numeric), source_field=key)


def _local_instant(
    value: Any, airport: str, timezones: Mapping[str, str]
) -> tuple[str | None, datetime | None, str | None]:
    if not isinstance(value, str) or not value:
        return None, None, timezones.get(airport)
    tz_name = timezones.get(airport)
    if not tz_name:
        return value, None, None
    try:
        zone = ZoneInfo(tz_name)
        # Seats.aero documents airport-local times despite examples ending in Z.
        naive = datetime.fromisoformat(value.removesuffix("Z")).replace(tzinfo=None)
        aware = naive.replace(tzinfo=zone)
        if aware.utcoffset() != naive.replace(tzinfo=zone, fold=1).utcoffset():
            return value, None, tz_name
        if aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive:
            return value, None, tz_name
        return value, aware.astimezone(UTC), tz_name
    except (ValueError, ZoneInfoNotFoundError):
        return value, None, tz_name


def _pagination(cursor: str | None) -> tuple[int | None, int]:
    if cursor is None:
        return None, 0
    try:
        parsed = json.loads(cursor)
        first = parsed["first_cursor"]
        skip = parsed["skip"]
        if type(first) is not int or type(skip) is not int or first < 0 or skip < 1:
            raise ValueError
        return first, skip
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("invalid Seats.aero page cursor") from exc


def _trip_in_scope(query: ProviderQuery, row: Mapping[str, Any]) -> bool:
    if query.cabins and row.get("Cabin") not in query.cabins:
        return False
    for obligation in query.filters:
        if (
            obligation.kind == FilterObligationKind.DIRECT_FLIGHT_AVAILABLE
            and row.get("Stops") != 0
        ):
            return False
        if (
            obligation.kind == FilterObligationKind.CABIN_AVAILABLE_IN
            and row.get("Cabin") not in obligation.values
        ):
            return False
        if (
            obligation.kind == FilterObligationKind.REDEMPTION_PROGRAM_IN
            and row.get("Source") not in obligation.values
        ):
            return False
        if obligation.kind == FilterObligationKind.CARRIER_INVOLVEMENT_MATCH:
            carriers = set(_split_carriers(row.get("Carriers")))
            if not carriers.intersection(value.upper() for value in obligation.values):
                return False
        if obligation.kind == FilterObligationKind.MIN_REPORTED_CABIN_DISTANCE_PERCENT:
            below_pct = row.get("MixedCabinPct", 0)
            if not isinstance(below_pct, int) or 100 - below_pct < int(obligation.values[0]):
                return False
    return True


class SeatsAeroAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        evidence_root: Path,
        transport: HttpTransport | None = None,
        provider_version: str = "cached-search-v1",
    ) -> None:
        if not api_key:
            raise ValueError("Seats.aero Partner-Authorization is required")
        self._api_key = api_key
        self._root = evidence_root
        self._transport = transport or HttpxTransport()
        self._version = provider_version

    def fetch(
        self,
        query: ProviderQuery,
        *,
        cursor: str | None,
        timeout_seconds: float,
        max_bytes: int,
    ) -> CapturedResponse:
        if query.provider != "seats_aero":
            raise ValueError("Seats.aero adapter received a non-award query")
        retrieved = datetime.now(UTC)
        started = time.monotonic()
        first_cursor, skip = _pagination(cursor)
        params: dict[str, str | int | bool] = {}
        if query.role == "award_detail":
            if cursor is not None:
                raise ValueError("Get Trips is not a paginated operation")
            url = f"{_BASE_URL}/trips/{query.detail_id}"
            for obligation in query.filters:
                if obligation.kind == FilterObligationKind.MIN_REPORTED_CABIN_DISTANCE_PERCENT:
                    params["min_cabin_pct"] = int(obligation.values[0])
        else:
            url = f"{_BASE_URL}/search"
            params = {
                "origin_airport": ",".join(query.origins),
                "destination_airport": ",".join(query.destinations),
                "start_date": query.start_date.isoformat(),
                "end_date": query.end_date.isoformat(),
                "take": query.page_size,
                "include_trips": query.include_trips,
            }
            if query.cabins:
                params["cabins"] = ",".join(query.cabins)
            if first_cursor is not None:
                params["cursor"] = first_cursor
                params["skip"] = skip
            for obligation in query.filters:
                if obligation.kind == FilterObligationKind.CABIN_AVAILABLE_IN:
                    params["cabins"] = ",".join(obligation.values)
                elif obligation.kind == FilterObligationKind.DIRECT_FLIGHT_AVAILABLE:
                    params["only_direct_flights"] = True
                elif obligation.kind == FilterObligationKind.CARRIER_INVOLVEMENT_MATCH:
                    params["carriers"] = ",".join(obligation.values).upper()
                elif obligation.kind == FilterObligationKind.REDEMPTION_PROGRAM_IN:
                    params["sources"] = ",".join(obligation.values)
                elif obligation.kind == FilterObligationKind.MIN_REPORTED_CABIN_DISTANCE_PERCENT:
                    params["min_cabin_pct"] = int(obligation.values[0])
                else:
                    raise ValueError(f"unsupported Seats.aero filter {obligation.kind}")
        try:
            response = self._transport.get(
                url,
                params=params,
                headers={"Partner-Authorization": self._api_key},
                timeout_seconds=timeout_seconds,
                max_response_bytes=max_bytes,
            )
            status = (
                "completed"
                if response.status_code == 200
                else "rate_limited"
                if response.status_code == 429
                else "blocked"
                if response.status_code in (401, 403)
                else "failed"
            )
            try:
                body = json.loads(response.body)
                sanitized = sanitize_provider_payload(body, secret_values=(self._api_key,))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
                sanitized = sanitize_provider_payload(
                    sanitized_failure_sample(response.body, truncated=False),
                    secret_values=(self._api_key,),
                )
                if status == "completed":
                    status = "malformed"
            path, digest = write_immutable_evidence(self._root, sanitized)
            return CapturedResponse(
                query_id=query.query_id,
                provider="seats_aero",
                status=cast(Outcome, status),
                evidence=EvidenceRef(
                    sha256=digest, relative_path=path.name, retrieved_at=retrieved
                ),
                body=sanitized,
                http_status=response.status_code,
                elapsed_seconds=response.elapsed_seconds,
                byte_count=len(response.body),
                error_code=None if status == "completed" else status,
                cursor=cursor,
            )
        except (httpx.TimeoutException, TimeoutError):
            status, code, consumed, sample = "timeout", "timeout", 0, b""
        except TransportLimitError as exc:
            status, code, consumed, sample = (
                "budget_exhausted",
                "byte_budget",
                exc.observed_bytes,
                exc.sample,
            )
        except httpx.HTTPError:
            status, code, consumed, sample = "failed", "transport_error", 0, b""
        error_body: dict[str, JsonValue] = {"transport_error": code, "observed_bytes": consumed}
        if sample:
            error_body.update(
                cast(dict[str, JsonValue], sanitized_failure_sample(sample, truncated=True))
            )
        error_body = cast(
            dict[str, JsonValue],
            sanitize_provider_payload(error_body, secret_values=(self._api_key,)),
        )
        path, digest = write_immutable_evidence(self._root, error_body)
        return CapturedResponse(
            query_id=query.query_id,
            provider="seats_aero",
            status=cast(Outcome, status),
            evidence=EvidenceRef(sha256=digest, relative_path=path.name, retrieved_at=retrieved),
            body=error_body,
            elapsed_seconds=time.monotonic() - started,
            byte_count=consumed,
            error_code=code,
            cursor=cursor,
        )

    def parse(
        self,
        query: ProviderQuery,
        capture: CapturedResponse,
        *,
        airport_timezones: Mapping[str, str],
    ) -> ParsedProviderPage:
        if capture.query_id != query.query_id or capture.provider != "seats_aero":
            raise ValueError("captured response does not belong to this Seats.aero query")
        if capture.status != "completed":
            return ParsedProviderPage(query_id=query.query_id, status=capture.status)
        body = capture.body
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            return ParsedProviderPage(
                query_id=query.query_id,
                status="schema_drift",
                findings=(
                    ValidationFinding(
                        code="seats_schema", severity="error", message="missing data array"
                    ),
                ),
            )
        body = cast(dict[str, Any], body)
        rows = cast(list[Any], body["data"])
        if query.role == "award_detail":
            more, next_cursor = False, None
        else:
            more_value = body.get("hasMore")
            if type(more_value) is not bool:
                return ParsedProviderPage(
                    query_id=query.query_id,
                    status="schema_drift",
                    findings=(
                        ValidationFinding(
                            code="seats_pagination",
                            severity="error",
                            message="missing hasMore boolean",
                        ),
                    ),
                )
            more = more_value
            next_cursor = None
            if more:
                first, skip = _pagination(capture.cursor)
                first = cast(int | None, body.get("cursor")) if first is None else first
                if type(first) is not int or not rows:
                    return ParsedProviderPage(
                        query_id=query.query_id,
                        status="schema_drift",
                        findings=(
                            ValidationFinding(
                                code="seats_cursor",
                                severity="error",
                                message="invalid continuation cursor",
                            ),
                        ),
                    )
                next_cursor = json.dumps(
                    {"first_cursor": first, "skip": skip + len(rows)}, sort_keys=True
                )
        observations: list[ProviderObservation] = []
        findings: list[ValidationFinding] = []
        ids: list[str] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or not isinstance(row.get("ID"), str):
                findings.append(
                    ValidationFinding(
                        code="seats_row_schema", severity="error", message=f"row {index} missing ID"
                    )
                )
                continue
            ids.append(cast(str, row["ID"]))
            try:
                if query.role == "award_detail":
                    if _trip_in_scope(query, row):
                        observations.append(
                            self._trip_observation(query, capture, row, airport_timezones)
                        )
                else:
                    observations.extend(
                        self._summary_observations(query, capture, row, airport_timezones)
                    )
                    if query.include_trips and isinstance(row.get("AvailabilityTrips"), list):
                        for trip in row["AvailabilityTrips"]:
                            if (
                                isinstance(trip, dict)
                                and _trip_in_scope(query, trip)
                                and isinstance(trip.get("AvailabilitySegments"), list)
                                and bool(trip["AvailabilitySegments"])
                            ):
                                observations.append(
                                    self._trip_observation(
                                        query, capture, trip, airport_timezones, parent=row
                                    )
                                )
            except (KeyError, TypeError) as exc:
                findings.append(
                    ValidationFinding(
                        code="seats_row_schema", severity="error", message=f"row {index}: {exc}"
                    )
                )
            except ValueError as exc:
                findings.append(
                    ValidationFinding(
                        code="seats_row_invalid", severity="error", message=f"row {index}: {exc}"
                    )
                )
        schema_failed = any(item.code == "seats_row_schema" for item in findings)
        status: Outcome = (
            "schema_drift"
            if schema_failed
            else ("partial" if findings else ("empty" if not rows and not more else "completed"))
        )
        return ParsedProviderPage(
            query_id=query.query_id,
            status=status,
            observations=tuple(observations),
            more=more,
            next_cursor=next_cursor,
            returned_row_count=len(rows),
            provider_row_ids=tuple(ids),
            findings=tuple(findings),
            pair_coverage_exhaustive=(
                len(query.origins) == 1
                and len(query.destinations) == 1
                and query.role != "award_detail"
                and not more
                and not findings
            ),
        )

    def _summary_observations(
        self,
        query: ProviderQuery,
        capture: CapturedResponse,
        row: Mapping[str, Any],
        airport_timezones: Mapping[str, str],
    ) -> list[ProviderObservation]:
        route = row.get("Route")
        if not isinstance(route, dict):
            raise TypeError("missing Route object")
        origin, destination = route.get("OriginAirport"), route.get("DestinationAirport")
        if not isinstance(origin, str) or not isinstance(destination, str):
            raise TypeError("missing route airports")
        if origin not in query.origins or destination not in query.destinations:
            raise ValueError("route airports outside physical query")
        departure = row.get("Date")
        if not isinstance(departure, str):
            raise TypeError("missing departure date")
        departure_date = date.fromisoformat(departure)
        if not query.start_date <= departure_date <= query.end_date:
            raise ValueError("departure date outside query")
        program = row.get("Source")
        if not isinstance(program, str) or not program:
            raise ValueError("missing mileage program")
        output: list[ProviderObservation] = []
        for cabin, prefix in _CABINS.items():
            if row.get(prefix + "Available") is not True:
                continue
            if query.cabins and cabin not in query.cabins:
                continue
            if (
                any(ob.kind == FilterObligationKind.DIRECT_FLIGHT_AVAILABLE for ob in query.filters)
                and row.get(prefix + "Direct") is not True
            ):
                continue
            raw_seats = _nonnegative_field(row, prefix + "RemainingSeats")
            seats = (
                RawField(state="unknown", source_field=prefix + "RemainingSeats")
                if program in _SEAT_UNSUPPORTED_PROGRAMS
                else raw_seats
            )
            points = _nonnegative_field(row, prefix + "MileageCost")
            raw_taxes = _nonnegative_field(row, prefix + "TotalTaxes")
            taxes = (
                RawField(state="unknown", source_field=prefix + "TotalTaxes")
                if program in _TAX_UNAVAILABLE_PROGRAMS
                else raw_taxes
            )
            notes: list[ValidationFinding] = []
            if program in _SEAT_UNSUPPORTED_PROGRAMS:
                notes.append(
                    ValidationFinding(
                        code="seats_program_unsupported",
                        severity="unknown",
                        message="program does not supply reliable seat-count evidence",
                        field="seats",
                    )
                )
            elif seats.state == "value" and cast(int, seats.value) == 0:
                notes.append(
                    ValidationFinding(
                        code="seats_zero_ambiguous",
                        severity="unknown",
                        message="zero may mean seat count is unavailable",
                        field="seats",
                    )
                )
            elif seats.state == "value" and cast(int, seats.value) < query.travelers:
                notes.append(
                    ValidationFinding(
                        code="seats_below_travelers",
                        severity="warning",
                        message="reported seats are below requested travelers",
                        field="seats",
                    )
                )
            elif seats.state in ("absent", "null", "unknown"):
                notes.append(
                    ValidationFinding(
                        code="seats_unknown",
                        severity="unknown",
                        message="seat count is unavailable",
                        field="seats",
                    )
                )
            if points.state in ("absent", "null", "unknown"):
                notes.append(
                    ValidationFinding(
                        code="points_unknown",
                        severity="unknown",
                        message="mileage cost is unavailable",
                        field="points",
                    )
                )
            if query.include_trips and any(
                isinstance(trip, dict)
                and _trip_in_scope(query, trip)
                and not trip.get("AvailabilitySegments")
                for trip in (row.get("AvailabilityTrips") or [])
            ):
                notes.append(
                    ValidationFinding(
                        code="inline_trip_segments_unavailable",
                        severity="unknown",
                        message="inline trip lacks flight segments; detail retrieval is needed",
                        field="legs",
                    )
                )
            if program in _TAX_UNAVAILABLE_PROGRAMS:
                notes.append(
                    ValidationFinding(
                        code="taxes_program_unavailable",
                        severity="unknown",
                        message="program does not supply reliable taxes and fees",
                        field="taxes_fees",
                    )
                )
            elif taxes.state in ("absent", "null", "unknown"):
                notes.append(
                    ValidationFinding(
                        code="taxes_unknown",
                        severity="unknown",
                        message="summary taxes and fees are unavailable",
                        field="taxes_fees",
                    )
                )
            output.append(
                ProviderObservation(
                    observation_id=content_digest(
                        {
                            "query": query.query_id,
                            "row": row,
                            "cabin": cabin,
                            "evidence": capture.evidence.sha256,
                            "retrieved_at": capture.evidence.retrieved_at.isoformat(),
                        }
                    ),
                    provider="seats_aero",
                    backend="partnerapi",
                    provider_version=self._version,
                    kind="award_summary",
                    query_id=query.query_id,
                    logical_query_ids=query.logical_query_ids,
                    logical_use_ids=query.logical_use_ids,
                    strategy_ids=query.strategy_ids,
                    provider_record_id=row["ID"],
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    airport_sequence=(origin, destination),
                    retrieved_at=capture.evidence.retrieved_at,
                    provider_updated_at=_field(row, "UpdatedAt"),
                    requested_travelers=query.travelers,
                    requested_cabins=query.cabins,
                    cabin=RawField(state="value", value=cabin, source_field=prefix + "Available"),
                    program=_field(row, "Source"),
                    points=points,
                    taxes_fees=taxes,
                    taxes_fees_unit="minor" if taxes.state == "value" else "unknown",
                    tax_currency=_field(row, "TaxesCurrency"),
                    seats=seats,
                    carriers=_split_carriers(row.get(prefix + "Airlines")),
                    evidence=(capture.evidence,),
                    findings=tuple(notes),
                    raw_fields={
                        key: _field(row, key)
                        for key in (
                            prefix + "Available",
                            prefix + "Direct",
                            prefix + "RemainingSeats",
                            prefix + "MileageCost",
                            prefix + "TotalTaxes",
                            prefix + "TotalTaxesRaw",
                            prefix + "RemainingSeatsRaw",
                            prefix + "Airlines",
                            "AvailabilityTrips",
                        )
                    },
                )
            )
        return output

    def _trip_observation(
        self,
        query: ProviderQuery,
        capture: CapturedResponse,
        row: Mapping[str, Any],
        airport_timezones: Mapping[str, str],
        *,
        parent: Mapping[str, Any] | None = None,
    ) -> ProviderObservation:
        if not isinstance(row, dict):
            raise TypeError("trip is not an object")
        segments = row.get("AvailabilitySegments")
        if segments is None:
            segments = []
        if not isinstance(segments, list):
            raise TypeError("trip AvailabilitySegments is not a list")
        legs: list[ObservedLeg] = []
        findings: list[ValidationFinding] = []
        if not segments:
            findings.append(
                ValidationFinding(
                    code="trip_segments_unavailable",
                    severity="unknown",
                    message="provider returned an itinerary without flight segments",
                    field="legs",
                )
            )
        for segment in segments:
            if not isinstance(segment, dict):
                raise TypeError("invalid trip segment")
            origin, destination = segment.get("OriginAirport"), segment.get("DestinationAirport")
            if not isinstance(origin, str) or not isinstance(destination, str):
                raise TypeError("trip segment lacks airport codes")
            departure_local, departure_instant, origin_tz = _local_instant(
                segment.get("DepartsAt"), origin, airport_timezones
            )
            arrival_local, arrival_instant, destination_tz = _local_instant(
                segment.get("ArrivesAt"), destination, airport_timezones
            )
            if departure_instant is None or arrival_instant is None:
                findings.append(
                    ValidationFinding(
                        code="trip_time_unknown",
                        severity="unknown",
                        message="trip instant could not be derived from airport-local time",
                    )
                )
            elif arrival_instant < departure_instant:
                raise ValueError("trip segment arrives before departure")
            if legs and (
                legs[-1].destination != origin
                or (
                    legs[-1].arrival_instant is not None
                    and departure_instant is not None
                    and departure_instant < legs[-1].arrival_instant
                )
            ):
                raise ValueError("trip segments are discontinuous or reverse chronological")
            legs.append(
                ObservedLeg(
                    origin=origin,
                    destination=destination,
                    departure_local=departure_local,
                    arrival_local=arrival_local,
                    departure_instant=departure_instant,
                    arrival_instant=arrival_instant,
                    origin_timezone=origin_tz,
                    destination_timezone=destination_tz,
                    flight_number=_field(segment, "FlightNumber"),
                )
            )
        origin = legs[0].origin if legs else row.get("OriginAirport")
        destination = legs[-1].destination if legs else row.get("DestinationAirport")
        if not isinstance(origin, str) or not isinstance(destination, str):
            raise TypeError("trip lacks endpoint airports")
        if origin not in query.origins or destination not in query.destinations:
            raise ValueError("trip airports outside physical query")
        departure_local, departure_instant, origin_tz = _local_instant(
            row.get("DepartsAt"), origin, airport_timezones
        )
        arrival_local, arrival_instant, destination_tz = _local_instant(
            row.get("ArrivesAt"), destination, airport_timezones
        )
        if (
            departure_instant is not None
            and arrival_instant is not None
            and arrival_instant < departure_instant
        ):
            raise ValueError("trip itinerary arrives before departure")
        if departure_instant is None or arrival_instant is None:
            findings.append(
                ValidationFinding(
                    code="trip_envelope_time_unknown",
                    severity="unknown",
                    message="itinerary instant could not be derived from airport-local time",
                )
            )
        if legs and (
            legs[0].origin != origin
            or legs[-1].destination != destination
            or (
                departure_instant is not None
                and legs[0].departure_instant is not None
                and departure_instant != legs[0].departure_instant
            )
            or (
                arrival_instant is not None
                and legs[-1].arrival_instant is not None
                and arrival_instant != legs[-1].arrival_instant
            )
        ):
            raise ValueError("trip itinerary envelope differs from segments")
        departure_date = date.fromisoformat(departure_local[:10]) if departure_local else None
        if departure_date is not None and not query.start_date <= departure_date <= query.end_date:
            raise ValueError("trip departs outside query window")
        sequence = (
            (origin,) + tuple(leg.destination for leg in legs) if legs else (origin, destination)
        )
        if query.role == "award_detail" and row.get("AvailabilityID") != query.detail_id:
            raise ValueError("trip parent availability differs from detail request")
        program = _field(row, "Source")
        if program.state == "absent" and parent is not None:
            program = _field(parent, "Source")
        points = _nonnegative_field(row, "MileageCost")
        raw_seats = _nonnegative_field(row, "RemainingSeats")
        seats = (
            RawField(state="unknown", source_field="RemainingSeats")
            if program.state == "value" and program.value in _SEAT_UNSUPPORTED_PROGRAMS
            else raw_seats
        )
        raw_taxes = _nonnegative_field(row, "TotalTaxes")
        taxes = (
            RawField(state="unknown", source_field="TotalTaxes")
            if program.state == "value" and program.value in _TAX_UNAVAILABLE_PROGRAMS
            else raw_taxes
        )
        if program.state == "value" and program.value in _SEAT_UNSUPPORTED_PROGRAMS:
            findings.append(
                ValidationFinding(
                    code="seats_program_unsupported",
                    severity="unknown",
                    message="program does not supply reliable seat-count evidence",
                    field="seats",
                )
            )
        elif seats.state == "value" and cast(int, seats.value) == 0:
            findings.append(
                ValidationFinding(
                    code="seats_zero_ambiguous",
                    severity="unknown",
                    message="zero may mean seat count is unavailable",
                    field="seats",
                )
            )
        elif seats.state == "value" and cast(int, seats.value) < query.travelers:
            findings.append(
                ValidationFinding(
                    code="seats_below_travelers",
                    severity="warning",
                    message="reported seats are below requested travelers",
                    field="seats",
                )
            )
        elif seats.state in ("absent", "null", "unknown"):
            findings.append(
                ValidationFinding(
                    code="seats_unknown",
                    severity="unknown",
                    message="seat count is unavailable",
                    field="seats",
                )
            )
        if program.state == "value" and program.value in _TAX_UNAVAILABLE_PROGRAMS:
            findings.append(
                ValidationFinding(
                    code="taxes_program_unavailable",
                    severity="unknown",
                    message="program does not supply reliable taxes and fees",
                    field="taxes_fees",
                )
            )
        elif taxes.state == "value":
            findings.append(
                ValidationFinding(
                    code="taxes_minor_units",
                    severity="info",
                    message="Seats.aero TotalTaxes is in minor currency units",
                    field="taxes_fees",
                )
            )
        else:
            findings.append(
                ValidationFinding(
                    code="taxes_unknown",
                    severity="unknown",
                    message="trip taxes and fees are unavailable",
                    field="taxes_fees",
                )
            )
        if query.cabins and row.get("Cabin") not in query.cabins:
            findings.append(
                ValidationFinding(
                    code="cabin_scope_mismatch",
                    severity="warning",
                    message="returned trip cabin is outside requested cabin scope",
                    field="cabin",
                )
            )
        if (
            any(ob.kind == FilterObligationKind.DIRECT_FLIGHT_AVAILABLE for ob in query.filters)
            and len(legs) != 1
        ):
            findings.append(
                ValidationFinding(
                    code="direct_scope_mismatch",
                    severity="warning",
                    message="returned trip has connections despite direct-flight scope",
                    field="legs",
                )
            )
        return ProviderObservation(
            observation_id=content_digest(
                {
                    "query": query.query_id,
                    "trip": row,
                    "evidence": capture.evidence.sha256,
                    "retrieved_at": capture.evidence.retrieved_at.isoformat(),
                }
            ),
            provider="seats_aero",
            backend="partnerapi",
            provider_version=self._version,
            kind="award_itinerary",
            query_id=query.query_id,
            logical_query_ids=query.logical_query_ids,
            logical_use_ids=query.logical_use_ids,
            strategy_ids=query.strategy_ids,
            provider_record_id=row.get("ID"),
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            airport_sequence=sequence,
            legs=tuple(legs),
            departure_local=departure_local,
            arrival_local=arrival_local,
            departure_instant=departure_instant,
            arrival_instant=arrival_instant,
            origin_timezone=origin_tz,
            destination_timezone=destination_tz,
            retrieved_at=capture.evidence.retrieved_at,
            provider_updated_at=_field(row, "UpdatedAt"),
            requested_travelers=query.travelers,
            requested_cabins=query.cabins,
            cabin=_field(row, "Cabin"),
            program=program,
            points=points,
            taxes_fees=taxes,
            taxes_fees_unit="minor" if taxes.state == "value" else "unknown",
            tax_currency=_field(row, "TaxesCurrency"),
            seats=seats,
            duration_minutes=_field(row, "TotalDuration"),
            stops=_field(row, "Stops"),
            carriers=_split_carriers(row.get("Carriers")),
            evidence=(capture.evidence,),
            findings=tuple(findings),
            raw_fields={
                key: _field(row, key)
                for key in (
                    "Cabin",
                    "MileageCost",
                    "TotalTaxes",
                    "TaxesCurrency",
                    "RemainingSeats",
                    "MixedCabinPct",
                )
            },
        )
