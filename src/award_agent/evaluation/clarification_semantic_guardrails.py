"""Compatibility alias for the active one-way clarification conformance gate.

ADR 0014's return/duration evaluator is historical and cannot run against the
one-way request contract.  This module deliberately keeps the old import path
working while routing callers to the active typed controller checks.
"""

from award_agent.evaluation.one_way_award_clarification import (
    DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES as DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES,
)
from award_agent.evaluation.one_way_award_clarification import (
    OneWayAwardClarificationFixtureError as ClarificationSemanticGuardrailError,
)
from award_agent.evaluation.one_way_award_clarification import (
    preflight_one_way_award_clarification_cases as preflight_clarification_semantic_guardrail_cases,
)
from award_agent.evaluation.one_way_award_clarification import (
    run_offline_one_way_award_clarification_eval as run_offline_clarification_semantic_guardrails,
)

__all__ = [
    "DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES",
    "ClarificationSemanticGuardrailError",
    "preflight_clarification_semantic_guardrail_cases",
    "run_offline_clarification_semantic_guardrails",
]
