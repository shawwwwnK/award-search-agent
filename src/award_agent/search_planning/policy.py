"""Versioned limits for deterministic search-strategy compilation."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from award_agent.search_planning.contracts import PlanningContractModel


class PlanningPolicy(PlanningContractModel):
    """One current, identity-bound policy for the 2C compiler.

    The endpoint-pair guard is a provider-independent, all-or-nothing structural safety
    boundary. It never prunes mandatory pairs or supplemental relationships.
    """

    policy_version: Literal["search-planning-compilation-v3"] = (
        "search-planning-compilation-v3"
    )
    knowledge_freshness_policy_version: str = Field(default="knowledge-freshness-v1", min_length=1)
    max_source_evidence_age_days: int = Field(default=365, ge=0)
    max_structural_endpoint_pairs: int = Field(
        default=100,
        ge=1,
        description=(
            "All-pairs materialization safety bound. It covers the active single-location "
            "10 x 10 envelope and prevents unbounded multi-location cross-products; it is "
            "not a provider limit or a claim that aggregate upstream endpoints are bounded."
        ),
    )
    later_component_start_offset_days: Literal[-1] = -1
    later_component_end_offset_days: Literal[2] = 2
