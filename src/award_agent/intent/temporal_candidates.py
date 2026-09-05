"""Finite, local temporal candidates produced from raw-text temporal facts.

Candidates are deliberately not a temporal graph wire format.  They name only local facts and
selection dependencies; the compiler owns canonical relation construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, cast

from award_agent.domain import TemporalTarget
from award_agent.intent.temporal_lexing import DurationLiteral, LiteralAnchor, TemporalScan


class AnchorUseMode(str, Enum):
    DIRECT_WINDOW = "direct_window"
    REFERENCE_ONLY = "reference_only"
    UNRESOLVED_SUPPORT = "unresolved_support"


@dataclass(frozen=True)
class AnchorUse:
    handle: str
    mode: AnchorUseMode


class CandidateRelation(str, Enum):
    HOLIDAY_WEEKEND = "holiday_weekend"
    CHRISTMAS_PERIOD = "christmas_period"
    EXACT_DATE = "exact_date"
    MONTH_PORTION = "month_portion"
    RELATIVE_CALENDAR_PERIOD = "relative_calendar_period"
    DURATION = "duration"
    RELATIVE_WEEKEND_AFTER_ANCHOR = "relative_weekend_after_anchor"
    RETURN_WEEKEND_AFTER_DEPARTURE = "return_weekend_after_departure"
    EXTEND_DEPARTURE_TO_THURSDAY = "extend_departure_to_thursday"
    UNBOUNDED_AFTER = "unbounded_after"
    UNBOUNDED_BEFORE = "unbounded_before"
    UNRESOLVED = "unresolved"


class CandidateComposition(str, Enum):
    EXTEND_START = "extend_start"


@dataclass(frozen=True)
class TemporalCandidate:
    handle: str
    exclusive_group: str
    covers: tuple[str, ...]
    requires: tuple[str, ...]
    produces: tuple[str, ...]
    priority: int
    anchor_uses: tuple[AnchorUse, ...]
    relation: CandidateRelation
    composition: CandidateComposition | None = None
    # A composition is deliberately bound to one request-local production slot.  It is not
    # inferred from whatever departure decision happened to compile most recently.
    composition_operand: str | None = None
    target: TemporalTarget | None = None
    clause_handle: str | None = None
    ordinal: int = 1
    duration: DurationLiteral | None = None
    reason: str | None = None


@dataclass(frozen=True)
class TemporalCandidateCatalog:
    scan: TemporalScan
    candidates: tuple[TemporalCandidate, ...]

    def by_handle(self, handle: str) -> TemporalCandidate:
        for candidate in self.candidates:
            if candidate.handle == handle:
                return candidate
        raise KeyError(handle)


def _anchor(scan: TemporalScan, kind: str) -> LiteralAnchor | None:
    return next((anchor for anchor in scan.anchors if anchor.kind == kind), None)


def build_temporal_candidates(scan: TemporalScan) -> TemporalCandidateCatalog:
    """Create deterministic candidates for the initial supported grammar.

    Every semantic group has exactly one chosen candidate in this first slice.  The data shape
    keeps an unresolved alternative so a later selector can choose it for genuinely ambiguous
    future grammar without authoring graph fields.
    """

    candidates: list[TemporalCandidate] = []

    def add(**kwargs: object) -> None:
        """Use meaningful local IDs so frozen selector fixtures do not depend on list order."""

        values = cast(dict[str, Any], kwargs)
        relation = cast(CandidateRelation, values["relation"])
        target = cast(TemporalTarget | None, values.get("target"))
        clause_handle = cast(str | None, values.get("clause_handle"))
        clause_text = next(
            (item.text for item in scan.clauses if item.handle == clause_handle), "request"
        )
        semantic_clause = re.sub(r"[^a-z0-9]+", "-", clause_text.casefold()).strip("-")
        base = f"{relation.value}:{target.value if target else 'none'}:{semantic_clause}"
        handle = base
        duplicate = 2
        existing = {candidate.handle for candidate in candidates}
        while handle in existing:
            handle = f"{base}:{duplicate}"
            duplicate += 1
        candidates.append(TemporalCandidate(handle=handle, **values))

    def add_safe_with_unresolved(**kwargs: object) -> None:
        """Give every selectable group a conservative alternative for a future selector."""

        add(**kwargs)
        values = cast(dict[str, Any], kwargs)
        uses = tuple(
            AnchorUse(use.handle, AnchorUseMode.UNRESOLVED_SUPPORT)
            for use in cast(tuple[AnchorUse, ...], values["anchor_uses"])
        )
        add(
            exclusive_group=cast(str, values["exclusive_group"]),
            covers=cast(tuple[str, ...], values["covers"]),
            requires=(),
            produces=(),
            priority=0,
            anchor_uses=uses,
            relation=CandidateRelation.UNRESOLVED,
            target=cast(TemporalTarget | None, values.get("target")),
            clause_handle=cast(str | None, values.get("clause_handle")),
            reason="conservative unresolved alternative",
        )

    def contained_anchor(
        clause_handle: str, *, holiday: str | None = None, kind: str | None = None
    ) -> LiteralAnchor | None:
        clause = next(item for item in scan.clauses if item.handle == clause_handle)
        return next(
            (
                anchor
                for anchor in scan.anchors
                if anchor.clause.start >= clause.start
                and anchor.clause.end <= clause.end
                and (holiday is None or (anchor.holiday and anchor.holiday.value == holiday))
                and (kind is None or anchor.kind == kind)
            ),
            None,
        )

    for clause in scan.clauses:
        group = f"g:{clause.handle}"
        if clause.kind == "holiday_weekend":
            labor = contained_anchor(clause.handle, holiday="labor_day")
            if labor is None:
                continue
            add_safe_with_unresolved(
                exclusive_group=group,
                covers=(clause.handle,),
                requires=(),
                produces=("departure",),
                priority=100,
                anchor_uses=(AnchorUse(labor.handle, AnchorUseMode.DIRECT_WINDOW),),
                relation=CandidateRelation.HOLIDAY_WEEKEND,
                target=TemporalTarget.DEPARTURE,
                clause_handle=clause.handle,
            )
        elif clause.kind == "christmas_period":
            christmas = contained_anchor(clause.handle, holiday="christmas")
            if christmas:
                add_safe_with_unresolved(
                    exclusive_group=group,
                    covers=(clause.handle,),
                    requires=(),
                    produces=("departure",),
                    priority=100,
                    anchor_uses=(AnchorUse(christmas.handle, AnchorUseMode.DIRECT_WINDOW),),
                    relation=CandidateRelation.CHRISTMAS_PERIOD,
                    target=TemporalTarget.DEPARTURE,
                    clause_handle=clause.handle,
                )
        elif clause.kind == "thursday_extension":
            # This composition refers to the selected departure decision, not a holiday
            # anchor.  In particular, do not borrow the first Labor Day anchor in a request
            # merely to decorate a separate "Thursday as well" clause.
            add_safe_with_unresolved(
                exclusive_group=group,
                covers=(clause.handle,),
                requires=("departure",),
                produces=("departure",),
                priority=100,
                anchor_uses=(),
                relation=CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY,
                composition=CandidateComposition.EXTEND_START,
                target=TemporalTarget.DEPARTURE,
                clause_handle=clause.handle,
            )
        elif clause.kind == "return_weekend_after":
            add_safe_with_unresolved(
                exclusive_group=group,
                covers=(clause.handle,),
                requires=("departure",),
                produces=("return",),
                priority=100,
                anchor_uses=(),
                relation=CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE,
                target=TemporalTarget.RETURN,
                clause_handle=clause.handle,
            )
        elif clause.kind == "relative_weekend_after_holiday":
            thanksgiving = contained_anchor(clause.handle, holiday="thanksgiving")
            if thanksgiving:
                add_safe_with_unresolved(
                    exclusive_group=group,
                    covers=(clause.handle,),
                    requires=(),
                    produces=("departure",),
                    priority=100,
                    anchor_uses=(AnchorUse(thanksgiving.handle, AnchorUseMode.REFERENCE_ONLY),),
                    relation=CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR,
                    target=TemporalTarget.DEPARTURE,
                    clause_handle=clause.handle,
                    ordinal=2,
                )
        elif clause.kind == "unbounded_after":
            new_year = contained_anchor(clause.handle, holiday="new_years_day")
            if new_year is None:
                continue
            add_safe_with_unresolved(
                exclusive_group=group,
                covers=(clause.handle,),
                requires=(),
                produces=("departure",),
                priority=100,
                anchor_uses=(AnchorUse(new_year.handle, AnchorUseMode.REFERENCE_ONLY),),
                relation=CandidateRelation.UNBOUNDED_AFTER,
                target=TemporalTarget.DEPARTURE,
                clause_handle=clause.handle,
            )
        elif clause.kind == "unbounded_before":
            exact = contained_anchor(clause.handle, kind="exact_date")
            if exact:
                add_safe_with_unresolved(
                    exclusive_group=group,
                    covers=(clause.handle,),
                    requires=(),
                    produces=("return",),
                    priority=100,
                    anchor_uses=(AnchorUse(exact.handle, AnchorUseMode.REFERENCE_ONLY),),
                    relation=CandidateRelation.UNBOUNDED_BEFORE,
                    target=TemporalTarget.RETURN,
                    clause_handle=clause.handle,
                )
        elif clause.kind == "next_month":
            add_safe_with_unresolved(
                exclusive_group=group,
                covers=(clause.handle,),
                requires=(),
                produces=("departure",),
                priority=100,
                anchor_uses=(),
                relation=CandidateRelation.RELATIVE_CALENDAR_PERIOD,
                target=TemporalTarget.DEPARTURE,
                clause_handle=clause.handle,
            )
        elif clause.kind == "early_month":
            month = next(
                (
                    a
                    for a in scan.anchors
                    if a.kind == "month"
                    and a.clause.start >= clause.start
                    and a.clause.end <= clause.end
                ),
                None,
            )
            if month:
                add_safe_with_unresolved(
                    exclusive_group=group,
                    covers=(clause.handle,),
                    requires=(),
                    produces=(month.target.value,),
                    priority=100,
                    anchor_uses=(AnchorUse(month.handle, AnchorUseMode.DIRECT_WINDOW),),
                    relation=CandidateRelation.MONTH_PORTION,
                    target=month.target,
                    clause_handle=clause.handle,
                    reason="early",
                )
        elif clause.kind == "unsupported":
            # An unsupported clause may only retain an anchor that it literally
            # contains.  A later unrelated month must never make "first week"
            # look grounded or change its scope.
            support = contained_anchor(clause.handle, kind="month")
            uses = (
                ()
                if support is None
                else (AnchorUse(support.handle, AnchorUseMode.UNRESOLVED_SUPPORT),)
            )
            add(
                exclusive_group=group,
                covers=(clause.handle,),
                requires=(),
                produces=(),
                priority=100,
                anchor_uses=uses,
                relation=CandidateRelation.UNRESOLVED,
                target=TemporalTarget.DEPARTURE,
                clause_handle=clause.handle,
                reason="unsupported temporal grammar",
            )

    for anchor in scan.anchors:
        # Anchors already consumed as a direct/reference semantic component are not independently
        # made direct windows.  This is the key scope distinction of this design.
        used = {use.handle for candidate in candidates for use in candidate.anchor_uses}
        if anchor.handle in used:
            continue
        group = f"g:{anchor.clause.handle}"
        if anchor.kind == "exact_date":
            add_safe_with_unresolved(
                exclusive_group=group,
                covers=(anchor.clause.handle,),
                requires=(),
                produces=(anchor.target.value,),
                priority=100,
                anchor_uses=(AnchorUse(anchor.handle, AnchorUseMode.DIRECT_WINDOW),),
                relation=CandidateRelation.EXACT_DATE,
                target=anchor.target,
                clause_handle=anchor.clause.handle,
            )
        elif anchor.kind == "month":
            # Keep first-week wording unresolved even though a month anchor was harvested.
            if any(
                c.kind == "unsupported"
                and c.start <= anchor.clause.start
                and c.end >= anchor.clause.end
                for c in scan.clauses
            ):
                continue
            add_safe_with_unresolved(
                exclusive_group=group,
                covers=(anchor.clause.handle,),
                requires=(),
                produces=(anchor.target.value,),
                priority=100,
                anchor_uses=(AnchorUse(anchor.handle, AnchorUseMode.DIRECT_WINDOW),),
                relation=CandidateRelation.MONTH_PORTION,
                target=anchor.target,
                clause_handle=anchor.clause.handle,
                reason="whole",
            )

    for duration in scan.durations:
        add_safe_with_unresolved(
            exclusive_group=f"g:{duration.clause.handle}",
            covers=(duration.clause.handle,),
            requires=(),
            produces=("duration",),
            priority=100,
            anchor_uses=(),
            relation=CandidateRelation.DURATION,
            target=TemporalTarget.RETURN,
            clause_handle=duration.clause.handle,
            duration=duration,
        )
    return TemporalCandidateCatalog(scan, _assign_production_slots(candidates))


def _assign_production_slots(
    candidates: list[TemporalCandidate],
) -> tuple[TemporalCandidate, ...]:
    """Replace endpoint labels with private request-local production slots.

    Candidates in alternate branches of one exclusive group intentionally share a slot: exactly
    one branch can be selected, so that slot still has one selected producer.  Dependents bind
    only when the grammar has one compatible upstream producer.  This is purposefully independent
    of source order; a phrase such as "Thursday as well, Labor Day weekend" must not acquire a
    meaning from a mutable "last departure" variable.
    """

    supported = [item for item in candidates if item.relation is not CandidateRelation.UNRESOLVED]
    slots_by_group: dict[str, str] = {}
    for item in supported:
        if item.produces:
            slots_by_group.setdefault(item.exclusive_group, f"slot:{len(slots_by_group)}")

    normalized: list[TemporalCandidate] = []
    for item in candidates:
        if item.relation is CandidateRelation.UNRESOLVED or not item.produces:
            normalized.append(replace(item, requires=(), produces=(), composition_operand=None))
            continue
        normalized.append(
            replace(item, requires=(), produces=(slots_by_group[item.exclusive_group],))
        )

    # Only these relation forms have grammar that names another local endpoint fact.  There is no
    # generic "requires departure" fallback, because that would reintroduce order-dependent
    # target binding when multiple departure clauses occur in one request.
    bound: list[TemporalCandidate] = []
    for item in normalized:
        if item.relation not in {
            CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY,
            CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE,
        }:
            bound.append(item)
            continue
        operand_target = TemporalTarget.DEPARTURE
        compatible = [
            other
            for other in normalized
            if other is not item
            and other.relation is not CandidateRelation.UNRESOLVED
            and other.composition is None
            and other.target is operand_target
            and other.produces
        ]
        # Alternatives within one group are one logical producer.  More than one distinct slot
        # is genuine ambiguity, and this bounded grammar leaves the dependent phrase unresolved.
        operand_slots = {other.produces[0] for other in compatible}
        if len(operand_slots) != 1:
            # Do not leave an invalid supported candidate in the group; its pre-created unresolved
            # companion is the sole conservative option.
            continue
        operand = next(iter(operand_slots))
        bound.append(
            replace(
                item,
                requires=(operand,),
                composition_operand=(operand if item.composition is not None else None),
            )
        )
    return tuple(bound)


def auto_select_candidates(catalog: TemporalCandidateCatalog) -> tuple[str, ...]:
    """Return the sole safe candidate from every currently-supported local group."""

    groups: dict[str, list[TemporalCandidate]] = {}
    for candidate in catalog.candidates:
        groups.setdefault(candidate.exclusive_group, []).append(candidate)
    return tuple(max(items, key=lambda item: item.priority).handle for items in groups.values())
