"""Private structural challenge catalogs for the temporal-selector boundary.

This module deliberately contains the raw requests, compiler-local IDs, candidate rationales,
and private oracles for the seven-topology challenge set.  It does *not* serialize a public
fixture, make a model call, or define an evaluation gate.  A later fixture builder must project
these catalogs through :func:`build_temporal_selector_input` and retain only that date-free
projection.

The two surfaces under one topology are independent phrasings of that topology, not independent
population samples.  ``canonical``/``permuted`` public variants are intentionally deferred to the
fixture layer; ``challenge_surface_variants`` reserves that seam without conflating variants with
surfaces.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from award_agent.domain import (
    ExactDateAnchor,
    MonthAnchor,
    RawRequest,
    RequestContext,
    TemporalTarget,
)
from award_agent.evaluation.frozen_selector_eval import StaticFrozenHolidayProvider
from award_agent.intent.temporal_candidates import (
    AnchorUse,
    AnchorUseMode,
    CandidateComposition,
    CandidateRelation,
    TemporalCandidate,
    TemporalCandidateCatalog,
)
from award_agent.intent.temporal_compiler import CompiledTemporalIntent, compile_temporal_candidates
from award_agent.intent.temporal_lexing import (
    GroundedClause,
    LiteralAnchor,
    TemporalScan,
    scan_temporal_request,
)
from award_agent.intent.temporal_selector import plan_temporal_selection


class ChallengeTopology(StrEnum):
    """The complete, intentionally small structural challenge vocabulary."""

    ENDPOINT_FORK = "endpoint_fork"
    ANCHORED_REFERENCE_SCOPE_FORK = "anchored_reference_scope_fork"
    UNSUPPORTED_FORK = "unsupported_fork"
    SINGLE_COMPOSITION = "single_composition"
    DEPENDENCY_CLOSURE = "dependency_closure"
    DEPTH_TWO_COMPOSITION_CHAIN = "depth_two_composition_chain"
    TWO_INDEPENDENT_GROUPS = "two_independent_groups"


@dataclass(frozen=True)
class SelectorChallengeSurface:
    """One private natural-language surface and its complete compiler-local oracle.

    ``oracle_candidates`` contains one selected candidate from *every* exclusive group, including
    deterministic groups.  Consumers that need only the selector-visible oracle must use
    :func:`selector_oracle_candidates`; silently dropping deterministic choices would make the
    compiler oracle incomplete.
    """

    topology_id: ChallengeTopology
    subtype_id: str
    surface_id: str
    request: RawRequest
    catalog: TemporalCandidateCatalog
    oracle_candidates: tuple[str, ...]
    oracle_rationale: str
    candidate_rationales: Mapping[str, str]


@dataclass(frozen=True)
class ChallengeSurfaceVariant:
    """Reserved identity for the future public-payload permutation layer.

    The private surface remains the source of semantic truth.  A fixture builder can attach a
    bijective opaque-handle remapping and candidate/group ordering only at projection time.
    """

    surface: SelectorChallengeSurface
    order_variant: str


def _request(text: str) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 29), timezone="America/Los_Angeles"),
    )


def _scan(text: str) -> TemporalScan:
    return scan_temporal_request(_request(text))


def _clause(scan: TemporalScan, kind: str, *, occurrence: int = 0) -> GroundedClause:
    matches = [item for item in scan.clauses if item.kind == kind]
    if len(matches) <= occurrence:
        raise AssertionError(f"challenge surface needs {kind!r} clause")
    return matches[occurrence]


def _anchor(scan: TemporalScan, kind: str) -> LiteralAnchor:
    anchor = next((item for item in scan.anchors if item.kind == kind), None)
    if anchor is None:
        raise AssertionError(f"challenge surface needs {kind!r} anchor")
    return anchor


def _candidate(
    handle: str,
    group: str,
    relation: CandidateRelation,
    *,
    covers: tuple[str, ...],
    produces: tuple[str, ...] = (),
    requires: tuple[str, ...] = (),
    anchor_uses: tuple[AnchorUse, ...] = (),
    target: TemporalTarget | None = None,
    clause_handle: str | None = None,
    composition: CandidateComposition | None = None,
    composition_operand: str | None = None,
    ordinal: int = 1,
    reason: str | None = None,
) -> TemporalCandidate:
    return TemporalCandidate(
        handle=handle,
        exclusive_group=group,
        covers=covers,
        requires=requires,
        produces=produces,
        priority=100 if relation is not CandidateRelation.UNRESOLVED else 0,
        anchor_uses=anchor_uses,
        relation=relation,
        composition=composition,
        composition_operand=composition_operand,
        target=target,
        clause_handle=clause_handle,
        ordinal=ordinal,
        reason=reason,
    )


def _unresolved(
    handle: str,
    group: str,
    *,
    covers: tuple[str, ...],
    target: TemporalTarget | None,
    clause_handle: str,
    anchor_uses: tuple[AnchorUse, ...] = (),
) -> TemporalCandidate:
    return _candidate(
        handle,
        group,
        CandidateRelation.UNRESOLVED,
        covers=covers,
        target=target,
        clause_handle=clause_handle,
        anchor_uses=anchor_uses,
        reason="manual structural challenge unresolved alternative",
    )


def _with_exact_anchor(
    scan: TemporalScan,
    source: LiteralAnchor,
    *,
    handle: str,
    target: TemporalTarget,
    day: int | None = None,
) -> tuple[TemporalScan, LiteralAnchor]:
    """Add a private same-text exact-date anchor for a competing endpoint interpretation."""

    alternate = LiteralAnchor(
        handle,
        source.clause,
        "exact_date",
        month=source.month,
        day=source.day if day is None else day,
        year=source.year,
        target=target,
    )
    extraction = scan.coarse_extraction.model_copy(
        update={
            "date_anchors": [
                *scan.coarse_extraction.date_anchors,
                ExactDateAnchor(
                    kind="exact_date",
                    anchor_id=alternate.handle,
                    applies_to=target,
                    raw_text=source.clause.text,
                    month=alternate.month or 1,
                    day=alternate.day or 1,
                    year=alternate.year,
                ),
            ]
        }
    )
    return replace(scan, anchors=(*scan.anchors, alternate), coarse_extraction=extraction), alternate


def _with_month_anchor(
    scan: TemporalScan,
    source: LiteralAnchor,
    *,
    handle: str,
    target: TemporalTarget,
) -> tuple[TemporalScan, LiteralAnchor]:
    alternate = LiteralAnchor(
        handle,
        source.clause,
        "month",
        month=source.month,
        target=target,
    )
    extraction = scan.coarse_extraction.model_copy(
        update={
            "date_anchors": [
                *scan.coarse_extraction.date_anchors,
                MonthAnchor(
                    kind="month",
                    anchor_id=alternate.handle,
                    applies_to=target,
                    raw_text=source.clause.text,
                    month=alternate.month or 1,
                ),
            ]
        }
    )
    return replace(scan, anchors=(*scan.anchors, alternate), coarse_extraction=extraction), alternate


def _surface(
    topology: ChallengeTopology,
    subtype_id: str,
    surface_id: str,
    scan: TemporalScan,
    candidates: tuple[TemporalCandidate, ...],
    oracle: tuple[str, ...],
    rationale: str,
    candidate_rationales: Mapping[str, str],
) -> SelectorChallengeSurface:
    if set(oracle) - {candidate.handle for candidate in candidates}:
        raise AssertionError("challenge oracle names a missing private candidate")
    if set(candidate_rationales) != {candidate.handle for candidate in candidates}:
        raise AssertionError("every challenge candidate needs private review rationale")
    return SelectorChallengeSurface(
        topology_id=topology,
        subtype_id=subtype_id,
        surface_id=surface_id,
        request=_request(scan.request_text),
        catalog=TemporalCandidateCatalog(scan, candidates),
        oracle_candidates=oracle,
        oracle_rationale=rationale,
        candidate_rationales=dict(candidate_rationales),
    )


def _endpoint_fork(surface_id: str, text: str) -> SelectorChallengeSurface:
    scan = _scan(text)
    original = _anchor(scan, "exact_date")
    true_target = original.target
    alternate_target = (
        TemporalTarget.RETURN if true_target is TemporalTarget.DEPARTURE else TemporalTarget.DEPARTURE
    )
    scan, alternate = _with_exact_anchor(
        scan,
        original,
        handle=f"manual:{surface_id}:alternate-endpoint",
        target=alternate_target,
    )
    group = f"manual:{surface_id}:endpoint"
    clause = original.clause.handle
    true = _candidate(
        f"manual:{surface_id}:stated-endpoint", group, CandidateRelation.EXACT_DATE,
        covers=(clause,), produces=(f"slot:{surface_id}:{true_target.value}",),
        anchor_uses=(AnchorUse(original.handle, AnchorUseMode.DIRECT_WINDOW),), target=true_target,
        clause_handle=clause,
    )
    alternate_choice = _candidate(
        f"manual:{surface_id}:other-endpoint", group, CandidateRelation.EXACT_DATE,
        covers=(clause,), produces=(f"slot:{surface_id}:{alternate_target.value}",),
        anchor_uses=(AnchorUse(alternate.handle, AnchorUseMode.DIRECT_WINDOW),), target=alternate_target,
        clause_handle=clause,
    )
    unresolved = _unresolved(
        f"manual:{surface_id}:unresolved", group, covers=(clause,), target=None, clause_handle=clause,
        anchor_uses=(AnchorUse(original.handle, AnchorUseMode.UNRESOLVED_SUPPORT),),
    )
    return _surface(
        ChallengeTopology.ENDPOINT_FORK, "explicit_endpoint_cue", surface_id, scan,
        (true, alternate_choice, unresolved),
        (true.handle,), "The explicit endpoint cue in the local sentence fixes the date's endpoint.",
        {
            true.handle: "Uses the exact date for the endpoint explicitly named in the sentence.",
            alternate_choice.handle: "Uses the same date for the opposite endpoint; locally plausible only if the cue were absent or reversed.",
            unresolved.handle: "Declines an endpoint interpretation despite an explicit local endpoint cue.",
        },
    )


def _reference_surface() -> SelectorChallengeSurface:
    surface_id = "anchored-reference-weekend"
    scan = _scan("Leave two weekends after Thanksgiving.")
    thanksgiving = _anchor(scan, "holiday")
    clause = _clause(scan, "relative_weekend_after_holiday").handle
    group = f"manual:{surface_id}"
    relative = _candidate(
        f"manual:{surface_id}:relative", group, CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR,
        covers=(clause,), produces=("slot:reference-departure",),
        anchor_uses=(AnchorUse(thanksgiving.handle, AnchorUseMode.REFERENCE_ONLY),),
        target=TemporalTarget.DEPARTURE, clause_handle=clause, ordinal=2,
    )
    direct = _candidate(
        f"manual:{surface_id}:direct", group, CandidateRelation.HOLIDAY_WEEKEND,
        covers=(clause,), produces=("slot:reference-departure",),
        anchor_uses=(AnchorUse(thanksgiving.handle, AnchorUseMode.DIRECT_WINDOW),),
        target=TemporalTarget.DEPARTURE, clause_handle=clause,
    )
    unresolved = _unresolved(f"manual:{surface_id}:unresolved", group, covers=(clause,),
        target=TemporalTarget.DEPARTURE, clause_handle=clause,
        anchor_uses=(AnchorUse(thanksgiving.handle, AnchorUseMode.UNRESOLVED_SUPPORT),),)
    return _surface(
        ChallengeTopology.ANCHORED_REFERENCE_SCOPE_FORK, "weekend_after_anchor", surface_id, scan,
        (relative, direct, unresolved), (relative.handle,),
        "'After Thanksgiving' makes Thanksgiving a reference, not the requested travel window.",
        {relative.handle: "Counts the stated two weekends after the Thanksgiving anchor.",
         direct.handle: "Treats Thanksgiving itself as the trip weekend and discards the 'after' relation.",
         unresolved.handle: "Leaves an otherwise supported anchored relation unresolved."},
    )


def _scope_surface() -> SelectorChallengeSurface:
    surface_id = "anchored-scope-boundary"
    scan = _scan("Leave after New Year.")
    new_year = _anchor(scan, "holiday")
    clause = _clause(scan, "unbounded_after").handle
    group = f"manual:{surface_id}"
    boundary = _candidate(f"manual:{surface_id}:boundary", group, CandidateRelation.UNBOUNDED_AFTER,
        covers=(clause,), produces=("slot:scope-departure",),
        anchor_uses=(AnchorUse(new_year.handle, AnchorUseMode.REFERENCE_ONLY),),
        target=TemporalTarget.DEPARTURE, clause_handle=clause)
    direct = _candidate(f"manual:{surface_id}:direct", group, CandidateRelation.HOLIDAY_WEEKEND,
        covers=(clause,), produces=("slot:scope-departure",),
        anchor_uses=(AnchorUse(new_year.handle, AnchorUseMode.DIRECT_WINDOW),),
        target=TemporalTarget.DEPARTURE, clause_handle=clause)
    unresolved = _unresolved(f"manual:{surface_id}:unresolved", group, covers=(clause,),
        target=TemporalTarget.DEPARTURE, clause_handle=clause,
        anchor_uses=(AnchorUse(new_year.handle, AnchorUseMode.UNRESOLVED_SUPPORT),),)
    return _surface(
        ChallengeTopology.ANCHORED_REFERENCE_SCOPE_FORK, "unbounded_after_anchor", surface_id, scan,
        (boundary, direct, unresolved), (boundary.handle,),
        "'After New Year' is an unbounded boundary; it does not request New Year's holiday weekend.",
        {boundary.handle: "Preserves the after-anchor boundary and its unbounded scope.",
         direct.handle: "Narrows an after-boundary into New Year's holiday weekend.",
         unresolved.handle: "Avoids the supported boundary despite its explicit cue."},
    )


def _unsupported_spring_surface() -> SelectorChallengeSurface:
    surface_id = "unsupported-season"
    scan = _scan("Leave next spring.")
    clause = _clause(scan, "unsupported").handle
    group = f"manual:{surface_id}"
    one_month = _candidate(f"manual:{surface_id}:one-month", group, CandidateRelation.RELATIVE_CALENDAR_PERIOD,
        covers=(clause,), produces=("slot:season-departure",), target=TemporalTarget.DEPARTURE,
        clause_handle=clause, ordinal=1)
    two_month = _candidate(f"manual:{surface_id}:two-month", group, CandidateRelation.RELATIVE_CALENDAR_PERIOD,
        covers=(clause,), produces=("slot:season-departure",), target=TemporalTarget.DEPARTURE,
        clause_handle=clause, ordinal=2)
    unresolved = _unresolved(f"manual:{surface_id}:unresolved", group, covers=(clause,),
        target=TemporalTarget.DEPARTURE, clause_handle=clause)
    return _surface(
        ChallengeTopology.UNSUPPORTED_FORK, "season", surface_id, scan,
        (one_month, two_month, unresolved),
        (unresolved.handle,), "A season has no supported deterministic calendar policy in this slice.",
        {one_month.handle: "Invents 'next month' for the unsupported season wording.",
         two_month.handle: "Invents a different relative month for the unsupported season wording.",
         unresolved.handle: "Retains the unsupported season wording for clarification."},
    )


def _unsupported_first_week_surface() -> SelectorChallengeSurface:
    surface_id = "unsupported-first-week"
    scan = _scan("Leave the first week of October.")
    month = _anchor(scan, "month")
    clause = _clause(scan, "unsupported").handle
    group = f"manual:{surface_id}"
    early = _candidate(f"manual:{surface_id}:early", group, CandidateRelation.MONTH_PORTION,
        covers=(clause,), produces=("slot:first-week-departure",),
        anchor_uses=(AnchorUse(month.handle, AnchorUseMode.DIRECT_WINDOW),), target=TemporalTarget.DEPARTURE,
        clause_handle=clause, reason="early")
    whole = _candidate(f"manual:{surface_id}:whole", group, CandidateRelation.MONTH_PORTION,
        covers=(clause,), produces=("slot:first-week-departure",),
        anchor_uses=(AnchorUse(month.handle, AnchorUseMode.DIRECT_WINDOW),), target=TemporalTarget.DEPARTURE,
        clause_handle=clause, reason="whole")
    unresolved = _unresolved(f"manual:{surface_id}:unresolved", group, covers=(clause,),
        target=TemporalTarget.DEPARTURE, clause_handle=clause,
        anchor_uses=(AnchorUse(month.handle, AnchorUseMode.UNRESOLVED_SUPPORT),),)
    return _surface(
        ChallengeTopology.UNSUPPORTED_FORK, "first_week", surface_id, scan,
        (early, whole, unresolved),
        (unresolved.handle,), "'First week' has no current month-portion policy and must not be silently broadened.",
        {early.handle: "Collapses the unsupported first-week wording to the broader early-month policy.",
         whole.handle: "Collapses the unsupported first-week wording to the whole named month.",
         unresolved.handle: "Preserves the unsupported first-week wording for clarification."},
    )


def _single_composition_surface(surface_id: str, text: str) -> SelectorChallengeSurface:
    scan = _scan(text)
    labor = _anchor(scan, "holiday")
    holiday_clause = _clause(scan, "holiday_weekend").handle
    extension_clause = _clause(scan, "thursday_extension").handle
    base_group = f"manual:{surface_id}:base"
    base = _candidate(f"manual:{surface_id}:base", base_group, CandidateRelation.HOLIDAY_WEEKEND,
        covers=(holiday_clause,), produces=(f"slot:{surface_id}:base",),
        anchor_uses=(AnchorUse(labor.handle, AnchorUseMode.DIRECT_WINDOW),), target=TemporalTarget.DEPARTURE,
        clause_handle=holiday_clause)
    group = f"manual:{surface_id}:composition"
    extend = _candidate(f"manual:{surface_id}:extend", group, CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY,
        covers=(extension_clause,), requires=(f"slot:{surface_id}:base",), produces=(f"slot:{surface_id}:departure",),
        target=TemporalTarget.DEPARTURE, clause_handle=extension_clause,
        composition=CandidateComposition.EXTEND_START, composition_operand=f"slot:{surface_id}:base")
    direct = _candidate(f"manual:{surface_id}:direct", group, CandidateRelation.HOLIDAY_WEEKEND,
        covers=(extension_clause,), produces=(f"slot:{surface_id}:departure",),
        anchor_uses=(AnchorUse(labor.handle, AnchorUseMode.DIRECT_WINDOW),), target=TemporalTarget.DEPARTURE,
        clause_handle=extension_clause)
    unresolved = _unresolved(f"manual:{surface_id}:unresolved", group, covers=(extension_clause,),
        target=TemporalTarget.DEPARTURE, clause_handle=extension_clause)
    return _surface(
        ChallengeTopology.SINGLE_COMPOSITION, "holiday_weekend_thursday_extension", surface_id, scan,
        (base, extend, direct, unresolved),
        (base.handle, extend.handle), "The second clause explicitly extends the already selected Labor Day departure window to Thursday.",
        {base.handle: "Provides the deterministic Labor Day departure window that the composition consumes.",
         extend.handle: "Extends that explicit departure production to Thursday.",
         direct.handle: "Ignores 'Thursday as well' and repeats the unextended holiday weekend.",
         unresolved.handle: "Leaves the supported composition cue unresolved."},
    )


def _dependency_closure_surface(surface_id: str, text: str) -> SelectorChallengeSurface:
    scan = _scan(text)
    exact = _anchor(scan, "exact_date")
    scan, month = _with_month_anchor(scan, exact, handle=f"manual:{surface_id}:month", target=TemporalTarget.DEPARTURE)
    departure_clause = exact.clause.handle
    return_clause = _clause(scan, "return_weekend_after").handle
    upstream_group = f"manual:{surface_id}:upstream"
    exact_choice = _candidate(f"manual:{surface_id}:exact", upstream_group, CandidateRelation.EXACT_DATE,
        covers=(departure_clause,), produces=(f"slot:{surface_id}:departure",),
        anchor_uses=(AnchorUse(exact.handle, AnchorUseMode.DIRECT_WINDOW),), target=TemporalTarget.DEPARTURE,
        clause_handle=departure_clause)
    month_choice = _candidate(f"manual:{surface_id}:month", upstream_group, CandidateRelation.MONTH_PORTION,
        covers=(departure_clause,), produces=(f"slot:{surface_id}:departure",),
        anchor_uses=(AnchorUse(month.handle, AnchorUseMode.DIRECT_WINDOW),), target=TemporalTarget.DEPARTURE,
        clause_handle=departure_clause, reason="whole")
    upstream_unresolved = _unresolved(f"manual:{surface_id}:upstream-unresolved", upstream_group,
        covers=(departure_clause,), target=TemporalTarget.DEPARTURE, clause_handle=departure_clause,
        anchor_uses=(AnchorUse(exact.handle, AnchorUseMode.UNRESOLVED_SUPPORT),))
    downstream_group = f"manual:{surface_id}:downstream"
    return_weekend = _candidate(f"manual:{surface_id}:return-weekend", downstream_group,
        CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE, covers=(return_clause,),
        requires=(f"slot:{surface_id}:departure",), produces=(f"slot:{surface_id}:return",),
        target=TemporalTarget.RETURN, clause_handle=return_clause)
    downstream_unresolved = _unresolved(f"manual:{surface_id}:downstream-unresolved", downstream_group,
        covers=(return_clause,), target=TemporalTarget.RETURN, clause_handle=return_clause)
    return _surface(
        ChallengeTopology.DEPENDENCY_CLOSURE, "departure_to_return_weekend", surface_id, scan,
        (exact_choice, month_choice, upstream_unresolved, return_weekend, downstream_unresolved),
        (exact_choice.handle, return_weekend.handle),
        "The explicit date produces the departure value required by the stated return-weekend relation.",
        {exact_choice.handle: "Uses the exact departure date stated in the request.",
         month_choice.handle: "Broadens the exact date to the whole named month.",
         upstream_unresolved.handle: "Withholds the departure production needed by the dependent return relation.",
         return_weekend.handle: "Uses the required selected departure production for the return weekend.",
         downstream_unresolved.handle: "Declines the supported dependent return relation."},
    )


def _depth_two_composition_surface(surface_id: str, text: str) -> SelectorChallengeSurface:
    scan = _scan(text)
    exact = _anchor(scan, "exact_date")
    departure_clause = exact.clause.handle
    extension_clause = _clause(scan, "thursday_extension").handle
    return_clause = _clause(scan, "return_weekend_after").handle
    base_group = f"manual:{surface_id}:base"
    base = _candidate(f"manual:{surface_id}:base", base_group, CandidateRelation.EXACT_DATE,
        covers=(departure_clause,), produces=(f"slot:{surface_id}:base",),
        anchor_uses=(AnchorUse(exact.handle, AnchorUseMode.DIRECT_WINDOW),), target=TemporalTarget.DEPARTURE,
        clause_handle=departure_clause)
    composition_group = f"manual:{surface_id}:composition"
    extend = _candidate(f"manual:{surface_id}:extend", composition_group,
        CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY, covers=(extension_clause,),
        requires=(f"slot:{surface_id}:base",), produces=(f"slot:{surface_id}:departure",),
        target=TemporalTarget.DEPARTURE, clause_handle=extension_clause,
        composition=CandidateComposition.EXTEND_START, composition_operand=f"slot:{surface_id}:base")
    direct = _candidate(f"manual:{surface_id}:direct", composition_group, CandidateRelation.EXACT_DATE,
        covers=(extension_clause,), produces=(f"slot:{surface_id}:departure",),
        anchor_uses=(AnchorUse(exact.handle, AnchorUseMode.DIRECT_WINDOW),), target=TemporalTarget.DEPARTURE,
        clause_handle=extension_clause)
    composition_unresolved = _unresolved(f"manual:{surface_id}:composition-unresolved", composition_group,
        covers=(extension_clause,), target=TemporalTarget.DEPARTURE, clause_handle=extension_clause)
    return_group = f"manual:{surface_id}:return"
    return_weekend = _candidate(f"manual:{surface_id}:return-weekend", return_group,
        CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE, covers=(return_clause,),
        requires=(f"slot:{surface_id}:departure",), produces=(f"slot:{surface_id}:return",),
        target=TemporalTarget.RETURN, clause_handle=return_clause)
    return_unresolved = _unresolved(f"manual:{surface_id}:return-unresolved", return_group,
        covers=(return_clause,), target=TemporalTarget.RETURN, clause_handle=return_clause)
    return _surface(
        ChallengeTopology.DEPTH_TWO_COMPOSITION_CHAIN, "exact_to_thursday_to_return_weekend", surface_id, scan,
        (base, extend, direct, composition_unresolved, return_weekend, return_unresolved),
        (base.handle, extend.handle, return_weekend.handle),
        "The selected exact-date producer feeds Thursday composition, whose output feeds the return-weekend relation.",
        {base.handle: "Provides the starting departure date for the first dependency edge.",
         extend.handle: "Produces the composed departure window from the explicit base slot.",
         direct.handle: "Skips the Thursday composition and repeats the original exact departure date.",
         composition_unresolved.handle: "Withholds the departure production required by the return relation.",
         return_weekend.handle: "Consumes the composed departure output for the return weekend.",
         return_unresolved.handle: "Declines the supported final dependent relation."},
    )


def _two_independent_groups_surface(surface_id: str, text: str) -> SelectorChallengeSurface:
    scan = _scan(text)
    departure = next(anchor for anchor in scan.anchors if anchor.target is TemporalTarget.DEPARTURE)
    returned = next(anchor for anchor in scan.anchors if anchor.target is TemporalTarget.RETURN)
    scan, departure_other = _with_exact_anchor(scan, departure, handle=f"manual:{surface_id}:departure-other", target=TemporalTarget.RETURN)
    scan, return_other = _with_exact_anchor(scan, returned, handle=f"manual:{surface_id}:return-other", target=TemporalTarget.DEPARTURE)

    def choices(
        label: str,
        primary: LiteralAnchor,
        alternate: LiteralAnchor,
        target: TemporalTarget,
    ) -> tuple[TemporalCandidate, TemporalCandidate, TemporalCandidate]:
        group = f"manual:{surface_id}:{label}"
        clause = primary.clause.handle
        correct = _candidate(f"manual:{surface_id}:{label}:stated", group, CandidateRelation.EXACT_DATE,
            covers=(clause,), produces=(f"slot:{surface_id}:{label}:{target.value}",),
            anchor_uses=(AnchorUse(primary.handle, AnchorUseMode.DIRECT_WINDOW),), target=target, clause_handle=clause)
        other_target = TemporalTarget.RETURN if target is TemporalTarget.DEPARTURE else TemporalTarget.DEPARTURE
        other = _candidate(f"manual:{surface_id}:{label}:other", group, CandidateRelation.EXACT_DATE,
            covers=(clause,), produces=(f"slot:{surface_id}:{label}:{other_target.value}",),
            anchor_uses=(AnchorUse(alternate.handle, AnchorUseMode.DIRECT_WINDOW),), target=other_target, clause_handle=clause)
        unresolved = _unresolved(f"manual:{surface_id}:{label}:unresolved", group, covers=(clause,), target=None,
            clause_handle=clause, anchor_uses=(AnchorUse(primary.handle, AnchorUseMode.UNRESOLVED_SUPPORT),))
        return correct, other, unresolved

    departure_choices = choices("departure", departure, departure_other, TemporalTarget.DEPARTURE)
    return_choices = choices("return", returned, return_other, TemporalTarget.RETURN)
    candidates = (*departure_choices, *return_choices)
    oracle = (departure_choices[0].handle, return_choices[0].handle)
    return _surface(
        ChallengeTopology.TWO_INDEPENDENT_GROUPS, "independent_departure_return_endpoints", surface_id, scan,
        candidates, oracle,
        "Each sentence has its own explicit endpoint cue; neither endpoint decision depends on the other.",
        {candidate.handle: (
            "Uses the endpoint explicitly stated for this independent clause."
            if candidate in {departure_choices[0], return_choices[0]}
            else "Uses the opposite endpoint despite this clause's explicit cue."
            if candidate in {departure_choices[1], return_choices[1]}
            else "Leaves this explicitly scoped endpoint unresolved."
        ) for candidate in candidates},
    )


def challenge_surface_registry() -> dict[str, SelectorChallengeSurface]:
    """Build fourteen fresh private surfaces: two for each of seven topology clusters."""

    surfaces = (
        _endpoint_fork("endpoint-fork-departure", "Leave October 5."),
        _endpoint_fork("endpoint-fork-return", "Return November 12."),
        _reference_surface(),
        _scope_surface(),
        _unsupported_spring_surface(),
        _unsupported_first_week_surface(),
        _single_composition_surface("single-composition-leave", "Leave Labor Day weekend. Thursday as well."),
        _single_composition_surface("single-composition-travel", "We will leave for Labor Day weekend. Thursday as well."),
        _dependency_closure_surface("dependency-closure-october", "Leave October 5. Return the weekend afterwards."),
        _dependency_closure_surface("dependency-closure-march", "Depart March 3. Return the weekend afterwards."),
        _depth_two_composition_surface("depth-two-october", "Leave October 5. Thursday as well. Return the weekend afterwards."),
        _depth_two_composition_surface("depth-two-march", "Depart March 3. Thursday as well. Return the weekend afterwards."),
        _two_independent_groups_surface("two-independent-october", "Leave October 5. Return November 12."),
        _two_independent_groups_surface("two-independent-march-april", "Depart March 3. Be back April 4."),
    )
    registry = {surface.surface_id: surface for surface in surfaces}
    if len(registry) != len(surfaces):
        raise AssertionError("challenge surface ids must be unique")
    return registry


def challenge_surface_variants(surface: SelectorChallengeSurface) -> tuple[ChallengeSurfaceVariant, ...]:
    """Declare the future canonical/permuted fixture identities without mutating private catalogs."""

    return (
        ChallengeSurfaceVariant(surface, "canonical"),
        ChallengeSurfaceVariant(surface, "permuted"),
    )


def selector_oracle_candidates(surface: SelectorChallengeSurface) -> tuple[str, ...]:
    """Return the oracle handles belonging to selector-visible groups only."""

    plan = plan_temporal_selection(surface.catalog)
    selector_groups = set(plan.selector_groups)
    return tuple(
        handle
        for handle in surface.oracle_candidates
        if surface.catalog.by_handle(handle).exclusive_group in selector_groups
    )


def compile_challenge_oracle(surface: SelectorChallengeSurface) -> CompiledTemporalIntent:
    """Compile the complete private oracle using offline frozen holiday dates."""

    return compile_temporal_candidates(
        surface.request,
        surface.catalog,
        surface.oracle_candidates,
        holiday_provider=StaticFrozenHolidayProvider(),
    )
