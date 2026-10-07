"""Deterministic Results preparation, checks, delivery, and exact replay."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from html import escape
from typing import Literal, cast

from award_agent.providers.contracts import RawField, content_digest
from award_agent.ranking.projection_contracts import (
    SolutionAlternative,
    SolutionComponent,
    SolutionProjection,
    SolutionView,
)

from .contracts import (
    CheckFinding,
    DeclaredClaim,
    PreparedResultsInput,
    RenderedFact,
    ResultsArtifact,
    ResultsAttempt,
    ResultsConfig,
    ResultsDocument,
    ResultsPart,
    ResultsWriter,
    ResultsWriterError,
    ValidationNotice,
    WriterReceipt,
)

SLOT_RE = re.compile(r"\{\{fact:([a-z][a-z0-9_]*)\}\}")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
INSTRUCTIONS = """Write a useful Results answer using only supplied source facts. You control headings,
ordering, prose, grouping, tables, and selected distinct alternatives. Use ordered scoped Markdown
parts and exact {{fact:key}} slots for factual values; slots resolve only within a part's scope and
reference_id. You may assign each journey a unique traveler-friendly identifier in each part's
identifier field; show it visibly and use the same identifier when that journey resumes. The
{{fact:journey_id}} slot is also available. Select
complete admitted or conditional journeys as recommendations; rejected journeys must be described
as excluded. Keep the direct cash benchmark separate. Declare material cabin, connection-protection,
price-scope, comparison, and eligibility claims with their literal claim text and exact scope IDs.
Supply disclosures for timing, cabin evidence, costs and quote scope, unresolved requirements,
separate-ticket obligations, component observation dates, and search coverage. Missing information
must remain unknown. Usually select three distinct journeys; five is a soft presentation target.
Do not invent availability, protection, leg cabins, party totals, or valuation arithmetic.
Use source.claim_catalog proposition names for supported deterministic checks. A claim's text must
appear visibly in its part. For comparisons, scope_ids must equal the supplied comparison_pool_ids.
"""


def _slot_tokens(markdown: str) -> tuple[tuple[int, int, str | None], ...]:
    """Lex original authored slots once, including nested malformed references."""
    tokens: list[tuple[int, int, str | None]] = []
    cursor = 0
    while (start := markdown.find("{{fact:", cursor)) >= 0:
        position = start + len("{{fact:")
        depth = 1
        while position < len(markdown) and markdown[position] != "\n":
            if markdown.startswith("{{fact:", position):
                depth += 1
                position += len("{{fact:")
            elif markdown.startswith("}}", position):
                depth -= 1
                position += 2
                if depth == 0:
                    break
            else:
                position += 1
        match = SLOT_RE.fullmatch(markdown[start:position]) if depth == 0 else None
        tokens.append((start, position, match.group(1) if match else None))
        cursor = max(position, start + 1)
    return tuple(tokens)


def _slot_keys(markdown: str) -> set[str]:
    return {key for _, _, key in _slot_tokens(markdown) if key is not None}


def _visible_parts(parts: tuple[ResultsPart, ...]) -> tuple[str, ...]:
    """Exclude non-visible Markdown destinations and code across part boundaries."""
    visible: list[str] = []
    fence: str | None = None
    comment = False
    for part in parts:
        lines: list[str] = []
        for line in part.markdown.splitlines(keepends=True):
            stripped = line.lstrip()
            marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else None
            if marker:
                if fence == marker:
                    fence = None
                elif fence is None:
                    fence = marker
                lines.append("\n")
                continue
            if fence:
                lines.append("\n")
                continue
            if comment:
                end = line.find("-->")
                if end < 0:
                    lines.append("\n")
                    continue
                line = line[end + 3:]
                comment = False
            while "<!--" in line:
                start = line.find("<!--")
                end = line.find("-->", start + 4)
                if end < 0:
                    line = line[:start]
                    comment = True
                    break
                line = line[:start] + line[end + 3:]
            line = re.sub(r"`[^`]*`", "", line)
            line = IMAGE_RE.sub("", line)
            line = LINK_RE.sub(r"\1", line)
            lines.append(line)
        visible.append("".join(lines))
    return tuple(visible)


def _plain(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, RawField):
        return str(value.value) if value.state == "value" else "unknown"
    return str(value)


def _safe(value: object) -> str:
    """Escape source text as a Markdown literal; never parse source as markup."""
    result = escape(_plain(value), quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", result).replace("\n", " ")


def _when(time: object) -> str:
    local = getattr(time, "local_iso", None)
    zone = getattr(time, "timezone", None)
    instant = getattr(time, "instant", None)
    return f"{local or 'local time unknown'} ({zone or 'timezone unknown'}; UTC {instant or 'unknown'})"


def _component_slots(component: SolutionComponent,
                     scope: Literal["benchmark", "incomplete"]) -> dict[str, str]:
    slots = {
        "observation_id": component.observation_id,
        "kind": component.kind,
        "disposition": "direct cash benchmark only" if scope == "benchmark"
                       else "incomplete research lead; not a complete journey",
        "route": f"{component.origin} to {component.destination}",
        "departure": _when(component.departure),
        "arrival": _when(component.arrival),
        "program": _plain(component.program),
        "carrier": ", ".join(component.carriers) or "unreported",
        "cabin": _plain(component.cabin),
        "mixed_cabin_pct": f"{_plain(component.mixed_cabin_pct)}% of distance below reported cabin",
        "leg_cabins": "; ".join(
            f"{leg.origin}–{leg.destination}: {_plain(leg.cabin)}" for leg in component.legs
        ) or "leg cabins unreported",
        "points": _plain(component.points),
        "fees": f"{_plain(component.taxes_fees)} {_plain(component.tax_currency)} "
                f"({component.taxes_fees_unit} units)",
        "cash": f"{_plain(component.cash_amount)} {_plain(component.cash_currency)}",
        "price_scope": component.price_scope,
        "observed_at": component.retrieved_at.isoformat(),
        "provider_updated_at": _plain(component.provider_updated_at),
        "requested_travelers": str(component.requested_travelers),
    }
    return {key: _safe(value) for key, value in slots.items()}


def _journey_slots(view: SolutionView, alternative: SolutionAlternative,
                   components: dict[str, SolutionComponent]) -> dict[str, str]:
    award = components[alternative.award_observation_id]
    cash = components.get(alternative.cash_observation_id or "")
    reasons = next(record.reasons for record in view.reason_sets
                   if record.reason_set_id == alternative.reason_set_id)
    unresolved = [reason.detail for reason in reasons if reason.state != "passed"]
    assessments = {record.assessment_id: record for record in view.assessments}
    styles = ", ".join(f"{assessments[aid].style}: {assessments[aid].state}"
                        for aid in alternative.assessment_ids) or "no style membership reported"
    slots = {
        "journey_id": alternative.candidate_id,
        "status": alternative.status,
        "styles": styles,
        "option_family_id": alternative.option_family_id,
        "route": f"{alternative.original_origin} to {alternative.original_destination}",
        "departure": _when(alternative.departure),
        "arrival": _when(alternative.arrival),
        "elapsed": f"{alternative.elapsed_minutes} minutes" if alternative.elapsed_minutes is not None else "unknown",
        "transfer": f"{alternative.transfer_minutes} minutes at {alternative.transfer_airport}"
                    if alternative.transfer_minutes is not None else "no reported transfer wait",
        "award_program": _plain(award.program),
        "award_route": f"{award.origin} to {award.destination}",
        "award_departure": _when(award.departure),
        "award_arrival": _when(award.arrival),
        "award_carrier": ", ".join(award.carriers) or "unreported",
        "award_cabin": _plain(alternative.award_cabin),
        "award_mixed_cabin_pct": f"{_plain(award.mixed_cabin_pct)}% of distance below reported award cabin",
        "award_leg_cabins": "; ".join(
            f"{leg.origin}–{leg.destination}: {_plain(leg.cabin)}" for leg in award.legs
        ) or "award leg cabins unreported",
        "cash_cabin": _plain(cash.cabin) if cash else "no cash flight",
        "cash_mixed_cabin_pct": (f"{_plain(cash.mixed_cabin_pct)}% of distance below reported cash cabin"
                                 if cash else "no cash flight"),
        "cash_leg_cabins": "; ".join(
            f"{leg.origin}–{leg.destination}: {_plain(leg.cabin)}" for leg in cash.legs
        ) if cash and cash.legs else "cash leg cabins unreported" if cash else "no cash flight",
        "cash_route": f"{cash.origin} to {cash.destination}" if cash else "no cash component",
        "cash_departure": _when(cash.departure) if cash else "no cash component",
        "cash_arrival": _when(cash.arrival) if cash else "no cash component",
        "points": f"{_plain(award.points)} points",
        "fees": f"{_plain(award.taxes_fees)} {_plain(award.tax_currency)} "
                f"({award.taxes_fees_unit} units)",
        "cash": f"{_plain(cash.cash_amount)} {_plain(cash.cash_currency)}" if cash else "no cash component",
        "award_price_scope": award.price_scope,
        "cash_price_scope": cash.price_scope if cash else "no cash component",
        "price_completeness": alternative.price_completeness,
        "booking_obligation": alternative.booking_obligation,
        "requirements": "; ".join(unresolved) or "none reported by upstream matching",
        "award_observed_at": award.retrieved_at.isoformat(),
        "cash_observed_at": cash.retrieved_at.isoformat() if cash else "no cash component",
    }
    return {key: _safe(value) for key, value in slots.items()}


def _shared_slots(view: SolutionView) -> dict[str, str]:
    coverage = "; ".join(f"{group.kind}: {group.status} ({group.reason}); "
                         f"{', '.join(group.routes_and_dates) or 'route details unavailable'}"
                         for group in view.coverage_groups) or "coverage unavailable"
    return {"coverage": _safe(coverage), "provider_status": _safe(view.provider_status),
            "complete_journey_count": str(sum(item.status in {"admitted", "conditional"}
                                              for item in view.alternatives)),
            "benchmark_status": _safe("available" if view.direct_cash_observation_ids
                                      else "unavailable")}


def prepare_slot_keys(view: SolutionView, scope: str, reference_id: str | None,
                      components: dict[str, SolutionComponent],
                      alternatives: dict[str, SolutionAlternative]) -> set[str]:
    if scope == "shared" and reference_id is None:
        return set(_shared_slots(view))
    if scope == "journey" and reference_id in alternatives:
        return set(_journey_slots(view, alternatives[reference_id], components))
    if scope in {"benchmark", "incomplete"} and reference_id in components:
        return set(_component_slots(components[reference_id], cast("Literal['benchmark', 'incomplete']", scope)))
    return set()


def _valid_part_reference(part: ResultsPart, view: SolutionView) -> bool:
    rid = part.reference_id
    if part.scope == "shared":
        return rid is None
    if part.scope == "journey":
        return rid in {item.candidate_id for item in view.alternatives}
    if part.scope == "benchmark":
        return rid in view.direct_cash_observation_ids
    return rid in (set(view.award_summary_observation_ids) |
                   set(view.unmatched_award_observation_ids) |
                   set(view.unpaired_positioning_observation_ids))


def _source(view: SolutionView) -> dict[str, object]:
    # All alternatives remain present. Linked records retain decision-relevant facts.
    return {
        "request": view.request.model_dump(mode="json"),
        "ranking_policy": view.policy.model_dump(mode="json"),
        "fx_snapshot": view.fx_snapshot.model_dump(mode="json"),
        "matching_policy_version": view.matching_policy_version,
        "claim_catalog": {
            "cabin": {"journey_business": "Award journey-level business cabin evidence only",
                      "component_business": "Scoped benchmark or incomplete component cabin evidence",
                      "all_award_legs_business": "Every award leg is business",
                      "all_legs_business": "Every award and cash leg in the journey is business"},
            "connection_protection": {"protected_connection": "Separate-ticket protection assertion"},
            "price_scope": {"party_total": "Every journey price component covers the party",
                            "per_traveler": "Every journey price component is per traveler"},
            "comparison": {"fastest": "Journey equals Ranking's complete-pool elapsed-time reference",
                           "cheapest": "Journey equals Ranking's complete heuristic USD cost reference"},
            "eligibility": {"no_unresolved_requirements": "Admitted with no unresolved matching reasons"},
            "other": "Other claims are unchecked by the M2 catalog",
        },
        "provider_status": view.provider_status,
        "alternatives": [item.model_dump(mode="json") for item in view.alternatives],
        "components": [item.model_dump(mode="json", exclude={
            "backend", "provider_version", "provider_record_id", "logical_query_ids",
            "logical_use_ids", "strategy_ids", "reported_flight_numbers", "findings",
        }) for item in view.components],
        "reason_sets": [item.model_dump(mode="json") for item in view.reason_sets],
        "cost_components": [item.model_dump(mode="json") for item in view.cost_components],
        "costs": [item.model_dump(mode="json") for item in view.costs],
        "assessments": [item.model_dump(mode="json") for item in view.assessments],
        "indexes": view.indexes.model_dump(mode="json"),
        "comparison_pool_ids": list(view.comparison_pool_ids),
        "time_reference_minutes": str(view.time_reference_minutes) if view.time_reference_minutes is not None else None,
        "cost_reference_usd": str(view.cost_reference_usd) if view.cost_reference_usd is not None else None,
        "direct_cash_observation_ids": list(view.direct_cash_observation_ids),
        "award_summary_observation_ids": list(view.award_summary_observation_ids),
        "unmatched_award_observation_ids": list(view.unmatched_award_observation_ids),
        "unpaired_positioning_observation_ids": list(view.unpaired_positioning_observation_ids),
        "coverage_groups": [item.model_dump(mode="json") for item in view.coverage_groups],
        "planning_issues": [item.model_dump(mode="json") for item in view.planning_issues],
        "planning_deferred_constraints": [item.model_dump(mode="json") for item in view.planning_deferred_constraints],
        "planning_coverage": view.planning_coverage.model_dump(mode="json"),
        "planning_strategy_notes": [item.model_dump(mode="json")
                                    for item in view.planning_strategy_notes],
        "discovery_limitations": list(view.discovery_limitations),
        "discovery_issues": [item.model_dump(mode="json") for item in view.discovery_issues],
        "provider_findings": [item.model_dump(mode="json") for item in view.provider_findings],
        "execution_findings": [item.model_dump(mode="json") for item in view.execution_findings],
        "transport_findings": [item.model_dump(mode="json") for item in view.transport_findings],
    }


def prepare_results(projection: SolutionProjection, config: ResultsConfig) -> PreparedResultsInput:
    # Revalidation checks the receipt/view digest and all exact references before writer access.
    trusted = SolutionProjection.model_validate(projection.model_dump(mode="json"))
    view = trusted.view
    components = {item.observation_id: item for item in view.components}
    slots = {"shared": _shared_slots(view)}
    slots.update({f"journey:{item.candidate_id}": _journey_slots(view, item, components)
                  for item in view.alternatives})
    slots.update({f"benchmark:{item.observation_id}": _component_slots(item, "benchmark")
                  for item in view.components if item.observation_id in view.direct_cash_observation_ids})
    slots.update({f"incomplete:{item.observation_id}": _component_slots(item, "incomplete")
                  for item in view.components if item.observation_id in (
                      set(view.award_summary_observation_ids) |
                      set(view.unmatched_award_observation_ids) |
                      set(view.unpaired_positioning_observation_ids))})
    source = _source(view)
    source["slot_key_catalog"] = {
        "shared": sorted(slots["shared"]),
        "journey": sorted(next((value for key, value in slots.items()
                                if key.startswith("journey:")), {})),
        "benchmark": sorted(next((value for key, value in slots.items()
                                  if key.startswith("benchmark:")), {})),
        "incomplete": sorted(next((value for key, value in slots.items()
                                   if key.startswith("incomplete:")), {})),
    }
    initial = PreparedResultsInput(source_digest=trusted.receipt.view_digest, source=source,
        slots=slots, instructions=INSTRUCTIONS, input_bytes=0, estimated_input_tokens=0,
        estimated_total_tokens=0)
    size, total, _, _ = _measurement(initial, config, (), None)
    return initial.model_copy(update={"input_bytes": size,
        "estimated_input_tokens": total - config.max_output_tokens,
        "estimated_total_tokens": total})


def authoring_payload(prepared: PreparedResultsInput,
                      feedback: tuple[CheckFinding, ...] = (),
                      previous_document: ResultsDocument | None = None) -> str:
    body = {
        "prepared": prepared.model_dump(mode="json", exclude={"instructions", "slots", "input_bytes",
            "estimated_input_tokens", "estimated_total_tokens"}),
        "feedback": [finding.model_dump(mode="json") for finding in feedback],
        "previous_document": previous_document.model_dump(mode="json") if previous_document else None,
    }
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _measurement(prepared: PreparedResultsInput, config: ResultsConfig,
                 feedback: tuple[CheckFinding, ...], previous_document: ResultsDocument | None,
                 ) -> tuple[int, int, str, str]:
    payload = authoring_payload(prepared, feedback, previous_document)
    # The adapter's strict schema may add required fields. The explicit buffer covers
    # protocol wrapping; byte count is a conservative token upper bound, not tokenizer proof.
    from openai.lib._pydantic import to_strict_json_schema
    schema = to_strict_json_schema(ResultsDocument)
    schema_text = json.dumps(schema, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    prompt = prepared.instructions + payload
    size = len(prompt.encode("utf-8")) + len(schema_text.encode("utf-8"))
    return size, size + config.prompt_overhead_tokens + config.max_output_tokens, \
        content_digest(prompt), content_digest(schema_text)


def _failure(code: str, scope: Literal["shared", "journey", "benchmark", "incomplete"],
             reference_id: str | None, part_index: int | None,
             message: str, fact: str | None = None, claim_id: str | None = None,
             outcome: Literal["supported", "failed", "unchecked", "insufficient_evidence"] = "failed") -> CheckFinding:
    return CheckFinding(code=code, outcome=outcome, scope=scope,
                        reference_id=reference_id, part_index=part_index,
                        claim_id=claim_id, message=message, supplied_fact=fact)


def _claim_check(claim: DeclaredClaim, part: ResultsPart, index: int,
                 view: SolutionView) -> CheckFinding:
    alternatives = {item.candidate_id: item for item in view.alternatives}
    components = {item.observation_id: item for item in view.components}
    reference = part.reference_id
    target = alternatives.get(reference or "")
    component = components.get(reference or "") if part.scope in {"benchmark", "incomplete"} else None
    code = f"claim:{claim.kind}:{claim.proposition}"
    result: Literal["supported", "failed", "unchecked", "insufficient_evidence"] = "unchecked"
    fact: str | None = None
    proposition = claim.proposition
    if claim.kind == "cabin" and proposition in {
        "all_legs_business", "all_award_legs_business", "journey_business", "component_business"
    }:
        if component:
            if proposition in {"component_business", "journey_business"}:
                result = ("supported" if component.cabin.state == "value" and
                          "business" in _plain(component.cabin).lower() else
                          "failed" if component.cabin.state == "value" else "insufficient_evidence")
                fact = f"Scoped component cabin evidence: {_plain(component.cabin)}."
            elif proposition == "all_legs_business" or (
                    proposition == "all_award_legs_business" and component.kind.startswith("award")):
                if any(leg.cabin.state == "value" and "business" not in _plain(leg.cabin).lower()
                       for leg in component.legs):
                    result = "failed"
                elif not component.legs or any(leg.cabin.state != "value" for leg in component.legs):
                    result = "insufficient_evidence"
                else:
                    result = "supported"
                fact = "Scoped component leg cabins: " + ", ".join(
                    f"{leg.origin}–{leg.destination} {_plain(leg.cabin)}" for leg in component.legs)
            else:
                result = "insufficient_evidence"
                fact = "This cabin proposition does not describe the scoped component."
        elif target:
            award = components[target.award_observation_id]
            if proposition in {"journey_business", "component_business"}:
                result = ("supported" if "business" in _plain(target.award_cabin).lower()
                          else "failed" if target.award_cabin.state == "value"
                          else "insufficient_evidence")
                fact = f"Journey award cabin evidence: {_plain(target.award_cabin)}."
            else:
                cash = components.get(target.cash_observation_id or "") if (
                    proposition == "all_legs_business") else None
                legs = award.legs + (cash.legs if cash else ())
                try:
                    mixed = Decimal(str(award.mixed_cabin_pct.value)) if (
                        award.mixed_cabin_pct.state == "value") else None
                except (InvalidOperation, TypeError):
                    mixed = None
                try:
                    cash_mixed = Decimal(str(cash.mixed_cabin_pct.value)) if cash and (
                        cash.mixed_cabin_pct.state == "value") else None
                except (InvalidOperation, TypeError):
                    cash_mixed = None
                contradicted = (
                    (mixed is not None and mixed > 0 and
                     "business" in _plain(award.cabin).lower()) or
                    (cash_mixed is not None and cash_mixed > 0 and cash is not None and
                     "business" in _plain(cash.cabin).lower()) or
                    (cash is not None and cash.cabin.state == "value" and
                     "business" not in _plain(cash.cabin).lower()) or
                    any(leg.cabin.state == "value" and
                        "business" not in _plain(leg.cabin).lower() for leg in legs)
                )
                missing = ((cash is not None and cash.cabin.state != "value") or
                           not award.legs or (cash is not None and not cash.legs) or
                           any(leg.cabin.state != "value" for leg in legs))
                if contradicted:
                    result = "failed"
                elif missing:
                    result = "insufficient_evidence"
                else:
                    result = "supported"
                fact = "Reported award mixed cabin percentage: " + _plain(award.mixed_cabin_pct) + \
                       ". Cash mixed cabin percentage: " + (
                           _plain(cash.mixed_cabin_pct) if cash else "no cash flight") + \
                       ". Leg cabins: " + ", ".join(
                           f"{leg.origin}–{leg.destination} {_plain(leg.cabin)}" for leg in legs)
    elif claim.kind == "connection_protection" and proposition == "protected_connection":
        if target:
            result = "failed" if target.booking_obligation == "separate_tickets_unverified" else "insufficient_evidence"
            fact = f"Booking obligation: {target.booking_obligation}; protection is not confirmed."
    elif claim.kind == "price_scope" and proposition in {"party_total", "per_traveler"}:
        if component:
            expected = "party" if proposition == "party_total" else "per_traveler"
            result = ("supported" if component.price_scope == expected else
                      "insufficient_evidence" if component.price_scope == "unknown" else "failed")
            fact = f"Scoped component quote scope: {component.price_scope}."
        elif target:
            award = components[target.award_observation_id]
            cash = components.get(target.cash_observation_id or "")
            scopes = [award.price_scope] + ([cash.price_scope] if cash else [])
            expected = "party" if proposition == "party_total" else "per_traveler"
            if any(scope != expected and scope != "unknown" for scope in scopes):
                result = "failed"
            elif "unknown" in scopes:
                result = "insufficient_evidence"
            else:
                result = "supported"
            fact = "Quote scopes: " + ", ".join(scopes) + "."
    elif claim.kind == "comparison" and proposition in {"fastest", "cheapest"}:
        ids = tuple(claim.scope_ids)
        if reference and reference in ids and ids and all(cid in alternatives for cid in ids):
            if set(ids) != set(view.comparison_pool_ids):
                result = "insufficient_evidence"
                fact = "The declared comparison scope does not match the supplied comparison pool."
            elif proposition == "fastest":
                if view.time_reference_microseconds is None or target is None or target.elapsed_microseconds is None:
                    result = "insufficient_evidence"
                else:
                    result = "supported" if target.elapsed_microseconds == view.time_reference_microseconds else "failed"
                fact = f"Supplied fastest reference: {view.time_reference_minutes} elapsed minutes; " \
                       f"this journey: {target.elapsed_minutes if target else 'unknown'} minutes."
            else:
                costs = {record.cost_id: record.cost for record in view.costs}
                target_cost = costs.get(target.cost_id) if target and target.cost_id else None
                if (view.cost_reference_numerator is None or view.cost_reference_denominator is None
                        or target_cost is None or target_cost.exact_subtotal_numerator is None
                        or target_cost.exact_subtotal_denominator is None or
                        target_cost.completeness != "complete"):
                    result = "insufficient_evidence"
                else:
                    result = ("supported" if target_cost.exact_subtotal_numerator *
                              view.cost_reference_denominator == view.cost_reference_numerator *
                              target_cost.exact_subtotal_denominator else "failed")
                fact = f"Supplied complete heuristic USD reference: {view.cost_reference_usd}; " \
                       f"this journey: {target_cost.complete_usd if target_cost else 'unknown'}."
    elif claim.kind == "eligibility" and proposition == "no_unresolved_requirements" and target:
        reasons = next(record.reasons for record in view.reason_sets
                       if record.reason_set_id == target.reason_set_id)
        unresolved = [reason.detail for reason in reasons if reason.state != "passed"]
        result = "failed" if target.status != "admitted" or unresolved else "supported"
        fact = f"Upstream status: {target.status}. " + (
            "Unresolved: " + "; ".join(unresolved) if unresolved else "No unresolved matching reasons.")
    elif claim.kind != "other" and proposition in {
        "journey_business", "component_business", "all_legs_business", "all_award_legs_business",
        "protected_connection", "party_total", "per_traveler", "fastest", "cheapest",
        "no_unresolved_requirements",
    }:
        result = "insufficient_evidence"
        fact = "The exact scoped source lacks evidence for this proposition."
    return _failure(code, part.scope, reference, index,
                    f"The assertion ‘{claim.text}’ is {result.replace('_', ' ')}.",
                    fact, claim.claim_id, result)


def check_document(document: ResultsDocument, projection: SolutionProjection) -> tuple[CheckFinding, ...]:
    view = projection.view
    alternatives = {item.candidate_id: item for item in view.alternatives}
    components = {item.observation_id: item for item in view.components}
    visible = _visible_parts(document.parts)
    findings: list[CheckFinding] = []
    labels: dict[str, str] = {}
    label_owners: dict[str, str] = {}
    selection = document.selection
    for candidate_id in selection.journey_ids:
        alternative = alternatives.get(candidate_id)
        if alternative is None or alternative.status not in {"admitted", "conditional"}:
            detail = (f"{candidate_id} is {alternative.status} and excluded by upstream matching."
                      if alternative else "Details unavailable.")
            findings.append(_failure("invalid_selection", "journey", candidate_id, None,
                                     "Selected recommendation is unavailable or excluded.", detail))
        if not any(part.scope == "journey" and part.reference_id == candidate_id
                   for part in document.parts):
            findings.append(_failure("missing_selected_journey", "journey", candidate_id, None,
                                     "Selected journey has no visible explanation.",
                                     "Details unavailable."))
    if len(selection.journey_ids) > 5:
        findings.append(_failure("over_target", "shared", None, None,
                                 "More than five complete journeys were selected.",
                                 f"{len(selection.journey_ids)} journeys were selected; review the distinct choices."))
    if selection.benchmark_observation_id and selection.benchmark_observation_id not in view.direct_cash_observation_ids:
        findings.append(_failure("benchmark_reference", "benchmark", selection.benchmark_observation_id,
                                 None, "The direct cash benchmark reference is unavailable.", "Details unavailable."))
    if selection.benchmark_observation_id and not any(
        part.scope == "benchmark" and part.reference_id == selection.benchmark_observation_id
        for part in document.parts
    ):
        findings.append(_failure("missing_benchmark", "benchmark", selection.benchmark_observation_id,
                                 None, "Selected benchmark has no visible explanation.",
                                 "Direct cash benchmark details unavailable."))
    for observation_id in selection.incomplete_observation_ids:
        if observation_id not in (set(view.award_summary_observation_ids) |
                                  set(view.unmatched_award_observation_ids) |
                                  set(view.unpaired_positioning_observation_ids)):
            findings.append(_failure("incomplete_reference", "incomplete", observation_id,
                                     None, "Incomplete lead reference is unavailable.",
                                     "Details unavailable."))
        elif not any(part.scope == "incomplete" and part.reference_id == observation_id
                     for part in document.parts):
            findings.append(_failure("missing_incomplete_lead", "incomplete", observation_id,
                                     None, "Selected incomplete lead has no visible explanation.",
                                     "This is an incomplete research lead, not a complete journey."))
    for index, part in enumerate(document.parts):
        rid = part.reference_id
        valid = _valid_part_reference(part, view)
        if not valid:
            findings.append(_failure("unavailable_reference", part.scope, rid, index,
                                     "Factual reference could not be resolved.", "Details unavailable."))
            continue
        if part.scope == "journey" and rid:
            label = (part.identifier or "").strip()
            if label:
                if label not in visible[index]:
                    findings.append(_failure("identifier_not_visible", "journey", rid, index,
                        "The journey identifier is not visible in its authored part.",
                        f"Journey ID: {_safe(rid)}."))
                if rid in labels and labels[rid] != label:
                    findings.append(_failure("identifier_changed", "journey", rid, index,
                        "The resumed journey uses a different identifier.",
                        f"Earlier identifier: {_safe(labels[rid])}."))
                owner = label_owners.get(label.casefold())
                if owner is not None and owner != rid:
                    findings.append(_failure("identifier_reused", "journey", rid, index,
                        "The same identifier was used for another journey variant.",
                        f"Journey ID: {_safe(rid)}."))
                labels.setdefault(rid, label)
                label_owners.setdefault(label.casefold(), rid)
        if part.scope == "journey" and rid and index > 0:
            previous = document.parts[index - 1]
            if (previous.scope != "journey" or previous.reference_id != rid) and not (
                "journey_id" in _slot_keys(visible[index]) or
                rid in visible[index] or
                (part.identifier and part.identifier in visible[index] and
                 labels.get(rid) == part.identifier and label_owners.get(part.identifier.casefold()) == rid)
            ):
                findings.append(_failure("resumed_identity", "journey", rid, index,
                    "The resumed journey needs a visible identifier.",
                    f"Journey ID: {_safe(rid)}."))
        available = prepare_slot_keys(view, part.scope, rid, components, alternatives)
        if ("```" in part.markdown or "~~~" in part.markdown or "`" in part.markdown or
                "<" in part.markdown or IMAGE_RE.search(part.markdown) or
                LINK_RE.search(part.markdown)):
            findings.append(_failure("unsupported_format", part.scope, rid, index,
                "Some authored formatting was rendered as safe literal text.",
                "Review this section's wording and factual details."))
        for _, _, key in _slot_tokens(part.markdown):
            if key is None:
                findings.append(_failure("malformed_fact_slot", part.scope, rid, index,
                                         "A factual reference is malformed.", "Details unavailable."))
        for key in sorted(_slot_keys(part.markdown) - available):
            findings.append(_failure("unavailable_fact", part.scope, rid, index,
                                     f"The factual slot {key} is unavailable in this exact scope.",
                                     "Details unavailable."))
        if (part.scope == "journey" and rid in alternatives and
                rid not in selection.journey_ids and rid not in selection.excluded_journey_ids):
            findings.append(_failure("unmanifested_journey", "journey", rid, index,
                                     "Journey appears without a matching selection reference.",
                                     f"Upstream status: {alternatives[rid].status}."))
        for claim in part.claims:
            if claim.text not in visible[index]:
                findings.append(_failure("claim_not_visible", part.scope, rid, index,
                    f"Declared assertion ‘{claim.text}’ is not visible in its authored part.",
                    "This assertion cannot be verified as displayed.", claim.claim_id))
            if claim.kind == "comparison":
                scope_valid = (part.scope == "journey" and rid in claim.scope_ids and
                               claim.scope_ids == view.comparison_pool_ids)
            elif claim.kind != "other":
                scope_valid = (part.scope != "shared" and rid is not None and
                               claim.scope_ids == (rid,))
            else:
                scope_valid = (claim.scope_ids == (rid,) if part.scope == "journey" else
                               claim.scope_ids == ())
            if not scope_valid:
                findings.append(_failure("claim_scope_mismatch", part.scope, rid, index,
                    "Declared assertion does not have the exact supported scope.",
                    "This assertion cannot be verified for the stated scope.", claim.claim_id))
                continue
            findings.append(_claim_check(claim, part, index, view))
    # Disclosures may be spread across repeated or interleaved parts of one journey.
    for rid, alt in alternatives.items():
        scoped = [(index, part) for index, part in enumerate(document.parts)
                  if part.scope == "journey" and part.reference_id == rid]
        if not scoped:
            continue
        used = {key for index, _ in scoped for key in _slot_keys(visible[index])}
        if alt.status == "rejected" and not {"status", "requirements"} <= used:
            reasons = next(record.reasons for record in view.reason_sets
                           if record.reason_set_id == alt.reason_set_id)
            fact = "Excluded by upstream checks: " + "; ".join(
                reason.detail for reason in reasons if reason.state == "failed")
            findings.append(_failure("rejected_visible", "journey", rid, scoped[0][0],
                                     "Rejected candidate must be visibly excluded.", fact))
        required = {"status", "styles", "route", "departure", "arrival", "elapsed",
                    "award_program", "award_route", "award_departure", "award_arrival",
                    "award_carrier", "award_cabin", "award_leg_cabins",
                    "points", "fees", "award_price_scope", "price_completeness",
                    "booking_obligation", "requirements", "award_observed_at"}
        if rid not in labels or any(part.identifier != labels[rid] or labels[rid] not in visible[index]
                                    for index, part in scoped):
            required.add("journey_id")
        if alt.cash_observation_id:
            required |= {"transfer", "cash", "cash_cabin", "cash_leg_cabins",
                         "cash_route", "cash_departure", "cash_arrival",
                         "cash_price_scope", "cash_observed_at"}
        award = components[alt.award_observation_id]
        if award.mixed_cabin_pct.state == "value":
            required.add("award_mixed_cabin_pct")
        cash = components.get(alt.cash_observation_id or "")
        if cash and cash.mixed_cabin_pct.state == "value":
            required.add("cash_mixed_cabin_pct")
        for key in sorted(required - used):
            fact = _journey_slots(view, alt, components)[key]
            findings.append(_failure(f"missing_disclosure:{key}", "journey", rid, scoped[0][0],
                                     f"Required {key.replace('_', ' ')} was omitted.",
                                     f"{key.replace('_', ' ').capitalize()}: {fact}."))
    for scope in ("benchmark", "incomplete"):
        for rid in {part.reference_id for part in document.parts
                    if part.scope == scope and _valid_part_reference(part, view)}:
            if rid not in components:
                continue
            scoped = [(index, part) for index, part in enumerate(document.parts)
                      if part.scope == scope and part.reference_id == rid and
                      _valid_part_reference(part, view)]
            used = {key for index, _ in scoped for key in _slot_keys(visible[index])}
            required = {"observation_id", "disposition", "route", "departure", "arrival",
                        "observed_at", "provider_updated_at"}
            if scope == "benchmark":
                required |= {"cash", "price_scope", "carrier", "cabin", "leg_cabins"}
            if components[rid].mixed_cabin_pct.state == "value":
                required.add("mixed_cabin_pct")
            for key in sorted(required - used):
                fact = _component_slots(components[rid], scope)[key]
                findings.append(_failure(f"missing_disclosure:{key}", scope, rid, scoped[0][0],
                                         f"Required {key.replace('_', ' ')} was omitted.",
                                         f"{key.replace('_', ' ').capitalize()}: {fact}."))
    if view.coverage_groups and not any(part.scope == "shared" and
                                       _valid_part_reference(part, view) and
                                       "coverage" in _slot_keys(visible[index])
                                       for index, part in enumerate(document.parts)):
        summary = _shared_slots(view)["coverage"]
        findings.append(_failure("missing_disclosure:coverage", "shared", None, None,
                                 "Search coverage was omitted.", f"Search coverage: {summary}."))
    shared_keys = {key for index, part in enumerate(document.parts)
                   if part.scope == "shared" and _valid_part_reference(part, view)
                   for key in _slot_keys(visible[index])}
    if not view.comparison_pool_ids and "complete_journey_count" not in shared_keys:
        findings.append(_failure("missing_disclosure:no_complete_journeys", "shared", None,
                                 None, "No complete journey finding was omitted.",
                                 "No complete admitted or conditional journeys are available."))
    if view.provider_status != "complete" and "provider_status" not in shared_keys:
        findings.append(_failure("missing_disclosure:provider_status", "shared", None,
                                 None, "Provider completion status was omitted.",
                                 f"Provider status: {_safe(view.provider_status)}."))
    if "benchmark_status" not in shared_keys and not selection.benchmark_observation_id:
        findings.append(_failure("missing_disclosure:benchmark_status", "shared", None,
                                 None, "Direct cash benchmark status was omitted.",
                                 f"Direct cash benchmark: {_safe('available' if view.direct_cash_observation_ids else 'unavailable')}."))
    return tuple(findings)


def _notice(finding: CheckFinding) -> ValidationNotice:
    # Missing-disclosure facts come from already escaped source slots. Other details
    # include raw source reasons or model wording and need escaping exactly once.
    supplied = finding.supplied_fact or "Please verify this detail before acting."
    detail = supplied if finding.code.startswith("missing_disclosure:") else _safe(supplied)
    if finding.code.startswith("missing_disclosure:"):
        body = detail
    elif finding.code == "unavailable_reference":
        body = "Details unavailable. This reference could not be resolved."
    else:
        body = f"{_safe(finding.message)} {detail}"
    return ValidationNotice(code=finding.code, scope=finding.scope,
                            reference_id=finding.reference_id, part_index=finding.part_index,
                            claim_id=finding.claim_id, text=f"Validation: {body}")


def _safe_authored_markdown(markdown: str, fence: str | None,
                           ) -> tuple[str, str | None]:
    """Keep prose, lists and tables; render unsupported markup as safe literal text."""
    lines: list[str] = []
    for line in markdown.splitlines(keepends=True):
        stripped = line.lstrip()
        marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else None
        if marker:
            if fence == marker:
                fence = None
            elif fence is None:
                fence = marker
            lines.append("\n" if line.endswith("\n") else "")
            continue
        if fence:
            # An unsupported code block becomes literal text. Its fact-looking
            # tokens are unavailable, never a second source of bound facts.
            chunks: list[str] = []
            cursor = 0
            for start, end, _ in _slot_tokens(line):
                chunks.extend((line[cursor:start], "Details unavailable"))
                cursor = end
            chunks.append(line[cursor:])
            literal = "".join(chunks)
            trailing_newline = "\n" if literal.endswith("\n") else ""
            lines.append(_safe(literal.rstrip("\n")) + trailing_newline)
            continue
        line = IMAGE_RE.sub("", line)
        line = LINK_RE.sub(r"\1", line)
        line = re.sub(r"[<>]", lambda match: "&lt;" if match.group() == "<" else "&gt;", line)
        line = line.replace("`", "\\`")
        lines.append(line)
    return "".join(lines), fence


def _unescaped_pipe(base: str, position: int) -> bool:
    if base[position] != "|":
        return False
    backslashes = 0
    cursor = position - 1
    while cursor >= 0 and base[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 0


def _insert_local_notices(base: str, starts: list[int], ends: list[int],
                          parts: tuple[ResultsPart, ...],
                          targets: dict[int, list[ValidationNotice]]) -> str:
    insertions: dict[int, list[str]] = {}
    visible = _visible_parts(parts)
    for index, notices in targets.items():
        start, end = starts[index], ends[index]
        anchor = end - 1
        while anchor >= start and (base[anchor].isspace() or _unescaped_pipe(base, anchor)):
            anchor -= 1
        if anchor < start:
            anchor = end - 1 if end > start else start
        line_start = base.rfind("\n", 0, anchor + 1) + 1
        line_end = base.find("\n", anchor)
        if line_end < 0:
            line_end = len(base)
        line = base[line_start:line_end]
        identifier = parts[index].identifier
        label = identifier if identifier is not None and identifier in visible[index] else None
        text = " ".join(
            notice.text.replace("Validation:",
                f"Validation: ({_safe(label or notice.reference_id)})", 1)
            if notice.scope != "shared" and (label or notice.reference_id) else notice.text
            for notice in notices
        )
        is_separator = bool(re.fullmatch(r"[\s|:\-]+", line))
        if line.lstrip().startswith("|") and not is_separator and anchor >= start:
            closing = next((position for position in range(anchor + 1, line_end)
                            if _unescaped_pipe(base, position)), None)
            if closing is not None:
                insertions.setdefault(closing, []).append(" " + text + " ")
                continue
        if line.lstrip().startswith("|"):
            table_end = line_end
            while table_end < len(base):
                next_end = base.find("\n", table_end + 1)
                if next_end < 0:
                    next_end = len(base)
                next_line = base[table_end + 1:next_end]
                if not next_line.lstrip().startswith("|"):
                    break
                table_end = next_end
            insertions.setdefault(table_end, []).append("\n\n" + text + "\n\n")
        else:
            insertions.setdefault(line_end, []).append("\n\n" + text + "\n\n")
    for position in sorted(insertions, reverse=True):
        base = base[:position] + " ".join(insertions[position]) + base[position:]
    return base


def render_results(document: ResultsDocument, projection: SolutionProjection,
                   notices: tuple[ValidationNotice, ...] = (),
                   ) -> tuple[str, tuple[RenderedFact, ...]]:
    slots = prepare_results(projection, ResultsConfig(model="replay", max_output_tokens=1,
        timeout_seconds=1, context_limit_tokens=1, prompt_overhead_tokens=0)).slots
    output: list[str] = []
    facts: list[RenderedFact] = []
    starts: list[int] = []
    ends: list[int] = []
    running_length = 0
    fence: str | None = None
    notice_targets: dict[int, list[ValidationNotice]] = {}
    end_notices: list[ValidationNotice] = []
    for notice in notices:
        if notice.part_index is not None and notice.part_index < len(document.parts):
            notice_targets.setdefault(notice.part_index, []).append(notice)
            continue
        matching = next((index for index, part in enumerate(document.parts)
                         if part.scope == notice.scope and part.reference_id == notice.reference_id), None)
        if matching is None:
            end_notices.append(notice)
        else:
            notice_targets.setdefault(matching, []).append(notice)
    for index, part in enumerate(document.parts):
        scope_key = f"{part.scope}:{part.reference_id}" if part.scope != "shared" else "shared"
        local_slots = slots.get(scope_key) if _valid_part_reference(part, projection.view) else None
        authored, fence = _safe_authored_markdown(part.markdown, fence)
        chunks: list[str] = []
        cursor = 0
        for start, end, key in _slot_tokens(authored):
            chunks.append(authored[cursor:start])
            if key is None or local_slots is None or key not in local_slots:
                chunks.append("Details unavailable")
            else:
                value = local_slots[key]
                facts.append(RenderedFact(part_index=index, scope=part.scope,
                                          reference_id=part.reference_id, key=key, value=value))
                chunks.append(value)
            cursor = end
        chunks.append(authored[cursor:])
        rendered = "".join(chunks)
        starts.append(running_length)
        output.append(rendered)
        running_length += len(rendered)
        ends.append(running_length)
    shared = [notice.text for notice in end_notices]
    rendered_all = _insert_local_notices("".join(output), starts, ends,
                                          document.parts, notice_targets)
    if shared:
        rendered_all += "\n\n" + "\n\n".join(shared)
    return rendered_all, tuple(facts)


def replay_results(artifact: ResultsArtifact) -> str:
    trusted = SolutionProjection.model_validate(artifact.projection.model_dump(mode="json"))
    expected_prepared = prepare_results(trusted, artifact.config)
    if artifact.prepared != expected_prepared:
        raise ValueError("saved Results preparation differs from trusted source")
    if len(artifact.attempts) > 2 or tuple(a.phase for a in artifact.attempts) != (
        ("initial", "correction") if len(artifact.attempts) == 2 else
        ("initial",) if artifact.attempts else ()
    ):
        raise ValueError("saved Results attempt sequence is invalid")
    feedback: tuple[CheckFinding, ...] = ()
    previous: ResultsDocument | None = None
    for index, saved in enumerate(artifact.attempts):
        size, total, prompt_digest, schema_digest = _measurement(
            artifact.prepared, artifact.config, feedback, previous)
        if (saved.input_bytes, saved.estimated_total_tokens, saved.prompt_digest,
                saved.schema_digest) != (size, total, prompt_digest, schema_digest):
            raise ValueError("saved Results attempt measurement differs from prompt")
        if saved.writer_called:
            if total > artifact.config.context_limit_tokens:
                raise ValueError("saved Results attempt exceeds context limit")
        elif not (index == 1 and saved.outcome == "generation_error" and
                  saved.error == "context_limit" and total > artifact.config.context_limit_tokens
                  and saved.document is None):
            raise ValueError("saved Results noninvocation receipt is inconsistent")
        if index == 1 and (previous is None or not feedback):
            raise ValueError("saved Results correction has no failed initial draft")
        if saved.outcome == "recoverable":
            if saved.document is None or not saved.writer_called or saved.error is not None:
                raise ValueError("saved Results recoverable receipt is inconsistent")
            feedback = tuple(f for f in saved.findings if f.outcome == "failed")
            previous = saved.document
        elif saved.document is not None:
            raise ValueError("saved Results failed attempt contains a document")
        if saved.outcome == "api_error" and saved.failure_subtype != "api_error":
            raise ValueError("saved Results API failure subtype is inconsistent")
        if saved.outcome == "generation_error" and saved.writer_called and saved.failure_subtype not in {
            "refusal", "incomplete", "schema_error"
        }:
            raise ValueError("saved Results generation failure subtype is inconsistent")
    if (len(artifact.attempts) == 1 and artifact.attempts[0].outcome == "recoverable" and
            any(f.outcome == "failed" for f in artifact.attempts[0].findings)):
        raise ValueError("saved Results correction attempt is missing")
    for saved in artifact.attempts:
        if saved.document is not None and saved.findings != check_document(saved.document, trusted):
            raise ValueError("saved Results check receipt differs from source")
    if artifact.selected_attempt is None:
        if any(saved.outcome == "recoverable" for saved in artifact.attempts):
            raise ValueError("saved Results recoverable draft was not selected")
        if artifact.attempts:
            terminal = artifact.attempts[-1]
            expected_outcome = "api_error" if terminal.outcome == "api_error" else "generation_error"
            if (artifact.selection_reason != "no_recoverable_draft" or
                    artifact.generation_outcome != expected_outcome):
                raise ValueError("saved Results generation outcome is inconsistent")
        elif (artifact.selection_reason != "context_limit" or
              artifact.generation_outcome != "context_limit" or
              artifact.prepared.estimated_total_tokens <= artifact.config.context_limit_tokens):
            raise ValueError("saved Results context-limit outcome is inconsistent")
        if artifact.delivery_outcome != "not_delivered" or artifact.validation_outcome != "unavailable":
            raise ValueError("saved Results undelivered outcome is inconsistent")
        if artifact.rendered_markdown or artifact.rendered_digest is not None:
            raise ValueError("undelivered artifact has rendered content")
        return ""
    if artifact.selected_attempt >= len(artifact.attempts):
        raise ValueError("saved Results selected attempt index is invalid")
    attempt = artifact.attempts[artifact.selected_attempt]
    if attempt.document is None:
        raise ValueError("selected attempt has no document")
    recoverable = [(index, saved) for index, saved in enumerate(artifact.attempts)
                   if saved.outcome == "recoverable" and saved.document is not None]
    expected_index = min(recoverable, key=lambda pair: (
        sum(f.outcome == "failed" for f in pair[1].findings), -pair[0]))[0]
    if artifact.selected_attempt != expected_index:
        raise ValueError("saved Results draft selection differs from checks")
    expected_reason = "initial_only" if len(recoverable) == 1 else (
        "correction_fewer_failures" if expected_index == 1 and
        sum(f.outcome == "failed" for f in recoverable[1][1].findings) <
        sum(f.outcome == "failed" for f in recoverable[0][1].findings)
        else "correction_tie" if expected_index == 1 else "initial_fewer_failures")
    if artifact.selection_reason != expected_reason:
        raise ValueError("saved Results selection reason differs from checks")
    expected_notices = tuple(_notice(finding) for finding in attempt.findings
                             if finding.outcome == "failed")
    if artifact.notices != expected_notices:
        raise ValueError("saved Results notices differ from checks")
    if (artifact.generation_outcome != "success" or artifact.delivery_outcome != "delivered" or
            artifact.validation_outcome != ("annotated" if expected_notices else "clean")):
        raise ValueError("saved Results delivered outcome is inconsistent")
    rendered, facts = render_results(attempt.document, artifact.projection, artifact.notices)
    if rendered != artifact.rendered_markdown or facts != artifact.inserted_facts or \
            content_digest(rendered) != artifact.rendered_digest:
        raise ValueError("saved Results artifact does not replay exactly")
    return rendered


def _receipt(writer: ResultsWriter) -> WriterReceipt | None:
    take = getattr(writer, "take_receipt", None)
    result = take() if callable(take) else None
    if result is None:
        return None
    return WriterReceipt.model_validate(result)


def run_results(projection: SolutionProjection, config: ResultsConfig,
                writer: ResultsWriter) -> ResultsArtifact:
    prepared = prepare_results(projection, config)
    attempts: list[ResultsAttempt] = []
    feedback: tuple[CheckFinding, ...] = ()
    previous: ResultsDocument | None = None
    for phase in cast("tuple[Literal['initial', 'correction'], ...]", ("initial", "correction")):
        size, total, prompt_digest, schema_digest = _measurement(prepared, config,
                                                                  feedback, previous)
        if total > config.context_limit_tokens:
            if not attempts:
                return ResultsArtifact(projection=projection, config=config, prepared=prepared,
                    attempts=(), selected_attempt=None, selection_reason="context_limit",
                    generation_outcome="context_limit", validation_outcome="unavailable",
                    delivery_outcome="not_delivered")
            attempts.append(ResultsAttempt(phase="correction", outcome="generation_error",
                error="context_limit", input_bytes=size, estimated_total_tokens=total,
                prompt_digest=prompt_digest, schema_digest=schema_digest,
                writer_called=False))
            break
        try:
            document = writer.author(prepared, config, feedback=feedback,
                                     previous_document=previous)
            if not isinstance(document, ResultsDocument):
                document = ResultsDocument.model_validate(document)
            findings = check_document(document, projection)
            attempts.append(ResultsAttempt(phase=phase, outcome="recoverable",
                document=document, findings=findings, writer_receipt=_receipt(writer),
                input_bytes=size, estimated_total_tokens=total,
                prompt_digest=prompt_digest, schema_digest=schema_digest))
            failed = tuple(item for item in findings if item.outcome == "failed")
            if phase == "initial" and failed:
                feedback = failed
                previous = document
                continue
            break
        except ResultsWriterError as exc:
            outcome: Literal["api_error", "generation_error"] = "api_error" if exc.outcome == "api_error" else "generation_error"
            receipt = _receipt(writer) or WriterReceipt(raw_response=exc.raw_response)
            attempts.append(ResultsAttempt(phase=phase, outcome=outcome,
                error=str(exc), failure_subtype=exc.outcome, writer_receipt=receipt,
                input_bytes=size, estimated_total_tokens=total,
                prompt_digest=prompt_digest, schema_digest=schema_digest))
            break
        except (ValueError, TypeError) as exc:
            attempts.append(ResultsAttempt(phase=phase, outcome="generation_error",
                error=f"schema_error: {exc}", failure_subtype="schema_error",
                writer_receipt=_receipt(writer), input_bytes=size,
                estimated_total_tokens=total, prompt_digest=prompt_digest,
                schema_digest=schema_digest))
            break
    recoverable = [(index, attempt) for index, attempt in enumerate(attempts)
                   if attempt.outcome == "recoverable" and attempt.document is not None]
    if not recoverable:
        terminal = attempts[-1] if attempts else None
        generation: Literal["api_error", "generation_error"] = (
            "api_error" if terminal and terminal.outcome == "api_error" else "generation_error")
        return ResultsArtifact(projection=projection, config=config, prepared=prepared,
            attempts=tuple(attempts), selected_attempt=None, selection_reason="no_recoverable_draft",
            generation_outcome=generation, validation_outcome="unavailable",
            delivery_outcome="not_delivered")
    selected, attempt = min(recoverable, key=lambda pair: (
        sum(f.outcome == "failed" for f in pair[1].findings), -pair[0]))
    reason = "initial_only" if len(recoverable) == 1 else (
        "correction_fewer_failures" if selected == 1 and
        sum(f.outcome == "failed" for f in recoverable[1][1].findings) <
        sum(f.outcome == "failed" for f in recoverable[0][1].findings)
        else "correction_tie" if selected == 1 else "initial_fewer_failures")
    notices = tuple(_notice(finding) for finding in attempt.findings if finding.outcome == "failed")
    assert attempt.document is not None
    rendered, facts = render_results(attempt.document, projection, notices)
    artifact = ResultsArtifact(projection=projection, config=config, prepared=prepared,
        attempts=tuple(attempts), selected_attempt=selected, selection_reason=reason,
        generation_outcome="success", validation_outcome="annotated" if notices else "clean",
        delivery_outcome="delivered", notices=notices, inserted_facts=facts,
        rendered_markdown=rendered, rendered_digest=content_digest(rendered))
    replay_results(artifact)
    return artifact
