"""Deterministic temporal normalization for answer-message evidence only."""

from __future__ import annotations

import calendar
import re
from datetime import date

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


_MONTHS = {
    name.casefold(): number
    for number, name in enumerate(calendar.month_name)
    if name
}
_MONTH_PATTERN = "|".join(re.escape(name) for name in _MONTHS)
_NAMED_DATE = re.compile(
    rf"\b(?P<month>{_MONTH_PATTERN})\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{{4}}))?\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")
_SLASH_DATE = re.compile(
    r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{2}|\d{4}))?\b"
)
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


def _fact_span(amendment: TemporalAmendment, match: re.Match[str]) -> MessageSpan:
    occurrence = amendment.span.text.find(match.group(0))
    if occurrence < 0:
        raise ClarificationTemporalNormalizationError("normalized fact is not grounded in answer span")
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
            raise ClarificationTemporalNormalizationError("invalid calendar date in answer") from exc
        return candidate if candidate >= context.reference_date else date(year + 1, month, day)
    year = int(literal_year)
    if len(literal_year) == 2:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ClarificationTemporalNormalizationError("invalid calendar date in answer") from exc


def _date_match(text: str) -> re.Match[str] | None:
    matches = [match for pattern in (_ISO_DATE, _SLASH_DATE, _NAMED_DATE) for match in pattern.finditer(text)]
    if not matches:
        return None
    if len(matches) != 1:
        raise AmbiguousClarificationTemporalAnswer("answer contains more than one date fact")
    return matches[0]


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
    if duration_matches and date_match is not None:
        raise AmbiguousClarificationTemporalAnswer("answer amendment mixes date and duration facts")
    if duration_matches:
        if len(duration_matches) != 1:
            raise AmbiguousClarificationTemporalAnswer("answer contains more than one duration fact")
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
    if date_match is None:
        raise UnsupportedClarificationTemporalAnswer(
            "supported clarification temporal grammar requires one numeric or named exact date, "
            "or one day/week duration"
        )
    # Endpoint cues may surround the date in a wider grounded span (for
    # example, ``depart October 6``) while the literal temporal fact remains
    # the narrower ``October 6``.  Use the former for ownership, never an
    # ungrounded whole-message guess.
    kind = _endpoint_for_date(amendment.span.text, requirements)
    endpoint = (
        AmendmentTarget.DEPARTURE
        if kind is TemporalContributionKind.DEPARTURE_WINDOW
        else AmendmentTarget.RETURN_OR_DURATION
    )
    if amendment.target not in {endpoint, AmendmentTarget.CONFLICTING_DATES}:
        raise ClarificationTemporalNormalizationError(
            "temporal amendment target does not match its deterministic endpoint ownership"
        )
    value = _normal_date(date_match, context)
    _fact_span(amendment, date_match)
    window = DateWindow(
        start=value,
        end=value,
        precision=DateWindowPrecision.EXACT,
        raw_text=date_match.group(0),
    )
    return ClarificationTemporalNormalization(
        contributions=(
            TemporalContribution(
                contribution_id=f"answer:{amendment.amendment_id}:{kind.value}",
                kind=kind,
                    source=AnswerMessageSource(span=amendment.span),
                    raw_text=date_match.group(0),
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
]
