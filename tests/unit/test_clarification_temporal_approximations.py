"""Regression tests: one-way clarification has no duration approximation state."""

import pytest

from award_agent.clarification.calendar_plan import CalendarProposalTarget
from award_agent.domain import AmendmentTarget, BlockingRequirementKind, EffectiveField


def test_return_duration_contract_members_are_not_live() -> None:
    with pytest.raises(ValueError):
        CalendarProposalTarget("duration")
    with pytest.raises(ValueError):
        AmendmentTarget("return_or_duration")
    with pytest.raises(ValueError):
        BlockingRequirementKind("return_or_duration")
    with pytest.raises(ValueError):
        EffectiveField("return_or_duration")
