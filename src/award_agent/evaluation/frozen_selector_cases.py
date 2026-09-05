"""Private/manual catalogs for the frozen temporal-selector study.

The corresponding YAML intentionally contains only the selector's public projection.  These
builders retain the local candidate identities and semantic oracle needed to restore and compile
a selection, but those details must never be sent to a selector or copied into the public fixture.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

from award_agent.domain import (
    ExactDateAnchor,
    Holiday,
    MonthAnchor,
    RawRequest,
    RequestContext,
    TemporalTarget,
)
from award_agent.intent.temporal_candidates import (
    AnchorUse,
    AnchorUseMode,
    CandidateComposition,
    CandidateRelation,
    TemporalCandidate,
    TemporalCandidateCatalog,
)
from award_agent.intent.temporal_lexing import LiteralAnchor, scan_temporal_request


@dataclass(frozen=True)
class FrozenSelectorCase:
    """One private fixture definition and its semantic oracle."""

    identifier: str
    category: str
    pair: str
    request: RawRequest
    catalog: TemporalCandidateCatalog
    oracle_candidates: tuple[str, ...]


def _request(text: str) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 29), timezone="America/Los_Angeles"),
    )


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
    clause_handle: str | None,
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
        reason="manual frozen ambiguity unresolved alternative",
    )


def _reorder(items: tuple[TemporalCandidate, ...], reversed_order: bool) -> tuple[TemporalCandidate, ...]:
    return tuple(reversed(items)) if reversed_order else items


def _target_case(reversed_order: bool) -> FrozenSelectorCase:
    request = _request("Leave October 5.")
    scan = scan_temporal_request(request)
    departure = next(anchor for anchor in scan.anchors if anchor.kind == "exact_date")
    returned = LiteralAnchor(
        "manual:return-anchor",
        departure.clause,
        "exact_date",
        month=departure.month,
        day=departure.day,
        year=departure.year,
        target=TemporalTarget.RETURN,
    )
    extraction = scan.coarse_extraction.model_copy(
        update={
            "date_anchors": [
                *scan.coarse_extraction.date_anchors,
                ExactDateAnchor(
                    kind="exact_date",
                    anchor_id=returned.handle,
                    applies_to=TemporalTarget.RETURN,
                    raw_text=departure.clause.text,
                    month=departure.month or 1,
                    day=departure.day or 1,
                    year=departure.year,
                ),
            ]
        }
    )
    scan = replace(scan, anchors=(*scan.anchors, returned), coarse_extraction=extraction)
    direct_departure = AnchorUse(departure.handle, AnchorUseMode.DIRECT_WINDOW)
    direct_return = AnchorUse(returned.handle, AnchorUseMode.DIRECT_WINDOW)
    support = AnchorUse(departure.handle, AnchorUseMode.UNRESOLVED_SUPPORT)
    group = "manual:target"
    choices = (
        _candidate(
            "manual:target:departure",
            group,
            CandidateRelation.EXACT_DATE,
            covers=(departure.clause.handle,),
            produces=("slot:departure",),
            anchor_uses=(direct_departure,),
            target=TemporalTarget.DEPARTURE,
            clause_handle=departure.clause.handle,
        ),
        _candidate(
            "manual:target:return",
            group,
            CandidateRelation.EXACT_DATE,
            covers=(departure.clause.handle,),
            produces=("slot:return",),
            anchor_uses=(direct_return,),
            target=TemporalTarget.RETURN,
            clause_handle=departure.clause.handle,
        ),
        _unresolved(
            "manual:target:unresolved",
            group,
            covers=(departure.clause.handle,),
            target=None,
            clause_handle=departure.clause.handle,
            anchor_uses=(support,),
        ),
    )
    suffix = "reversed" if reversed_order else "forward"
    return FrozenSelectorCase(
        f"target-{suffix}",
        "target",
        "target",
        request,
        TemporalCandidateCatalog(scan, _reorder(choices, reversed_order)),
        ("manual:target:departure",),
    )


def _reference_case(reversed_order: bool) -> FrozenSelectorCase:
    request = _request("Leave two weekends after Thanksgiving.")
    scan = scan_temporal_request(request)
    thanksgiving = next(anchor for anchor in scan.anchors if anchor.holiday is Holiday.THANKSGIVING)
    phrase = next(clause for clause in scan.clauses if clause.kind == "relative_weekend_after_holiday")
    group = "manual:reference"
    choices = (
        _candidate(
            "manual:reference:relative",
            group,
            CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR,
            covers=(phrase.handle,),
            produces=("slot:departure",),
            anchor_uses=(AnchorUse(thanksgiving.handle, AnchorUseMode.REFERENCE_ONLY),),
            target=TemporalTarget.DEPARTURE,
            clause_handle=phrase.handle,
            ordinal=2,
        ),
        _candidate(
            "manual:reference:direct",
            group,
            CandidateRelation.HOLIDAY_WEEKEND,
            covers=(phrase.handle,),
            produces=("slot:departure",),
            anchor_uses=(AnchorUse(thanksgiving.handle, AnchorUseMode.DIRECT_WINDOW),),
            target=TemporalTarget.DEPARTURE,
            clause_handle=phrase.handle,
        ),
        _unresolved(
            "manual:reference:unresolved",
            group,
            covers=(phrase.handle,),
            target=TemporalTarget.DEPARTURE,
            clause_handle=phrase.handle,
            anchor_uses=(AnchorUse(thanksgiving.handle, AnchorUseMode.UNRESOLVED_SUPPORT),),
        ),
    )
    suffix = "reversed" if reversed_order else "forward"
    return FrozenSelectorCase(
        f"reference-{suffix}",
        "reference",
        "reference",
        request,
        TemporalCandidateCatalog(scan, _reorder(choices, reversed_order)),
        ("manual:reference:relative",),
    )


def _composition_case(reversed_order: bool) -> FrozenSelectorCase:
    request = _request("Leave Labor Day weekend. Thursday as well.")
    scan = scan_temporal_request(request)
    labor = next(anchor for anchor in scan.anchors if anchor.holiday is Holiday.LABOR_DAY)
    holiday_clause = next(clause for clause in scan.clauses if clause.kind == "holiday_weekend")
    extension_clause = next(clause for clause in scan.clauses if clause.kind == "thursday_extension")
    base = _candidate(
        "manual:composition:base",
        "manual:composition:base-group",
        CandidateRelation.HOLIDAY_WEEKEND,
        covers=(holiday_clause.handle,),
        produces=("slot:base-departure",),
        anchor_uses=(AnchorUse(labor.handle, AnchorUseMode.DIRECT_WINDOW),),
        target=TemporalTarget.DEPARTURE,
        clause_handle=holiday_clause.handle,
    )
    group = "manual:composition"
    choices = (
        _candidate(
            "manual:composition:extend",
            group,
            CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY,
            covers=(extension_clause.handle,),
            requires=("slot:base-departure",),
            produces=("slot:departure",),
            target=TemporalTarget.DEPARTURE,
            clause_handle=extension_clause.handle,
            composition=CandidateComposition.EXTEND_START,
            composition_operand="slot:base-departure",
        ),
        _candidate(
            "manual:composition:weekend-after",
            group,
            CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR,
            covers=(extension_clause.handle,),
            requires=("slot:base-departure",),
            produces=("slot:departure",),
            anchor_uses=(AnchorUse(labor.handle, AnchorUseMode.REFERENCE_ONLY),),
            target=TemporalTarget.DEPARTURE,
            clause_handle=extension_clause.handle,
            ordinal=1,
        ),
        _unresolved(
            "manual:composition:unresolved",
            group,
            covers=(extension_clause.handle,),
            target=TemporalTarget.DEPARTURE,
            clause_handle=extension_clause.handle,
        ),
    )
    suffix = "reversed" if reversed_order else "forward"
    return FrozenSelectorCase(
        f"composition-{suffix}",
        "composition",
        "composition",
        request,
        TemporalCandidateCatalog(scan, (base, *_reorder(choices, reversed_order))),
        ("manual:composition:extend",),
    )


def _scope_case(reversed_order: bool) -> FrozenSelectorCase:
    request = _request("Leave after New Year.")
    scan = scan_temporal_request(request)
    new_year = next(anchor for anchor in scan.anchors if anchor.holiday is Holiday.NEW_YEARS_DAY)
    phrase = next(clause for clause in scan.clauses if clause.kind == "unbounded_after")
    group = "manual:scope"
    choices = (
        _candidate(
            "manual:scope:reference-only",
            group,
            CandidateRelation.UNBOUNDED_AFTER,
            covers=(phrase.handle,),
            produces=("slot:departure",),
            anchor_uses=(AnchorUse(new_year.handle, AnchorUseMode.REFERENCE_ONLY),),
            target=TemporalTarget.DEPARTURE,
            clause_handle=phrase.handle,
        ),
        _candidate(
            "manual:scope:direct-window",
            group,
            CandidateRelation.HOLIDAY_WEEKEND,
            covers=(phrase.handle,),
            produces=("slot:departure",),
            anchor_uses=(AnchorUse(new_year.handle, AnchorUseMode.DIRECT_WINDOW),),
            target=TemporalTarget.DEPARTURE,
            clause_handle=phrase.handle,
        ),
        _unresolved(
            "manual:scope:unresolved",
            group,
            covers=(phrase.handle,),
            target=TemporalTarget.DEPARTURE,
            clause_handle=phrase.handle,
            anchor_uses=(AnchorUse(new_year.handle, AnchorUseMode.UNRESOLVED_SUPPORT),),
        ),
    )
    suffix = "reversed" if reversed_order else "forward"
    return FrozenSelectorCase(
        f"scope-{suffix}",
        "scope",
        "scope",
        request,
        TemporalCandidateCatalog(scan, _reorder(choices, reversed_order)),
        ("manual:scope:reference-only",),
    )


def _dependency_case(reversed_order: bool) -> FrozenSelectorCase:
    request = _request("Leave October 5. Return the weekend afterwards.")
    scan = scan_temporal_request(request)
    exact = next(anchor for anchor in scan.anchors if anchor.kind == "exact_date")
    month = LiteralAnchor(
        "manual:month-anchor",
        exact.clause,
        "month",
        month=exact.month,
        target=TemporalTarget.DEPARTURE,
    )
    extraction = scan.coarse_extraction.model_copy(
        update={
            "date_anchors": [
                *scan.coarse_extraction.date_anchors,
                MonthAnchor(
                    kind="month",
                    anchor_id=month.handle,
                    applies_to=TemporalTarget.DEPARTURE,
                    raw_text=exact.clause.text,
                    month=exact.month or 1,
                ),
            ]
        }
    )
    scan = replace(scan, anchors=(*scan.anchors, month), coarse_extraction=extraction)
    return_phrase = next(clause for clause in scan.clauses if clause.kind == "return_weekend_after")
    upstream = (
        _candidate(
            "manual:dependency:exact",
            "manual:dependency:upstream",
            CandidateRelation.EXACT_DATE,
            covers=(exact.clause.handle,),
            produces=("slot:departure",),
            anchor_uses=(AnchorUse(exact.handle, AnchorUseMode.DIRECT_WINDOW),),
            target=TemporalTarget.DEPARTURE,
            clause_handle=exact.clause.handle,
        ),
        _candidate(
            "manual:dependency:month",
            "manual:dependency:upstream",
            CandidateRelation.MONTH_PORTION,
            covers=(exact.clause.handle,),
            produces=("slot:departure",),
            anchor_uses=(AnchorUse(month.handle, AnchorUseMode.DIRECT_WINDOW),),
            target=TemporalTarget.DEPARTURE,
            clause_handle=exact.clause.handle,
            reason="whole",
        ),
        _unresolved(
            "manual:dependency:upstream-unresolved",
            "manual:dependency:upstream",
            covers=(exact.clause.handle,),
            target=TemporalTarget.DEPARTURE,
            clause_handle=exact.clause.handle,
            anchor_uses=(AnchorUse(exact.handle, AnchorUseMode.UNRESOLVED_SUPPORT),),
        ),
    )
    downstream = (
        _candidate(
            "manual:dependency:return-weekend",
            "manual:dependency:downstream",
            CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE,
            covers=(return_phrase.handle,),
            requires=("slot:departure",),
            produces=("slot:return",),
            target=TemporalTarget.RETURN,
            clause_handle=return_phrase.handle,
        ),
        _unresolved(
            "manual:dependency:downstream-unresolved",
            "manual:dependency:downstream",
            covers=(return_phrase.handle,),
            target=TemporalTarget.RETURN,
            clause_handle=return_phrase.handle,
        ),
    )
    suffix = "reversed" if reversed_order else "forward"
    # Reverse each group separately, preserving group ordering and therefore the dependency graph.
    candidates = (*_reorder(upstream, reversed_order), *_reorder(downstream, reversed_order))
    return FrozenSelectorCase(
        f"dependency-{suffix}",
        "dependency_closure",
        "dependency",
        request,
        TemporalCandidateCatalog(scan, candidates),
        ("manual:dependency:exact", "manual:dependency:return-weekend"),
    )


def _unsupported_case(reversed_order: bool) -> FrozenSelectorCase:
    request = _request("Leave next spring.")
    scan = scan_temporal_request(request)
    phrase = next(clause for clause in scan.clauses if clause.kind == "unsupported")
    group = "manual:unsupported"
    choices = (
        _candidate(
            "manual:unsupported:next-month",
            group,
            CandidateRelation.RELATIVE_CALENDAR_PERIOD,
            covers=(phrase.handle,),
            produces=("slot:departure",),
            target=TemporalTarget.DEPARTURE,
            clause_handle=phrase.handle,
            ordinal=1,
        ),
        _candidate(
            "manual:unsupported:two-months",
            group,
            CandidateRelation.RELATIVE_CALENDAR_PERIOD,
            covers=(phrase.handle,),
            produces=("slot:departure",),
            target=TemporalTarget.DEPARTURE,
            clause_handle=phrase.handle,
            ordinal=2,
        ),
        _unresolved(
            "manual:unsupported:unresolved",
            group,
            covers=(phrase.handle,),
            target=TemporalTarget.DEPARTURE,
            clause_handle=phrase.handle,
        ),
    )
    suffix = "reversed" if reversed_order else "forward"
    return FrozenSelectorCase(
        f"unsupported-{suffix}",
        "unsupported",
        "unsupported",
        request,
        TemporalCandidateCatalog(scan, _reorder(choices, reversed_order)),
        ("manual:unsupported:unresolved",),
    )


_CASE_BUILDERS: tuple[Callable[[bool], FrozenSelectorCase], ...] = (
    _target_case,
    _reference_case,
    _composition_case,
    _scope_case,
    _dependency_case,
    _unsupported_case,
)


def frozen_selector_case_registry() -> dict[str, FrozenSelectorCase]:
    """Build a fresh private catalog registry for every preflight/evaluation run."""

    cases = [builder(reversed_order) for builder in _CASE_BUILDERS for reversed_order in (False, True)]
    return {case.identifier: case for case in cases}
