"""Version-gated exact connection and original-quote facts for focused V9."""

from __future__ import annotations

from typing import Any, cast

from .currency import original_quote_major
from .structured_contracts import StructuredPreparedInput
from .workspace_contracts import ComponentView, ComponentViewV1, ConnectionView, WorkspaceEvidence


def _connection(connection: ConnectionView) -> dict[str, object]:
    return {"kind": connection.kind, "airport": connection.airport,
            "wait_minutes": connection.wait_minutes,
            "unknown_reason": connection.unknown_reason}


def _quote(component: ComponentView | ComponentViewV1, *, kind: str,
           ) -> dict[str, object]:
    if kind == "award_taxes":
        amount, currency, unit = (component.taxes_fees, component.tax_currency,
                                  component.taxes_fees_unit)
    else:
        amount, currency, unit = component.cash_amount, component.cash_currency, "major"
    major = original_quote_major(amount, currency, unit)
    code = currency.value if currency.state == "value" else None
    if code is not None and not isinstance(code, str):
        code = None
    exact = format(major, "f") if major is not None else None
    if exact is not None:
        whole, dot, fractional = exact.partition(".")
        exact = whole + "." + fractional.ljust(2, "0") if dot else whole + ".00"
    return {"display": (f"{code} {exact}"
                if exact is not None and code is not None else None),
            "source_unit": unit, "price_scope": component.price_scope,
            "amount_state": amount.state}


def build_selector_details(prepared: StructuredPreparedInput,
                           evidence: WorkspaceEvidence) -> dict[str, object]:
    """Factor repeated award connections and component quotes by source alias."""
    if prepared.source_digest != evidence.source_binding.view_digest:
        raise ValueError("focused details source binding differs")
    refs = prepared.references
    by_journey = {item.candidate_id: item for item in evidence.journeys}
    by_component = {item.observation_id: item for item in evidence.components}
    component_alias = refs.awards | refs.cash
    reverse_component = {canonical: alias for alias, canonical in component_alias.items()}
    if len(reverse_component) != len(component_alias):
        raise ValueError("focused details duplicate component source alias")
    journeys: dict[str, dict[str, object]] = {}
    journey_connections: dict[str, list[dict[str, object]]] = {}
    award_connections: dict[str, list[dict[str, object]]] = {}
    required_components: set[str] = set()
    for alias, canonical in refs.journeys.items():
        journey = by_journey.get(canonical)
        if journey is None:
            raise ValueError("focused journey detail is absent from workspace")
        award = reverse_component.get(journey.award_observation_id)
        cash = (reverse_component.get(journey.cash_observation_id)
                if journey.cash_observation_id else None)
        if award is None or (journey.cash_observation_id and cash is None):
            raise ValueError("focused journey detail lacks exact component aliases")
        journeys[alias] = {"award_ref": award, "cash_ref": cash}
        required_components.add(award)
        if cash is not None:
            required_components.add(cash)
        award_rows = [_connection(item) for item in journey.connections
                      if item.kind == "award_connection"]
        prior = award_connections.setdefault(award, award_rows)
        if prior != award_rows:
            raise ValueError("shared award reference has conflicting connection facts")
        journey_connections[alias] = [_connection(item) for item in journey.connections
                                      if item.kind != "award_connection"]
    for canonical in evidence.direct_cash_benchmark_ids:
        benchmark_alias = reverse_component.get(canonical)
        if benchmark_alias is None:
            raise ValueError("focused benchmark detail lacks exact component alias")
        required_components.add(benchmark_alias)
    # The prepared map contains exactly the selectable A/C source identities.
    # Some workspace lead records also mention supporting observations that are
    # not separately selectable; their own source facts remain in the workspace.
    required_components.update(component_alias)
    components: dict[str, dict[str, object]] = {}
    for alias in sorted(required_components):
        component = by_component.get(component_alias[alias])
        if component is None:
            raise ValueError("focused component detail is absent from workspace")
        quote_kind = ("cash_fare" if component.kind == "cash_itinerary"
                      else "award_taxes")
        components[alias] = {"kind": quote_kind,
                             **_quote(component, kind=quote_kind)}
    return {"journey_components": journeys,
            "journey_connections": journey_connections,
            "award_connections": award_connections,
            "component_quotes": components,
            "legend": "Exact source aliases. award_connections belong to the award "
                      "itinerary; journey_connections retain separate-booking/cash "
                      "waits per journey. wait_minutes=null means unknown, never zero. "
                      "Quotes are original-currency major units with source unit and "
                      "price scope; unknown scope is neither per traveler nor party total."}


def build_selected_details(selector_details: dict[str, object],
                           focused_packet: dict[str, Any]) -> dict[str, object]:
    """Translate only selected exact references into the focused wire namespace."""
    registry = cast(dict[str, str], focused_packet["wire_aliases"])
    short_to_long = {short: long for long, short in registry.items()}
    if len(short_to_long) != len(registry):
        raise ValueError("focused selected detail aliases are not one-to-one")
    selected = {section: {member["ref"] for group in focused_packet[section]
                          for member in group["members"]}
                for section in ("journeys", "benchmarks", "leads")}
    journey_short = {registry[item] for item in selected["journeys"]}
    component_short = {registry[item] for item in
                       selected["benchmarks"] | selected["leads"]}
    source_j = cast(dict[str, dict[str, object]], selector_details["journey_components"])
    source_j_connections = cast(dict[str, list[dict[str, object]]],
                                selector_details["journey_connections"])
    source_award_connections = cast(dict[str, list[dict[str, object]]],
                                    selector_details["award_connections"])
    source_c = cast(dict[str, dict[str, object]], selector_details["component_quotes"])
    journeys = {}
    journey_connections = {}
    award_connections = {}
    for short in sorted(journey_short):
        row = source_j[short]
        award, cash = row["award_ref"], row["cash_ref"]
        if not isinstance(award, str) or (cash is not None and not isinstance(cash, str)):
            raise ValueError("focused selected component aliases are invalid")
        if award not in short_to_long or (cash is not None and cash not in short_to_long):
            raise ValueError("focused selected journey component is outside packet")
        long = short_to_long[short]
        journeys[long] = {"award_ref": short_to_long[award],
                          "cash_ref": short_to_long[cash] if cash else None}
        journey_connections[long] = source_j_connections[short]
        award_connections[short_to_long[award]] = source_award_connections[award]
        component_short.add(award)
        if cash is not None:
            component_short.add(cash)
    components = {short_to_long[short]: source_c[short]
                  for short in sorted(component_short)}
    if set(journeys) != selected["journeys"] or \
            set(components) != selected["benchmarks"] | selected["leads"] | {
                item for row in journeys.values() for item in
                (row["award_ref"], row["cash_ref"]) if item is not None}:
        raise ValueError("focused selected details do not match exact role references")
    return {"journey_components": journeys,
            "journey_connections": journey_connections,
            "award_connections": award_connections,
            "component_quotes": components,
            "legend": selector_details["legend"]}
