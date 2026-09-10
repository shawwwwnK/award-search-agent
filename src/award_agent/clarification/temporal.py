"""Deterministic temporal normalization for answer-message evidence only."""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from award_agent.clarification.interpreter import validate_message_span
from award_agent.domain import (
    AmendmentTarget,
    AnswerMessageSource,
    BlockingRequirement,
    BlockingRequirementKind,
    DateWindow,
    DateWindowPrecision,
    InterpretedDuration,
    MessageSpan,
    RequestContext,
    TemporalAmendment,
    TemporalContribution,
    TemporalContributionKind,
)
from award_agent.domain.clarification_session import SessionContractModel


class ClarificationTemporalNormalizationError(ValueError):
    """A grounded answer fact cannot be deterministically normalized."""


class AmbiguousClarificationTemporalAnswer(ClarificationTemporalNormalizationError):
    """The active requirements do not assign an answer date to one endpoint."""


class UnsupportedClarificationTemporalAnswer(ClarificationTemporalNormalizationError):
    """The answer contains temporal wording outside this deliberately small grammar."""


class ClarificationTemporalNormalization(SessionContractModel):
    """One or more source-keyed facts for later deterministic state reduction."""

    contributions: tuple[TemporalContribution, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_contribution_ids(self) -> ClarificationTemporalNormalization:
        identifiers = [item.contribution_id for item in self.contributions]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("normalized temporal contribution IDs must be unique")
        return self


_MONTHS = {name.casefold(): number for number, name in enumerate(calendar.month_name) if name}
_MONTH_PATTERN = "|".join(re.escape(name) for name in _MONTHS)
_NAMED_DATE = re.compile(
    rf"\b(?P<month>{_MONTH_PATTERN})\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{{4}}))?\b",
    re.IGNORECASE,
)
_NAMED_MONTH = re.compile(rf"\b(?P<month>{_MONTH_PATTERN})\b", re.IGNORECASE)
_ISO_DATE = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")
_SLASH_DATE = re.compile(r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{2}|\d{4}))?\b")
_DURATION = re.compile(
    r"\b(?:(?P<approx>about|around|approximately)\s+)?"
    r"(?P<quantity>\d+)\s*(?P<unit>days?|weeks?)\b",
    re.IGNORECASE,
)
_DEPARTURE_CUE = re.compile(
    r"\b(?:departure|depart(?:ing)?|leave|leaving|outbound|fly\s+out)\b", re.IGNORECASE
)
_RETURN_CUE = re.compile(
    r"\b(?:return(?:ing)?|back|come\s+back|inbound|fly\s+home)\b", re.IGNORECASE
)
_CORRECTION_CUE = re.compile(
    r"\b(?:actually|instead|rather|change|update|move|make|correct)\b", re.IGNORECASE
)
_WEEKDAYS = {name.casefold(): number for number, name in enumerate(calendar.day_name)}
_WEEKDAY_PATTERN = "|".join(re.escape(name) for name in _WEEKDAYS)
_THIS_WEEKEND = re.compile(r"\bthis\s+weekend\b", re.IGNORECASE)
_THIS_WEEKDAY = re.compile(
    rf"\bthis\s+(?P<weekday>{_WEEKDAY_PATTERN})\b", re.IGNORECASE
)
_ON_WEEKDAY = re.compile(rf"\bon\s+(?P<weekday>{_WEEKDAY_PATTERN})\b", re.IGNORECASE)
_NUMBERED_LINE = re.compile(r"^\s*(?P<ordinal>[1-9]\d*)\.\s+\S(?:.*\S)?\s*$")
_PHYSICAL_BOUNDARY = re.compile(r"[\n.!?;]")
_DISJUNCTION = re.compile(r"\b(?:or|either)\b", re.IGNORECASE)
_COORDINATOR = re.compile(r"\b(?:and|then)\b", re.IGNORECASE)


def _fact_span(amendment: TemporalAmendment, match: re.Match[str]) -> MessageSpan:
    occurrence = amendment.span.text.find(match.group(0))
    if occurrence < 0:
        raise ClarificationTemporalNormalizationError(
            "normalized fact is not grounded in answer span"
        )
    if amendment.span.text.find(match.group(0), occurrence + 1) >= 0:
        raise ClarificationTemporalNormalizationError(
            "repeated temporal fact requires a narrower answer evidence span"
        )
    return MessageSpan(
        message_id=amendment.span.message_id,
        start=amendment.span.start + occurrence,
        end=amendment.span.start + occurrence + len(match.group(0)),
        text=match.group(0),
    )


