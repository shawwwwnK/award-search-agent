"""Deterministic enrichment and validation around model-proposed date ranges."""

from __future__ import annotations

import calendar
import re
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Literal

from award_agent.domain import (
    CoarseIntentExtraction,
    DateResolutionProposal,
    DateWindow,
    DateWindowPrecision,
    ExactDateAnchor,
    Holiday,
    HolidayAnchor,
    MonthAnchor,
    ProposedDateWindow,
    RawRequest,
    ResolvedTemporalAnchor,
    TemporalPhraseTarget,
    TemporalTarget,
    UnresolvedTemporalConstraint,
)
from award_agent.intent.holidays import HolidayDateProvider, HolidayDateResolutionError


class TemporalResolutionValidationError(ValueError):
    """Raised when temporal evidence or a proposed range is not grounded in the request."""


def _contains_text(request_text: str, supporting_text: str) -> bool:
    return supporting_text.casefold() in request_text.casefold()


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


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
        if not isinstance(anchor, HolidayAnchor) or anchor.applies_to is not TemporalTarget.DEPARTURE:
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
        raise HolidayDateResolutionError(
            "holiday anchors require a HolidayDateProvider"
        )
    year = anchor.year or reference_date.year
    resolved = holiday_provider.holiday_date(anchor.holiday, year)
    if anchor.year is None and resolved < reference_date:
        resolved = holiday_provider.holiday_date(anchor.holiday, year + 1)
    return resolved


def sanitize_temporal_extraction(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
) -> CoarseIntentExtraction:
    """Remove unsupported inferred years and validate first-pass evidence spans."""

    seen_ids: set[str] = set()
    sanitized_anchors = []
    for anchor in extraction.date_anchors:
        if anchor.anchor_id in seen_ids:
            raise TemporalResolutionValidationError(
                f"duplicate temporal anchor id: {anchor.anchor_id}"
            )
        seen_ids.add(anchor.anchor_id)
        if not _contains_text(request.text, anchor.raw_text):
            raise TemporalResolutionValidationError(
                f"temporal anchor evidence is not present in the request: {anchor.raw_text!r}"
            )
        if anchor.year is not None and str(anchor.year) not in anchor.raw_text:
            anchor = anchor.model_copy(update={"year": None})
        sanitized_anchors.append(anchor)

    for phrase in extraction.temporal_phrases:
        if not _contains_text(request.text, phrase.raw_text):
            raise TemporalResolutionValidationError(
                f"temporal phrase evidence is not present in the request: {phrase.raw_text!r}"
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

    windows = [proposal.departure, proposal.return_date]
    for window in windows:
        if window is None:
            continue
        for supporting_text in window.supporting_text:
            if not _contains_text(request.text, supporting_text):
                raise TemporalResolutionValidationError(
                    "proposed date supporting text is not present in the request: "
                    f"{supporting_text!r}"
                )
    grounded_unresolved = [
        unresolved
        for unresolved in proposal.unresolved
        if _contains_text(request.text, unresolved.raw_text)
    ]
    proposal = proposal.model_copy(update={"unresolved": grounded_unresolved})

    duration = proposal.interpreted_duration
    if duration is not None and not _contains_text(request.text, duration.raw_text):
        raise TemporalResolutionValidationError(
            "interpreted duration evidence is not present in the request: "
            f"{duration.raw_text!r}"
        )

    proposal = _apply_authoritative_holiday_window(
        request,
        extraction,
        proposal,
        resolved_anchors,
    )

    request_text = request.text
    normalized_request = request_text.casefold()
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
