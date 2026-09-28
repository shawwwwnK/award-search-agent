"""Immutable Provider Stage contracts; no provider calls or planning mutation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from typing import Annotated, ClassVar, Literal, Protocol

from pydantic import Field, JsonValue, model_validator

from award_agent.search_planning.compilation_contracts import IdentifiedDeferredConstraint
from award_agent.search_planning.contracts import (
    FilterObligation,
    PlanningContractModel,
    ResultValidationObligation,
)

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ProviderName = Literal["seats_aero", "gfly"]
Outcome = Literal[
    "completed", "empty", "partial", "failed", "blocked", "rate_limited",
    "timeout", "malformed", "schema_drift", "budget_exhausted",
]
CoverageStatus = Literal[
    "scheduled", "attempted", "completed", "empty", "partial", "failed", "omitted"
]


def content_digest(value: object) -> str:
    """Canonical JSON SHA-256 for replay identities, never Python object hashes."""
    if isinstance(value, PlanningContractModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class RawField(PlanningContractModel):
    """Preserve absence, explicit null, unknown, and supplied zero independently."""

    state: Literal["absent", "null", "unknown", "value"] = "absent"
    value: JsonValue = None
    source_field: str | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"value"})

    @model_validator(mode="after")
    def coherent_state(self) -> RawField:
        if self.state in {"absent", "null", "unknown"} and self.value is not None:
            raise ValueError("absent/null/unknown raw fields cannot contain a known value")
        if self.state == "value" and self.value is None:
            raise ValueError("a supplied null must retain null state")
        return self

    @classmethod
    def from_mapping(cls, data: Mapping[str, JsonValue], key: str) -> RawField:
        if key not in data:
            return cls(source_field=key)
        return cls(
            state="null" if data[key] is None else "value", value=data[key], source_field=key
        )


class ValidationFinding(PlanningContractModel):
    code: str = Field(min_length=1)
    severity: Literal["info", "unknown", "warning", "error"]
    message: str = Field(min_length=1)
    field: str | None = None
    observation_id: str | None = None


class EvidenceRef(PlanningContractModel):
    sha256: Sha256
    relative_path: str = Field(min_length=1)
    retrieved_at: datetime
    media_type: str = "application/json"
    sanitized: Literal[True] = True
    synthetic: bool = False

    @model_validator(mode="after")
    def safe_reference(self) -> EvidenceRef:
        from pathlib import PurePosixPath

        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts or "\\" in self.relative_path:
            raise ValueError("evidence references must stay below their evidence root")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("evidence retrieval time requires a timezone")
        return self


class ProviderCapability(PlanningContractModel):
    provider: ProviderName
    version: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    reviewed: bool = False
    evidence_digests: tuple[Sha256, ...] = ()
    rectangle_batching_accepted: bool = False
    rectangle_acceptance_evidence: tuple[Sha256, ...] = ()
    detail_strategy: Literal["none", "include_trips", "get_trips"] = "none"
    caveats: tuple[str, ...] = ()

    @model_validator(mode="after")
    def evidence_required(self) -> ProviderCapability:
        if self.reviewed and not self.evidence_digests:
            raise ValueError("reviewed capabilities require captured evidence digests")
        if self.rectangle_batching_accepted and (
            self.provider != "seats_aero" or not self.rectangle_acceptance_evidence
        ):
            raise ValueError("rectangle acceptance requires Seats.aero comparison evidence")
        return self


class ResourceBudget(PlanningContractModel):
    """Explicit caller limits; values must come from the declared capture/policy record."""

    requests: int = Field(ge=0)
    attempts: int = Field(ge=0)
    pages: int = Field(ge=0)
    detail_calls: int = Field(ge=0)
    rows: int = Field(ge=0)
    bytes: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)


class ResourceUsage(PlanningContractModel):
    requests: int = Field(default=0, ge=0)
    attempts: int = Field(default=0, ge=0)
    pages: int = Field(default=0, ge=0)
    detail_calls: int = Field(default=0, ge=0)
    rows: int = Field(default=0, ge=0)
    bytes: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)


class ExecutionPolicy(PlanningContractModel):
    version: str = Field(min_length=1)
    award_budget: ResourceBudget
    cash_budget: ResourceBudget
    budget_evidence: tuple[str, ...] = Field(min_length=1)
    direct_cash_samples: int = Field(ge=0)
    positioning_cash_samples: int = Field(ge=0)
    page_size: int = Field(ge=1, le=1000)
    request_timeout_seconds: float = Field(gt=0, allow_inf_nan=False)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    retries: Literal[0] = 0


class ProviderQuery(PlanningContractModel):
    query_id: str = Field(min_length=1)
    provider: ProviderName
    role: Literal["mandatory_award", "supplemental_award", "direct_cash", "cash_access", "cash_egress", "award_detail"]
    origins: tuple[str, ...] = Field(min_length=1)
    destinations: tuple[str, ...] = Field(min_length=1)
    start_date: date
    end_date: date
    travelers: int = Field(ge=1)
    cabins: tuple[str, ...] = ()
    filters: tuple[FilterObligation, ...] = ()
    result_validation_obligations: tuple[ResultValidationObligation, ...] = ()
    logical_query_ids: tuple[str, ...] = ()
    logical_use_ids: tuple[str, ...] = ()
    strategy_ids: tuple[str, ...] = ()
    positioning_dependency_ids: tuple[str, ...] = ()
    activation_observation_ids: tuple[str, ...] = ()
    activation_scope: str = Field(default="mandatory", min_length=1)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    page_size: int = Field(default=100, ge=1, le=1000)
    include_trips: bool = False
    detail_id: str | None = None

    @model_validator(mode="after")
    def query_shape(self) -> ProviderQuery:
        if self.end_date < self.start_date:
            raise ValueError("provider date window is reversed")
        for values in (self.origins, self.destinations):
            if len(set(values)) != len(values) or any(
                len(value) != 3 or not value.isascii() or not value.isupper()
                or not value.isalpha() for value in values
            ):
                raise ValueError("provider airport lists require unique uppercase IATA codes")
        if self.provider == "gfly" and (
            len(self.origins) != 1 or len(self.destinations) != 1
            or self.start_date != self.end_date
        ):
            raise ValueError("gfly acquisition is exactly one pair/date")
        if self.provider == "seats_aero" and self.page_size < 10:
            raise ValueError("Seats.aero Cached Search take must be at least 10")
        if self.role in {"cash_access", "cash_egress"} and (
            not self.positioning_dependency_ids or not self.activation_observation_ids
        ):
            raise ValueError("positioning cash requires a dependency and observed award evidence")
        if self.role == "award_detail" and not self.detail_id:
            raise ValueError("award detail calls require a captured parent availability ID")
        if self.role == "award_detail" and not self.activation_observation_ids:
            raise ValueError("award detail calls require observed parent summaries")
        if self.provider == "seats_aero" and self.role in {
            "direct_cash", "cash_access", "cash_egress"
        }:
            raise ValueError("cash roles require gfly")
        if self.provider == "gfly" and self.role not in {
            "direct_cash", "cash_access", "cash_egress"
        }:
            raise ValueError("gfly cannot execute award work")
        return self


class CapturedResponse(PlanningContractModel):
    query_id: str = Field(min_length=1)
    provider: ProviderName
    status: Outcome
    evidence: EvidenceRef
    body: JsonValue = None
    http_status: int | None = None
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    byte_count: int = Field(ge=0)
    error_code: str | None = None
    cursor: str | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"body"})


class ObservedLeg(PlanningContractModel):
    origin: str
    destination: str
    departure_local: str | None = None
    arrival_local: str | None = None
    departure_instant: datetime | None = None
    arrival_instant: datetime | None = None
    origin_timezone: str | None = None
    destination_timezone: str | None = None
    carrier: RawField = Field(default_factory=RawField)
    flight_number: RawField = Field(default_factory=RawField)
    cabin: RawField = Field(default_factory=RawField)

    @model_validator(mode="after")
    def aware_instants(self) -> ObservedLeg:
        for instant in (self.departure_instant, self.arrival_instant):
            if instant is not None and instant.tzinfo is None:
                raise ValueError("normalized instants must be timezone-aware")
        return self


class ProviderObservation(PlanningContractModel):
    observation_id: str = Field(min_length=1)
    provider: ProviderName
    backend: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    kind: Literal["award_summary", "award_itinerary", "cash_itinerary"]
    query_id: str = Field(min_length=1)
    logical_query_ids: tuple[str, ...] = ()
    logical_use_ids: tuple[str, ...] = ()
    strategy_ids: tuple[str, ...] = ()
    provider_record_id: str | None = None
    origin: str
    destination: str
    departure_date: date | None = None
    departure_local: str | None = None
    arrival_local: str | None = None
    departure_instant: datetime | None = None
    arrival_instant: datetime | None = None
    origin_timezone: str | None = None
    destination_timezone: str | None = None
    airport_sequence: tuple[str, ...] = ()
    legs: tuple[ObservedLeg, ...] = ()
    retrieved_at: datetime
    provider_updated_at: RawField = Field(default_factory=RawField)
    requested_travelers: int = Field(ge=1)
    requested_cabins: tuple[str, ...] = ()
    returned_travelers: RawField = Field(default_factory=RawField)
    cabin: RawField = Field(default_factory=RawField)
    program: RawField = Field(default_factory=RawField)
    points: RawField = Field(default_factory=RawField)
    taxes_fees: RawField = Field(default_factory=RawField)
    taxes_fees_unit: Literal["major", "minor", "unknown"] = "unknown"
    tax_currency: RawField = Field(default_factory=RawField)
    seats: RawField = Field(default_factory=RawField)
    cash_amount: RawField = Field(default_factory=RawField)
    cash_currency: RawField = Field(default_factory=RawField)
    price_scope: Literal["per_traveler", "party", "unknown"] = "unknown"
    duration_minutes: RawField = Field(default_factory=RawField)
    stops: RawField = Field(default_factory=RawField)
    carriers: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1)
    findings: tuple[ValidationFinding, ...] = ()
    raw_fields: dict[str, RawField] = Field(default_factory=dict)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"raw_fields"})

    @model_validator(mode="after")
    def observed_scope(self) -> ProviderObservation:
        if self.retrieved_at.tzinfo is None:
            raise ValueError("observation retrieval time requires a timezone")
        for instant in (self.departure_instant, self.arrival_instant):
            if instant is not None and instant.tzinfo is None:
                raise ValueError("normalized itinerary instants must be timezone-aware")
        if self.kind == "cash_itinerary" and self.provider != "gfly":
            raise ValueError("cash observations require gfly")
        if self.kind != "cash_itinerary" and self.provider != "seats_aero":
            raise ValueError("award observations require Seats.aero")
        return self


class ParsedProviderPage(PlanningContractModel):
    query_id: str
    status: Outcome
    observations: tuple[ProviderObservation, ...] = ()
    more: bool = False
    next_cursor: str | None = None
    returned_row_count: int = Field(default=0, ge=0)
    provider_row_ids: tuple[str, ...] = ()
    findings: tuple[ValidationFinding, ...] = ()
    pair_coverage_exhaustive: bool = False

    @model_validator(mode="after")
    def page_identity(self) -> ParsedProviderPage:
        if any(item.query_id != self.query_id for item in self.observations):
            raise ValueError("parsed observations must match their physical query")
        if self.more and self.next_cursor is None:
            raise ValueError("a continued page requires its next cursor")
        return self


class ProviderAdapter(Protocol):
    def fetch(
        self, query: ProviderQuery, *, cursor: str | None, timeout_seconds: float,
        max_bytes: int,
    ) -> CapturedResponse: ...

    def parse(
        self, query: ProviderQuery, capture: CapturedResponse, *,
        airport_timezones: Mapping[str, str],
    ) -> ParsedProviderPage: ...


class ExecutionBinding(PlanningContractModel):
    run_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    effective_request_digest: Sha256
    compilation_binding_digest: Sha256
    plan_digest: Sha256
    policy_digest: Sha256
    award_capability_digest: Sha256
    cash_capability_digest: Sha256


class CoverageUnit(PlanningContractModel):
    unit_id: str = Field(min_length=1)
    kind: Literal[
        "logical_query", "mandatory_use", "strategy_use", "positioning_dependency",
        "relationship", "cash_query", "detail_query",
    ]
    logical_query_ids: tuple[str, ...] = ()
    strategy_id: str | None = None


class ProviderExecutionPlan(PlanningContractModel):
    binding: ExecutionBinding
    policy: ExecutionPolicy
    award_capability: ProviderCapability
    cash_capability: ProviderCapability
    queries: tuple[ProviderQuery, ...] = ()
    coverage_units: tuple[CoverageUnit, ...] = Field(min_length=1)
    deferred_constraints: tuple[IdentifiedDeferredConstraint, ...] = ()
    findings: tuple[ValidationFinding, ...] = ()

    @model_validator(mode="after")
    def integrity(self) -> ProviderExecutionPlan:
        if self.award_capability.provider != "seats_aero" or self.cash_capability.provider != "gfly":
            raise ValueError("execution capabilities must match their award/cash roles")
        if content_digest(self.policy) != self.binding.policy_digest:
            raise ValueError("execution policy digest mismatch")
        if content_digest(self.award_capability) != self.binding.award_capability_digest:
            raise ValueError("award capability digest mismatch")
        if content_digest(self.cash_capability) != self.binding.cash_capability_digest:
            raise ValueError("cash capability digest mismatch")
        ids = [item.query_id for item in self.queries]
        units = [item.unit_id for item in self.coverage_units]
        if len(ids) != len(set(ids)) or len(units) != len(set(units)):
            raise ValueError("execution query and coverage unit IDs must be unique")
        logical_ids = {
            unit.unit_id for unit in self.coverage_units if unit.kind == "logical_query"
        }
        use_ids = {
            unit.unit_id for unit in self.coverage_units
            if unit.kind in {"mandatory_use", "strategy_use"}
        }
        dependency_ids = {
            unit.unit_id for unit in self.coverage_units if unit.kind == "positioning_dependency"
        }
        for query in self.queries:
            if not set(query.logical_query_ids) <= logical_ids:
                raise ValueError("physical queries reference unknown logical query IDs")
            if not set(query.logical_use_ids) <= use_ids:
                raise ValueError("physical queries reference unknown logical use IDs")
            if not set(query.positioning_dependency_ids) <= dependency_ids:
                raise ValueError("physical queries reference unknown positioning dependencies")
        if any(
            not set(constraint.applies_to_query_ids) <= logical_ids
            for constraint in self.deferred_constraints
        ):
            raise ValueError("deferred constraints reference unknown logical queries")
        return self


class TransportReceipt(PlanningContractModel):
    transport_id: str = Field(min_length=1)
    query_id: str = Field(min_length=1)
    provider: ProviderName
    attempt: int = Field(ge=1)
    page: int = Field(ge=1)
    status: Outcome
    evidence: EvidenceRef
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    byte_count: int = Field(ge=0)
    returned_rows: int = Field(ge=0)
    more: bool = False
    cursor: str | None = None
    duplicate_provider_ids: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    findings: tuple[ValidationFinding, ...] = ()


class CoverageReceipt(PlanningContractModel):
    unit_id: str = Field(min_length=1)
    status: CoverageStatus
    query_ids: tuple[str, ...] = ()
    transport_ids: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    reason: str = Field(min_length=1)
    stream_complete: bool = False
    pair_coverage: Literal["observed", "empty", "unknown", "not_attempted"] = "not_attempted"

    @model_validator(mode="after")
    def truthful_empty(self) -> CoverageReceipt:
        if self.status == "empty" and (
            not self.stream_complete or self.pair_coverage != "empty"
        ):
            raise ValueError("empty coverage requires a complete pair stream")
        if self.status == "omitted" and self.transport_ids:
            raise ValueError("attempted work cannot be described as omitted")
        return self


class ProviderResultSet(PlanningContractModel):
    contract_version: Literal["provider-result-set-v1"] = "provider-result-set-v1"
    execution_plan: ProviderExecutionPlan
    status: Literal["completed", "partial", "failed", "stale"]
    observations: tuple[ProviderObservation, ...] = ()
    transport_receipts: tuple[TransportReceipt, ...] = ()
    coverage: tuple[CoverageReceipt, ...] = ()
    award_usage: ResourceUsage = Field(default_factory=ResourceUsage)
    cash_usage: ResourceUsage = Field(default_factory=ResourceUsage)
    findings: tuple[ValidationFinding, ...] = ()

    @model_validator(mode="after")
    def replay_integrity(self) -> ProviderResultSet:
        units = {item.unit_id for item in self.execution_plan.coverage_units}
        receipt_units = [item.unit_id for item in self.coverage]
        if len(receipt_units) != len(set(receipt_units)) or set(receipt_units) != units:
            raise ValueError("each execution coverage unit requires exactly one final receipt")
        observations = {item.observation_id for item in self.observations}
        transports = {item.transport_id for item in self.transport_receipts}
        query_by_id = {item.query_id: item for item in self.execution_plan.queries}
        queries = set(query_by_id)
        observation_by_id = {item.observation_id: item for item in self.observations}
        transport_by_id = {item.transport_id: item for item in self.transport_receipts}
        unit_by_id = {item.unit_id: item for item in self.execution_plan.coverage_units}
        if len(observations) != len(self.observations) or len(transports) != len(self.transport_receipts):
            raise ValueError("observation and transport IDs must be unique")
        for observation in self.observations:
            if observation.query_id not in queries:
                raise ValueError("observation references an unknown physical query")
            query = query_by_id[observation.query_id]
            if observation.provider != query.provider:
                raise ValueError("observation provider differs from its query")
            capability = (self.execution_plan.award_capability
                          if observation.provider == "seats_aero"
                          else self.execution_plan.cash_capability)
            if (observation.backend, observation.provider_version) != (
                capability.backend, capability.version
            ):
                raise ValueError("observation backend/version differs from bound capability")
            if observation.origin not in query.origins or observation.destination not in query.destinations:
                raise ValueError("observation airports fall outside their physical query")
            if observation.departure_date is not None and not (
                query.start_date <= observation.departure_date <= query.end_date
            ):
                raise ValueError("observation departure date falls outside its physical query")
            if not set(observation.logical_query_ids) <= set(query.logical_query_ids) or (
                not set(observation.logical_use_ids) <= set(query.logical_use_ids)
            ) or not set(observation.strategy_ids) <= set(query.strategy_ids):
                raise ValueError("observation logical attribution must belong to its query")
        for query in self.execution_plan.queries:
            if not set(query.activation_observation_ids) <= observations:
                raise ValueError("cash activation references missing award observations")
            if any(
                observation_by_id[oid].provider != "seats_aero"
                for oid in query.activation_observation_ids
            ):
                raise ValueError("cash activation must cite award evidence")
            if query.role == "award_detail" and any(
                observation_by_id[oid].kind != "award_summary"
                or observation_by_id[oid].provider_record_id != query.detail_id
                or not set(observation_by_id[oid].logical_query_ids) <= set(query.logical_query_ids)
                for oid in query.activation_observation_ids
            ):
                raise ValueError("award detail activation must cite its exact availability summary")
        for receipt in self.transport_receipts:
            if receipt.query_id not in queries or not set(receipt.observation_ids) <= observations:
                raise ValueError("transport references unknown queries or observations")
            if receipt.provider != query_by_id[receipt.query_id].provider:
                raise ValueError("transport provider differs from its query")
            if any(
                observation_by_id[oid].query_id != receipt.query_id
                for oid in receipt.observation_ids
            ):
                raise ValueError("transport cannot claim another query's observation")
            if any(
                receipt.evidence not in observation_by_id[oid].evidence
                for oid in receipt.observation_ids
            ):
                raise ValueError("transport observations must retain their captured evidence")
        for coverage_receipt in self.coverage:
            if not set(coverage_receipt.query_ids) <= queries or not set(coverage_receipt.transport_ids) <= transports:
                raise ValueError("coverage references unknown queries or transports")
            if not set(coverage_receipt.observation_ids) <= observations:
                raise ValueError("coverage references unknown observations")
            if any(
                transport_by_id[tid].query_id not in coverage_receipt.query_ids
                for tid in coverage_receipt.transport_ids
            ) or any(
                observation_by_id[oid].query_id not in coverage_receipt.query_ids
                for oid in coverage_receipt.observation_ids
            ):
                raise ValueError("coverage evidence must belong to its attributed queries")
            attributed_transports = tuple(
                transport_by_id[tid] for tid in coverage_receipt.transport_ids
            )
            attributed_observations = {
                oid for transport in attributed_transports for oid in transport.observation_ids
            }
            if set(coverage_receipt.observation_ids) != attributed_observations:
                raise ValueError("coverage observations must reconcile to its transport evidence")
            if coverage_receipt.status in {"completed", "empty"}:
                if (
                    not coverage_receipt.stream_complete or not attributed_transports
                    or any(transport.status not in {"completed", "empty"} for transport in attributed_transports)
                    or {transport.query_id for transport in attributed_transports} != set(coverage_receipt.query_ids)
                ):
                    raise ValueError("completed coverage requires successful complete transport streams")
                for query_id in coverage_receipt.query_ids:
                    terminal = max(
                        (transport for transport in attributed_transports if transport.query_id == query_id),
                        key=lambda transport: (transport.page, transport.attempt),
                    )
                    if terminal.more:
                        raise ValueError("completed coverage cannot hide an interrupted page stream")
            unit = unit_by_id[coverage_receipt.unit_id]
            for query_id in coverage_receipt.query_ids:
                query = query_by_id[query_id]
                if unit.kind in {"logical_query", "mandatory_use", "strategy_use", "relationship"}:
                    if query.provider != "seats_aero":
                        raise ValueError("award graph coverage requires award-provider queries")
                    if unit.logical_query_ids and not (
                        set(query.logical_query_ids) & set(unit.logical_query_ids)
                    ):
                        raise ValueError("coverage query is unrelated to the logical graph unit")
                if unit.kind in {"mandatory_use", "strategy_use"} and (
                    unit.unit_id not in query.logical_use_ids
                ):
                    raise ValueError("coverage query does not serve the named logical use")
                if unit.kind == "positioning_dependency" and (
                    unit.unit_id not in query.positioning_dependency_ids
                ):
                    raise ValueError("positioning coverage must cite its own dependency query")
                if unit.kind == "cash_query" and (
                    query.provider != "gfly" or unit.unit_id != f"cash:{query_id}"
                ):
                    raise ValueError("cash coverage must cite its exact cash query")
                if unit.kind == "detail_query" and (
                    query.role != "award_detail" or unit.unit_id != f"detail:{query_id}"
                ):
                    raise ValueError("detail coverage must cite its exact award detail query")
        observed_by_transports = {
            oid for receipt in self.transport_receipts for oid in receipt.observation_ids
        }
        if observed_by_transports != observations:
            raise ValueError("every normalized observation must be attributed to a transport")
        for provider, usage in (("seats_aero", self.award_usage), ("gfly", self.cash_usage)):
            provider_receipts = tuple(
                item for item in self.transport_receipts if item.provider == provider
            )
            budget = (
                self.execution_plan.policy.award_budget if provider == "seats_aero"
                else self.execution_plan.policy.cash_budget
            )
            seen_queries: set[str] = set()
            prior_rows = 0
            prior_bytes = 0
            prior_elapsed = 0.0
            prior_pages = 0
            prior_details = 0
            for attempt_index, attempt_receipt in enumerate(provider_receipts):
                is_detail = query_by_id[attempt_receipt.query_id].role == "award_detail"
                if (
                    attempt_index >= budget.attempts
                    or (attempt_receipt.query_id not in seen_queries and len(seen_queries) >= budget.requests)
                    or (is_detail and prior_details >= budget.detail_calls)
                    or (not is_detail and prior_pages >= budget.pages)
                    or prior_rows >= budget.rows or prior_bytes >= budget.bytes
                    or prior_elapsed >= budget.elapsed_seconds
                ):
                    raise ValueError("transport receipt records a call after its resource budget was exhausted")
                seen_queries.add(attempt_receipt.query_id)
                prior_rows += attempt_receipt.returned_rows
                prior_bytes += attempt_receipt.byte_count
                prior_elapsed += attempt_receipt.elapsed_seconds
                prior_pages += not is_detail
                prior_details += is_detail
            expected_counts = {
                "requests": len({item.query_id for item in provider_receipts}),
                "attempts": len(provider_receipts),
                "pages": sum(
                    query_by_id[item.query_id].role != "award_detail"
                    for item in provider_receipts
                ),
                "detail_calls": sum(
                    query_by_id[item.query_id].role == "award_detail"
                    for item in provider_receipts
                ),
                "rows": sum(item.returned_rows for item in provider_receipts),
                "bytes": sum(item.byte_count for item in provider_receipts),
            }
            if any(getattr(usage, key) != count for key, count in expected_counts.items()):
                raise ValueError("resource usage must reconcile exactly to transport receipts")
            elapsed = sum(item.elapsed_seconds for item in provider_receipts)
            if abs(usage.elapsed_seconds - elapsed) > 1e-6:
                raise ValueError("resource elapsed time must reconcile to transport receipts")
        if self.status == "completed" and any(
            receipt.status not in {"completed", "empty"} for receipt in self.coverage
        ):
            raise ValueError("completed result cannot hide unfinished coverage")
        return self
