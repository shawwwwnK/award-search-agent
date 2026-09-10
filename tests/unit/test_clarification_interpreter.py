"""Offline contract tests for the Step-3 clarification answer interpreter seam."""

import pytest

from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreterInput,
    ClarificationInterpretationError,
    interpret_answer,
)
from award_agent.clarification.temporal_approximations import (
    ClarificationTemporalApproximationBinding,
    ClarificationTemporalApproximationSelection,
    ClarificationTemporalApproximationUnresolved,
    approximation_coverage_cues,
    global_temporal_approximation_projection,
)
from award_agent.clarification.temporal_templates import (
    ClarificationTemporalTemplateBinding,
    ClarificationTemporalTemplateSelection,
    ClarificationTemporalTemplateUnresolved,
    global_temporal_template_projection,
)
from award_agent.domain import (
    AmendmentTarget,
    BlockingRequirement,
    BlockingRequirementKind,
    EffectiveField,
    LocationAmendment,
    LocationKind,
    LocationRef,
    MessageSpan,
    RejectedFragment,
    RejectedFragmentReason,
    TravelersAmendment,
)


class FakeInterpreter:
    def __init__(self, interpretation: ClarificationAnswerInterpretation) -> None:
        self.interpretation = interpretation
        self.inputs: list[ClarificationAnswerInterpreterInput] = []

    def interpret(
        self, input: ClarificationAnswerInterpreterInput
    ) -> ClarificationAnswerInterpretation:
        self.inputs.append(input)
        return self.interpretation


def _input(text: str, *requirements: BlockingRequirement) -> ClarificationAnswerInterpreterInput:
    return ClarificationAnswerInterpreterInput(
        message_id="answer-1",
        text=text,
        requirements=requirements,
    )


def _requirement(kind: BlockingRequirementKind) -> BlockingRequirement:
    field_by_kind = {
        BlockingRequirementKind.ORIGIN: EffectiveField.ORIGIN,
        BlockingRequirementKind.DESTINATION: EffectiveField.DESTINATION,
        BlockingRequirementKind.TRAVELERS: EffectiveField.TRAVELERS,
    }
    return BlockingRequirement(
        requirement_id=f"required:{kind.value}",
        kind=kind,
        field=field_by_kind.get(kind),
        conflict_code="date_conflict" if kind is BlockingRequirementKind.CONFLICT else None,
    )


def _span(text: str, fragment: str) -> MessageSpan:
    start = text.index(fragment)
    return MessageSpan(message_id="answer-1", start=start, end=start + len(fragment), text=fragment)


def _temporal_input(text: str) -> ClarificationAnswerInterpreterInput:
    requirements = (
        BlockingRequirement(
            requirement_id="departure",
            kind=BlockingRequirementKind.DEPARTURE,
            field=EffectiveField.DEPARTURE,
        ),
        BlockingRequirement(
            requirement_id="return_or_duration",
            kind=BlockingRequirementKind.RETURN_OR_DURATION,
            field=EffectiveField.RETURN_OR_DURATION,
        ),
    )
    return ClarificationAnswerInterpreterInput(
        message_id="answer-1",
        text=text,
        requirements=requirements,
        temporal_template_projection=global_temporal_template_projection(),
        temporal_approximation_projection=global_temporal_approximation_projection(),
    )


def test_fake_interpreter_accepts_multiple_independent_typed_amendments() -> None:
    text = "SFO to Bangkok; two travelers."
    origin = _requirement(BlockingRequirementKind.ORIGIN)
    destination = _requirement(BlockingRequirementKind.DESTINATION)
    travelers = _requirement(BlockingRequirementKind.TRAVELERS)
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                LocationAmendment(
                    amendment_id="origin-1",
                    target=AmendmentTarget.ORIGIN,
                    requirement_ids=(origin.requirement_id,),
                    span=_span(text, "SFO"),
                    locations=(
                        LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),
                    ),
                ),
                LocationAmendment(
                    amendment_id="destination-1",
                    target=AmendmentTarget.DESTINATION,
                    requirement_ids=(destination.requirement_id,),
                    span=_span(text, "Bangkok"),
                    locations=(
                        LocationRef(kind=LocationKind.CITY, value="Bangkok", raw_text="Bangkok"),
                    ),
                ),
                TravelersAmendment(
                    amendment_id="travelers-1",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=(travelers.requirement_id,),
                    span=_span(text, "two"),
                    travelers=2,
                ),
            )
        )
    )

    output = interpret_answer(fake, _input(text, origin, destination, travelers))

    assert output.amendments[0].target is AmendmentTarget.ORIGIN
    assert output.amendments[1].target is AmendmentTarget.DESTINATION
    assert output.amendments[2].travelers == 2
    assert fake.inputs[0].requirements == (origin, destination, travelers)


