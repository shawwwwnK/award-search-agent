"""Compact, versioned writer view over canonical Ranking evidence.

The canonical projection remains the authority for checks and rendering. This module
only decides which facts the writer must read and how short typed references bind.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING, cast

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection

from .contracts import (
    AuthoringReferenceMap,
    CheckFinding,
    CompactAuthoringInput,
    ResultsDocument,
)

if TYPE_CHECKING:
    from .contracts import PreparedResultsInput


def _raw(value: dict[str, object]) -> dict[str, object]:
    return {key: value.get(key) for key in ("state", "value")}


def _time(value: dict[str, object]) -> dict[str, object]:
    result = {key: value.get(key) for key in ("local_iso", "timezone")}
    if result["local_iso"] is None and value.get("instant") is not None:
        result["instant"] = value["instant"]
    return result


def _component_facts(value: dict[str, object],
                     canonical: dict[str, object]) -> dict[str, object]:
    legs = []
    for leg in cast("list[dict[str, object]]", value.get("legs", [])):
        legs.append({
            "origin": leg["origin"], "destination": leg["destination"],
            "departure": _time(cast("dict[str, object]", leg["departure"])),
            "arrival": _time(cast("dict[str, object]", leg["arrival"])),
            "carrier": _raw(cast("dict[str, object]", leg["carrier"])),
            "flight_number": _raw(cast("dict[str, object]", leg["flight_number"])),
            "cabin": _raw(cast("dict[str, object]", leg["cabin"])),
        })
    return {
        "kind": value["kind"], "provider": value["provider"],
        "origin": value["origin"], "destination": value["destination"],
        "departure_date": value.get("departure_date"),
        "departure": _time(cast("dict[str, object]", value["departure"])),
        "arrival": _time(cast("dict[str, object]", value["arrival"])),
        "airport_sequence": value["airport_sequence"], "legs": legs,
        "requested_travelers": value["requested_travelers"],
        "requested_cabins": value["requested_cabins"],
        "returned_travelers": _raw(cast("dict[str, object]", value["returned_travelers"])),
        "cabin": _raw(cast("dict[str, object]", value["cabin"])),
        "program": _raw(cast("dict[str, object]", value["program"])),
        "points": _raw(cast("dict[str, object]", value["points"])),
        "taxes_fees": _raw(cast("dict[str, object]", value["taxes_fees"])),
        "taxes_fees_unit": value["taxes_fees_unit"],
        "tax_currency": _raw(cast("dict[str, object]", value["tax_currency"])),
        "seats": _raw(cast("dict[str, object]", value["seats"])),
        "cash_amount": _raw(cast("dict[str, object]", value["cash_amount"])),
        "cash_currency": _raw(cast("dict[str, object]", value["cash_currency"])),
        "price_scope": value["price_scope"],
        "duration_minutes": _raw(cast("dict[str, object]", value["duration_minutes"])),
        "stops": _raw(cast("dict[str, object]", value["stops"])),
        "carriers": value["carriers"],
        "mixed_cabin_pct": _raw(cast("dict[str, object]", value["mixed_cabin_pct"])),
        "reported_flight_numbers": _raw(cast("dict[str, object]", canonical["reported_flight_numbers"])),
        "findings": [{key: finding[key] for key in ("code", "severity", "message", "field")}
                     for finding in cast("list[dict[str, object]]", canonical["findings"])],
    }


def _compact_request(source: dict[str, object]) -> dict[str, object]:
    request = cast("dict[str, object]", source["request"])
    # Preserve semantic request constraints and unresolved state, not extraction lineage.
    return {key: value for key, value in request.items()
            if key not in {"raw_text", "field_provenance", "source_turn_ids"}}


def _coverage(source: dict[str, object]) -> dict[str, object]:
    groups = cast("list[dict[str, object]]", source["coverage_groups"])
    return {
        "provider_status": source["provider_status"],
        "groups": [{key: group[key] for key in ("kind", "status", "reason", "stream_complete",
                   "pair_coverage", "routes_and_dates") if key in group} for group in groups],
        "planning_coverage": source["planning_coverage"],
        "planning_strategy_notes": [{key: note[key] for key in ("reason", "material_uncertainty")
                                     if key in note} for note in cast("list[dict[str, object]]",
                                                                        source["planning_strategy_notes"])],
        "planning_issues": source["planning_issues"],
        "planning_deferred_constraints": source["planning_deferred_constraints"],
        "discovery_limitations": source["discovery_limitations"],
        "discovery_issues": source["discovery_issues"],
        "provider_findings": source["provider_findings"],
        "execution_findings": source["execution_findings"],
        "transport_findings": [finding["findings"] for finding in cast("list[dict[str, object]]",
                                                                     source["transport_findings"])],
    }


def _source_signature(value: dict[str, object]) -> dict[str, object]:
    clean = {key: item for key, item in value.items() if key not in {"observation_id", "query_id"}}
    clean["evidence"] = [{key: item for key, item in ref.items() if key != "retrieved_at"}
                         for ref in cast("list[dict[str, object]]", value["evidence"])]
    return clean


def _component_signature(component: dict[str, object],
                         source_map: dict[str, object]) -> str:
    canonical = {key: value for key, value in component.items()
                 if key not in {"observation_id", "query_id", "retrieved_at"}}
    signature: dict[str, object] = {"canonical": canonical, "source": _source_signature(source_map)}
    # Cross-query grouping is restricted to the validated gfly adapter family;
    # other providers require the same query identity.
    if (component["provider"] != "gfly" or
            component["provider_version"] != "0.3.0+award-search-unpriced-party-echo-v2"):
        signature["same_query"] = component["query_id"]
    if not source_map["evidence"] or not all(
        ref.get("sha256") for ref in cast("list[dict[str, object]]", source_map["evidence"])
    ):
        signature["unverified_source"] = component["observation_id"]
    return content_digest(signature)


def build_authoring_view(projection: SolutionProjection,
                         source: dict[str, object]) -> CompactAuthoringInput:
    """Build one deterministic writer catalog without changing canonical Ranking records."""
    view = projection.view
    eligible = [item for item in view.alternatives if item.status in {"admitted", "conditional"}]
    journey_refs = {f"J{i}": item.candidate_id for i, item in enumerate(eligible, 1)}
    journey_alias = {value: key for key, value in journey_refs.items()}
    lead_ids = (set(view.award_summary_observation_ids) |
                set(view.unmatched_award_observation_ids) |
                set(view.unpaired_positioning_observation_ids))
    retained_ids = ({item.award_observation_id for item in eligible} |
                    {item.cash_observation_id for item in eligible if item.cash_observation_id} |
                    set(view.direct_cash_observation_ids) | lead_ids)
    components = [item for item in view.components if item.observation_id in retained_ids]
    award_refs = {f"A{i}": item.observation_id for i, item in enumerate(
        (item for item in components if item.kind != "cash_itinerary"), 1)}
    cash_refs = {f"C{i}": item.observation_id for i, item in enumerate(
        (item for item in components if item.kind == "cash_itinerary"), 1)}
    component_alias = {value: key for key, value in (award_refs | cash_refs).items()}
    source_components = {item["observation_id"]: item for item in
                         cast("list[dict[str, object]]", source["components"])}
    evidence = {item.observation_id: item.model_dump(mode="json")
                for item in projection.receipt.observation_sources}
    canonical_components = {item.observation_id: item.model_dump(mode="json")
                            for item in view.components}
    component_signatures = {oid: _component_signature(component, evidence[oid])
                            for oid, component in canonical_components.items() if oid in evidence}
    component_groups: dict[str, dict[str, object]] = {}
    for component in components:
        raw = source_components[component.observation_id]
        facts = _component_facts(raw, canonical_components[component.observation_id])
        # Identical report content alone is insufficient: request semantics and retained
        # source hashes must agree. Timestamp stays on the member, never on the group.
        fingerprint = component_signatures[component.observation_id]
        group = component_groups.setdefault(fingerprint, {"facts": facts, "members": []})
        cast("list[dict[str, object]]", group["members"]).append({
            "ref": component_alias[component.observation_id],
            "observed_at": raw["retrieved_at"],
            "provider_updated_at": _raw(cast("dict[str, object]", raw["provider_updated_at"])),
        })
    reasons = {item.reason_set_id: item for item in view.reason_sets}
    costs = {item.cost_id: item for item in view.costs}
    cost_parts = {item.cost_component_id: item.component for item in view.cost_components}
    assessments = {item.assessment_id: item for item in view.assessments}
    required = cast("dict[str, object]", source.get("presentation_required_keys", {}))
    required_by_id = cast("dict[str, list[str]]", required.get("selected_journey_by_id", {}))
    profile_refs: dict[tuple[str, ...], str] = {}
    profiles: dict[str, list[str]] = {}
    journey_groups: dict[str, dict[str, object]] = {}
    for item in eligible:
        keys = tuple(required_by_id.get(item.candidate_id, []))
        if keys not in profile_refs:
            profile = f"D{len(profile_refs) + 1}"
            profile_refs[keys] = profile
            profiles[profile] = list(keys)
        reason_facts = [reason.model_dump(mode="json") for reason in reasons[item.reason_set_id].reasons]
        cost = costs.get(item.cost_id or "")
        cost_facts: dict[str, object] | None = None
        if cost:
            cost_facts = {key: value for key, value in cost.cost.model_dump(mode="json").items()
                          if key not in {"component_ids", "exact_subtotal_numerator",
                                         "exact_subtotal_denominator"}}
            cost_facts["components"] = [
                {"kind": cost_parts[cid].kind, "state": cost_parts[cid].state,
                 "scope": cost_parts[cid].scope, "reason": cost_parts[cid].reason,
                 "per_traveler_usd": (str(cost_parts[cid].per_traveler_usd)
                                      if cost_parts[cid].per_traveler_usd is not None else None)}
                for cid in cost.cost.component_ids]
        style_facts = [{"style": assessments[aid].style, "state": assessments[aid].state,
                        "feature_label": assessments[aid].feature_label,
                        "reasons": assessments[aid].reasons,
                        "validation_needs": assessments[aid].validation_needs}
                       for aid in item.assessment_ids]
        facts = {
            "topology": item.topology, "status": item.status,
            "origin": item.original_origin, "destination": item.original_destination,
            "departure": _time(item.departure.model_dump(mode="json")),
            "arrival": _time(item.arrival.model_dump(mode="json")),
            "departure_date": (item.original_departure_date.isoformat()
                               if item.original_departure_date else None),
            "transfer_airport": item.transfer_airport,
            "transfer_minutes": item.transfer_minutes,
            "transfer_local_day_offset": item.transfer_local_day_offset,
            "elapsed_minutes": str(item.elapsed_minutes) if item.elapsed_minutes is not None else None,
            "price_completeness": item.price_completeness,
            "booking_obligation": item.booking_obligation,
            "award_cabin": _raw(item.award_cabin.model_dump(mode="json")),
            "premium_economy_addon": item.premium_economy_addon,
            "positioning_reason": item.positioning_reason,
            "reasons": reason_facts, "cost": cost_facts, "assessments": style_facts,
            "disclosure_profile": profile_refs[keys],
        }
        award = source_components[item.award_observation_id]
        cash = source_components.get(item.cash_observation_id or "")
        canonical_cost = None
        if cost:
            canonical_cost = cost.cost.model_dump(mode="json", exclude={"component_ids"})
            canonical_cost["components"] = []
            for cid in cost.cost.component_ids:
                part = cost_parts[cid].model_dump(mode="json")
                part["observation_id"] = component_signatures[part["observation_id"]]
                cast("list[dict[str, object]]", canonical_cost["components"]).append(part)
        group_key = content_digest({
            "canonical_journey": item.model_dump(mode="json", exclude={
                "candidate_id", "option_family_id", "award_observation_id", "cash_observation_id",
                "strategy_id", "reason_set_id", "cost_id", "assessment_ids"}),
            "award": component_signatures[item.award_observation_id],
            "cash": component_signatures[item.cash_observation_id] if item.cash_observation_id else None,
            "reasons": reason_facts,
            "cost": canonical_cost,
            "assessments": [assessments[aid].model_dump(mode="json") for aid in item.assessment_ids],
            "disclosure_profile": profile_refs[keys],
        })
        group = journey_groups.setdefault(group_key, {"facts": facts, "members": []})
        cast("list[dict[str, object]]", group["members"]).append({
            "ref": journey_alias[item.candidate_id],
            "award": component_alias[item.award_observation_id],
            "cash": component_alias[item.cash_observation_id] if item.cash_observation_id else None,
            "award_observed_at": award["retrieved_at"],
            "cash_observed_at": cash["retrieved_at"] if cash else None,
        })
    excluded = [item for item in view.alternatives if item.status == "rejected"]
    failed_reasons: Counter[tuple[str, str]] = Counter()
    unresolved_caveats: Counter[tuple[str, str]] = Counter()
    for alternative in excluded:
        for reason in reasons[alternative.reason_set_id].reasons:
            if reason.state == "failed":
                failed_reasons[(reason.code, reason.detail)] += 1
            elif reason.state == "unknown":
                unresolved_caveats[(reason.code, reason.detail)] += 1
    comparison_refs = {"P1": tuple(view.comparison_pool_ids)}
    references = AuthoringReferenceMap(journeys=journey_refs, awards=award_refs,
                                       cash=cash_refs, comparison_pools=comparison_refs)
    compact_view: dict[str, object] = {
        "request": _compact_request(source),
        "policy": {"ranking": source["ranking_policy"],
                   "fx": {key: value for key, value in
                          cast("dict[str, object]", source["fx_snapshot"]).items()
                          if key not in {"snapshot_id", "source_digest"}},
                   "matching_version": source["matching_policy_version"]},
        "journeys": list(journey_groups.values()),
        "components": list(component_groups.values()),
        "benchmarks": [component_alias[oid] for oid in view.direct_cash_observation_ids],
        "incomplete_leads": [{"ref": component_alias[oid], "kind":
            "award_summary" if oid in view.award_summary_observation_ids else
            "unmatched_award" if oid in view.unmatched_award_observation_ids else
            "unpaired_positioning"} for oid in dict.fromkeys(
                (*view.award_summary_observation_ids, *view.unmatched_award_observation_ids,
                 *view.unpaired_positioning_observation_ids))],
        "exclusions": {"rejected_count": len(excluded),
                       "failed_reasons": [{"code": code, "detail": detail, "count": count}
                                          for (code, detail), count in sorted(failed_reasons.items())],
                       "unresolved_caveats": [{"code": code, "detail": detail, "count": count}
                                              for (code, detail), count in sorted(unresolved_caveats.items())],
                       "route_dates": sorted({f"{item.original_origin}-{item.original_destination} "
                           f"{item.original_departure_date}" for item in excluded})},
        "comparison": {"full_pool": "P1", "eligible_count": len(view.comparison_pool_ids),
                       "time_reference_minutes": source["time_reference_minutes"],
                       "cost_reference_usd": source["cost_reference_usd"]},
        "coverage": _coverage(source),
        "claim_catalog": source["claim_catalog"],
        "presentation_required_keys": {key: value for key, value in required.items()
                                       if key != "selected_journey_by_id"},
        "disclosure_profiles": profiles,
        "display_slot_vocabulary": source.get("display_slot_vocabulary", {}),
        "slot_key_catalog": source["slot_key_catalog"],
    }
    # Use JSON-native lists throughout so a saved artifact reconstructs the same
    # view after Pydantic serialization and exact replay.
    compact_view = json.loads(json.dumps(compact_view, ensure_ascii=False))
    bound = {"source_digest": projection.receipt.view_digest, "view": compact_view,
             "references": references.model_dump(mode="json")}
    return CompactAuthoringInput(source_digest=projection.receipt.view_digest,
                                 view=compact_view, references=references,
                                 binding_digest=content_digest(bound))


def verify_authoring_view(projection: SolutionProjection,
                          prepared: PreparedResultsInput) -> None:
    """Reject altered compact facts or mappings before replay or writer access."""
    actual = prepared.authoring_view
    if actual is None:
        raise ValueError("compact authoring view is missing")
    expected = build_authoring_view(projection, prepared.source)
    if (actual.contract_version != expected.contract_version or
            actual.source_digest != expected.source_digest or
            actual.binding_digest != expected.binding_digest or
            content_digest(actual.view) != content_digest(expected.view) or
            content_digest(actual.references) != content_digest(expected.references)):
        raise ValueError("compact authoring view differs from trusted source")


def _maps(prepared: PreparedResultsInput) -> tuple[dict[str, str], dict[str, str]]:
    compact = prepared.authoring_view
    if compact is None:
        raise ValueError("compact authoring view is missing")
    refs = compact.references
    aliases = refs.journeys | refs.awards | refs.cash
    reverse = {value: key for key, value in aliases.items()}
    if len(reverse) != len(aliases):
        raise ValueError("compact authoring references are ambiguous")
    return aliases, reverse


def _translate_document(prepared: PreparedResultsInput, document: ResultsDocument,
                        *, canonical: bool) -> ResultsDocument:
    aliases, reverse = _maps(prepared)
    refs = prepared.authoring_view.references  # type: ignore[union-attr]
    selection = document.selection.model_dump(mode="json")
    parts = [part.model_dump(mode="json") for part in document.parts]

    def change(value: str | None, kind: str) -> str | None:
        if value is None:
            return None
        if canonical:
            table = (refs.journeys if kind == "journey" else
                     refs.cash if kind == "benchmark" else
                     (refs.awards | refs.cash) if kind == "incomplete" else aliases)
            # An invalid marker cannot accidentally resolve to a canonical source ID.
            return table.get(value, f"invalid-authoring-reference:{kind}")
        table = {v: k for k, v in (refs.journeys if kind == "journey" else
                 refs.cash if kind == "benchmark" else
                 (refs.awards | refs.cash) if kind == "incomplete" else aliases).items()}
        return table.get(value, value if not _opaque(value) else f"unavailable-{kind}")

    selection["journey_ids"] = [change(v, "journey") for v in selection["journey_ids"]]
    selection["benchmark_observation_id"] = change(selection["benchmark_observation_id"], "benchmark")
    selection["incomplete_observation_ids"] = [change(v, "incomplete") for v in
                                              selection["incomplete_observation_ids"]]
    selection["excluded_journey_ids"] = [change(v, "journey") for v in
                                         selection["excluded_journey_ids"]]
    for part in parts:
        part["reference_id"] = change(part["reference_id"], str(part["scope"]))
        for claim in part["claims"]:
            values: list[str] = []
            scope_ids = claim["scope_ids"]
            comparison_pool = claim["kind"] == "comparison" and len(scope_ids) == 1
            if not canonical and claim["kind"] == "comparison":
                for pool_alias, pool in refs.comparison_pools.items():
                    width = len(pool)
                    if width and tuple(scope_ids) == pool:
                        scope_ids = [pool_alias]
                        break
            for value in scope_ids:
                if canonical and comparison_pool and value in refs.comparison_pools:
                    values.extend(refs.comparison_pools[value])
                elif canonical:
                    values.append(change(value, "claim") or "invalid-authoring-reference:claim")
                elif value == "P1":
                    values.append(value)
                else:
                    values.append(reverse.get(value, value if not _opaque(value) else "unavailable-claim"))
            claim["scope_ids"] = values
        for binding in part["shared_disclosures"]:
            binding["journey_ids"] = [change(v, "journey") for v in binding["journey_ids"]]
    return ResultsDocument.model_validate({"selection": selection, "parts": parts})


def rebind_document(prepared: PreparedResultsInput, document: ResultsDocument) -> ResultsDocument:
    """Bind only structured writer references to canonical Results identities."""
    return _translate_document(prepared, document, canonical=True)


def alias_document(prepared: PreparedResultsInput, document: ResultsDocument) -> ResultsDocument:
    """Keep correction drafts in the frozen short-reference namespace."""
    return _translate_document(prepared, document, canonical=False)


def _opaque(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def compact_payload(prepared: PreparedResultsInput,
                    feedback: tuple[CheckFinding, ...] = (),
                    previous_document: ResultsDocument | None = None) -> str:
    compact = prepared.authoring_view
    if compact is None:
        raise ValueError("compact authoring view is missing")
    _, reverse = _maps(prepared)
    findings = []
    for finding in feedback:
        row = finding.model_dump(mode="json")
        reference = finding.reference_id
        row["reference_id"] = reverse.get(reference or "", "unavailable-reference"
                                           if reference and _opaque(reference) else reference)
        findings.append(row)
    body = {"prepared": {"contract_version": compact.contract_version, "view": compact.view},
            "feedback": findings,
            "previous_document": (alias_document(prepared, previous_document).model_dump(mode="json")
                                  if previous_document else None)}
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