def _requirements_by_kind(
    requirements: tuple[BlockingRequirement, ...],
) -> set[BlockingRequirementKind]:
    return {item.kind for item in requirements}


def _endpoint_for_date(
    text: str,
    requirements: tuple[BlockingRequirement, ...],
) -> TemporalContributionKind:
    departure_cued = _DEPARTURE_CUE.search(text) is not None
    return_cued = _RETURN_CUE.search(text) is not None
    if departure_cued and return_cued:
        raise AmbiguousClarificationTemporalAnswer("answer contains both departure and return cues")
    if departure_cued:
        return TemporalContributionKind.DEPARTURE_WINDOW
    if return_cued:
        return TemporalContributionKind.RETURN_WINDOW

    # The deterministic fallback prompt lists requirements in the same order
    # passed to the interpreter.  A complete, numbered answer line therefore
    # has explicit, answer-local ownership without asking the model to infer
    # which endpoint a bare temporal phrase belongs to.  Do not accept a
    # number elsewhere in prose: doing so would turn incidental text into
    # endpoint ownership.
    numbered_line = _NUMBERED_LINE.fullmatch(text)
    if numbered_line is not None:
        ordinal = int(numbered_line.group("ordinal"))
        if ordinal > len(requirements):
            raise AmbiguousClarificationTemporalAnswer(
                "numbered answer item has no supplied requirement"
            )
        requirement = requirements[ordinal - 1]
        if requirement.kind is BlockingRequirementKind.DEPARTURE:
            return TemporalContributionKind.DEPARTURE_WINDOW
        if requirement.kind is BlockingRequirementKind.RETURN_OR_DURATION:
            return TemporalContributionKind.RETURN_WINDOW
        raise UnsupportedClarificationTemporalAnswer(
            "numbered answer item does not own a temporal requirement"
        )

    kinds = _requirements_by_kind(requirements)
    departure_active = BlockingRequirementKind.DEPARTURE in kinds
    return_active = BlockingRequirementKind.RETURN_OR_DURATION in kinds
    if departure_active == return_active:
        raise AmbiguousClarificationTemporalAnswer(
            "bare date needs one active endpoint requirement or an explicit endpoint cue"
        )
    return (
        TemporalContributionKind.DEPARTURE_WINDOW
        if departure_active
        else TemporalContributionKind.RETURN_WINDOW
    )


def _supported_fact_ranges(text: str) -> tuple[tuple[int, int], ...]:
    """Find non-overlapping facts in the deliberately small answer grammar.

    This is not a second parser: it is used only to avoid borrowing an
    endpoint cue across two facts in one physical answer segment.  Prefer a
    complete date over the named-month substring it contains.
    """

    candidates = [
        (match.start(), match.end())
        for pattern in (
            _ISO_DATE,
            _SLASH_DATE,
            _NAMED_DATE,
            _DURATION,
            _THIS_WEEKEND,
            _THIS_WEEKDAY,
            _ON_WEEKDAY,
            _NAMED_MONTH,
        )
        for match in pattern.finditer(text)
    ]
    ranges: list[tuple[int, int]] = []
    for candidate in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]))):
        if any(
            candidate[0] < existing[1] and existing[0] < candidate[1]
            for existing in ranges
        ):
            continue
        ranges.append(candidate)
    return tuple(sorted(ranges))


def _physical_segment(text: str, *, fact_start: int, fact_end: int) -> tuple[int, int]:
    """Keep cue repair inside the fact's answer line or sentence."""

    start = 0
    end = len(text)
    for boundary in _PHYSICAL_BOUNDARY.finditer(text):
        # ``1. This weekend`` is one numbered answer line, not two physical
        # segments. Do not apply that exception to ordinary sentences ending
        # in numeric dates such as ``2026-10-06.``.
        if boundary.group(0) == ".":
            line_start = text.rfind("\n", 0, boundary.start()) + 1
            if re.fullmatch(r"\s*[1-9]\d*", text[line_start : boundary.start()]):
                continue
        if boundary.end() <= fact_start:
            start = boundary.end()
        elif boundary.start() >= fact_end:
            end = boundary.start()
            break
    return start, end


