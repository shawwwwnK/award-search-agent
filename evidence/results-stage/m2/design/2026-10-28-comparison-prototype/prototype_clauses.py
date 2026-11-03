"""Offline, narrow experiment in source-bound comparative clauses.

This is deliberately a clause renderer, not an answer checker or Results runtime.
Its input is the hand-audited ``source-facts.json`` beside this file.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re


class ClauseError(ValueError):
    """The proposed clause cannot be justified from the visible records."""


_RELATIONS = {
    "arrival": {"earlier": -1, "later": 1, "equal": 0},
    "departure": {"earlier": -1, "later": 1, "equal": 0},
    "elapsed": {"shorter": -1, "longer": 1, "equal": 0},
    "points": {"fewer": -1, "more": 1, "equal": 0},
    "native_fee": {"lower": -1, "higher": 1, "equal": 0},
}
_AMOUNT = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ClauseError(message)


def _amount(value: object, field: str) -> Decimal:
    _require(isinstance(value, str) and bool(_AMOUNT.fullmatch(value)),
             f"{field} must be a nonnegative plain decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ClauseError(f"{field} is not a decimal") from exc
    _require(number.is_finite(), f"{field} must be finite")
    return number


def _datetime(value: object, field: str) -> datetime:
    _require(isinstance(value, str), f"{field} must be an offset datetime")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ClauseError(f"{field} must be an ISO offset datetime") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
             f"{field} must have a UTC offset")
    return parsed


def _minutes(value: object, field: str) -> int:
    _require(type(value) is int and value >= 0, f"{field} must be nonnegative integer minutes")
    return value


def _label(record: dict, ref: str) -> str:
    label = record.get("label")
    _require(isinstance(label, str) and bool(label.strip()), f"{ref} lacks a source label")
    return label


def _display_decimal(value: Decimal) -> str:
    return format(value, "f")


def _display_minutes(value: int) -> str:
    hours, minutes = divmod(value, 60)
    parts = []
    if hours:
        parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
    if minutes or not parts:
        parts.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")
    return " ".join(parts)


def render_clause(spec: dict, records: dict, visible_refs: set[str] | list[str]) -> dict:
    """Render one checked relation between two exact, visible source records.

    Rejects unsupported units/scopes and a relation whose asserted direction does
    not equal the computed direction. Free text outside this clause is untouched.
    """
    _require(isinstance(spec, dict), "clause spec must be an object")
    clause_id = spec.get("id")
    left_ref, right_ref = spec.get("left_ref"), spec.get("right_ref")
    metric, relation, scope = spec.get("metric"), spec.get("relation"), spec.get("scope")
    _require(isinstance(clause_id, str) and bool(clause_id), "clause id is required")
    _require(isinstance(left_ref, str) and isinstance(right_ref, str) and left_ref != right_ref,
             "two distinct endpoint references are required")
    _require(isinstance(records, dict) and left_ref in records and right_ref in records,
             "both endpoints must be known source records")
    _require(left_ref in visible_refs and right_ref in visible_refs,
             "both endpoints must be visible")
    _require(metric in _RELATIONS, "unsupported metric")
    _require(relation in _RELATIONS[metric], "relation is invalid for metric")
    expected_scope = "schedule" if metric in {"arrival", "departure", "elapsed"} else "reported_quote"
    _require(scope == expected_scope, f"{metric} requires {expected_scope} scope")

    left, right = records[left_ref], records[right_ref]
    _require(isinstance(left, dict) and isinstance(right, dict), "source records must be objects")
    _require(left.get("id") == left_ref and right.get("id") == right_ref,
             "source record identity disagrees with reference")
    left_label, right_label = _label(left, left_ref), _label(right, right_ref)
    limitation = None

    if metric in {"arrival", "departure"}:
        _require(left.get("role") in {"journey", "lead", "benchmark"} and
                 right.get("role") in {"journey", "lead", "benchmark"},
                 "clock comparison requires scheduled journey or benchmark records")
        a = _datetime(left.get(metric), f"{left_ref}.{metric}")
        b = _datetime(right.get(metric), f"{right_ref}.{metric}")
        seconds = (a - b).total_seconds()
        _require(seconds % 60 == 0, "clock difference must resolve to whole minutes")
        difference = int(seconds // 60)
        unit = "minutes"
        limitation = "Scheduled times only; actual operations may differ."
    elif metric == "elapsed":
        a = _minutes(left.get("elapsed_minutes"), f"{left_ref}.elapsed_minutes")
        b = _minutes(right.get("elapsed_minutes"), f"{right_ref}.elapsed_minutes")
        difference = a - b
        unit = "minutes"
        limitation = "Reported schedule duration only."
    elif metric == "points":
        _require(left.get("price_scope") == right.get("price_scope") == "unknown",
                 "this prototype only compares quotes with unknown price scope")
        left_program, right_program = left.get("program"), right.get("program")
        _require(isinstance(left_program, str) and bool(left_program.strip()) and
                 left_program == right_program, "points comparison requires one known program")
        a = _amount(left.get("points"), f"{left_ref}.points")
        b = _amount(right.get("points"), f"{right_ref}.points")
        _require(a == a.to_integral_value() and b == b.to_integral_value(),
                 "points must be whole numbers")
        difference = a - b
        unit = "points"
        limitation = "Raw reported point quotes; traveler and trip price scope is unknown."
    else:
        _require(left.get("price_scope") == right.get("price_scope") == "unknown",
                 "this prototype only compares quotes with unknown price scope")
        left_currency, right_currency = left.get("fee_currency"), right.get("fee_currency")
        _require(isinstance(left_currency, str) and bool(left_currency.strip()) and
                 left_currency == right_currency, "native fee comparison requires one known currency")
        if "expected_currency" in spec:
            _require(spec["expected_currency"] == left_currency,
                     "expected currency disagrees with source")
        def quote_role(record: dict) -> str:
            role = record.get("role")
            _require(role in {"journey", "lead", "benchmark"}, "unknown quote role")
            return "cash fare" if role == "benchmark" else "award fee"
        quote_kind = quote_role(left)
        _require(quote_kind == quote_role(right), "award fees and cash fares are incomparable")
        a = _amount(left.get("native_fee"), f"{left_ref}.native_fee")
        b = _amount(right.get("native_fee"), f"{right_ref}.native_fee")
        difference = a - b
        unit = left_currency
        limitation = f"Raw reported {quote_kind} quotes; traveler and trip price scope is unknown."

    actual_direction = (difference > 0) - (difference < 0)
    _require(actual_direction == _RELATIONS[metric][relation],
             "asserted relation disagrees with source values")
    delta = abs(difference)
    display_delta = str(delta) if isinstance(delta, int) else _display_decimal(delta)
    if metric in {"arrival", "departure"}:
        verb = "arrives" if metric == "arrival" else "departs"
        text = (f"{left_label} {verb} {_display_minutes(delta)} {relation} than {right_label}."
                if relation != "equal" else f"{left_label} and {right_label} have the same reported {metric} time.")
    elif metric == "elapsed":
        text = (f"The reported elapsed time for {left_label} is {_display_minutes(delta)} {relation} than for {right_label}."
                if relation != "equal" else f"{left_label} and {right_label} have the same reported elapsed time.")
    elif metric == "points":
        program = left["program"].title()
        point_unit = "Alaska miles" if left["program"] == "alaska" else f"{program} points"
        text = (f"{left_label} reports {int(delta):,} {relation} {point_unit} than {right_label}."
                if relation != "equal" else f"{left_label} and {right_label} report equal {point_unit} quotes.")
        text += " These are reported quotes with unknown price scope."
    else:
        text = (f"The reported {quote_kind} quote for {left_label} is {unit} {display_delta} {relation} than for {right_label}."
                if relation != "equal" else f"{left_label} and {right_label} have equal reported {unit} {quote_kind} quotes.")
        text += " These are reported quotes with unknown price scope."
    source_field = "elapsed_minutes" if metric == "elapsed" else metric
    return {
        "clause_id": clause_id,
        "text": text,
        "endpoints": [left_ref, right_ref],
        "metric": metric,
        "scope": scope,
        "delta": {"value": display_delta, "unit": unit},
        "source_fact_refs": [f"{left_ref}.{source_field}", f"{right_ref}.{source_field}"],
        "limitation": limitation,
    }