def test_subset_answer_can_reject_one_fragment_without_losing_valid_amendment() -> None:
    text = "Two travelers, perhaps first class someday."
    travelers = _requirement(BlockingRequirementKind.TRAVELERS)
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                TravelersAmendment(
                    amendment_id="travelers-1",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=(travelers.requirement_id,),
                    span=_span(text, "Two"),
                    travelers=2,
                ),
            ),
            rejected_fragments=(
                RejectedFragment(
                    span=_span(text, "first class"),
                    reason=RejectedFragmentReason.OUT_OF_SCOPE,
                    detail="cabin is not an active clarification requirement",
                ),
            ),
        )
    )

    output = interpret_answer(fake, _input(text, travelers))

    assert output.amendments[0].amendment_id == "travelers-1"
    assert output.rejected_fragments[0].reason is RejectedFragmentReason.OUT_OF_SCOPE


def test_explicit_supported_correction_can_be_proposed_without_a_pending_requirement() -> None:
    text = "Actually change the origin to LAX."
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                LocationAmendment(
                    amendment_id="origin-correction-1",
                    target=AmendmentTarget.ORIGIN,
                    span=_span(text, "Actually change the origin to LAX"),
                    is_correction=True,
                    locations=(
                        LocationRef(kind=LocationKind.AIRPORT, value="LAX", raw_text="LAX"),
                    ),
                ),
            )
        )
    )

    output = interpret_answer(fake, _input(text, _requirement(BlockingRequirementKind.TRAVELERS)))

    assert output.amendments[0].is_correction is True


def test_interpreter_rejects_ungrounded_spans_and_unrelated_requirement_links() -> None:
    text = "Two travelers."
    travelers = _requirement(BlockingRequirementKind.TRAVELERS)
    unrelated = ClarificationAnswerInterpretation(
        amendments=(
            LocationAmendment(
                amendment_id="origin-1",
                target=AmendmentTarget.ORIGIN,
                requirement_ids=(travelers.requirement_id,),
                span=MessageSpan(message_id="answer-1", start=0, end=3, text="Two"),
                locations=(LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),),
            ),
        )
    )

    with pytest.raises(ClarificationInterpretationError, match="incompatible requirement"):
        interpret_answer(FakeInterpreter(unrelated), _input(text, travelers))

    bad_span = ClarificationAnswerInterpretation(
        amendments=(
            TravelersAmendment(
                amendment_id="travelers-1",
                target=AmendmentTarget.TRAVELERS,
                requirement_ids=(travelers.requirement_id,),
                span=MessageSpan(message_id="answer-1", start=0, end=3, text="One"),
                travelers=2,
            ),
        )
    )
    with pytest.raises(ClarificationInterpretationError, match="does not equal"):
        interpret_answer(FakeInterpreter(bad_span), _input(text, travelers))


def test_interpreter_rejects_next_question_for_an_inactive_requirement() -> None:
    travelers = _requirement(BlockingRequirementKind.TRAVELERS)
    output = ClarificationAnswerInterpretation(
        next_question="Where would you like to go?",
        next_question_requirement_ids=("required:destination",),
    )

    with pytest.raises(ClarificationInterpretationError, match="next question links"):
        interpret_answer(FakeInterpreter(output), _input("Two travelers.", travelers))