def _repair_endpoint_ownership_text(
    *,
    amendment: TemporalAmendment,
    answer_text: str,
    fact: re.Match[str],
) -> str:
    """Return a same-answer clause only when its ownership is unambiguous.

    Models often retain just the literal temporal fact as the amendment span.
    A nearby endpoint cue is usable only inside the same physical segment. If
    that segment contains two supported facts, split it solely at a single
    coordinating word between them; alternatives and larger groups remain
    explicit ambiguity rather than becoming an inferred endpoint assignment.
    """

    fact_start = amendment.span.start + fact.start()
    fact_end = amendment.span.start + fact.end()
    segment_start, segment_end = _physical_segment(
        answer_text, fact_start=fact_start, fact_end=fact_end
    )
    segment = answer_text[segment_start:segment_end]
    if _DISJUNCTION.search(segment) is not None:
        raise AmbiguousClarificationTemporalAnswer(
            "answer segment contains a temporal alternative or disjunction"
        )

    local_fact = (fact_start - segment_start, fact_end - segment_start)
    facts = _supported_fact_ranges(segment)
    if local_fact not in facts:
        raise AmbiguousClarificationTemporalAnswer(
            "narrow amendment does not identify one supported answer fact"
        )
    if len(facts) == 1:
        return segment
    if len(facts) != 2:
        raise AmbiguousClarificationTemporalAnswer(
            "answer segment contains multiple temporal facts"
        )

    first, second = facts
    between = segment[first[1] : second[0]]
    coordinators = tuple(_COORDINATOR.finditer(between))
    if len(coordinators) != 1:
        raise AmbiguousClarificationTemporalAnswer(
            "two temporal facts need one explicit coordinator"
        )
    coordinator = coordinators[0]
    split = first[1] + coordinator.start()
    if local_fact == first:
        return segment[:split]
    return segment[split + len(coordinator.group(0)) :]


def _endpoint_for_temporal_amendment(
    *,
    amendment: TemporalAmendment,
    answer_text: str,
    requirements: tuple[BlockingRequirement, ...],
    fact: re.Match[str],
) -> TemporalContributionKind:
    """Resolve endpoint ownership, repairing only a narrow missing-cue span."""

    try:
        return _endpoint_for_date(amendment.span.text, requirements)
    except AmbiguousClarificationTemporalAnswer:
        kinds = _requirements_by_kind(requirements)
        if {
            BlockingRequirementKind.DEPARTURE,
            BlockingRequirementKind.RETURN_OR_DURATION,
        } - kinds:
            raise
        ordered_pair_endpoint = _ordered_pair_endpoint(
            amendment=amendment,
            answer_text=answer_text,
            requirements=requirements,
            fact=fact,
        )
        if ordered_pair_endpoint is not None:
            return ordered_pair_endpoint
        repair_text = _repair_endpoint_ownership_text(
            amendment=amendment,
            answer_text=answer_text,
            fact=fact,
        )
        return _endpoint_for_date(repair_text, requirements)


def _ordered_pair_endpoint(
    *,
    amendment: TemporalAmendment,
    answer_text: str,
    requirements: tuple[BlockingRequirement, ...],
    fact: re.Match[str],
) -> TemporalContributionKind | None:
    """Assign a simple ordered two-date reply to the two pending endpoints.

    A prompt always orders departure before return/duration.  A reply such as
    ``10/25 and 11/1`` is consequently unambiguous only when it is exactly two
    supported facts in one sentence/line joined by one ``and`` or ``then``.
    Endpoint labels, alternatives, extra facts, and swapped amendment targets
    still fail closed through the ordinary ownership checks.
    """

    if _DEPARTURE_CUE.search(amendment.span.text) or _RETURN_CUE.search(amendment.span.text):
        return None
    segment_start, segment_end = _physical_segment(
        answer_text,
        fact_start=amendment.span.start + fact.start(),
        fact_end=amendment.span.start + fact.end(),
    )
    segment = answer_text[segment_start:segment_end]
    if _DISJUNCTION.search(segment) is not None:
        return None
    facts = _supported_fact_ranges(segment)
    if len(facts) != 2:
        return None
    first, second = facts
    coordinators = tuple(_COORDINATOR.finditer(segment[first[1] : second[0]]))
    if len(coordinators) != 1:
        return None
    local_fact = (
        amendment.span.start + fact.start() - segment_start,
        amendment.span.start + fact.end() - segment_start,
    )
    if local_fact not in (first, second):
        return None
    ordered_temporal = tuple(
        requirement.kind
        for requirement in requirements
        if requirement.kind
        in {
            BlockingRequirementKind.DEPARTURE,
            BlockingRequirementKind.RETURN_OR_DURATION,
        }
    )
    if ordered_temporal != (
        BlockingRequirementKind.DEPARTURE,
        BlockingRequirementKind.RETURN_OR_DURATION,
    ):
        return None
    expected = (
        TemporalContributionKind.DEPARTURE_WINDOW
        if local_fact == first
        else TemporalContributionKind.RETURN_WINDOW
    )
    target = (
        AmendmentTarget.DEPARTURE
        if expected is TemporalContributionKind.DEPARTURE_WINDOW
        else AmendmentTarget.RETURN_OR_DURATION
    )
    if amendment.target is not target:
        raise ClarificationTemporalNormalizationError(
            "temporal amendment target does not match ordered date-pair ownership"
        )
    return expected


