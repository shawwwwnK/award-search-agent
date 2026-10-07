"""Public, replayable Results M2 contracts."""

from __future__ import annotations

import math
from typing import ClassVar, Literal, Protocol

from pydantic import Field, model_validator

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.search_planning.contracts import PlanningContractModel


class ResultsConfig(PlanningContractModel):
    model: str = Field(min_length=1)
    max_output_tokens: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)
    context_limit_tokens: int = Field(gt=0)
    prompt_overhead_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_settings(self) -> ResultsConfig:
        if not self.model.strip() or not math.isfinite(self.timeout_seconds):
            raise ValueError("model and timeout must be usable finite settings")
        return self


class ResultsSelection(PlanningContractModel):
    journey_ids: tuple[str, ...] = ()
    benchmark_observation_id: str | None = None
    incomplete_observation_ids: tuple[str, ...] = ()
    excluded_journey_ids: tuple[str, ...] = ()


class DeclaredClaim(PlanningContractModel):
    claim_id: str = Field(min_length=1)
    kind: Literal["cabin", "connection_protection", "price_scope", "comparison", "eligibility", "other"]
    proposition: str = Field(min_length=1)
    scope_ids: tuple[str, ...] = ()
    text: str = Field(min_length=1)


class ResultsPart(PlanningContractModel):
    scope: Literal["shared", "journey", "benchmark", "incomplete"]
    reference_id: str | None = None
    identifier: str | None = None
    markdown: str
    claims: tuple[DeclaredClaim, ...] = ()
    disclosures: tuple[str, ...] = ()


class ResultsDocument(PlanningContractModel):
    selection: ResultsSelection
    parts: tuple[ResultsPart, ...] = Field(min_length=1)


class PreparedResultsInput(PlanningContractModel):
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"source", "slots"})
    contract_version: Literal["results-prepared-v1"] = "results-prepared-v1"
    source_digest: str
    source: dict[str, object]
    slots: dict[str, dict[str, str]]
    instructions: str
    input_bytes: int = Field(ge=0)
    estimated_input_tokens: int = Field(ge=0)
    estimated_total_tokens: int = Field(ge=0)


class WriterReceipt(PlanningContractModel):
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"usage"})
    raw_response: str | None = None
    status: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    latency_seconds: float | None = None


class CheckFinding(PlanningContractModel):
    code: str
    outcome: Literal["supported", "failed", "unchecked", "insufficient_evidence"]
    scope: Literal["shared", "journey", "benchmark", "incomplete"]
    reference_id: str | None = None
    part_index: int | None = None
    claim_id: str | None = None
    message: str
    supplied_fact: str | None = None


class ValidationNotice(PlanningContractModel):
    code: str
    scope: Literal["shared", "journey", "benchmark", "incomplete"]
    reference_id: str | None = None
    part_index: int | None = None
    claim_id: str | None = None
    text: str


class RenderedFact(PlanningContractModel):
    part_index: int
    scope: str
    reference_id: str | None
    key: str
    value: str


class ResultsAttempt(PlanningContractModel):
    phase: Literal["initial", "correction"]
    outcome: Literal["recoverable", "api_error", "generation_error"]
    document: ResultsDocument | None = None
    findings: tuple[CheckFinding, ...] = ()
    error: str | None = None
    failure_subtype: Literal["api_error", "refusal", "incomplete", "schema_error"] | None = None
    writer_receipt: WriterReceipt | None = None
    input_bytes: int = Field(ge=0)
    estimated_total_tokens: int = Field(ge=0)
    prompt_digest: str | None = None
    schema_digest: str | None = None
    writer_called: bool = True


class ResultsArtifact(PlanningContractModel):
    contract_version: Literal["results-artifact-v1"] = "results-artifact-v1"
    projection: SolutionProjection
    config: ResultsConfig
    prepared: PreparedResultsInput
    attempts: tuple[ResultsAttempt, ...]
    selected_attempt: int | None
    selection_reason: str
    generation_outcome: Literal["success", "api_error", "generation_error", "context_limit"]
    validation_outcome: Literal["clean", "annotated", "unavailable"]
    delivery_outcome: Literal["delivered", "not_delivered"]
    notices: tuple[ValidationNotice, ...] = ()
    inserted_facts: tuple[RenderedFact, ...] = ()
    rendered_markdown: str = ""
    rendered_digest: str | None = None


class ResultsWriter(Protocol):
    def author(
        self,
        prepared: PreparedResultsInput,
        config: ResultsConfig,
        feedback: tuple[CheckFinding, ...] = (),
        previous_document: ResultsDocument | None = None,
    ) -> ResultsDocument: ...


class ResultsWriterError(Exception):
    def __init__(self, outcome: Literal["api_error", "refusal", "incomplete", "schema_error"],
                 message: str, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.outcome = outcome
        self.raw_response = raw_response
