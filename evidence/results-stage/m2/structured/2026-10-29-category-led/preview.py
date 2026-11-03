"""Read-only review preview with real source-resolved flight cards."""

from __future__ import annotations

import html
from datetime import datetime
from decimal import Decimal
from typing import Any


def _model(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _raw(value: Any) -> Any:
    value = _model(value)
    return value.get("value") if isinstance(value, dict) and value.get("state") == "value" else None


def _cabin(value: Any) -> str | None:
    raw = _raw(value)
    if not isinstance(raw, str):
        return None
    return raw.replace("_", " ")


def _local(value: Any) -> str:
    value = _model(value)
    iso = value.get("local_iso") if isinstance(value, dict) else None
    if not iso:
        return "time unavailable"
    try:
        return datetime.fromisoformat(iso).strftime("%-I:%M %p, %b %-d, %Y")
    except ValueError:
        return iso


def _duration(minutes: Any) -> str:
    if minutes is None:
        return "duration unavailable"
    value = int(Decimal(str(minutes)))
    hours, rem = divmod(value, 60)
    return f"{hours}h {rem:02d}m" if hours else f"{rem}m"


def _travelers(value: int) -> str:
    return f"{value} traveler" if value == 1 else f"{value} travelers"


def _updated(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%b %-d, %Y %H:%M UTC")
    except ValueError:
        return value


def _money(value: Any) -> str | None:
    value = _model(value)
    if not isinstance(value, dict):
        return None
    amount = _raw(value.get("raw_amount"))
    currency = _raw(value.get("raw_currency"))
    if amount is None or currency is None:
        return None
    unit = value.get("unit")
    if unit == "minor" and currency in {"USD", "CAD"}:
        amount = Decimal(str(amount)) / Decimal(100)
    elif unit != "major":
        return None
    scope = value.get("scope")
    basis = (" per traveler" if scope == "per_traveler" else
             " for the party" if scope == "party" else "")
    return f"{currency} {Decimal(str(amount)):,.2f} quote{basis}"


def _award_tax_row(value: Any) -> str | None:
    value = _model(value)
    if not isinstance(value, dict) or value.get("kind") != "award_taxes":
        return None
    quote = _money(value)
    if quote:
        return f"Taxes {quote}"
    raw_amount = _model(value.get("raw_amount"))
    state = raw_amount.get("state") if isinstance(raw_amount, dict) else None
    if state == "unknown":
        return "Award taxes: amount unconfirmed"
    if state == "absent":
        return "Award taxes: amount not provided"
    return None


def _legs(rows: Any) -> list[str]:
    result = []
    for leg in rows or []:
        if not leg.get("reported"):
            continue
        number = _raw(leg.get("flight_number"))
        cabin = _cabin(leg.get("cabin"))
        detail = f"{leg.get('origin', '?')}–{leg.get('destination', '?')}"
        if number:
            detail += f" · {number}"
        if cabin:
            detail += f" · {cabin}"
        departure, arrival = _local(leg.get("departure")), _local(leg.get("arrival"))
        if departure != "time unavailable" or arrival != "time unavailable":
            detail += f" · {departure} → {arrival}"
        result.append(detail)
    return result


def _cash_component_schedule(component: dict[str, Any]) -> str | None:
    origin, destination = component.get("origin"), component.get("destination")
    if not origin or not destination:
        return None
    legs = component.get("legs") or []
    departure = _local(legs[0].get("departure")) if legs else "time unavailable"
    arrival = _local(legs[-1].get("arrival")) if legs else "time unavailable"
    head = f"Separately booked {origin}–{destination} component"
    if departure != "time unavailable" and arrival != "time unavailable":
        detail = ("" if any(leg.get("reported") for leg in legs) else
                  " Individual flight details unreported.")
        return (f"{head}: departs {departure} ({origin} local); "
                f"arrives {arrival} ({destination} local).{detail}")
    date = component.get("departure_date")
    if date:
        return f"{head}: {date}; exact flight times unavailable."
    return f"{head}: flight times unavailable."


def _card(block: dict[str, Any], components: dict[str, dict[str, Any]],
          travelers: int | None) -> list[str]:
    kind = ("journey" if block.get("kind") == "journey_card" else
            "lead" if block.get("kind") == "lead_card" else
            block.get("reference_kind"))
    label = block.get("label") or "Flight option"
    if kind == "journey" and isinstance(block.get("journey"), dict):
        journey = block["journey"]
        award = block.get("award_component") or components.get(journey.get("award_observation_id"), {})
        origin, destination = journey.get("origin"), journey.get("destination")
        rows = [f"{label} — {origin}–{destination}",
                (f"Departs {_local(journey.get('departure'))} ({origin} local); "
                 f"arrives {_local(journey.get('arrival'))} ({destination} local); "
                 f"{_duration(journey.get('elapsed_minutes'))} total")]
        cabin = _cabin(journey.get("award_cabin"))
        program = _raw(journey.get("award_program"))
        points = _raw(journey.get("award_points"))
        fare = f"{int(points):,} {str(program).title()} points" if isinstance(points, int) and program else None
        if cabin:
            fare = f"{cabin} award · {fare}" if fare else f"{cabin} award"
        if fare:
            rows.append(fare)
        legs = _legs(journey.get("legs"))
        if legs:
            rows.append("Flights: " + "; ".join(legs))
        cash_component = block.get("cash_component") or components.get(
            journey.get("cash_observation_id"), {})
        if isinstance(cash_component, dict) and cash_component:
            cash_schedule = _cash_component_schedule(cash_component)
            if cash_schedule:
                rows.append(cash_schedule)
        money = journey.get("money") or {}
        tax = _award_tax_row(money.get("award_taxes"))
        cash = _money(money.get("cash_fare"))
        if tax or cash:
            rows.append(" · ".join(part for part in (tax,
                                                  cash and f"Positioning flight {cash}") if part))
        connections = journey.get("connections") or []
        if connections:
            rows.append("Connections: " + "; ".join(
                f"{row.get('airport') or 'unknown airport'} ({_duration(row.get('wait_minutes'))} wait"
                + (", separate tickets" if row.get("kind") == "separate_booking" else "") + ")"
                for row in connections))
        seats = _raw(award.get("seats"))
        if seats is not None:
            rows.append(f"{seats} award seats reported")
        returned = _raw(award.get("returned_travelers"))
        if returned is not None:
            rows.append(f"Award result returned for {_travelers(returned)}")
        elif travelers is not None:
            codes = journey.get("internal", {}).get("reason_codes", [])
            if "award_travelers_supported" in codes:
                rows.append(f"Award evidence supports the requested {_travelers(travelers)}")
            elif "award_travelers_unknown" in codes:
                rows.append(f"Award support for {_travelers(travelers)} unconfirmed")
        styles = journey.get("styles") or []
        style_labels = {"time": "shorter journey", "cost": "lower comparison cost",
                        "premium": "business or first class"}
        if styles:
            rows.append("Good for: " + ", ".join(style_labels[style] for style in styles))
        updated = _raw(award.get("provider_updated_at"))
        retrieved = award.get("retrieved_at")
        if updated or retrieved:
            rows.append("Source " + (f"updated {_updated(updated)}" if updated else
                                      f"retrieved {_updated(retrieved)}"))
        if any((money.get(key) or {}).get("scope") == "unknown"
               for key in ("award_taxes", "cash_fare")) or money.get("points_scope") == "unknown":
            rows.append("Price basis unconfirmed")
        return rows
    if kind == "lead":
        component = (_model(block.get("lead_component")) or _model(block.get("component")) or
                     components.get(block.get("canonical_id"), {}))
        if not isinstance(component, dict):
            component = {}
        rows = [f"{label} — research lead",
                (f"{component.get('origin', '?')}–{component.get('destination', '?')} · "
                 f"{component.get('departure_date') or 'date unavailable'} · "
                 f"{_cabin(component.get('cabin')) or 'cabin unavailable'}")]
        points = _raw(component.get("points"))
        program = _raw(component.get("program"))
        if points is not None and program:
            rows.append(f"{int(points):,} {str(program).title()} points reported")
        component_money = component.get("money") or {}
        quote = _money(component_money)
        if quote:
            label = "Cash fare" if component_money.get("kind") == "cash_fare" else "Taxes"
            rows.append(f"{label} {quote}")
        else:
            tax_status = _award_tax_row(component_money)
            if tax_status:
                rows.append(tax_status)
        seats = _raw(component.get("seats"))
        if seats is not None:
            rows.append(f"{seats} seats reported")
        returned = _raw(component.get("returned_travelers"))
        if returned is not None:
            rows.append(f"Result returned for {_travelers(returned)}")
        if component_money.get("scope") == "unknown":
            rows.append("Price basis unconfirmed")
        legs = _legs(component.get("legs"))
        if legs:
            rows.append("Reported flights: " + "; ".join(legs))
        lead = block.get("lead") or {}
        missing = lead.get("missing_information") or []
        if missing:
            rows.append("Needs checking: " + ", ".join(
                value.replace("_", " ") for value in missing))
        return rows
    return [label]


def _parts(artifact: Any) -> list[tuple[str, list[str]]]:
    data = _model(artifact)
    resolved = data.get("resolved")
    if not isinstance(resolved, dict):
        return []
    evidence = data.get("evidence") or {}
    components = {row["observation_id"]: row for row in evidence.get("components", [])}
    travelers = (((evidence.get("source") or {}).get("view") or {}).get("request") or {}).get("travelers")
    parts = []
    for block in resolved.get("blocks", []):
        kind = block.get("kind")
        if kind in {"journey_card", "lead_card"} or (kind == "reference" and
                block.get("reference_kind") in {"journey", "lead"}):
            if block.get("text"):
                parts.append(("text", [block["text"]]))
            parts.append(("card", _card(block, components, travelers)))
        elif kind == "cash_sentence":
            value = block.get("text")
            if value:
                parts.append(("text", ["Cash comparison: " + value]))
        elif kind == "comparison":
            comparison = block.get("comparison") or {}
            parts.append(("text", [comparison.get("comparison_id", "Comparison")]))
        else:
            value = block.get("text")
            if value:
                parts.append(("text", [value]))
    guidance = resolved.get("availability_guidance")
    if isinstance(guidance, str) and guidance.strip():
        parts.append(("text", [guidance.strip()]))
    return parts


def render_markdown(artifact: Any) -> str:
    chunks = []
    for kind, rows in _parts(artifact):
        chunks.append("\n".join(["> **Flight card**", *(f"> {row}" for row in rows)])
                      if kind == "card" else rows[0])
    return "\n\n".join(chunks) + "\n"


def render_html(artifact: Any) -> str:
    chunks = ["<!doctype html><html lang='en'><meta charset='utf-8'>",
              "<title>Category-led Results review</title>",
              ("<style>body{font:16px/1.5 system-ui;max-width:52rem;margin:2rem auto;padding:0 1rem;color:#17202b}"
               "article{border:1px solid #bcc8d2;border-radius:.6rem;padding:1rem;margin:1rem 0;background:#f6f9fb}"
               "article h2{font-size:1.1rem;margin:0 0 .5rem}article p{margin:.3rem 0}</style><body><main>")]
    for kind, rows in _parts(artifact):
        if kind == "card":
            chunks.append("<article aria-label='Flight card'><h2>" + html.escape(rows[0]) + "</h2>" +
                          "".join("<p>" + html.escape(row) + "</p>" for row in rows[1:]) + "</article>")
        else:
            chunks.append("<p>" + html.escape(rows[0]) + "</p>")
    chunks.append("</main></body></html>")
    return "\n".join(chunks) + "\n"
