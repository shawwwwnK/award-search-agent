"""Run-frozen FX acquisition and observed monetary facts for Results."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import urlencode
from urllib.request import urlopen

from award_agent.providers.contracts import RawField, Sha256, content_digest
from award_agent.ranking.projection_contracts import SolutionComponent
from award_agent.ranking.style_contracts import CurrencyConversionSnapshot
from award_agent.search_planning.contracts import PlanningContractModel

FX_SOURCE = "frankfurter-v2-ecb"
FX_URL = "https://api.frankfurter.dev/v2/providers/ecb/rates"
FX_TIMEOUT_SECONDS = 5.0
MAX_QUOTES = 20
MAX_RESPONSE_BYTES = 65536


class MoneyAmount(PlanningContractModel):
    kind: Literal["award_taxes", "cash_fare"]
    raw_amount: RawField
    raw_currency: RawField
    unit: Literal["major", "minor", "unknown"]
    scope: Literal["per_traveler", "party", "unknown"]
    rate_to_usd: Decimal | None
    quoted_usd: Decimal | None
    per_traveler_usd: Decimal | None
    conversion_snapshot_id: str | None
    conversion_as_of: date | None
    approximate_conversion: bool
    reason: str | None


class JourneyMoney(PlanningContractModel):
    award_taxes: MoneyAmount
    cash_fare: MoneyAmount | None
    observed_cash_per_traveler_usd: Decimal | None
    points_raw: RawField
    points_per_traveler: Decimal | None
    points_program: str | None
    points_scope: Literal["per_traveler", "party", "unknown"]
    incomparable_reasons: tuple[str, ...]


class FxAcquisitionReceipt(PlanningContractModel):
    status: Literal["success", "partial", "unavailable"]
    source: str
    request_url: str | None
    requested_currencies: tuple[str, ...]
    received_currencies: tuple[str, ...]
    missing_currencies: tuple[str, ...]
    retrieved_at: datetime
    effective_date: date | None
    raw_response_digest: Sha256 | None
    reason: str | None


class FxAcquisition(PlanningContractModel):
    snapshot: CurrencyConversionSnapshot
    receipt: FxAcquisitionReceipt


def _decimal(raw: RawField) -> Decimal | None:
    if raw.state != "value" or isinstance(raw.value, bool):
        return None
    try:
        value = Decimal(str(raw.value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return value if value.is_finite() and value >= 0 else None


def _currency(raw: RawField) -> str | None:
    value = raw.value if raw.state == "value" else None
    if isinstance(value, str) and len(value) == 3 and value.isascii() and value.isalpha() and value.isupper():
        return value
    return None


def observed_money(
    component: SolutionComponent, kind: Literal["award_taxes", "cash_fare"],
    snapshot: CurrencyConversionSnapshot, travelers: int,
) -> MoneyAmount:
    """Convert a reported price, preserving its original quote and scope."""
    if travelers < 1:
        raise ValueError("travelers must be positive")
    amount = component.taxes_fees if kind == "award_taxes" else component.cash_amount
    currency = component.tax_currency if kind == "award_taxes" else component.cash_currency
    unit: Literal["major", "minor", "unknown"] = (
        component.taxes_fees_unit if kind == "award_taxes" else "major"
    )
    parsed = _decimal(amount)
    code = _currency(currency)
    reason = None
    if parsed is None:
        reason = f"amount_{amount.state}" if amount.state != "value" else "amount_invalid"
    elif code is None:
        reason = "currency_unknown"
    elif unit == "unknown" or (unit == "minor" and code not in {"USD", "CAD"}):
        reason = "unit_unknown" if unit == "unknown" else "minor_unit_unsupported"
    rate = snapshot.rates_to_usd.get(code) if code is not None else None
    if reason is None and rate is None:
        reason = "rate_unavailable"
    quoted: Decimal | None = None
    if reason is None and parsed is not None and rate is not None:
        major = parsed / 100 if unit == "minor" else parsed
        quoted = major * rate
    per_traveler = quoted
    if quoted is not None and component.price_scope == "party":
        per_traveler = quoted / travelers
    elif component.price_scope == "unknown":
        per_traveler = None
        if reason is None:
            reason = "scope_unknown"
    return MoneyAmount(
        kind=kind, raw_amount=amount, raw_currency=currency, unit=unit,
        scope=component.price_scope, rate_to_usd=rate,
        quoted_usd=quoted, per_traveler_usd=per_traveler,
        conversion_snapshot_id=snapshot.snapshot_id if quoted is not None else None,
        conversion_as_of=snapshot.as_of if quoted is not None else None,
        approximate_conversion=quoted is not None and code != "USD", reason=reason,
    )


def journey_money(
    award: SolutionComponent, cash: SolutionComponent | None,
    snapshot: CurrencyConversionSnapshot, travelers: int,
) -> JourneyMoney:
    """Report observed cash and points separately from Ranking's heuristic cost."""
    taxes = observed_money(award, "award_taxes", snapshot, travelers)
    fare = observed_money(cash, "cash_fare", snapshot, travelers) if cash is not None else None
    pieces = (taxes,) if fare is None else (taxes, fare)
    complete_cash = all(piece.per_traveler_usd is not None for piece in pieces)
    cash_total = sum((piece.per_traveler_usd for piece in pieces if piece.per_traveler_usd is not None),
                     Decimal(0)) if complete_cash else None
    points_amount = _decimal(award.points)
    program_value = award.program.value if award.program.state == "value" else None
    program = program_value if isinstance(program_value, str) and program_value.strip() else None
    points = points_amount
    if award.price_scope == "party" and points is not None:
        points /= travelers
    if award.price_scope == "unknown" or program is None:
        points = None
    reasons = [piece.reason for piece in pieces if piece.reason]
    if points is None:
        reasons.append("points_incomparable")
    return JourneyMoney(
        award_taxes=taxes, cash_fare=fare, observed_cash_per_traveler_usd=cash_total,
        points_raw=award.points, points_per_traveler=points, points_program=program,
        points_scope=award.price_scope,
        incomparable_reasons=tuple(dict.fromkeys(reasons)),
    )


