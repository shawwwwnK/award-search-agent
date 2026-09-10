"""Date-free, clarification-only relative-time template selection.

This is deliberately *not* a phrase scanner. The model receives a small,
fixed catalog of opaque, distinguishable operator affordances and grounds the
answer-local spans to which they apply. The catalog contains no dates,
request context, evaluator fixture identifiers, or template names. All slot
ownership, dependency validation, and calendar evaluation happen after the
model boundary in this module.
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
    BlockingRequirement,
    BlockingRequirementKind,
    DateWindow,
    DateWindowPrecision,
    MessageSpan,
    RequestContext,
)
from award_agent.domain.clarification_session import SessionContractModel

REGISTRY_VERSION = "clarification-temporal-templates-v2"


class ClarificationTemporalTemplateError(ValueError):
    """A template selection cannot be compiled safely."""


class ClarificationTemporalTemplateChoice(SessionContractModel):
    """One model-visible, date-free approved operator affordance."""

    handle: str = Field(pattern=r"^h\d+$")
    affordance: str = Field(min_length=1, max_length=220)


class ClarificationTemporalTemplateProjection(SessionContractModel):
    """Static global selector catalog exposed to the answer model."""

    registry_version: str = Field(min_length=1)
    choices: tuple[ClarificationTemporalTemplateChoice, ...] = ()

    @model_validator(mode="after")
    def validate_choices(self) -> ClarificationTemporalTemplateProjection:
        handles = [item.handle for item in self.choices]
        if len(handles) != len(set(handles)):
            raise ValueError("temporal template choice handles must be unique")
        return self


class ClarificationTemporalTemplateBinding(SessionContractModel):
    """A model-grounded answer span paired with one opaque choice handle."""

    template_handle: str = Field(pattern=r"^h\d+$")
    span: MessageSpan
    weekday: str | None = Field(default=None, pattern=r"^[a-z]+$")


class ClarificationTemporalTemplateUnresolved(SessionContractModel):
    """An answer-local temporal-looking span with no approved interpretation."""

    span: MessageSpan
    requirement_ids: tuple[str, ...] = ()
    reason: Literal["ambiguous", "unsupported"] = "unsupported"

    @model_validator(mode="after")
    def validate_requirement_ids(self) -> ClarificationTemporalTemplateUnresolved:
        if len(self.requirement_ids) != len(set(self.requirement_ids)):
            raise ValueError("unresolved template requirement IDs must be unique")
        return self


class ClarificationTemporalTemplateSelection(SessionContractModel):
    """Complete model classification of answer-local relative-time spans."""

    selected: tuple[ClarificationTemporalTemplateBinding, ...] = ()
    unresolved: tuple[ClarificationTemporalTemplateUnresolved, ...] = ()
    # The production Structured Output field is required and must be true.
    complete: bool = False

    @model_validator(mode="after")
    def validate_unique_spans(self) -> ClarificationTemporalTemplateSelection:
        spans = [(item.span.start, item.span.end) for item in self.selected]
        spans.extend((item.span.start, item.span.end) for item in self.unresolved)
        if len(spans) != len(set(spans)):
            raise ValueError("template classification spans must be unique")
        if any(
            left[0] < right[1] and right[0] < left[1]
            for index, left in enumerate(spans)
            for right in spans[index + 1 :]
        ):
            raise ValueError("template classification spans must not overlap")
        return self


@dataclass(frozen=True, slots=True)
class ClarificationTemporalCandidate:
    """Deterministic post-selection candidate; never model-visible."""

    candidate_id: str
    candidate_group_id: str
    unresolved_candidate_id: str
    span: MessageSpan
    requirement_id: str
    dependency_candidate_ids: tuple[str, ...]
    template_handle: str


@dataclass(frozen=True, slots=True)
class CompiledTemporalTemplateFact:
    candidate: ClarificationTemporalCandidate
    template_id: str
    window: DateWindow


@dataclass(frozen=True, slots=True)
class _Template:
    template_id: str
    handle: str
    affordance: str
    mode: str
    requires_weekday: bool = False


_WEEKDAYS = {name.casefold(): number for number, name in enumerate(calendar.day_name)}
_TEMPLATES = (
    _Template("next_weekend", "h1", "a weekend explicitly described as next: the weekend after the upcoming weekend", "next_weekend"),
    _Template("this_weekend", "h2", "a weekend explicitly described as this: the upcoming/current weekend", "this_weekend"),
    _Template("next_weekday", "h3", "a named weekday directly qualified by next, or anchored by an explicit next/following week phrase: that weekday in the next calendar week", "next_weekday", True),
    _Template("this_weekday", "h4", "a named weekday explicitly described as this: that weekday in the current calendar week", "this_weekday", True),
    _Template("on_weekday", "h5", "a named weekday with no this/next qualifier: its first upcoming occurrence", "on_weekday", True),
    _Template("weekday_afterwards", "h6", "a named weekday described as following or afterwards after an earlier departure span in this answer", "weekday_afterwards", True),
)
_TEMPLATE_BY_HANDLE = {item.handle: item for item in _TEMPLATES}
_NUMBERED_LINE = re.compile(r"^\s*(?P<ordinal>[1-9]\d*)\.\s+\S(?:.*\S)?\s*$")
_DEPARTURE_CUE = re.compile(r"\b(?:departure|depart(?:ing)?|leave|leaving|outbound|fly\s+out)\b", re.IGNORECASE)
_RETURN_CUE = re.compile(r"\b(?:return(?:ing)?|back|come\s+back|inbound|fly\s+home)\b", re.IGNORECASE)
_TEMPORAL_CUE = re.compile(
    r"\b(?:weekend|today|tomorrow|tonight|spring|summer|fall|autumn|winter|"
    + "|".join(_WEEKDAYS)
    + r")\b",
    re.IGNORECASE,
)
_RELATIVE_UNIT_CUE = re.compile(
    r"\b(?:(?:next|this|following)\s+(?:week|month|year)|"
    r"(?:week|month|year)\s+after\s+next)\b",
    re.IGNORECASE,
)


def template_coverage_cues(text: str) -> tuple[re.Match[str], ...]:
    """Return v1's lexical coverage cues without choosing a semantic operator."""

    return _temporal_cues(text)


