"""Deterministic anchor enrichment and semantic temporal-graph evaluation."""

from __future__ import annotations

import calendar
import re
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Literal

from award_agent.domain import (
    AnchorReference,
    AnchorWindowConstraint,
    CalendarPeriodSemantics,
    CoarseIntentExtraction,
    DateResolutionProposal,
    DateWindow,
    DateWindowPrecision,
    DurationModifier,
    ExactDateAnchor,
    Holiday,
    HolidayAnchor,
    InterpretedDuration,
    MonthAnchor,
    MonthPortionConstraint,
    ProposedDateWindow,
    RawRequest,
    RelativeCalendarPeriodConstraint,
    RelativeOffsetConstraint,
    RelativeWeekdayConstraint,
    RelativeWeekendConstraint,
    RequestFieldReference,
    ResolvedTemporalAnchor,
    SemanticDurationConstraint,
    SymbolicContextReference,
    TemporalDirection,
    TemporalEdge,
    TemporalPhraseTarget,
    TemporalRelationGraph,
    TemporalTarget,
    TemporalUnit,
    UnboundedBoundaryConstraint,
    UnresolvedRelationConstraint,
    UnresolvedTemporalConstraint,
    Weekday,
)
from award_agent.intent.evidence import (
    TemporalEvidenceValidationError,
    TemporalResolutionValidationError,
    resolve_source_quote,
)
from award_agent.intent.holidays import HolidayDateProvider, HolidayDateResolutionError


def _contains_text(request_text: str, supporting_text: str) -> bool:
    return supporting_text in request_text


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_MONTH_NAMES = {
    month: {calendar.month_name[month].casefold(), calendar.month_abbr[month].casefold()}
    for month in range(1, 13)
}

_HOLIDAY_EVIDENCE = {
    Holiday.NEW_YEARS_DAY: ("new year", "new year's"),
    Holiday.MARTIN_LUTHER_KING_JR_DAY: ("martin luther king", "mlk"),
    Holiday.WASHINGTONS_BIRTHDAY: ("washington", "presidents"),
    Holiday.MEMORIAL_DAY: ("memorial day",),
    Holiday.JUNETEENTH: ("juneteenth",),
    Holiday.INDEPENDENCE_DAY: ("independence day", "fourth of july", "4th of july"),
    Holiday.LABOR_DAY: ("labor day",),
    Holiday.COLUMBUS_DAY: ("columbus day", "indigenous peoples"),
    Holiday.VETERANS_DAY: ("veterans day", "veteran's day"),
    Holiday.THANKSGIVING: ("thanksgiving",),
    Holiday.CHRISTMAS: ("christmas",),
}


def _has_literal_year(raw_text: str, year: int) -> bool:
    """Require one complete four-digit source token for an explicit anchor year."""

    return re.search(rf"(?<!\d){year:04d}(?!\d)", raw_text) is not None


def _associated_weekend(anchor_date: date) -> tuple[date, date]:
    """Return the Saturday-Sunday conventionally associated with a holiday."""

    weekday = anchor_date.weekday()
    if weekday <= 2:
        saturday = anchor_date - timedelta(days=weekday + 2)
    elif weekday <= 5:
        saturday = anchor_date + timedelta(days=5 - weekday)
    else:
        saturday = anchor_date - timedelta(days=1)
    return saturday, saturday + timedelta(days=1)


def _holiday_weekend_evidence(
    request: RawRequest,
    anchor: HolidayAnchor,
    extraction: CoarseIntentExtraction,
) -> str | None:
    """Find explicit non-relative wording that selects the holiday-weekend policy."""

    if re.search(r"\bweekend\b", anchor.raw_text, flags=re.IGNORECASE):
        return anchor.raw_text

    anchor_text = re.escape(anchor.raw_text)
    direct_match = re.search(
        rf"\b(?:{anchor_text}\s+weekend|weekend\s+of\s+{anchor_text}(?:\s+weekend)?)\b",
        request.text,
        flags=re.IGNORECASE,
    )
    if direct_match is not None:
        return request.text[direct_match.start() : direct_match.end()]

    for phrase in extraction.temporal_phrases:
        if phrase.applies_to not in {
            TemporalPhraseTarget.DEPARTURE,
            TemporalPhraseTarget.UNSPECIFIED,
        }:
            continue
        normalized = phrase.raw_text.casefold().strip()
        if normalized == "weekend":
            return phrase.raw_text
    return None


def _over_christmas_evidence(request: RawRequest, anchor: HolidayAnchor) -> str | None:
    if anchor.holiday is not Holiday.CHRISTMAS:
        return None
    match = re.search(r"\bover\s+christmas\b", request.text, flags=re.IGNORECASE)
    if match is None:
        return None
    return request.text[match.start() : match.end()]


