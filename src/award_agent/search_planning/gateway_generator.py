"""One grouped, structured model proposal for optional gateway-search hypotheses.

This module is intentionally only the model-facing seam.  It neither decides
whether a call is appropriate nor treats an airport code, relationship, or
market assertion as a catalog or connectivity fact.  The later domain
validator owns those decisions and may retain valid siblings from this raw
proposal.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, cast

from openai import OpenAI
from pydantic import Field, model_validator

from award_agent.observability.llm_trace import LLMCallTraceCollector, response_schema_sha256
from award_agent.search_planning.contracts import PlanningContractModel
from award_agent.search_planning.market_policy import (
    AirportMarketAssignment,
    MarketGenerationGate,
    MarketGenerationGateStatus,
    PlanningMarket,
)

GATEWAY_GENERATOR_ADAPTER_VERSION = "openai_gateway_generator_v1"
GATEWAY_GENERATOR_PROMPT_VERSION = "gateway-generator-prompt-v6"

# These intentionally exceed the v1 product caps.  The validator, rather
# than schema parsing, records a bad or over-cap entry without losing useful
# siblings in the same grouped response.
_STRUCTURAL_POOL_MAX = 20
_STRUCTURAL_SCOPE_MAX = 40
_STRUCTURAL_REFERENCE_MAX = 40

_INSTRUCTIONS = """Suggest optional airport-search opportunities for a supplied award-trip request.

Return one grouped result with origin_access_gateways, destination_access_gateways, and
intermediate_hubs.  Every airport code must identify one individual airport; do not use a
metropolitan aggregate code.  The original endpoints are already selected and must not be removed.

Origin-access gateways are alternative places from which a regional origin, or one with limited
international usefulness toward the opposite market, can usefully begin a search.  They may also
be materially complementary alternative departure search endpoints for an already-strong origin
when they offer specific incremental search value relative to the opposite market.  A major or
already-useful endpoint raises the threshold for such an alternative but does not disqualify it.
Destination-access gateways may likewise be materially complementary alternative arrival search
endpoints for a regional, limited-use, or already-strong destination.  Gateway usefulness is
relative to the opposite market, not airport size alone.  Size, proximity, sharing a market, or
geographic diversity alone is not incremental search value.  Assess this suitability for each
supported original endpoint: do not apply a gateway to an already-useful endpoint merely because
it helps a sibling.  Do not propose an access gateway if it equals any applicable opposite-side
endpoint, because that would create a self-pair.  Positioning is allowed.

Intermediate hubs are optional search hypotheses with explicit origin-side and destination-side
scopes.  A scope means all pairings between its listed sides.  References may name an original
endpoint or a gateway in the appropriate pool; do not invent additional gateway layers.  Use narrow
scopes when a broad scope would imply pairings you cannot support.  An intermediate hub may be in
the origin market, destination market, or a third market.  Major original endpoints do not
disqualify other hubs in those markets.  A candidate sharing an endpoint's market remains eligible
when this supplied request has cross-market portions.  Put a hub relationship directly supporting
original endpoints in a separate scope from a relationship that depends on an access gateway, so a
rejected gateway does not erase an independent original relationship.  Do not make an otherwise
independent original relationship depend solely on a gateway.

Before returning, reconcile each candidate's uncertainty with every stated applicability or scope.
If a pairing is described as marginal, overlapping, materially circuitous, or unlikely to justify
positioning, omit that pairing unless the candidate reason names concrete countervailing value
specific to that pairing.  Do not default a candidate to every endpoint solely because endpoints
share a market.

Return fewer candidates rather than padding.  Access gateways and intermediate hubs serve distinct
purposes: do not omit a useful access alternative to make room for hubs, and do not pad either
pool.  Propose at most two origin-access gateways, two destination-access gateways, and five
intermediate hubs regardless of whether either access pool is populated.  Candidates are
alternatives, not itinerary legs.  Prefer complementary strong candidates without geographic quotas
or a promise of better award availability.  The
supplied origin or destination side can span multiple markets; use the actual labels and scope
proposals to cross-market portions without discarding original endpoints.  Evaluate circuitousness
before marginal distinctness.  A different market, role, geography, or search topology alone never
justifies substantial backtracking or positioning away from the opposite endpoint.  If a candidate's
only incremental rationale is distinctness and its positioning may be materially circuitous, omit it
and allow an empty result.  Airport size or correct market alone is insufficient.

Make a marginal selection, not an inventory.  Five hubs is a safety ceiling, not a completion
target.  After selecting access gateways, add a hub only when its search function is materially
distinct from every selected access gateway and every earlier hub.  Omit a candidate whose only
distinction is another airport, geography, size, or a generic claim of a different search pool.
Prefer the smallest complementary subset even if more valid airports exist.
When two candidates have the same applicability or scope and differ only by airport, geography, or
a generic different-search-pool rationale, retain only the stronger one.

