"""Accepting, clarification-only temporal approximations (ADR 0012).

This sibling registry deliberately does not alter the frozen request-intent
compiler or the v1 relative-time registry.  A model chooses opaque handles
against answer-local text; this module owns every calendar calculation and the
small, versioned set of meanings that can be accepted as an assumption.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from award_agent.domain import (
    AmendmentTarget,
    AssumptionDisclosure,
    BlockingRequirement,
    BlockingRequirementKind,
    DateWindow,
    DateWindowPrecision,
    InterpretedDuration,
    MessageSpan,
    RequestContext,
    TemporalAnswerInterpretationProvenance,
)
from award_agent.domain.clarification_session import SessionContractModel

REGISTRY_VERSION = "clarification-accepting-temporal-v1"


class ClarificationTemporalApproximationError(ValueError):
    """An accepting temporal selection cannot be compiled safely."""


class ClarificationTemporalApproximationChoice(SessionContractModel):
    handle: str = Field(pattern=r"^a\d+$")
    affordance: str = Field(min_length=1, max_length=220)


class ClarificationTemporalApproximationProjection(SessionContractModel):
    registry_version: str = Field(min_length=1)
    choices: tuple[ClarificationTemporalApproximationChoice, ...] = ()

    @model_validator(mode="after")
    def validate_choices(self) -> ClarificationTemporalApproximationProjection:
        handles = [item.handle for item in self.choices]
        if len(handles) != len(set(handles)):
            raise ValueError("temporal approximation choice handles must be unique")
        return self


class ClarificationTemporalApproximationBinding(SessionContractModel):
    """One answer-local fuzzy fact and its selected, opaque affordance."""

    approximation_handle: str = Field(pattern=r"^a\d+$")
    span: MessageSpan
    # Closed symbolic slots selected by the model.  The *surface wording* is
    # deliberately open: deterministic code verifies only that these slots
    # are literally grounded in the answer span, then owns the calendar work.
    month_reference: Literal["named_month", "next_month"] | None = None
    month_name: str | None = Field(default=None, pattern=r"^[a-z]+$")
    # This is only useful for a correction of a field no longer active. It is
    # validated against a literal correction cue and local endpoint wording.
    is_correction: bool = False


class ClarificationTemporalApproximationUnresolved(SessionContractModel):
    span: MessageSpan
    requirement_ids: tuple[str, ...] = ()
    reason: Literal["ambiguous", "unsupported"] = "unsupported"

    @model_validator(mode="after")
    def validate_requirement_ids(self) -> ClarificationTemporalApproximationUnresolved:
        if len(self.requirement_ids) != len(set(self.requirement_ids)):
            raise ValueError("unresolved approximation requirement IDs must be unique")
        return self


class ClarificationTemporalApproximationSelection(SessionContractModel):
    selected: tuple[ClarificationTemporalApproximationBinding, ...] = ()
    unresolved: tuple[ClarificationTemporalApproximationUnresolved, ...] = ()
    complete: bool = False

    @model_validator(mode="after")
    def validate_spans(self) -> ClarificationTemporalApproximationSelection:
        spans = [(item.span.start, item.span.end) for item in self.selected]
        spans.extend((item.span.start, item.span.end) for item in self.unresolved)
        if len(spans) != len(set(spans)):
            raise ValueError("temporal approximation classification spans must be unique")
        if any(
            left[0] < right[1] and right[0] < left[1]
            for index, left in enumerate(spans)
            for right in spans[index + 1 :]
        ):
            raise ValueError("temporal approximation classification spans must not overlap")
        return self


@dataclass(frozen=True, slots=True)
class ClarificationTemporalApproximationCandidate:
    candidate_id: str
    span: MessageSpan
    target: AmendmentTarget
    requirement_id: str | None
    is_correction: bool
    approximation_handle: str


@dataclass(frozen=True, slots=True)
class CompiledTemporalApproximationFact:
    candidate: ClarificationTemporalApproximationCandidate
    interpretation_id: str
    window: DateWindow | None
    duration: InterpretedDuration | None
    provenance: TemporalAnswerInterpretationProvenance


@dataclass(frozen=True, slots=True)
class _Approximation:
    interpretation_id: str
    handle: str
    affordance: str
    mode: Literal["early", "mid", "late", "week", "approx_week"]


_APPROXIMATIONS = (
    _Approximation("month_early_1_10", "a1", "the early bounded portion of one explicitly named or next month", "early"),
    _Approximation("month_mid_11_20", "a2", "the middle bounded portion of one explicitly named or next month", "mid"),
    _Approximation("month_late_21_end", "a3", "the late bounded portion of one explicitly named or next month", "late"),
    _Approximation("one_week_exact_7", "a4", "an ordinary one-week duration", "week"),
    _Approximation("about_one_week_6_8", "a5", "an explicitly approximate one-week duration", "approx_week"),
)
_BY_HANDLE = {item.handle: item for item in _APPROXIMATIONS}
_MONTHS = {name.casefold(): number for number, name in enumerate(calendar.month_name) if name}
_MONTH_PATTERN = "|".join(_MONTHS)
_MONTH_WORD = re.compile(rf"\b(?P<month>{_MONTH_PATTERN})\b", re.IGNORECASE)
_NEXT_MONTH = re.compile(r"\bnext\s+month\b", re.IGNORECASE)
_WEEK_WORD = re.compile(r"\bweek\b", re.IGNORECASE)
_NON_DISJUNCTION_TEXT = r"(?:(?!\b(?:or|either)\b)[^\n])"
_MONTH_PORTION = re.compile(
    rf"\b(?:early|mid(?:dle)?|late|beginning|start|end)\b"
    rf"{_NON_DISJUNCTION_TEXT}{{0,32}}?\b(?:{_MONTH_PATTERN}|next\s+month)\b",
    re.IGNORECASE,
)
_ORDINARY_WEEK = re.compile(r"\b(?:about\s+)?(?:a|one)\s+week\b", re.IGNORECASE)
_LEGACY_NAMED_MONTH = rf"(?:in\s+)?(?:{_MONTH_PATTERN})"
_LEGACY_NAMED_DATE = rf"(?:{_MONTH_PATTERN})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?"
_LEGACY_ISO_DATE = r"\d{4}-\d{1,2}-\d{1,2}"
_LEGACY_SLASH_DATE = r"\d{1,2}/\d{1,2}(?:/\d{2,4})?"
_LEGACY_DATE_TOKEN = (
    rf"(?:{_LEGACY_NAMED_DATE}|{_LEGACY_ISO_DATE}|{_LEGACY_SLASH_DATE}|{_LEGACY_NAMED_MONTH})"
)
_LEGACY_UNRESOLVED_SURFACE = re.compile(
    rf"\s*(?:either\s+)?{_LEGACY_DATE_TOKEN}(?:\s+or\s+{_LEGACY_DATE_TOKEN})*\s*[?.!]*\s*",
    re.IGNORECASE,
)
_DISJUNCTION = re.compile(r"\b(?:or|either)\b", re.IGNORECASE)
_CORRECTION = re.compile(r"\b(?:actually|instead|rather|change|update|move|make|correct)\b", re.IGNORECASE)
_DEPARTURE = re.compile(r"\b(?:departure|depart(?:ing)?|leave|leaving|outbound|fly\s+out)\b", re.IGNORECASE)
_RETURN = re.compile(r"\b(?:return(?:ing)?|back|come\s+back|inbound|fly\s+home)\b", re.IGNORECASE)
_NUMBERED_LINE = re.compile(r"^\s*(?P<ordinal>[1-9]\d*)\.\s+\S(?:.*\S)?\s*$")


def global_temporal_approximation_projection() -> ClarificationTemporalApproximationProjection:
    return ClarificationTemporalApproximationProjection(
        registry_version=REGISTRY_VERSION,
        choices=tuple(
            ClarificationTemporalApproximationChoice(handle=item.handle, affordance=item.affordance)
            for item in _APPROXIMATIONS
        ),
    )


def harvest_temporal_approximation_projection(**_: object) -> ClarificationTemporalApproximationProjection:
    return global_temporal_approximation_projection()


def _looks_temporal(text: str) -> bool:
    """A minimal grounding guard, intentionally not a phrase grammar."""

    return bool(_MONTH_WORD.search(text) or _NEXT_MONTH.search(text) or _WEEK_WORD.search(text))


def approximation_coverage_cues(text: str) -> tuple[re.Match[str], ...]:
    """Return phrases the accepting registry must classify.

    A bare named month remains legacy temporal wording. This registry's
    coverage obligation starts only at a month portion or an ordinary one-week
    duration, so the two registries can be checked as a union without turning
    every explicit date/month answer into an approximation task.
    """

    return tuple(sorted(
        (*_MONTH_PORTION.finditer(text), *_ORDINARY_WEEK.finditer(text)),
        key=lambda match: (match.start(), match.end()),
    ))


def approximation_selectable_surface(text: str) -> bool:
    """Whether wording belongs to the accepting month/week registry."""

    return bool(approximation_coverage_cues(text))


def bare_named_month_surface(text: str) -> bool:
    """Recognize a bare month that has no accepting-registry affordance."""

    return re.fullmatch(rf"\s*(?:in\s+)?(?:{_MONTH_PATTERN})\s*[?.!]*\s*", text, re.IGNORECASE) is not None


def legacy_unresolved_surface(text: str) -> bool:
    """Recognize bounded legacy month/date wording without assigning meaning."""

    return _LEGACY_UNRESOLVED_SURFACE.fullmatch(text) is not None


def _line(text: str, start: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    return text[line_start:] if line_end < 0 else text[line_start:line_end]


def _target_for_span(
    text: str,
    span: MessageSpan,
    requirements: tuple[BlockingRequirement, ...],
    *,
    correction: bool,
    duration: bool,
) -> tuple[AmendmentTarget, str | None]:
    line = _line(text, span.start)
    if duration:
        requirement = next(
            (item for item in requirements if item.kind is BlockingRequirementKind.RETURN_OR_DURATION),
            None,
        )
        if requirement is not None:
            return AmendmentTarget.RETURN_OR_DURATION, requirement.requirement_id
        if correction and _RETURN.search(line):
            return AmendmentTarget.RETURN_OR_DURATION, None
        raise ClarificationTemporalApproximationError(
            "week duration needs an active return/duration requirement or explicit return correction"
        )

    numbered = _NUMBERED_LINE.fullmatch(line)
    if numbered is not None:
        ordinal = int(numbered.group("ordinal"))
        if ordinal <= len(requirements):
            requirement = requirements[ordinal - 1]
            if requirement.kind is BlockingRequirementKind.DEPARTURE:
                return AmendmentTarget.DEPARTURE, requirement.requirement_id
            if requirement.kind is BlockingRequirementKind.RETURN_OR_DURATION:
                return AmendmentTarget.RETURN_OR_DURATION, requirement.requirement_id
    departure, returned = bool(_DEPARTURE.search(line)), bool(_RETURN.search(line))
    if departure != returned:
        target = AmendmentTarget.DEPARTURE if departure else AmendmentTarget.RETURN_OR_DURATION
        selected_requirement: BlockingRequirement | None = next(
            (item for item in requirements if item.kind is (
                BlockingRequirementKind.DEPARTURE if target is AmendmentTarget.DEPARTURE else BlockingRequirementKind.RETURN_OR_DURATION
            )),
            None,
        )
        if selected_requirement is not None:
            return target, selected_requirement.requirement_id
        if correction:
            return target, None
    temporal = tuple(item for item in requirements if item.kind in {
        BlockingRequirementKind.DEPARTURE, BlockingRequirementKind.RETURN_OR_DURATION
    })
    if len(temporal) == 1:
        item = temporal[0]
        return (
            AmendmentTarget.DEPARTURE if item.kind is BlockingRequirementKind.DEPARTURE else AmendmentTarget.RETURN_OR_DURATION,
            item.requirement_id,
        )
    if departure and returned:
        relative = span.start - (text.rfind("\n", 0, span.start) + 1)
        cues = tuple(_DEPARTURE.finditer(line)), tuple(_RETURN.finditer(line))
        distance = lambda items: min(
            min(abs(relative - item.start()), abs(relative - item.end())) for item in items
        )
        departure_distance, return_distance = distance(cues[0]), distance(cues[1])
        if departure_distance != return_distance:
            target = (
                AmendmentTarget.DEPARTURE
                if departure_distance < return_distance
                else AmendmentTarget.RETURN_OR_DURATION
            )
            required_kind = (
                BlockingRequirementKind.DEPARTURE
                if target is AmendmentTarget.DEPARTURE
                else BlockingRequirementKind.RETURN_OR_DURATION
            )
            selected_requirement = next(
                (item for item in requirements if item.kind is required_kind), None
            )
            if selected_requirement is not None:
                return target, selected_requirement.requirement_id
    if correction and departure != returned:
        return (AmendmentTarget.DEPARTURE if departure else AmendmentTarget.RETURN_OR_DURATION), None
    raise ClarificationTemporalApproximationError("accepting temporal span has no deterministic endpoint ownership")


def validate_temporal_approximation_selection(
    projection: ClarificationTemporalApproximationProjection,
    selection: ClarificationTemporalApproximationSelection,
    *,
    text: str | None = None,
    requirements: tuple[BlockingRequirement, ...] | None = None,
    additional_classified_spans: tuple[MessageSpan, ...] = (),
    require_coverage: bool = False,
) -> None:
    if projection.registry_version != REGISTRY_VERSION:
        raise ClarificationTemporalApproximationError("unsupported temporal approximation registry version")
    if not selection.complete:
        raise ClarificationTemporalApproximationError("temporal approximation selection must declare complete classification")
    handles = {item.handle for item in projection.choices}
    if any(item.approximation_handle not in handles for item in selection.selected):
        raise ClarificationTemporalApproximationError("temporal approximation selection contains an unknown choice handle")
    for binding in selection.selected:
        choice = _BY_HANDLE[binding.approximation_handle]
        if not _looks_temporal(binding.span.text):
            raise ClarificationTemporalApproximationError("selected approximation span has no temporal grounding")
        if choice.mode in {"early", "mid", "late"}:
            if binding.month_reference is None:
                raise ClarificationTemporalApproximationError("month portion selection requires a month reference slot")
            if binding.month_reference == "named_month":
                if binding.month_name not in _MONTHS or not any(
                    match.group("month").casefold() == binding.month_name
                    for match in _MONTH_WORD.finditer(binding.span.text)
                ):
                    raise ClarificationTemporalApproximationError("named month slot is not grounded in its answer span")
            elif binding.month_name is not None or _NEXT_MONTH.search(binding.span.text) is None:
                raise ClarificationTemporalApproximationError("next-month slot is not grounded in its answer span")
        elif binding.month_reference is not None or binding.month_name is not None:
            raise ClarificationTemporalApproximationError("week duration cannot carry month slots")
        if choice.mode in {"week", "approx_week"} and _WEEK_WORD.search(binding.span.text) is None:
            raise ClarificationTemporalApproximationError("week duration handle is not grounded in its answer span")
        if binding.is_correction:
            correction_source = binding.span.text
            if text is not None:
                correction_source = _line(text, binding.span.start)
            if _CORRECTION.search(correction_source) is None:
                raise ClarificationTemporalApproximationError("approximation correction requires an explicit correction cue")
    if text is not None:
        if any(not _looks_temporal(item.span.text) for item in selection.unresolved):
            raise ClarificationTemporalApproximationError("unresolved approximation span must contain a supported cue")
        classified = (
            tuple(item.span for item in selection.selected)
            + tuple(item.span for item in selection.unresolved)
            + additional_classified_spans
        )
        if require_coverage:
            missing = [
                match.group(0)
                for match in approximation_coverage_cues(text)
                if not any(span.start <= match.start() and match.end() <= span.end for span in classified)
            ]
            if missing:
                raise ClarificationTemporalApproximationError(
                    "approximation selection does not classify every accepting temporal cue"
                )
    if requirements is not None:
        temporal_ids = {
            item.requirement_id
            for item in requirements
            if item.kind
            in {
                BlockingRequirementKind.DEPARTURE,
                BlockingRequirementKind.RETURN_OR_DURATION,
            }
        }
        for item in selection.unresolved:
            if not item.requirement_ids:
                raise ClarificationTemporalApproximationError(
                    "unresolved approximation span requires active temporal requirement IDs"
                )
            if not set(item.requirement_ids).issubset(temporal_ids):
                raise ClarificationTemporalApproximationError(
                    "unresolved approximation span links an inactive or non-temporal requirement"
                )


def unresolved_approximation_rejections(
    selection: ClarificationTemporalApproximationSelection,
) -> tuple[tuple[MessageSpan, tuple[str, ...], Literal["ambiguous", "unsupported"], str], ...]:
    return tuple(
        (
            item.span,
            item.requirement_ids,
            item.reason,
            f"{REGISTRY_VERSION}.unresolved.{item.reason}",
        )
        for item in selection.unresolved
    )


def _month_number(
    binding: ClarificationTemporalApproximationBinding, context: RequestContext, end_day: int
) -> tuple[int, int]:
    if binding.month_reference == "next_month":
        month = context.reference_date.month + 1
        return (context.reference_date.year + (month == 13), 1 if month == 13 else month)
    assert binding.month_reference == "named_month" and binding.month_name is not None
    month = _MONTHS[binding.month_name]
    year = context.reference_date.year
    if month < context.reference_date.month or (
        month == context.reference_date.month and end_day < context.reference_date.day
    ):
        year += 1
    return year, month


def _disclosed(phrase: str, meaning: str, candidate_id: str) -> TemporalAnswerInterpretationProvenance:
    return TemporalAnswerInterpretationProvenance(
        policy_version=REGISTRY_VERSION,
        interpretation_id=meaning,
        candidate_ids=(candidate_id,),
        assumption_disclosure=AssumptionDisclosure(
            disclosure_id=f"assumption:{candidate_id}",
            message=f'I’ll interpret “{phrase}” as {meaning.replace("_", " ")}.',
        ),
    )


def compile_temporal_approximation_selection(
    projection: ClarificationTemporalApproximationProjection,
    selection: ClarificationTemporalApproximationSelection,
    *,
    context: RequestContext,
    text: str,
    requirements: tuple[BlockingRequirement, ...],
) -> tuple[CompiledTemporalApproximationFact, ...]:
    validate_temporal_approximation_selection(
        projection, selection, text=text, requirements=requirements
    )
    facts: list[CompiledTemporalApproximationFact] = []
    for ordinal, binding in enumerate(sorted(selection.selected, key=lambda item: item.span.start)):
        choice = _BY_HANDLE[binding.approximation_handle]
        if _DISJUNCTION.search(_line(text, binding.span.start)):
            raise ClarificationTemporalApproximationError("a discrete temporal alternative remains unresolved")
        target, requirement_id = _target_for_span(
            text,
            binding.span,
            requirements,
            correction=binding.is_correction,
            duration=choice.mode in {"week", "approx_week"},
        )
        candidate = ClarificationTemporalApproximationCandidate(
            candidate_id=f"{binding.span.message_id}:a{ordinal}", span=binding.span, target=target,
            requirement_id=requirement_id, is_correction=binding.is_correction,
            approximation_handle=binding.approximation_handle,
        )
        if choice.mode in {"early", "mid", "late"}:
            start_day, end_day = {"early": (1, 10), "mid": (11, 20), "late": (21, 31)}[choice.mode]
            year, month = _month_number(binding, context, end_day)
            end_of_month = calendar.monthrange(year, month)[1]
            window = DateWindow(
                start=date(year, month, start_day), end=date(year, month, min(end_day, end_of_month)),
                precision=DateWindowPrecision.WINDOW, raw_text=binding.span.text,
            )
            meaning = f"{calendar.month_name[month]} {start_day}–{min(end_day, end_of_month)}, {year}"
            facts.append(CompiledTemporalApproximationFact(
                candidate=candidate, interpretation_id=choice.interpretation_id, window=window, duration=None,
                provenance=_disclosed(binding.span.text, meaning, candidate.candidate_id),
            ))
        else:
            if target is not AmendmentTarget.RETURN_OR_DURATION:
                raise ClarificationTemporalApproximationError("week duration must resolve return or duration")
            minimum, maximum = (7, 7) if choice.mode == "week" else (6, 8)
            duration = InterpretedDuration(raw_text=binding.span.text, minimum_days=minimum, maximum_days=maximum)
            meaning = "7 days" if minimum == maximum else "6–8 days"
            facts.append(CompiledTemporalApproximationFact(
                candidate=candidate, interpretation_id=choice.interpretation_id, window=None, duration=duration,
                provenance=_disclosed(binding.span.text, meaning, candidate.candidate_id),
            ))
    return tuple(facts)


__all__ = [
    "REGISTRY_VERSION",
    "ClarificationTemporalApproximationBinding",
    "ClarificationTemporalApproximationCandidate",
    "ClarificationTemporalApproximationChoice",
    "ClarificationTemporalApproximationError",
    "ClarificationTemporalApproximationProjection",
    "ClarificationTemporalApproximationSelection",
    "ClarificationTemporalApproximationUnresolved",
    "CompiledTemporalApproximationFact",
    "approximation_coverage_cues",
    "approximation_selectable_surface",
    "bare_named_month_surface",
    "compile_temporal_approximation_selection",
    "global_temporal_approximation_projection",
    "harvest_temporal_approximation_projection",
    "legacy_unresolved_surface",
    "unresolved_approximation_rejections",
    "validate_temporal_approximation_selection",
]
