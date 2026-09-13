"""Retired ADR 0012 live runner compatibility boundary."""

from award_agent.evaluation.clarification_live import (
    DEFAULT_LIVE_CLARIFICATION_FIXTURES as DEFAULT_LIVE_BEHAVIOR_FIXTURES,
)
from award_agent.evaluation.clarification_live import (
    DEFAULT_LIVE_CLARIFICATION_TRACE_DIR as DEFAULT_LIVE_BEHAVIOR_TRACE_DIR,
)
from award_agent.evaluation.clarification_live import (
    ClarificationLiveFixtureError as ClarificationBehaviorLiveFixtureError,
)

__all__ = [
    "DEFAULT_LIVE_BEHAVIOR_FIXTURES",
    "DEFAULT_LIVE_BEHAVIOR_TRACE_DIR",
    "ClarificationBehaviorLiveFixtureError",
    "run_live_clarification_behavior_eval",
]


def run_live_clarification_behavior_eval(**_kwargs: object) -> object:
    raise RuntimeError(
        "The ADR 0012 live evaluator is retired for one-way scope; use "
        "python -m award_agent.cli.one_way_award_live_eval instead."
    )
