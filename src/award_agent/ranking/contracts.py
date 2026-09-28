"""Replayable, evidence-preserving contracts for deterministic journey matching."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from award_agent.domain.clarification_session import EffectiveRequest
from award_agent.providers.contracts import ProviderResultSet, Sha256, content_digest
from award_agent.search_planning.compilation_contracts import CompiledSearchPlan
from award_agent.search_planning.contracts import PlanningContractModel
from award_agent.search_planning.planner import effective_request_digest


class MatchReason(PlanningContractModel):
    code: str = Field(min_length=1)
    dimension: Literal["scope", "route", "schedule", "requirement", "price", "booking", "evidence"]
    state: Literal["passed", "failed", "unknown"]
    detail: str = Field(min_length=1)


def classify_match(reasons: tuple[MatchReason, ...]) -> str:
    if any(reason.state == "failed" for reason in reasons):
        return "rejected"
    structural_unknowns = {
        "award_legs_missing", "award_leg_time_missing", "cash_leg_time_missing",
        "cash_internal_legs_unknown", "cash_endpoint_time_disagreement",
        "cash_provider_error", "award_provider_error", "transfer_timezone_unknown",
        "original_departure_date_unknown", "endpoint_time_missing",
        "transfer_time_unknown", "award_departure_disagreement",
        "award_arrival_disagreement",
    }
    if any(reason.code in structural_unknowns for reason in reasons):
        return "research_lead"
    if any(reason.state == "unknown" and reason.dimension in {"requirement", "evidence"}
           for reason in reasons):
        return "conditional"
    return "admitted"


class MatchedJourney(PlanningContractModel):
    candidate_id: Sha256
    option_family_id: Sha256
    topology: Literal["direct_award", "cash_access_award", "award_cash_egress"]
    status: Literal["admitted", "conditional", "rejected", "research_lead"]
    award_observation_id: str
    cash_observation_id: str | None = None
    award_query_id: str
    cash_query_id: str | None = None
    logical_award_query_ids: tuple[str, ...]
    strategy_id: str | None = None
    support_id: str | None = None
    positioning_dependency_id: str | None = None
    positioning_reason: str | None = None
    activation_observation_ids: tuple[str, ...] = ()
    original_origin: str
    original_destination: str
    departure_instant: datetime | None = None
    arrival_instant: datetime | None = None
    original_departure_date: date | None = None
    transfer_airport: str | None = None
    transfer_minutes: int | None = Field(default=None, ge=0)
    transfer_local_day_offset: int | None = None
    price_completeness: Literal["known", "partial", "unknown"] = "unknown"
    booking_obligation: Literal["single_award", "separate_tickets_unverified"]
    reasons: tuple[MatchReason, ...] = ()

    @model_validator(mode="after")
    def coherent_topology(self) -> MatchedJourney:
        if (self.topology == "direct_award") != (self.cash_observation_id is None):
            raise ValueError("direct topology must have no cash component")
        if self.topology != "direct_award" and (
            self.cash_query_id is None or self.support_id is None
            or self.positioning_dependency_id is None or self.strategy_id is None
        ):
            raise ValueError("mixed topology requires its exact planning and query links")
        identity = {
            "award": self.award_observation_id, "cash": self.cash_observation_id,
            "support": self.support_id, "dependency": self.positioning_dependency_id,
            "topology": self.topology, "origin": self.original_origin,
            "destination": self.original_destination,
        }
        if self.candidate_id != content_digest(identity):
            raise ValueError("candidate ID differs from matching identity")
        family_identity = {
            "award": self.award_observation_id, "support": self.support_id,
            "topology": self.topology, "origin": self.original_origin,
            "destination": self.original_destination,
        }
        if self.option_family_id != content_digest(family_identity):
            raise ValueError("option family ID differs from award/support identity")
        if self.status != classify_match(self.reasons):
            raise ValueError("candidate status differs from validation reasons")
        if any(instant is not None and instant.tzinfo is None for instant in (
            self.departure_instant, self.arrival_instant
        )):
            raise ValueError("candidate instants must be timezone-aware")
        return self


class MatchAccounting(PlanningContractModel):
    award_itineraries: int = Field(ge=0)
    cash_positioning_observations: int = Field(ge=0)
    direct_cash_observations: int = Field(ge=0)
    scoped_pairs: int = Field(ge=0)
    retained_direct: int = Field(ge=0)
    retained_mixed: int = Field(ge=0)
    admitted: int = Field(ge=0)
    conditional: int = Field(ge=0)
    rejected: int = Field(ge=0)
    research_leads: int = Field(ge=0)
    unpaired_positioning_observation_ids: tuple[str, ...] = ()


class PairingReceipt(PlanningContractModel):
    support_id: str
    positioning_dependency_id: str
    eligible_award_observation_ids: tuple[str, ...]
    cash_observation_ids: tuple[str, ...]
    enumerated_pairs: int = Field(ge=0)


class MatchedJourneySet(PlanningContractModel):
    contract_version: Literal["matched-journey-set-v1"] = "matched-journey-set-v1"
    matching_policy_version: Literal["m1-v1"] = "m1-v1"
    current_session_id: str
    current_revision: int = Field(ge=0)
    effective_request_digest: Sha256
    compilation_binding_digest: Sha256
    plan_digest: Sha256
    provider_run_id: str
    provider_policy_digest: Sha256
    provider_result_digest: Sha256
    max_combinations: int = Field(ge=1)
    request: EffectiveRequest
    plan: CompiledSearchPlan
    provider_result: ProviderResultSet
    journeys: tuple[MatchedJourney, ...]
    direct_cash_observation_ids: tuple[str, ...] = ()
    award_summary_observation_ids: tuple[str, ...] = ()
    unmatched_award_observation_ids: tuple[str, ...] = ()
    pairing_receipts: tuple[PairingReceipt, ...] = ()
    accounting: MatchAccounting

    @model_validator(mode="after")
    def check_accounting(self) -> MatchedJourneySet:
        binding = self.provider_result.execution_plan.binding
        if (self.current_session_id, self.current_revision) != (
            self.plan.identity.session_id, self.plan.identity.revision
        ) or (binding.session_id, binding.revision) != (
            self.current_session_id, self.current_revision
        ):
            raise ValueError("matched journey session authority differs from source binding")
        if self.effective_request_digest != effective_request_digest(self.request) or (
            self.effective_request_digest != self.plan.identity.effective_request_digest
            or self.effective_request_digest != binding.effective_request_digest
        ):
            raise ValueError("matched journey request digest differs from source binding")
        if self.compilation_binding_digest != self.plan.identity.compilation_binding_digest or (
            self.compilation_binding_digest != binding.compilation_binding_digest
        ) or self.plan_digest != self.plan.plan_digest or self.plan_digest != binding.plan_digest:
            raise ValueError("matched journey plan binding differs from source binding")
        if (self.provider_run_id, self.provider_policy_digest) != (
            binding.run_id, binding.policy_digest
        ) or self.provider_result_digest != content_digest(self.provider_result):
            raise ValueError("matched journey provider identity differs from source result")
        counts = {status: sum(j.status == status for j in self.journeys)
                  for status in ("admitted", "conditional", "rejected", "research_lead")}
        if any(getattr(self.accounting, "research_leads" if status == "research_lead" else status)
               != count for status, count in counts.items()):
            raise ValueError("journey status accounting differs from retained candidates")
        if self.accounting.retained_direct + self.accounting.retained_mixed != len(self.journeys):
            raise ValueError("journey topology accounting differs from retained candidates")
        if self.accounting.retained_mixed != self.accounting.scoped_pairs or (
            sum(receipt.enumerated_pairs for receipt in self.pairing_receipts)
            != self.accounting.scoped_pairs
        ):
            raise ValueError("pairing receipts must account for every scoped mixed pair")
        if self.accounting.scoped_pairs > self.max_combinations or (
            self.accounting.retained_direct != sum(j.topology == "direct_award" for j in self.journeys)
            or self.accounting.retained_mixed != sum(j.topology != "direct_award" for j in self.journeys)
        ):
            raise ValueError("candidate topology or fanout accounting differs")
        if len({j.candidate_id for j in self.journeys}) != len(self.journeys):
            raise ValueError("candidate IDs must be unique")
        observations = {o.observation_id: o for o in self.provider_result.observations}
        queries = {q.query_id: q for q in self.provider_result.execution_plan.queries}
        strategies = {s.strategy_id: s for s in self.plan.supplemental_strategies}
        supports = {s.support_id: s for s in self.plan.support_alternatives}
        dependencies = {d.dependency_id: d for d in self.plan.positioning_dependencies}
        uses = {u.query_use_id: u for u in self.plan.strategy_query_uses}
        awards = {o.observation_id for o in self.provider_result.observations
                  if o.kind == "award_itinerary"}
        cash_positioning = {o.observation_id for o in self.provider_result.observations
                            if o.kind == "cash_itinerary" and
                            queries[o.query_id].role in {"cash_access", "cash_egress"}}
        summaries = tuple(o.observation_id for o in self.provider_result.observations
                          if o.kind == "award_summary")
        if self.accounting.award_itineraries != len(awards) or (
            self.accounting.cash_positioning_observations != len(cash_positioning)
            or self.accounting.direct_cash_observations != len(self.direct_cash_observation_ids)
            or self.award_summary_observation_ids != summaries
        ):
            raise ValueError("source observation accounting differs from provider result")
        if any(j.award_observation_id not in observations or (
            j.cash_observation_id is not None and j.cash_observation_id not in observations
        ) or j.award_query_id != observations[j.award_observation_id].query_id or (
            j.cash_observation_id is not None and
            j.cash_query_id != observations[j.cash_observation_id].query_id
        ) for j in self.journeys):
            raise ValueError("matched journey references observations outside its result")
        if any(observations[j.award_observation_id].kind != "award_itinerary" or (
            j.cash_observation_id is not None and
            observations[j.cash_observation_id].kind != "cash_itinerary"
        ) for j in self.journeys):
            raise ValueError("matched journey observation kinds are invalid")
        if any(j.cash_query_id is not None and queries[j.cash_query_id].role
               not in {"cash_access", "cash_egress"} for j in self.journeys):
            raise ValueError("direct cash cannot be a matched journey component")
        for journey in self.journeys:
            if journey.cash_observation_id is None:
                if any(value is not None for value in (
                    journey.strategy_id, journey.support_id, journey.positioning_dependency_id,
                    journey.cash_query_id,
                )) or journey.logical_award_query_ids != (
                    observations[journey.award_observation_id].logical_query_ids
                ):
                    raise ValueError("direct award cannot claim positioning support")
                continue
            support = supports.get(journey.support_id)
            dependency = dependencies.get(journey.positioning_dependency_id)
            strategy = strategies.get(journey.strategy_id)
            cash_query = queries[journey.cash_query_id]
            award = observations[journey.award_observation_id]
            airport = {a.airport_id: a.airport_iata for a in self.plan.airport_directory}
            if support is None or dependency is None or strategy is None or (
                support.strategy_id != strategy.strategy_id
                or dependency.support_id != support.support_id
                or dependency.dependency_id not in support.positioning_dependency_ids
                or cash_query.role != ("cash_access" if dependency.side == "origin"
                                       else "cash_egress")
                or journey.topology != ("cash_access_award" if dependency.side == "origin"
                                        else "award_cash_egress")
                or dependency.dependency_id not in cash_query.positioning_dependency_ids
                or strategy.strategy_id not in cash_query.strategy_ids
                or journey.activation_observation_ids != cash_query.activation_observation_ids
                or journey.logical_award_query_ids != award.logical_query_ids
                or journey.positioning_reason != strategy.reason
                or (journey.original_origin, journey.original_destination) != (
                    airport[support.original_origin_airport_fact_id],
                    airport[support.original_destination_airport_fact_id],
                )
                or (observations[journey.cash_observation_id].origin,
                    observations[journey.cash_observation_id].destination) != (
                    airport[dependency.from_airport_fact_id],
                    airport[dependency.to_airport_fact_id],
                )
                or not any(uses[uid].role == "access_main" and (
                    uses[uid].query_id in award.logical_query_ids
                ) for uid in support.query_use_ids)
            ):
                raise ValueError("matched journey strategy/support/dependency refs differ from plan")
        if tuple(o.observation_id for o in self.provider_result.observations if
                 queries[o.query_id].role == "direct_cash") != self.direct_cash_observation_ids:
            raise ValueError("direct cash benchmark accounting differs from provider result")
        used_awards = {j.award_observation_id for j in self.journeys}
        used_cash = {j.cash_observation_id for j in self.journeys
                     if j.cash_observation_id is not None}
        if set(self.unmatched_award_observation_ids) != awards - used_awards or (
            set(self.accounting.unpaired_positioning_observation_ids)
            != cash_positioning - used_cash
        ) or len(self.unmatched_award_observation_ids) != len(awards - used_awards) or (
            len(self.accounting.unpaired_positioning_observation_ids)
            != len(cash_positioning - used_cash)
        ):
            raise ValueError("unmatched observation accounting differs from retained journeys")
        receipt_members: dict[tuple[str, str], tuple[set[str], set[str]]] = {}
        for receipt in self.pairing_receipts:
            key = (receipt.support_id, receipt.positioning_dependency_id)
            award_ids = set(receipt.eligible_award_observation_ids)
            cash_ids = set(receipt.cash_observation_ids)
            support = supports.get(receipt.support_id)
            dependency = dependencies.get(receipt.positioning_dependency_id)
            if support is None or dependency is None or (
                dependency.support_id != support.support_id
                or dependency.dependency_id not in support.positioning_dependency_ids
            ):
                raise ValueError("pairing receipt references unknown plan support")
            if key in receipt_members or len(award_ids) != len(receipt.eligible_award_observation_ids) or (
                len(cash_ids) != len(receipt.cash_observation_ids)
                or not award_ids <= awards or not cash_ids <= cash_positioning
                or receipt.enumerated_pairs != len(award_ids) * len(cash_ids)
            ):
                raise ValueError("pairing receipt identity or members are invalid")
            receipt_members[key] = (award_ids, cash_ids)
        actual_pairs: dict[tuple[str, str], set[tuple[str, str]]] = {}
        for journey in self.journeys:
            if journey.cash_observation_id is None:
                continue
            key = (journey.support_id, journey.positioning_dependency_id)
            if key not in receipt_members or (
                journey.award_observation_id not in receipt_members[key][0]
                or journey.cash_observation_id not in receipt_members[key][1]
            ):
                raise ValueError("mixed journey lies outside pairing receipt")
            actual_pairs.setdefault(key, set()).add((journey.award_observation_id,
                                                      journey.cash_observation_id))
        for key, (award_ids, cash_ids) in receipt_members.items():
            if len(actual_pairs.get(key, set())) != len(award_ids) * len(cash_ids):
                raise ValueError("pairing receipt does not cover each scoped pair")
        return self