def _preceding_flexible_weekday(
    extraction: CoarseIntentExtraction,
    window_start: date,
) -> date | None:
    candidates: list[date] = []
    for phrase in extraction.temporal_phrases:
        if phrase.applies_to not in {
            TemporalPhraseTarget.DEPARTURE,
            TemporalPhraseTarget.UNSPECIFIED,
        }:
            continue
        normalized = phrase.raw_text.casefold()
        if not any(marker in normalized for marker in ("as well", "also", "flexib")):
            continue
        for weekday_name, weekday in _WEEKDAYS.items():
            if not re.search(rf"\b{weekday_name}\b", normalized):
                continue
            days_before = (window_start.weekday() - weekday) % 7
            if days_before == 0:
                days_before = 7
            candidates.append(window_start - timedelta(days=days_before))
    return min(candidates) if candidates else None


def _apply_authoritative_holiday_window(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
    proposal: DateResolutionProposal,
    resolved_anchors: Sequence[ResolvedTemporalAnchor],
) -> DateResolutionProposal:
    resolved_by_id = {
        item.anchor.anchor_id: item
        for item in resolved_anchors
        if isinstance(item.anchor, HolidayAnchor)
    }
    for anchor in extraction.date_anchors:
        if (
            not isinstance(anchor, HolidayAnchor)
            or anchor.applies_to is not TemporalTarget.DEPARTURE
        ):
            continue
        resolved = resolved_by_id.get(anchor.anchor_id)
        if resolved is None:
            continue

        weekend_evidence = _holiday_weekend_evidence(request, anchor, extraction)
        over_christmas_evidence = _over_christmas_evidence(request, anchor)
        if weekend_evidence is not None:
            saturday, sunday = _associated_weekend(resolved.start)
            start = min(resolved.start, saturday) - timedelta(days=1)
            end = max(resolved.end, sunday)
            evidence = weekend_evidence
            interpretation = (
                "Deterministic holiday-weekend policy: the holiday, its associated weekend, "
                "and the preceding calendar day."
            )
        elif over_christmas_evidence is not None:
            start = resolved.start - timedelta(days=1)
            end = resolved.end + timedelta(days=1)
            evidence = over_christmas_evidence
            interpretation = (
                "Deterministic Christmas-period policy: Christmas Eve through the day after "
                "Christmas."
            )
        else:
            continue

        flexible_start = _preceding_flexible_weekday(extraction, start)
        if flexible_start is not None:
            start = min(start, flexible_start)

        deterministic_assumption = (
            f"Deterministic holiday policy resolved the inclusive window as {start.isoformat()} "
            f"through {end.isoformat()}."
        )
        if proposal.departure is None:
            departure = ProposedDateWindow(
                start=start,
                end=end,
                supporting_text=[evidence],
                interpretation=interpretation,
                assumptions=[deterministic_assumption],
            )
        else:
            departure = proposal.departure.model_copy(
                update={
                    "start": start,
                    "end": end,
                    "interpretation": interpretation,
                    "assumptions": [
                        *proposal.departure.assumptions,
                        deterministic_assumption,
                    ],
                }
            )
        return proposal.model_copy(update={"departure": departure})
    return proposal


def _next_exact(anchor: ExactDateAnchor, reference_date: date) -> date:
    if anchor.year is not None:
        return date(anchor.year, anchor.month, anchor.day)
    candidate = date(reference_date.year, anchor.month, anchor.day)
    if candidate < reference_date:
        candidate = date(reference_date.year + 1, anchor.month, anchor.day)
    return candidate


def _month_window(anchor: MonthAnchor, reference_date: date) -> tuple[date, date]:
    year = anchor.year or reference_date.year
    end = date(year, anchor.month, calendar.monthrange(year, anchor.month)[1])
    if anchor.year is None and end < reference_date:
        year += 1
    return (
        date(year, anchor.month, 1),
        date(year, anchor.month, calendar.monthrange(year, anchor.month)[1]),
    )


def _holiday_date(
    anchor: HolidayAnchor,
    reference_date: date,
    holiday_provider: HolidayDateProvider | None,
) -> date:
    if holiday_provider is None:
        raise HolidayDateResolutionError("holiday anchors require a HolidayDateProvider")
    year = anchor.year or reference_date.year
    resolved = holiday_provider.holiday_date(anchor.holiday, year)
    if anchor.year is None and resolved < reference_date:
        resolved = holiday_provider.holiday_date(anchor.holiday, year + 1)
    return resolved