def template_selectable_surface(text: str) -> bool:
    """Whether this wording belongs to the weekday/weekend registry.

    This narrow classifier is used only to rehome an *unresolved* model record
    from its sibling registry. It does not grant selection authority.
    """

    return bool(_TEMPORAL_CUE.search(text))


def _temporal_cues(text: str) -> tuple[re.Match[str], ...]:
    """Lexically guard relative-time coverage without harvesting templates."""

    return tuple(sorted(
        (*_TEMPORAL_CUE.finditer(text), *_RELATIVE_UNIT_CUE.finditer(text)),
        key=lambda match: (match.start(), match.end()),
    ))


def global_temporal_template_projection() -> ClarificationTemporalTemplateProjection:
    """Return the constant, date-free catalog used for every answer."""

    return ClarificationTemporalTemplateProjection(
        registry_version=REGISTRY_VERSION,
        choices=tuple(
            ClarificationTemporalTemplateChoice(handle=item.handle, affordance=item.affordance)
            for item in _TEMPLATES
        ),
    )


def harvest_temporal_template_projection(**_: object) -> ClarificationTemporalTemplateProjection:
    """Compatibility controller entry point; intentionally does no harvesting."""

    return global_temporal_template_projection()


def _numbered_requirement(
    text: str, start: int, requirements: tuple[BlockingRequirement, ...]
) -> BlockingRequirement | None:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    match = _NUMBERED_LINE.fullmatch(text[line_start:] if line_end < 0 else text[line_start:line_end])
    if match is None:
        return None
    ordinal = int(match.group("ordinal"))
    return requirements[ordinal - 1] if ordinal <= len(requirements) else None


def _owning_requirement(
    text: str, start: int, requirements: tuple[BlockingRequirement, ...]
) -> BlockingRequirement | None:
    numbered = _numbered_requirement(text, start, requirements)
    if numbered is not None:
        return numbered if numbered.kind in {
            BlockingRequirementKind.DEPARTURE,
            BlockingRequirementKind.RETURN_OR_DURATION,
        } else None
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    segment = text[line_start:] if line_end < 0 else text[line_start:line_end]
    departure, returned = tuple(_DEPARTURE_CUE.finditer(segment)), tuple(_RETURN_CUE.finditer(segment))
    if bool(departure) == bool(returned):
        temporal = tuple(item for item in requirements if item.kind in {
            BlockingRequirementKind.DEPARTURE,
            BlockingRequirementKind.RETURN_OR_DURATION,
        })
        if len(temporal) == 1:
            return temporal[0]
        if departure and returned:
            relative = start - line_start
            distance = lambda cue: min(abs(relative - cue.start()), abs(relative - cue.end()))
            left, right = min(map(distance, departure)), min(map(distance, returned))
            if left != right:
                desired = BlockingRequirementKind.DEPARTURE if left < right else BlockingRequirementKind.RETURN_OR_DURATION
                return next((item for item in requirements if item.kind is desired), None)
        return None
    desired = BlockingRequirementKind.DEPARTURE if departure else BlockingRequirementKind.RETURN_OR_DURATION
    return next((item for item in requirements if item.kind is desired), None)


