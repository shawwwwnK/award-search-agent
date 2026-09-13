"""Versioned limits for deterministic airport-group selection."""

from __future__ import annotations

from pydantic import Field, model_validator

from award_agent.search_planning.contracts import PlanningContractModel


class PlanningPolicy(PlanningContractModel):
    """Versioned bounded policy for endpoint-market planning."""

    policy_version: str = Field(default="search-planning-v1", min_length=1)
    max_automatic_group_airports: int = Field(default=3, ge=1, le=5)
    hard_max_automatic_group_airports: int = Field(default=5, ge=1, le=5)
    knowledge_freshness_policy_version: str = Field(default="knowledge-freshness-v1", min_length=1)
    max_source_evidence_age_days: int = Field(default=365, ge=0)
    max_endpoint_pairs: int = Field(default=25, ge=1)
    max_input_window_days: int = Field(default=31, ge=1)
    # These are planner work bounds, not provider limits or customer-facing
    # itinerary restrictions.  Endpoint probes are always selected first.
    max_outgoing_route_edges_per_endpoint_pair: int = Field(default=20, ge=0, le=20)
    max_path_candidate_exploration: int = Field(default=20, ge=0)
    max_path_hypotheses: int = Field(default=12, ge=0)
    max_total_award_search_items: int = Field(default=40, ge=1)
    max_date_expanded_work_days: int = Field(default=1400, ge=1)

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
