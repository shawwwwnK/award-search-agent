"""Active one-way semantic calendar compilation tests."""

from datetime import date

import pytest

from award_agent.clarification.semantic import (
    SemanticTarget,
    TemporalAstKind,
    TemporalSemanticAst,
    compile_temporal_ast,
)
from award_agent.domain import MessageSpan, RequestContext


def test_departure_date_compiles_without_model_calculated_date() -> None:
    compiled = compile_temporal_ast(
        amendment_id="departure",
        target=SemanticTarget.DEPARTURE_WINDOW,
        ast=TemporalSemanticAst(kind=TemporalAstKind.CALENDAR_DATE, month=10, day=6),
        span=MessageSpan(message_id="m1", start=0, end=9, text="October 6"),
        context=RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles"),
    )
    assert compiled.contribution.date_window is not None
    assert compiled.contribution.date_window.start == date(2026, 10, 6)


def test_semantic_target_excludes_return_and_duration() -> None:
    with pytest.raises(ValueError):
        SemanticTarget("return_window")
    with pytest.raises(ValueError):
        SemanticTarget("duration")
