"""Versioned receipts for the bounded V17 editorial patch pass."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, StrictInt, model_validator

from award_agent.search_planning.contracts import PlanningContractModel

from .contracts import CheckFinding, InputTokenReceipt, ResultsConfig, WriterReceipt
from .focused_comparison_contracts import (
    FocusedComparisonDocument,
    FocusedComparisonPass,
    FocusedComparisonPreparedInput,
    ResolvedFocusedComparisonAnswer,
    TemporalComparisonRegistry,
)
from .interactive_contracts import InteractivePreparedInput, InteractiveSettings
from .workspace_contracts import WorkspaceEvidence


class FocusedPatchEdit(PlanningContractModel):
    start: StrictInt = Field(ge=0)
    end: StrictInt = Field(ge=0)
    blocks: tuple[dict[str, Any], ...]


class FocusedPatch(PlanningContractModel):
    edits: tuple[FocusedPatchEdit, ...]


class FocusedPatchPass(PlanningContractModel):
    phase: Literal["editorial_revision"] = "editorial_revision"
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
    draft_digest: str
    raw_patch: str | None = None
    patch: FocusedPatch | None = None
    materialized_wire: str | None = None
    materialized_digest: str | None = None
    document: FocusedComparisonDocument | None = None
    findings: tuple[CheckFinding, ...] = ()
    error: str | None = None
    failure_subtype: Literal["api_error", "refusal", "incomplete", "schema_error"] | None = None

    @model_validator(mode="after")
    def coherent_patch(self) -> FocusedPatchPass:
        derived = (self.patch is not None or self.materialized_wire is not None or
                   self.materialized_digest is not None or self.document is not None or
                   bool(self.findings))
        if self.outcome == "recoverable":
            if (self.raw_patch is None or self.patch is None or self.materialized_wire is None or
                    self.materialized_digest is None or self.document is None or
                    self.error is not None or self.failure_subtype is not None):
                raise ValueError("recoverable editorial pass lacks complete patch evidence")
        elif derived:
            raise ValueError("failed editorial pass cannot have materialized patch evidence")
        return self


class FocusedResultsArtifactV12(PlanningContractModel):
    contract_version: Literal["results-artifact-v12"] = "results-artifact-v12"
    evidence: WorkspaceEvidence
    config: ResultsConfig
    selector_settings: InteractiveSettings
    composer_settings: InteractiveSettings
    revision_settings: InteractiveSettings
    revision_trigger: Literal["editorial_revision"] | None = None
    selector_prepared: InteractivePreparedInput
    focus_prepared: FocusedComparisonPreparedInput | None = None
    comparison_registry: TemporalComparisonRegistry | None = None
    passes: tuple[FocusedComparisonPass | FocusedPatchPass, ...]
    generation_outcome: Literal["success", "api_error", "generation_error", "context_limit", "measurement_error"]
    validation_outcome: Literal["clean", "annotated", "unavailable"]
    delivery_outcome: Literal["delivered", "not_delivered"]
    resolved: ResolvedFocusedComparisonAnswer | None = None
    resolved_digest: str | None = None
    runtime_seconds: float = Field(ge=0)
    selected_pass_index: int | None = None
    selection_reason: Literal["revision_fewer_failures", "revision_tie", "initial_fewer_failures",
                              "revision_unrecoverable", "no_recoverable_draft"]

    @model_validator(mode="after")
    def phase_sequence(self) -> FocusedResultsArtifactV12:
        if not 1 <= len(self.passes) <= 3 or [row.phase for row in self.passes] != [
                "selection", "composition", "editorial_revision"][:len(self.passes)]:
            raise ValueError("V17 phase sequence differs")
        if self.revision_trigger != ("editorial_revision" if len(self.passes) == 3 else None):
            raise ValueError("V17 revision trigger differs from attempted passes")
        return self