def test_model_facing_interpreter_input_excludes_concrete_request_context() -> None:
    model_input = _input("Two travelers.", _requirement(BlockingRequirementKind.TRAVELERS))

    payload = model_input.model_dump(mode="json")
    assert set(payload) == {
        "message_id", "text", "requirements", "temporal_template_projection",
        "temporal_approximation_projection",
    }
    assert "reference_date" not in str(payload)
    assert "timezone" not in str(payload)
    schema = ClarificationAnswerInterpreterInput.model_json_schema()
    assert "context" not in schema["properties"]
    assert "reference_date" not in str(schema)
    assert "timezone" not in str(schema)


def test_combined_registry_coverage_accepts_an_approximation_without_v1_duplicate() -> None:
    text = "Leave early next month for a week"
    output = ClarificationAnswerInterpretation(
        temporal_approximation_selection=ClarificationTemporalApproximationSelection(
            selected=(
                ClarificationTemporalApproximationBinding(
                    approximation_handle="a1",
                    span=_span(text, "early next month"),
                    month_reference="next_month",
                ),
                ClarificationTemporalApproximationBinding(
                    approximation_handle="a4", span=_span(text, "a week")
                ),
            ),
            complete=True,
        )
    )

    interpreted = interpret_answer(FakeInterpreter(output), _temporal_input(text))

    assert len(interpreted.temporal_approximation_selection.selected) == 2
    assert interpreted.temporal_template_selection.unresolved == ()


def test_wrong_registry_unresolved_is_rehomed_with_links_and_reason() -> None:
    text = "a week"
    output = ClarificationAnswerInterpretation(
        temporal_template_selection=ClarificationTemporalTemplateSelection(
            unresolved=(
                ClarificationTemporalTemplateUnresolved(
                    span=_span(text, text),
                    requirement_ids=("return_or_duration",),
                    reason="ambiguous",
                ),
            ),
            complete=True,
        )
    )

    interpreted = interpret_answer(FakeInterpreter(output), _temporal_input(text))

    assert interpreted.temporal_template_selection.unresolved == ()
    rehomed = interpreted.temporal_approximation_selection.unresolved
    assert len(rehomed) == 1
    assert rehomed[0].span.text == text
    assert rehomed[0].requirement_ids == ("return_or_duration",)
    assert rehomed[0].reason == "ambiguous"


def test_wrong_registry_weekend_unresolved_moves_to_template_registry() -> None:
    text = "this weekend"
    output = ClarificationAnswerInterpretation(
        temporal_approximation_selection=ClarificationTemporalApproximationSelection(
            unresolved=(
                ClarificationTemporalApproximationUnresolved(
                    span=_span(text, text), requirement_ids=("departure",), reason="unsupported"
                ),
            ),
            complete=True,
        )
    )

    interpreted = interpret_answer(FakeInterpreter(output), _temporal_input(text))

    assert interpreted.temporal_approximation_selection.unresolved == ()
    assert interpreted.temporal_template_selection.unresolved[0].reason == "unsupported"


def test_bare_named_month_unresolved_routes_to_the_generic_rejection_channel() -> None:
    text = "October"
    output = ClarificationAnswerInterpretation(
        temporal_approximation_selection=ClarificationTemporalApproximationSelection(
            unresolved=(
                ClarificationTemporalApproximationUnresolved(
                    span=_span(text, text), requirement_ids=("departure",), reason="ambiguous"
                ),
            ),
            complete=True,
        )
    )

    interpreted = interpret_answer(FakeInterpreter(output), _temporal_input(text))

    assert interpreted.temporal_approximation_selection.unresolved == ()
    assert interpreted.temporal_template_selection.unresolved == ()
    assert len(interpreted.rejected_fragments) == 1
    assert interpreted.rejected_fragments[0].reason is RejectedFragmentReason.AMBIGUOUS
    assert interpreted.rejected_fragments[0].span.text == "October"
    assert interpreted.rejected_fragments[0].requirement_ids == ("departure",)


