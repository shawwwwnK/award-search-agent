"""Retired ADR 0011 live runner compatibility boundary.

Use ``one_way_award_live_eval`` for live one-way qualification. Historical
round-trip inputs fail closed rather than exercising incompatible contracts.
"""

from pathlib import Path
from typing import Any

from award_agent.evaluation.one_way_award_clarification import (
    DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES,
    OneWayAwardClarificationFixtureError,
    preflight_one_way_award_clarification_cases,
)

DEFAULT_LIVE_CLARIFICATION_FIXTURES = DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES
DEFAULT_LIVE_CLARIFICATION_TRACE_DIR = Path("evals/clarification/traces-one-way")
ClarificationLiveFixtureError = OneWayAwardClarificationFixtureError

__all__ = [
    "DEFAULT_LIVE_CLARIFICATION_FIXTURES",
    "DEFAULT_LIVE_CLARIFICATION_TRACE_DIR",
    "ClarificationLiveFixtureError",
    "_load_cases",
    "_required_terminal_correct",
    "run_live_clarification_eval",
]


def _load_cases(path: Path = DEFAULT_LIVE_CLARIFICATION_FIXTURES):
    cases = preflight_one_way_award_clarification_cases(path)
    return [case.payload for case in cases], path.read_bytes()


def _required_terminal_correct(session_count: int) -> int:
    return session_count


def run_live_clarification_eval(**_kwargs: Any) -> dict[str, Any]:
    raise RuntimeError(
        "The ADR 0011 live evaluator is retired for one-way scope; use "
        "python -m award_agent.cli.one_way_award_live_eval instead."
    )
