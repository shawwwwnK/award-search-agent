"""Raw-text-only temporal lexing for the deterministic compiler.

This module deliberately has no input from model extraction.  Its handles are local to a
single request and are useful for candidate selection only; they are not canonical IDs,
calendar values, or source offsets exposed to a model.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from typing import Literal

from award_agent.domain import (
    CoarseIntentExtraction,
    DurationModifier,
    ExactDateAnchor,
    Holiday,
    HolidayAnchor,
    MonthAnchor,
    RawRequest,
    TemporalAnchor,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalTarget,
    TemporalUnit,
)


@dataclass(frozen=True)
class GroundedClause:
    """A verbatim local clause, with offsets retained only for deterministic diagnostics."""

    handle: str
    text: str
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class LiteralAnchor:
    handle: str
    clause: GroundedClause
    kind: Literal["holiday", "exact_date", "month"]
    holiday: Holiday | None = None
    month: int | None = None
    day: int | None = None
    year: int | None = None
    target: TemporalTarget = TemporalTarget.DEPARTURE


@dataclass(frozen=True)
class DurationLiteral:
    clause: GroundedClause
    minimum: int
    maximum: int
    unit: TemporalUnit
    modifier: DurationModifier


@dataclass(frozen=True)
class TemporalScan:
    """Only facts literally harvested from ``RawRequest.text``.

    ``coarse_extraction`` is a compatibility projection for the existing deterministic
    enricher/evaluator.  It is constructed here, never accepted from Pass 1.
    """

    request_text: str
    clauses: tuple[GroundedClause, ...]
    anchors: tuple[LiteralAnchor, ...]
    durations: tuple[DurationLiteral, ...]
    coarse_extraction: CoarseIntentExtraction


_MONTHS = {name.casefold(): number for number, name in enumerate(calendar.month_name) if name}
_HOLIDAYS = {
    "labor day": Holiday.LABOR_DAY,
    "new year's": Holiday.NEW_YEARS_DAY,
    "new year": Holiday.NEW_YEARS_DAY,
    "thanksgiving": Holiday.THANKSGIVING,
    "christmas": Holiday.CHRISTMAS,
}
_NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def _target(text: str, start: int) -> TemporalTarget:
    """Use nearby endpoint cues; departure is the safe default for literal anchors."""

    lead = text[max(0, start - 45) : start].casefold()
    if re.search(r"\b(?:return|returning|back|come back)\b", lead):
        return TemporalTarget.RETURN
    return TemporalTarget.DEPARTURE


def _number(value: str) -> int:
    return int(value) if value.isdigit() else _NUMBER_WORDS[value.casefold()]


def _is_trip_duration_context(text: str, match: re.Match[str]) -> bool:
    """Require a local trip-span construction before admitting a duration literal.

    A bare amount after ``in`` is ordinarily a point offset (``Leave in 10 days``), not a
    trip length.  The scanner intentionally supports only the small grammar it can compile:
    ``for``/``stay`` or ``be back after`` immediately before the amount, or a hyphenated amount
    immediately naming a trip-like noun.  Other phrasings remain outside this deterministic
    grammar rather than being silently compiled as a duration.
    """

    before = text[: match.start()]
    after = text[match.end() :]
    return bool(
        re.search(r"\b(?:for|stay|staying|(?:be\s+)?back\s+after)\s*$", before, re.IGNORECASE)
        or re.match(r"\s*(?:trip|stay|vacation|holiday)\b", after, re.IGNORECASE)
    )


def scan_temporal_request(request: RawRequest) -> TemporalScan:
    """Harvest supported temporal literals directly from raw request text.

    This intentionally recognizes a bounded grammar only.  Unsupported wording is retained as
    an ``unsupported`` clause so the candidate factory can compile it to an explicit unresolved
    relation rather than silently widening it.
    """

    text = request.text
    clauses: list[GroundedClause] = []
    anchors: list[LiteralAnchor] = []
    durations: list[DurationLiteral] = []
    date_anchors: list[TemporalAnchor] = []
    phrases: list[TemporalPhrase] = []

    def clause(match: re.Match[str], kind: str) -> GroundedClause:
        item = GroundedClause(f"e{len(clauses)}", match.group(0), match.start(), match.end(), kind)
        clauses.append(item)
        return item

    # Holidays are anchors even when reference-only.  Candidate anchor scope determines whether
    # an anchor becomes a direct endpoint window.
    for match in re.finditer(
        r"\b(?:labor\s+day|new\s+year(?:'s)?|thanksgiving|christmas)\b", text, re.IGNORECASE
    ):
        item = clause(match, "holiday")
        holiday = _HOLIDAYS[match.group(0).casefold()]
        target = _target(text, match.start())
        anchor = LiteralAnchor(f"a{len(anchors)}", item, "holiday", holiday=holiday, target=target)
        anchors.append(anchor)
        date_anchors.append(
            HolidayAnchor(
                kind="holiday",
                anchor_id=anchor.handle,
                applies_to=target,
                raw_text=item.text,
                holiday=holiday,
            )
        )

    # Month/day before bare month so the month inside an exact date does not make a second anchor.
    exact_spans: list[tuple[int, int]] = []
    month_pattern = "|".join(re.escape(name) for name in _MONTHS)
    for match in re.finditer(
        rf"\b({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b",
        text,
        re.IGNORECASE,
    ):
        day = int(match.group(2))
        if not 1 <= day <= 31:
            continue
        item = clause(match, "exact_date")
        month = _MONTHS[match.group(1).casefold()]
        year = int(match.group(3)) if match.group(3) else None
        target = _target(text, match.start())
        anchor = LiteralAnchor(
            f"a{len(anchors)}", item, "exact_date", month=month, day=day, year=year, target=target
        )
        anchors.append(anchor)
        exact_spans.append((match.start(), match.end()))
        date_anchors.append(
            ExactDateAnchor(
                kind="exact_date",
                anchor_id=anchor.handle,
                applies_to=target,
                raw_text=item.text,
                month=month,
                day=day,
                year=year,
            )
        )
    for match in re.finditer(rf"\b({month_pattern})\b", text, re.IGNORECASE):
        if any(start <= match.start() < end for start, end in exact_spans):
            continue
        item = clause(match, "month")
        month = _MONTHS[match.group(1).casefold()]
        target = _target(text, match.start())
        anchor = LiteralAnchor(f"a{len(anchors)}", item, "month", month=month, target=target)
        anchors.append(anchor)
        date_anchors.append(
            MonthAnchor(
                kind="month",
                anchor_id=anchor.handle,
                applies_to=target,
                raw_text=item.text,
                month=month,
            )
        )

    number_words = "|".join(_NUMBER_WORDS)
    duration_re = re.compile(
        rf"\b(?:(about|around|approximately)\s+)?(\d+|{number_words})\s*(?:or\s+(\d+|{number_words})\s*)?[-\s]?(days?|weeks?|months?)\b",
        re.IGNORECASE,
    )
    for match in duration_re.finditer(text):
        if not _is_trip_duration_context(text, match):
            continue
        item = clause(match, "duration")
        first = _number(match.group(2))
        second = _number(match.group(3)) if match.group(3) else first
        unit = TemporalUnit(match.group(4).casefold().rstrip("s"))
        modifier = (
            DurationModifier.ALTERNATIVE
            if match.group(3)
            else (DurationModifier.APPROXIMATE if match.group(1) else DurationModifier.EXACT)
        )
        durations.append(
            DurationLiteral(item, min(first, second), max(first, second), unit, modifier)
        )
        phrases.append(
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text=item.text,
                claim_ids=[
                    TemporalEvidenceClaim.APPROXIMATE_DURATION
                    if modifier is DurationModifier.APPROXIMATE
                    else TemporalEvidenceClaim.DURATION
                ],
            )
        )

    # Whole semantic clauses used by the bounded candidate grammar.
    patterns = (
        (
            "holiday_weekend",
            r"\b(?:weekend\s+of\s+labor\s+day(?:\s+weekend)?|labor\s+day\s+weekend)\b",
        ),
        ("thursday_extension", r"\bthursday\s+(?:as\s+well|also)\b"),
        ("return_weekend_after", r"\b(?:the\s+)?weekend\s+afterwards\b"),
        ("relative_weekend_after_holiday", r"\b(two)\s+weekends?\s+after\s+thanksgiving\b"),
        ("christmas_period", r"\b(?:over|around|during)\s+christmas\b"),
        ("unbounded_after", r"\bafter\s+new\s+year(?:'s)?\b"),
        (
            "unbounded_before",
            r"\b(?:back|return(?:ing)?)\s+before\s+[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?\b",
        ),
        ("next_month", r"\bnext\s+month\b"),
        ("early_month", r"\bearly\s+[A-Za-z]+\b"),
        (
            "unsupported",
            # Non-contiguous choices deliberately have no finite-window policy.  Keep the
            # complete phrase (and its month anchor) unresolved rather than treating the
            # trailing month as a safe whole-month window.
            (
                r"\b(?:first|second|third|fourth|last)\s+and\s+(?:first|second|third|fourth|last)\s+weekends?\s+of\s+[A-Za-z]+\b"
                r"|\bfirst\s+week\s+of\s+[A-Za-z]+\b"
                r"|\bnext\s+(?:spring|summer|fall|autumn|winter)\b"
            ),
        ),
    )
    occupied = {(item.start, item.end) for item in clauses}
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if (match.start(), match.end()) in occupied:
                continue
            item = clause(match, kind)
            phrase_target = (
                TemporalPhraseTarget.RETURN
                if kind == "return_weekend_after"
                else TemporalPhraseTarget.DEPARTURE
            )
            claim = (
                TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY
                if kind == "thursday_extension"
                else (
                    TemporalEvidenceClaim.RETURN_PERIOD
                    if phrase_target is TemporalPhraseTarget.RETURN
                    else TemporalEvidenceClaim.DEPARTURE_PERIOD
                )
            )
            phrases.append(
                TemporalPhrase(
                    applies_to=phrase_target,
                    raw_text=item.text,
                    claim_ids=[claim],
                )
            )

    clauses.sort(key=lambda item: (item.start, item.end, item.kind))
    return TemporalScan(
        text,
        tuple(clauses),
        tuple(anchors),
        tuple(durations),
        CoarseIntentExtraction(date_anchors=date_anchors, temporal_phrases=phrases),
    )
