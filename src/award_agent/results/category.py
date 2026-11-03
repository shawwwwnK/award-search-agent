"""Isolated category-led Results experiment with exact offline replay."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from copy import deepcopy
from functools import partial
from typing import Any, Literal, cast

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection

from .category_contracts import CategoryAnswer, CategoryArtifact, CategoryBlock
from .comparison_registry import build_temporal_registry
from .contracts import CheckFinding, ResultsConfig, ResultsInputMeasurer
from .currency import FxAcquisition
from .focused import (
    _pass,
    _prepared,
    _replay_pass,
    prepare_focused_composer,
    prepare_focused_selector,
)
from .focused_packet import decode_selection_v2, selection_schema_v2
from .focused_records import writer_packet
from .focused_selector_records import selector_packet
from .focused_traveler_evidence import build_traveler_evidence
from .focused_v4 import _findings
from .focused_wire import decode as decode_document
from .focused_wire import schema as document_schema
from .interactive_contracts import InteractivePreparedInput, InteractiveSettings, InteractiveWriter
from .presentation import resolve_workspace
from .runner import RequestEnvelope, choose_recoverable
from .structured import resolve_structured_document
from .structured_contracts import StructuredDocument, StructuredSelection
from .workspace_contracts import WorkspaceEvidence

MAX_NONBENCHMARK = 6
MAX_TOTAL = 7
_SETTINGS = InteractiveSettings(reasoning_effort="low", service_tier="fast")
_MEDIUM_SETTINGS = InteractiveSettings(reasoning_effort="medium", service_tier="fast")
_PROFILE_INSTRUCTIONS: dict[str, tuple[str, str]] = {
    "category-c01": (
        "Select a compact set of exact source references for a traveler answer. "  # noqa: ISC004
        "Ranking's time, cost, and premium memberships are authoritative and overlap. "
        "Represent every materially different available category perspective; one "
        "journey may represent several. Do not fill a quota or select near-identical "
        "journeys without a supported traveler benefit. Preserve conditional journeys "
        "and uncertain cost states. If no complete journey exists, choose useful "
        "different research leads without assigning styles. Include one direct cash "
        "benchmark if available. The full explorer remains separate. Return JSON "
        "choices with k=j|b|l and exact r alias, plus omitted category reasons. "
        "A reason is audit-only; do not invent a source fact or traveler preference.",
        "Write one natural traveler answer around Ranking's time, cost, and premium "  # noqa: ISC004
        "perspectives from the selected exact authoring_records. Make the category "
        "labels visible in prose, but choose an organic order. Explain each useful "
        "journey's supported reason to consider it, meaningful downside and local "
        "tradeoff. Show overlapping category strengths once, with one journey card. "
        "A reference block is a SOURCE-RESOLVED CARD: write the short reason in v "
        "and a natural label in n; do not copy flight schedules, routes, seats, "
        "points or taxes into prose just to fill a card. Code renders card facts. "
        "Use k=p or a for journey cards, k=l for research lead cards, and k=t "
        "for connecting prose. The k=b block is a SOURCE-BOUND INLINE CASH "
        "SENTENCE, not a cash itinerary card: its v must contain exactly one brief "
        "sentence with the source's true origin-to-destination quote and material "
        "uncertainty; choose the exact benchmark r. Do not imply the quote covers "
        "other connecting cities. For no complete journey, compare supported "
        "research directions, not invented styles or itineraries. Explain shared "
        "missing evidence once, with choice-specific risks near the affected "
        "choice. Do not claim cheapest overall from incomplete or unknown-scope "
        "amounts, or compare points from different programs as economic value. "
        "Use only exact references in authoring_records. Every concrete option "
        "discussed needs its own visible exact card or cash sentence. Never print "
        "internal J/A/C aliases. Output JSON blocks in reading order."
    ),
}
_PROFILE_INSTRUCTIONS["category-c02"] = (
    _PROFILE_INSTRUCTIONS["category-c01"][0] +
    " In omitted, list ONLY an available Ranking category perspective that the "
    "selected journeys do not represent. Do not list a category with no available "
    "members, and do not list a category already represented by a selected journey. "
    "Return omitted=[] when every available category is represented. Any omitted "
    "reason is an audit note, never an authoring fact. For incomplete leads, inspect "
    "useful same-program, same-cabin alternatives across allowed dates before "
    "choosing. A supported difference in reported miles, taxes or date may "
    "change the next check; do not treat an earlier row as better merely because "
    "it appears first. One reported seat supports a request for one traveler "
    "without proving current availability. Avoid program or cabin quotas and "
    "do not turn raw quotes into a cross-program value ranking.",
    _PROFILE_INSTRUCTIONS["category-c01"][1] +
    " For this version, identify each journey by its OWN exact record. A loyalty "
    "program is not the operating airline. If a record has flight numbers but no "
    "reported operating carrier, name the program and route without guessing the "
    "airline. Never borrow a carrier from another record, route or benchmark. "
    "If the source has NO complete eligible journey, do not create Time, Cost or "
    "Premium recommendation sections: those Ranking categories have no members. "
    "Use natural research-choice language about date, program and what to verify; "
    "never call cross-program points lowest or cheaper. For complete journeys, "
    "describe the category benefit naturally, such as a shorter trip or business "
    "cabin, without mandatory headings or empty sections. State a choice's reason "
    "once, in its card explanation; opening prose should frame the decision without "
    "repeating card copy. Put shared missing-cost and availability limitations once "
    "after the choices, with local unique conditions beside their own choice. "
    "Canonical availability guidance is displayed separately, so do not restate "
    "generic current-availability advice. Flight itinerary details belong to "
    "source-resolved cards, not dense copied prose. A missing full trip price does "
    "not erase a supported same-program comparison of quoted miles and cabin. "
    "Use that difference when it genuinely helps the choice, while preserving "
    "each quote's unknown scope and avoiding a total-cost or per-person claim. "
    "Do not manufacture a numerical comparison or tradeoff where none helps.",
)
_PROFILE_INSTRUCTIONS["category-c03"] = (
    _PROFILE_INSTRUCTIONS["category-c02"][0],
    "Write a concise, natural answer for a traveler using only the selected exact "  # noqa: ISC004
    "authoring_records. The cards display source flight facts; use prose to explain "
    "why a choice is worth considering and its meaningful downside, without reciting "
    "the card's route, schedule, points, taxes or seat count. Each concrete option "
    "needs one source-resolved reference block: k=p or a for a complete journey, "
    "k=l for an incomplete research lead. Put its short decision reason in v and "
    "a traveler-friendly label in n. Use k=t only for useful connecting prose. "
    "When complete journeys exist, follow Ranking's overlapping time, cost and "
    "premium memberships, but describe their actual traveler benefit naturally, "
    "such as a shorter trip or a business cabin. One card can serve more than one "
    "perspective. Do not announce an unavailable or unselected category, use "
    "Time/Cost/Premium as section or card titles, or force a three-part layout. "
    "Explain a supported local tradeoff only where it helps the decision. "
    "When there is no complete eligible journey, say so once and discuss leads "
    "as research directions, never Ranking-style recommendations. Give each lead "
    "a distinct conditional next-check reason when supported by program access, "
    "cabin, date or a same-program quote difference. A source quote or date alone "
    "is a card fact, not a reason. Do not assume the traveler owns program points "
    "or prefers a cabin or date, and do not force a quota or a lowest-points rule. "
    "A missing full trip price still allows a useful same-program comparison of "
    "reported miles or cabin, qualified by the source quote's scope. Do not "
    "compare points across programs as economic value or claim cheapest overall "
    "from unknown-scope amounts. State shared gaps once after the choices; place "
    "only a unique material condition beside its affected choice. Do not repeat "
    "generic availability advice; the display adds it separately. Keep any opening "
    "sentence to a decision frame, not a summary of every card reason. "
    "The k=b block is one SOURCE-BOUND INLINE CASH SENTENCE, never a cash card: "
    "use its exact benchmark r and one brief sentence containing the true "
    "origin-to-destination cash quote and material uncertainty. Do not extend "
    "that quote to a connecting city. Name each source accurately: a loyalty "
    "program is not an operating airline, and a carrier missing from the record "
    "must not be guessed or borrowed from another record. Never print internal "
    "J/A/C aliases. Output JSON blocks in reading order.",
)
_PROFILE_INSTRUCTIONS["category-c04"] = (
    _PROFILE_INSTRUCTIONS["category-c03"][0],
    _PROFILE_INSTRUCTIONS["category-c03"][1] +
    " Put the cash comparison only in its k=b sentence; do not copy that sentence "
    "into k=t prose or a card reason. Make any opening comparison agree with the "
    "exact benefits of the selected journeys: if one journey offers both earlier "
    "arrival and a premium cabin, do not present them as opposing choices. Omit "
    "an opening comparison if the source does not support one. Explain a different "
    "supported benefit, such as a longer connection buffer, only when it helps "
    "the decision. Keep common quote-scope gaps in one shared sentence.",
)
_PROFILE_INSTRUCTIONS["category-c05"] = (
    _PROFILE_INSTRUCTIONS["category-c04"][0],
    _PROFILE_INSTRUCTIONS["category-c03"][1] +
    " Put the cash comparison only in its k=b sentence; do not copy that sentence "
    "into k=t prose or a card reason. Make any opening comparison agree with "
    "the exact benefits of the selected journeys, or omit it if the source does "
    "not support one. A journey in Ranking's time category qualifies for a "
    "duration band; that membership alone does not mean it arrives before a "
    "different selected journey or is shorter than every selected journey. "
    "Use selected_temporal_relations for any relative departure, arrival or "
    "duration statement; preserve equal arrivals as equal and do not replace "
    "arrival with elapsed duration or departure. An overlap of categories is "
    "not an overall winner. Say shared separate-ticket protection uncertainty "
    "once, adding only a choice's different connection buffer locally when "
    "useful. Keep the cash sentence plain: source route, quoted amount and "
    "uncertainty, without creative stop-label compounds.",
)
_PROFILE_INSTRUCTIONS["category-c06"] = (
    _PROFILE_INSTRUCTIONS["category-c05"][0],
    "Write a concise, natural traveler answer from the exact authoring_records. "  # noqa: ISC004
    "They are a candidate pool, not a list to display in full. Show the smallest "
    "useful subset that explains materially different choices while representing "
    "each selected Ranking category perspective. A selected journey may cover "
    "several perspectives; no category requires a separate card or fixed quota. "
    "Omit a pool member if it adds no distinct traveler decision, and never refer "
    "to an omitted member in prose. Every concrete option discussed needs its "
    "own exact source-resolved block: k=p or a for a complete journey, k=l for "
    "a research lead. Put its short decision reason in v and a natural label in "
    "n. Source-resolved cards show schedules, routes, cabin, points, fees, seats "
    "and conditions; do not repeat those facts in prose as a card recap. "
    "For complete journeys, explain the supported benefit that distinguishes "
    "each shown choice, such as a shorter trip, cabin or connection buffer. "
    "Use Ranking's time/cost/premium memberships as source facts, but describe "
    "the traveler benefit in ordinary language, with no empty category notices "
    "or mandatory headings. Time membership means a qualifying duration band, "
    "not earlier arrival or dominance over another selected journey. Use "
    "selected_temporal_relations for relative departure, arrival or duration "
    "claims; preserve equal arrivals as equal and do not substitute one metric "
    "for another. Category overlap does not create an overall winner. "
    "When no complete eligible journey exists, say so once. Show only leads "
    "with a distinct supported conditional next-check reason, such as program "
    "access, a compatible date, cabin or a useful same-program quote difference. "
    "A date or quote alone is a card fact, not a reason. Do not assume the "
    "traveler owns program points or prefers a date or cabin. Do not force "
    "same-program pairs, a lowest-points rule, or cross-program economic ranking. "
    "Preserve each quote's scope: incomplete or unknown-scope amounts do not "
    "establish a per-person fare, all-in trip cost or cheapest-overall choice. "
    "Give a choice-specific downside or condition only when it changes that "
    "choice's decision; do not invent a local downside from a shared unknown. "
    "State common missing schedule, quote-scope, seat, taxes or separate-ticket "
    "limits once after the choices. Keep any opening sentence consistent with "
    "shown choices, or omit the comparison if unsupported. Do not repeat "
    "generic availability advice; display adds it separately. "
    "Use one k=b SOURCE-BOUND INLINE CASH SENTENCE with the exact benchmark "
    "r: plain source origin-to-destination route, quoted amount and material "
    "uncertainty. Do not copy this sentence into k=t prose or a card reason, "
    "extend the quote to connecting cities, or invent stop descriptors. "
    "A loyalty program is not an operating airline; do not guess a missing "
    "carrier or borrow one from another record. Never print internal J/A/C "
    "aliases. Output JSON blocks in reading order.",
)
_PROFILE_INSTRUCTIONS["category-c07"] = (
    "Select exact source references for a concise traveler answer. Ranking's "  # noqa: ISC004
    "time, cost and premium memberships are authoritative and can overlap. "
    "Return JSON with choices plus style_audit for time, cost and premium. "
    "For each available style, set r to one exact source member worth showing, "
    "or null with a specific omission_reason if that perspective adds no "
    "material traveler value. A nonnull r selects that reference into the "
    "authoring pool even if absent from choices; leave its omission_reason empty. "
    "For an unavailable style use r=null and omission_reason=''. One journey "
    "may serve several styles, so reuse its alias and do not fill a quota. "
    "Choices may add other useful exact journey or incomplete-lead references "
    "and one direct cash benchmark; the union has at most six nonbenchmark "
    "references plus one cash benchmark. Do not choose near-identical variants "
    "without a distinct traveler decision. If no complete journey exists, "
    "choose useful different research leads without styles; inspect supported "
    "same-program, cabin and date contrasts without imposing pairs or quotas. "
    "A reported seat does not prove current availability. Preserve uncertain "
    "cost states and do not rank different programs by point totals. Reasons "
    "are audit-only and never authoring facts. The full explorer is separate.",
    _PROFILE_INSTRUCTIONS["category-c06"][1] +
    " For cash context rely on its quote.kind, quote.display and "
    "quote.source_unit; fee metadata does not describe the cash fare unit. "
    "The display already supplies the canonical availability reminder, so "
    "leave generic current-availability warnings out of authored prose.",
)
_PROFILE_INSTRUCTIONS["category-c08"] = (
    _PROFILE_INSTRUCTIONS["category-c07"][0]
    .replace("leave its omission_reason empty.", "set omission_reason=null.")
    .replace("For an unavailable style use r=null and omission_reason=''.",
             "For an unavailable style use r=null and omission_reason=null."),
    _PROFILE_INSTRUCTIONS["category-c07"][1],
)
_PROFILE_INSTRUCTIONS["category-c09"] = _PROFILE_INSTRUCTIONS["category-c08"]
_PROFILE_INSTRUCTIONS["category-c10"] = (
    _PROFILE_INSTRUCTIONS["category-c09"][0],
    _PROFILE_INSTRUCTIONS["category-c09"][1].replace(
        "When no complete eligible journey exists, say so once. Show only leads "
        "with a distinct supported conditional next-check reason, such as program "
        "access, a compatible date, cabin or a useful same-program quote difference. "
        "A date or quote alone is a card fact, not a reason.",
        "When no complete eligible journey exists, say so once. For every k=l "
        "lead, use v for its supported conditional reason to check the program, "
        "date, cabin or useful same-program quote difference. The source card "
        "already identifies research status and shows its reported gaps. Discuss "
        "shared gaps once; add a lead-specific condition only if it changes the "
        "next check. A date or quote alone is a card fact, not a reason."),
)
_PROFILE_INSTRUCTIONS["category-c11"] = (
    _PROFILE_INSTRUCTIONS["category-c10"][0],
    _PROFILE_INSTRUCTIONS["category-c10"][1].replace(
        "Give a choice-specific downside or condition only when it changes that "
        "choice's decision; do not invent a local downside from a shared unknown. "
        "State common missing schedule, quote-scope, seat, taxes or separate-ticket "
        "limits once after the choices.",
        "The condition_applicability table gives source condition codes, states "
        "and exact selected-pool aliases, not words to copy. Consider only the "
        "choices you actually show; explain each relevant condition once in "
        "natural language, locally when it changes that choice's next action or "
        "together when it applies across shown choices. Do not repeat a condition "
        "in both places or infer one from a missing field."),
)
_PROFILE_INSTRUCTIONS["category-c12"] = (
    _PROFILE_INSTRUCTIONS["category-c11"][0],
    _PROFILE_INSTRUCTIONS["category-c11"][1].replace(
        "Source-resolved cards show schedules, routes, cabin, points, fees, seats "
        "and conditions; do not repeat those facts in prose as a card recap. ",
        "Cards provide itinerary details. Use selected_choice_facts and exact "
        "records to explain why each shown option is worth considering. Briefly "
        "reuse a fact when it explains that reason; avoid narrating the card. "
        "The table does not rank options. A reason may depend on a program, "
        "cabin, date or connection preference without assuming the traveler "
        "has that preference. "),
)
_PROFILE_INSTRUCTIONS["category-c13"] = _PROFILE_INSTRUCTIONS["category-c12"]
_PROFILE_INSTRUCTIONS["category-c14"] = (
    _PROFILE_INSTRUCTIONS["category-c12"][0].replace(
        "the union has at most six nonbenchmark references plus one cash benchmark.",
        "the union has at most three nonbenchmark references plus one cash benchmark."),
    _PROFILE_INSTRUCTIONS["category-c12"][1],
)
_PROFILE_INSTRUCTIONS["category-c15"] = (
    "Select exact source references for a concise traveler answer. Ranking's "  # noqa: ISC004
    "time, cost and premium memberships are authoritative and can overlap. "
    "Return JSON with choices, benchmark_alias and style_audit. Choices contains "
    "at most three unique complete-journey or incomplete-lead references, never "
    "the cash benchmark; this is a ceiling, not a quota. Set benchmark_alias "
    "to one exact direct cash benchmark or null. For each available style, set "
    "choice_index to the zero-based index of a chosen journey that belongs to "
    "that style, or null with a specific omission_reason if that perspective "
    "adds no material traveler value. An index only points into choices and "
    "never adds a reference. One journey may serve several styles; use its same "
    "index and do not fill a quota. For an unavailable style use choice_index=null "
    "and omission_reason=null; for a chosen witness use omission_reason=null. "
    "Choices may include other useful exact journey or incomplete-lead references "
    "within the same three-reference ceiling. Do not choose near-identical "
    "variants without a distinct traveler decision. If no complete journey "
    "exists, choose useful different research leads without styles; inspect "
    "supported same-program, cabin and date contrasts without imposing pairs "
    "or quotas. A reported seat does not prove current availability. Preserve "
    "uncertain cost states and do not rank different programs by point totals. "
    "Omission reasons are audit-only and never authoring facts. The full explorer "
    "is separate.",
    _PROFILE_INSTRUCTIONS["category-c14"][1],
)
_PROFILE_INSTRUCTIONS["category-c16"] = (
    _PROFILE_INSTRUCTIONS["category-c15"][0],
    _PROFILE_INSTRUCTIONS["category-c15"][1].replace(
        "Do not force same-program pairs, a lowest-points rule, or cross-program "
        "economic ranking. ",
        "Do not force same-program pairs, a lowest-points rule or a numerical "
        "comparison. Points belong to their named loyalty programs: a smaller "
        "raw count in a different program does not establish an advantage and "
        "is not a reason to favor or investigate that lead. Conditional program "
        "access, date or cabin suitability can supply the reason on its own. "
        "Within one program, reported quotes may be compared while preserving "
        "their scope and incomplete status. "),
)
_PROFILE_INSTRUCTIONS["category-c17"] = _PROFILE_INSTRUCTIONS["category-c16"]
_PROFILE_INSTRUCTIONS["category-c18"] = (
    _PROFILE_INSTRUCTIONS["category-c17"][0],
    _PROFILE_INSTRUCTIONS["category-c17"][1].replace(
        "For complete journeys, explain the supported benefit that distinguishes "
        "each shown choice, such as a shorter trip, cabin or connection buffer. "
        "Use Ranking's time/cost/premium memberships as source facts, but describe "
        "the traveler benefit in ordinary language, with no empty category notices "
        "or mandatory headings. Time membership means a qualifying duration band, "
        "not earlier arrival or dominance over another selected journey. Use "
        "selected_temporal_relations for relative departure, arrival or duration "
        "claims; preserve equal arrivals as equal and do not substitute one metric "
        "for another. Category overlap does not create an overall winner. ",
        "For each shown complete journey, explain when a traveler might choose it "
        "using a supported fact, such as cabin, timing, trip duration, connection "
        "details or a scope-qualified cost or point quote. Put "
        "that decision reason in k=p or a's v; a relevant local condition may "
        "accompany it, but a checklist alone is not a reason. Use Ranking's "
        "time/cost/premium memberships to preserve the useful perspectives, and "
        "express overlapping strengths once in traveler language rather than "
        "explaining category qualification. One journey can be enough; do not "
        "invent a benefit or add a comparison just to fill a pattern. Keep these "
        "evidence limits in your reasoning: time membership alone proves neither "
        "earlier arrival nor superiority over another shown journey, and overlap "
        "is not an overall winner. For any relative departure, arrival or duration "
        "claim, use selected_temporal_relations, preserve equal arrivals as equal "
        "and do not substitute one metric for another. If no useful supported "
        "comparison is being made, omit it rather than adding a disclaimer about "
        "a comparison the answer never makes. "),
)
_PROFILE_INSTRUCTIONS["category-c19"] = (
    _PROFILE_INSTRUCTIONS["category-c18"][0],
    _PROFILE_INSTRUCTIONS["category-c18"][1].replace(
        "Preserve each quote's scope: incomplete or unknown-scope amounts do not "
        "establish a per-person fare, all-in trip cost or cheapest-overall choice. "
        "The condition_applicability table gives source condition codes, states "
        "and exact selected-pool aliases, not words to copy. Consider only the "
        "choices you actually show; explain each relevant condition once in "
        "natural language, locally when it changes that choice's next action or "
        "together when it applies across shown choices. Do not repeat a condition "
        "in both places or infer one from a missing field. ",
        "Preserve each quote's meaning: a reported number and its pricing basis "
        "are different facts. Unknown scope does not make a known points, tax or "
        "cash amount unknown, and incomplete quotes or reported amounts with "
        "unknown scope do not "
        "establish a per-person fare, all-in trip cost or cheapest-overall choice. "
        "Use the condition_applicability table only for the specific source fields "
        "and shown choices to which each condition applies; keep amount "
        "uncertainty, quote basis, party support and separate cash roles distinct. "
        "Explain the practical consequence of a relevant condition once, in your "
        "own words. Its explanation may sit with a choice or comparison, or in "
        "shared prose; either placement is sufficient. If it is already qualified "
        "locally, a later shared paragraph should cover only the remaining "
        "distinct conditions, not restate that qualification as another check. "
        "Do not turn the table into an extra checklist after those conditions "
        "have already been explained. Do not group known reported amounts into "
        "a blanket 'these details are unknown' statement or infer a condition "
        "from a missing field. "),
)
_PROFILE_INSTRUCTIONS["category-c20"] = (
    _PROFILE_INSTRUCTIONS["category-c19"][0],
    _PROFILE_INSTRUCTIONS["category-c19"][1].replace(
        "Explain the practical consequence of a relevant condition once, in your "
        "own words. Its explanation may sit with a choice or comparison, or in "
        "shared prose; either placement is sufficient. ",
        "For each relevant condition_applicability row, consider only its "
        "applies_to choices that you actually show. Explain the condition's "
        "practical consequence once for that whole affected group, in your own "
        "words, not separately for each quote or card; make clear which shown "
        "choices it covers. A condition affecting only one shown choice can stay "
        "local. This explanation may sit in a caption, comparison, opening or "
        "other prose; no separate shared-limits block is required. "),
)

_PROFILE_INCOMPLETE_FORMAT: dict[str, Literal["roles-v20", "roles-v30"]] = {
    "category-c01": "roles-v20",
    "category-c02": "roles-v20",
    "category-c03": "roles-v30",
    "category-c04": "roles-v30",
    "category-c05": "roles-v30",
    "category-c06": "roles-v30",
    "category-c07": "roles-v30",
    "category-c08": "roles-v30",
    "category-c09": "roles-v30",
    "category-c10": "roles-v30",
    "category-c11": "roles-v30",
    "category-c12": "roles-v30",
    "category-c13": "roles-v30",
    "category-c14": "roles-v30",
    "category-c15": "roles-v30",
    "category-c16": "roles-v30",
    "category-c17": "roles-v30",
    "category-c18": "roles-v30",
    "category-c19": "roles-v30",
    "category-c20": "roles-v30",
}
_PROFILE_CHECK_POLICIES = {
    "category-c01": "legacy",
    "category-c02": "legacy",
    "category-c03": "legacy",
    "category-c04": "exact_cash_dedup",
    "category-c05": "exact_cash_dedup",
    "category-c06": "exact_cash_dedup",
    "category-c07": "exact_cash_dedup",
    "category-c08": "exact_cash_dedup",
    "category-c09": "exact_cash_dedup",
    "category-c10": "exact_cash_dedup",
    "category-c11": "exact_cash_dedup",
    "category-c12": "exact_cash_dedup",
    "category-c13": "exact_cash_dedup",
    "category-c14": "exact_cash_dedup",
    "category-c15": "exact_cash_dedup",
    "category-c16": "exact_cash_dedup",
    "category-c17": "exact_cash_dedup",
    "category-c18": "exact_cash_dedup",
    "category-c19": "exact_cash_dedup",
    "category-c20": "exact_cash_dedup",
}
_PROFILE_TEMPORAL_AID = {
    "category-c01": False,
    "category-c02": False,
    "category-c03": False,
    "category-c04": False,
    "category-c05": True,
    "category-c06": True,
    "category-c07": True,
    "category-c08": True,
    "category-c09": True,
    "category-c10": True,
    "category-c11": True,
    "category-c12": True,
    "category-c13": True,
    "category-c14": True,
    "category-c15": True,
    "category-c16": True,
    "category-c17": True,
    "category-c18": True,
    "category-c19": True,
    "category-c20": True,
}
_PROFILE_SELECTION_POLICIES = {
    "category-c01": "omitted_list",
    "category-c02": "omitted_list",
    "category-c03": "omitted_list",
    "category-c04": "omitted_list",
    "category-c05": "omitted_list",
    "category-c06": "omitted_list",
    "category-c07": "style_audit",
    "category-c08": "style_audit_nullable",
    "category-c09": "style_audit_nullable",
    "category-c10": "style_audit_nullable",
    "category-c11": "style_audit_nullable",
    "category-c12": "style_audit_nullable",
    "category-c13": "style_audit_nullable",
    "category-c14": "style_audit_nullable",
    "category-c15": "indexed_audit",
    "category-c16": "indexed_audit",
    "category-c17": "indexed_audit",
    "category-c18": "indexed_audit",
    "category-c19": "indexed_audit",
    "category-c20": "indexed_audit",
}
_PROFILE_COMPOSER_SETTINGS = {"category-c09": _MEDIUM_SETTINGS,
                              "category-c10": _MEDIUM_SETTINGS,
                              "category-c11": _MEDIUM_SETTINGS,
                              "category-c12": _MEDIUM_SETTINGS,
                              "category-c13": _SETTINGS,
                              "category-c14": _MEDIUM_SETTINGS,
                              "category-c15": _MEDIUM_SETTINGS,
                              "category-c16": _MEDIUM_SETTINGS,
                              "category-c17": _MEDIUM_SETTINGS,
                              "category-c18": _MEDIUM_SETTINGS,
                              "category-c19": _MEDIUM_SETTINGS,
                              "category-c20": _MEDIUM_SETTINGS}
_PROFILE_LEAD_V_DESCRIPTION = {
    "category-c10": ("Supported conditional reason to check this lead's program, "
                     "date or cabin. Its source card shows research status and "
                     "reported gaps; shared gaps belong once in surrounding prose."),
}
_PROFILE_LEAD_V_DESCRIPTION["category-c11"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_LEAD_V_DESCRIPTION["category-c12"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_LEAD_V_DESCRIPTION["category-c13"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_LEAD_V_DESCRIPTION["category-c14"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_LEAD_V_DESCRIPTION["category-c15"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_LEAD_V_DESCRIPTION["category-c16"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_LEAD_V_DESCRIPTION["category-c17"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_LEAD_V_DESCRIPTION["category-c18"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_LEAD_V_DESCRIPTION["category-c19"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_LEAD_V_DESCRIPTION["category-c20"] = _PROFILE_LEAD_V_DESCRIPTION["category-c10"]
_PROFILE_CONDITION_AID = {"category-c11", "category-c12", "category-c13", "category-c14",
                          "category-c15", "category-c16", "category-c17", "category-c18",
                          "category-c19", "category-c20"}
_PROFILE_CHOICE_AID = {"category-c12", "category-c13", "category-c14", "category-c15",
                       "category-c16", "category-c17", "category-c18", "category-c19",
                       "category-c20"}
_PROFILE_SELECTION_LIMITS = {"category-c14": (3, 4), "category-c15": (3, 4),
                             "category-c16": (3, 4), "category-c17": (3, 4),
                             "category-c18": (3, 4), "category-c19": (3, 4),
                             "category-c20": (3, 4)}
_PROFILE_AWARD_SCOPE_NORMALIZATION = {"category-c17", "category-c18", "category-c19",
                                      "category-c20"}


def _selection_limits(profile: str) -> tuple[int, int]:
    return _PROFILE_SELECTION_LIMITS.get(profile, (MAX_NONBENCHMARK, MAX_TOTAL))


def _nonbenchmark_limit_error(limit: int) -> ValueError:
    # Preserve the archived six-reference failure text for earlier profiles.
    label = "six" if limit == MAX_NONBENCHMARK else str(limit)
    return ValueError(f"category selection exceeds {label} nonbenchmark references")


def _composer_settings(profile: str) -> InteractiveSettings:
    return _PROFILE_COMPOSER_SETTINGS.get(profile, _SETTINGS)


def category_profiles() -> tuple[str, ...]:
    """Public opt-in profile names, shared by API validation and CLI choices."""
    return tuple(_PROFILE_INSTRUCTIONS)


def _selection_format(profile: str, projection: SolutionProjection) -> Literal["roles-v20", "roles-v30"]:
    return (_PROFILE_INCOMPLETE_FORMAT[profile] if not projection.view.comparison_pool_ids
            else "roles-v20")


def _envelope(config: ResultsConfig, settings: InteractiveSettings, instructions: str,
              packet: dict[str, object], schema: dict[str, object], *, name: str,
              previous_wire: str | None = None,
              feedback: tuple[CheckFinding, ...] = ()) -> RequestEnvelope:
    payload: dict[str, object] = {"packet": packet}
    if previous_wire is not None:
        payload["previous_wire"] = json.loads(previous_wire)
        payload["feedback"] = [item.model_dump(mode="json") for item in feedback]
    input_text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    schema_text = json.dumps(schema, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    request: dict[str, object] = {
        "model": config.model, "reasoning": {"effort": settings.reasoning_effort},
        "instructions": instructions, "input": input_text,
        "text": {"format": {"type": "json_schema", "name": name,
                            "strict": True, "schema": schema}},
    }
    size = len((instructions + input_text).encode()) + len(schema_text.encode())
    return RequestEnvelope(request, size, size + config.prompt_overhead_tokens +
                           config.max_output_tokens, content_digest(instructions + input_text),
                           content_digest(schema_text))


def _style_aliases(selector: InteractivePreparedInput,
                   projection: SolutionProjection) -> dict[str, list[str]]:
    refs = selector.structured.references.journeys
    return {style: [alias for alias, canonical in refs.items()
                    if canonical in set(getattr(projection.view.indexes, style))]
            for style in ("time", "cost", "premium")}


def _selection_schema(selector: InteractivePreparedInput,
                      projection: SolutionProjection, profile: str) -> dict[str, object]:
    nonbenchmark_limit, total_limit = _selection_limits(profile)
    schema = selection_schema_v2(selector.structured, projection, max_references=total_limit)
    properties = cast(dict[str, Any], schema["properties"])
    policy = _PROFILE_SELECTION_POLICIES[profile]
    if policy == "indexed_audit":
        choices = cast(dict[str, Any], properties["choices"])
        branches = cast(list[dict[str, Any]],
                        cast(dict[str, Any], choices["items"]).get("anyOf", []))
        noncash = [branch for branch in branches
                   if cast(dict[str, Any], branch["properties"])["k"]["enum"] != ["b"]]
        choices["items"] = ({"anyOf": noncash} if noncash else
                            {"type": "object", "additionalProperties": False,
                             "properties": {"k": {"type": "string"},
                                            "r": {"type": "string"}},
                             "required": ["k", "r"]})
        choices["minItems"] = 0
        choices["maxItems"] = nonbenchmark_limit if noncash else 0
        benchmarks = cast(list[str], selector.packet["benchmark_refs"])
        properties["benchmark_alias"] = ({"anyOf": [
            {"type": "string", "enum": benchmarks}, {"type": "null"}]}
            if benchmarks else {"type": "null"})

        def indexed_branch(index: dict[str, object],
                           reason: dict[str, object]) -> dict[str, object]:
            return {"type": "object", "additionalProperties": False,
                    "properties": {"choice_index": index, "omission_reason": reason},
                    "required": ["choice_index", "omission_reason"]}

        indexed_style_properties: dict[str, object] = {}
        for style, aliases in _style_aliases(selector, projection).items():
            indexed_style_properties[style] = ({"anyOf": [
                indexed_branch({"type": "integer", "enum": list(range(nonbenchmark_limit))},
                               {"type": "null"}),
                indexed_branch({"type": "null"}, {"type": "string"})]}
                if aliases else indexed_branch({"type": "null"}, {"type": "null"}))
        properties["style_audit"] = {"type": "object", "additionalProperties": False,
            "properties": indexed_style_properties, "required": ["time", "cost", "premium"]}
        schema["required"] = ["choices", "benchmark_alias", "style_audit"]
        return schema
    if policy in {"style_audit", "style_audit_nullable"}:
        cast(dict[str, Any], properties["choices"])["minItems"] = 0
        style_properties: dict[str, object] = {}
        for style, aliases in _style_aliases(selector, projection).items():
            if policy == "style_audit_nullable":
                def branch(reference: dict[str, object],
                           reason: dict[str, object]) -> dict[str, object]:
                    return {"type": "object", "additionalProperties": False,
                            "properties": {"r": reference, "omission_reason": reason},
                            "required": ["r", "omission_reason"]}
                style_properties[style] = ({"anyOf": [
                    branch({"type": "string", "enum": aliases}, {"type": "null"}),
                    branch({"type": "null"}, {"type": "string"})]}
                    if aliases else branch({"type": "null"}, {"type": "null"}))
            else:
                reference: dict[str, object] = ({"anyOf": [
                    {"type": "string", "enum": aliases}, {"type": "null"}]}
                    if aliases else {"type": "null"})
                style_properties[style] = {"type": "object", "additionalProperties": False,
                    "properties": {"r": reference,
                                   "omission_reason": {"type": "string"}},
                    "required": ["r", "omission_reason"]}
        properties["style_audit"] = {"type": "object", "additionalProperties": False,
            "properties": style_properties,
            "required": ["time", "cost", "premium"]}
        schema["required"] = ["choices", "style_audit"]
        return schema
    properties["omitted"] = {"type": "array", "items": {"type": "object",
        "additionalProperties": False,
        "properties": {"style": {"type": "string", "enum": ["time", "cost", "premium"]},
                       "reason": {"type": "string"}},
        "required": ["style", "reason"]}}
    schema["required"] = ["choices", "omitted"]
    return schema


def _decode_selection(raw: str, selector: InteractivePreparedInput,
                      projection: SolutionProjection, profile: str) -> StructuredSelection:
    value = json.loads(raw)
    nonbenchmark_limit, total_limit = _selection_limits(profile)
    policy = _PROFILE_SELECTION_POLICIES[profile]
    if policy == "indexed_audit":
        return _decode_indexed_selection(value, selector, projection,
                                         nonbenchmark_limit, total_limit)
    if policy in {"style_audit", "style_audit_nullable"}:
        if not isinstance(value, dict) or set(value) != {"choices", "style_audit"} or \
                not isinstance(value["choices"], list) or \
                not isinstance(value["style_audit"], dict) or \
                set(value["style_audit"]) != {"time", "cost", "premium"}:
            raise ValueError("category selection requires choices and every style audit")
        aliases = _style_aliases(selector, projection)
        witnesses: list[dict[str, str]] = []
        for style in ("time", "cost", "premium"):
            row = value["style_audit"][style]
            if not isinstance(row, dict) or set(row) != {"r", "omission_reason"}:
                raise ValueError("category style audit fields are invalid")
            reference = row["r"]
            supplied_reason = row["omission_reason"]
            if policy == "style_audit" and not isinstance(supplied_reason, str):
                raise ValueError("category style audit fields are invalid")
            if policy == "style_audit_nullable" and supplied_reason is not None and \
                    not isinstance(supplied_reason, str):
                raise ValueError("category style audit fields are invalid")
            reason = supplied_reason.strip() if isinstance(supplied_reason, str) else ""
            if reference is None:
                if bool(aliases[style]) != bool(reason) or \
                        (policy == "style_audit_nullable" and
                         ((bool(aliases[style]) and not isinstance(supplied_reason, str)) or
                          (not aliases[style] and supplied_reason is not None))):
                    raise ValueError("category omission requires an available style and reason")
            elif not isinstance(reference, str) or reference not in aliases[style] or reason or \
                    (policy == "style_audit_nullable" and supplied_reason is not None):
                raise ValueError("category witness is not a source style member")
            else:
                witnesses.append({"k": "j", "r": reference})
        choices = value["choices"]
        if any(not isinstance(item, dict) or set(item) != {"k", "r"} or
               item.get("k") not in {"j", "b", "l"} or
               not isinstance(item.get("r"), str) for item in choices):
            raise ValueError("category free choice has invalid role or reference")
        keys = [(item["k"], item["r"]) for item in choices]
        if len(keys) != len(set(keys)):
            raise ValueError("category free choices repeat an exact reference")
        combined: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in (*witnesses, *choices):
            key = (item["k"], item["r"])
            if key not in seen:
                combined.append(item)
                seen.add(key)
        selection = decode_selection_v2({"choices": combined}, selector.structured,
                                        projection, max_references=total_limit)
        if len(selection.journey_ids) + len(selection.incomplete_observation_ids) > nonbenchmark_limit:
            raise _nonbenchmark_limit_error(nonbenchmark_limit)
        return selection
    if not isinstance(value, dict) or set(value) != {"choices", "omitted"} or \
            not isinstance(value["omitted"], list):
        raise ValueError("category selection requires choices and omitted reasons")
    if (any(not isinstance(row, dict) or set(row) != {"style", "reason"} or
            row["style"] not in {"time", "cost", "premium"} or
            not isinstance(row["reason"], str) for row in value["omitted"]) or
            len({row["style"] for row in value["omitted"]}) != len(value["omitted"])):
        raise ValueError("category omission notes are invalid")
    selection = decode_selection_v2({"choices": value["choices"]},
                                    selector.structured, projection,
                                    max_references=total_limit)
    if len(selection.journey_ids) + len(selection.incomplete_observation_ids) > nonbenchmark_limit:
        raise _nonbenchmark_limit_error(nonbenchmark_limit)
    return selection


def _decode_indexed_selection(value: object, selector: InteractivePreparedInput,
                              projection: SolutionProjection, nonbenchmark_limit: int,
                              total_limit: int) -> StructuredSelection:
    if not isinstance(value, dict) or set(value) != {
            "choices", "benchmark_alias", "style_audit"} or \
            not isinstance(value["choices"], list) or \
            not isinstance(value["style_audit"], dict) or \
            set(value["style_audit"]) != {"time", "cost", "premium"}:
        raise ValueError("indexed category selection requires choices, benchmark and every style")
    choices = value["choices"]
    if len(choices) > nonbenchmark_limit:
        raise _nonbenchmark_limit_error(nonbenchmark_limit)
    if any(not isinstance(item, dict) or set(item) != {"k", "r"} or
           item.get("k") not in {"j", "l"} or
           not isinstance(item.get("r"), str) for item in choices):
        raise ValueError("indexed category choice has invalid role or reference")
    keys = [(item["k"], item["r"]) for item in choices]
    if len(keys) != len(set(keys)):
        raise ValueError("indexed category choices repeat an exact reference")
    benchmark = value["benchmark_alias"]
    benchmarks = cast(list[str], selector.packet["benchmark_refs"])
    if benchmark is not None and (not isinstance(benchmark, str) or
                                  benchmark not in benchmarks):
        raise ValueError("indexed category benchmark is not an exact source reference")
    aliases = _style_aliases(selector, projection)
    for style in ("time", "cost", "premium"):
        row = value["style_audit"][style]
        if not isinstance(row, dict) or set(row) != {"choice_index", "omission_reason"}:
            raise ValueError("indexed category style audit fields are invalid")
        index = row["choice_index"]
        supplied_reason = row["omission_reason"]
        if index is None:
            if aliases[style]:
                if not isinstance(supplied_reason, str) or not supplied_reason.strip():
                    raise ValueError("indexed category omission needs a source style and reason")
                if any(item["k"] == "j" and item["r"] in aliases[style]
                       for item in choices):
                    raise ValueError("indexed category omission contradicts chosen journey")
            elif supplied_reason is not None:
                raise ValueError("indexed category absent style has an omission reason")
        elif type(index) is not int or index < 0 or index >= len(choices) or \
                choices[index]["k"] != "j" or choices[index]["r"] not in aliases[style] or \
                supplied_reason is not None:
            raise ValueError("indexed category witness is not a chosen source style member")
    normalized = [*choices]
    if benchmark is not None:
        normalized.append({"k": "b", "r": benchmark})
    selection = decode_selection_v2({"choices": normalized}, selector.structured,
                                    projection, max_references=total_limit)
    if len(selection.journey_ids) + len(selection.incomplete_observation_ids) > nonbenchmark_limit:
        raise _nonbenchmark_limit_error(nonbenchmark_limit)
    return selection


def _selection_findings(raw: str, selection: StructuredSelection,
                        projection: SolutionProjection, profile: str) -> tuple[CheckFinding, ...]:
    value = json.loads(raw)
    policy = _PROFILE_SELECTION_POLICIES[profile]
    omitted = ({style: row["omission_reason"].strip()
                for style, row in value["style_audit"].items()
                if row["choice_index"] is None and isinstance(row["omission_reason"], str)
                and row["omission_reason"].strip()}
               if policy == "indexed_audit" else
               {style: row["omission_reason"].strip()
                for style, row in value["style_audit"].items() if row["r"] is None
                and isinstance(row["omission_reason"], str)
                and row["omission_reason"].strip()}
               if policy in {"style_audit", "style_audit_nullable"} else
               {row["style"]: row["reason"].strip() for row in value["omitted"]})
    indexes = projection.view.indexes
    rows: list[CheckFinding] = []
    if projection.view.direct_cash_observation_ids and selection.benchmark_observation_id is None:
        rows.append(CheckFinding(code="cash_context_omitted", outcome="failed",
            scope="benchmark", message="Available full-cash context was omitted."))
    for style in ("time", "cost", "premium"):
        available = set(getattr(indexes, style))
        selected = available.intersection(selection.journey_ids)
        if available and not selected:
            rows.append(CheckFinding(code="category_omitted", outcome="unchecked" if
                omitted.get(style) else "failed",
                scope="shared", message=f"Available {style} perspective omitted: "
                f"{omitted.get(style) or 'no audit reason supplied'}"))
        elif style in omitted:
            rows.append(CheckFinding(code="spurious_category_omission", outcome="failed",
                scope="shared", message=f"{style} omission note contradicts selection"))
    return tuple(rows)


def _focus(selection: StructuredSelection, selector: InteractivePreparedInput,
           projection: SolutionProjection, evidence: WorkspaceEvidence, *,
           profile: str = "category-c01",
           ) -> InteractivePreparedInput:
    # V30 groups selector leads but its legacy composer has a two-reference cap.
    # Category authoring applies its profile limit after this lossless format bridge.
    composer_selector = (selector.model_copy(update={"packet": {
        **selector.packet, "selection_format": "roles-v20"}})
        if selector.packet.get("selection_format") == "roles-v30" else selector)
    focus = prepare_focused_composer(selection, composer_selector, projection, evidence,
                                     composition_format="complete-v18")
    packet = dict(focus.packet)
    packet["traveler_evidence"] = build_traveler_evidence(focus, evidence)
    packet["source_scope"] = {
        "full_selectable_journey_count": len(cast(list[object], selector.packet["journey_rows"])),
        "full_selectable_lead_count": len(cast(list[object], selector.packet["lead_rows"])),
        "full_direct_cash_benchmark_count": len(cast(list[object], selector.packet["benchmark_refs"])),
        "selected_journey_count": len(selection.journey_ids),
        "selected_lead_count": len(selection.incomplete_observation_ids),
        "selected_benchmark_count": int(selection.benchmark_observation_id is not None),
    }
    packet["editorial_plan"] = []
    packet["temporal_comparisons"] = []
    indexes = projection.view.indexes
    selected = set(selection.journey_ids)
    aliases = cast(dict[str, str], focus.packet["wire_aliases"])
    by_short = {short: long for long, short in aliases.items()}
    reverse = {canonical: by_short[alias]
               for alias, canonical in selector.structured.references.journeys.items()
               if canonical in selected}
    if _PROFILE_TEMPORAL_AID[profile]:
        source_aliases = {long_alias: canonical for canonical, long_alias in reverse.items()}
        registry = build_temporal_registry(evidence, selection.journey_ids, source_aliases)
        packet["selected_temporal_relations"] = [
            {"first_alias": fact.first_alias, "second_alias": fact.second_alias,
             "metric": fact.metric, "relation": fact.relation,
             "difference_minutes": str(fact.difference_minutes)}
            for fact in registry.facts]
    packet["category_landscape"] = {
        "available_counts": {style: len(getattr(indexes, style))
                             for style in ("time", "cost", "premium")},
        "selected_members": {style: [reverse[item] for item in getattr(indexes, style)
                                     if item in selected]
                             for style in ("time", "cost", "premium")},
        "possible_cost_count": len(indexes.possible_cost),
        "meaning": "Ranking memberships are source facts; counts are journey variants, not discoveries.",
    }
    return _prepared(packet, focus.structured)


def _writer_input(focus: InteractivePreparedInput, *,
                  profile: str = "category-c01") -> dict[str, object]:
    result = writer_packet(focus)
    result["category_landscape"] = focus.packet["category_landscape"]
    if _PROFILE_TEMPORAL_AID[profile]:
        result["selected_temporal_relations"] = focus.packet["selected_temporal_relations"]
    if profile in _PROFILE_CONDITION_AID:
        result["condition_applicability"] = _condition_applicability(
            cast(dict[str, dict[str, Any]], result["authoring_records"]),
            merge_award_scope=profile in _PROFILE_AWARD_SCOPE_NORMALIZATION)
    if profile in _PROFILE_CHOICE_AID:
        result["selected_choice_facts"] = _selected_choice_facts(
            cast(dict[str, dict[str, Any]], result["authoring_records"]))
    if _PROFILE_SELECTION_POLICIES[profile] in {
            "style_audit", "style_audit_nullable", "indexed_audit"}:
        records = cast(dict[str, dict[str, Any]], result["authoring_records"])
        for record in records.values():
            if record["role"] == "benchmark" and record["quote"]["kind"] == "cash_fare":
                cast(dict[str, Any], record["facts"]).pop("fee_unit", None)
    return result


def _selected_choice_facts(records: dict[str, dict[str, Any]]) -> list[dict[str, object]]:
    """Expose exact selected choice observations without assigning their merits."""
    rows: list[dict[str, object]] = []
    for alias, record in records.items():
        role = record["role"]
        if role == "benchmark":
            continue
        facts = cast(dict[str, Any], record["facts"])
        award = cast(dict[str, Any], facts["award"] if role == "journey" else facts)
        row: dict[str, object] = {"alias": alias, "role": role}
        for source_key, target_key in (("date", "date"), ("route", "route")):
            if source_key in facts:
                row[target_key] = deepcopy(facts[source_key])
        for key in ("program", "points", "price_scope"):
            if key in award:
                row[key] = deepcopy(award[key])
        if "cabin" in award:
            row["reported_cabin"] = deepcopy(award["cabin"])
        if "kind" in award:
            row["component_kind"] = deepcopy(award["kind"])
        if "leg_cabins" in award:
            row["reported_leg_cabins"] = deepcopy(award["leg_cabins"])
        if role == "journey":
            component = cast(dict[str, Any], record["award_component"])
            row["award_connections"] = deepcopy(component["award_itinerary_connections"])
            row["journey_connections"] = deepcopy(record["journey_connections"])
        rows.append(row)
    return rows


def _condition_applicability(records: dict[str, dict[str, Any]], *,
                             merge_award_scope: bool = False) -> list[dict[str, object]]:
    """Index explicit source conditions by exact selected-pool aliases; write no prose."""
    affected: dict[tuple[str, str], set[str]] = {}

    def field(record: dict[str, Any], *path: str) -> object:
        value: object = record
        for key in path:
            if not isinstance(value, dict):
                return None
            value = value.get(key)
        return value

    def add(code: str, state: object, alias: str) -> None:
        if isinstance(state, str):
            affected.setdefault((code, state), set()).add(alias)

    for alias, record in records.items():
        role = record.get("role")
        if role == "journey":
            points_unknown = field(record, "facts", "award", "price_scope") == "unknown"
            tax_quote = field(record, "award_component", "quote", "kind") == "award_taxes"
            tax_scope_unknown = tax_quote and field(
                record, "award_component", "quote", "price_scope") == "unknown"
            member_award_ref = field(record, "member", "award_ref")
            source_bound_award = (isinstance(member_award_ref, str) and bool(member_award_ref)
                                  and member_award_ref == field(record, "award_component", "ref"))
            if merge_award_scope and source_bound_award and points_unknown and tax_scope_unknown:
                # Both scope projections copy the same exact award component's price_scope.
                add("award_points_and_tax_quote_scope", "unknown", alias)
            else:
                if points_unknown:
                    add("award_price_scope", "unknown", alias)
                if tax_scope_unknown:
                    add("award_tax_quote_scope", "unknown", alias)
            if tax_quote:
                amount_state = field(record, "award_component", "quote", "amount_state")
                if amount_state in {"absent", "null", "unknown"}:
                    add("award_tax_amount", amount_state, alias)
            party = field(record, "traveler_evidence", "award_support_for_requested_party")
            if party in {"failed", "unknown"}:
                add("award_party_support", party, alias)
            caveats = field(record, "facts", "caveats")
            if isinstance(caveats, list):
                for caveat in caveats:
                    if isinstance(caveat, dict) and caveat.get("code") in {
                            "separate_ticket_obligation", "positioning_permission_unknown"}:
                        add(caveat["code"], caveat.get("state"), alias)
            if field(record, "cash_component", "quote", "kind") == "cash_fare" and \
                    field(record, "cash_component", "quote", "price_scope") == "unknown":
                add("positioning_cash_quote_scope", "unknown", alias)
        elif role == "lead":
            if field(record, "facts", "schedule_state") == "date_only":
                add("lead_schedule", "date_only", alias)
            quote_kind = field(record, "quote", "kind")
            if field(record, "quote", "price_scope") == "unknown":
                if quote_kind == "award_taxes":
                    add("lead_award_tax_quote_scope", "unknown", alias)
                elif quote_kind == "cash_fare":
                    add("lead_cash_quote_scope", "unknown", alias)
        elif role == "benchmark" and field(record, "quote", "kind") == "cash_fare" and \
                field(record, "quote", "price_scope") == "unknown":
            add("benchmark_cash_quote_scope", "unknown", alias)
    return [{"code": code, "state": state, "applies_to": sorted(aliases)}
            for (code, state), aliases in sorted(affected.items())]


def _document_findings(document: StructuredDocument, projection: SolutionProjection,
                       focus: InteractivePreparedInput, *,
                       exact_cash_dedup: bool = False) -> tuple[CheckFinding, ...]:
    rows = list(_findings(document, projection, focus))
    shown = {block.reference_id for block in document.blocks
             if block.kind == "reference" and block.reference_kind == "journey"}
    shown_list = [block.reference_id for block in document.blocks
                  if block.kind == "reference" and block.reference_kind == "journey"]
    if len(shown_list) != len(shown):
        rows.append(CheckFinding(code="duplicate_journey_card", outcome="failed",
            scope="shared", message="Explain each exact journey with one card."))
    cash_blocks = [block for block in document.blocks
                   if block.kind == "reference" and block.reference_kind == "benchmark"]
    if len(cash_blocks) > 1:
        rows.append(CheckFinding(code="repeated_cash_sentence", outcome="failed",
            scope="benchmark", message="Show the full-cash comparison once."))
    if exact_cash_dedup and len(cash_blocks) == 1:
        cash_text = " ".join(cash_blocks[0].text.split())
        if cash_text:
            for index, block in enumerate(document.blocks):
                if block is cash_blocks[0]:
                    continue
                if cash_text in " ".join(block.text.split()):
                    rows.append(CheckFinding(code="duplicate_cash_sentence_in_prose",
                        outcome="failed", scope="benchmark",
                        reference_id=cash_blocks[0].reference_id, part_index=index,
                        message="Keep the exact cash sentence only in its source-bound block."))
    lead_list = [block.reference_id for block in document.blocks
                 if block.kind == "reference" and block.reference_kind == "lead"]
    if len(lead_list) != len(set(lead_list)):
        rows.append(CheckFinding(code="duplicate_lead_card", outcome="failed",
            scope="incomplete", message="Show each research lead once."))
    landscape = cast(dict[str, object], focus.packet["category_landscape"])
    selected_members = cast(dict[str, list[str]], landscape["selected_members"])
    aliases = cast(dict[str, str], focus.packet["wire_aliases"])
    refs = focus.structured.references.journeys
    for style in ("time", "cost", "premium"):
        selected = {refs[aliases[alias]] for alias in selected_members[style]}
        if selected and not shown.intersection(selected):
            rows.append(CheckFinding(code="selected_category_not_shown", outcome="failed",
                scope="shared", message=f"Selected {style} journey has no visible card"))
    for index, block in enumerate(document.blocks):
        if block.kind == "reference" and block.reference_kind == "benchmark":
            sentence = block.text.strip()
            if not sentence or len(re.findall(r"[.!?](?:\s|$)", sentence)) != 1:
                rows.append(CheckFinding(code="cash_not_one_sentence", outcome="failed",
                    scope="benchmark", reference_id=block.reference_id, part_index=index,
                    message="Cash context must be one brief sentence."))
    return tuple(rows)


def _checker(profile: str) -> Callable[[StructuredDocument, SolutionProjection,
                                       InteractivePreparedInput], tuple[CheckFinding, ...]]:
    return partial(_document_findings,
                   exact_cash_dedup=_PROFILE_CHECK_POLICIES[profile] == "exact_cash_dedup")


def _document_schema(focus: InteractivePreparedInput, profile: str) -> dict[str, object]:
    schema = document_schema(focus)
    description = _PROFILE_LEAD_V_DESCRIPTION.get(profile)
    if description is not None:
        branches = cast(list[dict[str, Any]],
            cast(dict[str, Any], cast(dict[str, Any], schema["properties"])["blocks"])["items"]["anyOf"])
        for branch in branches:
            properties = cast(dict[str, Any], branch["properties"])
            if properties["k"]["enum"] == ["l"]:
                properties["v"] = {**cast(dict[str, Any], properties["v"]),
                                   "description": description}
                break
    return schema


def _answer(document: StructuredDocument, focus: InteractivePreparedInput,
            evidence: WorkspaceEvidence, findings: tuple[CheckFinding, ...],
            selection_findings: tuple[CheckFinding, ...]) -> CategoryAnswer:
    resolved = resolve_structured_document(document, focus.structured, evidence, findings)
    components = {item.observation_id: item for item in evidence.components}
    by_assessment = {row.assessment_id: row for row in evidence.source.view.assessments}
    assessments = {option.candidate_id: tuple(by_assessment[assessment_id].model_dump(mode="json")
                   for assessment_id in option.assessment_ids)
                   for option in evidence.source.view.alternatives}
    blocks: list[CategoryBlock] = []
    for block in resolved.blocks:
        if block.kind == "narrative":
            blocks.append(CategoryBlock(kind="text", text=block.text))
        elif block.reference_kind == "journey" and block.journey is not None:
            journey = block.journey
            blocks.append(CategoryBlock(kind="journey_card", text=block.text,
                label=block.label, canonical_id=block.canonical_id, journey=journey,
                award_component=components.get(journey.award_observation_id),
                cash_component=components.get(journey.cash_observation_id or ""),
                ranking_assessments=assessments.get(journey.candidate_id, ())))
        elif block.reference_kind == "lead" and block.lead is not None:
            blocks.append(CategoryBlock(kind="lead_card", text=block.text,
                label=block.label, canonical_id=block.canonical_id, lead=block.lead,
                lead_component=components.get(block.lead.award_observation_id or "") or
                               components.get(block.lead.cash_observation_id or "")))
        elif block.reference_kind == "benchmark" and block.component is not None:
            blocks.append(CategoryBlock(kind="cash_sentence", text=block.text,
                canonical_id=block.canonical_id, benchmark_component=block.component))
        else:
            raise ValueError("category answer contains an unavailable selected reference")
    return CategoryAnswer(selected_journey_ids=resolved.selected_journey_ids,
        blocks=tuple(blocks), availability_guidance=resolved.availability_guidance,
        findings=selection_findings + findings)


def _requests(projection: SolutionProjection, config: ResultsConfig,
              selector: InteractivePreparedInput, focus: InteractivePreparedInput | None,
              profile: str, *, previous_wire: str | None = None,
              feedback: tuple[CheckFinding, ...] = (),
              ) -> RequestEnvelope:
    selection_guide, author_guide = _PROFILE_INSTRUCTIONS[profile]
    if focus is None:
        return _envelope(config, _SETTINGS, selection_guide,
            selector_packet(selector), _selection_schema(selector, projection, profile),
            name="CategorySelection")
    guide = author_guide
    if previous_wire is not None:
        guide += " Repair the same full answer from frozen facts and findings."
    if config.authoring_guidance and config.authoring_guidance.strip():
        guide += "\n" + config.authoring_guidance
    settings = _SETTINGS if previous_wire is not None else _composer_settings(profile)
    return _envelope(config, settings, guide, _writer_input(focus, profile=profile),
        _document_schema(focus, profile), name="CategoryDocument",
        previous_wire=previous_wire, feedback=feedback)


def run_category_results(projection: SolutionProjection, config: ResultsConfig,
                         writer: InteractiveWriter,
                         input_measurer: ResultsInputMeasurer | None = None, *,
                         fx_acquisition: FxAcquisition | None = None,
                         profile: str = "category-c01") -> CategoryArtifact:
    """Run one immutable category hypothesis; no implicit public-default switch."""
    if profile not in _PROFILE_INSTRUCTIONS or config.model != "gpt-6-luna":
        raise ValueError("unknown category profile or non-Luna model")
    started = time.perf_counter()
    evidence = resolve_workspace(projection, fx_acquisition=fx_acquisition)
    selector = prepare_focused_selector(projection, config, evidence,
                                        selection_format=_selection_format(profile, projection))
    decode: Callable[[str], StructuredSelection] = lambda raw: _decode_selection(
        raw, selector, projection, profile)
    first = _pass("selection", _requests(projection, config, selector, None, profile),
        config, _SETTINGS, writer, input_measurer, decode,
        projection=projection, prepared=selector)
    passes = [first]
    focus = None
    selection_findings: tuple[CheckFinding, ...] = ()
    if first.outcome == "recoverable":
        assert first.selection is not None and first.raw_wire is not None
        selection_findings = _selection_findings(first.raw_wire, first.selection,
                                                projection, profile)
        focus = _focus(first.selection, selector, projection, evidence, profile=profile)
        decode_author: Callable[[str], StructuredDocument] = lambda raw: decode_document(raw, focus, projection)
        second = _pass("composition", _requests(projection, config, selector, focus, profile),
            config, _composer_settings(profile), writer, input_measurer, decode_author,
            projection=projection, prepared=focus, checker=_checker(profile))
        passes.append(second)
        failures = tuple(f for f in second.findings if f.outcome == "failed")
        if second.outcome == "recoverable" and failures:
            assert second.raw_wire is not None
            passes.append(_pass("correction", _requests(projection, config, selector,
                focus, profile, previous_wire=second.raw_wire, feedback=failures),
                config, _SETTINGS, writer, input_measurer, decode_author,
                projection=projection, prepared=focus, checker=_checker(profile)))
    recoverable = tuple((index - 1, item.findings) for index, item in enumerate(passes)
                        if index >= 1 and item.outcome == "recoverable" and item.document is not None)
    chosen = (choose_recoverable(recoverable)[0] + 1 if recoverable else None)
    chosen_index = chosen if chosen is not None else 0
    resolved = (_answer(cast(StructuredDocument, passes[chosen_index].document),
                        cast(InteractivePreparedInput, focus), evidence,
                        passes[chosen_index].findings, selection_findings)
                if chosen is not None else None)
    terminal = passes[-1]
    validation = ("unavailable" if resolved is None else
                  "annotated" if any(f.outcome == "failed" for f in selection_findings) or any(f.outcome == "failed" for f in
                  passes[chosen_index].findings) else "clean")
    artifact = CategoryArtifact(profile=profile, evidence=evidence, config=config,
        selector_settings=_SETTINGS, composer_settings=_composer_settings(profile),
        correction_settings=_SETTINGS, selector_prepared=selector,
        focus_prepared=focus, passes=tuple(passes), selection_findings=selection_findings,
        selected_pass_index=chosen, generation_outcome=cast(Any,
            "success" if resolved is not None else terminal.outcome),
        validation_outcome=cast(Any, validation),
        delivery_outcome="delivered" if resolved is not None else "not_delivered",
        resolved=resolved,
        resolved_digest=content_digest(resolved.model_dump(mode="json")) if resolved else None,
        runtime_seconds=time.perf_counter() - started)
    return artifact


def measure_category_results(projection: SolutionProjection, config: ResultsConfig,
                             *, profile: str = "category-c01",
                             fx_acquisition: FxAcquisition | None = None,
                             ) -> dict[str, object]:
    """Prepare and size only the selector request; make no API calls."""
    if profile not in _PROFILE_INSTRUCTIONS or config.model != "gpt-6-luna":
        raise ValueError("unknown category profile or non-Luna model")
    evidence = resolve_workspace(projection, fx_acquisition=fx_acquisition)
    selector = prepare_focused_selector(projection, config, evidence,
                                        selection_format=_selection_format(profile, projection))
    envelope = _requests(projection, config, selector, None, profile)
    return {"profile": profile, "source_digest": selector.source_digest,
            "packet_digest": selector.packet_digest,
            "request_digest": content_digest(envelope.request),
            "schema_digest": envelope.schema_digest,
            "input_bytes": envelope.input_bytes,
            "estimated_total_tokens": envelope.estimated_total_tokens,
            "qualification": "Selector preparation only; no model context-fit qualification."}


def replay_category_results(artifact: CategoryArtifact) -> CategoryAnswer | None:
    """Rebuild every preparation, request, check and displayed card from saved source."""
    if artifact.profile not in _PROFILE_INSTRUCTIONS or \
            artifact.selector_settings != _SETTINGS or \
            artifact.composer_settings != _composer_settings(artifact.profile) or \
            artifact.correction_settings != _SETTINGS:
        raise ValueError("saved category profile/settings differ")
    projection = SolutionProjection.model_validate(artifact.evidence.source.model_dump(mode="json"))
    evidence = resolve_workspace(projection, fx_acquisition=artifact.evidence.fx_acquisition)
    if evidence != artifact.evidence:
        raise ValueError("saved category source differs")
    selector = prepare_focused_selector(projection, artifact.config, evidence,
                                        selection_format=_selection_format(artifact.profile, projection))
    if artifact.selector_prepared != selector or not 1 <= len(artifact.passes) <= 3:
        raise ValueError("saved category selector or pass count differs")
    first = artifact.passes[0]
    if first.phase != "selection":
        raise ValueError("saved category first phase differs")
    _replay_pass(first, _requests(projection, artifact.config, selector, None, artifact.profile),
        artifact.config, lambda raw: _decode_selection(raw, selector, projection,
                                                      artifact.profile),
        projection, selector)
    focus = None
    selection_findings: tuple[CheckFinding, ...] = ()
    if first.outcome == "recoverable":
        assert first.selection is not None and first.raw_wire is not None
        selection_findings = _selection_findings(first.raw_wire, first.selection,
                                                projection, artifact.profile)
        focus = _focus(first.selection, selector, projection, evidence,
                       profile=artifact.profile)
        if len(artifact.passes) < 2 or artifact.passes[1].phase != "composition":
            raise ValueError("saved category composition is missing")
        _replay_pass(artifact.passes[1], _requests(projection, artifact.config, selector,
            focus, artifact.profile), artifact.config,
            lambda raw: decode_document(raw, focus, projection), projection, focus,
            checker=_checker(artifact.profile))
        failures = tuple(f for f in artifact.passes[1].findings if f.outcome == "failed")
        if len(artifact.passes) == 3:
            if not failures or artifact.passes[1].outcome != "recoverable" or \
                    artifact.passes[2].phase != "correction" or \
                    artifact.passes[1].raw_wire is None:
                raise ValueError("saved category correction trigger differs")
            _replay_pass(artifact.passes[2], _requests(projection, artifact.config,
                selector, focus, artifact.profile,
                previous_wire=artifact.passes[1].raw_wire, feedback=failures),
                artifact.config, lambda raw: decode_document(raw, focus, projection),
                projection, focus, checker=_checker(artifact.profile))
        elif failures and artifact.passes[1].outcome == "recoverable":
            raise ValueError("saved category correction is missing")
    elif len(artifact.passes) != 1:
        raise ValueError("saved category authoring follows failed selection")
    if artifact.focus_prepared != focus or artifact.selection_findings != selection_findings:
        raise ValueError("saved category preparation or selection audit differs")
    recoverable = tuple((index - 1, item.findings) for index, item in enumerate(artifact.passes)
                        if index >= 1 and item.outcome == "recoverable" and item.document is not None)
    chosen = (choose_recoverable(recoverable)[0] + 1 if recoverable else None)
    chosen_index = chosen if chosen is not None else 0
    resolved = (_answer(cast(StructuredDocument, artifact.passes[chosen_index].document),
                        cast(InteractivePreparedInput, focus), evidence,
                        artifact.passes[chosen_index].findings, selection_findings)
                if chosen is not None else None)
    terminal = artifact.passes[-1]
    validation = ("unavailable" if resolved is None else
                  "annotated" if any(f.outcome == "failed" for f in selection_findings) or any(f.outcome == "failed" for f in
                  artifact.passes[chosen_index].findings) else "clean")
    if (artifact.selected_pass_index != chosen or artifact.resolved != resolved or
            artifact.resolved_digest != (content_digest(resolved.model_dump(mode="json"))
                                         if resolved else None) or
            artifact.validation_outcome != validation or
            artifact.delivery_outcome != ("delivered" if resolved else "not_delivered") or
            artifact.generation_outcome != ("success" if resolved else terminal.outcome)):
        raise ValueError("saved category outcome differs")
    return resolved


def parse_category_artifact(raw: bytes | str) -> CategoryArtifact:
    value = json.loads(raw)
    if value.get("contract_version") != "results-category-artifact-v1":
        raise ValueError("unknown category artifact contract")
    return CategoryArtifact.model_validate(value)