def _validate_anchor_kind_evidence(anchor: ExactDateAnchor | MonthAnchor | HolidayAnchor) -> None:
    """Reject grounded text that does not support the anchor variant's semantic kind."""

    normalized = anchor.raw_text.casefold()
    if isinstance(anchor, MonthAnchor):
        if not any(
            re.search(rf"\b{re.escape(name)}\b", normalized) for name in _MONTH_NAMES[anchor.month]
        ):
            raise TemporalResolutionValidationError(
                f"month anchor evidence does not name month {anchor.month}: {anchor.raw_text!r}",
                stage="pass_one_anchor_validation",
                error_code="anchor_kind_evidence_mismatch",
                relation_kind=anchor.kind,
                contradictory_fields=("kind", "month", "raw_text"),
                validation_cause="literal evidence does not name the selected month",
            )
    elif isinstance(anchor, ExactDateAnchor):
        month_supported = (
            any(
                re.search(rf"\b{re.escape(name)}\b", normalized)
                for name in _MONTH_NAMES[anchor.month]
            )
            or re.search(rf"\b0?{anchor.month}\b", normalized) is not None
        )
        day_supported = re.search(rf"\b0?{anchor.day}\b", normalized) is not None
        if not month_supported or not day_supported:
            raise TemporalResolutionValidationError(
                "exact-date anchor evidence does not support its month and day: "
                f"{anchor.raw_text!r}",
                stage="pass_one_anchor_validation",
                error_code="anchor_kind_evidence_mismatch",
                relation_kind=anchor.kind,
                contradictory_fields=("kind", "month", "day", "raw_text"),
                validation_cause="literal evidence does not name the selected month and day",
            )
    else:
        if not any(alias in normalized for alias in _HOLIDAY_EVIDENCE[anchor.holiday]):
            raise TemporalResolutionValidationError(
                f"holiday anchor evidence does not name {anchor.holiday.value}: {anchor.raw_text!r}",
                stage="pass_one_anchor_validation",
                error_code="anchor_kind_evidence_mismatch",
                relation_kind=anchor.kind,
                contradictory_fields=("kind", "holiday", "raw_text"),
                validation_cause="literal evidence does not name the selected holiday",
            )


def sanitize_temporal_extraction(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
) -> CoarseIntentExtraction:
    """Remove unsupported inferred years and validate first-pass evidence spans."""

    sanitized_anchors = []
    for anchor in extraction.date_anchors:
        claim_id = f"{anchor.applies_to.value}_anchor"
        resolve_source_quote(
            request.text,
            anchor.raw_text,
            claim_id=claim_id,
            occurrence_index=anchor.occurrence_index,
        )
        _validate_anchor_kind_evidence(anchor)
        if anchor.year is not None and not _has_literal_year(anchor.raw_text, anchor.year):
            anchor = anchor.model_copy(update={"year": None})
        sanitized_anchors.append(anchor)

    for phrase in extraction.temporal_phrases:
        claim_id = ",".join(claim.value for claim in phrase.claim_ids) or phrase.applies_to.value
        resolve_source_quote(
            request.text,
            phrase.raw_text,
            claim_id=claim_id,
            occurrence_index=phrase.occurrence_index,
        )
    return extraction.model_copy(update={"date_anchors": sanitized_anchors})


def enrich_temporal_anchors(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
    holiday_provider: HolidayDateProvider | None = None,
) -> list[ResolvedTemporalAnchor]:
    """Resolve only explicit exact-date, month, and holiday anchors."""

    extraction = sanitize_temporal_extraction(request, extraction)
    resolved: list[ResolvedTemporalAnchor] = []
    for anchor in extraction.date_anchors:
        if isinstance(anchor, ExactDateAnchor):
            start = end = _next_exact(anchor, request.context.reference_date)
            source: Literal["calendar", "holiday_provider"] = "calendar"
            detail = "Exact date resolved from the explicit month and day."
        elif isinstance(anchor, MonthAnchor):
            start, end = _month_window(anchor, request.context.reference_date)
            source = "calendar"
            detail = "Calendar-month boundaries resolved from the explicit month."
        elif isinstance(anchor, HolidayAnchor):
            start = end = _holiday_date(
                anchor,
                request.context.reference_date,
                holiday_provider,
            )
            source = "holiday_provider"
            detail = f"Holiday provider resolved {anchor.holiday.value}."
        else:  # pragma: no cover - closed union defensive check
            raise TypeError(f"unsupported temporal anchor: {type(anchor)!r}")

        resolved.append(
            ResolvedTemporalAnchor(
                anchor=anchor,
                start=start,
                end=end,
                source=source,
                source_detail=detail,
            )
        )

    return resolved