def _http_fetch(url: str, timeout: float) -> bytes:
    with urlopen(url, timeout=timeout) as response:
        return bytes(response.read(MAX_RESPONSE_BYTES + 1))


def _fallback(
    requested: tuple[str, ...], now: datetime, url: str | None, reason: str,
    raw_digest: str | None = None,
) -> FxAcquisition:
    snapshot = CurrencyConversionSnapshot(
        snapshot_id=f"fx-unavailable-{content_digest((now.isoformat(), requested, reason))[:16]}",
        as_of=now.date(), source="fx-acquisition-unavailable",
        source_digest=content_digest({"requested": requested, "retrieved_at": now.isoformat(),
                                      "reason": reason, "raw_digest": raw_digest}),
        rates_to_usd={"USD": Decimal(1)},
    )
    return FxAcquisition(
        snapshot=snapshot,
        receipt=FxAcquisitionReceipt(
            status="unavailable", source=FX_SOURCE, request_url=url,
            requested_currencies=requested, received_currencies=("USD",),
            missing_currencies=tuple(code for code in requested if code != "USD"),
            retrieved_at=now, effective_date=None, raw_response_digest=raw_digest,
            reason=reason,
        ),
    )


def acquire_fx_snapshot(
    currencies: tuple[str, ...], *, fetch: Callable[[str, float], bytes] = _http_fetch,
    now: datetime | None = None, timeout: float = FX_TIMEOUT_SECONDS,
) -> FxAcquisition:
    """Acquire one ECB dated response; malformed or mixed-date data becomes explicit outage."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("retrieval time must be timezone-aware")
    now = now.astimezone(UTC)
    if not 0 < timeout <= 30:
        raise ValueError("FX timeout must be positive and at most 30 seconds")
    requested = tuple(sorted(set(currencies) | {"USD"}))
    if len(requested) > MAX_QUOTES or any(
        len(code) != 3 or not code.isascii() or not code.isalpha() or not code.isupper()
        for code in requested
    ):
        raise ValueError("FX currencies require bounded uppercase ISO codes")
    non_usd = tuple(code for code in requested if code != "USD")
    if not non_usd:
        snapshot = CurrencyConversionSnapshot(
            snapshot_id=f"fx-usd-only-{now.date().isoformat()}", as_of=now.date(),
            source="usd-identity", source_digest=content_digest({"identity": "USD"}),
            rates_to_usd={"USD": Decimal(1)},
        )
        return FxAcquisition(
            snapshot=snapshot,
            receipt=FxAcquisitionReceipt(
                status="success", source="usd-identity", request_url=None,
                requested_currencies=requested, received_currencies=requested,
                missing_currencies=(), retrieved_at=now, effective_date=now.date(),
                raw_response_digest=None, reason=None,
            ),
        )
    url = FX_URL + "?" + urlencode({"base": "USD", "quotes": ",".join(requested)})
    raw: bytes | None = None
    try:
        raw = fetch(url, timeout)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("FX response exceeds byte limit")
        parsed = json.loads(raw, parse_float=Decimal)
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("FX response must contain rate rows")
        rates: dict[str, Decimal] = {"USD": Decimal(1)}
        effective: date | None = None
        seen: set[str] = set()
        for row in parsed:
            if not isinstance(row, dict) or row.get("base") != "USD":
                raise ValueError("FX rate row has wrong base")
            code = row.get("quote")
            if code not in requested or not isinstance(code, str) or code in seen:
                raise ValueError("FX rate row has duplicate or unrequested quote")
            seen.add(code)
            row_date = date.fromisoformat(row["date"])
            if row_date > now.date() or (effective is not None and row_date != effective):
                raise ValueError("FX rate rows have future or mixed dates")
            effective = row_date
            if isinstance(row["rate"], bool):
                raise TypeError("FX rate must be numeric")
            rate = Decimal(str(row["rate"]))
            if not rate.is_finite() or rate <= 0:
                raise ValueError("FX rate must be positive and finite")
            if code == "USD":
                if rate != 1:
                    raise ValueError("FX identity rate must equal one")
            else:
                rates[code] = Decimal(1) / rate
        if effective is None:
            raise ValueError("FX response lacks an effective date")
        raw_digest = hashlib.sha256(raw).hexdigest()
        snapshot = CurrencyConversionSnapshot(
            snapshot_id=f"fx-{effective.isoformat()}-{raw_digest[:16]}", as_of=effective,
            source=FX_SOURCE, source_digest=raw_digest, rates_to_usd=rates,
        )
        missing = tuple(code for code in requested if code not in rates)
        return FxAcquisition(
            snapshot=snapshot,
            receipt=FxAcquisitionReceipt(
                status="partial" if missing else "success", source=FX_SOURCE,
                request_url=url, requested_currencies=requested,
                received_currencies=tuple(sorted(rates)), missing_currencies=missing,
                retrieved_at=now, effective_date=effective,
                raw_response_digest=raw_digest, reason="missing_rates" if missing else None,
            ),
        )
    except (OSError, TimeoutError, ValueError, KeyError, TypeError, InvalidOperation,
            OverflowError) as exc:
        failure_digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
        return _fallback(requested, now, url, f"{type(exc).__name__}: {exc}", failure_digest)
