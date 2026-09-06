"""Planning and date-free views for temporal-candidate selection.

The selector never authors temporal graph fields.  It receives only request-local opaque
handles for pre-built alternatives and returns a subset of those handles.  This module owns the
private restoration map and rejects invalid output before the compiler sees it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from award_agent.intent.model_views import (
    TemporalSelectorAnchor,
    TemporalSelectorAnchorUse,
    TemporalSelectorCandidate,
    TemporalSelectorEvidence,
    TemporalSelectorGroup,
    TemporalSelectorInput,
    TemporalSelectorOutput,
)
from award_agent.intent.temporal_candidates import (
    CandidateRelation,
    TemporalCandidate,
    TemporalCandidateCatalog,
)
from award_agent.intent.temporal_compiler import (
    TemporalCandidateValidationError,
    validate_candidate_catalog,
)


class TemporalSelectorValidationError(ValueError):
    """A model selection did not choose exactly the published local candidates."""


TemporalSelectorPolicy = Literal["ambiguous_only", "supported_or_unresolved"]
# The low-level default preserves frozen fixture compatibility. The selector-only workflow passes
# ``supported_or_unresolved`` explicitly, so the production path has no policy switch.
DEFAULT_TEMPORAL_SELECTOR_POLICY: TemporalSelectorPolicy = "ambiguous_only"


@dataclass(frozen=True)
class TemporalSelectionPlan:
    """Which catalog groups are deterministic and which need an optional selector."""

    auto_selected: tuple[str, ...]
    selector_groups: tuple[str, ...]


def _grouped(catalog: TemporalCandidateCatalog) -> dict[str, tuple[TemporalCandidate, ...]]:
    groups: dict[str, list[TemporalCandidate]] = {}
    for candidate in catalog.candidates:
        groups.setdefault(candidate.exclusive_group, []).append(candidate)
    return {handle: tuple(candidates) for handle, candidates in groups.items()}


def _unresolved_candidate(candidates: Sequence[TemporalCandidate]) -> TemporalCandidate:
    unresolved = [item for item in candidates if item.relation is CandidateRelation.UNRESOLVED]
    if len(unresolved) != 1:
        raise TemporalSelectorValidationError(
            "every non-deterministic candidate group must contain exactly one unresolved choice"
        )
    return unresolved[0]


def _validate_catalog_for_selector(catalog: TemporalCandidateCatalog) -> None:
    """Translate structural catalog validation into the selector-boundary error type."""

    try:
        validate_candidate_catalog(catalog)
    except TemporalCandidateValidationError as exc:
        raise TemporalSelectorValidationError(str(exc)) from exc


def plan_temporal_selection(
    catalog: TemporalCandidateCatalog,
    *,
    policy: TemporalSelectorPolicy = DEFAULT_TEMPORAL_SELECTOR_POLICY,
) -> TemporalSelectionPlan:
    """Partition a catalog without treating priority as model-facing semantic policy.

    ``supported_or_unresolved`` is the selector-only workflow policy: the selector chooses
    between every supported interpretation and its explicit unresolved alternative.
    ``ambiguous_only`` remains available for frozen historical fixture analysis. Groups with no
    supported option remain deterministically unresolved under either policy.

    Groups that consume a value whose availability depends on a selector group join the selector
    view too, allowing it to select their explicit unresolved alternative.
    """

    if policy not in {"ambiguous_only", "supported_or_unresolved"}:
        raise ValueError(f"unsupported temporal selector policy: {policy}")

    # Validate every alternative before partitioning.  In particular, an unselected manual
    # distractor must never become public selector input merely because another branch is safe.
    _validate_catalog_for_selector(catalog)
    groups = _grouped(catalog)
    selector_groups: set[str] = set()
    deterministic: dict[str, TemporalCandidate] = {}
    for group, candidates in groups.items():
        supported = [
            item for item in candidates if item.relation is not CandidateRelation.UNRESOLVED
        ]
        if len(supported) == 0:
            deterministic[group] = _unresolved_candidate(candidates)
        elif len(supported) == 1:
            if policy == "supported_or_unresolved":
                _unresolved_candidate(candidates)
                selector_groups.add(group)
            else:
                deterministic[group] = supported[0]
        else:
            _unresolved_candidate(candidates)
            selector_groups.add(group)

    # A deterministic dependent candidate is not actually unconditional if an upstream selector
    # group might choose unresolved.  Promote it, then repeat for its own dependents.
    changed = True
    while changed:
        changed = False
        possible_selector_productions = {
            value
            for group in selector_groups
            for candidate in groups[group]
            if candidate.relation is not CandidateRelation.UNRESOLVED
            for value in candidate.produces
        }
        for group, candidate in tuple(deterministic.items()):
            if set(candidate.requires) & possible_selector_productions:
                _unresolved_candidate(groups[group])
                del deterministic[group]
                selector_groups.add(group)
                changed = True

    # Preserve catalog order rather than exposing an incidental set iteration order.
    return TemporalSelectionPlan(
        auto_selected=tuple(
            candidate.handle
            for group, candidates in groups.items()
            for candidate in candidates
            if deterministic.get(group) is candidate
        ),
        selector_groups=tuple(group for group in groups if group in selector_groups),
    )


def unresolved_selection(
    catalog: TemporalCandidateCatalog,
    plan: TemporalSelectionPlan,
) -> tuple[str, ...]:
    """Choose conservative unresolved alternatives when no selector is configured."""

    groups = _grouped(catalog)
    return tuple(_unresolved_candidate(groups[group]).handle for group in plan.selector_groups)


_ENDPOINT_TOKEN = re.compile(r"\b(?:leave|leaving|left|depart|departs|departing|departure|return|returns|returning|returned|back)\b", re.IGNORECASE)


def _endpoint_cue(
    request_text: str,
    *,
    start: int,
    end: int,
) -> Literal["departure", "return", "unspecified"]:
    """Expose only explicit endpoint tokens from the clause's local sentence.

    The scanner's private target default is deliberately not consulted. A literal may omit the
    endpoint word itself (for example, ``October 5`` in ``Leave October 5``), so the sentence
    surrounding that literal is the bounded local source for the cue.
    """

    departures = 0
    returns = 0
    left = max(
        request_text.rfind(".", 0, start),
        request_text.rfind("!", 0, start),
        request_text.rfind("?", 0, start),
        request_text.rfind(";", 0, start),
    ) + 1
    right_candidates = [
        position
        for marker in ".!?;"
        if (position := request_text.find(marker, end)) >= 0
    ]
    right = min(right_candidates) if right_candidates else len(request_text)
    for match in _ENDPOINT_TOKEN.finditer(request_text[left:right]):
        token = match.group(0).lower()
        if token in {"leave", "leaving", "left", "depart", "departs", "departing", "departure"}:
            departures += 1
        else:
            returns += 1
    if departures and not returns:
        return "departure"
    if returns and not departures:
        return "return"
    return "unspecified"


def _interpretation_kind(candidate: TemporalCandidate) -> str:
    """Map private compiler enums to a stable, date-free selector vocabulary."""

    kinds = {
        CandidateRelation.UNRESOLVED: "unresolved",
        CandidateRelation.HOLIDAY_WEEKEND: "holiday_weekend",
        CandidateRelation.CHRISTMAS_PERIOD: "christmas_period",
        CandidateRelation.EXACT_DATE: "exact_date_anchor",
        CandidateRelation.MONTH_PORTION: "named_month_portion",
        CandidateRelation.RELATIVE_CALENDAR_PERIOD: "relative_calendar_period",
        CandidateRelation.DURATION: "trip_duration",
        CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR: "weekend_after_anchor",
        CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE: "return_weekend_after_departure",
        CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY: "extend_departure_start_to_thursday",
        CandidateRelation.UNBOUNDED_AFTER: "after_anchor_boundary",
        CandidateRelation.UNBOUNDED_BEFORE: "before_anchor_boundary",
    }
    return kinds[candidate.relation]


def _relation_ordinal(candidate: TemporalCandidate) -> int | None:
    """Publish only ordinals that distinguish a selector-visible relation."""

    if candidate.relation in {
        CandidateRelation.RELATIVE_CALENDAR_PERIOD,
        CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR,
        CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE,
    }:
        return candidate.ordinal
    return None


def _ordinal_label(value: int) -> str:
    suffix = "th" if 10 < value % 100 < 14 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _candidate_summary(
    candidate: TemporalCandidate,
    *,
    evidence: tuple[str, ...],
    anchors: tuple[TemporalSelectorAnchorUse, ...],
    composition_operand: str | None,
) -> str:
    """Describe the complete public choice without leaking compiler identities or dates."""

    evidence_text = ", ".join(evidence) if evidence else "the supplied local wording"
    target = candidate.target.value if candidate.target is not None else "unspecified"
    kind = _interpretation_kind(candidate)
    if kind == "unresolved":
        return f"Keep {evidence_text} unresolved; do not infer a date, endpoint, or relation."
    anchor_text = ", ".join(f"{use.anchor} ({use.mode})" for use in anchors)
    if kind == "extend_departure_start_to_thursday":
        return (
            f"Interpret {evidence_text} as extending the start of {composition_operand} to Thursday "
            "for departure."
        )
    if kind == "weekend_after_anchor":
        return (
            f"Interpret {evidence_text} as the {_ordinal_label(_relation_ordinal(candidate) or 1)} weekend after "
            f"{anchor_text} for {target}."
        )
    if kind == "return_weekend_after_departure":
        return (
            f"Interpret {evidence_text} as the {_ordinal_label(_relation_ordinal(candidate) or 1)} return weekend "
            "after the required departure production."
        )
    if kind == "after_anchor_boundary":
        return f"Interpret {evidence_text} as an unbounded after-{anchor_text} boundary for {target}."
    if kind == "before_anchor_boundary":
        return f"Interpret {evidence_text} as an unbounded before-{anchor_text} boundary for {target}."
    if kind == "relative_calendar_period":
        return (
            f"Interpret {evidence_text} as the {_ordinal_label(_relation_ordinal(candidate) or 1)} supplied relative "
            f"calendar period for {target}."
        )
    if kind == "trip_duration":
        # A duration's ordinal is an implementation default, not its literal meaning.  Keep the
        # public description faithful to the scanner's stated quantity range, unit, and modifier
        # so the selector never has to guess whether (for example) "about 10 days" is ten days
        # or a generic one-unit duration.
        assert candidate.duration is not None
        duration = candidate.duration
        quantity = (
            str(duration.minimum)
            if duration.minimum == duration.maximum
            else f"{duration.minimum} to {duration.maximum}"
        )
        unit = duration.unit.value
        display_unit = unit if duration.minimum == duration.maximum == 1 else f"{unit}s"
        return (
            f"Interpret {evidence_text} as a trip duration stated as {duration.modifier.value} "
            f"{quantity} {display_unit} (minimum {duration.minimum}, maximum {duration.maximum}; "
            f"unit {unit}). A trip duration is trip length, not a departure or return endpoint "
            "assertion."
        )
    return f"Interpret {evidence_text} as {kind} for {target} using {anchor_text or 'no anchor'}."


def _v1_candidate_summary(candidate: TemporalCandidate) -> str:
    """Retain the original frozen-study projection for historical v1 fixture preflight."""

    if candidate.relation is CandidateRelation.UNRESOLVED:
        return "Leave this temporal wording unresolved for clarification."
    target = candidate.target.value if candidate.target is not None else "unspecified"
    descriptions = {
        CandidateRelation.HOLIDAY_WEEKEND: "Use the supplied holiday-weekend interpretation.",
        CandidateRelation.CHRISTMAS_PERIOD: "Use the supplied Christmas-period interpretation.",
        CandidateRelation.EXACT_DATE: "Use the supplied exact-date interpretation.",
        CandidateRelation.MONTH_PORTION: "Use the supplied named-month interpretation.",
        CandidateRelation.RELATIVE_CALENDAR_PERIOD: "Use the supplied relative-calendar interpretation.",
        CandidateRelation.DURATION: "Use the supplied trip-duration interpretation.",
        CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR: (
            "Use the supplied weekend-after-reference interpretation."
        ),
        CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE: (
            "Use the supplied return-weekend-after-departure interpretation."
        ),
        CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY: (
            "Extend the supplied departure interpretation to include Thursday."
        ),
        CandidateRelation.UNBOUNDED_AFTER: "Use the supplied after-reference boundary.",
        CandidateRelation.UNBOUNDED_BEFORE: "Use the supplied before-reference boundary.",
    }
    return f"{descriptions[candidate.relation]} It contributes to {target}."


def build_temporal_selector_input(
    catalog: TemporalCandidateCatalog,
    plan: TemporalSelectionPlan,
    *,
    contract_version: Literal["v1", "v2"] = "v2",
) -> TemporalSelectorInput:
    """Project ambiguous local choices into the public, date-free selector contract."""

    # Callers may supply a hand-built plan, so projection has its own preflight rather than
    # trusting that ``plan_temporal_selection`` ran first.
    _validate_catalog_for_selector(catalog)
    groups = _grouped(catalog)
    selected_groups = [groups[group] for group in plan.selector_groups]
    selected_candidates = [candidate for group in selected_groups for candidate in group]
    candidate_covers = {
        clause_handle for candidate in selected_candidates for clause_handle in candidate.covers
    }
    candidate_anchor_uses = {
        use.handle for candidate in selected_candidates for use in candidate.anchor_uses
    }
    # An anchor can be a reference for an interpretation whose ``covers`` only names the
    # principal clause.  Publish that anchor's literal clause as well: otherwise the public
    # anchor would reference an evidence handle that was never assigned.  Order evidence by
    # its raw-text position *before* assigning opaque handles, rather than relying on the
    # scanner's grouped harvesting passes.
    selected_anchor_clauses = {
        anchor.clause.handle
        for anchor in catalog.scan.anchors
        if anchor.handle in candidate_anchor_uses
    }
    selected_clause_handles = candidate_covers | selected_anchor_clauses

    clauses = sorted(
        (clause for clause in catalog.scan.clauses if clause.handle in selected_clause_handles),
        key=lambda clause: (clause.start, clause.end, clause.handle),
    )
    anchors = sorted(
        (anchor for anchor in catalog.scan.anchors if anchor.handle in candidate_anchor_uses),
        key=lambda anchor: (anchor.clause.start, anchor.clause.end, anchor.handle),
    )
    evidence_public = {clause.handle: f"e{index}" for index, clause in enumerate(clauses)}
    anchor_public = {anchor.handle: f"a{index}" for index, anchor in enumerate(anchors)}
    group_public = {group: f"g{index}" for index, group in enumerate(plan.selector_groups)}
    candidate_public = {
        candidate.handle: f"c{index}" for index, candidate in enumerate(selected_candidates)
    }
    # Production slots are compiler-private identities.  The selector sees only stable request
    # local pN labels; neither endpoint names nor canonical constraint IDs cross this boundary.
    all_slots = [
        slot
        for handle in (
            *plan.auto_selected,
            *(candidate.handle for candidate in selected_candidates),
        )
        for slot in catalog.by_handle(handle).produces
    ]
    slot_public = {slot: f"p{index}" for index, slot in enumerate(dict.fromkeys(all_slots))}

    def public_candidate(candidate: TemporalCandidate) -> TemporalSelectorCandidate:
        public_anchor_uses = tuple(
            TemporalSelectorAnchorUse(anchor=anchor_public[use.handle], mode=use.mode.value)
            for use in candidate.anchor_uses
        )
        public_covers = tuple(evidence_public[handle] for handle in candidate.covers)
        public_operand = (
            slot_public[candidate.composition_operand]
            if candidate.composition_operand is not None
            else None
        )
        return TemporalSelectorCandidate(
            handle=candidate_public[candidate.handle],
            summary=(
                _candidate_summary(
                    candidate,
                    evidence=public_covers,
                    anchors=public_anchor_uses,
                    composition_operand=public_operand,
                )
                if contract_version == "v2"
                else _v1_candidate_summary(candidate)
            ),
            interpretation_kind=(
                _interpretation_kind(candidate) if contract_version == "v2" else None
            ),
            relation_ordinal=(
                _relation_ordinal(candidate) if contract_version == "v2" else None
            ),
            target=candidate.target.value if candidate.target is not None else None,
            covers=public_covers,
            requires=tuple(slot_public[slot] for slot in candidate.requires),
            produces=tuple(slot_public[slot] for slot in candidate.produces),
            anchor_uses=public_anchor_uses,
            composition=(
                candidate.composition.value if candidate.composition is not None else None
            ),
            composition_operand=(
                slot_public[candidate.composition_operand]
                if candidate.composition_operand is not None
                else None
            ),
        )

    model_input = TemporalSelectorInput(
        ordered_evidence=tuple(
            TemporalSelectorEvidence(
                handle=evidence_public[clause.handle],
                text=clause.text,
                endpoint_cue=(
                    (
                        # A scanner-admitted duration is trip length.  Nearby ``leave`` or
                        # ``return`` wording can describe a separate endpoint in the same
                        # sentence, so it must not turn duration evidence into an endpoint
                        # assertion.
                        "unspecified"
                        if clause.kind == "duration"
                        else _endpoint_cue(
                            catalog.scan.request_text, start=clause.start, end=clause.end
                        )
                    )
                    if contract_version == "v2"
                    else None
                ),
            )
            for clause in clauses
        ),
        local_anchors=tuple(
            TemporalSelectorAnchor(
                handle=anchor_public[anchor.handle],
                evidence=evidence_public[anchor.clause.handle],
                kind=anchor.kind,
            )
            for anchor in anchors
        ),
        available_productions=tuple(
            slot_public[production]
            for handle in plan.auto_selected
            for production in catalog.by_handle(handle).produces
        ),
        candidate_groups=tuple(
            TemporalSelectorGroup(
                handle=group_public[group],
                candidates=tuple(public_candidate(candidate) for candidate in groups[group]),
            )
            for group in plan.selector_groups
        ),
    )
    model_input._candidate_handles = {
        public: internal for internal, public in candidate_public.items()
    }
    model_input._group_handles = {public: internal for internal, public in group_public.items()}
    model_input._evidence_handles = {
        public: internal for internal, public in evidence_public.items()
    }
    model_input._anchor_handles = {public: internal for internal, public in anchor_public.items()}
    model_input._production_slots = {public: internal for internal, public in slot_public.items()}
    return model_input


def restore_selector_output(
    model_input: TemporalSelectorInput,
    selector_output: TemporalSelectorOutput,
) -> tuple[str, ...]:
    """Validate public output and restore private internal candidate handles."""

    selected = selector_output.selected_candidates
    if len(selected) != len(set(selected)):
        raise TemporalSelectorValidationError(
            "selector output contains duplicate candidate handles"
        )
    unknown = [handle for handle in selected if handle not in model_input._candidate_handles]
    if unknown:
        raise TemporalSelectorValidationError(
            "selector output contains an unknown candidate handle"
        )

    groups_by_candidate = {
        candidate.handle: group.handle
        for group in model_input.candidate_groups
        for candidate in group.candidates
    }
    selected_groups: dict[str, str] = {}
    for handle in selected:
        group = groups_by_candidate[handle]
        if group in selected_groups:
            raise TemporalSelectorValidationError(
                "selector output chooses multiple candidates from one group"
            )
        selected_groups[group] = handle
    expected_groups = {group.handle for group in model_input.candidate_groups}
    if set(selected_groups) != expected_groups:
        raise TemporalSelectorValidationError(
            "selector output does not cover every candidate group"
        )
    return tuple(model_input._candidate_handles[handle] for handle in selected)
