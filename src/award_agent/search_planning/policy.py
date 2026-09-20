"""Versioned limits for deterministic search-strategy compilation."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from award_agent.search_planning.contracts import PlanningContractModel

StrategyTypeName = Literal["origin_access", "destination_access", "scoped_hub"]


class PlanningPolicy(PlanningContractModel):
    """One current, identity-bound policy for the 2C compiler.

    The endpoint-group fields remain because grounding is part of the compiler.
    The other limits bound compiler output; they are not provider limits.
    """

    policy_version: Literal["search-planning-compilation-v1"] = (
        "search-planning-compilation-v1"
    )
    max_automatic_group_airports: int = Field(default=3, ge=1, le=5)
    hard_max_automatic_group_airports: int = Field(default=5, ge=1, le=5)
    knowledge_freshness_policy_version: str = Field(default="knowledge-freshness-v1", min_length=1)
    max_source_evidence_age_days: int = Field(default=365, ge=0)
    max_input_window_days: int = Field(default=31, ge=1)
    max_mandatory_endpoint_pairs: int = Field(default=100, ge=1)
    max_supplemental_relationship_bundles: int = Field(default=24, ge=0)
    max_unique_logical_queries: int = Field(default=128, ge=1)
    max_query_date_days: int = Field(default=4000, ge=1)
    strategy_type_priority: tuple[StrategyTypeName, ...] = (
        "origin_access",
        "destination_access",
        "scoped_hub",
    )
    later_component_start_offset_days: Literal[-1] = -1
    later_component_end_offset_days: Literal[2] = 2

    @model_validator(mode="after")
    def validate_policy_invariants(self) -> PlanningPolicy:
        if self.max_automatic_group_airports > self.hard_max_automatic_group_airports:
            raise ValueError("automatic airport cap cannot exceed its hard maximum")
        expected_priority = ("origin_access", "destination_access", "scoped_hub")
        if self.strategy_type_priority != expected_priority:
            raise ValueError(
                "strategy priority must be the complete canonical first-slice order"
            )
        if self.max_unique_logical_queries < self.max_mandatory_endpoint_pairs:
            raise ValueError(
                "unique-query budget must admit the complete maximum mandatory baseline"
            )
        if self.max_query_date_days < (
            self.max_mandatory_endpoint_pairs * self.max_input_window_days
        ):
            raise ValueError(
                "query-date budget must admit the complete maximum mandatory baseline"
            )
        return self

    def effective_group_cap(self, snapshot_policy_cap: int) -> int:
        return min(
            self.max_automatic_group_airports,
            self.hard_max_automatic_group_airports,
            snapshot_policy_cap,
        )
