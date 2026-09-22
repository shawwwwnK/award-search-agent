"""Bounded model proposal and honest catalog validation for endpoint airports.

This module deliberately does not create city-serving relationships.  The
model proposes endpoints for an already resolved entity; deterministic code
records exactly which limited catalog facts supported accepting or rejecting
each proposal.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Literal

from openai import OpenAI
from pydantic import Field, model_validator

from award_agent.observability.llm_trace import LLMCallTraceCollector, response_schema_sha256
from award_agent.search_planning.airport_selection_policy import (
    AirportSelectionCapPolicy,
    AirportSelectionCategory,
    ApplicableAirportSelectionCap,
    ResolvedEntityContext,
    airport_selection_cap_policy_digest,
)
from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    EndpointRole,
    PlanningContractModel,
    SelectedAirport,
)
from award_agent.search_planning.distance_consistency import (
    CityAirportDistanceAssessment,
    CityAirportDistanceConsistency,
    CityAirportDistanceStatus,
    assess_city_airport_distance,
)
from award_agent.search_planning.knowledge import PlanningKnowledgeRepository

AIRPORT_SELECTOR_ADAPTER_VERSION = "openai_airport_selector_v1"
AIRPORT_SELECTOR_PROMPT_VERSION = "airport-selector-prompt-v1"
AIRPORT_SELECTOR_ORIGINAL_SIMPLE_PROMPT_VERSION = "airport-selector-original-simple-v1"

_IATA = re.compile(r"^[A-Z]{3}$")
_REFINED_INSTRUCTIONS = """Propose useful initial airport-search endpoints for the supplied established location.

Return at most the supplied cap of distinct individual commercial passenger-airport IATA codes.
Prioritize commonly useful initial endpoints within the supplied geographic scope. Return fewer
candidates rather than padding the list. Do not return metropolitan aggregate codes. Do not make
claims about current routes, schedules, or award availability. If you have insufficient knowledge
to make a useful proposal, return outcome=insufficient_knowledge with an empty code list.

