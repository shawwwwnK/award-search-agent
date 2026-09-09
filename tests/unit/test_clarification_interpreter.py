"""Offline contract tests for the Step-3 clarification answer interpreter seam."""

import pytest

from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreterInput,
    ClarificationInterpretationError,
    interpret_answer,
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
                    locations=(LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),),
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
                    locations=(LocationRef(kind=LocationKind.AIRPORT, value="LAX", raw_text="LAX"),),
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


def test_model_facing_interpreter_input_excludes_concrete_request_context() -> None:
    model_input = _input("Two travelers.", _requirement(BlockingRequirementKind.TRAVELERS))

    assert set(model_input.model_dump(mode="json")) == {"message_id", "text", "requirements"}
    schema = ClarificationAnswerInterpreterInput.model_json_schema()
    assert "context" not in schema["properties"]
    assert "reference_date" not in str(schema)
    assert "timezone" not in str(schema)
