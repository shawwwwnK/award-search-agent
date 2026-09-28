"""Offline execution checks over a saved current trace-derived plan."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from award_agent.domain import EffectiveRequest
from award_agent.providers.contracts import (
    CapturedResponse,
    EvidenceRef,
    ExecutionPolicy,
    ObservedLeg,
    ParsedProviderPage,
    ProviderCapability,
    ProviderObservation,
    ProviderQuery,
    RawField,
    ResourceBudget,
    ResourceUsage,
)
from award_agent.providers.execution import (
    _execute_query,
    _positioning_queries,
    _supplemental_order,
    build_execution_plan,
    execute_provider_plan,
    validate_result_attachment,
)
from award_agent.search_planning.compilation_contracts import CompiledSearchPlan


@lru_cache(maxsize=1)
def _inputs() -> tuple[CompiledSearchPlan, dict[str, Any]]:
    bundle_path = Path("evidence/provider-stage/saved-searches/trace-inputs/ready_exact_airports.json")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    plan = CompiledSearchPlan.model_validate(bundle["plan"])
    request = EffectiveRequest.model_validate(bundle["current_effective_request"])
    budget = ResourceBudget(requests=1, attempts=2, pages=2, detail_calls=0,
                            rows=30, bytes=100000, elapsed_seconds=30)
    execution_policy = ExecutionPolicy(
        version="test", award_budget=budget, cash_budget=budget,
        budget_evidence=("offline-test",), direct_cash_samples=1,
        positioning_cash_samples=0, page_size=10, request_timeout_seconds=10)
    seats = ProviderCapability(provider="seats_aero", version="test", backend="test",
                               operation="search", reviewed=True, evidence_digests=("a" * 64,))
    cash = ProviderCapability(provider="gfly", version="test", backend="test",
                              operation="search", reviewed=True, evidence_digests=("b" * 64,))
    args = {
        "run_id": "test-run", "current_session_id": bundle["current_session_id"],
        "current_revision": bundle["current_revision"],
        "current_effective_request": request,
        "expected_compilation_binding_digest": bundle["expected_compilation_binding_digest"],
        "policy": execution_policy, "award_capability": seats, "cash_capability": cash,
    }
    return plan, args


class EmptyAdapter:
    def __init__(self, *, paginated: bool = False) -> None:
        self.queries: list[tuple[str, str | None]] = []
        self.paginated = paginated

    def fetch(self, query: ProviderQuery, *, cursor: str | None,
              timeout_seconds: float, max_bytes: int) -> CapturedResponse:
        self.queries.append((query.query_id, cursor))
        ref = EvidenceRef(sha256="c" * 64, relative_path="test.json",
                          retrieved_at=datetime(2026, 9, 22, tzinfo=UTC),
                          synthetic=True)
        return CapturedResponse(query_id=query.query_id, provider=query.provider,
                                status="completed", evidence=ref, body={},
                                elapsed_seconds=0.1, byte_count=2, cursor=cursor)

    def parse(self, query: ProviderQuery, capture: CapturedResponse, *,
              airport_timezones: Mapping[str, str]) -> ParsedProviderPage:
        more = self.paginated and capture.cursor is None
        return ParsedProviderPage(query_id=query.query_id, status="empty", more=more,
                                  next_cursor="page-2" if more else None,
                                  pair_coverage_exhaustive=not more)


@pytest.mark.parametrize("name", [
    "ready_exact_airports", "ready_whole_month", "mixed_award_cash_eligible",
    "united_states_to_japan", "united_states_to_india",
])
def test_frozen_plan_projects_award_and_corresponding_cash_work(name: str) -> None:
    bundle = json.loads(Path(
        f"evidence/provider-stage/saved-searches/trace-inputs/{name}.json"
    ).read_text(encoding="utf-8"))
    plan = CompiledSearchPlan.model_validate(bundle["plan"])
    request = EffectiveRequest.model_validate(bundle["current_effective_request"])
    _, base = _inputs()
    policy = base["policy"].model_copy(update={"positioning_cash_samples": 1})
    projection = build_execution_plan(
        plan, run_id=f"projection-{name}",
        current_session_id=bundle["current_session_id"],
        current_revision=bundle["current_revision"],
        current_effective_request=request,
        expected_compilation_binding_digest=bundle["expected_compilation_binding_digest"],
        policy=policy, award_capability=base["award_capability"],
        cash_capability=base["cash_capability"])
    award_by_logical = {query.logical_query_ids[0]: query for query in projection.queries
                        if query.provider == "seats_aero"}
    cash_by_probe: dict[str, list[ProviderQuery]] = defaultdict(list)
    for query in projection.queries:
        if query.role == "direct_cash":
            cash_by_probe[query.logical_use_ids[0]].append(query)
    mandatory_use_by_probe = {use.probe_id: use for use in plan.mandatory_query_uses}
    assert len(mandatory_use_by_probe) == len(plan.mandatory_endpoint_probes)
    for probe in plan.mandatory_endpoint_probes:
        award = award_by_logical[mandatory_use_by_probe[probe.probe_id].query_id]
        assert award.role == "mandatory_award"
        assert award.origins == (probe.origin_endpoint.airport_iata,)
        assert award.destinations == (probe.destination_endpoint.airport_iata,)
        cash = cash_by_probe[probe.probe_id]
        assert len(cash) == len(probe.requested_cabins or (None,))
        assert all(query.origins == award.origins and
                   query.destinations == award.destinations and
                   probe.date_envelope.start <= query.start_date <=
                   probe.date_envelope.end and query.start_date == query.end_date
                   for query in cash)
    assert len(cash_by_probe) == len(plan.mandatory_endpoint_probes)
    assert not any(query.role in {"cash_access", "cash_egress"}
                   for query in projection.queries)
    assert _positioning_queries(plan, projection, (), request) == ()

    if plan.positioning_dependencies:
        dependency = next(d for d in plan.positioning_dependencies
                          if d.requested_permission is not False)
        support = next(s for s in plan.support_alternatives
                       if s.support_id == dependency.support_id)
        use = next(u for u in plan.strategy_query_uses
                   if u.query_use_id in support.query_use_ids)
        award = award_by_logical[use.query_id]
        observed_day = request.departure_window.start
        evidence = EvidenceRef(sha256="d" * 64, relative_path="award.json",
                               retrieved_at=datetime(2026, 9, 22, tzinfo=UTC),
                               synthetic=True)
        observation = ProviderObservation(
            observation_id="observed-access-award", provider="seats_aero",
            backend="test", provider_version="test", kind="award_itinerary",
            query_id=award.query_id, logical_query_ids=award.logical_query_ids,
            requested_travelers=award.travelers, origin=award.origins[0],
            destination=award.destinations[0], departure_date=observed_day,
            legs=(ObservedLeg(origin=award.origins[0],
                              destination=award.destinations[0],
                              departure_local=f"{observed_day}T10:00:00",
                              arrival_local=f"{observed_day}T20:00:00"),),
            retrieved_at=evidence.retrieved_at, evidence=(evidence,))
        positioning = _positioning_queries(plan, projection, (observation,), request)
        assert any(query.positioning_dependency_ids == (dependency.dependency_id,) and
                   query.activation_observation_ids == (observation.observation_id,)
                   for query in positioning)


def test_mandatory_then_direct_cash_and_complete_empty_stream() -> None:
    plan, args = _inputs()
    award = EmptyAdapter(paginated=True)
    cash = EmptyAdapter()
    result = execute_provider_plan(plan, award_adapter=award, cash_adapter=cash, **args)
    assert result.status == "partial"
    assert len(award.queries) == 2
    assert len(cash.queries) == 1
    assert result.award_usage.requests == 1
    assert result.award_usage.pages == 2
    assert any(receipt.status == "empty" for receipt in result.coverage)
    assert any(receipt.status == "omitted" for receipt in result.coverage)
    assert {r.unit_id for r in result.coverage} == {
        u.unit_id for u in result.execution_plan.coverage_units}


def test_stale_before_fetch_blocks_transport() -> None:
    plan, args = _inputs()
    award = EmptyAdapter()
    cash = EmptyAdapter()
    result = execute_provider_plan(
        plan, award_adapter=award, cash_adapter=cash,
        current_authority=lambda: ("new-session", 3, args["current_effective_request"],
                                   args["expected_compilation_binding_digest"]), **args)
    assert result.status == "stale"
    assert not award.queries and not cash.queries
    assert all(receipt.status == "omitted" for receipt in result.coverage)


def test_stale_initial_handoff_rejects_execution_plan() -> None:
    plan, args = _inputs()
    with pytest.raises(ValueError, match="stale plan handoff"):
        build_execution_plan(plan, **{**args, "current_revision": 3})


def test_attachment_rebuilds_original_query_projection() -> None:
    plan, args = _inputs()
    result = execute_provider_plan(plan, award_adapter=EmptyAdapter(),
                                   cash_adapter=EmptyAdapter(), **args)
    assert validate_result_attachment(plan, result, **{k: v for k, v in args.items()
                                                        if k != "run_id"}) == result
    with pytest.raises(ValueError, match="stale plan handoff"):
        validate_result_attachment(plan, result, **{**{k: v for k, v in args.items()
                                                     if k != "run_id"}, "current_revision": 3})


def test_final_partial_page_stays_partial() -> None:
    class PartialAdapter(EmptyAdapter):
        def parse(self, query: ProviderQuery, capture: CapturedResponse, *,
                  airport_timezones: Mapping[str, str]) -> ParsedProviderPage:
            return ParsedProviderPage(query_id=query.query_id, status="partial",
                                      pair_coverage_exhaustive=False)

    plan, args = _inputs()
    query = build_execution_plan(plan, **args).queries[0]
    receipt, transports, observations, usage = _execute_query(
        query, PartialAdapter(), policy=args["policy"],
        budget=args["policy"].award_budget, usage=ResourceUsage(),
        timezones={"SFO": "America/Los_Angeles", "LAX": "America/Los_Angeles"},
        fresh=lambda: True)
    assert receipt.status == "partial"
    assert receipt.pair_coverage == "unknown"
    assert len(transports) == 1 and not observations and usage.pages == 1


def test_full_trace_graph_is_accounted_and_cash_precedes_supplemental() -> None:
    plan, args = _inputs()
    budget = ResourceBudget(requests=20, attempts=20, pages=20, detail_calls=0,
                            rows=50, bytes=100000, elapsed_seconds=30)
    args = {**args, "policy": args["policy"].model_copy(update={"award_budget": budget})}
    order: list[str] = []

    class OrderedAdapter(EmptyAdapter):
        def fetch(self, query: ProviderQuery, *, cursor: str | None,
                  timeout_seconds: float, max_bytes: int) -> CapturedResponse:
            order.append(query.role)
            return super().fetch(query, cursor=cursor, timeout_seconds=timeout_seconds,
                                 max_bytes=max_bytes)

    award = OrderedAdapter()
    cash = OrderedAdapter()
    result = execute_provider_plan(plan, award_adapter=award, cash_adapter=cash, **args)
    assert len({query_id for query_id, _ in award.queries}) == len(plan.logical_queries)
    assert order[0] == "mandatory_award"
    assert order[1] == "direct_cash"
    assert "supplemental_award" in order[2:]
    assert len(result.coverage) == len(result.execution_plan.coverage_units)
    assert all(receipt.status != "omitted" for receipt in result.coverage
               if receipt.unit_id in {d.relationship_id for d in plan.relationship_dispositions
                                      if d.query_ids})


def test_interrupted_page_stream_does_not_claim_empty_pair() -> None:
    plan, args = _inputs()
    result = execute_provider_plan(plan, award_adapter=EmptyAdapter(paginated=True),
                                   cash_adapter=EmptyAdapter(), **{
                                       **args, "policy": args["policy"].model_copy(update={
                                           "award_budget": ResourceBudget(
                                               requests=1, attempts=1, pages=1, detail_calls=0,
                                               rows=30, bytes=100000, elapsed_seconds=30)})})
    mandatory_ids = {u.query_id for u in plan.mandatory_query_uses}
    mandatory = next(r for r in result.coverage if r.unit_id in mandatory_ids)
    assert mandatory.status == "partial"
    assert mandatory.pair_coverage == "unknown"
    assert not mandatory.stream_complete


def test_atomic_bundle_reserves_a_first_page_for_each_member() -> None:
    plan, args = _inputs()
    hub = next(s for s in plan.supplemental_strategies
               if s.strategy_type.value == "scoped_hub")
    hub_ids = [u.query_id for u in plan.strategy_query_uses
               if u.strategy_id == hub.strategy_id]
    assert len(hub_ids) == 2
    first_hub = f"award:{hub_ids[0]}"
    budget = ResourceBudget(requests=3, attempts=3, pages=3, detail_calls=0,
                            rows=30, bytes=100000, elapsed_seconds=30)
    args = {**args, "policy": args["policy"].model_copy(update={"award_budget": budget})}

    class PaginatedFirstHub(EmptyAdapter):
        def parse(self, query: ProviderQuery, capture: CapturedResponse, *,
                  airport_timezones: Mapping[str, str]) -> ParsedProviderPage:
            more = query.query_id == first_hub and capture.cursor is None
            return ParsedProviderPage(query_id=query.query_id, status="empty", more=more,
                                      next_cursor="page-2" if more else None,
                                      pair_coverage_exhaustive=not more)

    award = PaginatedFirstHub()
    result = execute_provider_plan(plan, award_adapter=award,
                                   cash_adapter=EmptyAdapter(), **args)
    attempted = {query_id for query_id, _ in award.queries}
    assert all(f"award:{logical_id}" in attempted for logical_id in hub_ids)
    first_receipt = next(r for r in result.coverage if r.unit_id == hub_ids[0])
    assert first_receipt.status == "partial"
    assert first_receipt.pair_coverage == "unknown"


def test_refused_positioning_dependency_cannot_activate_cash() -> None:
    plan, args = _inputs()
    access = next(s for s in plan.supplemental_strategies
                  if s.strategy_type.value == "origin_access")
    access_use = next(u for u in plan.strategy_query_uses
                      if u.strategy_id == access.strategy_id)
    physical = f"award:{access_use.query_id}"
    evidence = EvidenceRef(sha256="d" * 64, relative_path="award.json",
                           retrieved_at=datetime(2026, 9, 22, tzinfo=UTC), synthetic=True)
    observation = ProviderObservation(
        observation_id="award-observed", provider="seats_aero", backend="test",
        provider_version="test", kind="award_itinerary", query_id=physical,
        logical_query_ids=(access_use.query_id,), requested_travelers=2,
        origin="SFO", destination="BKK", departure_date=date(2026, 10, 5),
        legs=(ObservedLeg(origin="LAX", destination="BKK",
                          departure_local="2026-10-05T12:00:00"),),
        retrieved_at=datetime(2026, 9, 22, tzinfo=UTC), evidence=(evidence,))
    positioning_policy = args["policy"].model_copy(update={"positioning_cash_samples": 1})
    execution_plan = build_execution_plan(plan, **{**args, "policy": positioning_policy})
    dependency = plan.positioning_dependencies[0]
    assert dependency.requested_permission is None
    assert _positioning_queries(plan, execution_plan, (observation,),
                                args["current_effective_request"])
    refused = plan.model_copy(update={"positioning_dependencies": (
        dependency.model_copy(update={"requested_permission": False}),)})
    assert not _positioning_queries(refused, execution_plan, (observation,),
                                    args["current_effective_request"])


def test_positioning_samples_after_excluding_off_window_awards() -> None:
    plan, args = _inputs()
    access = next(s for s in plan.supplemental_strategies
                  if s.strategy_type.value == "origin_access")
    access_use = next(u for u in plan.strategy_query_uses
                      if u.strategy_id == access.strategy_id)
    evidence = EvidenceRef(sha256="d" * 64, relative_path="award.json",
                           retrieved_at=datetime(2026, 9, 22, tzinfo=UTC), synthetic=True)

    def itinerary(observation_id: str, day: date) -> ProviderObservation:
        return ProviderObservation(
            observation_id=observation_id, provider="seats_aero", backend="test",
            provider_version="test", kind="award_itinerary",
            query_id=f"award:{access_use.query_id}",
            logical_query_ids=(access_use.query_id,), requested_travelers=2,
            origin="LAX", destination="BKK", departure_date=day,
            legs=(ObservedLeg(origin="LAX", destination="BKK",
                              departure_local=f"{day}T12:00:00"),),
            retrieved_at=datetime(2026, 9, 22, tzinfo=UTC), evidence=(evidence,))

    policy = args["policy"].model_copy(update={"positioning_cash_samples": 1})
    execution_plan = build_execution_plan(plan, **{**args, "policy": policy})
    queries = _positioning_queries(
        plan, execution_plan,
        (itinerary("off-window", date(2026, 10, 4)),
         itinerary("in-window", date(2026, 10, 5))),
        args["current_effective_request"])
    assert len(queries) == 1
    assert queries[0].activation_observation_ids == ("in-window",)
    assert queries[0].start_date == date(2026, 10, 5)


def test_fair_rotation_on_high_fanout_trace() -> None:
    bundle = json.loads(Path(
        "evidence/provider-stage/saved-searches/trace-inputs/united_states_to_india.json"
    ).read_text(encoding="utf-8"))
    plan = CompiledSearchPlan.model_validate(bundle["plan"])
    request = EffectiveRequest.model_validate(bundle["current_effective_request"])
    _, base = _inputs()
    projection = build_execution_plan(
        plan, run_id="fair-test", current_session_id=bundle["current_session_id"],
        current_revision=bundle["current_revision"], current_effective_request=request,
        expected_compilation_binding_digest=bundle["expected_compilation_binding_digest"],
        policy=base["policy"], award_capability=base["award_capability"],
        cash_capability=base["cash_capability"])
    by_logical = {q.logical_query_ids[0]: q for q in projection.queries
                  if q.provider == "seats_aero"}
    served: dict[tuple[str, str], int] = defaultdict(int)
    first = _supplemental_order(plan, set(), served, by_logical)[0]
    first_pair = first.supported_original_endpoint_pairs[0]
    first_key = (first_pair.origin_airport_fact_id, first_pair.destination_airport_fact_id)
    served[first_key] = 1
    second = _supplemental_order(plan, set(), served, by_logical)[0]
    second_pair = second.supported_original_endpoint_pairs[0]
    assert (second_pair.origin_airport_fact_id,
            second_pair.destination_airport_fact_id) != first_key


def test_tight_mandatory_budget_spreads_endpoints_and_keeps_omission_ledger() -> None:
    bundle = json.loads(Path(
        "evidence/provider-stage/saved-searches/trace-inputs/united_states_to_japan.json"
    ).read_text(encoding="utf-8"))
    plan = CompiledSearchPlan.model_validate(bundle["plan"])
    request = EffectiveRequest.model_validate(bundle["current_effective_request"])
    _, base = _inputs()
    budget = ResourceBudget(requests=3, attempts=3, pages=3, detail_calls=0,
                            rows=30, bytes=100000, elapsed_seconds=30)
    args = {**base, "run_id": "mandatory-fair-test",
            "current_session_id": bundle["current_session_id"],
            "current_revision": bundle["current_revision"],
            "current_effective_request": request,
            "expected_compilation_binding_digest": bundle["expected_compilation_binding_digest"],
            "policy": base["policy"].model_copy(update={"award_budget": budget,
                                                    "cash_budget": budget})}
    award = EmptyAdapter()
    cash = EmptyAdapter()
    result = execute_provider_plan(plan, award_adapter=award,
                                   cash_adapter=cash, **args)
    assert len(award.queries) == 3
    by_id = {q.query_id: q for q in result.execution_plan.queries}
    selected = [by_id[query_id] for query_id, _ in award.queries]
    assert len({q.origins[0] for q in selected}) == 3
    assert len({q.destinations[0] for q in selected}) == 3
    assert len(cash.queries) == 3
    cash_selected = [by_id[query_id] for query_id, _ in cash.queries]
    assert len({q.origins[0] for q in cash_selected}) == 3
    assert len({q.destinations[0] for q in cash_selected}) == 3
    mandatory_ids = {use.probe_id for use in plan.mandatory_query_uses}
    mandatory_receipts = [r for r in result.coverage if r.unit_id in mandatory_ids]
    assert len(mandatory_receipts) == len(plan.mandatory_endpoint_probes) == 40
    assert sum(r.status == "empty" for r in mandatory_receipts) == 3
    assert sum(r.status == "omitted" for r in mandatory_receipts) == 37


def test_get_trips_budget_keeps_all_observed_detail_opportunities() -> None:
    plan, base = _inputs()
    award_capability = base["award_capability"].model_copy(
        update={"detail_strategy": "get_trips"})
    award_budget = ResourceBudget(requests=3, attempts=3, pages=1,
                                  detail_calls=2, rows=30, bytes=100000,
                                  elapsed_seconds=30)
    args = {**base, "award_capability": award_capability,
            "policy": base["policy"].model_copy(update={"award_budget": award_budget})}

    class SummaryDetailAdapter(EmptyAdapter):
        def parse(self, query: ProviderQuery, capture: CapturedResponse, *,
                  airport_timezones: Mapping[str, str]) -> ParsedProviderPage:
            if query.role == "award_detail":
                observation = ProviderObservation(
                    observation_id=f"trip-{query.detail_id}", provider="seats_aero",
                    backend="test", provider_version="test", kind="award_itinerary",
                    query_id=query.query_id, logical_query_ids=query.logical_query_ids,
                    logical_use_ids=query.logical_use_ids, strategy_ids=query.strategy_ids,
                    provider_record_id=f"trip-{query.detail_id}",
                    origin=query.origins[0], destination=query.destinations[0],
                    departure_date=query.start_date,
                    legs=(ObservedLeg(origin=query.origins[0],
                                      destination=query.destinations[0],
                                      departure_local=f"{query.start_date}T10:00:00"),),
                    retrieved_at=capture.evidence.retrieved_at,
                    requested_travelers=query.travelers,
                    requested_cabins=query.cabins,
                    cabin=RawField(state="value", value="business"),
                    evidence=(capture.evidence,))
                return ParsedProviderPage(query_id=query.query_id, status="completed",
                                          observations=(observation,), returned_row_count=1,
                                          pair_coverage_exhaustive=True)
            if query.role != "mandatory_award":
                return super().parse(query, capture, airport_timezones=airport_timezones)
            summaries = tuple(ProviderObservation(
                observation_id=f"summary-{i}", provider="seats_aero",
                backend="test", provider_version="test", kind="award_summary",
                query_id=query.query_id, logical_query_ids=query.logical_query_ids,
                logical_use_ids=query.logical_use_ids, strategy_ids=query.strategy_ids,
                provider_record_id=f"availability-{i}", origin=query.origins[0],
                destination=query.destinations[0], departure_date=query.start_date,
                retrieved_at=capture.evidence.retrieved_at,
                requested_travelers=query.travelers, requested_cabins=query.cabins,
                cabin=RawField(state="value", value="business"),
                seats=RawField() if i == 2 else RawField(state="value", value=2),
                evidence=(capture.evidence,))
                for i in range(3))
            return ParsedProviderPage(query_id=query.query_id, status="completed",
                                      observations=summaries, returned_row_count=3,
                                      pair_coverage_exhaustive=True)

    award = SummaryDetailAdapter()
    result = execute_provider_plan(plan, award_adapter=award,
                                   cash_adapter=EmptyAdapter(), **args)
    details = [q for q in result.execution_plan.queries if q.role == "award_detail"]
    assert len(details) == 3
    assert len([q for q, _ in award.queries if q.startswith("award-detail:")]) == 2
    assert result.award_usage.pages == 1 and result.award_usage.detail_calls == 2
    detail_receipts = [r for r in result.coverage if r.unit_id.startswith("detail:")]
    assert sorted(r.status for r in detail_receipts) == ["completed", "completed", "omitted"]
    assert sum(o.kind == "award_summary" for o in result.observations) == 3
    assert sum(o.kind == "award_itinerary" for o in result.observations) == 2
    assert validate_result_attachment(plan, result, **{k: v for k, v in args.items()
                                                     if k != "run_id"}) == result


def test_access_detail_gets_first_slot_before_mandatory_detail() -> None:
    plan, base = _inputs()
    access = next(s for s in plan.supplemental_strategies
                  if s.strategy_type.value == "origin_access")
    capability = base["award_capability"].model_copy(update={"detail_strategy": "get_trips"})
    query_count = len(plan.logical_queries)
    budget = ResourceBudget(requests=query_count + 2, attempts=query_count + 2,
                            pages=query_count, detail_calls=2, rows=30,
                            bytes=100000, elapsed_seconds=30)
    args = {**base, "award_capability": capability,
            "policy": base["policy"].model_copy(update={"award_budget": budget})}

    class AccessAndMandatorySummaries(EmptyAdapter):
        def parse(self, query: ProviderQuery, capture: CapturedResponse, *,
                  airport_timezones: Mapping[str, str]) -> ParsedProviderPage:
            if query.role == "award_detail":
                observation = ProviderObservation(
                    observation_id=f"trip-{query.detail_id}", provider="seats_aero",
                    backend="test", provider_version="test", kind="award_itinerary",
                    query_id=query.query_id, logical_query_ids=query.logical_query_ids,
                    logical_use_ids=query.logical_use_ids, strategy_ids=query.strategy_ids,
                    provider_record_id=query.detail_id, origin=query.origins[0],
                    destination=query.destinations[0], departure_date=query.start_date,
                    legs=(ObservedLeg(origin=query.origins[0],
                                      destination=query.destinations[0],
                                      departure_local=f"{query.start_date}T10:00:00"),),
                    retrieved_at=capture.evidence.retrieved_at,
                    requested_travelers=query.travelers, requested_cabins=query.cabins,
                    evidence=(capture.evidence,))
                return ParsedProviderPage(query_id=query.query_id, status="completed",
                                          observations=(observation,), returned_row_count=1,
                                          pair_coverage_exhaustive=True)
            if query.role not in {"mandatory_award", "supplemental_award"} or (
                query.role == "supplemental_award" and access.strategy_id not in query.strategy_ids
            ):
                return super().parse(query, capture, airport_timezones=airport_timezones)
            summaries = tuple(ProviderObservation(
                observation_id=f"summary-{query.query_id}-{i}", provider="seats_aero",
                backend="test", provider_version="test", kind="award_summary",
                query_id=query.query_id, logical_query_ids=query.logical_query_ids,
                logical_use_ids=query.logical_use_ids, strategy_ids=query.strategy_ids,
                provider_record_id=f"{query.query_id}-{i}", origin=query.origins[0],
                destination=query.destinations[0],
                departure_date=(date(2026, 10, 5) if i == 1 and
                                access.strategy_id in query.strategy_ids else
                                query.start_date),
                retrieved_at=capture.evidence.retrieved_at,
                requested_travelers=query.travelers, requested_cabins=query.cabins,
                cabin=RawField(state="value", value=query.cabins[0]),
                evidence=(capture.evidence,)) for i in range(2))
            return ParsedProviderPage(query_id=query.query_id, status="completed",
                                      observations=summaries, returned_row_count=2,
                                      pair_coverage_exhaustive=True)

    award = AccessAndMandatorySummaries()
    result = execute_provider_plan(plan, award_adapter=award,
                                   cash_adapter=EmptyAdapter(), **args)
    details = [q for q in result.execution_plan.queries if q.role == "award_detail"]
    fetched = [q for q in details if (q.query_id, None) in award.queries]
    assert len(details) == 4
    assert len(fetched) == 2
    assert access.strategy_id in fetched[0].strategy_ids
    assert fetched[0].detail_id is not None and fetched[0].detail_id.endswith("-1")
    assert fetched[1].activation_scope.startswith("detail:award:")
    assert fetched[1].strategy_ids == ()
    assert sorted(receipt.status for receipt in result.coverage
                  if receipt.unit_id.startswith("detail:")) == [
                      "completed", "completed", "omitted", "omitted"]
    assert validate_result_attachment(plan, result, **{k: v for k, v in args.items()
                                                     if k != "run_id"}) == result
