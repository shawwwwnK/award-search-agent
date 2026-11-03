"""V16 writer-only, lossless named projection of the full selector inventory."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from .interactive_contracts import InteractivePreparedInput


def _profiles(rows: list[list[Any]], columns: list[str], prefix: str) -> dict[str, dict[str, Any]]:
    if any(len(row) != len(columns) for row in rows):
        raise ValueError("selector profile does not match its source legend")
    return {f"{prefix}{index}": dict(zip(columns, deepcopy(row), strict=True))
            for index, row in enumerate(rows)}


def selector_packet(prepared: InteractivePreparedInput) -> dict[str, object]:
    """Name existing profiles and bind source quotes to exact J refs; never rank rows."""
    packet = prepared.packet
    if packet.get("selection_format") not in {"roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        raise ValueError("named selector records require a named profile marker")
    legend = cast(dict[str, Any], packet["legend"])
    journeys = _profiles(cast(list[list[Any]], packet["journey_profiles"]),
                         cast(list[str], legend["journey_profile"]), "JP")
    components = _profiles(cast(list[list[Any]], packet["component_profiles"]),
                           cast(list[str], legend["component_profile"]), "CP")
    component_rows = cast(list[list[Any]], packet["component_rows"])
    component_columns = cast(list[str], legend["component_row"])
    if len(component_columns) != 2 or any(len(row) != 2 for row in component_rows):
        raise ValueError("selector component row is not an exact profile binding")
    component_records: dict[str, dict[str, Any]] = {}
    for ref, index in component_rows:
        if type(index) is not int or not 0 <= index < len(components):
            raise ValueError("selector component profile index is invalid")
        profile_ref = f"CP{index}"
        if not isinstance(ref, str) or ref in component_records or profile_ref not in components:
            raise ValueError("selector component source binding is invalid")
        component_records[ref] = {"profile_ref": profile_ref}
    journey_rows = cast(list[list[Any]], packet["journey_rows"])
    journey_columns = cast(list[str], legend["journey_row"])
    if len(journey_columns) != 4 or any(len(row) != 4 for row in journey_rows):
        raise ValueError("selector journey row is not an exact component binding")
    journey_records: dict[str, dict[str, Any]] = {}
    for ref, index, award_ref, cash_ref in journey_rows:
        if type(index) is not int or not 0 <= index < len(journeys):
            raise ValueError("selector journey profile index is invalid")
        profile_ref = f"JP{index}"
        if (not isinstance(ref, str) or ref in journey_records or profile_ref not in journeys
                or not isinstance(award_ref, str) or award_ref not in component_records
                or (cash_ref is not None and cash_ref not in component_records)):
            raise ValueError("selector journey source binding is invalid")
        award_profile = components[component_records[award_ref]["profile_ref"]]
        journey_records[ref] = {
            "profile_ref": profile_ref, "award_ref": award_ref, "cash_ref": cash_ref,
            "award_cabin": journeys[profile_ref]["award_cabin"],
            "award_program": award_profile["program"],
            "award_points": award_profile["points"],
        }
    if len(journey_records) != len(journey_rows) or len(component_records) != len(component_rows):
        raise ValueError("selector records lost a source alias")
    retained = {key: deepcopy(value) for key, value in packet.items()
                if key not in {"legend", "journey_profiles", "journey_rows",
                               "component_profiles", "component_rows"}}
    named_legend = {key: deepcopy(value) for key, value in legend.items()
                    if key not in {"journey_row", "journey_profile", "component_row",
                                   "component_profile", "profiles"}}
    named_legend["named_profiles"] = (
        "Every J record owns an exact JP profile and its A/C refs; every A/C record "
        "owns an exact CP profile. Inline award fields repeat exact source values "
        "for that J only. JP/CP are data profiles, not selectable identities. "
        "Award cabin does not establish the cabin of each leg; points retain source scope.")
    retained.update({"legend": named_legend, "journey_profiles": journeys,
                     "journey_records": journey_records, "component_profiles": components,
                     "component_records": component_records})
    if packet.get("selection_format") in {"roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v27", "roles-v29", "roles-v30"}:
        if journey_rows:
            raise ValueError("V24 named lead view requires no eligible complete journey")
        lead_columns = cast(list[str], legend["lead_row"])
        lead_rows = cast(list[list[Any]], packet["lead_rows"])
        details = cast(dict[str, Any], retained["exact_details"])
        quotes = cast(dict[str, Any], details["component_quotes"])
        lead_records: list[dict[str, Any]] = []
        lead_refs: set[str] = set()
        for row in lead_rows:
            if len(row) != len(lead_columns):
                raise ValueError("V24 lead row does not match its canonical legend")
            record = dict(zip(lead_columns, deepcopy(row), strict=True))
            ref = record["A_or_C"]
            if not isinstance(ref, str) or ref in lead_refs or ref not in quotes:
                raise ValueError("V24 lead lacks a unique original quote source")
            lead_refs.add(ref)
            record["original_quote"] = quotes.pop(ref)
            lead_records.append(record)
        retained.pop("lead_rows")
        named_legend.pop("lead_row")
        named_legend["lead_records"] = [*lead_columns, "original_quote"]
        retained["lead_records"] = lead_records
        if packet.get("selection_format") in {"roles-v29", "roles-v30"}:
            groups: list[dict[str, Any]] = []
            for ordinal, record in enumerate(lead_records):
                program = record["program"]
                group = next((item for item in groups
                              if type(item["program"]) is type(program) and
                              item["program"] == program), None)
                if group is None:
                    group = {"program": deepcopy(program), "members": []}
                    groups.append(group)
                cast(list[dict[str, Any]], group["members"]).append(
                    {"source_ordinal": ordinal, "record": record})
            retained.pop("lead_records")
            named_legend["lead_program_groups"] = named_legend.pop("lead_records")
            retained["lead_program_groups"] = groups
    return retained
