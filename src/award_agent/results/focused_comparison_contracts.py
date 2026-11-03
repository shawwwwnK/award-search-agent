"""V11 temporal comparison references and their source-owned resolved cards."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from award_agent.search_planning.contracts import PlanningContractModel

from .contracts import CheckFinding, InputTokenReceipt, ResultsConfig, WriterReceipt
from .interactive_contracts import InteractivePreparedInput, InteractiveSettings
from .structured_contracts import (
    ResolvedStructuredBlock,
    StructuredBlock,
    StructuredSelection,
)
from .workspace_contracts import WorkspaceEvidence


class TemporalComparisonSource(PlanningContractModel):
    origin: str
    destination: str
    departure_local_iso: str | None
    arrival_local_iso: str | None
    local_iso: str | None
    instant: datetime | None
    timezone: str | None
    day_change: int | None
    elapsed_minutes: Decimal | None


class TemporalComparisonFact(PlanningContractModel):
    comparison_id: str
    metric: Literal["departure", "arrival", "elapsed"]
    first_journey_id: str
    second_journey_id: str
    first_alias: str
    second_alias: str
    first_source: TemporalComparisonSource
    second_source: TemporalComparisonSource
    difference_minutes: Decimal = Field(ge=0)
    relation: Literal["first_earlier", "second_earlier", "first_shorter", "second_shorter", "equal"]
    source_digest: str


class TemporalComparisonRegistry(PlanningContractModel):
    contract_version: Literal["focused-temporal-registry-v1"] = "focused-temporal-registry-v1"
    evidence_contract_version: Literal["results-workspace-evidence-v1", "results-workspace-evidence-v2"]
    source_digest: str
    facts: tuple[TemporalComparisonFact, ...]


class FocusedComparisonPreparedInput(InteractivePreparedInput):
    comparison_contract_version: Literal["focused-comparison-prepared-v1"] = (
        "focused-comparison-prepared-v1"
    )


class FocusedComparisonBlock(PlanningContractModel):
    kind: Literal["comparison"] = "comparison"
    comparison_id: str


class FocusedComparisonDocument(PlanningContractModel):
    contract_version: Literal["results-focused-document-v1"] = "results-focused-document-v1"
    selection: StructuredSelection
    blocks: tuple[StructuredBlock | FocusedComparisonBlock, ...] = Field(min_length=1)


class ResolvedFocusedComparisonBlock(PlanningContractModel):
    kind: Literal["comparison"] = "comparison"
    comparison: TemporalComparisonFact


class ResolvedFocusedComparisonAnswer(PlanningContractModel):
    contract_version: Literal["results-focused-resolved-v1"] = "results-focused-resolved-v1"
    selected_journey_ids: tuple[str, ...]
    blocks: tuple[ResolvedStructuredBlock | ResolvedFocusedComparisonBlock, ...]
    availability_guidance: str
    findings: tuple[CheckFinding, ...] = ()


class FocusedComparisonPass(PlanningContractModel):
    phase: Literal["selection", "composition", "correction"]
    outcome: Literal["recoverable", "api_error", "generation_error", "measurement_error", "context_limit"]
    request: dict[str, object]
    request_digest: str
    input_bytes: int = Field(ge=0)
    estimated_total_tokens: int = Field(ge=0)
    prompt_digest: str
    schema_digest: str
    input_token_receipt: InputTokenReceipt | None = None
    writer_called: bool
    writer_receipt: WriterReceipt | None = None
    returned_service_tier: str | None = None
    raw_wire: str | None = None
    selection: StructuredSelection | None = None
    document: FocusedComparisonDocument | None = None
    findings: tuple[CheckFinding, ...] = ()
    error: str | None = None
    failure_subtype: Literal["api_error", "refusal", "incomplete", "schema_error"] | None = None

    @model_validator(mode="after")
    def v11_shape(self) -> FocusedComparisonPass:
        if self.phase == "selection" and (self.document is not None or self.findings):
            raise ValueError("selection pass cannot have a document or findings")
        if self.phase in {"composition", "correction"} and self.selection is not None:
            raise ValueError("authoring pass cannot contain a selection")
        return self


class FocusedResultsArtifactV11(PlanningContractModel):
    contract_version: Literal["results-artifact-v11"] = "results-artifact-v11"
    evidence: WorkspaceEvidence
    config: ResultsConfig
    selector_settings: InteractiveSettings
    composer_settings: InteractiveSettings
    correction_settings: InteractiveSettings
    selector_prepared: InteractivePreparedInput
    focus_prepared: FocusedComparisonPreparedInput | None = None
    comparison_registry: TemporalComparisonRegistry | None = None
    passes: tuple[FocusedComparisonPass, ...]
    generation_outcome: Literal["success", "api_error", "generation_error", "context_limit", "measurement_error"]
    validation_outcome: Literal["clean", "annotated", "unavailable"]
    delivery_outcome: Literal["delivered", "not_delivered"]
    resolved: ResolvedFocusedComparisonAnswer | None = None
    resolved_digest: str | None = None
    runtime_seconds: float = Field(ge=0)
    selected_pass_index: int | None = None
    selection_reason: Literal["initial_only", "correction_fewer_failures",
                              "correction_tie", "initial_fewer_failures",
                              "no_recoverable_draft"]
