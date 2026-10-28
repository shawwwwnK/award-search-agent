"""Versioned receipts for the two-pass focused Results channel."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from award_agent.search_planning.contracts import PlanningContractModel

from .contracts import CheckFinding, InputTokenReceipt, ResultsConfig, WriterReceipt
from .interactive_contracts import InteractivePreparedInput, InteractiveSettings
from .structured_contracts import ResolvedStructuredAnswer, StructuredDocument, StructuredSelection
from .workspace_contracts import WorkspaceEvidence


class FocusedPass(PlanningContractModel):
    phase: Literal["selection", "composition"]
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
    document: StructuredDocument | None = None
    findings: tuple[CheckFinding, ...] = ()
    error: str | None = None
    failure_subtype: Literal["api_error", "refusal", "incomplete", "schema_error"] | None = None

    @model_validator(mode="after")
    def phase_shape(self) -> FocusedPass:
        if self.phase == "selection" and (self.document is not None or self.findings):
            raise ValueError("selection pass cannot contain a document or findings")
        if self.phase == "composition" and self.selection is not None:
            raise ValueError("composition pass cannot contain a selection")
        return self


class FocusedResultsArtifact(PlanningContractModel):
    contract_version: Literal["results-artifact-v8"] = "results-artifact-v8"
    evidence: WorkspaceEvidence
    config: ResultsConfig
    selector_settings: InteractiveSettings
    composer_settings: InteractiveSettings
    selector_prepared: InteractivePreparedInput
    focus_prepared: InteractivePreparedInput | None = None
    passes: tuple[FocusedPass, ...]
    generation_outcome: Literal["success", "api_error", "generation_error", "context_limit", "measurement_error"]
    validation_outcome: Literal["clean", "annotated", "unavailable"]
    delivery_outcome: Literal["delivered", "not_delivered"]
    resolved: ResolvedStructuredAnswer | None = None
    resolved_digest: str | None = None
    runtime_seconds: float = Field(ge=0)
