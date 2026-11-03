"""V20 request and component traveler evidence, kept under exact journey ownership."""

from __future__ import annotations

from typing import Any, cast

from award_agent.providers.contracts import RawField

from .interactive_contracts import InteractivePreparedInput
from .workspace_contracts import WorkspaceEvidence


def _count(field: RawField) -> dict[str, object]:
    return {"state": field.state, "value": field.value,
            "source_field": field.source_field}


def build_traveler_evidence(focus: InteractivePreparedInput,
                            evidence: WorkspaceEvidence) -> dict[str, dict[str, object]]:
    """Bind known request size and raw component states without inferring support."""
    packet = focus.packet
    aliases = cast(dict[str, str], packet["wire_aliases"])
    by_journey = {item.candidate_id: item for item in evidence.journeys}
    by_component = {item.observation_id: item for item in evidence.components}
    requested = evidence.source.view.request.travelers
    if not isinstance(requested, int) or requested < 1:
        raise ValueError("V20 needs the canonical requested traveler count")
    result: dict[str, dict[str, object]] = {}
    for group in cast(list[dict[str, Any]], packet["journeys"]):
        facts = cast(dict[str, Any], group["facts"])
        award_support = facts.get("traveler_support")
        seat_check = facts.get("seat_support")
        if award_support not in {"passed", "failed", "unknown"} or \
                seat_check not in {"passed", "failed", "unknown"}:
            raise ValueError("V20 selected journey lacks canonical support states")
        for member in cast(list[dict[str, str | None]], group["members"]):
            ref = member["ref"]
            if not isinstance(ref, str) or ref not in aliases:
                raise ValueError("V20 journey lacks exact alias")
            canonical = focus.structured.references.journeys.get(aliases[ref])
            journey = by_journey.get(canonical or "")
            if journey is None:
                raise ValueError("V20 selected journey differs from source")
            award = by_component.get(journey.award_observation_id)
            cash = (by_component.get(journey.cash_observation_id)
                    if journey.cash_observation_id is not None else None)
            if award is None or (journey.cash_observation_id is not None and cash is None):
                raise ValueError("V20 journey component evidence is missing")
            award_ref = member.get("award_ref")
            cash_ref = member.get("cash_ref")
            if (not isinstance(award_ref, str) or award_ref not in aliases or
                    focus.structured.references.awards.get(aliases[award_ref]) !=
                    award.observation_id or
                    (cash is None and cash_ref is not None) or
                    (cash is not None and (not isinstance(cash_ref, str) or
                     cash_ref not in aliases or
                     focus.structured.references.cash.get(aliases[cash_ref]) !=
                     cash.observation_id))):
                raise ValueError("V20 journey component aliases differ from source")
            result[ref] = {
                "requested_travelers": requested,
                "award_component_ref": award_ref,
                "award_support_for_requested_party": award_support,
                "award_minimum_seats_check": seat_check,
                "award_reported_seats": _count(award.seats),
                "award_returned_travelers": _count(award.returned_travelers),
                "cash_component_ref": cash_ref,
                "cash_returned_travelers": _count(cash.returned_travelers) if cash else None,
                "meaning": "Requested party size is known. Component support follows its "
                           "separate evidence; absent returned travelers is not zero or failure. "
                           "These fields do not establish current availability, quote scope, "
                           "or bookability."}
    return result