def test_legacy_exact_date_alternatives_route_generic_without_positive_authority() -> None:
    text = "October 3 or October 10"
    output = ClarificationAnswerInterpretation(
        temporal_approximation_selection=ClarificationTemporalApproximationSelection(
            unresolved=(
                ClarificationTemporalApproximationUnresolved(
                    span=_span(text, text),
                    requirement_ids=("departure", "return_or_duration"),
                    reason="ambiguous",
                ),
            ),
            complete=True,
        )
    )

    interpreted = interpret_answer(FakeInterpreter(output), _temporal_input(text))

    assert interpreted.temporal_template_selection.selected == ()
    assert interpreted.temporal_approximation_selection.selected == ()
    assert interpreted.temporal_template_selection.unresolved == ()
    assert interpreted.temporal_approximation_selection.unresolved == ()
    assert len(interpreted.rejected_fragments) == 1
    assert interpreted.rejected_fragments[0].span.text == text
    assert interpreted.rejected_fragments[0].reason is RejectedFragmentReason.AMBIGUOUS
    assert interpreted.rejected_fragments[0].requirement_ids == (
        "departure",
        "return_or_duration",
    )


def test_approximation_coverage_splits_each_discrete_alternative() -> None:
    assert [item.group(0) for item in approximation_coverage_cues("early October or late October")] == [
        "early October",
        "late October",
    ]


@pytest.mark.parametrize(
    ("text", "interpretation"),
    [
        (
            "early October or late October",
            ClarificationAnswerInterpretation(
                temporal_approximation_selection=ClarificationTemporalApproximationSelection(
                    selected=(
                        ClarificationTemporalApproximationBinding(
                            approximation_handle="a1",
                            span=MessageSpan(
                                message_id="answer-1", start=0, end=13, text="early October"
                            ),
                            month_reference="named_month",
                            month_name="october",
                        ),
                    ),
                    complete=True,
                )
            ),
        ),
        (
            "this Friday or next Friday",
            ClarificationAnswerInterpretation(
                temporal_template_selection=ClarificationTemporalTemplateSelection(
                    selected=(
                        ClarificationTemporalTemplateBinding(
                            template_handle="h4",
                            span=MessageSpan(
                                message_id="answer-1", start=0, end=11, text="this Friday"
                            ),
                            weekday="friday",
                        ),
                    ),
                    complete=True,
                )
            ),
        ),
    ],
)
def test_discrete_positive_registry_selection_is_downgraded_before_compilation(
    text: str, interpretation: ClarificationAnswerInterpretation
) -> None:
    interpreted = interpret_answer(FakeInterpreter(interpretation), _temporal_input(text))
    template = interpreted.temporal_template_selection
    approximation = interpreted.temporal_approximation_selection

    assert not template.selected and not approximation.selected
    unresolved = template.unresolved + approximation.unresolved
    assert len(unresolved) == 1
    assert unresolved[0].span.text == text
    assert unresolved[0].reason == "ambiguous"
    assert unresolved[0].requirement_ids == ("departure", "return_or_duration")


def test_multiple_positive_alternatives_on_one_line_merge_to_one_ambiguity() -> None:
    text = "early October or late October"
    output = ClarificationAnswerInterpretation(
        temporal_approximation_selection=ClarificationTemporalApproximationSelection(
            selected=(
                ClarificationTemporalApproximationBinding(
                    approximation_handle="a1",
                    span=_span(text, "early October"),
                    month_reference="named_month",
                    month_name="october",
                ),
                ClarificationTemporalApproximationBinding(
                    approximation_handle="a3",
                    span=_span(text, "late October"),
                    month_reference="named_month",
                    month_name="october",
                ),
            ),
            complete=True,
        )
    )

    interpreted = interpret_answer(FakeInterpreter(output), _temporal_input(text))

    assert interpreted.temporal_approximation_selection.selected == ()
    unresolved = interpreted.temporal_approximation_selection.unresolved
    assert len(unresolved) == 1
    assert unresolved[0].span.text == text
    assert unresolved[0].reason == "ambiguous"
    assert unresolved[0].requirement_ids == ("departure", "return_or_duration")
