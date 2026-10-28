"""Second isolated Luna writer-input hypothesis, built on reversible candidate v1.

Observed v1 failures motivate local exact-member identity, raw award carrier/cabin,
and traveler/seat reason copies. This module changes no Results runtime policy.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import candidate as v1

from award_agent.results.structured_contracts import StructuredPreparedInput

IDENTITY_FIELDS = ("origin", "destination", "departure", "arrival", "elapsed_minutes",
                   "award_cabin", "booking_obligation")
TRAVELER_REASON_CODES = frozenset({"award_travelers_supported", "award_travelers_unknown",
                                   "result_validation_minimum_award_seats"})
GUIDE = (
    "\n\nExact-member check: choice.identity beside each J reference repeats that exact "
    "member's complete-journey origin, destination, full dated local departure and "
    "arrival, elapsed minutes, reported journey cabin and booking obligation. "
    "Before writing an introduction, comparison, supporting card or reference, "
    "check that every mentioned date, time, cabin and route belongs to the same "
    "exact J member. Nearby aliases are distinct even when their schedules look "
    "similar. Do not print J/A/C aliases or internal IDs in traveler prose. "
    "choice.award_quote.program is the points program; its raw carriers field is "
    "the award component's reported carrier list and its cabin field is the "
    "award component's reported cabin. A program is not a flight carrier; do not "
    "infer any carrier or leg cabin from a connection airport or program name. "
    "choice.traveler_seat_assessment copies the exact journey's reason code, state "
    "and detail for traveler and minimum award-seat evidence. Interpret this "
    "independently of award/cash price_scope: unknown price scope alone does not "
    "make supported traveler evidence unknown. Unknown traveler or seat evidence "
    "remains unknown; do not claim bookable seats from a dated observation.\n"
    "Before saying an earlier arrival requires an earlier start, inspect eligible "
    "options with that same destination and full arrival timestamp for a later "
    "departure, elapsed time, quoted price scope and connection buffer. Explain "
    "a longer buffer if it is the actual reason to favor an earlier departure; "
    "separate-ticket protection remains unresolved. Do not presume a schedule "
    "variant dominates another merely from matching arrival.\n"
    "Report points quotes from different programs separately. Do not rank one "
    "program's mileage as lower, lowest or cheaper than another program's mileage, "
    "even if a later sentence says the currencies are incomparable. Compare "
    "points as a cost only within the same program.\n"
    "When there is no complete eligible journey, use incomplete_leads identities "
    "and the requested endpoint/date window to discuss the most relevant observed "
    "leads when useful. A different-origin or out-of-window component remains an "
    "incomplete observation; never present a known out-of-window positioning "
    "connection as a workable itinerary. Keep one connected natural answer with "
    "exact embedded references and no internal aliases in visible prose.\n"
)


def _components(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for group in view["components"]:
        for member in group["members"]:
            alias = member["ref"]
            if alias in result:
                raise ValueError(f"duplicate component alias: {alias}")
            result[alias] = group["facts"]
    return result


def transform(request: dict[str, Any], prepared: StructuredPreparedInput) -> dict[str, Any]:
    result = v1.transform(request, prepared)
    body = json.loads(result["input"])
    view = body["prepared"]["view"]
    originals = prepared.authoring_view.view["journeys"]
    if len(view["journeys"]) != len(originals):
        raise ValueError("v1 journey grouping changed")
    components = _components(prepared.authoring_view.view)
    for revised_group, source_group in zip(view["journeys"], originals, strict=True):
        facts = source_group["facts"]
        assessment = [{key: copy.deepcopy(reason[key]) for key in ("code", "state", "detail")}
                      for reason in facts["reasons"]
                      if reason["code"] in TRAVELER_REASON_CODES]
        if len(revised_group["members"]) != len(source_group["members"]):
            raise ValueError("v1 journey member count changed")
        for revised, source in zip(revised_group["members"],
                                   source_group["members"], strict=True):
            if revised["ref"] != source["ref"] or revised["award"] != source["award"]:
                raise ValueError("v1 journey member identity changed")
            award = components[source["award"]]
            choice = revised["choice"]
            choice["identity"] = {field: copy.deepcopy(facts[field]) for field in IDENTITY_FIELDS}
            choice["traveler_seat_assessment"] = copy.deepcopy(assessment)
            choice["award_quote"]["carriers"] = copy.deepcopy(award["carriers"])
            choice["award_quote"]["cabin"] = copy.deepcopy(award["cabin"])
    result["instructions"] += GUIDE
    result["input"] = v1.compact(body, sort_keys=False)
    return result


def restore(request: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(request)
    if not result["instructions"].endswith(GUIDE):
        raise ValueError("v2 guide missing")
    result["instructions"] = result["instructions"][:-len(GUIDE)]
    body = json.loads(result["input"])
    for group in body["prepared"]["view"]["journeys"]:
        for member in group["members"]:
            choice = member["choice"]
            choice.pop("identity")
            choice.pop("traveler_seat_assessment")
            choice["award_quote"].pop("carriers")
            choice["award_quote"].pop("cabin")
    result["input"] = v1.compact(body, sort_keys=False)
    return v1.restore(result)