def _normal_date(match: re.Match[str], context: RequestContext) -> date:
    values = match.groupdict()
    month_value = values["month"]
    month = _MONTHS.get(month_value.casefold(), None)
    if month is None:
        month = int(month_value)
    day = int(values["day"])
    literal_year = values.get("year")
    if literal_year is None:
        year = context.reference_date.year
        try:
            candidate = date(year, month, day)
        except ValueError as exc:
            raise ClarificationTemporalNormalizationError(
                "invalid calendar date in answer"
            ) from exc
        return candidate if candidate >= context.reference_date else date(year + 1, month, day)
    year = int(literal_year)
    if len(literal_year) == 2:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ClarificationTemporalNormalizationError("invalid calendar date in answer") from exc


def _normal_month(match: re.Match[str], context: RequestContext) -> DateWindow:
    """Resolve a named month to its next available whole-month window.

    This deliberately mirrors the frozen initial path's named-month policy:
    an unspecified year is the current year unless the entire month has
    already elapsed under the original request context.
    """

    month = _MONTHS[match.group("month").casefold()]
    year = context.reference_date.year
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    if month_end < context.reference_date:
        year += 1
    return DateWindow(
        start=date(year, month, 1),
        end=date(year, month, calendar.monthrange(year, month)[1]),
        precision=DateWindowPrecision.MONTH,
        raw_text=match.group(0),
    )


