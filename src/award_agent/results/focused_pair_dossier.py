"""Compact V19 pair facts derived from selected canonical Results evidence."""

from __future__ import annotations

from decimal import Decimal
from itertools import combinations
from typing import Any, cast

from .currency import original_quote_major
from .interactive_contracts import InteractivePreparedInput
from .structured_contracts import StructuredPreparedInput
from .workspace_contracts import ComponentView, ComponentViewV1, WorkspaceEvidence


def _known(value: object) -> bool:
    return value is not None and value not in ("unknown", "absent", "null", "-")


def _number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        return None
    try:
        number = Decimal(value)
    except ArithmeticError:
        return None
    return number if number.is_finite() else None


def _direction(left: Decimal | None, right: Decimal | None) -> dict[str, object]:
    if left is None or right is None:
        return {"relation": "not_comparable"}
    relation = "equal" if left == right else "left_less" if left < right else "right_less"
    return {"relation": relation, "difference": str(abs(left - right))}


def _quote(ref: str | None, aliases: dict[str, str], prepared: StructuredPreparedInput,
           components: dict[str, ComponentView | ComponentViewV1]) -> dict[str, object] | None:
    if ref is None:
        return None
    short = aliases.get(ref)
    if short is None:
        raise ValueError("V19 quote reference lacks selected alias")
    canonical = prepared.references.awards.get(short) or prepared.references.cash.get(short)
    component = components.get(canonical or "")
    if component is None:
        raise ValueError("V19 quote component differs from canonical source")
    is_cash = component.kind == "cash_itinerary"
    amount = component.cash_amount if is_cash else component.taxes_fees
    currency = component.cash_currency if is_cash else component.tax_currency
    unit = "major" if is_cash else component.taxes_fees_unit
    major = original_quote_major(amount, currency, unit)
    code = currency.value if currency.state == "value" and isinstance(currency.value, str) else None
    exact = format(major, "f") if major is not None else None
    if exact is not None:
        whole, dot, fractional = exact.partition(".")
        exact = whole + "." + fractional.ljust(2, "0") if dot else whole + ".00"
    return {"source_ref": ref, "kind": "cash_fare" if is_cash else "award_taxes",
            "display": f"{code} {exact}" if code and exact is not None else None,
            "amount_major": str(major) if major is not None else None,
            "currency": code, "source_unit": unit, "price_scope": component.price_scope,
            "amount_state": amount.state}


def _side(ref: str, record: dict[str, Any], aliases: dict[str, str],
          prepared: StructuredPreparedInput,
          components: dict[str, ComponentView | ComponentViewV1]) -> dict[str, object]:
    facts = cast(dict[str, Any], record["facts"])
    if record["role"] == "journey":
        award = cast(dict[str, Any], facts["award"])
        cash = facts.get("cash")
        award_component = cast(dict[str, Any], record["award_component"])
        cash_component = record.get("cash_component")
        return {"ref": ref, "role": "journey", "route": facts.get("route"),
                "date": facts.get("date"), "departure": facts.get("departure"),
                "arrival": facts.get("arrival"), "elapsed_minutes": facts.get("elapsed_minutes"),
                "award_program": award.get("program"), "award_cabin": award.get("cabin"),
                "award_points": award.get("points"), "award_seats": award.get("seats"),
                "award_carriers": award.get("carriers"),
                "cash_carriers": cash.get("carriers") if isinstance(cash, dict) else None,
                "award_connections": award_component["award_itinerary_connections"],
                "journey_connections": record["journey_connections"],
                "award_quote": _quote(award_component["ref"], aliases, prepared, components),
                "cash_quote": _quote(cash_component["ref"], aliases, prepared, components)
                if isinstance(cash_component, dict) else None}
    member = cast(dict[str, Any], record["member"])
    quote = _quote(member["ref"], aliases, prepared, components)
    return {"ref": ref, "role": "lead", "route": facts.get("route"),
            "date": facts.get("date"), "schedule_state": facts.get("schedule_state"),
            "award_program": facts.get("program"), "award_cabin": facts.get("cabin"),
            "award_points": facts.get("points"), "award_seats": facts.get("seats"),
            "award_carriers": facts.get("carriers"), "reported_quote": quote}


