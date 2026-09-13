"""Regression guard for the retired raw-text clarification temporal templates."""

from award_agent.clarification.interpreter import ClarificationOneWayScopeKind
from award_agent.clarification.semantic import SemanticTarget


def test_one_way_receiver_uses_a_typed_scope_classification_not_return_templates() -> None:
    assert ClarificationOneWayScopeKind.RETURN_OR_DURATION.value == "return_or_duration"
    assert [target.value for target in SemanticTarget] == [
        "origin",
        "destination",
        "travelers",
        "departure_window",
    ]