def _date_match(text: str) -> re.Match[str] | None:
    matches = [
        match
        for pattern in (_ISO_DATE, _SLASH_DATE, _NAMED_DATE)
        for match in pattern.finditer(text)
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise AmbiguousClarificationTemporalAnswer("answer contains more than one date fact")
    return matches[0]


def recover_ordered_numeric_date_pair(
    *,
    message_id: str,
    text: str,
    requirements: tuple[BlockingRequirement, ...],
) -> tuple[TemporalAmendment, ...]:
    """Recover a literal ordered date pair that needs no semantic judgment.

    This covers a cooperative answer such as ``10/25 and 11/1`` when the
    pending temporal questions are departure followed by return/duration. It
    is intentionally limited to exactly two slash dates, one coordinator, and
    no other content, so it cannot convert prose alternatives or an arbitrary
    list of dates into hard constraints.
    """

    temporal_requirements = tuple(
        requirement
        for requirement in requirements
        if requirement.kind
        in {
            BlockingRequirementKind.DEPARTURE,
            BlockingRequirementKind.RETURN_OR_DURATION,
        }
    )
    if tuple(requirement.kind for requirement in temporal_requirements) != (
        BlockingRequirementKind.DEPARTURE,
        BlockingRequirementKind.RETURN_OR_DURATION,
    ):
        return ()
    matches = tuple(_SLASH_DATE.finditer(text))
    if len(matches) != 2:
        return ()
    first, second = matches
    if text[: first.start()].strip() or text[second.end() :].strip():
        return ()
    if re.fullmatch(r"\s+(?:and|then)\s+", text[first.end() : second.start()], re.IGNORECASE) is None:
        return ()

    def amendment(
        match: re.Match[str],
        *,
        target: Literal[
            AmendmentTarget.DEPARTURE,
            AmendmentTarget.RETURN_OR_DURATION,
        ],
        requirement: BlockingRequirement,
        ordinal: int,
    ) -> TemporalAmendment:
        quote = match.group(0)
        return TemporalAmendment(
            amendment_id=f"{message_id}:ordered-date-pair:{ordinal}",
            target=target,
            requirement_ids=(requirement.requirement_id,),
            span=MessageSpan(
                message_id=message_id,
                start=match.start(),
                end=match.end(),
                text=quote,
            ),
            temporal_text=quote,
        )

    return (
        amendment(
            first,
            target=AmendmentTarget.DEPARTURE,
            requirement=temporal_requirements[0],
            ordinal=1,
        ),
        amendment(
            second,
            target=AmendmentTarget.RETURN_OR_DURATION,
            requirement=temporal_requirements[1],
            ordinal=2,
        ),
    )


def _month_match(text: str) -> re.Match[str] | None:
    """Return one bare named month, excluding names already part of a date."""

    matches = [
        match
        for match in _NAMED_MONTH.finditer(text)
        if _NAMED_DATE.fullmatch(text[match.start() :]) is None
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise AmbiguousClarificationTemporalAnswer("answer contains more than one named month")
    return matches[0]


def _relative_temporal_match(text: str) -> re.Match[str] | None:
    """Return one supported answer-local relative calendar phrase.

    This deliberately recognizes only the small continuation grammar.  The
    frozen initial parser remains responsible for broader relative-time
    language; this path has the retained original request context but never
    delegates calendar arithmetic to the answer interpreter.
    """

    matches = [
        match
        for pattern in (_THIS_WEEKEND, _THIS_WEEKDAY, _ON_WEEKDAY)
        for match in pattern.finditer(text)
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise AmbiguousClarificationTemporalAnswer(
            "answer contains more than one supported relative temporal fact"
        )
    return matches[0]


def _normal_relative_temporal(match: re.Match[str], context: RequestContext) -> DateWindow:
    """Resolve one supported relative phrase against the immutable context."""

    phrase = match.group(0)
    if match.re is _THIS_WEEKEND:
        # Saturday through Sunday of the first weekend beginning on or after
        # the reference date.  On 2026-09-09, this is 2026-09-12..13.
        days_until_saturday = (calendar.SATURDAY - context.reference_date.weekday()) % 7
        start = date.fromordinal(context.reference_date.toordinal() + days_until_saturday)
        return DateWindow(
            start=start,
            end=date.fromordinal(start.toordinal() + 1),
            precision=DateWindowPrecision.WINDOW,
            raw_text=phrase,
        )

    weekday = _WEEKDAYS[match.group("weekday").casefold()]
    days_until_weekday = (weekday - context.reference_date.weekday()) % 7
    value = date.fromordinal(context.reference_date.toordinal() + days_until_weekday)
    return DateWindow(
        start=value,
        end=value,
        precision=DateWindowPrecision.EXACT,
        raw_text=phrase,
    )


def normalize_temporal_amendment(
    amendment: TemporalAmendment,
    *,
    answer_text: str,
    requirements: tuple[BlockingRequirement, ...],
    context: RequestContext,
) -> ClarificationTemporalNormalization:
    """Normalize one grounded answer fact under the original request context.

    It never scans or compiles the full conversation and intentionally supports
    only one explicit date or one day/week duration per amendment.  The reducer
    later decides how the resulting source-keyed contribution supersedes prior
    active contributions.
    """

    validate_message_span(
        message_id=amendment.span.message_id,
        text=answer_text,
        span=amendment.span,
    )
    if amendment.temporal_text not in amendment.span.text:
        raise ClarificationTemporalNormalizationError(
            "temporal amendment text is not grounded in its answer span"
        )
    duration_matches = list(_DURATION.finditer(amendment.temporal_text))
    date_match = _date_match(amendment.temporal_text)
    month_match = _month_match(amendment.temporal_text) if date_match is None else None
    relative_match = (
        _relative_temporal_match(amendment.temporal_text)
        if date_match is None and month_match is None
        else None
    )
    if duration_matches and any(item is not None for item in (date_match, month_match, relative_match)):
        raise AmbiguousClarificationTemporalAnswer("answer amendment mixes date and duration facts")
    if duration_matches:
        if len(duration_matches) != 1:
            raise AmbiguousClarificationTemporalAnswer(
                "answer contains more than one duration fact"
            )
        return_or_duration_active = (
            BlockingRequirementKind.RETURN_OR_DURATION in _requirements_by_kind(requirements)
        )
        explicit_duration_correction = (
            amendment.is_correction and _CORRECTION_CUE.search(amendment.span.text) is not None
        )
        if not return_or_duration_active and not explicit_duration_correction:
            raise UnsupportedClarificationTemporalAnswer(
                "a bare duration is accepted only while return/duration is active, "
                "or as an explicit correction"
            )
        if amendment.target not in {
            AmendmentTarget.RETURN_OR_DURATION,
            AmendmentTarget.CONFLICTING_DATES,
        }:
            raise ClarificationTemporalNormalizationError(
                "a duration amendment must target return/duration or a date conflict"
            )
        match = duration_matches[0]
        _fact_span(amendment, match)
        quantity = int(match.group("quantity"))
        multiplier = 1 if match.group("unit").casefold().startswith("day") else 7
        tolerance = 1 if match.group("approx") is not None else 0
        duration = InterpretedDuration(
            raw_text=match.group(0),
            minimum_days=max(1, quantity * multiplier - tolerance),
            maximum_days=quantity * multiplier + tolerance,
        )
        return ClarificationTemporalNormalization(
            contributions=(
                TemporalContribution(
                    contribution_id=f"answer:{amendment.amendment_id}:duration",
                    kind=TemporalContributionKind.DURATION,
                    # The ledger links a contribution to its retained typed
                    # amendment, whose span may include an endpoint cue around
                    # the narrower literal fact.
                    source=AnswerMessageSource(span=amendment.span),
                    raw_text=match.group(0),
                    amendment_id=amendment.amendment_id,
                    interpreted_duration=duration,
                ),
            )
        )
    if date_match is None and month_match is None and relative_match is None:
        raise UnsupportedClarificationTemporalAnswer(
            "supported clarification temporal grammar requires one numeric or named exact date, "
            "one named month, this weekend, this/on weekday, or one day/week duration"
        )
    # Endpoint cues may surround the date in a wider grounded span (for
    # example, ``depart October 6``) while the literal temporal fact remains
    # the narrower ``October 6``.  A model may instead retain only that fact.
    # In the latter case, use a strictly bounded same-answer clause to recover
    # a local cue; provenance still remains the original narrow amendment span.
    fact = date_match or month_match or relative_match
    assert fact is not None
    kind = _endpoint_for_temporal_amendment(
        amendment=amendment,
        answer_text=answer_text,
        requirements=requirements,
        fact=fact,
    )
    endpoint = (
        AmendmentTarget.DEPARTURE
        if kind is TemporalContributionKind.DEPARTURE_WINDOW
        else AmendmentTarget.RETURN_OR_DURATION
    )
    if amendment.target not in {endpoint, AmendmentTarget.CONFLICTING_DATES}:
        raise ClarificationTemporalNormalizationError(
            "temporal amendment target does not match its deterministic endpoint ownership"
        )
    if date_match is not None:
        value = _normal_date(date_match, context)
        _fact_span(amendment, date_match)
        window = DateWindow(
            start=value,
            end=value,
            precision=DateWindowPrecision.EXACT,
            raw_text=date_match.group(0),
        )
    elif month_match is not None:
        _fact_span(amendment, month_match)
        window = _normal_month(month_match, context)
    else:
        assert relative_match is not None
        _fact_span(amendment, relative_match)
        window = _normal_relative_temporal(relative_match, context)
    return ClarificationTemporalNormalization(
        contributions=(
            TemporalContribution(
                contribution_id=f"answer:{amendment.amendment_id}:{kind.value}",
                kind=kind,
                source=AnswerMessageSource(span=amendment.span),
                raw_text=window.raw_text,
                amendment_id=amendment.amendment_id,
                date_window=window,
            ),
        )
    )


__all__ = [
    "AmbiguousClarificationTemporalAnswer",
    "ClarificationTemporalNormalization",
    "ClarificationTemporalNormalizationError",
    "UnsupportedClarificationTemporalAnswer",
    "normalize_temporal_amendment",
    "recover_ordered_numeric_date_pair",
]