def validate_date_resolution_proposal(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
    proposal: DateResolutionProposal,
    resolved_anchors: Sequence[ResolvedTemporalAnchor] = (),
) -> DateResolutionProposal:
    """Reject ungrounded proposal evidence while preserving semantic uncertainty."""

    has_temporal_evidence = bool(extraction.date_anchors or extraction.temporal_phrases)
    if not has_temporal_evidence and (
        proposal.departure is not None or proposal.return_date is not None
    ):
        raise TemporalResolutionValidationError(
            "the model proposed dates without temporal evidence in the request"
        )

    windows = [
        ("departure_period", proposal.departure),
        ("return_period", proposal.return_date),
    ]
    for claim_id, window in windows:
        if window is None:
            continue
        for supporting_text in window.supporting_text:
            resolve_source_quote(request.text, supporting_text, claim_id=claim_id)
    unresolved_claims = {
        "departure": "departure_period",
        "return_or_duration": "return_period",
        "dates": "temporal_unspecified",
    }
    for unresolved in proposal.unresolved:
        resolve_source_quote(
            request.text,
            unresolved.raw_text,
            claim_id=unresolved_claims[unresolved.field],
        )

    duration = proposal.interpreted_duration
    if duration is not None:
        resolve_source_quote(request.text, duration.raw_text, claim_id="duration")

    proposal = _apply_authoritative_holiday_window(
        request,
        extraction,
        proposal,
        resolved_anchors,
    )

    request_text = request.text
    normalized_request = request_text.casefold()
    grounded_unresolved = list(proposal.unresolved)
    for anchor in extraction.date_anchors:
        if not isinstance(anchor, HolidayAnchor):
            continue
        holiday_text = re.escape(anchor.raw_text.casefold())
        relation = re.search(rf"\b(after|before)\s+{holiday_text}\b", normalized_request)
        duration_number = r"(?:\d+|one|two|three|a|an)"
        duration_relation = re.search(
            rf"\bfor\s+(?:about\s+)?{duration_number}"
            rf"(?:\s+or\s+{duration_number})?\s+(?:days?|weeks?|months?)\s+"
            rf"(after|before)\s+{holiday_text}\b",
            normalized_request,
        )
        bounded_relation = re.search(
            rf"\b(?:\d+|one|two|three|a|the)?\s*"
            rf"(?:days?|weeks?|weekends?|months?)\s+(?:after|before)\s+{holiday_text}\b",
            normalized_request,
        )
        if relation is None and duration_relation is None:
            continue
        if duration_relation is None and bounded_relation is not None:
            continue
        match = relation or duration_relation
        assert match is not None
        relation_text = request_text[match.start() : match.end()]
        grounded_unresolved.append(
            UnresolvedTemporalConstraint(
                field="departure",
                raw_text=relation_text,
                reason=(
                    "A holiday-relative boundary without a bounded departure offset does not "
                    "define a useful departure range."
                ),
            )
        )
        return proposal.model_copy(
            update={
                "departure": None,
                "return_date": None,
                "unresolved": grounded_unresolved,
            }
        )

    if proposal.departure is not None and duration is not None:
        return_start = proposal.departure.start + timedelta(days=duration.minimum_days)
        return_end = proposal.departure.end + timedelta(days=duration.maximum_days)
        if proposal.return_date is None:
            return_date = ProposedDateWindow(
                start=return_start,
                end=return_end,
                supporting_text=[duration.raw_text],
                interpretation="Return range derived from the model-interpreted trip duration.",
                assumptions=[],
            )
        else:
            return_date = proposal.return_date.model_copy(
                update={"start": return_start, "end": return_end}
            )
        proposal = proposal.model_copy(update={"return_date": return_date})
    return proposal


def proposal_window_to_date_window(
    proposal: DateResolutionProposal,
    field: str,
) -> DateWindow | None:
    proposed = proposal.departure if field == "departure" else proposal.return_date
    if proposed is None:
        return None
    return DateWindow(
        start=proposed.start,
        end=proposed.end,
        precision=(
            DateWindowPrecision.EXACT
            if proposed.start == proposed.end
            else DateWindowPrecision.WINDOW
        ),
        raw_text="; ".join(proposed.supporting_text),
    )


def _constraint_reference(constraint: object) -> AnchorReference | RequestFieldReference | None:
    if isinstance(
        constraint,
        (
            RelativeWeekendConstraint,
            RelativeWeekdayConstraint,
            RelativeOffsetConstraint,
            SemanticDurationConstraint,
            UnboundedBoundaryConstraint,
        ),
    ):
        return constraint.reference
    return None


