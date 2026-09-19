"""Deterministic validation and replay for optional gateway-search hypotheses.

This is deliberately a boundary before search-plan compilation.  The model may
suggest airport codes and applicability; this module verifies only catalog
identity, retained-facility metadata, bounded relationships, and the versioned
planning-market policy.  It does not infer or attest routes, schedules, awards,
or feasibility.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import Field, model_validator

from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    PlanningContractModel,
    SelectedAirport,
)
from award_agent.search_planning.gateway_generator import (
    GATEWAY_GENERATOR_ADAPTER_VERSION,
    GATEWAY_GENERATOR_PROMPT_VERSION,
    GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
    DestinationAccessGatewayProposal,
    GatewayCandidateProposal,
    GatewayEndpointMarketAssessment,
    GatewayGeneratorModelInput,
    GatewayOutboundDateContext,
    GatewayScopeDestinationReference,
    GatewayScopeOriginReference,
    IntermediateHubProposal,
    IntermediateHubScopeProposal,
    OriginAccessGatewayProposal,
)
from award_agent.search_planning.knowledge import Airport
from award_agent.search_planning.market_policy import (
    MarketGenerationGate,
    MarketGenerationGateStatus,
    PlanningMarketCatalogRepository,
    PlanningMarketPolicy,
    classify_and_gate_airport_markets,
    planning_market_policy_digest,
)

_IATA = re.compile(r"^[A-Z]{3}$")


class GatewayCandidateGenerator(Protocol):
    """Narrow optional-generation seam; implementations make one proposal call."""

    def propose(self, model_input: GatewayGeneratorModelInput) -> GatewayCandidateProposal: ...


class GatewayDiscoveryCatalogRepository(PlanningMarketCatalogRepository, Protocol):
    """The catalog facts required by 2B validation, independent of planner topology."""

    def lookup_airport_iata(self, iata: str) -> Airport | None: ...


class GatewayDiscoveryGeneratorConfiguration(PlanningContractModel):
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    response_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_version: str = Field(min_length=1)


class GatewayCaptureStatus(str, Enum):
    NOT_EXPOSED = "not_exposed"
    CAPTURED = "captured"
    ACCESSOR_FAILURE = "accessor_failure"
    INVALID_RECEIPT = "invalid_receipt"


class GatewayGeneratorInvocation(PlanningContractModel):
    """Redacted adapter receipt; raw traces stay in the evaluation-only trace sink."""

    usage: dict[str, int] | None = None
    usage_capture_status: GatewayCaptureStatus
    trace_capture_status: GatewayCaptureStatus
    trace_count: int = Field(ge=0)
    trace_error_count: int = Field(ge=0)
    trace_latency_seconds: float | None = Field(default=None, ge=0)
    capture_issue_codes: tuple[str, ...] = ()
    _copy_on_read_fields = frozenset({"usage", "capture_issue_codes"})


DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION = GatewayDiscoveryGeneratorConfiguration(
    model="unspecified",
    prompt_version=GATEWAY_GENERATOR_PROMPT_VERSION,
    response_schema_sha256=GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
    adapter_version=GATEWAY_GENERATOR_ADAPTER_VERSION,
)


class GatewayDiscoveryInput(PlanningContractModel):
    """Already-selected endpoints and resolved date context, never raw request text."""

    origin_endpoints: tuple[SelectedAirport, ...]
    destination_endpoints: tuple[SelectedAirport, ...]
    outbound_date: GatewayOutboundDateContext
    upstream_selection_record_ids: tuple[str, ...] = ()
    upstream_selection_record_digests: tuple[str, ...] = ()
    _copy_on_read_fields = frozenset({"origin_endpoints", "destination_endpoints", "outbound_date"})

    @model_validator(mode="after")
    def validate_upstream_receipts(self) -> GatewayDiscoveryInput:
        if len(self.upstream_selection_record_ids) != len(set(self.upstream_selection_record_ids)):
            raise ValueError("upstream selection-record IDs must be unique")
        if self.upstream_selection_record_digests != tuple(
            sorted(set(self.upstream_selection_record_digests))
        ) or any(not _is_sha256(item) for item in self.upstream_selection_record_digests):
            raise ValueError(
                "upstream selection-record digests must be sorted unique SHA-256 values"
            )
        return self


class GatewayDiscoveryIssueStage(str, Enum):
    GATE = "gate"
    GENERATION = "generation"
    VALIDATION = "validation"
    REPLAY = "replay"


class GatewayDiscoveryIssue(PlanningContractModel):
    stage: GatewayDiscoveryIssueStage
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1200)
    pool: str | None = None
    candidate_index: int | None = Field(default=None, ge=0)
    scope_index: int | None = Field(default=None, ge=0)


class GatewayMarketComparisonStatus(str, Enum):
    MATCH = "match"
    MISMATCH_ADVISORY = "mismatch_advisory"
    MODEL_UNSPECIFIED = "model_unspecified"
    POLICY_UNKNOWN = "policy_unknown"
    ASSESSMENT_UNRECOGNIZED = "assessment_unrecognized"
    NOT_EVALUATED = "not_evaluated"


class GatewayMarketComparison(PlanningContractModel):
    status: GatewayMarketComparisonStatus
    policy_market_id: str | None = None
    model_asserted_market_id: str | None = None
    advisory: bool
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_advisory_shape(self) -> GatewayMarketComparison:
        expected = self.status in {
            GatewayMarketComparisonStatus.MISMATCH_ADVISORY,
            GatewayMarketComparisonStatus.ASSESSMENT_UNRECOGNIZED,
        }
        if self.advisory != expected:
            raise ValueError("market comparison advisory flag must match comparison status")
        return self


class GatewayScopeDecision(PlanningContractModel):
    scope_index: int = Field(ge=0)
    accepted: bool
    issues: tuple[GatewayDiscoveryIssue, ...] = ()
    expanded_original_origin_iata_codes: tuple[str, ...] = ()
    expanded_original_destination_iata_codes: tuple[str, ...] = ()
    _copy_on_read_fields = frozenset({"issues"})


class GatewayCandidateDecision(PlanningContractModel):
    pool: Literal["origin_access_gateways", "destination_access_gateways", "intermediate_hubs"]
    candidate_index: int = Field(ge=0)
    proposed_airport_iata: str
    accepted: bool
    relationship_pruned: bool = False
    issues: tuple[GatewayDiscoveryIssue, ...] = ()
    market_comparison: GatewayMarketComparison
    scope_decisions: tuple[GatewayScopeDecision, ...] = ()
    _copy_on_read_fields = frozenset({"issues", "scope_decisions", "market_comparison"})


class GatewayEndpointAssessmentDecision(PlanningContractModel):
    assessment: GatewayEndpointMarketAssessment
    comparison: GatewayMarketComparison
    _copy_on_read_fields = frozenset({"assessment", "comparison"})


class AcceptedOriginAccessGateway(PlanningContractModel):
    airport: SelectedAirport
    reason: str
    material_uncertainty: str | None = None
    model_asserted_market_id: str | None = None
    supported_original_origin_iata_codes: tuple[str, ...]
    applicable_original_destination_iata_codes: tuple[str, ...]
    market_comparison: GatewayMarketComparison
    _copy_on_read_fields = frozenset({"airport", "market_comparison"})


class AcceptedDestinationAccessGateway(PlanningContractModel):
    airport: SelectedAirport
    reason: str
    material_uncertainty: str | None = None
    model_asserted_market_id: str | None = None
    supported_original_destination_iata_codes: tuple[str, ...]
    applicable_original_origin_iata_codes: tuple[str, ...]
    market_comparison: GatewayMarketComparison
    _copy_on_read_fields = frozenset({"airport", "market_comparison"})


class AcceptedIntermediateHubScope(PlanningContractModel):
    origin_side: tuple[GatewayScopeOriginReference, ...]
    destination_side: tuple[GatewayScopeDestinationReference, ...]
    reason: str | None = None
    expanded_original_origin_iata_codes: tuple[str, ...]
    expanded_original_destination_iata_codes: tuple[str, ...]


class AcceptedIntermediateHub(PlanningContractModel):
    airport: SelectedAirport
    reason: str
    material_uncertainty: str | None = None
    model_asserted_market_id: str | None = None
    market_comparison: GatewayMarketComparison
    scopes: tuple[AcceptedIntermediateHubScope, ...] = Field(min_length=1)
    _copy_on_read_fields = frozenset({"airport", "market_comparison", "scopes"})


class GatewayDiscoveryGenerationStatus(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    GENERATED = "generated"
    FAILED = "failed"


class GatewayDiscoveryOutcome(str, Enum):
    INPUT_ERROR = "input_error"
    POLICY_SKIPPED = "policy_skipped"
    SUCCESS_EMPTY = "success_empty"
    SUCCESS_NONEMPTY = "success_nonempty"
    PARTIAL_ACCEPTANCE = "partial_acceptance"
    REJECTED_ALL = "rejected_all"
    GENERATION_FAILURE = "generation_failure"
    VALIDATION_FAILURE = "validation_failure"


class GatewayMarketCoverage(str, Enum):
    COMPLETE = "complete"
    ENDPOINT_MAPPING_GAPS = "endpoint_mapping_gaps"
    CANDIDATE_MAPPING_GAPS = "candidate_mapping_gaps"
    ENDPOINT_AND_CANDIDATE_MAPPING_GAPS = "endpoint_and_candidate_mapping_gaps"


class GatewayDiscoveryResult(PlanningContractModel):
    """Immutable inspection/replay record; accepted entries stay unverified hypotheses."""

    input: GatewayDiscoveryInput
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_receipt: CatalogKnowledgeReceipt
    market_policy_version: str = Field(min_length=1)
    market_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    market_gate: MarketGenerationGate
    generator_configuration: GatewayDiscoveryGeneratorConfiguration | None = None
    generator_invocation: GatewayGeneratorInvocation | None = None
    generation_status: GatewayDiscoveryGenerationStatus
    outcome: GatewayDiscoveryOutcome
    proposal: GatewayCandidateProposal | None = None
    endpoint_market_assessment_decisions: tuple[GatewayEndpointAssessmentDecision, ...] = ()
    candidate_decisions: tuple[GatewayCandidateDecision, ...] = ()
    accepted_origin_access_gateways: tuple[AcceptedOriginAccessGateway, ...] = ()
    accepted_destination_access_gateways: tuple[AcceptedDestinationAccessGateway, ...] = ()
    accepted_intermediate_hubs: tuple[AcceptedIntermediateHub, ...] = ()
    issues: tuple[GatewayDiscoveryIssue, ...] = ()
    market_coverage: GatewayMarketCoverage
    limitations: tuple[str, ...] = Field(min_length=1)
    result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    _copy_on_read_fields = frozenset(
        {
            "input",
            "catalog_receipt",
            "market_gate",
            "generator_configuration",
            "generator_invocation",
            "proposal",
            "endpoint_market_assessment_decisions",
            "candidate_decisions",
            "accepted_origin_access_gateways",
            "accepted_destination_access_gateways",
            "accepted_intermediate_hubs",
            "issues",
        }
    )

    @model_validator(mode="after")
    def validate_result(self) -> GatewayDiscoveryResult:
        if self.input_digest != gateway_discovery_input_digest(self.input):
            raise ValueError("gateway discovery input digest does not match input")
        if self.catalog_receipt != self.market_gate.compatibility.runtime_catalog_receipt:
            raise ValueError("gateway discovery catalog receipt must match market gate")
        accepted_count = (
            len(self.accepted_origin_access_gateways)
            + len(self.accepted_destination_access_gateways)
            + len(self.accepted_intermediate_hubs)
        )
        if self.outcome is GatewayDiscoveryOutcome.INPUT_ERROR:
            if (
                self.market_gate.status is not MarketGenerationGateStatus.INPUT_ERROR
                or self.generation_status is not GatewayDiscoveryGenerationStatus.NOT_ATTEMPTED
            ):
                raise ValueError(
                    "input-error outcome must exactly reflect an unattempted input-error gate"
                )
        elif self.outcome is GatewayDiscoveryOutcome.POLICY_SKIPPED:
            if (
                self.market_gate.status is not MarketGenerationGateStatus.SKIP_SINGLE_MARKET
                or self.generation_status is not GatewayDiscoveryGenerationStatus.NOT_ATTEMPTED
            ):
                raise ValueError(
                    "policy skip must exactly reflect an unattempted single-market gate"
                )
        elif self.market_gate.status is not MarketGenerationGateStatus.GENERATION_REQUIRED:
            raise ValueError("generated gateway outcome requires a generation-required market gate")
        if self.generation_status is GatewayDiscoveryGenerationStatus.NOT_ATTEMPTED:
            if self.outcome not in {
                GatewayDiscoveryOutcome.INPUT_ERROR,
                GatewayDiscoveryOutcome.POLICY_SKIPPED,
            }:
                raise ValueError("only input-error and policy-skip outcomes may be unattempted")
            if (
                self.generator_configuration is not None
                or self.generator_invocation is not None
                or self.proposal is not None
                or self.candidate_decisions
                or accepted_count
                or self.endpoint_market_assessment_decisions
            ):
                raise ValueError("unattempted gateway result cannot carry generation payload")
        elif self.generator_configuration is None:
            raise ValueError("attempted gateway result requires generator configuration")
        if self.outcome is GatewayDiscoveryOutcome.GENERATION_FAILURE and (
            self.generation_status is not GatewayDiscoveryGenerationStatus.FAILED
        ):
            raise ValueError("generation-failure outcome must have failed generation status")
        if (
            self.outcome
            in {
                GatewayDiscoveryOutcome.SUCCESS_EMPTY,
                GatewayDiscoveryOutcome.SUCCESS_NONEMPTY,
                GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE,
                GatewayDiscoveryOutcome.REJECTED_ALL,
                GatewayDiscoveryOutcome.VALIDATION_FAILURE,
            }
            and self.generation_status is not GatewayDiscoveryGenerationStatus.GENERATED
        ):
            raise ValueError("validated gateway outcomes require a generated proposal")
        if self.generation_status is GatewayDiscoveryGenerationStatus.FAILED and (
            self.outcome is not GatewayDiscoveryOutcome.GENERATION_FAILURE
            or self.proposal is not None
            or self.candidate_decisions
            or accepted_count
        ):
            raise ValueError("failed generation cannot carry candidate validation payload")
        if (
            self.generation_status is GatewayDiscoveryGenerationStatus.GENERATED
            and self.outcome
            not in {
                GatewayDiscoveryOutcome.SUCCESS_EMPTY,
                GatewayDiscoveryOutcome.SUCCESS_NONEMPTY,
                GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE,
                GatewayDiscoveryOutcome.REJECTED_ALL,
                GatewayDiscoveryOutcome.VALIDATION_FAILURE,
            }
        ):
            raise ValueError("generated proposal must have a validation outcome")
        if (
            self.generation_status is GatewayDiscoveryGenerationStatus.GENERATED
            and self.proposal is None
        ):
            raise ValueError("generated result requires its raw structured proposal")
        if (
            self.outcome
            in {
                GatewayDiscoveryOutcome.SUCCESS_EMPTY,
                GatewayDiscoveryOutcome.REJECTED_ALL,
                GatewayDiscoveryOutcome.VALIDATION_FAILURE,
            }
            and accepted_count
        ):
            raise ValueError(
                "empty, rejected, and validation-failure outcomes cannot carry accepted candidates"
            )
        if (
            self.outcome
            in {
                GatewayDiscoveryOutcome.SUCCESS_NONEMPTY,
                GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE,
            }
            and not accepted_count
        ):
            raise ValueError("nonempty and partial outcomes require accepted candidates")
        if (
            self.outcome is GatewayDiscoveryOutcome.SUCCESS_EMPTY
            and self.proposal is not None
            and (
                self.proposal.origin_access_gateways
                or self.proposal.destination_access_gateways
                or self.proposal.intermediate_hubs
            )
        ):
            raise ValueError("successful empty generation requires all candidate pools to be empty")
        if (
            self.outcome is GatewayDiscoveryOutcome.REJECTED_ALL
            and self.proposal is not None
            and not (
                self.proposal.origin_access_gateways
                or self.proposal.destination_access_gateways
                or self.proposal.intermediate_hubs
            )
        ):
            raise ValueError("rejected-all outcome requires at least one proposed candidate")
        if self.result_digest != gateway_discovery_result_digest(self):
            raise ValueError("gateway discovery result digest does not match its canonical record")
        return self


class GatewayDiscoveryReplayError(ValueError):
    """Stored 2B record cannot be trusted against the supplied replay identities."""


_LIMITATIONS = (
    "Accepted candidates are unverified hypotheses; catalog validation does not verify connectivity.",
    "Schedules, award availability, protected connections, feasibility, and bookability are unverified.",
    "No route, itinerary, provider payload, or SearchPlan is produced by this record.",
)


def gateway_discovery_input_digest(discovery_input: GatewayDiscoveryInput) -> str:
    return _canonical_digest(discovery_input.model_dump(mode="json", round_trip=True))


def gateway_discovery_result_digest(result: GatewayDiscoveryResult) -> str:
    payload = result.model_dump(mode="json", round_trip=True)
    payload.pop("result_digest", None)
    return _canonical_digest(payload)


def discover_gateway_candidates(
    *,
    discovery_input: GatewayDiscoveryInput,
    policy: PlanningMarketPolicy,
    repository: GatewayDiscoveryCatalogRepository,
    generator_factory: Callable[[], GatewayCandidateGenerator],
    generator_configuration: GatewayDiscoveryGeneratorConfiguration,
) -> GatewayDiscoveryResult:
    """Gate and make at most one optional proposal call; failures preserve endpoint inputs."""

    gate = classify_and_gate_airport_markets(
        origin_endpoints=discovery_input.origin_endpoints,
        destination_endpoints=discovery_input.destination_endpoints,
        policy=policy,
        repository=repository,
    )
    if gate.status is MarketGenerationGateStatus.INPUT_ERROR:
        return _result(
            discovery_input=discovery_input,
            policy=policy,
            gate=gate,
            generator_configuration=None,
            generation_status=GatewayDiscoveryGenerationStatus.NOT_ATTEMPTED,
            outcome=GatewayDiscoveryOutcome.INPUT_ERROR,
            market_coverage=_coverage_for(gate, ()),
            issues=tuple(_gate_issues(gate)),
        )
    if gate.status is MarketGenerationGateStatus.SKIP_SINGLE_MARKET:
        return _result(
            discovery_input=discovery_input,
            policy=policy,
            gate=gate,
            generator_configuration=None,
            generation_status=GatewayDiscoveryGenerationStatus.NOT_ATTEMPTED,
            outcome=GatewayDiscoveryOutcome.POLICY_SKIPPED,
            market_coverage=_coverage_for(gate, ()),
        )
    generator: GatewayCandidateGenerator | None = None
    try:
        model_input = GatewayGeneratorModelInput.from_market_gate(
            gate, policy.markets, discovery_input.outbound_date
        )
        generator = generator_factory()
        proposal = generator.propose(model_input)
    except Exception as exc:  # noqa: BLE001 - optional generator implementations have no common error base.
        return _result(
            discovery_input=discovery_input,
            policy=policy,
            gate=gate,
            generator_configuration=generator_configuration,
            generator_invocation=None if generator is None else _generator_invocation(generator),
            generation_status=GatewayDiscoveryGenerationStatus.FAILED,
            outcome=GatewayDiscoveryOutcome.GENERATION_FAILURE,
            market_coverage=_coverage_for(gate, ()),
            issues=(
                GatewayDiscoveryIssue(
                    stage=GatewayDiscoveryIssueStage.GENERATION,
                    code="generator_failure",
                    message=f"optional grouped gateway generation failed: {type(exc).__name__}",
                ),
            ),
        )
    assert generator is not None
    invocation = _generator_invocation(generator)
    try:
        return validate_gateway_candidate_proposal(
            discovery_input=discovery_input,
            policy=policy,
            repository=repository,
            gate=gate,
            proposal=proposal,
            generator_configuration=generator_configuration,
            generator_invocation=invocation,
        )
    except Exception as exc:  # noqa: BLE001 - return a typed systemic validation receipt.
        return _result(
            discovery_input=discovery_input,
            policy=policy,
            gate=gate,
            generator_configuration=generator_configuration,
            generator_invocation=invocation,
            generation_status=GatewayDiscoveryGenerationStatus.GENERATED,
            outcome=GatewayDiscoveryOutcome.VALIDATION_FAILURE,
            proposal=proposal,
            market_coverage=_coverage_for(gate, ()),
            issues=(
                GatewayDiscoveryIssue(
                    stage=GatewayDiscoveryIssueStage.VALIDATION,
                    code="system_validation_failure",
                    message=f"gateway proposal could not be validated: {type(exc).__name__}",
                ),
            ),
        )


def validate_gateway_candidate_proposal(
    *,
    discovery_input: GatewayDiscoveryInput,
    policy: PlanningMarketPolicy,
    repository: GatewayDiscoveryCatalogRepository,
    gate: MarketGenerationGate,
    proposal: GatewayCandidateProposal,
    generator_configuration: GatewayDiscoveryGeneratorConfiguration,
    generator_invocation: GatewayGeneratorInvocation | None = None,
) -> GatewayDiscoveryResult:
    """Pure proposal validator used both after generation and on deterministic replay."""

    recomputed_gate = classify_and_gate_airport_markets(
        origin_endpoints=discovery_input.origin_endpoints,
        destination_endpoints=discovery_input.destination_endpoints,
        policy=policy,
        repository=repository,
    )
    if gate != recomputed_gate:
        raise ValueError("market gate does not reproduce from discovery input, policy, and catalog")
    if gate.status is not MarketGenerationGateStatus.GENERATION_REQUIRED:
        raise ValueError("gateway proposal validation requires a generation-required gate")
    if (
        gate.origin_endpoints != discovery_input.origin_endpoints
        or gate.destination_endpoints != discovery_input.destination_endpoints
    ):
        raise ValueError("market gate endpoints must exactly match gateway discovery input")
    if gate.compatibility.runtime_catalog_receipt != repository.knowledge_receipt:
        raise ValueError("market gate catalog receipt does not match validation repository")

    origin_codes = _endpoint_map(discovery_input.origin_endpoints)
    destination_codes = _endpoint_map(discovery_input.destination_endpoints)
    endpoint_decisions = _endpoint_assessment_decisions(proposal, gate)
    decisions: list[GatewayCandidateDecision] = []
    candidate_gap = False
    global_seen: set[str] = set()

    accepted_origins: list[AcceptedOriginAccessGateway] = []
    origin_attempts = 0
    for index, origin_item in enumerate(proposal.origin_access_gateways):
        origin_decision, accepted_origin, gap, consumed = _validate_origin_gateway(
            origin_item,
            index,
            origin_codes,
            destination_codes,
            repository,
            policy,
            global_seen,
            origin_attempts,
        )
        if consumed:
            origin_attempts += 1
        decisions.append(origin_decision)
        candidate_gap = candidate_gap or gap
        if accepted_origin is not None:
            accepted_origins.append(accepted_origin)

    accepted_destinations: list[AcceptedDestinationAccessGateway] = []
    destination_attempts = 0
    for index, destination_item in enumerate(proposal.destination_access_gateways):
        destination_decision, accepted_destination, gap, consumed = _validate_destination_gateway(
            destination_item,
            index,
            origin_codes,
            destination_codes,
            repository,
            policy,
            global_seen,
            destination_attempts,
        )
        if consumed:
            destination_attempts += 1
        decisions.append(destination_decision)
        candidate_gap = candidate_gap or gap
        if accepted_destination is not None:
            accepted_destinations.append(accepted_destination)

    hub_cap = 3 if accepted_origins or accepted_destinations else 5
    accepted_hubs: list[AcceptedIntermediateHub] = []
    origin_gateways = {item.airport.airport_iata: item for item in accepted_origins}
    destination_gateways = {item.airport.airport_iata: item for item in accepted_destinations}
    hub_attempts = 0
    for index, hub_item in enumerate(proposal.intermediate_hubs):
        hub_decision, accepted_hub, gap, consumed = _validate_hub(
            hub_item,
            index,
            origin_codes,
            destination_codes,
            origin_gateways,
            destination_gateways,
            repository,
            policy,
            global_seen,
            hub_attempts,
            hub_cap,
        )
        if consumed:
            hub_attempts += 1
        decisions.append(hub_decision)
        candidate_gap = candidate_gap or gap
        if accepted_hub is not None:
            accepted_hubs.append(accepted_hub)

    raw_count = (
        len(proposal.origin_access_gateways)
        + len(proposal.destination_access_gateways)
        + len(proposal.intermediate_hubs)
    )
    accepted_count = len(accepted_origins) + len(accepted_destinations) + len(accepted_hubs)
    has_rejections = any(
        not item.accepted or item.relationship_pruned for item in decisions
    ) or any(not scope.accepted for item in decisions for scope in item.scope_decisions)
    if raw_count == 0:
        outcome = GatewayDiscoveryOutcome.SUCCESS_EMPTY
    elif accepted_count == 0:
        outcome = GatewayDiscoveryOutcome.REJECTED_ALL
    elif has_rejections:
        outcome = GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE
    else:
        outcome = GatewayDiscoveryOutcome.SUCCESS_NONEMPTY
    return _result(
        discovery_input=discovery_input,
        policy=policy,
        gate=gate,
        generator_configuration=generator_configuration,
        generator_invocation=generator_invocation,
        generation_status=GatewayDiscoveryGenerationStatus.GENERATED,
        outcome=outcome,
        proposal=proposal,
        endpoint_market_assessment_decisions=tuple(endpoint_decisions),
        candidate_decisions=tuple(decisions),
        accepted_origin_access_gateways=tuple(accepted_origins),
        accepted_destination_access_gateways=tuple(accepted_destinations),
        accepted_intermediate_hubs=tuple(accepted_hubs),
        market_coverage=_coverage_for(gate, (), candidate_gap=candidate_gap),
    )


def replay_gateway_discovery_result(
    *,
    record: GatewayDiscoveryResult,
    policy: PlanningMarketPolicy,
    repository: GatewayDiscoveryCatalogRepository,
) -> GatewayDiscoveryResult:
    """Revalidate a stored proposal without a model call or accepting forged identities."""

    if record.result_digest != gateway_discovery_result_digest(record):
        raise GatewayDiscoveryReplayError("gateway discovery record digest is forged or corrupt")
    if (
        record.market_policy_version != policy.policy_version
        or record.market_policy_digest != planning_market_policy_digest(policy)
    ):
        raise GatewayDiscoveryReplayError("gateway discovery record market-policy identity differs")
    if record.catalog_receipt != repository.knowledge_receipt:
        raise GatewayDiscoveryReplayError("gateway discovery record catalog identity differs")
    fresh_gate = classify_and_gate_airport_markets(
        origin_endpoints=record.input.origin_endpoints,
        destination_endpoints=record.input.destination_endpoints,
        policy=policy,
        repository=repository,
    )
    if fresh_gate != record.market_gate:
        raise GatewayDiscoveryReplayError("gateway discovery market gate does not reproduce")
    if record.generation_status is GatewayDiscoveryGenerationStatus.GENERATED:
        if record.proposal is None or record.generator_configuration is None:
            raise GatewayDiscoveryReplayError(
                "generated gateway record lacks replayable proposal metadata"
            )
        if record.outcome is GatewayDiscoveryOutcome.VALIDATION_FAILURE:
            try:
                validate_gateway_candidate_proposal(
                    discovery_input=record.input,
                    policy=policy,
                    repository=repository,
                    gate=fresh_gate,
                    proposal=record.proposal,
                    generator_configuration=record.generator_configuration,
                    generator_invocation=record.generator_invocation,
                )
            except Exception:  # noqa: BLE001 - successful reproduction is the replay requirement.
                replayed = _result(
                    discovery_input=record.input,
                    policy=policy,
                    gate=fresh_gate,
                    generator_configuration=record.generator_configuration,
                    generator_invocation=record.generator_invocation,
                    generation_status=GatewayDiscoveryGenerationStatus.GENERATED,
                    outcome=GatewayDiscoveryOutcome.VALIDATION_FAILURE,
                    proposal=record.proposal,
                    market_coverage=_coverage_for(fresh_gate, ()),
                    issues=record.issues,
                )
            else:
                raise GatewayDiscoveryReplayError(
                    "stored systemic validation failure is not reproducible"
                )
        else:
            replayed = validate_gateway_candidate_proposal(
                discovery_input=record.input,
                policy=policy,
                repository=repository,
                gate=fresh_gate,
                proposal=record.proposal,
                generator_configuration=record.generator_configuration,
                generator_invocation=record.generator_invocation,
            )
    elif record.generation_status is GatewayDiscoveryGenerationStatus.NOT_ATTEMPTED:
        if fresh_gate.status is MarketGenerationGateStatus.INPUT_ERROR:
            replayed = _result(
                discovery_input=record.input,
                policy=policy,
                gate=fresh_gate,
                generator_configuration=None,
                generation_status=GatewayDiscoveryGenerationStatus.NOT_ATTEMPTED,
                outcome=GatewayDiscoveryOutcome.INPUT_ERROR,
                market_coverage=_coverage_for(fresh_gate, ()),
                issues=tuple(_gate_issues(fresh_gate)),
            )
        elif fresh_gate.status is MarketGenerationGateStatus.SKIP_SINGLE_MARKET:
            replayed = _result(
                discovery_input=record.input,
                policy=policy,
                gate=fresh_gate,
                generator_configuration=None,
                generation_status=GatewayDiscoveryGenerationStatus.NOT_ATTEMPTED,
                outcome=GatewayDiscoveryOutcome.POLICY_SKIPPED,
                market_coverage=_coverage_for(fresh_gate, ()),
            )
        else:
            raise GatewayDiscoveryReplayError(
                "not-attempted record contradicts generation-required gate"
            )
    else:
        # A failure has no proposal to replay. Its immutable receipt is still useful,
        # but cannot be recomputed as a semantic acceptance result.
        replayed = _result(
            discovery_input=record.input,
            policy=policy,
            gate=fresh_gate,
            generator_configuration=record.generator_configuration,
            generator_invocation=record.generator_invocation,
            generation_status=GatewayDiscoveryGenerationStatus.FAILED,
            outcome=GatewayDiscoveryOutcome.GENERATION_FAILURE,
            market_coverage=_coverage_for(fresh_gate, ()),
            issues=record.issues,
        )
    if replayed != record:
        raise GatewayDiscoveryReplayError(
            "gateway discovery record semantic output does not reproduce"
        )
    return replayed


def _validate_origin_gateway(
    item: OriginAccessGatewayProposal,
    index: int,
    origins: dict[str, SelectedAirport],
    destinations: dict[str, SelectedAirport],
    repository: GatewayDiscoveryCatalogRepository,
    policy: PlanningMarketPolicy,
    global_seen: set[str],
    attempts: int,
) -> tuple[GatewayCandidateDecision, AcceptedOriginAccessGateway | None, bool, bool]:
    pool: Literal["origin_access_gateways"] = "origin_access_gateways"
    issues, airport, comparison, gap, consumed = _candidate_identity(
        pool,
        index,
        item.airport_iata,
        item.model_asserted_market_id,
        repository,
        policy,
        global_seen,
        attempts,
        2,
    )
    if not item.reason.strip():
        issues.append(
            _issue(pool, index, "missing_candidate_reason", "candidate reason must not be blank")
        )
    refs_valid = _valid_ref_tuple(
        item.supported_original_origin_iata_codes,
        origins,
        pool,
        index,
        "supported_original_origin_iata_codes",
        issues,
    )
    applies_valid = _valid_ref_tuple(
        item.applicable_original_destination_iata_codes,
        destinations,
        pool,
        index,
        "applicable_original_destination_iata_codes",
        issues,
    )
    retained_applicable_destinations = tuple(
        code
        for code in item.applicable_original_destination_iata_codes
        if code != item.airport_iata
    )
    relationship_pruned = (
        retained_applicable_destinations != item.applicable_original_destination_iata_codes
    )
    pruning_issues: list[GatewayDiscoveryIssue] = []
    if relationship_pruned:
        pruning_issues.append(
            _issue(
                pool,
                index,
                "gateway_equals_applicable_opposite_endpoint",
                "origin access gateway was removed from an applicable original destination pairing",
            )
        )
        if not retained_applicable_destinations:
            issues.append(
                _issue(
                    pool,
                    index,
                    "no_applicable_relationship_after_self_pair_pruning",
                    "origin access gateway has no applicable destinations after self-pair pruning",
                )
            )
    if item.airport_iata in item.supported_original_origin_iata_codes:
        issues.append(
            _issue(
                pool,
                index,
                "self_supporting_gateway",
                "origin access gateway cannot support itself",
            )
        )
    accepted = not issues and airport is not None and refs_valid and applies_valid
    decision = GatewayCandidateDecision(
        pool=pool,
        candidate_index=index,
        proposed_airport_iata=item.airport_iata,
        accepted=accepted,
        relationship_pruned=relationship_pruned,
        issues=tuple(issues + pruning_issues),
        market_comparison=comparison,
    )
    selected = None if airport is None else _selected_airport(airport)
    return (
        decision,
        None
        if not accepted or selected is None
        else AcceptedOriginAccessGateway(
            airport=selected,
            reason=item.reason,
            material_uncertainty=item.material_uncertainty,
            model_asserted_market_id=item.model_asserted_market_id,
            supported_original_origin_iata_codes=item.supported_original_origin_iata_codes,
            applicable_original_destination_iata_codes=retained_applicable_destinations,
            market_comparison=comparison,
        ),
        gap,
        consumed,
    )


def _validate_destination_gateway(
    item: DestinationAccessGatewayProposal,
    index: int,
    origins: dict[str, SelectedAirport],
    destinations: dict[str, SelectedAirport],
    repository: GatewayDiscoveryCatalogRepository,
    policy: PlanningMarketPolicy,
    global_seen: set[str],
    attempts: int,
) -> tuple[GatewayCandidateDecision, AcceptedDestinationAccessGateway | None, bool, bool]:
    pool: Literal["destination_access_gateways"] = "destination_access_gateways"
    issues, airport, comparison, gap, consumed = _candidate_identity(
        pool,
        index,
        item.airport_iata,
        item.model_asserted_market_id,
        repository,
        policy,
        global_seen,
        attempts,
        2,
    )
    if not item.reason.strip():
        issues.append(
            _issue(pool, index, "missing_candidate_reason", "candidate reason must not be blank")
        )
    refs_valid = _valid_ref_tuple(
        item.supported_original_destination_iata_codes,
        destinations,
        pool,
        index,
        "supported_original_destination_iata_codes",
        issues,
    )
    applies_valid = _valid_ref_tuple(
        item.applicable_original_origin_iata_codes,
        origins,
        pool,
        index,
        "applicable_original_origin_iata_codes",
        issues,
    )
    retained_applicable_origins = tuple(
        code for code in item.applicable_original_origin_iata_codes if code != item.airport_iata
    )
    relationship_pruned = retained_applicable_origins != item.applicable_original_origin_iata_codes
    pruning_issues: list[GatewayDiscoveryIssue] = []
    if relationship_pruned:
        pruning_issues.append(
            _issue(
                pool,
                index,
                "gateway_equals_applicable_opposite_endpoint",
                "destination access gateway was removed from an applicable original origin pairing",
            )
        )
        if not retained_applicable_origins:
            issues.append(
                _issue(
                    pool,
                    index,
                    "no_applicable_relationship_after_self_pair_pruning",
                    "destination access gateway has no applicable origins after self-pair pruning",
                )
            )
    if item.airport_iata in item.supported_original_destination_iata_codes:
        issues.append(
            _issue(
                pool,
                index,
                "self_supporting_gateway",
                "destination access gateway cannot support itself",
            )
        )
    accepted = not issues and airport is not None and refs_valid and applies_valid
    decision = GatewayCandidateDecision(
        pool=pool,
        candidate_index=index,
        proposed_airport_iata=item.airport_iata,
        accepted=accepted,
        relationship_pruned=relationship_pruned,
        issues=tuple(issues + pruning_issues),
        market_comparison=comparison,
    )
    selected = None if airport is None else _selected_airport(airport)
    return (
        decision,
        None
        if not accepted or selected is None
        else AcceptedDestinationAccessGateway(
            airport=selected,
            reason=item.reason,
            material_uncertainty=item.material_uncertainty,
            model_asserted_market_id=item.model_asserted_market_id,
            supported_original_destination_iata_codes=item.supported_original_destination_iata_codes,
            applicable_original_origin_iata_codes=retained_applicable_origins,
            market_comparison=comparison,
        ),
        gap,
        consumed,
    )


def _validate_hub(
    item: IntermediateHubProposal,
    index: int,
    origins: dict[str, SelectedAirport],
    destinations: dict[str, SelectedAirport],
    origin_gateways: dict[str, AcceptedOriginAccessGateway],
    destination_gateways: dict[str, AcceptedDestinationAccessGateway],
    repository: GatewayDiscoveryCatalogRepository,
    policy: PlanningMarketPolicy,
    global_seen: set[str],
    attempts: int,
    cap: int,
) -> tuple[GatewayCandidateDecision, AcceptedIntermediateHub | None, bool, bool]:
    pool: Literal["intermediate_hubs"] = "intermediate_hubs"
    issues, airport, comparison, gap, consumed = _candidate_identity(
        pool,
        index,
        item.airport_iata,
        item.model_asserted_market_id,
        repository,
        policy,
        global_seen,
        attempts,
        cap,
    )
    if not item.reason.strip():
        issues.append(
            _issue(pool, index, "missing_candidate_reason", "candidate reason must not be blank")
        )
    scope_decisions: list[GatewayScopeDecision] = []
    accepted_scopes: list[AcceptedIntermediateHubScope] = []
    # Scope identity is the declared typed reference relationship.  Do not use
    # expanded original endpoints here: an original endpoint and an access
    # gateway that happens to support it are distinct intentional search forms.
    covered_relationships: set[tuple[str, str, str, str]] = set()
    for scope_index, scope in enumerate(item.scopes):
        scope_issues, expanded_origins, expanded_destinations = _validate_hub_scope(
            scope,
            scope_index,
            index,
            item.airport_iata,
            origins,
            destinations,
            origin_gateways,
            destination_gateways,
            pool,
        )
        relationships = {
            (
                origin_ref.kind,
                origin_ref.airport_iata,
                destination_ref.kind,
                destination_ref.airport_iata,
            )
            for origin_ref in scope.origin_side
            for destination_ref in scope.destination_side
        }
        if relationships & covered_relationships:
            scope_issues.append(
                _issue(
                    pool,
                    index,
                    "duplicate_scope_relationship",
                    "hub scope repeats a relationship covered by an earlier accepted scope",
                    scope_index,
                )
            )
        scope_ok = not scope_issues
        scope_decisions.append(
            GatewayScopeDecision(
                scope_index=scope_index,
                accepted=scope_ok,
                issues=tuple(scope_issues),
                expanded_original_origin_iata_codes=tuple(sorted(expanded_origins)),
                expanded_original_destination_iata_codes=tuple(sorted(expanded_destinations)),
            )
        )
        if scope_ok:
            covered_relationships.update(relationships)
            accepted_scopes.append(
                AcceptedIntermediateHubScope(
                    origin_side=scope.origin_side,
                    destination_side=scope.destination_side,
                    reason=scope.reason,
                    expanded_original_origin_iata_codes=tuple(sorted(expanded_origins)),
                    expanded_original_destination_iata_codes=tuple(sorted(expanded_destinations)),
                )
            )
    if not item.scopes:
        issues.append(
            _issue(pool, index, "empty_scopes", "intermediate hub must have at least one scope")
        )
    accepted = not issues and airport is not None and bool(accepted_scopes)
    decision = GatewayCandidateDecision(
        pool=pool,
        candidate_index=index,
        proposed_airport_iata=item.airport_iata,
        accepted=accepted,
        issues=tuple(issues),
        market_comparison=comparison,
        scope_decisions=tuple(scope_decisions),
    )
    selected = None if airport is None else _selected_airport(airport)
    return (
        decision,
        None
        if not accepted or selected is None
        else AcceptedIntermediateHub(
            airport=selected,
            reason=item.reason,
            material_uncertainty=item.material_uncertainty,
            model_asserted_market_id=item.model_asserted_market_id,
            market_comparison=comparison,
            scopes=tuple(accepted_scopes),
        ),
        gap,
        consumed,
    )


def _validate_hub_scope(
    scope: IntermediateHubScopeProposal,
    scope_index: int,
    candidate_index: int,
    hub_iata: str,
    origins: dict[str, SelectedAirport],
    destinations: dict[str, SelectedAirport],
    origin_gateways: dict[str, AcceptedOriginAccessGateway],
    destination_gateways: dict[str, AcceptedDestinationAccessGateway],
    pool: str,
) -> tuple[list[GatewayDiscoveryIssue], set[str], set[str]]:
    issues: list[GatewayDiscoveryIssue] = []
    origin_refs = tuple((item.kind, item.airport_iata) for item in scope.origin_side)
    destination_refs = tuple((item.kind, item.airport_iata) for item in scope.destination_side)
    if not scope.origin_side or not scope.destination_side:
        issues.append(
            _issue(
                pool,
                candidate_index,
                "empty_scope_side",
                "hub scope requires nonempty origin and destination sides",
                scope_index,
            )
        )
    if len(origin_refs) != len(set(origin_refs)) or len(destination_refs) != len(
        set(destination_refs)
    ):
        issues.append(
            _issue(
                pool,
                candidate_index,
                "duplicate_scope_reference",
                "hub scope repeats a side reference",
                scope_index,
            )
        )
    if hub_iata in {item.airport_iata for item in scope.origin_side} | {
        item.airport_iata for item in scope.destination_side
    }:
        issues.append(
            _issue(
                pool,
                candidate_index,
                "hub_equals_scope_reference",
                "hub cannot equal an endpoint reference in its scope",
                scope_index,
            )
        )

    expanded_origins: set[str] = set()
    expanded_destinations: set[str] = set()
    referenced_origin_gateways: list[AcceptedOriginAccessGateway] = []
    referenced_destination_gateways: list[AcceptedDestinationAccessGateway] = []
    for origin_ref in scope.origin_side:
        if origin_ref.kind == "original_origin":
            if origin_ref.airport_iata not in origins:
                issues.append(
                    _issue(
                        pool,
                        candidate_index,
                        "invalid_origin_scope_reference",
                        "scope original-origin reference is not an input endpoint",
                        scope_index,
                    )
                )
            else:
                expanded_origins.add(origin_ref.airport_iata)
        else:
            origin_gateway = origin_gateways.get(origin_ref.airport_iata)
            if origin_gateway is None:
                issues.append(
                    _issue(
                        pool,
                        candidate_index,
                        "rejected_or_missing_origin_gateway",
                        "scope references no accepted origin access gateway",
                        scope_index,
                    )
                )
            else:
                referenced_origin_gateways.append(origin_gateway)
                expanded_origins.update(origin_gateway.supported_original_origin_iata_codes)
    for destination_ref in scope.destination_side:
        if destination_ref.kind == "original_destination":
            if destination_ref.airport_iata not in destinations:
                issues.append(
                    _issue(
                        pool,
                        candidate_index,
                        "invalid_destination_scope_reference",
                        "scope original-destination reference is not an input endpoint",
                        scope_index,
                    )
                )
            else:
                expanded_destinations.add(destination_ref.airport_iata)
        else:
            destination_gateway = destination_gateways.get(destination_ref.airport_iata)
            if destination_gateway is None:
                issues.append(
                    _issue(
                        pool,
                        candidate_index,
                        "rejected_or_missing_destination_gateway",
                        "scope references no accepted destination access gateway",
                        scope_index,
                    )
                )
            else:
                referenced_destination_gateways.append(destination_gateway)
                expanded_destinations.update(
                    destination_gateway.supported_original_destination_iata_codes
                )
    if hub_iata in expanded_origins or hub_iata in expanded_destinations:
        issues.append(
            _issue(
                pool,
                candidate_index,
                "hub_equals_implied_endpoint",
                "hub cannot equal an endpoint of an implied scope pairing",
                scope_index,
            )
        )
    for origin_gateway in referenced_origin_gateways:
        if not expanded_destinations.issubset(
            set(origin_gateway.applicable_original_destination_iata_codes)
        ):
            issues.append(
                _issue(
                    pool,
                    candidate_index,
                    "origin_gateway_applicability_violation",
                    "scope exceeds origin gateway destination applicability",
                    scope_index,
                )
            )
    for destination_gateway in referenced_destination_gateways:
        if not expanded_origins.issubset(
            set(destination_gateway.applicable_original_origin_iata_codes)
        ):
            issues.append(
                _issue(
                    pool,
                    candidate_index,
                    "destination_gateway_applicability_violation",
                    "scope exceeds destination gateway origin applicability",
                    scope_index,
                )
            )
    return issues, expanded_origins, expanded_destinations


def _candidate_identity(
    pool: str,
    index: int,
    iata: str,
    model_market_id: str | None,
    repository: GatewayDiscoveryCatalogRepository,
    policy: PlanningMarketPolicy,
    global_seen: set[str],
    attempts: int,
    cap: int,
) -> tuple[list[GatewayDiscoveryIssue], Any | None, GatewayMarketComparison, bool, bool]:
    issues: list[GatewayDiscoveryIssue] = []
    if not _IATA.fullmatch(iata):
        issues.append(
            _issue(
                pool,
                index,
                "invalid_iata_format",
                "candidate IATA must be exact uppercase three-letter code",
            )
        )
        return issues, None, _comparison_not_evaluated(model_market_id), False, False
    if iata in global_seen:
        issues.append(
            _issue(
                pool,
                index,
                "duplicate_candidate",
                "candidate airport code duplicates an earlier pool entry",
            )
        )
        return issues, None, _comparison_not_evaluated(model_market_id), False, False
    global_seen.add(iata)
    if attempts >= cap:
        issues.append(_issue(pool, index, "over_pool_cap", "candidate exceeds the shared pool cap"))
        return issues, None, _comparison_not_evaluated(model_market_id), False, True
    airport = repository.lookup_airport_iata(iata)
    if airport is None:
        issues.append(
            _issue(
                pool,
                index,
                "airport_absent_from_catalog",
                "candidate is not validated in this catalog snapshot",
            )
        )
        return issues, None, _comparison_not_evaluated(model_market_id), False, True
    metadata = repository.airport_selection_metadata(airport.airport_id)
    if metadata is None:
        issues.append(
            _issue(
                pool,
                index,
                "missing_retained_facility_metadata",
                "candidate lacks retained-facility metadata",
            )
        )
        return issues, None, _comparison_not_evaluated(model_market_id), False, True
    comparison, gap = _candidate_market_comparison(
        airport.airport_id, metadata.country_code, metadata.iso_region, model_market_id, policy
    )
    return issues, airport, comparison, gap, True


def _valid_ref_tuple(
    values: tuple[str, ...],
    permitted: dict[str, SelectedAirport],
    pool: str,
    index: int,
    name: str,
    issues: list[GatewayDiscoveryIssue],
) -> bool:
    if not values:
        issues.append(_issue(pool, index, "empty_relationship", f"{name} must be nonempty"))
        return False
    if len(values) != len(set(values)):
        issues.append(
            _issue(pool, index, "duplicate_relationship_reference", f"{name} repeats an endpoint")
        )
        return False
    unknown = [value for value in values if value not in permitted]
    if unknown:
        issues.append(
            _issue(
                pool, index, "invalid_relationship_reference", f"{name} names a non-input endpoint"
            )
        )
        return False
    return True


def _endpoint_assessment_decisions(
    proposal: GatewayCandidateProposal, gate: MarketGenerationGate
) -> tuple[GatewayEndpointAssessmentDecision, ...]:
    assignments = {
        (item.role, item.endpoint.airport_id, item.endpoint.airport_iata): item
        for item in gate.assignments
    }
    decisions: list[GatewayEndpointAssessmentDecision] = []
    for assessment in proposal.endpoint_market_assessments:
        assignment = assignments.get(
            (assessment.role, assessment.airport_id, assessment.airport_iata)
        )
        if assignment is None:
            comparison = GatewayMarketComparison(
                status=GatewayMarketComparisonStatus.ASSESSMENT_UNRECOGNIZED,
                policy_market_id=None,
                model_asserted_market_id=assessment.model_asserted_market_id,
                advisory=True,
                message="model endpoint market assessment does not name an input endpoint",
            )
        else:
            comparison = _market_comparison(
                assignment.market_id, assessment.model_asserted_market_id
            )
        decisions.append(
            GatewayEndpointAssessmentDecision(assessment=assessment, comparison=comparison)
        )
    return tuple(decisions)


def _candidate_market_comparison(
    airport_id: str,
    country_code: str,
    iso_region: str,
    model_market_id: str | None,
    policy: PlanningMarketPolicy,
) -> tuple[GatewayMarketComparison, bool]:
    override = next(
        (item for item in policy.airport_overrides if item.airport_id == airport_id), None
    )
    if override is not None:
        policy_market = override.market_id
    elif iso_region in policy.override_coverage_regions:
        policy_market = None
    else:
        policy_market = policy.country_assignments.get(country_code)
    return _market_comparison(policy_market, model_market_id), policy_market is None


def _market_comparison(
    policy_market_id: str | None, model_market_id: str | None
) -> GatewayMarketComparison:
    if policy_market_id is None:
        return GatewayMarketComparison(
            status=GatewayMarketComparisonStatus.POLICY_UNKNOWN,
            policy_market_id=None,
            model_asserted_market_id=model_market_id,
            advisory=False,
            message="deterministic planning-market policy has no assignment for this airport",
        )
    if model_market_id is None:
        return GatewayMarketComparison(
            status=GatewayMarketComparisonStatus.MODEL_UNSPECIFIED,
            policy_market_id=policy_market_id,
            model_asserted_market_id=None,
            advisory=False,
            message="model did not assert a planning market",
        )
    if model_market_id == policy_market_id:
        return GatewayMarketComparison(
            status=GatewayMarketComparisonStatus.MATCH,
            policy_market_id=policy_market_id,
            model_asserted_market_id=model_market_id,
            advisory=False,
            message="model market assertion matches deterministic planning-market policy",
        )
    return GatewayMarketComparison(
        status=GatewayMarketComparisonStatus.MISMATCH_ADVISORY,
        policy_market_id=policy_market_id,
        model_asserted_market_id=model_market_id,
        advisory=True,
        message="model market assertion disagrees with deterministic planning-market policy",
    )


def _comparison_not_evaluated(model_market_id: str | None) -> GatewayMarketComparison:
    return GatewayMarketComparison(
        status=GatewayMarketComparisonStatus.NOT_EVALUATED,
        policy_market_id=None,
        model_asserted_market_id=model_market_id,
        advisory=False,
        message="candidate lacks catalog identity needed for planning-market comparison",
    )


def _selected_airport(airport: Any) -> SelectedAirport:
    return SelectedAirport(
        airport_id=airport.airport_id,
        airport_iata=airport.iata,
        airport_evidence_source_ids=airport.source_ids,
    )


def _endpoint_map(endpoints: tuple[SelectedAirport, ...]) -> dict[str, SelectedAirport]:
    result: dict[str, SelectedAirport] = {}
    for endpoint in endpoints:
        if endpoint.airport_iata in result:
            raise ValueError("endpoint side has ambiguous duplicate IATA identity")
        result[endpoint.airport_iata] = endpoint
    return result


def _issue(
    pool: str,
    candidate_index: int | None,
    code: str,
    message: str,
    scope_index: int | None = None,
) -> GatewayDiscoveryIssue:
    return GatewayDiscoveryIssue(
        stage=GatewayDiscoveryIssueStage.VALIDATION,
        code=code,
        message=message,
        pool=pool,
        candidate_index=candidate_index,
        scope_index=scope_index,
    )


def _gate_issues(gate: MarketGenerationGate) -> list[GatewayDiscoveryIssue]:
    return [
        GatewayDiscoveryIssue(
            stage=GatewayDiscoveryIssueStage.GATE, code=item.code.value, message=item.message
        )
        for item in gate.issues
    ]


def _coverage_for(
    gate: MarketGenerationGate,
    _: tuple[object, ...],
    *,
    candidate_gap: bool = False,
) -> GatewayMarketCoverage:
    endpoint_gap = any(item.mapping_gap for item in gate.assignments)
    if endpoint_gap and candidate_gap:
        return GatewayMarketCoverage.ENDPOINT_AND_CANDIDATE_MAPPING_GAPS
    if endpoint_gap:
        return GatewayMarketCoverage.ENDPOINT_MAPPING_GAPS
    if candidate_gap:
        return GatewayMarketCoverage.CANDIDATE_MAPPING_GAPS
    return GatewayMarketCoverage.COMPLETE


def _result(
    *,
    discovery_input: GatewayDiscoveryInput,
    policy: PlanningMarketPolicy,
    gate: MarketGenerationGate,
    generator_configuration: GatewayDiscoveryGeneratorConfiguration | None,
    generator_invocation: GatewayGeneratorInvocation | None = None,
    generation_status: GatewayDiscoveryGenerationStatus,
    outcome: GatewayDiscoveryOutcome,
    market_coverage: GatewayMarketCoverage,
    proposal: GatewayCandidateProposal | None = None,
    endpoint_market_assessment_decisions: tuple[GatewayEndpointAssessmentDecision, ...] = (),
    candidate_decisions: tuple[GatewayCandidateDecision, ...] = (),
    accepted_origin_access_gateways: tuple[AcceptedOriginAccessGateway, ...] = (),
    accepted_destination_access_gateways: tuple[AcceptedDestinationAccessGateway, ...] = (),
    accepted_intermediate_hubs: tuple[AcceptedIntermediateHub, ...] = (),
    issues: tuple[GatewayDiscoveryIssue, ...] = (),
) -> GatewayDiscoveryResult:
    payload: dict[str, object] = {
        "input": discovery_input,
        "input_digest": gateway_discovery_input_digest(discovery_input),
        "catalog_receipt": gate.compatibility.runtime_catalog_receipt,
        "market_policy_version": policy.policy_version,
        "market_policy_digest": planning_market_policy_digest(policy),
        "market_gate": gate,
        "generator_configuration": generator_configuration,
        "generator_invocation": generator_invocation,
        "generation_status": generation_status,
        "outcome": outcome,
        "proposal": proposal,
        "endpoint_market_assessment_decisions": endpoint_market_assessment_decisions,
        "candidate_decisions": candidate_decisions,
        "accepted_origin_access_gateways": accepted_origin_access_gateways,
        "accepted_destination_access_gateways": accepted_destination_access_gateways,
        "accepted_intermediate_hubs": accepted_intermediate_hubs,
        "issues": issues,
        "market_coverage": market_coverage,
        "limitations": _LIMITATIONS,
    }
    result_digest = _canonical_digest({key: _dump(value) for key, value in payload.items()})
    return GatewayDiscoveryResult.model_validate({**payload, "result_digest": result_digest})


def _dump(value: object) -> object:
    if isinstance(value, PlanningContractModel):
        return value.model_dump(mode="json", round_trip=True)
    if isinstance(value, tuple):
        return [_dump(item) for item in value]
    return value


def _generator_invocation(
    generator: GatewayCandidateGenerator,
) -> GatewayGeneratorInvocation | None:
    """Drain optional telemetry independently, preserving no raw prompt/response material.

    Core handoff intentionally drains and redacts adapter traces. A live evaluator
    that needs raw private traces must tee/wrap the generator into its own private
    trace sink before this handoff drain; raw traces never belong in this record.
    """

    trace_status, traces, trace_issue = _safe_capture(generator, "take_call_traces")
    usage_status, usage, usage_issue = _safe_capture(generator, "take_usage")
    trace_count = 0
    trace_error_count = 0
    latency_total: float | None = None
    if trace_status is GatewayCaptureStatus.CAPTURED:
        if not isinstance(traces, list) or any(not isinstance(item, dict) for item in traces):
            trace_status = GatewayCaptureStatus.INVALID_RECEIPT
            trace_issue = "invalid_trace_receipt"
        else:
            trace_count = len(traces)
            trace_error_count = sum(1 for item in traces if item.get("error") is not None)
            latencies = [
                item.get("latency_seconds")
                for item in traces
                if isinstance(item.get("latency_seconds"), (int, float))
                and item.get("latency_seconds") >= 0
            ]
            latency_total = float(sum(latencies)) if latencies else None
    normalized_usage: dict[str, int] | None = None
    if usage_status is GatewayCaptureStatus.CAPTURED:
        if not isinstance(usage, dict) or any(
            not isinstance(key, str) or not isinstance(value, int) for key, value in usage.items()
        ):
            usage_status = GatewayCaptureStatus.INVALID_RECEIPT
            usage_issue = "invalid_usage_receipt"
        else:
            normalized_usage = dict(usage)
    if (
        trace_status is GatewayCaptureStatus.NOT_EXPOSED
        and usage_status is GatewayCaptureStatus.NOT_EXPOSED
    ):
        return None
    return GatewayGeneratorInvocation(
        usage=normalized_usage,
        usage_capture_status=usage_status,
        trace_capture_status=trace_status,
        trace_count=trace_count,
        trace_error_count=trace_error_count,
        trace_latency_seconds=latency_total,
        capture_issue_codes=tuple(item for item in (trace_issue, usage_issue) if item is not None),
    )


def _safe_capture(
    generator: GatewayCandidateGenerator, accessor_name: str
) -> tuple[GatewayCaptureStatus, object | None, str | None]:
    try:
        accessor = getattr(generator, accessor_name, None)
    except Exception:  # noqa: BLE001 - instrumented adapters may have failing properties.
        return GatewayCaptureStatus.ACCESSOR_FAILURE, None, f"{accessor_name}_attribute_failure"
    if not callable(accessor):
        return GatewayCaptureStatus.NOT_EXPOSED, None, None
    try:
        return GatewayCaptureStatus.CAPTURED, accessor(), None
    except Exception:  # noqa: BLE001 - telemetry must never change generator outcome.
        return GatewayCaptureStatus.ACCESSOR_FAILURE, None, f"{accessor_name}_failure"


def _canonical_digest(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
