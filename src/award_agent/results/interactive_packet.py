"""Offline, source-bound decision view for the under-20-second writer experiment.

The packet is an input projection, not a selector or a new source of authority.
Profiles factor only equal decision facts; every exact source alias remains visible.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, cast

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.structured_contracts import StructuredPreparedInput
from award_agent.results.workspace_contracts import WorkspaceEvidence

JOURNEY_COLUMNS = ("status", "topology", "route", "date", "depart", "arrive",
                   "elapsed_minutes", "transfer", "award_cabin", "premium_economy_addon",
                   "booking", "price_completeness", "traveler_support", "seat_support",
                   "caveats", "heuristic_cost", "styles")
COMPONENT_COLUMNS = ("kind", "route", "date", "depart", "arrive", "airports",
                     "program", "cabin", "carriers", "points", "fees", "fee_unit",
                     "fee_currency", "cash", "cash_currency", "price_scope",
                     "returned_travelers", "seats", "stops", "duration_minutes",
                     "mixed_cabin_pct", "reported_flight_numbers", "leg_cabins",
                     "findings")
TIMEZONE_CODES: dict[str | None, str] = {
    "America/Los_Angeles": "LA", "Asia/Bangkok": "BKK",
    "Asia/Taipei": "TPE", "Asia/Seoul": "SEL",
    "Asia/Hong_Kong": "HKG", "Asia/Singapore": "SIN",
}
NONVALUE_STATES = frozenset(("absent", "null", "unknown", "-"))


def _raw(value: Any) -> Any:
    if isinstance(value, dict) and "state" in value:
        return value.get("value") if value["state"] == "value" else value["state"]
    return value


def _time(value: dict[str, Any]) -> str | None:
    local = value.get("local_iso")
    zone = value.get("timezone")
    if not local:
        return None
    return f"{local}@{TIMEZONE_CODES.get(zone, zone)}"


def _component(facts: dict[str, Any]) -> dict[str, Any]:
    result = {
        "kind": facts["kind"], "route": [facts["origin"], facts["destination"]],
        "date": facts["departure_date"], "depart": _time(facts["departure"]),
        "arrive": _time(facts["arrival"]), "airports": facts["airport_sequence"],
        "program": _raw(facts["program"]),
        "cabin": _raw(facts["cabin"]), "carriers": facts["carriers"],
        "points": _raw(facts["points"]), "fees": _raw(facts["taxes_fees"]),
        "fee_unit": facts["taxes_fees_unit"],
        "fee_currency": _raw(facts["tax_currency"]),
        "cash": _raw(facts["cash_amount"]),
        "cash_currency": _raw(facts["cash_currency"]),
        "price_scope": facts["price_scope"],
        "returned_travelers": _raw(facts["returned_travelers"]),
        "seats": _raw(facts["seats"]), "stops": _raw(facts["stops"]),
        "duration_minutes": _raw(facts["duration_minutes"]),
        "mixed_cabin_pct": _raw(facts["mixed_cabin_pct"]),
        "reported_flight_numbers": _raw(facts["reported_flight_numbers"]),
        "leg_cabins": [_raw(leg["cabin"]) for leg in facts["legs"]],
        "findings": [finding["code"] for finding in facts["findings"]],
    }
    return {key: value for key, value in result.items()
            if value not in (None, "absent", [])}


def _journey(facts: dict[str, Any]) -> dict[str, Any]:
    # Passed validation prose is redundant; preserve every unresolved state/code.
    caveats = [r["code"] if r["state"] == "unknown" else [r["code"], r["state"]]
               for r in facts["reasons"]
               if r["state"] != "passed"]
    traveler = next((r["state"] for r in facts["reasons"]
                     if r["code"].startswith("award_travelers_")), "unknown")
    seats = next((r["state"] for r in facts["reasons"]
                  if r["code"] == "result_validation_minimum_award_seats"), "unknown")
    result = {
        "status": facts["status"], "topology": facts["topology"],
        "route": [facts["origin"], facts["destination"]],
        "date": facts["departure_date"], "depart": _time(facts["departure"]),
        "arrive": _time(facts["arrival"]), "elapsed_minutes": facts["elapsed_minutes"],
        "transfer": [facts["transfer_airport"], facts["transfer_minutes"],
                     facts["transfer_local_day_offset"]],
        "award_cabin": _raw(facts["award_cabin"]),
        "premium_economy_addon": facts["premium_economy_addon"],
        "booking": facts["booking_obligation"],
        "price_completeness": facts["price_completeness"],
        "traveler_support": traveler,
        "seat_support": seats,
        "caveats": caveats,
        "heuristic_cost": [facts["cost"][k] for k in
                           ("known_subtotal_usd", "complete_usd", "missing_parts", "completeness")],
        "styles": [next(a["state"] for a in facts["assessments"] if a["style"] == style)
                   for style in ("time", "cost", "premium")],
    }
    return {key: value for key, value in result.items()
            if value not in (None, [])}


def _profiles(groups: list[dict[str, Any]], transform: Any,
              member_fields: tuple[str, ...]) -> tuple[list[dict[str, Any]], list[list[Any]]]:
    profiles: list[dict[str, Any]] = []
    rows: list[list[Any]] = []
    for group in groups:
        profile = transform(group["facts"])
        index = len(profiles)
        profiles.append(profile)
        for member in group["members"]:
            rows.append([member.get("ref"), index, *[member.get(k) for k in member_fields]])
    return profiles, rows


def build_packet(prepared: StructuredPreparedInput, source: SolutionProjection,
                 evidence: WorkspaceEvidence) -> dict[str, Any]:
    """Return compact readable tables with every selectable exact source reference."""
    if prepared.source_digest != source.receipt.view_digest or (
        evidence.source_binding.view_digest != source.receipt.view_digest
    ):
        raise ValueError("prepared, source and workspace view digests differ")
    # The compact authoring view is validated upstream; its heterogeneous
    # nested records are intentionally represented as a plain JSON-like mapping.
    view = cast(dict[str, Any], prepared.authoring_view.view)
    journey_profiles, journey_rows = _profiles(
        view["journeys"], _journey,
        ("award", "cash"),
    )
    all_component_profiles, all_component_rows = _profiles(
        view["components"], _component, ("observed_at", "provider_updated_at"),
    )
    component_by_ref = {row[0]: all_component_profiles[row[1]]
                        for row in all_component_rows}
    canonical_journey_alias = {canonical: alias for alias, canonical
                               in prepared.references.journeys.items()}
    ranking_hints = {key: [canonical_journey_alias[candidate] for candidate in
                           getattr(source.view.indexes, key)]
                     for key in ("time", "cost", "premium", "possible_cost",
                                 "premium_economy_addons", "definite_highlights",
                                 "possible_highlights", "other_alternatives")}
    finding_catalog: dict[str, dict[str, str]] = {}
    for group in view["components"]:
        for finding in group["facts"]["findings"]:
            meaning = {key: finding[key] for key in ("severity", "field", "message")}
            previous = finding_catalog.setdefault(finding["code"], meaning)
            if previous != meaning:
                raise ValueError("same finding code has conflicting meanings")
    required_components = set(view["benchmarks"])
    for row in journey_rows:
        required_components.add(row[2])
        if row[3] is not None:
            required_components.add(row[3])
    component_profiles: list[dict[str, Any]] = []
    component_rows = []
    profile_index: dict[int, int] = {}
    for row in all_component_rows:
        if row[0] not in required_components:
            continue
        old_index = row[1]
        if old_index not in profile_index:
            profile_index[old_index] = len(component_profiles)
            component_profiles.append(all_component_profiles[old_index])
        component_rows.append([row[0], profile_index[old_index]])
    # Lead identity and quote stay in the same row. This is critical in the
    # incomplete case, where hundreds of similar summaries have distinct quotes.
    leads = []
    window = view["request"]["departure_window"]
    origin = {x["value"] for x in view["request"]["origins"]}
    destination = {x["value"] for x in view["request"]["destinations"]}
    for lead in view["incomplete_leads"]:
        ref = lead["ref"]
        item = component_by_ref[ref]
        date = item.get("date")
        route_match = item["route"][0] in origin and item["route"][1] in destination
        in_window = bool(date and window and window["start"] <= date <= window["end"])
        schedule = ("timed" if item.get("depart") and item.get("arrive") else
                    "date_only" if date else "unknown")
        leads.append([ref, item["kind"], item["route"], date, item.get("program", "absent"),
                      item.get("cabin", "absent"), item.get("points", "absent"),
                      item.get("fees", "absent"), item["fee_unit"],
                      item.get("fee_currency", "absent"), item.get("cash", "absent"),
                      item.get("cash_currency", "absent"), item["price_scope"],
                      route_match, in_window, schedule,
                      item.get("seats", "absent"),
                      item.get("returned_travelers", "absent"),
                      item.get("findings", []),
                      [item.get("depart", "absent"), item.get("arrive", "absent"),
                       item.get("duration_minutes", "absent")] if schedule == "timed" else "-",
                      item.get("airports", "absent"), item.get("carriers", "absent"),
                      item.get("leg_cabins", "absent")])
    # Source-computed relation groups name every member. They do not rank or
    # prune; the writer still sees the complete eligible table.
    schedule_groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    same_award_arrival: dict[tuple[str, Any], list[str]] = defaultdict(list)
    for row in journey_rows:
        ref, profile_id, award, _cash = row[:4]
        profile = journey_profiles[profile_id]
        if profile.get("arrive"):
            same_award_arrival[(award, profile["arrive"])].append(ref)
        program = component_by_ref[award].get("program", "absent")
        cabin = profile.get("award_cabin", "absent")
        if (program not in NONVALUE_STATES and cabin not in NONVALUE_STATES and
            profile.get("depart") and profile.get("arrive")):
            schedule_groups[(program, profile["depart"], profile["arrive"],
                             profile["route"][0], profile["route"][1])].append(ref)
    lead_relevance: dict[tuple[bool, bool, str], list[str]] = defaultdict(list)
    for row in leads:
        lead_relevance[(row[13], row[14], row[15])].append(row[0])
    relations = {
        "same_award_arrival_alternatives": [[award, arrival, members]
            for (award, arrival), members in same_award_arrival.items()
            if len(members) > 1],
        "timing_match_cross_cabin": [members for members in schedule_groups.values()
            if len({journey_profiles[next(r[1] for r in journey_rows if r[0] == ref)]["award_cabin"]
                    for ref in members}) > 1],
        "lead_relevance": [[route, window, schedule, members]
            for (route, window, schedule), members in lead_relevance.items()],
    }
    policy = view["policy"]
    request = {k: view["request"][k] for k in
               ("travelers", "origins", "destinations", "departure_window",
                "cabins", "search_modes", "repositioning_allowed", "hard_constraints",
                "unknowns", "conflicts")}
    # Columnar profiles keep a single labeled lookup (alias -> profile), rather
    # than repeating field names per member. Null/absent defaults are explicit.
    caveat_profiles: list[list[Any]] = []
    caveat_index: dict[str, int] = {}
    for profile in journey_profiles:
        caveats = profile.get("caveats", [])
        key = str(caveats)
        if key not in caveat_index:
            caveat_index[key] = len(caveat_profiles)
            caveat_profiles.append(caveats)
        profile["caveats"] = caveat_index[key]
    journey_columns = [[p.get(key, "-") for key in JOURNEY_COLUMNS]
                       for p in journey_profiles]
    component_columns = [[p.get(key, "-") for key in COMPONENT_COLUMNS]
                         for p in component_profiles]
    all_observed = [row[2] for row in all_component_rows if row[2]]
    return {
        "legend": {
            "journey_row": ["J", "profile", "award_A", "cash_C"],
            "journey_profile": JOURNEY_COLUMNS,
            "component_row": ["A_or_C", "profile"],
            "component_profile": COMPONENT_COLUMNS,
            "lead_row": ["A_or_C", "kind", "route", "date", "program", "cabin",
                         "points", "fees", "fee_unit", "fee_currency", "cash",
                         "cash_currency", "price_scope", "request_route_match",
                         "in_departure_window", "schedule_state", "seats",
                         "returned_travelers", "findings", "timing", "airports",
                         "carriers", "leg_cabins"],
            "raw": "- means source absent or empty; explicit null/unknown states are retained. A profile applies to every row citing it.",
            "heuristic_cost": ["known_subtotal_usd", "complete_usd", "missing_parts", "completeness"],
            "styles": ["time", "cost", "premium"],
            "caveats": "Journey caveats index caveat_profiles; a bare code has unknown state. Traveler and seat support each retain passed versus unknown independently.",
            "relations": "Timing match is source schedule evidence, not proof of one physical flight; every listed alias remains independently selectable.",
            "ranking_hints": "Exact source Ranking index membership by J alias; hints do not force a selection or quota.",
            "timezones": {code: name for name, code in TIMEZONE_CODES.items()},
            "profiles": "Each numbered profile belongs to every row that cites it; no member is omitted.",
            "eligibility": "Only journey rows are eligible. Benchmarks and leads are separate roles.",
            "price": "Points, fees and cash retain their source scopes; heuristic USD is not payable cash.",
            "legs": "Airports, schedule, carrier and cabin scope are summarized here; exact per-leg records remain in canonical workspace evidence.",
            "leg_cabins": "Entries align with successive airport pairs; absent/unknown means those leg cabins are not established. Journey-level cabin does not prove every leg cabin.",
            "timing": ["departure_local_with_zone", "arrival_local_with_zone", "duration_minutes"],
            "lead_window": "Lead flag compares that observation's departure date with the request window; it does not establish a complete journey or connection.",
        },
        "request": request,
        "policy": {"ranking": policy["ranking"], "fx": policy["fx"]},
        "comparison": view["comparison"],
        "ranking_hints": ranking_hints,
        "journey_profiles": journey_columns,
        "caveat_profiles": caveat_profiles,
        "journey_rows": journey_rows,
        "component_profiles": component_columns,
        "component_rows": component_rows,
        "benchmark_refs": view["benchmarks"],
        "lead_rows": leads,
        "finding_catalog": finding_catalog,
        "relations": relations,
        "source_context": {"provider_status": view["coverage"]["provider_status"],
                           "observed_at_range": ([min(all_observed), max(all_observed)]
                                                 if all_observed else [None, None]),
                           "coverage_limits": [[group[k] for k in
                               ("kind", "status", "reason", "routes_and_dates")]
                               for group in view["coverage"]["groups"]
                               if group["status"] != "completed"],
                           "availability_guidance": evidence.availability_guidance},
    }
