"""V14 exact selector identities with an unverified editorial purpose note."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, cast

from award_agent.ranking.projection_contracts import SolutionProjection

from .focused_packet import decode_selection_v2, selection_instructions_v8, selection_schema_v2
from .interactive_contracts import InteractivePreparedInput
from .structured_contracts import StructuredPreparedInput, StructuredSelection


def schema(prepared: StructuredPreparedInput, source: SolutionProjection, *,
           max_references: int = 8) -> dict[str, object]:
    shape = deepcopy(selection_schema_v2(prepared, source, max_references=max_references))
    items = cast(dict[str, Any], shape["properties"])["choices"]["items"]
    branches = items.get("anyOf", [items])
    for branch in branches:
        properties = branch["properties"]
        properties["purpose"] = {"type": "string"}
        properties["compare_to"] = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        branch["required"] = ["k", "r", "purpose", "compare_to"]
    return shape


def instructions(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    basis = selection_instructions_v8(prepared, source).replace(
        "Return only JSON choices, no prose or copied source facts.",
        "Return only JSON choices with short editorial purpose text, no traveler answer prose or copied source facts.")
    return basis + (
        " For each selected choice, also return purpose: one short editorial "
        "hypothesis about why this exact choice helps the traveler decide, and "
        "compare_to: another selected exact alias or null. The output choice "
        "is {k:'j'|'b'|'l',r:exact alias,purpose:short text,compare_to:exact "
        "selected other alias or null}. Choose a comparison target when it "
        "helps reveal a concrete supported gain and real loss; otherwise null. "
        "Describe an intended traveler decision in purpose, not a new source "
        "value, repeated number or invented traveler preference. "
        "Do not choose near-identical siblings merely to fill the pool. If a "
        "same-program, same-cabin cousin looks worse on schedule and price, "
        "select it only for a source-supported offsetting traveler benefit. "
        "These purposes are unverified writing suggestions, not source facts "
        "or final recommendations. The composer must recheck every claim "
        "against each selected record and may reject a suggested purpose."
    )


def instructions_v15(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    """Clarify partial-lead comparison only when no complete journey is eligible."""
    base = instructions(prepared, source)
    if any(item.status in {"admitted", "conditional"} for item in source.view.alternatives):
        return base
    return base + (
        " With no complete journey, look for a supported lead-to-lead difference "
        "that changes the next check: reported program, date, seat evidence or "
        "same-program quote with comparable currency and scope. In each useful "
        "purpose, name the lead's potential upside and its real tradeoff against "
        "another selected lead. A shared missing schedule is not a benefit. "
        "Keep direct cash as a separate baseline, not a substitute for a useful "
        "lead comparison. There is no lead count or cabin quota; one lead is "
        "enough when no other source-supported contrast helps the traveler. "
        "These purposes remain unverified hypotheses for the composer to check."
    )


def instructions_v16(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    return instructions_v15(prepared, source) + (
        " In this selector packet, journey_records are keyed by exact J alias. "
        "Each record names its JP profile, exact award/cash component refs, "
        "and repeats that journey's reported award cabin, program and points. "
        "Component_records use exact A/C aliases and CP profiles. Read a "
        "record's named profile for its other facts. JP and CP are data "
        "profiles, never selectable source aliases. The inline fields retain "
        "their source scope and do not establish leg cabins or total cost."
    )


def instructions_v20(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    """Favor a useful next check for incomplete sources without option quotas."""
    base = instructions_v16(prepared, source)
    if any(item.status in {"admitted", "conditional"} for item in source.view.alternatives):
        return base
    return base + (
        " For incomplete leads, favor differences that could change which lead "
        "the traveler checks first, such as a reported date, program, or truly "
        "comparable original quote. There is no program, date, or count quota. "
        "A surplus reported seat count above the requested party is not by "
        "itself a traveler benefit. Do not compare points across programs as "
        "economic value, or prices across currencies or unknown scopes as "
        "total savings. Keep purpose text an unverified selector hypothesis."
    )


def instructions_v21(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    """Keep V20 selection policy while narrowing the authoring reference ceiling."""
    basis = instructions_v20(prepared, source)
    old = "strict maximum of eight references TOTAL"
    if old not in basis:
        raise ValueError("V21 selector lost its inherited reference ceiling")
    return basis.replace(old, "strict maximum of four references TOTAL")


def instructions_v22(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    """Describe only the relocated lead facts in the incomplete selector view."""
    basis = instructions_v21(prepared, source)
    old = ("The exact_details index supplies source-bound journey_components, "
           "per-journey separate-booking waits, factored award-itinerary "
           "connections, and component original-currency quotes in major units.")
    new = ("The exact_details index supplies source-bound journey_components, "
           "per-journey separate-booking waits, factored award-itinerary "
           "connections, and nonlead component original-currency quotes in major units. "
           "Lead original-currency quotes are in each lead_records entry's original_quote object.")
    if old not in basis:
        raise ValueError("V24 selector lost its inherited quote location")
    return basis.replace(old, new) + (
        " In this incomplete-only selector view, lead_records replaces lead_rows. "
        "Each ordered lead record names the former lead_row fields. "
        "Other component quotes remain in exact_details.component_quotes."
    )


def _three_reference_guidance(basis: str) -> str:
    old = "strict maximum of four references TOTAL"
    if old not in basis:
        raise ValueError("V28 selector lost its inherited reference ceiling")
    return basis.replace(old, "strict maximum of three references TOTAL") + (
        " Choose at most two nonbenchmark journey or lead references combined, "
        "and at most one direct cash benchmark. These are ceilings, not counts "
        "to fill; never truncate or substitute a selected reference."
    )


def instructions_v26(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    return _three_reference_guidance(instructions_v21(prepared, source))


def instructions_v27(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    return _three_reference_guidance(instructions_v22(prepared, source))


def instructions_v29(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    """Point to grouped named leads without changing the selector's decision policy."""
    basis = instructions_v27(prepared, source)
    old_quote = "Lead original-currency quotes are in each lead_records entry's original_quote object."
    new_quote = ("Lead original-currency quotes are in each "
                 "lead_program_groups member's record.original_quote object.")
    old_location = ("In this incomplete-only selector view, lead_records replaces lead_rows. "
                    "Each ordered lead record names the former lead_row fields.")
    new_location = ("In this incomplete-only selector view, lead_program_groups replaces "
                    "lead_rows. Each group is keyed by its exact reported program; its members "
                    "wrap unchanged lead records and source_ordinal gives each original row "
                    "position. The groups preserve every original lead, not a ranking. "
                    "Each member's record names the former lead_row fields.")
    if old_quote not in basis or old_location not in basis:
        raise ValueError("V29 selector lost its inherited lead location guidance")
    return basis.replace(old_quote, new_quote).replace(old_location, new_location)


