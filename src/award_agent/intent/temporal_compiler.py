"""Direct deterministic compilation of local temporal candidates to canonical relations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from itertools import product
from typing import Literal, cast

from award_agent.domain import (
    AnchorReference,
    AnchorWindowConstraint,
    CalendarPeriodSemantics,
    CoarseIntentExtraction,
    DateResolutionProposal,
    DateWindow,
    DecisionReference,
    DurationReferenceScope,
    Holiday,
    MonthPortionConstraint,
    RawRequest,
    RelativeCalendarPeriodConstraint,
    RelativeWeekdayConstraint,
    RelativeWeekendConstraint,
    RequestFieldReference,
    ResolvedTemporalAnchor,
    SemanticDurationConstraint,
    SymbolicContextReference,
    TemporalComposition,
    TemporalConstraint,
    TemporalDirection,
    TemporalEdge,
    TemporalRelationGraph,
    TemporalTarget,
    TemporalUnit,
    UnboundedBoundaryConstraint,
    UnresolvedRelationConstraint,
    UnresolvedTemporalConstraint,
    Weekday,
)
from award_agent.intent.holidays import HolidayDateProvider
from award_agent.intent.temporal import (
    enrich_temporal_anchors,
    evaluate_temporal_relation_graph,
    proposal_window_to_date_window,
)
from award_agent.intent.temporal_candidates import (
    AnchorUseMode,
    CandidateComposition,
    CandidateRelation,
    TemporalCandidate,
    TemporalCandidateCatalog,
)
from award_agent.intent.temporal_lexing import DurationLiteral


class TemporalCandidateValidationError(ValueError):
    """A selected local candidate set is inconsistent before graph construction."""


@dataclass(frozen=True)
class CompiledTemporalIntent:
    """The only temporal assembly input intended for the future workflow boundary."""

    extraction: CoarseIntentExtraction
    graph: TemporalRelationGraph
    resolved_anchors: tuple[ResolvedTemporalAnchor, ...]
    proposal: DateResolutionProposal
    departure_window: DateWindow | None
    return_window: DateWindow | None
    literal_duration: tuple[DurationLiteral, ...]
    unresolved: tuple[UnresolvedTemporalConstraint, ...]
    endpoint_bounds: tuple[CompiledEndpointBound, ...] = ()


@dataclass(frozen=True)
class CompiledEndpointBound:
    """Private strict endpoint bound retained outside the canonical finite-window graph."""

    target: TemporalTarget
    boundary: date
    direction: Literal["before", "after"]


def validate_candidate_selection(
    catalog: TemporalCandidateCatalog,
    selected_handles: Sequence[str],
) -> tuple[TemporalCandidate, ...]:
    """Validate selector output without accepting arbitrary graph fields.

    The checks intentionally happen before evaluation: candidate membership, exactly one choice
    per covered group, availability/selection dependencies, composition target agreement, and
    dependency cycles.
    """

    if len(selected_handles) != len(set(selected_handles)):
        raise TemporalCandidateValidationError("candidate selection contains duplicates")
    available = {candidate.handle: candidate for candidate in catalog.candidates}
    unknown = [handle for handle in selected_handles if handle not in available]
    if unknown:
        raise TemporalCandidateValidationError(f"unknown candidate handle: {unknown[0]}")
    selected = tuple(available[handle] for handle in selected_handles)
    selected_by_group: dict[str, TemporalCandidate] = {}
    for candidate in selected:
        if candidate.exclusive_group in selected_by_group:
            raise TemporalCandidateValidationError(
                f"exclusive group selected twice: {candidate.exclusive_group}"
            )
        selected_by_group[candidate.exclusive_group] = candidate
    required_groups = {candidate.exclusive_group for candidate in catalog.candidates}
    missing = required_groups - set(selected_by_group)
    if missing:
        raise TemporalCandidateValidationError(f"candidate coverage missing: {min(missing)}")

    producers: dict[str, TemporalCandidate] = {}
    for candidate in selected:
        for slot in candidate.produces:
            previous = producers.get(slot)
            if previous is not None:
                raise TemporalCandidateValidationError(
                    f"production slot has multiple selected producers: {slot}"
                )
            producers[slot] = candidate
    for candidate in selected:
        absent = set(candidate.requires) - set(producers)
        if absent:
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} requires unproduced value: {min(absent)}"
            )
        if candidate.composition is not None:
            if candidate.target is None or candidate.composition_operand is None:
                raise TemporalCandidateValidationError(
                    f"composed candidate {candidate.handle} needs an explicit operand"
                )
            if candidate.composition_operand not in candidate.requires:
                raise TemporalCandidateValidationError(
                    f"composed candidate {candidate.handle} operand is not required"
                )
            operand_producer = producers.get(candidate.composition_operand)
            if operand_producer is None:
                raise TemporalCandidateValidationError(
                    f"composed candidate {candidate.handle} has an unproduced operand"
                )
            if operand_producer is candidate or operand_producer.target is not candidate.target:
                raise TemporalCandidateValidationError(
                    f"composed candidate {candidate.handle} has cross-target composition"
                )

        expected_mode = {
            CandidateRelation.HOLIDAY_WEEKEND: AnchorUseMode.DIRECT_WINDOW,
            CandidateRelation.CHRISTMAS_PERIOD: AnchorUseMode.DIRECT_WINDOW,
            CandidateRelation.EXACT_DATE: AnchorUseMode.DIRECT_WINDOW,
            CandidateRelation.MONTH_PORTION: AnchorUseMode.DIRECT_WINDOW,
            CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR: AnchorUseMode.REFERENCE_ONLY,
            CandidateRelation.UNBOUNDED_AFTER: AnchorUseMode.REFERENCE_ONLY,
            CandidateRelation.UNBOUNDED_BEFORE: AnchorUseMode.REFERENCE_ONLY,
            CandidateRelation.UNRESOLVED: AnchorUseMode.UNRESOLVED_SUPPORT,
        }.get(candidate.relation)
        if expected_mode is not None and any(
            use.mode is not expected_mode for use in candidate.anchor_uses
        ):
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} has incompatible anchor scope"
            )
        anchors = {anchor.handle: anchor for anchor in catalog.scan.anchors}
        expected_anchor_kind = {
            CandidateRelation.HOLIDAY_WEEKEND: "holiday",
            CandidateRelation.CHRISTMAS_PERIOD: "holiday",
            CandidateRelation.EXACT_DATE: "exact_date",
            CandidateRelation.MONTH_PORTION: "month",
            CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR: "holiday",
            CandidateRelation.UNBOUNDED_AFTER: "holiday",
            CandidateRelation.UNBOUNDED_BEFORE: "exact_date",
        }.get(candidate.relation)
        if expected_anchor_kind is not None:
            if (
                len(candidate.anchor_uses) != 1
                or anchors.get(candidate.anchor_uses[0].handle) is None
            ):
                raise TemporalCandidateValidationError(
                    f"candidate {candidate.handle} needs one known anchor"
                )
            anchor = anchors[candidate.anchor_uses[0].handle]
            if anchor.kind != expected_anchor_kind or anchor.target is not candidate.target:
                # A reference-only holiday can still name a departure boundary, but must not
                # borrow a return-target anchor or another literal kind.
                raise TemporalCandidateValidationError(
                    f"candidate {candidate.handle} has incompatible anchor binding"
                )

    # Each required slot has exactly one selected producer.  This gives availability dependencies
    # an unambiguous edge and lets the compiler order candidates. Only relation-specific compiler
    # forms turn a requirement into a canonical relation reference.
    graph = {
        candidate.handle: {
            producers[slot].handle
            for slot in candidate.requires
            if producers[slot] is not candidate
        }
        for candidate in selected
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(handle: str) -> None:
        if handle in visiting:
            raise TemporalCandidateValidationError("candidate dependency cycle")
        if handle in visited:
            return
        visiting.add(handle)
        for dependency in graph[handle]:
            visit(dependency)
        visiting.remove(handle)
        visited.add(handle)

    for candidate in selected:
        visit(candidate.handle)
    return selected


def validate_candidate_catalog(catalog: TemporalCandidateCatalog) -> None:
    """Reject a semantically unsafe candidate catalog before selector planning.

    ``validate_candidate_selection`` protects the compiler from one chosen selection.  A
    selector also sees *unselected* alternatives, so catalog construction needs a stricter
    preflight: every alternative must be grounded, locally meaningful, and capable of
    participating in at least one complete selection.  This is structural validation only:
    it remains date-free and does not evaluate calendar arithmetic.
    """

    candidates = catalog.candidates
    if not candidates:
        # A request may have no temporal facts at all.  There is no selector-facing
        # alternative in that case, so an empty scanner catalog is already safe.
        return
    handles = [candidate.handle for candidate in candidates]
    if len(handles) != len(set(handles)):
        raise TemporalCandidateValidationError("candidate catalog contains duplicate handles")

    clauses = {clause.handle: clause for clause in catalog.scan.clauses}
    anchors = {anchor.handle: anchor for anchor in catalog.scan.anchors}
    groups: dict[str, list[TemporalCandidate]] = {}
    supported_by_slot: dict[str, list[TemporalCandidate]] = {}
    for candidate in candidates:
        if not candidate.exclusive_group:
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} has an empty exclusive group"
            )
        if not candidate.covers or len(candidate.covers) != len(set(candidate.covers)):
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} has invalid clause coverage"
            )
        if any(handle not in clauses for handle in candidate.covers):
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} covers an unknown clause"
            )
        if candidate.clause_handle not in clauses or candidate.clause_handle not in candidate.covers:
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} has an ungrounded clause handle"
            )
        if len(candidate.requires) != len(set(candidate.requires)):
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} has duplicate required slots"
            )
        if len(candidate.produces) != len(set(candidate.produces)):
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} has duplicate production slots"
            )
        groups.setdefault(candidate.exclusive_group, []).append(candidate)
        if candidate.relation is not CandidateRelation.UNRESOLVED:
            if candidate.target is None or len(candidate.produces) != 1:
                raise TemporalCandidateValidationError(
                    f"supported candidate {candidate.handle} must target and produce one slot"
                )
            supported_by_slot.setdefault(candidate.produces[0], []).append(candidate)

    for group, choices in groups.items():
        coverage = choices[0].covers
        if any(candidate.covers != coverage for candidate in choices[1:]):
            raise TemporalCandidateValidationError(
                f"candidate group {group} has inconsistent clause coverage"
            )
        unresolved_count = len(
            [candidate for candidate in choices if candidate.relation is CandidateRelation.UNRESOLVED]
        )
        if unresolved_count == 0 and len(choices) == 1:
            # A deterministic base fact need not be exposed as a selectable group.  It is
            # retained in the conservative selection below so dependent alternatives can be
            # checked against a real producer.
            continue
        if unresolved_count != 1:
            raise TemporalCandidateValidationError(
                f"candidate group {group} must contain exactly one unresolved alternative"
            )

    for slot, producers in supported_by_slot.items():
        targets = {candidate.target for candidate in producers}
        if len(targets) != 1:
            raise TemporalCandidateValidationError(
                f"production slot has incompatible producer targets: {slot}"
            )
        producer_groups = {candidate.exclusive_group for candidate in producers}
        if len(producer_groups) != 1:
            raise TemporalCandidateValidationError(
                f"production slot is shared across exclusive groups: {slot}"
            )

    def require_anchor(
        candidate: TemporalCandidate,
        *,
        kind: str,
        mode: AnchorUseMode,
        holiday: Holiday | None = None,
    ) -> None:
        if len(candidate.anchor_uses) != 1:
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} needs one known anchor"
            )
        use = candidate.anchor_uses[0]
        anchor = anchors.get(use.handle)
        if (
            anchor is None
            or use.mode is not mode
            or anchor.kind != kind
            or anchor.target is not candidate.target
            or (holiday is not None and anchor.holiday is not holiday)
        ):
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} has incompatible anchor binding"
            )

    for candidate in candidates:
        relation = candidate.relation
        if relation is not CandidateRelation.DURATION and candidate.duration is not None:
            raise TemporalCandidateValidationError(
                f"non-duration candidate {candidate.handle} cannot carry a duration"
            )
        if relation is CandidateRelation.UNRESOLVED:
            if (
                candidate.requires
                or candidate.produces
                or candidate.composition is not None
                or candidate.composition_operand is not None
            ):
                raise TemporalCandidateValidationError(
                    f"unresolved candidate {candidate.handle} cannot consume, produce, or compose"
                )
            group_targets = {
                item.target
                for item in groups[candidate.exclusive_group]
                if item.relation is not CandidateRelation.UNRESOLVED
            }
            if candidate.target is not None and group_targets and candidate.target not in group_targets:
                raise TemporalCandidateValidationError(
                    f"unresolved candidate {candidate.handle} has an incompatible target"
                )
            if any(use.mode is not AnchorUseMode.UNRESOLVED_SUPPORT for use in candidate.anchor_uses):
                raise TemporalCandidateValidationError(
                    f"unresolved candidate {candidate.handle} has incompatible anchor scope"
                )
            if any(use.handle not in anchors for use in candidate.anchor_uses):
                raise TemporalCandidateValidationError(
                    f"unresolved candidate {candidate.handle} uses an unknown anchor"
                )
            continue

        if relation is CandidateRelation.HOLIDAY_WEEKEND:
            if candidate.target is not TemporalTarget.DEPARTURE:
                raise TemporalCandidateValidationError("holiday weekend must target departure")
            require_anchor(candidate, kind="holiday", mode=AnchorUseMode.DIRECT_WINDOW)
        elif relation is CandidateRelation.CHRISTMAS_PERIOD:
            if candidate.target is not TemporalTarget.DEPARTURE:
                raise TemporalCandidateValidationError("Christmas period must target departure")
            require_anchor(
                candidate,
                kind="holiday",
                mode=AnchorUseMode.DIRECT_WINDOW,
                holiday=Holiday.CHRISTMAS,
            )
        elif relation is CandidateRelation.EXACT_DATE:
            require_anchor(candidate, kind="exact_date", mode=AnchorUseMode.DIRECT_WINDOW)
        elif relation is CandidateRelation.MONTH_PORTION:
            if candidate.reason not in {"early", "mid", "late", "whole"}:
                raise TemporalCandidateValidationError(
                    f"month portion {candidate.handle} has an unsupported portion"
                )
            require_anchor(candidate, kind="month", mode=AnchorUseMode.DIRECT_WINDOW)
        elif relation is CandidateRelation.RELATIVE_CALENDAR_PERIOD:
            if (
                candidate.target is not TemporalTarget.DEPARTURE
                or candidate.anchor_uses
                or candidate.composition is not None
                or candidate.composition_operand is not None
                or candidate.ordinal < 1
            ):
                raise TemporalCandidateValidationError(
                    f"relative calendar period {candidate.handle} has incompatible semantics"
                )
        elif relation is CandidateRelation.DURATION:
            if (
                candidate.target is not TemporalTarget.RETURN
                or candidate.duration is None
                or candidate.duration not in catalog.scan.durations
                or candidate.duration.clause.handle != candidate.clause_handle
                or candidate.anchor_uses
                or candidate.composition is not None
                or candidate.composition_operand is not None
            ):
                raise TemporalCandidateValidationError(
                    f"duration candidate {candidate.handle} has incompatible semantics"
                )
        elif relation is CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR:
            if candidate.target is not TemporalTarget.DEPARTURE or candidate.ordinal < 1:
                raise TemporalCandidateValidationError("relative weekend must target departure")
            require_anchor(candidate, kind="holiday", mode=AnchorUseMode.REFERENCE_ONLY)
        elif relation is CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE:
            if (
                candidate.target is not TemporalTarget.RETURN
                or len(candidate.requires) != 1
                or candidate.composition is not None
                or candidate.composition_operand is not None
                or candidate.anchor_uses
                or candidate.ordinal < 1
            ):
                raise TemporalCandidateValidationError(
                    f"return weekend {candidate.handle} has incompatible dependency semantics"
                )
        elif relation is CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY:
            if (
                candidate.target is not TemporalTarget.DEPARTURE
                or candidate.composition is not CandidateComposition.EXTEND_START
                or len(candidate.requires) != 1
                or candidate.composition_operand != candidate.requires[0]
                or candidate.anchor_uses
            ):
                raise TemporalCandidateValidationError(
                    f"Thursday extension {candidate.handle} has incompatible composition semantics"
                )
        elif relation is CandidateRelation.UNBOUNDED_AFTER:
            if candidate.target is not TemporalTarget.DEPARTURE:
                raise TemporalCandidateValidationError("after boundary must target departure")
            require_anchor(
                candidate,
                kind="holiday",
                mode=AnchorUseMode.REFERENCE_ONLY,
                holiday=Holiday.NEW_YEARS_DAY,
            )
        elif relation is CandidateRelation.UNBOUNDED_BEFORE:
            if candidate.target is not TemporalTarget.RETURN:
                raise TemporalCandidateValidationError("before boundary must target return")
            require_anchor(candidate, kind="exact_date", mode=AnchorUseMode.REFERENCE_ONLY)

        # Any relation other than the explicit Thursday composition cannot smuggle an operand.
        if relation is not CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY and (
            candidate.composition is not None or candidate.composition_operand is not None
        ):
            raise TemporalCandidateValidationError(
                f"candidate {candidate.handle} has an unexpected composition operand"
            )

        for required in candidate.requires:
            # ``requires`` is a selection-availability dependency.  It is a compiler operand
            # only for the explicit return-weekend and Thursday-composition relation forms.
            possible = supported_by_slot.get(required, [])
            if not possible:
                raise TemporalCandidateValidationError(
                    f"candidate {candidate.handle} requires a slot without a possible producer: {required}"
                )
            if candidate in possible:
                raise TemporalCandidateValidationError(
                    f"candidate {candidate.handle} cannot require its own production slot: {required}"
                )
            expected_target = (
                TemporalTarget.DEPARTURE
                if relation
                in {
                    CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE,
                    CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY,
                }
                else candidate.target
            )
            if any(producer.target is not expected_target for producer in possible):
                raise TemporalCandidateValidationError(
                    f"candidate {candidate.handle} consumes an incompatible production slot: {required}"
                )

    conservative_selection = tuple(
        next(
            (
                candidate.handle
                for candidate in choices
                if candidate.relation is CandidateRelation.UNRESOLVED
            ),
            choices[0].handle,
        )
        for choices in groups.values()
    )
    # This is the all-unresolved selection, plus any forced deterministic base facts.  It must
    # always be structurally compilable before the selector can see an alternative.
    validate_candidate_selection(catalog, conservative_selection)

    group_options = tuple(tuple(items) for items in groups.values())
    combination_count = 1
    for group_choices in group_options:
        combination_count *= len(group_choices)
    if combination_count > 512:
        return

    viable: set[str] = set()
    for selection in product(*group_options):
        try:
            validate_candidate_selection(catalog, tuple(item.handle for item in selection))
        except TemporalCandidateValidationError:
            continue
        viable.update(item.handle for item in selection if item.relation is not CandidateRelation.UNRESOLVED)
    dead = next(
        (
            candidate.handle
            for candidate in candidates
            if candidate.relation is not CandidateRelation.UNRESOLVED and candidate.handle not in viable
        ),
        None,
    )
    if dead is not None:
        raise TemporalCandidateValidationError(
            f"supported candidate cannot participate in a complete selection: {dead}"
        )


def _topological_candidates(selected: Sequence[TemporalCandidate]) -> tuple[TemporalCandidate, ...]:
    """Stabilize graph construction independently of selector output order."""

    ordered: list[TemporalCandidate] = []
    visiting: set[str] = set()
    done: set[str] = set()

    producers = {slot: candidate for candidate in selected for slot in candidate.produces}

    def visit(candidate: TemporalCandidate) -> None:
        if candidate.handle in done:
            return
        if candidate.handle in visiting:
            raise TemporalCandidateValidationError("candidate dependency cycle")
        visiting.add(candidate.handle)
        for requirement in candidate.requires:
            producer = producers[requirement]
            if producer is not candidate:
                visit(producer)
        visiting.remove(candidate.handle)
        done.add(candidate.handle)
        ordered.append(candidate)

    for candidate in selected:
        visit(candidate)
    return tuple(ordered)


def compile_temporal_candidates(
    request: RawRequest,
    catalog: TemporalCandidateCatalog,
    selected_handles: Sequence[str],
    *,
    holiday_provider: HolidayDateProvider | None = None,
) -> CompiledTemporalIntent:
    """Compile selected local candidates directly to ``TemporalRelationGraph``.

    No Pass-2 wire model or v2 converter participates.  Existing anchor enrichment and graph
    evaluation remain the source of calendar arithmetic and relation conformance.
    """

    selected = _topological_candidates(validate_candidate_selection(catalog, selected_handles))
    scan = catalog.scan
    clauses = {clause.handle: clause for clause in scan.clauses}
    constraints: list[TemporalConstraint] = []
    # Compiler-local slots, never canonical or public IDs.  Values are created only after a
    # candidate produces its canonical constraint, so references cannot accidentally point at a
    # previously compiled same-target relation.
    produced_constraints: dict[str, str] = {}

    def cid() -> str:
        return f"d{len(constraints)}"

    for candidate in selected:
        clause = clauses.get(candidate.clause_handle or "")
        raw_text = (
            clause.text
            if clause
            else (candidate.duration.clause.text if candidate.duration else "")
        )
        if candidate.relation is CandidateRelation.HOLIDAY_WEEKEND:
            anchor = candidate.anchor_uses[0]
            constraints.append(
                AnchorWindowConstraint(
                    kind="anchor_window",
                    constraint_id=cid(),
                    target=TemporalTarget.DEPARTURE,
                    anchor_id=anchor.handle,
                    window="holiday_weekend",
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.CHRISTMAS_PERIOD:
            anchor = candidate.anchor_uses[0]
            constraints.append(
                AnchorWindowConstraint(
                    kind="anchor_window",
                    constraint_id=cid(),
                    target=TemporalTarget.DEPARTURE,
                    anchor_id=anchor.handle,
                    window="christmas_period",
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.EXACT_DATE:
            anchor = candidate.anchor_uses[0]
            constraints.append(
                AnchorWindowConstraint(
                    kind="anchor_window",
                    constraint_id=cid(),
                    target=candidate.target or TemporalTarget.DEPARTURE,
                    anchor_id=anchor.handle,
                    window="anchor",
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.MONTH_PORTION:
            anchor = candidate.anchor_uses[0]
            constraints.append(
                MonthPortionConstraint(
                    kind="month_portion",
                    constraint_id=cid(),
                    target=candidate.target or TemporalTarget.DEPARTURE,
                    anchor_id=anchor.handle,
                    portion=cast(
                        Literal["early", "mid", "late", "whole"],
                        candidate.reason or "whole",
                    ),
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY:
            operand = (
                produced_constraints.get(candidate.composition_operand)
                if candidate.composition_operand is not None
                else None
            )
            if operand is None:
                raise TemporalCandidateValidationError(
                    "Thursday extension requires compiled departure"
                )
            constraints.append(
                RelativeWeekdayConstraint(
                    kind="relative_weekday",
                    constraint_id=cid(),
                    combine=TemporalComposition.EXTEND_START,
                    combine_with=operand,
                    target=TemporalTarget.DEPARTURE,
                    reference=DecisionReference(
                        kind="decision", constraint_id=operand, edge=TemporalEdge.START
                    ),
                    direction=TemporalDirection.BEFORE,
                    weekday=Weekday.THURSDAY,
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE:
            operand_slot = candidate.requires[0] if candidate.requires else None
            operand = produced_constraints.get(operand_slot) if operand_slot else None
            if operand is None:
                raise TemporalCandidateValidationError(
                    "return weekend requires compiled departure operand"
                )
            constraints.append(
                RelativeWeekendConstraint(
                    kind="relative_weekend",
                    constraint_id=cid(),
                    target=TemporalTarget.RETURN,
                    reference=DecisionReference(
                        kind="decision", constraint_id=operand, edge=TemporalEdge.END
                    ),
                    direction=TemporalDirection.AFTER,
                    ordinal=candidate.ordinal,
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR:
            anchor = candidate.anchor_uses[0]
            constraints.append(
                RelativeWeekendConstraint(
                    kind="relative_weekend",
                    constraint_id=cid(),
                    target=TemporalTarget.DEPARTURE,
                    reference=AnchorReference(kind="anchor", anchor_id=anchor.handle),
                    direction=TemporalDirection.AFTER,
                    ordinal=candidate.ordinal,
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.UNBOUNDED_AFTER:
            anchor = candidate.anchor_uses[0]
            constraints.append(
                UnboundedBoundaryConstraint(
                    kind="unbounded_boundary",
                    constraint_id=cid(),
                    target=TemporalTarget.DEPARTURE,
                    reference=AnchorReference(kind="anchor", anchor_id=anchor.handle),
                    direction=TemporalDirection.AFTER,
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.UNBOUNDED_BEFORE:
            anchor = candidate.anchor_uses[0]
            constraints.append(
                UnboundedBoundaryConstraint(
                    kind="unbounded_boundary",
                    constraint_id=cid(),
                    target=TemporalTarget.RETURN,
                    reference=AnchorReference(kind="anchor", anchor_id=anchor.handle),
                    direction=TemporalDirection.BEFORE,
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.RELATIVE_CALENDAR_PERIOD:
            constraints.append(
                RelativeCalendarPeriodConstraint(
                    kind="relative_calendar_period",
                    constraint_id=cid(),
                    target=TemporalTarget.DEPARTURE,
                    reference=SymbolicContextReference(
                        kind="symbolic_context", key="context:request_date"
                    ),
                    direction=TemporalDirection.AFTER,
                    unit=TemporalUnit.MONTH,
                    ordinal=candidate.ordinal,
                    period_semantics=CalendarPeriodSemantics.WHOLE,
                    raw_text=raw_text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.DURATION:
            assert candidate.duration is not None
            duration = candidate.duration
            constraints.append(
                SemanticDurationConstraint(
                    kind="duration",
                    constraint_id=cid(),
                    reference=RequestFieldReference(
                        kind="request_field",
                        field=TemporalTarget.DEPARTURE,
                        scope=DurationReferenceScope.WHOLE_INTERVAL,
                        edge=None,
                    ),
                    stated_minimum_quantity=duration.minimum,
                    stated_maximum_quantity=duration.maximum,
                    unit=duration.unit,
                    modifier=duration.modifier,
                    raw_text=duration.clause.text,
                )
            )
            for slot in candidate.produces:
                produced_constraints[slot] = constraints[-1].constraint_id or ""
        elif candidate.relation is CandidateRelation.UNRESOLVED:
            constraints.append(
                UnresolvedRelationConstraint(
                    kind="unresolved",
                    constraint_id=cid(),
                    target=candidate.target,
                    raw_text=raw_text,
                    reason=candidate.reason or "unsupported temporal grammar",
                )
            )

    resolved = tuple(enrich_temporal_anchors(request, scan.coarse_extraction, holiday_provider))
    resolved_by_id = {item.anchor.anchor_id: item for item in resolved}
    endpoint_bounds = tuple(
        CompiledEndpointBound(
            target=candidate.target or TemporalTarget.RETURN,
            boundary=resolved_by_id[candidate.anchor_uses[0].handle].start,
            direction="before",
        )
        for candidate in selected
        if candidate.relation is CandidateRelation.UNBOUNDED_BEFORE
    )
    relation_graph = TemporalRelationGraph(constraints=constraints)
    proposal = evaluate_temporal_relation_graph(
        request, scan.coarse_extraction, relation_graph, resolved
    )
    # A strict unbounded return boundary is not a finite return window.  The
    # evaluator may otherwise expose a duration-derived date here; retain the
    # duration itself but leave final endpoint assembly unbounded so the private
    # bound is the only source used for chronology conflict detection.
    if any(bound.target is TemporalTarget.RETURN for bound in endpoint_bounds):
        proposal = proposal.model_copy(update={"return_date": None})
    return CompiledTemporalIntent(
        extraction=scan.coarse_extraction,
        graph=relation_graph,
        resolved_anchors=resolved,
        proposal=proposal,
        departure_window=proposal_window_to_date_window(proposal, "departure"),
        return_window=proposal_window_to_date_window(proposal, "return"),
        literal_duration=tuple(scan.durations),
        unresolved=tuple(proposal.unresolved),
        endpoint_bounds=endpoint_bounds,
    )
