"""Versioned limits for deterministic search-strategy compilation."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from award_agent.search_planning.contracts import PlanningContractModel


class PlanningPolicy(PlanningContractModel):
    """One current, identity-bound policy for the 2C compiler.

    The endpoint-group fields remain because grounding is part of the compiler. The
    endpoint-pair guard is a provider-independent, all-or-nothing structural safety
    boundary. It never prunes mandatory pairs or supplemental relationships.
    """

    policy_version: Literal["search-planning-compilation-v2"] = (
        "search-planning-compilation-v2"
    )
    max_automatic_group_airports: int = Field(default=3, ge=1, le=5)
    hard_max_automatic_group_airports: int = Field(default=5, ge=1, le=5)
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

    @model_validator(mode="after")
    def validate_policy_invariants(self) -> PlanningPolicy:
        if self.max_automatic_group_airports > self.hard_max_automatic_group_airports:
            raise ValueError("automatic airport cap cannot exceed its hard maximum")
        return self

    def effective_group_cap(self, snapshot_policy_cap: int) -> int:
        return min(
            self.max_automatic_group_airports,
            self.hard_max_automatic_group_airports,
            snapshot_policy_cap,
        )