def instructions_v30(prepared: StructuredPreparedInput, source: SolutionProjection) -> str:
    """Clarify cross-program units while preserving the V29 selection ownership."""
    basis = instructions_v29(prepared, source)
    old = ("Do not compare points across programs as economic value, or prices across "
           "currencies or unknown scopes as total savings.")
    new = ("Each rewards program has its own points unit. A smaller number in another "
           "program is not a supported advantage, even when called stated, nominal, "
           "or potential, and cannot supply the upside of a points-versus-fees "
           "tradeoff. Original program quotes remain reportable separately. Before "
           "retaining a comparator, remove cross-program numerical magnitude from the "
           "rationale and identify the source-supported benefit for which a traveler "
           "might accept its downside. An unspecified program preference alone does "
           "not establish that benefit. If no benefit remains, examine other leads in "
           "the full inventory. A supported conditional choice can suffice; no "
           "program, date, cabin, or count quota applies. Do not compare prices across "
           "currencies or unknown scopes as total savings.")
    if old not in basis:
        raise ValueError("V30 selector lost its inherited cross-program policy")
    return basis.replace(old, new)


def _choices(raw: str | dict[str, Any], *, max_references: int = 8,
             max_nonbenchmark_references: int | None = None
             ) -> list[dict[str, Any]]:
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict) or set(value) != {"choices"} or not isinstance(value["choices"], list):
        raise ValueError("planned selection requires exactly a choices array")
    if max_references < 8 and len(value["choices"]) > max_references:
        raise ValueError(f"planned selection exceeds the {max_references}-reference bundle")
    if max_nonbenchmark_references is not None and sum(
            isinstance(choice, dict) and choice.get("k") in ("j", "l")
            for choice in value["choices"]) > max_nonbenchmark_references:
        raise ValueError("planned selection exceeds the nonbenchmark reference ceiling")
    result = []
    for index, choice in enumerate(value["choices"]):
        if not isinstance(choice, dict) or set(choice) != {"k", "r", "purpose", "compare_to"}:
            raise ValueError(f"planned choice {index} has invalid fields")
        purpose, target = choice["purpose"], choice["compare_to"]
        if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 400:
            raise ValueError(f"planned choice {index} needs a short nonempty purpose")
        if target is not None and not isinstance(target, str):
            raise ValueError(f"planned choice {index} comparison target is invalid")
        result.append(choice)
    refs = [choice["r"] for choice in result]
    for index, choice in enumerate(result):
        target = choice["compare_to"]
        if target is not None and (target == choice["r"] or target not in refs):
            raise ValueError(f"planned choice {index} target must be another selected ref")
    return result


def decode(raw: str | dict[str, Any], prepared: StructuredPreparedInput,
           source: SolutionProjection, *, max_references: int = 8,
           max_nonbenchmark_references: int | None = None) -> StructuredSelection:
    choices = _choices(raw, max_references=max_references,
                       max_nonbenchmark_references=max_nonbenchmark_references)
    core = {"choices": [{"k": row["k"], "r": row["r"]} for row in choices]}
    return decode_selection_v2(core, prepared, source, max_references=max_references)


def editorial_plan(raw: str, selector: InteractivePreparedInput,
                   focus: InteractivePreparedInput,
                   selection: StructuredSelection,
                   source: SolutionProjection) -> list[dict[str, object]]:
    """Map selector notes to selected composer refs without promoting them to facts."""
    marker = selector.packet.get("selection_format")
    max_references = 3 if marker in {"roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"} else (
        4 if marker in {"roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"} else 8)
    max_nonbenchmark_references = 2 if marker in {"roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"} else None
    if decode(raw, selector.structured, source, max_references=max_references,
              max_nonbenchmark_references=max_nonbenchmark_references) != selection:
        raise ValueError("editorial plan identities differ from validated selection")
    reverse = {short: long for long, short in cast(dict[str, str],
               focus.packet["wire_aliases"]).items()}
    if len(reverse) != len(cast(dict[str, str], focus.packet["wire_aliases"])):
        raise ValueError("editorial plan has ambiguous exact source aliases")
    plan = []
    for choice in _choices(raw, max_references=max_references,
                           max_nonbenchmark_references=max_nonbenchmark_references):
        ref = choice["r"]
        target = choice["compare_to"]
        if ref not in reverse or (target is not None and target not in reverse):
            raise ValueError("editorial plan aliases are outside selected authoring records")
        plan.append({"role": {"j": "journey", "b": "benchmark", "l": "lead"}[choice["k"]],
                     "ref": reverse[ref],
                     "purpose": choice["purpose"].strip(),
                     "compare_to": reverse[target] if target is not None else None,
                     "status": "unverified_editorial_suggestion"})
    return plan
