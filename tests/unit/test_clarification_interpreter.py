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
from award_agent.clarification.semantic import SemanticTarget, TemporalAstKind, TemporalSemanticAst
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
                target=SemanticTarget.DEPARTURE_WINDOW,
                temporal=TemporalSemanticAst(
                    kind=TemporalAstKind.MONTH_PORTION, month=10, portion="mid"
                ),
            ),
            ClarificationSemanticFact(
                fact_id="duration",
                span=_span(text, "about 12 days"),
                target=SemanticTarget.DURATION,
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


def test_receiver_contract_has_no_receiver_authorship_fields_and_rejects_ungrounded_fact() -> None:
    text = "LAX"
    semantic_fact = ClarificationAnswerInterpretation(
        facts=(
            ClarificationSemanticFact(
                fact_id="origin",
                span=_span(text, "LAX"),
                target=SemanticTarget.ORIGIN,
                location_kind=LocationKind.AIRPORT,
                location_value="LAX",
            ),
        )
    )
    assert (
        interpret_answer(FakeInterpreter(semantic_fact), _input(text)).facts == semantic_fact.facts
    )
    assert "operation" not in semantic_fact.facts[0].model_dump()
    assert "requirement_ids" not in semantic_fact.facts[0].model_dump()
    bad = ClarificationAnswerInterpretation(
        facts=(
            ClarificationSemanticFact(
                fact_id="origin",
                span=MessageSpan(message_id="a1", start=0, end=3, text="SFO"),
                target=SemanticTarget.ORIGIN,
                location_kind=LocationKind.AIRPORT,
                location_value="SFO",
            ),
        )
    )
    with pytest.raises(ClarificationInterpretationError, match="does not equal"):
        interpret_answer(FakeInterpreter(bad), _input(text))


def test_receiver_accepts_correction_semantics_without_an_authorship_link() -> None:
    text = "Actually October 12"
    output = ClarificationAnswerInterpretation(
        facts=(
            ClarificationSemanticFact(
                fact_id="departure",
                span=_span(text, text),
                target=SemanticTarget.DEPARTURE_WINDOW,
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


def test_unresolved_fragment_is_answer_local_and_can_name_a_semantic_target() -> None:
    text = "either Monday or Tuesday"
    output = ClarificationAnswerInterpretation(
        unresolved_fragments=(
            ClarificationUnresolvedFragment(
                span=_span(text, text), target=SemanticTarget.DEPARTURE_WINDOW, reason="alternative"
            ),
        )
    )
    assert (
        interpret_answer(FakeInterpreter(output), _input(text)).unresolved_fragments[0].reason
        == "alternative"
    )