For countries and broad regions, favor major useful gateways with meaningful geographic coverage
within the supplied scope. Do not require one airport per country and do not fill the cap."""

_ORIGINAL_SIMPLE_INSTRUCTIONS = """What are the common airports that serve the supplied location?
Give the IATA code of commercial airports. Give no more than 5 airports."""


class AirportSelectionProposalOutcome(str, Enum):
    PROPOSED = "proposed"
    INSUFFICIENT_KNOWLEDGE = "insufficient_knowledge"


class AirportSelectionProposal(PlanningContractModel):
    """The intentionally small structured model response."""

    outcome: AirportSelectionProposalOutcome
    airport_iata_codes: tuple[Annotated[str, Field(pattern=r"^[A-Z]{3}$")], ...] = Field(
        max_length=20
    )

    @model_validator(mode="after")
    def validate_outcome_shape(self) -> AirportSelectionProposal:
        if self.outcome is AirportSelectionProposalOutcome.INSUFFICIENT_KNOWLEDGE:
            if self.airport_iata_codes:
                raise ValueError("insufficient knowledge must not include airport codes")
        elif not self.airport_iata_codes:
            raise ValueError("proposed outcome requires at least one airport code")
        return self


AIRPORT_SELECTOR_RESPONSE_SCHEMA_SHA256 = response_schema_sha256(AirportSelectionProposal)


class AirportSelectorPrompt(PlanningContractModel):
    """One named instruction arm, held separate from model and wire schema."""

    version: str = Field(min_length=1)
    instructions: str = Field(min_length=1)


REFINED_AIRPORT_SELECTOR_PROMPT = AirportSelectorPrompt(
    version=AIRPORT_SELECTOR_PROMPT_VERSION, instructions=_REFINED_INSTRUCTIONS
)
ORIGINAL_SIMPLE_AIRPORT_SELECTOR_PROMPT = AirportSelectorPrompt(
    version=AIRPORT_SELECTOR_ORIGINAL_SIMPLE_PROMPT_VERSION,
    instructions=_ORIGINAL_SIMPLE_INSTRUCTIONS,
)


class AirportSelectorModelInput(PlanningContractModel):
    """The complete model-facing selector input, independent of request wording."""

    entity_id: str = Field(min_length=1)
    entity_label: str = Field(min_length=1)
    entity_kind: str = Field(min_length=1)
    category: AirportSelectionCategory
    category_basis: str = Field(min_length=1)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    applicable_cap: int = Field(ge=1, le=20)

    @classmethod
    def from_context(
        cls, context: ResolvedEntityContext, cap: ApplicableAirportSelectionCap
    ) -> AirportSelectorModelInput:
        return cls(
            entity_id=context.entity_id,
            entity_label=context.label,
            entity_kind=context.entity_kind.value,
            category=context.category,
            category_basis=context.category_basis.value,
            country_code=context.country_code,
            applicable_cap=cap.cap,
        )

    @model_validator(mode="after")
    def validate_category_against_entity_kind(self) -> AirportSelectorModelInput:
        expected = {
            "city": AirportSelectionCategory.CITY_METROPOLITAN,
            "country": AirportSelectionCategory.COUNTRY,
        }.get(self.entity_kind)
        if expected is not None and self.category is not expected:
            raise ValueError("selector model input category disagrees with entity kind")
        if self.entity_kind not in {"city", "country", "region"}:
            raise ValueError("selector model input entity kind must be geographic")
        return self


class OpenAIAirportSelectorError(RuntimeError):
    """Raised when no usable structured airport proposal is available."""


@dataclass(frozen=True, slots=True)
class OpenAIAirportSelectorConfig:
    model: str
    prompt: AirportSelectorPrompt = REFINED_AIRPORT_SELECTOR_PROMPT

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model must not be empty")


class OpenAIAirportSelector:
    """Responses-parse adapter with optional private evaluation capture."""

    def __init__(
        self,
        config: OpenAIAirportSelectorConfig,
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

    def propose(self, model_input: AirportSelectorModelInput) -> AirportSelectionProposal:
        payload = json.dumps(model_input.model_dump(mode="json"), separators=(",", ":"))
        started = time.perf_counter()
        self._usage_call_count += 1
        try:
            response = self._client.responses.parse(
                model=self.config.model,
                instructions=self.config.prompt.instructions,
                input=payload,
                text_format=AirportSelectionProposal,
                store=False,
            )
        except Exception as exc:
            self._llm_trace.record(
                stage="airport_endpoint_selector",
                model=self.config.model,
                instructions=self.config.prompt.instructions,
                payload=payload,
                text_format=AirportSelectionProposal,
                adapter_version=AIRPORT_SELECTOR_ADAPTER_VERSION,
                provider_stage="responses.parse",
                error=exc,
                latency_seconds=time.perf_counter() - started,
            )
            raise OpenAIAirportSelectorError("OpenAI airport selector failed") from exc
        self._llm_trace.record(
            stage="airport_endpoint_selector",
            model=self.config.model,
            instructions=self.config.prompt.instructions,
            payload=payload,
            text_format=AirportSelectionProposal,
            adapter_version=AIRPORT_SELECTOR_ADAPTER_VERSION,
            provider_stage="responses.parse",
            response=response,
            latency_seconds=time.perf_counter() - started,
        )
        self._capture_usage(response)
        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, AirportSelectionProposal):
            raise OpenAIAirportSelectorError(
                "OpenAI returned an unexpected airport-selection output type"
            )
        return parsed


class AirportIdentityStatus(str, Enum):
    NOT_EVALUATED = "not_evaluated"
    CATALOG_VERIFIED = "catalog_verified"
    ABSENT_FROM_SNAPSHOT = "absent_from_snapshot"
    INVALID_IATA_FORMAT = "invalid_iata_format"


class AirportFacilityStatus(str, Enum):
    CATALOG_ACCEPTED_UNDER_SNAPSHOT_FILTER = "catalog_accepted_under_snapshot_filter"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class GeographicMembershipStatus(str, Enum):
    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class CityServingStatus(str, Enum):
    """A model proposal label, never factual city-serving verification."""

    MODEL_PROPOSED = "model_proposed"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"
    NOT_EVALUATED = "not_evaluated"


class AirportCandidateDisposition(str, Enum):
    ACCEPTED_FOR_EXPLORATORY_SEARCH = "accepted_for_exploratory_search"
    REJECTED_DUPLICATE = "rejected_duplicate"
    REJECTED_OVER_CAP = "rejected_over_cap"
    REJECTED_INVALID_IDENTITY = "rejected_invalid_identity"
    REJECTED_MISSING_FACILITY_METADATA = "rejected_missing_facility_metadata"
    REJECTED_GEOGRAPHIC_CONTRADICTION = "rejected_geographic_contradiction"
    REJECTED_OUTSIDE_CITY_DISTANCE_POLICY = "rejected_outside_city_distance_policy"


class AirportCandidateValidation(PlanningContractModel):
    proposed_iata: str = Field(min_length=1, max_length=16)
    identity_status: AirportIdentityStatus
    facility_status: AirportFacilityStatus
    geographic_membership: GeographicMembershipStatus
    city_distance: CityAirportDistanceAssessment | None = None
    airport: SelectedAirport | None = None
    disposition: AirportCandidateDisposition
    city_serving_status: CityServingStatus
    priority_status: Literal["model_selected"] = "model_selected"

    @model_validator(mode="after")
    def validate_candidate_shape(self) -> AirportCandidateValidation:
        accepted = self.disposition is AirportCandidateDisposition.ACCEPTED_FOR_EXPLORATORY_SEARCH
        if accepted != (self.airport is not None):
            raise ValueError("accepted airport candidate and selected airport must agree")
        if (
            self.identity_status is AirportIdentityStatus.CATALOG_VERIFIED
            and self.airport is None
            and self.disposition
            not in {
                AirportCandidateDisposition.REJECTED_DUPLICATE,
                AirportCandidateDisposition.REJECTED_OVER_CAP,
                AirportCandidateDisposition.REJECTED_MISSING_FACILITY_METADATA,
                AirportCandidateDisposition.REJECTED_GEOGRAPHIC_CONTRADICTION,
                AirportCandidateDisposition.REJECTED_OUTSIDE_CITY_DISTANCE_POLICY,
            }
        ):
            raise ValueError("catalog-verified candidate requires a coherent rejection reason")
        if (
            self.identity_status is not AirportIdentityStatus.CATALOG_VERIFIED
            and self.airport is not None
        ):
            raise ValueError("unverified identity cannot name a selected airport")
        return self


class AirportSelectionRecord(PlanningContractModel):
    """Immutable model-generated selection plus deterministic validation receipts."""

    record_version: Literal["airport-selection-record-v1"] = "airport-selection-record-v1"
    role: EndpointRole
    resolved_entity: ResolvedEntityContext
    applicable_cap: ApplicableAirportSelectionCap
    cap_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    distance_policy: CityAirportDistanceConsistency
    proposal: AirportSelectionProposal
    candidate_validations: tuple[AirportCandidateValidation, ...]
    accepted_airports: tuple[SelectedAirport, ...] = ()
    model: str = Field(min_length=1)
    selector_adapter_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    response_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_snapshot_id: str = Field(min_length=1)
    catalog_receipt: CatalogKnowledgeReceipt

    @model_validator(mode="after")
    def validate_record(self) -> AirportSelectionRecord:
        if self.applicable_cap.category is not self.resolved_entity.category:
            raise ValueError("selection cap category must match resolved entity category")
        if self.applicable_cap.policy_version == "":
            raise ValueError("selection cap policy version must be nonempty")
        candidates = tuple(item.proposed_iata for item in self.candidate_validations)
        if candidates != self.proposal.airport_iata_codes:
            raise ValueError("candidate validation order must exactly match model proposal")
        accepted = tuple(
            item.airport
            for item in self.candidate_validations
            if item.disposition is AirportCandidateDisposition.ACCEPTED_FOR_EXPLORATORY_SEARCH
        )
        if accepted != self.accepted_airports:
            raise ValueError("accepted airports must be exactly the accepted candidate subset")
        if len(accepted) > self.applicable_cap.cap:
            raise ValueError("accepted airports cannot exceed the applicable cap")
        for candidate in self.candidate_validations:
            if candidate.city_serving_status is not _city_serving_status(
                self.resolved_entity, candidate.identity_status
            ):
                raise ValueError("candidate city-serving status must match its validation context")
        if self.catalog_receipt.release_id != self.catalog_snapshot_id:
            raise ValueError("selection record snapshot must match its catalog receipt")
        return self


def airport_selection_record_digest(record: AirportSelectionRecord) -> str:
    rendered = json.dumps(
        record.model_dump(mode="json", round_trip=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def airport_selection_distance_policy_digest(policy: CityAirportDistanceConsistency) -> str:
    rendered = json.dumps(
        policy.model_dump(mode="json", round_trip=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def validate_airport_selection_proposal(
    *,
    role: EndpointRole,
    context: ResolvedEntityContext,
    cap_policy: AirportSelectionCapPolicy,
    distance_policy: CityAirportDistanceConsistency,
    proposal: AirportSelectionProposal,
    model: str,
    prompt_version: str = AIRPORT_SELECTOR_PROMPT_VERSION,
    repository: PlanningKnowledgeRepository,
) -> AirportSelectionRecord:
    """Validate a finite proposal; never retry or fill candidates to the cap."""

    cap = cap_policy.applicable_cap_for(context)
    candidates: list[AirportCandidateValidation] = []
    accepted: list[SelectedAirport] = []
    seen: set[str] = set()
    distinct_count = 0
    for raw_iata in proposal.airport_iata_codes:
        # Do not normalize model output into validity. Structured output should
        # already be machine-safe; direct callers get the same strict rule.
        iata = raw_iata
        if not _IATA.fullmatch(iata):
            candidates.append(
                _candidate(
                    context,
                    raw_iata,
                    AirportIdentityStatus.INVALID_IATA_FORMAT,
                    AirportFacilityStatus.NOT_APPLICABLE,
                    GeographicMembershipStatus.NOT_APPLICABLE,
                    AirportCandidateDisposition.REJECTED_INVALID_IDENTITY,
                )
            )
            continue
        if iata in seen:
            candidates.append(
                _candidate(
                    context,
                    iata,
                    AirportIdentityStatus.NOT_EVALUATED,
                    AirportFacilityStatus.NOT_APPLICABLE,
                    GeographicMembershipStatus.NOT_APPLICABLE,
                    AirportCandidateDisposition.REJECTED_DUPLICATE,
                )
            )
            continue
        seen.add(iata)
        distinct_count += 1
        if distinct_count > cap.cap:
            candidates.append(
                _candidate(
                    context,
                    iata,
                    AirportIdentityStatus.NOT_EVALUATED,
                    AirportFacilityStatus.NOT_APPLICABLE,
                    GeographicMembershipStatus.NOT_APPLICABLE,
                    AirportCandidateDisposition.REJECTED_OVER_CAP,
                )
            )
            continue
        airport = repository.lookup_airport_iata(iata)
        if airport is None:
            candidates.append(
                _candidate(
                    context,
                    iata,
                    AirportIdentityStatus.ABSENT_FROM_SNAPSHOT,
                    AirportFacilityStatus.NOT_APPLICABLE,
                    GeographicMembershipStatus.NOT_APPLICABLE,
                    AirportCandidateDisposition.REJECTED_INVALID_IDENTITY,
                )
            )
            continue
        metadata = repository.airport_selection_metadata(airport.airport_id)
        if metadata is None:
            candidates.append(
                _candidate(
                    context,
                    iata,
                    AirportIdentityStatus.CATALOG_VERIFIED,
                    AirportFacilityStatus.UNAVAILABLE,
                    GeographicMembershipStatus.UNAVAILABLE,
                    AirportCandidateDisposition.REJECTED_MISSING_FACILITY_METADATA,
                )
            )
            continue
        membership = _membership(context, metadata.country_code)
        if membership is GeographicMembershipStatus.CONTRADICTED:
            candidates.append(
                _candidate(
                    context,
                    iata,
                    AirportIdentityStatus.CATALOG_VERIFIED,
                    AirportFacilityStatus.CATALOG_ACCEPTED_UNDER_SNAPSHOT_FILTER,
                    membership,
                    AirportCandidateDisposition.REJECTED_GEOGRAPHIC_CONTRADICTION,
                )
            )
            continue
        distance = assess_city_airport_distance(context, metadata, distance_policy)
        if distance.status is CityAirportDistanceStatus.OUTSIDE_POLICY_DISTANCE:
            candidates.append(
                _candidate(
                    context,
                    iata,
                    AirportIdentityStatus.CATALOG_VERIFIED,
                    AirportFacilityStatus.CATALOG_ACCEPTED_UNDER_SNAPSHOT_FILTER,
                    membership,
                    AirportCandidateDisposition.REJECTED_OUTSIDE_CITY_DISTANCE_POLICY,
                    distance=distance,
                )
            )
            continue
        selected = SelectedAirport(
            airport_id=airport.airport_id,
            airport_iata=airport.iata,
            airport_evidence_source_ids=airport.source_ids,
        )
        accepted.append(selected)
        candidates.append(
            _candidate(
                context,
                iata,
                AirportIdentityStatus.CATALOG_VERIFIED,
                AirportFacilityStatus.CATALOG_ACCEPTED_UNDER_SNAPSHOT_FILTER,
                membership,
                AirportCandidateDisposition.ACCEPTED_FOR_EXPLORATORY_SEARCH,
                airport=selected,
                distance=distance,
            )
        )
    return AirportSelectionRecord(
        role=role,
        resolved_entity=context,
        applicable_cap=cap,
        cap_policy_digest=airport_selection_cap_policy_digest(cap_policy),
        distance_policy=distance_policy,
        proposal=proposal,
        candidate_validations=tuple(candidates),
        accepted_airports=tuple(accepted),
        model=model,
        selector_adapter_version=AIRPORT_SELECTOR_ADAPTER_VERSION,
        prompt_version=prompt_version,
        response_schema_sha256=AIRPORT_SELECTOR_RESPONSE_SCHEMA_SHA256,
        catalog_snapshot_id=repository.snapshot_id,
        catalog_receipt=repository.knowledge_receipt,
    )


def _membership(
    context: ResolvedEntityContext, airport_country_code: str
) -> GeographicMembershipStatus:
    if context.category is AirportSelectionCategory.COUNTRY:
        if context.country_code is None:
            return GeographicMembershipStatus.UNAVAILABLE
        return (
            GeographicMembershipStatus.VERIFIED
            if context.country_code == airport_country_code
            else GeographicMembershipStatus.CONTRADICTED
        )
    if context.category in {
        AirportSelectionCategory.SUB_COUNTRY_REGION,
        AirportSelectionCategory.INTERNATIONAL_REGION,
        AirportSelectionCategory.REGION_UNSPECIFIED,
    }:
        return GeographicMembershipStatus.UNAVAILABLE
    return GeographicMembershipStatus.NOT_APPLICABLE


def _candidate(
    context: ResolvedEntityContext,
    iata: str,
    identity: AirportIdentityStatus,
    facility: AirportFacilityStatus,
    membership: GeographicMembershipStatus,
    disposition: AirportCandidateDisposition,
    *,
    airport: SelectedAirport | None = None,
    distance: CityAirportDistanceAssessment | None = None,
) -> AirportCandidateValidation:
    return AirportCandidateValidation(
        proposed_iata=iata,
        identity_status=identity,
        facility_status=facility,
        geographic_membership=membership,
        city_distance=distance,
        airport=airport,
        disposition=disposition,
        city_serving_status=_city_serving_status(context, identity),
    )


def _city_serving_status(
    context: ResolvedEntityContext, identity: AirportIdentityStatus
) -> CityServingStatus:
    if context.category is not AirportSelectionCategory.CITY_METROPOLITAN:
        return CityServingStatus.NOT_APPLICABLE
    if identity is AirportIdentityStatus.CATALOG_VERIFIED:
        return CityServingStatus.MODEL_PROPOSED
    if identity is AirportIdentityStatus.NOT_EVALUATED:
        return CityServingStatus.NOT_EVALUATED
    return CityServingStatus.UNAVAILABLE