def validate_temporal_relation_graph(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
    graph: TemporalRelationGraph,
    resolved_anchors: Sequence[ResolvedTemporalAnchor],
) -> None:
    """Validate grounding, references, dependencies, and cycles before calendar evaluation."""

    if graph.constraints and not (extraction.date_anchors or extraction.temporal_phrases):
        raise TemporalResolutionValidationError(
            "the model emitted temporal relations without temporal evidence in the request",
            stage="pass_two_conformance",
            error_code="relation_without_first_pass_evidence",
            missing_fields=("first_pass_temporal_claim",),
        )

    anchors = {item.anchor.anchor_id: item for item in resolved_anchors}
    bounded_types = (
        AnchorWindowConstraint,
        MonthPortionConstraint,
        RelativeWeekendConstraint,
        RelativeWeekdayConstraint,
        RelativeOffsetConstraint,
        RelativeCalendarPeriodConstraint,
    )
    producers: dict[TemporalTarget, int] = {target: 0 for target in TemporalTarget}
    semantic_producers: dict[TemporalTarget, int] = {target: 0 for target in TemporalTarget}
    dependencies: dict[TemporalTarget, set[TemporalTarget]] = {
        target: set() for target in TemporalTarget
    }
    strict_dependency_edges: set[tuple[TemporalTarget, TemporalTarget]] = set()

    for constraint_index, constraint in enumerate(graph.constraints):
        target = getattr(constraint, "target", None)
        claim_id = "temporal_unspecified" if target is None else f"{target.value}_period"
        try:
            span = resolve_source_quote(
                request.text,
                constraint.raw_text,
                claim_id=claim_id,
                occurrence_index=constraint.occurrence_index,
            )
        except TemporalEvidenceValidationError as exc:
            raise TemporalEvidenceValidationError(
                code=exc.code,
                quote=exc.quote,
                claim_id=exc.claim_id,
                reason=exc.reason,
                stage="pass_two_conformance",
                constraint_index=constraint_index,
                relation_kind=constraint.kind,
            ) from exc
        evidence_id = f"request:{span.start}:{span.end}"
        if isinstance(constraint, bounded_types):
            producers[constraint.target] += 1
            semantic_producers[constraint.target] += 1
        elif isinstance(constraint, UnboundedBoundaryConstraint):
            semantic_producers[constraint.target] += 1

        anchor_id = getattr(constraint, "anchor_id", None)
        if anchor_id is not None and anchor_id not in anchors:
            raise TemporalResolutionValidationError(
                f"temporal relation references missing anchor: {anchor_id}",
                stage="pass_two_conformance",
                error_code="unknown_anchor_id",
                constraint_index=constraint_index,
                relation_kind=constraint.kind,
                missing_fields=("catalog_anchor",),
                evidence_id=evidence_id,
                reference_id=anchor_id,
            )
        if isinstance(constraint, MonthPortionConstraint) and not isinstance(
            anchors[constraint.anchor_id].anchor, MonthAnchor
        ):
            raise TemporalResolutionValidationError(
                f"month_portion requires a month anchor: {constraint.anchor_id}",
                stage="pass_two_conformance",
                error_code="incompatible_relation_fields",
                constraint_index=constraint_index,
                relation_kind=constraint.kind,
                contradictory_fields=("anchor_id", "kind"),
                evidence_id=evidence_id,
                reference_id=constraint.anchor_id,
            )
        if isinstance(constraint, AnchorWindowConstraint):
            anchor = anchors[constraint.anchor_id].anchor
            if constraint.window in {"holiday_weekend", "christmas_period"} and not isinstance(
                anchor, HolidayAnchor
            ):
                raise TemporalResolutionValidationError(
                    f"{constraint.window} requires a holiday anchor: {constraint.anchor_id}",
                    stage="pass_two_conformance",
                    error_code="incompatible_relation_fields",
                    constraint_index=constraint_index,
                    relation_kind=constraint.kind,
                    contradictory_fields=("anchor_id", "window"),
                    evidence_id=evidence_id,
                    reference_id=constraint.anchor_id,
                )
            if constraint.window == "christmas_period" and (
                not isinstance(anchor, HolidayAnchor) or anchor.holiday is not Holiday.CHRISTMAS
            ):
                raise TemporalResolutionValidationError(
                    "christmas_period requires a Christmas anchor",
                    stage="pass_two_conformance",
                    error_code="incompatible_relation_fields",
                    constraint_index=constraint_index,
                    relation_kind=constraint.kind,
                    contradictory_fields=("anchor_id", "window"),
                    evidence_id=evidence_id,
                    reference_id=constraint.anchor_id,
                )

        reference = _constraint_reference(constraint)
        if isinstance(reference, AnchorReference) and reference.anchor_id not in anchors:
            raise TemporalResolutionValidationError(
                f"temporal relation references missing anchor: {reference.anchor_id}",
                stage="pass_two_conformance",
                error_code="unknown_anchor_id",
                constraint_index=constraint_index,
                relation_kind=constraint.kind,
                missing_fields=("catalog_anchor",),
                evidence_id=evidence_id,
                reference_id=reference.anchor_id,
            )
        if isinstance(reference, RequestFieldReference) and target is not None:
            dependencies[target].add(reference.field)
            if not isinstance(constraint, SemanticDurationConstraint):
                strict_dependency_edges.add((target, reference.field))

    for target, referenced_fields in dependencies.items():
        for referenced in referenced_fields:
            if producers[referenced] == 0 and (
                (target, referenced) in strict_dependency_edges
                or semantic_producers[referenced] == 0
            ):
                raise TemporalResolutionValidationError(
                    f"{target.value} depends on unresolved request field: {referenced.value}",
                    stage="pass_two_dependency_validation",
                    error_code="unresolved_dependency",
                    relation_kind="request_field_reference",
                    missing_fields=(f"{referenced.value}_producer",),
                    reference_id=f"request_field:{referenced.value}",
                )

    visiting: set[TemporalTarget] = set()
    visited: set[TemporalTarget] = set()

    def visit(target: TemporalTarget) -> None:
        if target in visiting:
            raise TemporalResolutionValidationError(
                f"cyclic temporal request-field dependency detected at {target.value}",
                stage="pass_two_dependency_validation",
                error_code="cyclic_dependency",
                relation_kind="request_field_reference",
                contradictory_fields=("dependency_graph",),
                reference_id=f"request_field:{target.value}",
            )
        if target in visited:
            return
        visiting.add(target)
        for dependency in dependencies[target]:
            visit(dependency)
        visiting.remove(target)
        visited.add(target)

    for target in TemporalTarget:
        visit(target)


