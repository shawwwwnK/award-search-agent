"""Contract tests for the semantic clarification receiver."""

import pytest

from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreterInput,
    ClarificationInterpretationError,
    ClarificationSemanticFact,
    ClarificationUnresolvedFragment,
    interpret_answer,
)
from award_agent.clarification.semantic import (
    SemanticOperation,
    SemanticTarget,
    TemporalAstKind,
    TemporalSemanticAst,
)
from award_agent.domain import (
    BlockingRequirement,
    BlockingRequirementKind,
    EffectiveField,
    LocationKind,
    MessageSpan,
)


class FakeInterpreter:
    def __init__(self, output: ClarificationAnswerInterpretation) -> None:
        self.output = output

    def interpret(
        self, _input: ClarificationAnswerInterpreterInput
    ) -> ClarificationAnswerInterpretation:
        return self.output


def _requirement(
    identifier: str, kind: BlockingRequirementKind, field: EffectiveField
) -> BlockingRequirement:
    return BlockingRequirement(requirement_id=identifier, kind=kind, field=field)


def _input(text: str) -> ClarificationAnswerInterpreterInput:
    return ClarificationAnswerInterpreterInput(
        message_id="a1",
        text=text,
        ordered_requirements=(
            _requirement("origin", BlockingRequirementKind.ORIGIN, EffectiveField.ORIGIN),
            _requirement("departure", BlockingRequirementKind.DEPARTURE, EffectiveField.DEPARTURE),
            _requirement(
                "return",
                BlockingRequirementKind.RETURN_OR_DURATION,
                EffectiveField.RETURN_OR_DURATION,
            ),
        ),
        correction_eligible_targets=(SemanticTarget.DEPARTURE_WINDOW,),
    )


def _span(text: str, quote: str) -> MessageSpan:
    start = text.index(quote)
    return MessageSpan(message_id="a1", start=start, end=start + len(quote), text=quote)


def test_receiver_accepts_multiple_grounded_semantic_facts_without_lexical_rules() -> None:
    text = "Actually mid october for depature and the trip will be about 12 days"
    output = ClarificationAnswerInterpretation(
        facts=(
            ClarificationSemanticFact(
                fact_id="departure",
                span=_span(text, "Actually mid october for depature"),
                operation=SemanticOperation.REPLACE,
                target=SemanticTarget.DEPARTURE_WINDOW,
                temporal=TemporalSemanticAst(
                    kind=TemporalAstKind.MONTH_PORTION, month=10, portion="mid"
                ),
            ),
            ClarificationSemanticFact(
                fact_id="duration",
                span=_span(text, "about 12 days"),
                operation=SemanticOperation.SET,
                target=SemanticTarget.DURATION,
                requirement_ids=("return",),
                temporal=TemporalSemanticAst(
                    kind=TemporalAstKind.DURATION, quantity=12, unit="day", approximate=True
                ),
            ),
        )
    )
    result = interpret_answer(FakeInterpreter(output), _input(text))
    assert [fact.target for fact in result.facts] == [
        SemanticTarget.DEPARTURE_WINDOW,
        SemanticTarget.DURATION,
    ]


def test_receiver_rejects_unauthorized_replace_and_ungrounded_fact() -> None:
    text = "LAX"
    unauthorized = ClarificationAnswerInterpretation(
        facts=(
            ClarificationSemanticFact(
                fact_id="origin",
                span=_span(text, "LAX"),
                operation=SemanticOperation.REPLACE,
                target=SemanticTarget.ORIGIN,
                location_kind=LocationKind.AIRPORT,
                location_value="LAX",
            ),
        )
    )
    with pytest.raises(ClarificationInterpretationError, match="not authorized"):
        interpret_answer(FakeInterpreter(unauthorized), _input(text))
    bad = ClarificationAnswerInterpretation(
        facts=(
            ClarificationSemanticFact(
                fact_id="origin",
                span=MessageSpan(message_id="a1", start=0, end=3, text="SFO"),
                operation=SemanticOperation.SET,
                target=SemanticTarget.ORIGIN,
                requirement_ids=("origin",),
                location_kind=LocationKind.AIRPORT,
                location_value="SFO",
            ),
        )
    )
    with pytest.raises(ClarificationInterpretationError, match="does not equal"):
        interpret_answer(FakeInterpreter(bad), _input(text))


def test_receiver_rejects_replace_linked_to_an_unrelated_active_requirement() -> None:
    text = "Actually October 12"
    output = ClarificationAnswerInterpretation(
        facts=(
            ClarificationSemanticFact(
                fact_id="departure",
                span=_span(text, text),
                operation=SemanticOperation.REPLACE,
                target=SemanticTarget.DEPARTURE_WINDOW,
                requirement_ids=("return",),
                temporal=TemporalSemanticAst(kind=TemporalAstKind.CALENDAR_DATE, month=10, day=12),
            ),
        )
    )
    with pytest.raises(ClarificationInterpretationError, match="unrelated active requirement"):
        interpret_answer(FakeInterpreter(output), _input(text))


def test_receiver_accepts_replace_linked_only_to_the_matching_active_requirement() -> None:
    text = "Actually October 12"
    output = ClarificationAnswerInterpretation(
        facts=(
            ClarificationSemanticFact(
                fact_id="departure",
                span=_span(text, text),
                operation=SemanticOperation.REPLACE,
                target=SemanticTarget.DEPARTURE_WINDOW,
                requirement_ids=("departure",),
                temporal=TemporalSemanticAst(kind=TemporalAstKind.CALENDAR_DATE, month=10, day=12),
            ),
        )
    )
    assert interpret_answer(FakeInterpreter(output), _input(text)).facts == output.facts


def test_model_input_has_no_context_values_or_ledger() -> None:
    payload = _input("October 12").model_dump(mode="json")
    assert set(payload) == {
        "message_id",
        "text",
        "ordered_requirements",
        "correction_eligible_targets",
        "temporal_affordance_catalog_version",
    }
    assert "reference_date" not in str(payload)
    assert "timezone" not in str(payload)
    assert "effective_request" not in str(payload)


def test_unresolved_fragment_is_answer_local_and_linked_to_active_requirement() -> None:
    text = "either Monday or Tuesday"
    output = ClarificationAnswerInterpretation(
        unresolved_fragments=(
            ClarificationUnresolvedFragment(
                span=_span(text, text), requirement_ids=("departure",), reason="alternative"
            ),
        )
    )
    assert (
        interpret_answer(FakeInterpreter(output), _input(text)).unresolved_fragments[0].reason
        == "alternative"
    )