Give each candidate one concise reason and any material uncertainty.  Its reason must explain its
specific incremental value relative to the original endpoints and candidates already selected, not
only the original endpoints.  endpoint_market_assessments may name only the supplied original
endpoints.  For each candidate, put any unverified market assessment only in that candidate's
model_asserted_market_id; use an approved supplied market ID or null.  Do not claim routes,
schedules, connections, protected tickets, award seats, availability, or bookability.  State
reasons and uncertainty as hypotheses; do not assert a current facility role, route or service,
connection or connection quality, schedule, award, or feasibility as fact.  Use general knowledge
without browsing, and only the supplied resolved airport, market, and date context; do not
reinterpret user wording."""


class GatewayGeneratorPrompt(PlanningContractModel):
    version: str = Field(min_length=1)
    instructions: str = Field(min_length=1)


DEFAULT_GATEWAY_GENERATOR_PROMPT = GatewayGeneratorPrompt(
    version=GATEWAY_GENERATOR_PROMPT_VERSION,
    instructions=_INSTRUCTIONS,
)


class GatewayApprovedMarket(PlanningContractModel):
    """An approved policy label supplied for model readability, not a model authority."""

    market_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    definition: str = Field(min_length=1, max_length=1000)

    @classmethod
    def from_market(cls, market: PlanningMarket) -> GatewayApprovedMarket:
        return cls(market_id=market.market_id, name=market.name, definition=market.definition)


class GatewayEndpointModelContext(PlanningContractModel):
    role: Literal["origin", "destination"]
    airport_id: str = Field(min_length=1, max_length=200)
    airport_iata: str = Field(min_length=1, max_length=16)
    catalog_country_code: str = Field(min_length=1, max_length=16)
    catalog_iso_region: str = Field(min_length=1, max_length=80)
    policy_market_id: str | None = Field(default=None, min_length=1, max_length=80)
    policy_market_name: str | None = Field(default=None, min_length=1, max_length=160)
    policy_market_known: bool
    policy_assignment_source: str = Field(min_length=1, max_length=80)

    @classmethod
    def from_assignment(
        cls,
        assignment: AirportMarketAssignment,
        market_names: dict[str, str],
    ) -> GatewayEndpointModelContext:
        if assignment.role not in {"origin", "destination"}:
            raise ValueError("market assignment role is not a supported endpoint role")
        market_id = assignment.market_id
        return cls(
            role=cast(Literal["origin", "destination"], assignment.role),
            airport_id=assignment.endpoint.airport_id,
            airport_iata=assignment.endpoint.airport_iata,
            catalog_country_code=assignment.catalog_country_code,
            catalog_iso_region=assignment.catalog_iso_region,
            policy_market_id=market_id,
            policy_market_name=None if market_id is None else market_names.get(market_id),
            policy_market_known=not assignment.mapping_gap,
            policy_assignment_source=assignment.source.value,
        )


class GatewayOutboundDateContext(PlanningContractModel):
    """Resolved date window only; never raw request language."""

    start: date
    end: date
    timezone: str = Field(min_length=1, max_length=100)
    effective_window_precision: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_date_order(self) -> GatewayOutboundDateContext:
        if self.end < self.start:
            raise ValueError("outbound date context end precedes start")
        return self


class GatewayGeneratorModelInput(PlanningContractModel):
    """Complete model-facing input with policy-known and policy-unknown labels."""

    origin_endpoints: tuple[GatewayEndpointModelContext, ...] = Field(min_length=1)
    destination_endpoints: tuple[GatewayEndpointModelContext, ...] = Field(min_length=1)
    approved_markets: tuple[GatewayApprovedMarket, ...] = Field(min_length=1)
    outbound_date: GatewayOutboundDateContext
    _copy_on_read_fields = frozenset(
        {"origin_endpoints", "destination_endpoints", "approved_markets", "outbound_date"}
    )

    @model_validator(mode="after")
    def validate_market_context(self) -> GatewayGeneratorModelInput:
        market_by_id = {item.market_id: item for item in self.approved_markets}
        if len(market_by_id) != len(self.approved_markets):
            raise ValueError("approved market IDs must be unique")
        for expected_role, endpoints in (
            ("origin", self.origin_endpoints),
            ("destination", self.destination_endpoints),
        ):
            for endpoint in endpoints:
                if endpoint.role != expected_role:
                    raise ValueError("endpoint role does not match its input side")
                known = endpoint.policy_market_known
                if known != (endpoint.policy_market_id is not None):
                    raise ValueError("policy market-known flag must agree with its market ID")
                if not known and endpoint.policy_market_name is not None:
                    raise ValueError("unknown policy market must not include a market name")
                if known:
                    assert endpoint.policy_market_id is not None
                    approved = market_by_id.get(endpoint.policy_market_id)
                    if approved is None:
                        raise ValueError("known endpoint policy market is not approved")
                    if endpoint.policy_market_name != approved.name:
                        raise ValueError("known endpoint policy market name disagrees with approved policy")
        return self

    @classmethod
    def from_market_gate(
        cls,
        gate: MarketGenerationGate,
        markets: tuple[PlanningMarket, ...],
        outbound_date: GatewayOutboundDateContext,
    ) -> GatewayGeneratorModelInput:
        if gate.status is not MarketGenerationGateStatus.GENERATION_REQUIRED:
            raise ValueError("gateway generator input requires a generation-required market gate")
        market_names = {market.market_id: market.name for market in markets}
        assignments_by_role = {
            "origin": tuple(item for item in gate.assignments if item.role == "origin"),
            "destination": tuple(item for item in gate.assignments if item.role == "destination"),
        }

        def contexts_for(
            role: Literal["origin", "destination"],
            endpoints: tuple[object, ...],
        ) -> tuple[GatewayEndpointModelContext, ...]:
            assignments = assignments_by_role[role]
            if len(assignments) != len(endpoints):
                raise ValueError("market gate does not provide one valid assignment per endpoint")
            contexts: list[GatewayEndpointModelContext] = []
            for endpoint, assignment in zip(endpoints, assignments, strict=True):
                if assignment.role != role or assignment.endpoint != endpoint:
                    raise ValueError("market gate assignment does not bind the ordered endpoint input")
                contexts.append(GatewayEndpointModelContext.from_assignment(assignment, market_names))
            return tuple(contexts)

        origins = contexts_for("origin", gate.origin_endpoints)
        destinations = contexts_for("destination", gate.destination_endpoints)
        return cls(
            origin_endpoints=origins,
            destination_endpoints=destinations,
            approved_markets=tuple(GatewayApprovedMarket.from_market(item) for item in markets),
            outbound_date=outbound_date,
        )


class GatewayEndpointMarketAssessment(PlanningContractModel):
    """Model market claim for one supplied endpoint, retained as provenance only."""

    role: Literal["origin", "destination"]
    airport_id: str = Field(max_length=200)
    airport_iata: str = Field(max_length=16)
    model_asserted_market_id: str | None = Field(default=None, max_length=80)


class GatewayCandidateBase(PlanningContractModel):
    airport_iata: str = Field(max_length=16)
    reason: str = Field(max_length=1200)
    material_uncertainty: str | None = Field(default=None, max_length=800)
    # It is provenance, not a required or authoritative classification.  The
    # validator compares this later and records an advisory disagreement.
    model_asserted_market_id: str | None = Field(default=None, max_length=80)


class OriginAccessGatewayProposal(GatewayCandidateBase):
    supported_original_origin_iata_codes: tuple[str, ...] = Field(max_length=_STRUCTURAL_REFERENCE_MAX)
    applicable_original_destination_iata_codes: tuple[str, ...] = Field(
        max_length=_STRUCTURAL_REFERENCE_MAX
    )


class DestinationAccessGatewayProposal(GatewayCandidateBase):
    supported_original_destination_iata_codes: tuple[str, ...] = Field(
        max_length=_STRUCTURAL_REFERENCE_MAX
    )
    applicable_original_origin_iata_codes: tuple[str, ...] = Field(max_length=_STRUCTURAL_REFERENCE_MAX)


class GatewayScopeOriginReference(PlanningContractModel):
    kind: Literal["original_origin", "origin_access_gateway"]
    airport_iata: str = Field(max_length=16)


class GatewayScopeDestinationReference(PlanningContractModel):
    kind: Literal["original_destination", "destination_access_gateway"]
    airport_iata: str = Field(max_length=16)


class IntermediateHubScopeProposal(PlanningContractModel):
    origin_side: tuple[GatewayScopeOriginReference, ...] = Field(max_length=_STRUCTURAL_REFERENCE_MAX)
    destination_side: tuple[GatewayScopeDestinationReference, ...] = Field(
        max_length=_STRUCTURAL_REFERENCE_MAX
    )
    reason: str | None = Field(default=None, max_length=800)


class IntermediateHubProposal(GatewayCandidateBase):
    scopes: tuple[IntermediateHubScopeProposal, ...] = Field(max_length=_STRUCTURAL_SCOPE_MAX)


class GatewayCandidateProposal(PlanningContractModel):
    """Wire structure only.  Empty pools are intentionally a valid response."""

    endpoint_market_assessments: tuple[GatewayEndpointMarketAssessment, ...] = Field(
        max_length=_STRUCTURAL_REFERENCE_MAX
    )
    origin_access_gateways: tuple[OriginAccessGatewayProposal, ...] = Field(
        max_length=_STRUCTURAL_POOL_MAX
    )
    destination_access_gateways: tuple[DestinationAccessGatewayProposal, ...] = Field(
        max_length=_STRUCTURAL_POOL_MAX
    )
    intermediate_hubs: tuple[IntermediateHubProposal, ...] = Field(max_length=_STRUCTURAL_POOL_MAX)
    _copy_on_read_fields = frozenset(
        {
            "endpoint_market_assessments",
            "origin_access_gateways",
            "destination_access_gateways",
            "intermediate_hubs",
        }
    )


GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256 = response_schema_sha256(GatewayCandidateProposal)


class OpenAIGatewayGeneratorError(RuntimeError):
    """Raised when the one grouped structured proposal cannot be obtained."""


@dataclass(frozen=True, slots=True)
class OpenAIGatewayGeneratorConfig:
    model: str
    prompt: GatewayGeneratorPrompt = DEFAULT_GATEWAY_GENERATOR_PROMPT

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model must not be empty")


class OpenAIGatewayGenerator:
    """One-call Responses structured-output adapter with opt-in private capture."""

    def __init__(
        self,
        config: OpenAIGatewayGeneratorConfig,
        client: OpenAI | None = None,
        *,
        capture_llm_io: bool = False,
    ) -> None:
        self.config = config
        self._client = client or OpenAI()
        self._usage_call_count = 0
        self._usage_records: list[dict[str, int]] = []
        self._llm_trace = LLMCallTraceCollector(enabled=capture_llm_io)

    def reset_capture(self) -> None:
        self._usage_call_count = 0
        self._usage_records = []
        self._llm_trace.reset()

    def take_call_traces(self) -> list[dict[str, Any]]:
        return self._llm_trace.take()

    def take_usage(self) -> dict[str, int] | None:
        calls, records = self._usage_call_count, self._usage_records
        self._usage_call_count, self._usage_records = 0, []
        if not records and calls == 0:
            return None
        return {
            "calls": calls,
            "captured_calls": len(records),
            "missing_calls": calls - len(records),
            "input_tokens": sum(item["input_tokens"] for item in records),
            "output_tokens": sum(item["output_tokens"] for item in records),
            "total_tokens": sum(item["total_tokens"] for item in records),
        }

    def _capture_usage(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        payload = usage if isinstance(usage, dict) else usage.model_dump(mode="json")
        input_tokens, output_tokens = payload.get("input_tokens"), payload.get("output_tokens")
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
            return
        total_tokens = payload.get("total_tokens")
        self._usage_records.append(
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens
                if isinstance(total_tokens, int)
                else input_tokens + output_tokens,
            }
        )

    def propose(self, model_input: GatewayGeneratorModelInput) -> GatewayCandidateProposal:
        payload = json.dumps(model_input.model_dump(mode="json"), separators=(",", ":"))
        started = time.perf_counter()
        self._usage_call_count += 1
        try:
            response = self._client.responses.parse(
                model=self.config.model,
                instructions=self.config.prompt.instructions,
                input=payload,
                text_format=GatewayCandidateProposal,
                store=False,
            )
        except Exception as exc:
            self._llm_trace.record(
                stage="gateway_candidate_generator",
                model=self.config.model,
                instructions=self.config.prompt.instructions,
                payload=payload,
                text_format=GatewayCandidateProposal,
                adapter_version=GATEWAY_GENERATOR_ADAPTER_VERSION,
                provider_stage="responses.parse",
                error=exc,
                latency_seconds=time.perf_counter() - started,
            )
            raise OpenAIGatewayGeneratorError("OpenAI gateway generator failed") from exc
        self._llm_trace.record(
            stage="gateway_candidate_generator",
            model=self.config.model,
            instructions=self.config.prompt.instructions,
            payload=payload,
            text_format=GatewayCandidateProposal,
            adapter_version=GATEWAY_GENERATOR_ADAPTER_VERSION,
            provider_stage="responses.parse",
            response=response,
            latency_seconds=time.perf_counter() - started,
        )
        self._capture_usage(response)
        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, GatewayCandidateProposal):
            raise OpenAIGatewayGeneratorError(
                "OpenAI returned an unexpected gateway-candidate output type"
            )
        return parsed