def _quote_relation(left: object, right: object) -> dict[str, object]:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return {"relation": "not_comparable"}
    if (left.get("kind") != right.get("kind") or not _known(left.get("currency")) or
            left.get("currency") != right.get("currency") or
            left.get("source_unit") != right.get("source_unit")):
        return {"relation": "not_comparable"}
    relation: dict[str, object] = _direction(_number(left.get("amount_major")),
                                             _number(right.get("amount_major")))
    relation["comparison_scope"] = (
        "matching_known_quote_scope" if left.get("price_scope") == right.get("price_scope")
        and left.get("price_scope") in {"per_traveler", "party"}
        else "reported_raw_quote_amounts_only")
    return relation


def _relations(left: dict[str, object], right: dict[str, object],
               temporal: list[dict[str, Any]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for field in ("award_program", "award_cabin", "award_carriers", "cash_carriers"):
        a, b = left.get(field), right.get(field)
        result[field] = {"relation": "equal" if a == b else "different"
                         } if _known(a) and _known(b) else {"relation": "not_comparable"}
    same_program = (_known(left.get("award_program")) and
                    left.get("award_program") == right.get("award_program"))
    result["award_points"] = ({**_direction(_number(left.get("award_points")),
                                             _number(right.get("award_points"))),
                                "comparison_scope": "reported_raw_points_same_program_only"}
                               if same_program else {"relation": "not_comparable",
                                                     "reason": "different_or_unknown_program"})
    result["award_seats"] = _direction(_number(left.get("award_seats")),
                                       _number(right.get("award_seats")))
    for field in ("award_quote", "cash_quote", "reported_quote"):
        if field in left or field in right:
            result[field] = _quote_relation(left.get(field), right.get(field))
    for field, metric in (("elapsed_minutes", "elapsed"),
                          ("departure", "departure"),
                          ("arrival", "arrival")):
        if field not in left or field not in right:
            continue
        found = next((row for row in temporal if row["metric"] == metric and
                      {row["first_ref"], row["second_ref"]} == {left["ref"], right["ref"]}), None)
        if found is None:
            result[field] = {"relation": "not_comparable"}
        else:
            first_less = found["relation"] in {"first_earlier", "first_shorter"}
            result[field] = {"relation": ("equal" if found["relation"] == "equal" else
                "left_less" if (found["first_ref"] == left["ref"]) == first_less
                else "right_less"),
                "difference_minutes": found["difference_minutes"]}
    waits: list[dict[str, object]] = []
    for key in ("award_connections", "journey_connections"):
        for a in cast(list[dict[str, Any]], left.get(key) or []):
            for b in cast(list[dict[str, Any]], right.get(key) or []):
                if a.get("kind") != b.get("kind") or a.get("airport") != b.get("airport"):
                    continue
                waits.append({"role": key, "airport": a.get("airport"), "kind": a.get("kind"),
                              **_direction(_number(a.get("wait_minutes")),
                                           _number(b.get("wait_minutes")))})
    result["matching_connection_waits"] = waits
    return result


def build_pair_dossiers(focus: InteractivePreparedInput, evidence: WorkspaceEvidence,
                        ) -> list[dict[str, object]]:
    """Pair every selected same-role option using exact source-bound values."""
    from .focused_records import writer_packet

    packet = focus.packet
    aliases = cast(dict[str, str], packet["wire_aliases"])
    records = cast(dict[str, dict[str, Any]], writer_packet(focus)["authoring_records"])
    components = {item.observation_id: item for item in evidence.components}
    temporal = cast(list[dict[str, Any]], packet["temporal_comparisons"])
    dossiers: list[dict[str, object]] = []
    for role in ("journey", "lead"):
        refs = [ref for ref, record in records.items() if record["role"] == role]
        for left_ref, right_ref in combinations(refs, 2):
            left = _side(left_ref, records[left_ref], aliases, focus.structured, components)
            right = _side(right_ref, records[right_ref], aliases, focus.structured, components)
            cards = [{"id": row["id"], "metric": row["metric"],
                      "first_ref": row["first_ref"], "second_ref": row["second_ref"]}
                     for row in temporal if {row["first_ref"], row["second_ref"]} ==
                     {left_ref, right_ref}]
            dossiers.append({"left_ref": left_ref, "right_ref": right_ref,
                             "left": left, "right": right,
                             "relations": _relations(left, right, temporal),
                             "card_ids": cards})
    return dossiers