def _edge(window: tuple[date, date], edge: TemporalEdge) -> date:
    return window[0] if edge is TemporalEdge.START else window[1]


def _duration_return_boundary(
    departure: date,
    quantity: int,
    unit: TemporalUnit,
) -> date:
    """Apply one literal duration quantity to a concrete departure date."""

    if unit is TemporalUnit.MONTH:
        return _add_months(departure, quantity)
    multiplier = 1 if unit is TemporalUnit.DAY else 7
    return departure + timedelta(days=quantity * multiplier)


def _duration_tolerance(modifier: DurationModifier) -> timedelta:
    """Normalize approximation consistently: ``about a week`` is 6--8 days."""

    return timedelta(days=1 if modifier is DurationModifier.APPROXIMATE else 0)


def _duration_day_bounds(
    duration: SemanticDurationConstraint,
    departure: tuple[date, date] | None,
) -> tuple[int, int]:
    """Return compatibility day bounds without driving calendar-month arithmetic."""

    tolerance_days = _duration_tolerance(duration.modifier).days
    if duration.unit is not TemporalUnit.MONTH:
        multiplier = 1 if duration.unit is TemporalUnit.DAY else 7
        return (
            max(1, duration.stated_minimum_quantity * multiplier - tolerance_days),
            duration.stated_maximum_quantity * multiplier + tolerance_days,
        )

    if departure is None:
        raise ValueError("month duration day bounds require a bounded departure")
    day_counts: list[int] = []
    current = departure[0]
    while current <= departure[1]:
        for quantity in {
            duration.stated_minimum_quantity,
            duration.stated_maximum_quantity,
        }:
            day_counts.append((_add_months(current, quantity) - current).days)
        current += timedelta(days=1)
    return max(1, min(day_counts) - tolerance_days), max(day_counts) + tolerance_days


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _relative_weekend(
    reference: date,
    direction: TemporalDirection,
    ordinal: int,
) -> tuple[date, date]:
    if direction is TemporalDirection.AFTER:
        delta = (5 - reference.weekday()) % 7
        if delta == 0:
            delta = 7
        saturday = reference + timedelta(days=delta + 7 * (ordinal - 1))
    else:
        delta = (reference.weekday() - 6) % 7
        if delta == 0:
            delta = 7
        sunday = reference - timedelta(days=delta + 7 * (ordinal - 1))
        saturday = sunday - timedelta(days=1)
    return saturday, saturday + timedelta(days=1)


