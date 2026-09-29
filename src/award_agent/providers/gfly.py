"""Pinned gfly CLI adapter for one-pair, one-day cash observations."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import JsonValue

from award_agent.providers.contracts import (
    CapturedResponse,
    EvidenceRef,
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
from award_agent.providers.transport import (
    CommandTransport,
    SubprocessTransport,
    TransportLimitError,
)

# Owner-approved policy (2026-09-27): the provider-returned query echo
# (body["query"]["adults"]) is validated page-level against the requested party
# before any itinerary row parses, so for these capability versions that validated
# echo is recorded as returned-traveler evidence: the provider returned these
# itineraries as the results of an N-adult search. Itinerary party bookability,
# cabin adequacy, and price scope remain unknown. Older embedded capability
# versions keep returned_travelers absent so saved replays stay byte-identical.
_PARTY_ECHO_VERSIONS = frozenset({"0.3.0+award-search-unpriced-party-echo-v2"})

_EXIT_STATUS = {
    0: "completed",
    1: "failed",
    2: "failed",
    3: "empty",
    4: "failed",
    5: "failed",
    6: "failed",
    7: "rate_limited",
    8: "failed",
    10: "failed",
    12: "failed",
    13: "failed",
    20: "blocked",
    21: "schema_drift",
    130: "failed",
}


def _raw(row: Mapping[str, Any], key: str) -> RawField:
    result = RawField.from_mapping(row, key)
    if result.state == "value" and result.value in ("", "unknown", "Unknown"):
        return RawField(state="unknown", source_field=key)
    return result


def _local_time(
    value: Any, airport: str, zones: Mapping[str, str]
) -> tuple[str | None, datetime | None, str | None]:
    if not isinstance(value, str) or not value:
        return None, None, zones.get(airport)
    zone_name = zones.get(airport)
    if not zone_name:
        return value, None, None
    try:
        zone = ZoneInfo(zone_name)
        naive = datetime.fromisoformat(value)
        if naive.tzinfo is not None:
            raise ValueError("gfly local time unexpectedly has a timezone offset")
        aware = naive.replace(tzinfo=zone)
        if aware.utcoffset() != naive.replace(tzinfo=zone, fold=1).utcoffset():
            return value, None, zone_name
        if aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive:
            return value, None, zone_name
        return value, aware.astimezone(UTC), zone_name
    except (ValueError, ZoneInfoNotFoundError):
        return value, None, zone_name


class GflyAdapter:
    def __init__(
        self,
        *,
        evidence_root: Path,
        transport: CommandTransport | None = None,
        executable: str = "gfly",
        wrapper: str | None = None,
        provider_version: str = "0.3.0",
    ) -> None:
        self._root = evidence_root
        self._transport = transport or SubprocessTransport()
        self._executable = executable
        self._wrapper = wrapper
        self._version = provider_version

    def fetch(
        self,
        query: ProviderQuery,
        *,
        cursor: str | None,
        timeout_seconds: float,
        max_bytes: int,
    ) -> CapturedResponse:
        if query.provider != "gfly" or cursor is not None:
            raise ValueError("gfly requires one non-paginated cash acquisition")
        if any(query.filters):
            raise ValueError("unmapped gfly filters must not be silently omitted")
        if len(query.cabins) > 1:
            raise ValueError("gfly accepts one cabin per acquisition")
        cabin = query.cabins[0] if query.cabins else "economy"
        cabin = "premium" if cabin == "premium_economy" else cabin
        if cabin not in {"economy", "premium", "business", "first"}:
            raise ValueError("unsupported gfly cabin")
        # --limit 0 means no local output truncation in pinned gfly 0.3.0.
        # gfly still performs one upstream fetch regardless of this flag.
        argv = [
            self._executable,
            *([self._wrapper] if self._wrapper is not None else []),
            "search",
            query.origins[0],
            query.destinations[0],
            "--depart",
            query.start_date.isoformat(),
            "--adults",
            str(query.travelers),
            "--cabin",
            cabin,
            "--currency",
            query.currency,
            "--backend",
            "google",
            "--sort",
            "best",
            "--limit",
            "0",
            "--json",
            "--no-input",
            "--wait",
            "--max-wait",
            str(max(1, int(timeout_seconds))),
        ]
        retrieved = datetime.now(UTC)
        started = time.monotonic()
        try:
            response = self._transport.run(
                argv,
                timeout_seconds=timeout_seconds,
                max_response_bytes=max_bytes,
            )
            status = _EXIT_STATUS.get(response.exit_code, "failed")
            raw = response.stdout if response.exit_code == 0 else response.stderr
            try:
                body = json.loads(raw)
                sanitized = sanitize_provider_payload(body)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
                sanitized = sanitized_failure_sample(raw, truncated=False)
                if status == "completed":
                    status = "malformed"
            path, digest = write_immutable_evidence(self._root, sanitized)
            error_code = sanitized.get("code") if isinstance(sanitized, dict) else None
            return CapturedResponse(
                query_id=query.query_id,
                provider="gfly",
                status=cast(Outcome, status),
                evidence=EvidenceRef(
                    sha256=digest, relative_path=path.name, retrieved_at=retrieved
                ),
                body=sanitized,
                elapsed_seconds=response.elapsed_seconds,
                byte_count=len(response.stdout) + len(response.stderr),
                error_code=error_code
                if isinstance(error_code, str)
                else (None if status == "completed" else status),
            )
        except TimeoutError:
            status, code, consumed, sample = "timeout", "timeout", 0, b""
        except TransportLimitError as exc:
            status, code, consumed, sample = (
                "budget_exhausted",
                "byte_budget",
                exc.observed_bytes,
                exc.sample,
            )
        except OSError:
            status, code, consumed, sample = "failed", "command_error", 0, b""
        error_body: dict[str, JsonValue] = {"transport_error": code, "observed_bytes": consumed}
        if sample:
            error_body.update(
                cast(dict[str, JsonValue], sanitized_failure_sample(sample, truncated=True))
            )
        path, digest = write_immutable_evidence(self._root, error_body)
        return CapturedResponse(
            query_id=query.query_id,
            provider="gfly",
            status=cast(Outcome, status),
            evidence=EvidenceRef(sha256=digest, relative_path=path.name, retrieved_at=retrieved),
            body=error_body,
            elapsed_seconds=time.monotonic() - started,
            byte_count=consumed,
            error_code=code,
        )

    def parse(
        self,
        query: ProviderQuery,
        capture: CapturedResponse,
        *,
        airport_timezones: Mapping[str, str],
    ) -> ParsedProviderPage:
        if capture.provider != "gfly" or capture.query_id != query.query_id:
            raise ValueError("captured response does not belong to this gfly query")
        if capture.status != "completed":
            return ParsedProviderPage(
                query_id=query.query_id,
                status=capture.status,
                pair_coverage_exhaustive=(
                    capture.status == "empty"
                    and isinstance(capture.body, dict)
                    and capture.body.get("code") == "EMPTY_RESULTS"
                ),
            )
        body = capture.body
        if (
            not isinstance(body, dict)
            or body.get("schemaVersion") != "1"
            or body.get("backend") != "google"
        ):
            return ParsedProviderPage(
                query_id=query.query_id,
                status="schema_drift",
                findings=(
                    ValidationFinding(
                        code="gfly_envelope",
                        severity="error",
                        message="unrecognized schema or backend",
                    ),
                ),
            )
        rows = body.get("itineraries")
        count, next_cursor, offset = body.get("count"), body.get("nextCursor"), body.get("offset")
        if (
            not isinstance(rows, list)
            or type(count) is not int
            or type(offset) is not int
            or next_cursor is not None
            or count != len(rows)
            or offset != 0
        ):
            return ParsedProviderPage(
                query_id=query.query_id,
                status="partial",
                findings=(
                    ValidationFinding(
                        code="gfly_incomplete",
                        severity="error",
                        message="full one-shot response was truncated or malformed",
                    ),
                ),
            )
        query_echo = body.get("query")
        if not isinstance(query_echo, dict) or any(
            (
                query_echo.get("from") != query.origins[0],
                query_echo.get("to") != query.destinations[0],
                query_echo.get("depart") != query.start_date.isoformat(),
                query_echo.get("adults") != query.travelers,
                query_echo.get("cabin")
                != (
                    "premium"
                    if query.cabins == ("premium_economy",)
                    else (query.cabins[0] if query.cabins else "economy")
                ),
                body.get("currency") != query.currency,
            )
        ):
            return ParsedProviderPage(
                query_id=query.query_id,
                status="schema_drift",
                findings=(
                    ValidationFinding(
                        code="gfly_query_echo",
                        severity="error",
                        message="response query differs from acquisition",
                    ),
                ),
            )
        observations: list[ProviderObservation] = []
        findings: list[ValidationFinding] = []
        for index, row in enumerate(rows):
            try:
                observations.append(self._observation(query, capture, row, airport_timezones))
            except (TypeError, KeyError) as exc:
                findings.append(
                    ValidationFinding(
                        code="gfly_row_schema", severity="error", message=f"row {index}: {exc}"
                    )
                )
            except ValueError as exc:
                findings.append(
                    ValidationFinding(
                        code="gfly_row_invalid", severity="error", message=f"row {index}: {exc}"
                    )
                )
        schema_failed = any(item.code == "gfly_row_schema" for item in findings)
        return ParsedProviderPage(
            query_id=query.query_id,
            status="schema_drift"
            if schema_failed
            else ("partial" if findings else ("empty" if not rows else "completed")),
            observations=tuple(observations),
            returned_row_count=len(rows),
            findings=tuple(findings),
            pair_coverage_exhaustive=not findings,
        )

    def _observation(
        self,
        query: ProviderQuery,
        capture: CapturedResponse,
        row: Any,
        zones: Mapping[str, str],
    ) -> ProviderObservation:
        if not isinstance(row, dict):
            raise TypeError("itinerary is not an object")
        origin, destination = row.get("origin"), row.get("destination")
        if not isinstance(origin, str) or not isinstance(destination, str):
            raise TypeError("itinerary airports are missing")
        if (origin, destination) != (query.origins[0], query.destinations[0]):
            raise ValueError("itinerary airports differ from query")
        departure_local, departure_instant, origin_tz = _local_time(
            row.get("departure"), origin, zones
        )
        arrival_local, arrival_instant, destination_tz = _local_time(
            row.get("arrival"), destination, zones
        )
        findings: list[ValidationFinding] = []
        if departure_instant is None or arrival_instant is None:
            findings.append(
                ValidationFinding(
                    code="gfly_time_unknown",
                    severity="unknown",
                    message="timezone instant unavailable for local itinerary time",
                )
            )
        elif arrival_instant < departure_instant:
            raise ValueError("itinerary arrives before departure")
        try:
            departure_date = date.fromisoformat(departure_local[:10]) if departure_local else None
        except ValueError as exc:
            raise ValueError("invalid local departure date") from exc
        if departure_date != query.start_date:
            raise ValueError("itinerary departs outside query date")
        layovers = row.get("layovers")
        airports: list[str] = [origin]
        if isinstance(layovers, list):
            for layover in layovers:
                if isinstance(layover, dict) and isinstance(layover.get("airport"), str):
                    airports.append(layover["airport"])
        airports.append(destination)
        airlines = row.get("airlines")
        if not isinstance(airlines, list):
            airlines = []
        raw_price = _raw(row, "price")
        if raw_price.state == "value":
            price = raw_price.value
            if (
                isinstance(price, bool)
                or not isinstance(price, (int, float))
                or (isinstance(price, float) and not math.isfinite(price))
            ):
                raise TypeError("cash price must be a finite number")
            if price < 0:
                raise ValueError("cash price must be nonnegative")
        if row.get("currency") != query.currency:
            raise ValueError("itinerary currency differs from query")
        if raw_price.state != "value":
            findings.append(
                ValidationFinding(
                    code="cash_price_unknown",
                    severity="unknown",
                    message="cash amount is unavailable",
                    field="cash_amount",
                )
            )
        returned_travelers = (
            RawField(state="value", value=query.travelers, source_field="query.adults")
            if self._version in _PARTY_ECHO_VERSIONS
            else RawField()
        )
        return ProviderObservation(
            observation_id=content_digest(
                {
                    "query": query.query_id,
                    "row": row,
                    "evidence": capture.evidence.sha256,
                    "retrieved_at": capture.evidence.retrieved_at.isoformat(),
                }
            ),
            provider="gfly",
            backend="google",
            provider_version=self._version,
            kind="cash_itinerary",
            query_id=query.query_id,
            logical_query_ids=query.logical_query_ids,
            logical_use_ids=query.logical_use_ids,
            strategy_ids=query.strategy_ids,
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            airport_sequence=tuple(airports),
            departure_local=departure_local,
            arrival_local=arrival_local,
            departure_instant=departure_instant,
            arrival_instant=arrival_instant,
            origin_timezone=origin_tz,
            destination_timezone=destination_tz,
            retrieved_at=capture.evidence.retrieved_at,
            requested_travelers=query.travelers,
            requested_cabins=query.cabins,
            returned_travelers=returned_travelers,
            cash_amount=raw_price,
            cash_currency=_raw(row, "currency"),
            price_scope="unknown",
            duration_minutes=_raw(row, "durationMinutes"),
            stops=_raw(row, "stops"),
            carriers=tuple(str(a) for a in airlines if a),
            evidence=(capture.evidence,),
            findings=tuple(findings),
            raw_fields={
                key: _raw(row, key)
                for key in (
                    "price",
                    "currency",
                    "departure",
                    "arrival",
                    "stops",
                    "durationMinutes",
                    "flightNumbers",
                    "bookingToken",
                )
            },
        )
