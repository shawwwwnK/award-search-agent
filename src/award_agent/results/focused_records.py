"""Lossless V13 writer projection with each selected fact owned by one exact ref."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from .interactive_contracts import InteractivePreparedInput


def writer_packet(prepared: InteractivePreparedInput) -> dict[str, object]:
    """Replace local joined groups and side indexes with per-reference records."""
    packet = prepared.packet
    version = packet.get("composition_format")
    if version not in {"complete-v10", "complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}:
        raise ValueError("per-reference writer packet requires a versioned records format")
    details = cast(dict[str, Any], packet["selected_details"])
    summaries = packet.get("traveler_evidence") if version in {"complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"} else None
    if version in {"complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"} and not isinstance(summaries, dict):
        raise ValueError("V20 writer packet lacks selected traveler evidence")
    quotes = cast(dict[str, dict[str, object]], details["component_quotes"])
    award_connections = cast(dict[str, list[dict[str, object]]], details["award_connections"])
    journey_connections = cast(dict[str, list[dict[str, object]]],
                               details["journey_connections"])
    journey_components = cast(dict[str, dict[str, str | None]],
                              details["journey_components"])
    records: dict[str, dict[str, object]] = {}
    expected: set[str] = set()
    for section, role in (("journeys", "journey"), ("benchmarks", "benchmark"),
                          ("leads", "lead")):
        groups = cast(list[dict[str, Any]], packet[section])
        for group in groups:
            facts = group["facts"]
            for member in group["members"]:
                ref = member["ref"]
                if not isinstance(ref, str) or ref in records:
                    raise ValueError("per-reference projection has duplicate or invalid ref")
                expected.add(ref)
                record: dict[str, object] = {"role": role, "member": deepcopy(member),
                                             "facts": deepcopy(facts)}
                if role == "journey":
                    components = journey_components.get(ref)
                    if components is None or components["award_ref"] != member["award_ref"] or \
                            components["cash_ref"] != member.get("cash_ref"):
                        raise ValueError("per-reference journey component binding differs")
                    award_ref = components["award_ref"]
                    cash_ref = components["cash_ref"]
                    if not isinstance(award_ref, str) or award_ref not in quotes or \
                            award_ref not in award_connections or ref not in journey_connections:
                        raise ValueError("per-reference journey source details are incomplete")
                    record["award_component"] = {"ref": award_ref,
                        "quote": deepcopy(quotes[award_ref]),
                        "award_itinerary_connections": deepcopy(award_connections[award_ref])}
                    record["cash_component"] = ({"ref": cash_ref,
                        "quote": deepcopy(quotes[cash_ref])} if isinstance(cash_ref, str)
                        and cash_ref in quotes else None)
                    if cash_ref is not None and record["cash_component"] is None:
                        raise ValueError("per-reference cash component quote is missing")
                    record["journey_connections"] = deepcopy(journey_connections[ref])
                    if version in {"complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}:
                        assert isinstance(summaries, dict)
                        if ref not in summaries:
                            raise ValueError("V20 writer packet lacks selected traveler evidence")
                        record["traveler_evidence"] = deepcopy(summaries[ref])
                else:
                    if ref not in quotes:
                        raise ValueError("per-reference component quote is missing")
                    record["quote"] = deepcopy(quotes[ref])
                records[ref] = record
    if set(records) != expected:
        raise ValueError("per-reference projection differs from selected source records")
    if version in {"complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"} and isinstance(summaries, dict) and set(summaries) != {
            ref for ref, record in records.items() if record["role"] == "journey"}:
        raise ValueError("V20 traveler evidence differs from selected journey refs")
    retained = ("request", "policy", "source_context", "outcome_mode", "selection_scope",
                "source_scope", "legend", "finding_meanings", "comparison",
                "selected_comparisons", "temporal_comparisons")
    if any(key not in packet for key in retained):
        raise ValueError("per-reference writer packet lacks global source context")
    result = {key: deepcopy(packet[key]) for key in retained}
    result.update({"format": ("focused-authoring-records-v3" if version in {"complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"} else
                              "focused-authoring-records-v2" if version in {"complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15"}
                              else "focused-authoring-records-v1"),
                   "selection_format": packet["selection_format"],
                   "composition_format": version,
                   "record_legend": deepcopy(details["legend"]),
                   "authoring_records": records})
    if version in {"complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}:
        plan = packet.get("editorial_plan")
        if not isinstance(plan, list):
            raise TypeError("V14 writer packet lacks separate editorial plan")
        result["editorial_plan"] = ([{"role": row["role"], "ref": row["ref"],
                                     "compare_to": row["compare_to"],
                                     "status": "nonfactual_selection_intent"} for row in plan]
                                    if version in {"complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"} else deepcopy(plan))
    if version in {"complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}:
        result.pop("selected_comparisons")
        result.pop("temporal_comparisons")
        if "comparison_pairs" in packet:
            result["comparison_pairs"] = deepcopy(packet["comparison_pairs"])
    return result