def _relative_weekday(
    reference: date,
    weekday: Weekday,
    direction: TemporalDirection,
    ordinal: int,
) -> date:
    wanted = _WEEKDAYS[weekday.value]
    if direction is TemporalDirection.AFTER:
        delta = (wanted - reference.weekday()) % 7
        if delta == 0:
            delta = 7
        return reference + timedelta(days=delta + 7 * (ordinal - 1))
    delta = (reference.weekday() - wanted) % 7
    if delta == 0:
        delta = 7
    return reference - timedelta(days=delta + 7 * (ordinal - 1))


def _offset_date(
    reference: date,
    direction: TemporalDirection,
    amount: int,
    unit: TemporalUnit,
) -> date:
    sign = 1 if direction is TemporalDirection.AFTER else -1
    if unit is TemporalUnit.MONTH:
        return _add_months(reference, sign * amount)
    days = amount if unit is TemporalUnit.DAY else amount * 7
    return reference + timedelta(days=sign * days)


def _relative_calendar_period(
    reference: date,
    direction: TemporalDirection,
    ordinal: int,
    unit: TemporalUnit,
    period_semantics: CalendarPeriodSemantics,
) -> tuple[date, date]:
    if unit is not TemporalUnit.MONTH:
        raise TemporalResolutionValidationError(
            f"unsupported relative calendar-period unit: {unit.value}"
        )
    if period_semantics is not CalendarPeriodSemantics.WHOLE:
        raise TemporalResolutionValidationError(
            "partial relative calendar periods require an explicit supported policy"
        )
    sign = 1 if direction is TemporalDirection.AFTER else -1
    target_month = _add_months(reference.replace(day=1), sign * ordinal)
    return (
        target_month,
        date(
            target_month.year,
            target_month.month,
            calendar.monthrange(target_month.year, target_month.month)[1],
        ),
    )


