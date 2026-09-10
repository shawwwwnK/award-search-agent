"""Tests for global, model-grounded clarification temporal selections."""

from datetime import date

import pytest

from award_agent.clarification.temporal_templates import (
    ClarificationTemporalTemplateBinding,
    ClarificationTemporalTemplateError,
    ClarificationTemporalTemplateSelection,
    ClarificationTemporalTemplateUnresolved,
    CompiledTemporalTemplateFact,
    compile_temporal_template_selection,
    global_temporal_template_projection,
    validate_temporal_template_selection,
)
from award_agent.domain import (
    BlockingRequirement,
    BlockingRequirementKind,
    EffectiveField,
    MessageSpan,
    RequestContext,
)


def _requirements() -> tuple[BlockingRequirement, ...]:
    return (
        BlockingRequirement(requirement_id="departure", kind=BlockingRequirementKind.DEPARTURE, field=EffectiveField.DEPARTURE),
        BlockingRequirement(requirement_id="return_or_duration", kind=BlockingRequirementKind.RETURN_OR_DURATION, field=EffectiveField.RETURN_OR_DURATION),
        BlockingRequirement(requirement_id="travelers", kind=BlockingRequirementKind.TRAVELERS, field=EffectiveField.TRAVELERS),
    )


def _selection(text: str, *items: tuple[str, str]) -> ClarificationTemporalTemplateSelection:
    return ClarificationTemporalTemplateSelection(
        selected=tuple(
            ClarificationTemporalTemplateBinding(
                template_handle=handle,
                span=MessageSpan(message_id="answer-1", start=text.index(phrase), end=text.index(phrase) + len(phrase), text=phrase),
                weekday=next((name for name in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday") if name in phrase.casefold()), None),
            )
            for handle, phrase in items
        ),
        complete=True,
    )


def _compile(text: str, *items: tuple[str, str]) -> tuple[CompiledTemporalTemplateFact, ...]:
    return compile_temporal_template_selection(
        global_temporal_template_projection(), _selection(text, *items),
        context=RequestContext(reference_date=date(2026, 9, 9), timezone="America/Los_Angeles"),
        text=text, requirements=_requirements(),
    )


def test_global_projection_is_date_free_and_not_phrase_gated() -> None:
    projection = global_temporal_template_projection()
    dumped = str(projection.model_dump(mode="json"))
    assert "2026" not in dumped and "reference_date" not in dumped and "next_weekend" not in dumped
    assert [item.handle for item in projection.choices] == [f"h{index}" for index in range(1, 7)]
    assert [item.affordance for item in projection.choices[:5]] == [
        "a weekend explicitly described as next: the weekend after the upcoming weekend",
        "a weekend explicitly described as this: the upcoming/current weekend",
        "a named weekday directly qualified by next, or anchored by an explicit next/following week phrase: that weekday in the next calendar week",
        "a named weekday explicitly described as this: that weekday in the current calendar week",
        "a named weekday with no this/next qualifier: its first upcoming occurrence",
    ]


def test_model_grounded_numbered_next_weekend_and_afterwards_compile() -> None:
    text = "1. Next weekend\n2. The Wednesday afterwards\n3. Just myself"
    facts = _compile(text, ("h1", "Next weekend"), ("h6", "The Wednesday afterwards"))
    assert [(item.window.start, item.window.end) for item in facts] == [
        (date(2026, 9, 19), date(2026, 9, 20)), (date(2026, 9, 23), date(2026, 9, 23)),
    ]
    assert facts[1].candidate.dependency_candidate_ids == ("c0",)


def test_following_weekday_uses_the_same_answer_departure_dependency() -> None:
    text = "leave the weekend after this one, return the following Wednesday"
    facts = _compile(text, ("h1", "the weekend after this one"), ("h6", "the following Wednesday"))
    assert [(item.template_id, item.window.start) for item in facts] == [
        ("next_weekend", date(2026, 9, 19)),
        ("weekday_afterwards", date(2026, 9, 23)),
    ]


@pytest.mark.parametrize(("text", "handle", "phrase", "expected"), [
    ("1. Next Friday", "h3", "Next Friday", date(2026, 9, 18)),
    ("leaving Wednesday of next week", "h3", "Wednesday of next week", date(2026, 9, 16)),
])
def test_global_templates_cover_blind_and_next_weekday_forms(text: str, handle: str, phrase: str, expected: date) -> None:
    facts = _compile(text, (handle, phrase))
    assert facts[0].window.start == facts[0].window.end == expected


def test_selection_rejects_unknown_handle_incomplete_and_invalid_post_selection_slot() -> None:
    projection = global_temporal_template_projection()
    text = "1. Next Friday"
    span = MessageSpan(message_id="answer-1", start=3, end=14, text="Next Friday")
    with pytest.raises(ClarificationTemporalTemplateError, match="complete"):
        validate_temporal_template_selection(projection, ClarificationTemporalTemplateSelection(selected=(ClarificationTemporalTemplateBinding(template_handle="h3", span=span, weekday="friday"),), complete=False))
    with pytest.raises(ClarificationTemporalTemplateError, match="unknown"):
        validate_temporal_template_selection(projection, ClarificationTemporalTemplateSelection(selected=(ClarificationTemporalTemplateBinding(template_handle="h99", span=span, weekday="friday"),), complete=True))
    with pytest.raises(ClarificationTemporalTemplateError, match="slot affordance"):
        _compile(text, ("h1", "Next Friday"))


def test_explicit_unresolved_span_is_required_to_be_nonoverlapping_provenance() -> None:
    text = "next spring"
    span = MessageSpan(message_id="answer-1", start=0, end=len(text), text=text)
    selection = ClarificationTemporalTemplateSelection(
        unresolved=(ClarificationTemporalTemplateUnresolved(span=span),), complete=True
    )
    validate_temporal_template_selection(global_temporal_template_projection(), selection)


def test_complete_classification_covers_each_temporal_cue_and_afterwards_requires_departure() -> None:
    projection = global_temporal_template_projection()
    with pytest.raises(ClarificationTemporalTemplateError, match="every temporal cue"):
        validate_temporal_template_selection(projection, ClarificationTemporalTemplateSelection(complete=True), text="Next Friday")
    for text in ("next month", "the week after next"):
        with pytest.raises(ClarificationTemporalTemplateError, match="every temporal cue"):
            validate_temporal_template_selection(
                projection, ClarificationTemporalTemplateSelection(complete=True), text=text
            )
    text = "Return on Monday; leave the Wednesday afterwards"
    with pytest.raises(ClarificationTemporalTemplateError, match="departure"):
        _compile(text, ("h5", "on Monday"), ("h6", "Wednesday afterwards"))


def test_unresolved_span_may_cover_a_compound_unsupported_relative_expression() -> None:
    text = "the first week of next month"
    selection = ClarificationTemporalTemplateSelection(
        unresolved=(ClarificationTemporalTemplateUnresolved(
            span=MessageSpan(message_id="answer-1", start=0, end=len(text), text=text)
        ),),
        complete=True,
    )
    validate_temporal_template_selection(global_temporal_template_projection(), selection, text=text)


def test_next_weekday_cannot_discard_a_conflicting_relative_unit() -> None:
    text = "leaving Wednesday next month"
    with pytest.raises(ClarificationTemporalTemplateError, match="exactly one temporal cue"):
        _compile(text, ("h3", "Wednesday next month"))