def validate_temporal_template_selection(
    projection: ClarificationTemporalTemplateProjection,
    selection: ClarificationTemporalTemplateSelection,
    *,
    text: str | None = None,
    requirements: tuple[BlockingRequirement, ...] | None = None,
    additional_classified_spans: tuple[MessageSpan, ...] = (),
) -> None:
    """Validate membership and the mandatory complete-classification claim."""

    if projection.registry_version != REGISTRY_VERSION:
        raise ClarificationTemporalTemplateError("unsupported temporal template registry version")
    if not selection.complete:
        raise ClarificationTemporalTemplateError("template selection must declare complete classification")
    handles = {item.handle for item in projection.choices}
    if any(item.template_handle not in handles for item in selection.selected):
        raise ClarificationTemporalTemplateError("template selection contains an unknown choice handle")
    for binding in selection.selected:
        template = _TEMPLATE_BY_HANDLE[binding.template_handle]
        if template.requires_weekday != (binding.weekday is not None):
            raise ClarificationTemporalTemplateError("template selection has invalid weekday slot affordance")
        if binding.weekday is not None and binding.weekday not in _WEEKDAYS:
            raise ClarificationTemporalTemplateError("template selection has an unknown weekday slot")
        words = set(re.findall(r"[a-z]+", binding.span.text.casefold()))
        if template.requires_weekday and binding.weekday not in words:
            raise ClarificationTemporalTemplateError("weekday slot is not grounded in its answer span")
        if not template.requires_weekday and "weekend" not in words:
            raise ClarificationTemporalTemplateError("weekend slot is not grounded in its answer span")
    if text is not None:
        classified = (
            tuple(item.span for item in selection.selected)
            + tuple(item.span for item in selection.unresolved)
            + additional_classified_spans
        )
        if any(
            len(_temporal_cues(binding.span.text)) != 1
            and not (
                binding.template_handle == "h3"
                and len(_temporal_cues(binding.span.text)) == 2
                and re.search(r"\b(?:next|following)\s+week\b", binding.span.text, re.IGNORECASE)
            )
            for binding in selection.selected
        ):
            raise ClarificationTemporalTemplateError(
                "each selected template span must contain exactly one temporal cue"
            )
        if any(not _temporal_cues(item.span.text) for item in selection.unresolved):
            raise ClarificationTemporalTemplateError(
                "each unresolved template span must contain a temporal cue"
            )
        missing = [
            match.group(0)
            for match in template_coverage_cues(text)
            if not any(span.start <= match.start() and match.end() <= span.end for span in classified)
        ]
        if missing:
            raise ClarificationTemporalTemplateError(
                "template selection does not classify every temporal cue"
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
                raise ClarificationTemporalTemplateError(
                    "unresolved template span requires active temporal requirement IDs"
                )
            if not set(item.requirement_ids).issubset(temporal_ids):
                raise ClarificationTemporalTemplateError(
                    "unresolved template span links an inactive or non-temporal requirement"
                )


def _candidates_for_selection(
    *,
    text: str,
    requirements: tuple[BlockingRequirement, ...],
    selection: ClarificationTemporalTemplateSelection,
) -> tuple[ClarificationTemporalCandidate, ...]:
    candidates: list[ClarificationTemporalCandidate] = []
    for ordinal, binding in enumerate(sorted(selection.selected, key=lambda item: item.span.start)):
        requirement = _owning_requirement(text, binding.span.start, requirements)
        if requirement is None:
            raise ClarificationTemporalTemplateError("selected template span has no deterministic temporal slot")
        template = _TEMPLATE_BY_HANDLE[binding.template_handle]
        dependencies: tuple[str, ...] = ()
        if template.mode == "weekday_afterwards":
            if not candidates:
                raise ClarificationTemporalTemplateError("relative dependency has no same-answer predecessor")
            predecessor = candidates[-1]
            predecessor_requirement = next(
                item for item in requirements if item.requirement_id == predecessor.requirement_id
            )
            if predecessor_requirement.kind is not BlockingRequirementKind.DEPARTURE:
                raise ClarificationTemporalTemplateError(
                    "relative dependency must follow a same-answer departure span"
                )
            if requirement.kind is not BlockingRequirementKind.RETURN_OR_DURATION:
                raise ClarificationTemporalTemplateError(
                    "relative dependency must resolve the same-answer return slot"
                )
            dependencies = (candidates[-1].candidate_id,)
        candidates.append(ClarificationTemporalCandidate(
            candidate_id=f"c{ordinal}", candidate_group_id=f"g{ordinal}", unresolved_candidate_id=f"u{ordinal}",
            span=binding.span, requirement_id=requirement.requirement_id,
            dependency_candidate_ids=dependencies, template_handle=binding.template_handle,
        ))
    return tuple(candidates)


def unresolved_template_rejections(
    selection: ClarificationTemporalTemplateSelection,
) -> tuple[tuple[MessageSpan, tuple[str, ...], Literal["ambiguous", "unsupported"], str], ...]:
    """Return durable answer-local provenance for explicit unresolved spans."""

    return tuple(
        (
            item.span,
            item.requirement_ids,
            item.reason,
            f"{REGISTRY_VERSION}.unresolved.{item.reason}",
        )
        for item in selection.unresolved
    )


def _weekday_after(value: date, weekday: int) -> date:
    delta = (weekday - value.weekday()) % 7
    return value.fromordinal(value.toordinal() + (delta or 7))


def compile_temporal_template_selection(
    projection: ClarificationTemporalTemplateProjection,
    selection: ClarificationTemporalTemplateSelection,
    *,
    context: RequestContext,
    text: str,
    requirements: tuple[BlockingRequirement, ...],
    additional_classified_spans: tuple[MessageSpan, ...] = (),
) -> tuple[CompiledTemporalTemplateFact, ...]:
    """Validate model selection then deterministically bind approved slots."""

    validate_temporal_template_selection(
        projection,
        selection,
        text=text,
        requirements=requirements,
        additional_classified_spans=additional_classified_spans,
    )
    candidates = _candidates_for_selection(text=text, requirements=requirements, selection=selection)
    compiled: dict[str, CompiledTemporalTemplateFact] = {}
    for candidate in candidates:
        template = _TEMPLATE_BY_HANDLE[candidate.template_handle]
        phrase = candidate.span.text
        if template.mode == "this_weekend":
            delta = (calendar.SATURDAY - context.reference_date.weekday()) % 7
            start = context.reference_date.fromordinal(context.reference_date.toordinal() + delta)
            end = start.fromordinal(start.toordinal() + 1)
        elif template.mode == "next_weekend":
            delta = (calendar.SATURDAY - context.reference_date.weekday()) % 7 + 7
            start = context.reference_date.fromordinal(context.reference_date.toordinal() + delta)
            end = start.fromordinal(start.toordinal() + 1)
        elif template.mode in {"this_weekday", "next_weekday", "on_weekday"}:
            weekday_name = next(
                binding.weekday for binding in selection.selected if binding.span == candidate.span
            )
            assert weekday_name is not None
            weekday = _WEEKDAYS[weekday_name]
            delta = (weekday - context.reference_date.weekday()) % 7
            if template.mode == "next_weekday":
                delta = delta or 7
                delta += 7 if delta < 7 else 0
            start = context.reference_date.fromordinal(context.reference_date.toordinal() + delta)
            end = start
        else:
            dependency = compiled[candidate.dependency_candidate_ids[0]]
            weekday_name = next(
                binding.weekday for binding in selection.selected if binding.span == candidate.span
            )
            assert weekday_name is not None
            weekday = _WEEKDAYS[weekday_name]
            start = _weekday_after(
                dependency.window.end, weekday
            )
            end = start
        compiled[candidate.candidate_id] = CompiledTemporalTemplateFact(
            candidate=candidate,
            template_id=template.template_id,
            window=DateWindow(
                start=start,
                end=end,
                precision=DateWindowPrecision.WINDOW if end != start else DateWindowPrecision.EXACT,
                raw_text=phrase,
            ),
        )
    return tuple(compiled[item.candidate_id] for item in candidates)


def target_for_template_candidate(
    candidate: ClarificationTemporalCandidate,
    requirements: tuple[BlockingRequirement, ...],
) -> Literal[AmendmentTarget.DEPARTURE, AmendmentTarget.RETURN_OR_DURATION]:
    requirement = next((item for item in requirements if item.requirement_id == candidate.requirement_id), None)
    if requirement is None:
        raise ClarificationTemporalTemplateError("template candidate requirement is inactive")
    if requirement.kind is BlockingRequirementKind.DEPARTURE:
        return AmendmentTarget.DEPARTURE
    if requirement.kind is BlockingRequirementKind.RETURN_OR_DURATION:
        return AmendmentTarget.RETURN_OR_DURATION
    raise ClarificationTemporalTemplateError("template candidate does not target a temporal requirement")


__all__ = [
    "REGISTRY_VERSION", "ClarificationTemporalCandidate", "ClarificationTemporalTemplateBinding",
    "ClarificationTemporalTemplateChoice", "ClarificationTemporalTemplateError",
    "ClarificationTemporalTemplateProjection", "ClarificationTemporalTemplateSelection",
    "ClarificationTemporalTemplateUnresolved", "CompiledTemporalTemplateFact",
    "compile_temporal_template_selection", "global_temporal_template_projection",
    "harvest_temporal_template_projection", "target_for_template_candidate",
    "template_coverage_cues", "template_selectable_surface",
    "unresolved_template_rejections", "validate_temporal_template_selection",
]
