"""Independent whole-graph accounting audit of trace-derived provider execution."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import JsonValue

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
    ProviderResultSet,
    RawField,
    ResourceBudget,
    content_digest,
)
from award_agent.providers.execution import execute_provider_plan, validate_result_attachment
from award_agent.search_planning.compilation_contracts import CompiledSearchPlan


class AuditAdapter:
    """Finite fake acquisition with one attributed itinerary per physical query."""

    def __init__(self, order: list[str]) -> None:
        self.order = order

    def fetch(
        self, query: ProviderQuery, *, cursor: str | None,
        timeout_seconds: float, max_bytes: int,
    ) -> CapturedResponse:
        assert cursor is None and timeout_seconds > 0 and max_bytes >= 100
        self.order.append(query.role)
        body: dict[str, JsonValue] = {"synthetic": True, "query": query.query_id}
        return CapturedResponse(
            query_id=query.query_id, provider=query.provider, status="completed", body=body,
            evidence=EvidenceRef(
                sha256=content_digest(body), relative_path=f"{content_digest(body)}.json",
                retrieved_at=datetime(2026, 9, 22, tzinfo=UTC), synthetic=True,
            ),
            elapsed_seconds=0.01, byte_count=100,
        )

    def parse(
        self, query: ProviderQuery, capture: CapturedResponse, *,
        airport_timezones: Mapping[str, str],
    ) -> ParsedProviderPage:
        origin, destination = query.origins[0], query.destinations[0]
        observation = ProviderObservation(
            observation_id=f"synthetic:{query.query_id}", provider=query.provider,
            backend="synthetic", provider_version="synthetic-v1",
            kind="award_itinerary" if query.provider == "seats_aero" else "cash_itinerary",
            query_id=query.query_id, logical_query_ids=query.logical_query_ids,
            logical_use_ids=query.logical_use_ids, strategy_ids=query.strategy_ids,
            provider_record_id=query.query_id, origin=origin, destination=destination,
            departure_date=query.start_date, airport_sequence=(origin, destination),
            legs=(ObservedLeg(
                origin=origin, destination=destination,
                departure_local=f"{query.start_date}T12:00:00",
                arrival_local=f"{query.start_date}T14:00:00",
            ),),
            retrieved_at=capture.evidence.retrieved_at, requested_travelers=query.travelers,
            requested_cabins=query.cabins, seats=RawField(state="value", value=query.travelers),
            evidence=(capture.evidence,),
        )
        return ParsedProviderPage(
            query_id=query.query_id, status="completed", observations=(observation,),
            returned_row_count=1, provider_row_ids=(query.query_id,), pair_coverage_exhaustive=True,
        )


@pytest.mark.parametrize("case", [
    "united_states_to_japan", "united_states_to_india", "ready_exact_airports",
])
@pytest.mark.parametrize("progressive", [False, True])
def test_every_trace_graph_unit_is_accounted_with_bounded_fake_calls(
    case: str, progressive: bool,
) -> None:
    source = Path("evidence/provider-stage/saved-searches/trace-inputs") / f"{case}.json"
    bundle = json.loads(source.read_text(encoding="utf-8"))
    plan = CompiledSearchPlan.model_validate(bundle["plan"])
    unchanged_plan = plan.model_dump_json()
    request = EffectiveRequest.model_validate(bundle["current_effective_request"])
    mandatory_ids = {use.query_id for use in plan.mandatory_query_uses}
    award_calls = len(mandatory_ids) + 5 if progressive else 3
    award_budget = ResourceBudget(
        requests=award_calls, attempts=award_calls, pages=award_calls, detail_calls=0,
        rows=award_calls, bytes=award_calls * 100, elapsed_seconds=30,
    )
    cash_budget = ResourceBudget(
        requests=3, attempts=3, pages=3, detail_calls=0, rows=3, bytes=300,
        elapsed_seconds=30,
    )
    policy = ExecutionPolicy(
        version="independent-graph-audit-v1", award_budget=award_budget, cash_budget=cash_budget,
        budget_evidence=("synthetic finite offline accounting test; no live acceptance",),
        direct_cash_samples=2, positioning_cash_samples=1, page_size=10,
        request_timeout_seconds=10,
    )
    award_capability = ProviderCapability(
        provider="seats_aero", version="synthetic-v1", backend="synthetic", operation="fake",
        reviewed=True, evidence_digests=("a" * 64,),
    )
    cash_capability = ProviderCapability(
        provider="gfly", version="synthetic-v1", backend="synthetic", operation="fake",
        reviewed=True, evidence_digests=("b" * 64,),
    )
    order: list[str] = []
    result = execute_provider_plan(
        plan, run_id="independent-review", current_session_id=bundle["current_session_id"],
        current_revision=bundle["current_revision"], current_effective_request=request,
        expected_compilation_binding_digest=bundle["expected_compilation_binding_digest"],
        policy=policy, award_capability=award_capability, cash_capability=cash_capability,
        award_adapter=AuditAdapter(order), cash_adapter=AuditAdapter(order),
    )
    assert plan.model_dump_json() == unchanged_plan
    receipts = {receipt.unit_id: receipt for receipt in result.coverage}
    graph_ids = (
        {query.query_id for query in plan.logical_queries}
        | {use.probe_id for use in plan.mandatory_query_uses}
        | {use.query_use_id for use in plan.strategy_query_uses}
        | {item.relationship_id for item in plan.relationship_dispositions}
        | {item.dependency_id for item in plan.positioning_dependencies}
    )
    cash_ids = {
        f"cash:{query.query_id}" for query in result.execution_plan.queries
        if query.provider == "gfly"
    }
    assert set(receipts) == graph_ids | cash_ids
    assert len(result.coverage) == len(graph_ids) + len(cash_ids)
    assert all(receipt.reason for receipt in result.coverage)
    assert result.award_usage.requests <= award_calls
    assert result.cash_usage.requests <= 3
    assert result.award_usage.attempts + result.cash_usage.attempts == len(order)
    assert all(receipt.status in {"completed", "omitted", "partial"} for receipt in result.coverage)
    executed_logical = {
        query_id for query_id in {q.query_id for q in plan.logical_queries}
        if receipts[query_id].status == "completed"
    }
    assert result.award_usage.requests == len(executed_logical)
    assert {receipt.query_id for receipt in result.transport_receipts if receipt.provider == "seats_aero"} == {
        f"award:{query_id}" for query_id in executed_logical
    }
    for use in plan.mandatory_query_uses:
        assert receipts[use.probe_id].status == receipts[use.query_id].status
        assert receipts[use.probe_id].transport_ids == receipts[use.query_id].transport_ids
    for strategy_use in plan.strategy_query_uses:
        assert receipts[strategy_use.query_use_id].status == receipts[strategy_use.query_id].status
        assert receipts[strategy_use.query_use_id].observation_ids == receipts[strategy_use.query_id].observation_ids
    for disposition in plan.relationship_dispositions:
        receipt = receipts[disposition.relationship_id]
        if disposition.query_ids:
            statuses = {receipts[qid].status for qid in disposition.query_ids}
            expected_status = (
                "completed" if statuses == {"completed"}
                else "omitted" if statuses == {"omitted"} else "partial"
            )
            assert receipt.status == expected_status
            assert set(receipt.query_ids) == {f"award:{qid}" for qid in disposition.query_ids}
            assert set(receipt.transport_ids) == {
                tid for qid in disposition.query_ids for tid in receipts[qid].transport_ids
            }
    for dependency in plan.positioning_dependencies:
        queries = [query for query in result.execution_plan.queries
                   if dependency.dependency_id in query.positioning_dependency_ids]
        if not queries:
            assert receipts[dependency.dependency_id].status == "omitted"
        else:
            assert all(query.activation_observation_ids for query in queries)
    if "direct_cash" in order:
        first_cash = order.index("direct_cash")
        assert all(role == "mandatory_award" for role in order[:first_cash])
        assert "mandatory_award" not in order[first_cash:]
    reloaded = ProviderResultSet.model_validate_json(result.model_dump_json())
    assert reloaded == result
    assert validate_result_attachment(
        plan, reloaded, current_session_id=bundle["current_session_id"],
        current_revision=bundle["current_revision"], current_effective_request=request,
        expected_compilation_binding_digest=bundle["expected_compilation_binding_digest"],
        policy=policy, award_capability=award_capability, cash_capability=cash_capability,
    ) == result
