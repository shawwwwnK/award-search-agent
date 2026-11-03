"""Saved category-led Results experiment and source-resolved display contract."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from award_agent.search_planning.contracts import PlanningContractModel

from .contracts import CheckFinding, ResultsConfig
from .focused_contracts import FocusedPass
from .interactive_contracts import InteractivePreparedInput, InteractiveSettings
from .workspace_contracts import (
    ComponentView,
    ComponentViewV1,
    JourneyView,
    LeadView,
    WorkspaceEvidence,
)


class CategoryBlock(PlanningContractModel):
    kind: Literal["text", "journey_card", "lead_card", "cash_sentence"]
    text: str
    label: str | None = None
    canonical_id: str | None = None
    journey: JourneyView | None = None
    award_component: ComponentView | ComponentViewV1 | None = None
    cash_component: ComponentView | ComponentViewV1 | None = None
    lead: LeadView | None = None
    lead_component: ComponentView | ComponentViewV1 | None = None
    benchmark_component: ComponentView | ComponentViewV1 | None = None
    ranking_assessments: tuple[dict[str, object], ...] = ()


class CategoryAnswer(PlanningContractModel):
    contract_version: Literal["results-category-resolved-v1"] = "results-category-resolved-v1"
    selected_journey_ids: tuple[str, ...]
    blocks: tuple[CategoryBlock, ...]
    availability_guidance: str
    findings: tuple[CheckFinding, ...] = ()


class CategoryArtifact(PlanningContractModel):
    contract_version: Literal["results-category-artifact-v1"] = "results-category-artifact-v1"
    profile: str
    evidence: WorkspaceEvidence
    config: ResultsConfig
    selector_settings: InteractiveSettings
    composer_settings: InteractiveSettings
    correction_settings: InteractiveSettings
    selector_prepared: InteractivePreparedInput
    focus_prepared: InteractivePreparedInput | None = None
    passes: tuple[FocusedPass, ...]
    selection_findings: tuple[CheckFinding, ...] = ()
    selected_pass_index: int | None = None
    generation_outcome: Literal["success", "api_error", "generation_error", "context_limit", "measurement_error"]
    validation_outcome: Literal["clean", "annotated", "unavailable"]
    delivery_outcome: Literal["delivered", "not_delivered"]
    resolved: CategoryAnswer | None = None
    resolved_digest: str | None = None
    runtime_seconds: float = Field(ge=0)