def evaluate_temporal_relation_graph(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
    graph: TemporalRelationGraph,
    resolved_anchors: Sequence[ResolvedTemporalAnchor],
) -> DateResolutionProposal:
    """Evaluate a validated semantic relation graph into authoritative date windows."""

    validate_temporal_relation_graph(request, extraction, graph, resolved_anchors)
    anchors = {item.anchor.anchor_id: item for item in resolved_anchors}
    field_constraints = {
        target: [
            item
            for item in graph.constraints
            if getattr(item, "target", None) is target
            and isinstance(
                item,
                (
                    AnchorWindowConstraint,
                    MonthPortionConstraint,
                    RelativeWeekendConstraint,
                    RelativeWeekdayConstraint,
                    RelativeOffsetConstraint,
                    RelativeCalendarPeriodConstraint,
                ),
            )
        ]
        for target in TemporalTarget
    }
    cache: dict[TemporalTarget, tuple[date, date] | None] = {}

    def resolve_reference(
        reference: AnchorReference | RequestFieldReference | SymbolicContextReference,
    ) -> date:
        if isinstance(reference, AnchorReference):
            anchor = anchors[reference.anchor_id]
            return _edge((anchor.start, anchor.end), reference.edge)
        if isinstance(reference, SymbolicContextReference):
            return request.context.reference_date
        resolved = resolve_field(reference.field)
        if resolved is None:  # validation should make this unreachable
            raise TemporalResolutionValidationError(
                f"request-field reference could not be evaluated: {reference.field.value}"
            )
        return _edge(resolved, reference.edge)

    def resolve_field(target: TemporalTarget) -> tuple[date, date] | None:
        if target in cache:
            return cache[target]
        windows: list[tuple[date, date]] = []
        for constraint in field_constraints[target]:
            if isinstance(constraint, AnchorWindowConstraint):
                anchor = anchors[constraint.anchor_id]
                if constraint.window == "holiday_weekend":
                    saturday, sunday = _associated_weekend(anchor.start)
                    window = (
                        min(anchor.start, saturday) - timedelta(days=1),
                        max(anchor.end, sunday),
                    )
                elif constraint.window == "christmas_period":
                    window = (anchor.start - timedelta(days=1), anchor.end + timedelta(days=1))
                else:
                    window = (anchor.start, anchor.end)
            elif isinstance(constraint, MonthPortionConstraint):
                anchor = anchors[constraint.anchor_id]
                if constraint.portion == "early":
                    window = (anchor.start, date(anchor.start.year, anchor.start.month, 10))
                elif constraint.portion == "mid":
                    window = (
                        date(anchor.start.year, anchor.start.month, 11),
                        date(anchor.start.year, anchor.start.month, 20),
                    )
                elif constraint.portion == "late":
                    window = (date(anchor.end.year, anchor.end.month, 21), anchor.end)
                else:
                    window = (anchor.start, anchor.end)
            elif isinstance(constraint, RelativeWeekendConstraint):
                window = _relative_weekend(
                    resolve_reference(constraint.reference),
                    constraint.direction,
                    constraint.ordinal,
                )
            elif isinstance(constraint, RelativeWeekdayConstraint):
                exact = _relative_weekday(
                    resolve_reference(constraint.reference),
                    constraint.weekday,
                    constraint.direction,
                    constraint.ordinal,
                )
                window = (exact, exact)
            elif isinstance(constraint, RelativeCalendarPeriodConstraint):
                window = _relative_calendar_period(
                    resolve_reference(constraint.reference),
                    constraint.direction,
                    constraint.ordinal,
                    constraint.unit,
                    constraint.period_semantics,
                )
            else:
                exact = _offset_date(
                    resolve_reference(constraint.reference),
                    constraint.direction,
                    constraint.amount,
                    constraint.unit,
                )
                window = (exact, exact)
            windows.append(window)
        cache[target] = (
            None
            if not windows
            else (min(item[0] for item in windows), max(item[1] for item in windows))
        )
        return cache[target]

    departure = resolve_field(TemporalTarget.DEPARTURE)
    explicit_return = resolve_field(TemporalTarget.RETURN)
    durations = [item for item in graph.constraints if isinstance(item, SemanticDurationConstraint)]
    interpreted_duration: InterpretedDuration | None = None
    derived_return: tuple[date, date] | None = None
    if durations:
        minimum_days: list[int] = []
        maximum_days: list[int] = []
        for duration in durations:
            if departure is None and duration.unit is TemporalUnit.MONTH:
                continue
            minimum, maximum = _duration_day_bounds(duration, departure)
            minimum_days.append(minimum)
            maximum_days.append(maximum)
        if minimum_days:
            interpreted_duration = InterpretedDuration(
                raw_text="; ".join(item.raw_text for item in durations),
                minimum_days=min(minimum_days),
                maximum_days=max(maximum_days),
            )
        if departure is not None and interpreted_duration is not None:
            return_starts: list[date] = []
            return_ends: list[date] = []
            for duration in durations:
                tolerance = _duration_tolerance(duration.modifier)
                return_starts.append(
                    max(
                        departure[0] + timedelta(days=1),
                        _duration_return_boundary(
                            departure[0],
                            duration.stated_minimum_quantity,
                            duration.unit,
                        )
                        - tolerance,
                    )
                )
                return_ends.append(
                    _duration_return_boundary(
                        departure[1],
                        duration.stated_maximum_quantity,
                        duration.unit,
                    )
                    + tolerance
                )
            derived_return = (min(return_starts), max(return_ends))

    unresolved: list[UnresolvedTemporalConstraint] = []
    for constraint in graph.constraints:
        if isinstance(constraint, UnboundedBoundaryConstraint):
            unresolved.append(
                UnresolvedTemporalConstraint(
                    field=(
                        "departure"
                        if constraint.target is TemporalTarget.DEPARTURE
                        else "return_or_duration"
                    ),
                    raw_text=constraint.raw_text,
                    reason="The semantic boundary is unbounded and does not define a finite window.",
                )
            )
        elif isinstance(constraint, UnresolvedRelationConstraint):
            unresolved.append(
                UnresolvedTemporalConstraint(
                    field=(
                        "dates"
                        if constraint.target is None
                        else (
                            "departure"
                            if constraint.target is TemporalTarget.DEPARTURE
                            else "return_or_duration"
                        )
                    ),
                    raw_text=constraint.raw_text,
                    reason=constraint.reason,
                )
            )
    if durations and departure is None:
        unresolved.append(
            UnresolvedTemporalConstraint(
                field="return_or_duration",
                raw_text="; ".join(item.raw_text for item in durations),
                reason="The duration cannot produce return dates until departure is bounded.",
            )
        )

    def proposed(
        target: TemporalTarget,
        window: tuple[date, date] | None,
        *,
        duration_derived: bool = False,
    ) -> ProposedDateWindow | None:
        if window is None:
            return None
        constraints = durations if duration_derived else field_constraints[target]
        return ProposedDateWindow(
            start=window[0],
            end=window[1],
            supporting_text=[item.raw_text for item in constraints],
            interpretation=(
                "Deterministically derived from the semantic duration relation."
                if duration_derived
                else "Deterministically evaluated from the semantic temporal-relation graph."
            ),
        )

    return DateResolutionProposal(
        departure=proposed(TemporalTarget.DEPARTURE, departure),
        return_date=proposed(
            TemporalTarget.RETURN,
            explicit_return if explicit_return is not None else derived_return,
            duration_derived=explicit_return is None and derived_return is not None,
        ),
        interpreted_duration=interpreted_duration,
        unresolved=unresolved,
    )
