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
    max_input_tokens: int | None = Field(default=None, gt=0)
    authoring_guidance: str | None = None

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


class SharedDisclosureBinding(PlanningContractModel):
    key: str = Field(min_length=1)
    journey_ids: tuple[str, ...] = Field(min_length=2)


class ResultsPart(PlanningContractModel):
    scope: Literal["shared", "journey", "benchmark", "incomplete"]
    reference_id: str | None = None
    identifier: str | None = None
    markdown: str
    claims: tuple[DeclaredClaim, ...] = ()
    disclosures: tuple[str, ...] = ()
    shared_disclosures: tuple[SharedDisclosureBinding, ...] = ()


class ResultsDocument(PlanningContractModel):
    selection: ResultsSelection
    parts: tuple[ResultsPart, ...] = Field(min_length=1)


class PreparedResultsInput(PlanningContractModel):
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"source", "slots"})
    contract_version: Literal["results-prepared-v1", "results-prepared-v2"] = "results-prepared-v1"
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


class InputTokenReceipt(PlanningContractModel):
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"raw_response"})
    method: Literal["responses_input_tokens"] = "responses_input_tokens"
    request_digest: str
    input_tokens: int = Field(ge=0, strict=True)
    raw_response: dict[str, object]

    @model_validator(mode="after")
    def valid_raw_count(self) -> InputTokenReceipt:
        raw = self.raw_response.get("input_tokens")
        if (self.raw_response.get("object") != "response.input_tokens" or
                isinstance(raw, bool) or not isinstance(raw, int) or raw != self.input_tokens):
            raise ValueError("input token receipt differs from raw response")
        return self


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
    outcome: Literal["recoverable", "api_error", "generation_error", "measurement_error"]
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
    input_token_receipt: InputTokenReceipt | None = None


class ResultsArtifact(PlanningContractModel):
    contract_version: Literal["results-artifact-v1", "results-artifact-v2", "results-artifact-v3"] = "results-artifact-v3"
    projection: SolutionProjection
    config: ResultsConfig
    prepared: PreparedResultsInput
    attempts: tuple[ResultsAttempt, ...]
    selected_attempt: int | None
    selection_reason: str
    generation_outcome: Literal["success", "api_error", "generation_error", "context_limit", "measurement_error"]
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


class ResultsInputMeasurer(Protocol):
    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt: ...


class ResultsWriterError(Exception):
    def __init__(self, outcome: Literal["api_error", "refusal", "incomplete", "schema_error"],
                 message: str, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.outcome = outcome
        self.raw_response = raw_response
