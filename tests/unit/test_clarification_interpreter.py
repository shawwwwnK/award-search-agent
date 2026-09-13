"""Receiver-boundary tests for active one-way clarification semantics."""

import pytest

from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreterInput,
    ClarificationInterpretationError,
    ClarificationOneWayScopeKind,
    ClarificationOneWayScopeNotice,
    validate_answer_interpretation,
)
from award_agent.domain import MessageSpan


def test_one_way_scope_notice_requires_an_exact_grounded_span() -> None:
    input = ClarificationAnswerInterpreterInput(message_id="m1", text="return October 15", ordered_requirements=())
    interpretation = ClarificationAnswerInterpretation(
        one_way_scope_notices=(
            ClarificationOneWayScopeNotice(
                kind=ClarificationOneWayScopeKind.RETURN_OR_DURATION,
                span=MessageSpan(message_id="m1", start=0, end=17, text="return October 15"),
            ),
        )
    )
    assert validate_answer_interpretation(input, interpretation) == interpretation
    invalid = interpretation.model_copy(
        update={
            "one_way_scope_notices": (
                ClarificationOneWayScopeNotice(
                    kind=ClarificationOneWayScopeKind.RETURN_OR_DURATION,
                    span=MessageSpan(message_id="m1", start=0, end=6, text="Return"),
                ),
            )
        }
    )
    with pytest.raises(ClarificationInterpretationError):
        validate_answer_interpretation(input, invalid)
