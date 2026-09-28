"""Deterministic, bounded activation of the complete M2C search graph."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import date, timedelta
from typing import Any, Literal, cast

from award_agent.domain import EffectiveRequest
from award_agent.search_planning.compilation_contracts import CompiledSearchPlan
from award_agent.search_planning.handoff import PlanHandoffStatus, check_plan_handoff
from award_agent.search_planning.knowledge import PlanningKnowledgeRepository

from .contracts import (
    CoverageReceipt,
    CoverageUnit,
    ExecutionBinding,
    ExecutionPolicy,
    ParsedProviderPage,
    ProviderAdapter,
    ProviderCapability,
    ProviderExecutionPlan,
    ProviderObservation,
    ProviderQuery,
    ProviderResultSet,
    ResourceBudget,
    ResourceUsage,
    TransportReceipt,
    ValidationFinding,
    content_digest,
)
from .timezones import CatalogTimezoneResolver

Authority = Callable[[], tuple[str, int, EffectiveRequest, str]]


def _fresh(
    plan: CompiledSearchPlan, session_id: str, revision: int,
    request: EffectiveRequest, compilation_binding_digest: str,
) -> bool:
    return check_plan_handoff(
        plan, current_session_id=session_id, current_revision=revision,
        current_effective_request=request,
        expected_compilation_binding_digest=compilation_binding_digest,
    ).status is PlanHandoffStatus.CURRENT


def _sample_dates(start: date, end: date, count: int) -> tuple[date, ...]:
    if count <= 0:
        return ()
    days = (end - start).days
    if count == 1 or days == 0:
        return (start,)
    return tuple(sorted({start + timedelta(days=round(days * i / (count - 1)))
                         for i in range(count)}))


def _query_id(prefix: str, payload: dict[str, Any]) -> str:
    return f"{prefix}:{content_digest(payload)}"


def build_execution_plan(
    plan: CompiledSearchPlan, *, run_id: str, current_session_id: str,
    current_revision: int, current_effective_request: EffectiveRequest,
    expected_compilation_binding_digest: str, policy: ExecutionPolicy,
    award_capability: ProviderCapability, cash_capability: ProviderCapability,
) -> ProviderExecutionPlan:
    """Project all compiled work; budget admission happens during execution."""
    if not _fresh(plan, current_session_id, current_revision, current_effective_request,
                  expected_compilation_binding_digest):
        raise ValueError("stale plan handoff prevents provider execution")
    if not (award_capability.reviewed and cash_capability.reviewed):
        raise ValueError("provider capabilities require reviewed capture evidence")
    if award_capability.provider != "seats_aero" or cash_capability.provider != "gfly":
        raise ValueError("provider capability assignment is reversed")
    if current_effective_request.travelers is None:
        raise ValueError("provider execution requires resolved traveler count")
    directory = {item.airport_id: item.airport_iata for item in plan.airport_directory}
    mandatory_by_query: dict[str, list[str]] = defaultdict(list)
    strategy_by_query: dict[str, list[str]] = defaultdict(list)
    strategies_by_query: dict[str, list[str]] = defaultdict(list)
    for use in plan.mandatory_query_uses:
        mandatory_by_query[use.query_id].append(use.probe_id)
    for strategy_use in plan.strategy_query_uses:
        strategy_by_query[strategy_use.query_id].append(strategy_use.query_use_id)
        strategies_by_query[strategy_use.query_id].append(strategy_use.strategy_id)
    queries: list[ProviderQuery] = []
    for logical in plan.logical_queries:
        query_id = logical.query_id
        queries.append(ProviderQuery(
            query_id=f"award:{query_id}", provider="seats_aero",
            role="mandatory_award" if query_id in mandatory_by_query else "supplemental_award",
            origins=(directory[logical.origin_airport_fact_id],),
            destinations=(directory[logical.destination_airport_fact_id],),
            start_date=logical.date_envelope.start, end_date=logical.date_envelope.end,
            travelers=current_effective_request.travelers,
            cabins=tuple(item.value for item in logical.requested_cabins),
            filters=logical.filter_obligations,
            result_validation_obligations=logical.result_validation_obligations,
            logical_query_ids=(query_id,),
            logical_use_ids=tuple(sorted(mandatory_by_query[query_id] + strategy_by_query[query_id])),
            strategy_ids=tuple(sorted(set(strategies_by_query[query_id]))),
            activation_scope="mandatory" if query_id in mandatory_by_query else "supplemental",
            page_size=policy.page_size,
            include_trips=award_capability.detail_strategy == "include_trips",
        ))
    for probe in plan.mandatory_endpoint_probes:
        for sampled in _sample_dates(probe.date_envelope.start, probe.date_envelope.end,
                                     policy.direct_cash_samples):
            requested_cabins = tuple(item.value for item in probe.requested_cabins)
            for cabin in requested_cabins or (None,):
                payload = {"probe": probe.probe_id, "date": sampled.isoformat(),
                           "currency": policy.currency, "cabin": cabin}
                queries.append(ProviderQuery(
                    query_id=_query_id("cash-direct", payload), provider="gfly", role="direct_cash",
                    origins=(probe.origin_endpoint.airport_iata,),
                    destinations=(probe.destination_endpoint.airport_iata,),
                    start_date=sampled, end_date=sampled, travelers=probe.traveler_count,
                    cabins=(cabin,) if cabin is not None else (),
                    logical_use_ids=(probe.probe_id,), activation_scope="direct_endpoint",
                    currency=policy.currency, page_size=policy.page_size,
                ))
    units: list[CoverageUnit] = []
    units.extend(CoverageUnit(unit_id=q.query_id, kind="logical_query",
                              logical_query_ids=(q.query_id,)) for q in plan.logical_queries)
    units.extend(CoverageUnit(unit_id=u.probe_id, kind="mandatory_use",
                              logical_query_ids=(u.query_id,)) for u in plan.mandatory_query_uses)
    units.extend(CoverageUnit(unit_id=u.query_use_id, kind="strategy_use",
                              logical_query_ids=(u.query_id,), strategy_id=u.strategy_id)
                 for u in plan.strategy_query_uses)
    units.extend(CoverageUnit(unit_id=d.relationship_id, kind="relationship",
                              logical_query_ids=d.query_ids)
                 for d in plan.relationship_dispositions)
    units.extend(CoverageUnit(unit_id=d.dependency_id,
                              kind="positioning_dependency") for d in plan.positioning_dependencies)
    units.extend(CoverageUnit(unit_id=f"cash:{q.query_id}", kind="cash_query")
                 for q in queries if q.provider == "gfly")
    binding = ExecutionBinding(
        run_id=run_id, session_id=plan.identity.session_id, revision=plan.identity.revision,
        effective_request_digest=plan.identity.effective_request_digest,
        compilation_binding_digest=plan.identity.compilation_binding_digest,
        plan_digest=plan.plan_digest, policy_digest=content_digest(policy),
        award_capability_digest=content_digest(award_capability),
        cash_capability_digest=content_digest(cash_capability),
    )
    return ProviderExecutionPlan(binding=binding, policy=policy,
                                 award_capability=award_capability,
                                 cash_capability=cash_capability,
                                 queries=tuple(queries), coverage_units=tuple(units),
                                 deferred_constraints=plan.constraint_obligations)


def _fits(usage: ResourceUsage, budget: ResourceBudget, *, continuing: bool = False,
          detail: bool = False) -> bool:
    return ((continuing or usage.requests < budget.requests)
            and usage.attempts < budget.attempts
            and ((usage.detail_calls < budget.detail_calls) if detail else
                 (usage.pages < budget.pages))
            and usage.rows < budget.rows
            and usage.bytes < budget.bytes and usage.elapsed_seconds < budget.elapsed_seconds)


def _execute_query(
    query: ProviderQuery, adapter: ProviderAdapter, *, policy: ExecutionPolicy,
    budget: ResourceBudget, usage: ResourceUsage, timezones: Mapping[str, str],
    fresh: Callable[[], bool],
) -> tuple[CoverageReceipt, list[TransportReceipt], list[ProviderObservation], ResourceUsage]:
    transports: list[TransportReceipt] = []
    observations: list[ProviderObservation] = []
    seen_ids: set[str] = set()
    seen_observation_ids: set[str] = set()
    cursor: str | None = None
    seen_cursors: set[str] = set()
    status = "omitted"
    reason = "budget_exhausted"
    complete = False
    pair_exhaustive = False
    is_detail = query.role == "award_detail"
    while _fits(usage, budget, continuing=bool(transports), detail=is_detail):
        if not fresh():
            status = "partial" if transports else "omitted"
            reason = "stale_handoff"
            break
        remaining_bytes = budget.bytes - usage.bytes
        remaining_seconds = min(policy.request_timeout_seconds,
                                budget.elapsed_seconds - usage.elapsed_seconds)
        if remaining_bytes <= 0 or remaining_seconds <= 0:
            break
        capture = adapter.fetch(query, cursor=cursor, timeout_seconds=remaining_seconds,
                                max_bytes=remaining_bytes)
        usage = usage.model_copy(update={
            "requests": usage.requests + (1 if cursor is None else 0),
            "attempts": usage.attempts + 1,
            "pages": usage.pages + (0 if is_detail else 1),
            "detail_calls": usage.detail_calls + (1 if is_detail else 0),
            "bytes": usage.bytes + capture.byte_count,
            "elapsed_seconds": usage.elapsed_seconds + capture.elapsed_seconds,
        })
        page: ParsedProviderPage = adapter.parse(query, capture,
                                                  airport_timezones=timezones)
        usage = usage.model_copy(update={"rows": usage.rows + page.returned_row_count})
        duplicate_ids: set[str] = set()
        for row_id in page.provider_row_ids:
            if row_id in seen_ids:
                duplicate_ids.add(row_id)
            seen_ids.add(row_id)
        duplicates = tuple(sorted(duplicate_ids))
        new_observations = []
        if page.status not in {"blocked", "rate_limited", "schema_drift", "malformed",
                               "timeout", "failed", "budget_exhausted"}:
            for observation in page.observations:
                if observation.observation_id not in seen_observation_ids:
                    new_observations.append(observation)
                    seen_observation_ids.add(observation.observation_id)
        observations.extend(new_observations)
        transport_id = _query_id("transport", {"query": query.query_id,
                                                "page": len(transports) + 1,
                                                "evidence": capture.evidence.sha256})
        transports.append(TransportReceipt(
            transport_id=transport_id, query_id=query.query_id, provider=query.provider,
            attempt=len(transports) + 1, page=len(transports) + 1,
            status=page.status, evidence=capture.evidence,
            elapsed_seconds=capture.elapsed_seconds, byte_count=capture.byte_count,
            returned_rows=page.returned_row_count, more=page.more, cursor=cursor,
            duplicate_provider_ids=duplicates,
            observation_ids=tuple(o.observation_id for o in new_observations), findings=page.findings,
        ))
        status = "attempted"
        reason = page.status
        if page.status in {"blocked", "rate_limited", "schema_drift", "malformed",
                           "timeout", "failed"}:
            status = "failed"
            break
        if page.status in {"partial", "budget_exhausted"}:
            status = "partial"
            break
        if (usage.rows > budget.rows or usage.bytes > budget.bytes or
                usage.elapsed_seconds > budget.elapsed_seconds):
            status = "partial"
            reason = "resource_budget_exceeded_by_response"
            break
        if not page.more:
            complete = True
            pair_exhaustive = page.pair_coverage_exhaustive
            status = "completed" if observations else "empty" if pair_exhaustive else "partial"
            reason = "stream_complete" if status != "partial" else "pair_coverage_unknown"
            break
        if page.next_cursor in seen_cursors:
            status = "partial"
            reason = "repeated_pagination_cursor"
            break
        assert page.next_cursor is not None
        cursor = page.next_cursor
        seen_cursors.add(cursor)
        if not _fits(usage, budget, continuing=True, detail=is_detail):
            status = "partial"
            reason = "pagination_budget_exhausted"
            break
    if transports and status == "attempted":
        status = "partial"
    receipt = CoverageReceipt(
        unit_id=f"detail:{query.query_id}" if is_detail else
                f"cash:{query.query_id}" if query.provider == "gfly" else
                query.logical_query_ids[0],
        status=cast(Literal["scheduled", "attempted", "completed", "empty", "partial", "failed", "omitted"], status), query_ids=(query.query_id,),
        transport_ids=tuple(t.transport_id for t in transports),
        observation_ids=tuple(o.observation_id for o in observations), reason=reason,
        stream_complete=complete,
        pair_coverage="observed" if observations else "empty" if complete and pair_exhaustive
                      else "unknown" if transports else "not_attempted",
    )
    return receipt, transports, observations, usage


def _derived_receipt(unit: CoverageUnit, query_receipts: dict[str, CoverageReceipt],
                     physical_ids: tuple[str, ...], *, reason: str) -> CoverageReceipt:
    relevant = [query_receipts[q] for q in physical_ids if q in query_receipts]
    if not relevant:
        return CoverageReceipt(unit_id=unit.unit_id, status="omitted", reason=reason)
    statuses = {item.status for item in relevant}
    if any(item.status == "failed" for item in relevant):
        status = "failed"
    elif any(item.status == "partial" for item in relevant):
        status = "partial"
    elif any(item.status == "omitted" for item in relevant):
        status = "omitted" if all(item.status == "omitted" for item in relevant) else "partial"
    elif statuses == {"empty"}:
        status = "empty"
    else:
        status = "completed"
    stream_complete = all(item.stream_complete for item in relevant)
    observations = tuple(sorted({oid for item in relevant for oid in item.observation_ids}))
    pair_coverage = ("observed" if observations else "empty" if status == "empty" else
                     "unknown" if any(item.transport_ids for item in relevant) else "not_attempted")
    return CoverageReceipt(
        unit_id=unit.unit_id, status=cast(Literal["scheduled", "attempted", "completed", "empty", "partial", "failed", "omitted"], status), query_ids=physical_ids,
        transport_ids=tuple(sorted({tid for item in relevant for tid in item.transport_ids})),
        observation_ids=observations, reason=reason if status in {"completed", "empty"} else
        ";".join(sorted({item.reason for item in relevant})),
        stream_complete=stream_complete, pair_coverage=cast(Literal["observed", "empty", "unknown", "not_attempted"], pair_coverage),
    )


def _supplemental_order(plan: CompiledSearchPlan, executed: set[str],
                        served_pairs: dict[tuple[str, str], int],
                        query_by_logical: dict[str, ProviderQuery]) -> list[Any]:
    uses_by_strategy: dict[str, set[str]] = defaultdict(set)
    for use in plan.strategy_query_uses:
        uses_by_strategy[use.strategy_id].add(use.query_id)

    def key(strategy: Any) -> tuple[Any, ...]:
        pairs = [(p.origin_airport_fact_id, p.destination_airport_fact_id)
                 for p in strategy.supported_original_endpoint_pairs]
        fairness = min(served_pairs[pair] for pair in pairs)
        qs = uses_by_strategy[strategy.strategy_id]
        new = {query_by_logical[q].query_id for q in qs} - executed
        reuse = len(qs) - len(new)
        marginal = sum(1 for q in qs if query_by_logical[q].query_id not in executed)
        return (fairness, -reuse, -len(pairs), -marginal, len(new), strategy.strategy_id)

    return sorted(plan.supplemental_strategies, key=key)


def _mandatory_order(
    plan: CompiledSearchPlan, query_by_logical: dict[str, ProviderQuery],
) -> tuple[str, ...]:
    """Spread first calls across endpoint airports while retaining every probe."""
    remaining = {use.query_id for use in plan.mandatory_query_uses}
    strategy_reuse: dict[str, int] = defaultdict(int)
    for use in plan.strategy_query_uses:
        strategy_reuse[use.query_id] += 1
    origin_count: dict[str, int] = defaultdict(int)
    destination_count: dict[str, int] = defaultdict(int)
    ordered: list[str] = []
    while remaining:
        def priority(logical_id: str) -> tuple[Any, ...]:
            query = query_by_logical[logical_id]
            origin = query.origins[0]
            destination = query.destinations[0]
            marginal = int(origin_count[origin] == 0) + int(destination_count[destination] == 0)
            date_days = (query.end_date - query.start_date).days + 1
            return (-marginal, -strategy_reuse[logical_id],
                    origin_count[origin] + destination_count[destination],
                    date_days, origin, destination, query.start_date, query.end_date,
                    logical_id)

        selected = min(remaining, key=priority)
        ordered.append(selected)
        remaining.remove(selected)
        query = query_by_logical[selected]
        origin_count[query.origins[0]] += 1
        destination_count[query.destinations[0]] += 1
    return tuple(ordered)


def _detail_queries(
    execution_plan: ProviderExecutionPlan,
    parent_queries: tuple[ProviderQuery, ...],
    observations: tuple[ProviderObservation, ...],
    completed_query_ids: set[str],
) -> tuple[ProviderQuery, ...]:
    """Enumerate every observed availability ID, including budget omissions."""
    if execution_plan.award_capability.detail_strategy != "get_trips":
        return ()
    summaries_by_parent: dict[str, dict[str, list[ProviderObservation]]] = defaultdict(
        lambda: defaultdict(list))
    parent_by_id = {query.query_id: query for query in parent_queries}
    for observation in observations:
        if (observation.kind == "award_summary" and observation.provider_record_id and
            observation.query_id in parent_by_id and
            observation.query_id in completed_query_ids):
            parent = parent_by_id[observation.query_id]
            if parent.cabins and (
                observation.cabin.state != "value" or
                observation.cabin.value not in parent.cabins
            ):
                continue
            summaries_by_parent[observation.query_id][observation.provider_record_id].append(
                observation)
    candidates_by_parent: dict[str, list[ProviderQuery]] = defaultdict(list)
    for parent in parent_queries:
        for record_id, summaries in sorted(summaries_by_parent[parent.query_id].items()):
            payload = {"parent": parent.query_id, "availability_id": record_id}
            candidates_by_parent[parent.query_id].append(ProviderQuery(
                query_id=_query_id("award-detail", payload), provider="seats_aero",
                role="award_detail", origins=parent.origins,
                destinations=parent.destinations, start_date=parent.start_date,
                end_date=parent.end_date, travelers=parent.travelers,
                cabins=parent.cabins, filters=parent.filters,
                result_validation_obligations=parent.result_validation_obligations,
                logical_query_ids=parent.logical_query_ids,
                logical_use_ids=parent.logical_use_ids,
                strategy_ids=parent.strategy_ids,
                activation_observation_ids=tuple(sorted(o.observation_id for o in summaries)),
                activation_scope=f"detail:{parent.query_id}",
                page_size=parent.page_size, detail_id=record_id,
            ))
    # One ID from each parent query before a second from any parent. This
    # retains fairness even when one response contains many availability IDs.
    return tuple(query for index in range(
        max((len(items) for items in candidates_by_parent.values()), default=0))
        for parent in parent_queries
        for query in candidates_by_parent[parent.query_id][index:index + 1])


def _ordered_details(
    plan: CompiledSearchPlan,
    mandatory: tuple[ProviderQuery, ...],
    supplemental: tuple[ProviderQuery, ...],
    observations: tuple[ProviderObservation, ...],
    request: EffectiveRequest,
) -> tuple[ProviderQuery, ...]:
    """Give each observed access award one detail chance before other details."""
    strategies = {strategy.strategy_id: strategy for strategy in plan.supplemental_strategies}
    uses = {use.query_use_id: use for use in plan.strategy_query_uses}
    supports = {support.support_id: support for support in plan.support_alternatives}
    access_sides: dict[str, set[str]] = defaultdict(set)
    for dependency in plan.positioning_dependencies:
        if dependency.requested_permission is False:
            continue
        support = supports.get(dependency.support_id)
        if support is None:
            continue
        for use_id in support.query_use_ids:
            use = uses.get(use_id)
            if use is not None and strategies[use.strategy_id].strategy_type.value in {
                "origin_access", "destination_access"
            }:
                access_sides[use.query_id].add(dependency.side)
    summaries = {observation.observation_id: observation for observation in observations
                 if observation.kind == "award_summary"}
    first_access: list[ProviderQuery] = []
    remaining_access: list[ProviderQuery] = []
    other: list[ProviderQuery] = []
    seen_parents: set[str] = set()
    for query in supplemental:
        parent_id = query.logical_query_ids[0]
        sides = access_sides.get(parent_id, set())
        in_window = any(
            "destination" in sides or
            ("origin" in sides and request.departure_window is not None and
             (summary := summaries.get(observation_id)) is not None and
             summary.departure_date is not None and
             request.departure_window.start <= summary.departure_date <=
             request.departure_window.end)
            for observation_id in query.activation_observation_ids)
        if not sides or not in_window:
            other.append(query)
        elif parent_id in seen_parents:
            remaining_access.append(query)
        else:
            first_access.append(query)
            seen_parents.add(parent_id)
    return tuple(first_access) + mandatory + tuple(remaining_access) + tuple(other)


def _positioning_queries(
    plan: CompiledSearchPlan, execution_plan: ProviderExecutionPlan,
    award_observations: tuple[ProviderObservation, ...],
    request: EffectiveRequest,
) -> tuple[ProviderQuery, ...]:
    """Activate access/egress research only from a matching observed access award."""
    if execution_plan.policy.positioning_cash_samples == 0:
        return ()
    strategy_by_id = {s.strategy_id: s for s in plan.supplemental_strategies}
    support_by_id = {s.support_id: s for s in plan.support_alternatives}
    use_by_id = {u.query_use_id: u for u in plan.strategy_query_uses}
    airport = {item.airport_id: item.airport_iata for item in plan.airport_directory}
    queries: list[ProviderQuery] = []
    for dependency in plan.positioning_dependencies:
        if dependency.requested_permission is False:
            continue
        support = support_by_id.get(dependency.support_id)
        if support is None:
            continue
        eligible_uses = [use_by_id[uid] for uid in support.query_use_ids
                         if uid in use_by_id and
                         strategy_by_id[use_by_id[uid].strategy_id].strategy_type.value
                         in {"origin_access", "destination_access"}]
        eligible_query_ids = {use.query_id for use in eligible_uses}
        observed = [o for o in award_observations
                    if o.kind == "award_itinerary" and
                    set(o.logical_query_ids) & eligible_query_ids and o.legs]
        if not observed:
            continue
        # Use the observed award departure or arrival local date. Component
        # chronology remains a later journey-validation obligation.
        eligible_observations: list[tuple[ProviderObservation, date]] = []
        for observation in observed:
            if dependency.side == "origin":
                local = observation.legs[0].departure_local
            else:
                local = observation.legs[-1].arrival_local
            if local is None:
                continue
            try:
                component_date = date.fromisoformat(local[:10])
            except ValueError:
                continue
            sampled = component_date
            if dependency.side == "origin":
                window = request.departure_window
                if window is None or not window.start <= sampled <= window.end:
                    continue
            eligible_observations.append((observation, sampled))
        for observation, sampled in eligible_observations[:
            execution_plan.policy.positioning_cash_samples
        ]:
            origin = airport[dependency.from_airport_fact_id]
            destination = airport[dependency.to_airport_fact_id]
            for cabin in observation.requested_cabins or (None,):
                payload = {"dependency": dependency.dependency_id,
                           "observation": observation.observation_id,
                           "date": sampled.isoformat(), "cabin": cabin}
                queries.append(ProviderQuery(
                    query_id=_query_id("cash-positioning", payload), provider="gfly",
                    role="cash_access" if dependency.side == "origin" else "cash_egress",
                    origins=(origin,), destinations=(destination,),
                    start_date=sampled, end_date=sampled,
                    travelers=observation.requested_travelers,
                    cabins=(cabin,) if cabin is not None else (),
                    strategy_ids=tuple(sorted({use.strategy_id for use in eligible_uses})),
                    positioning_dependency_ids=(dependency.dependency_id,),
                    activation_observation_ids=(observation.observation_id,),
                    activation_scope=f"dependency:{dependency.dependency_id}",
                    currency=execution_plan.policy.currency,
                    page_size=execution_plan.policy.page_size,
                ))
    return tuple(queries)


def execute_provider_plan(
    plan: CompiledSearchPlan, *, run_id: str, current_session_id: str,
    current_revision: int, current_effective_request: EffectiveRequest,
    expected_compilation_binding_digest: str, policy: ExecutionPolicy,
    award_capability: ProviderCapability, cash_capability: ProviderCapability,
    award_adapter: ProviderAdapter, cash_adapter: ProviderAdapter,
    current_authority: Authority | None = None,
    timezone_repository: PlanningKnowledgeRepository | None = None,
) -> ProviderResultSet:
    """Execute bounded mandatory, direct cash, and progressive supplemental work.

    A caller supplying ``current_authority`` gets an immediate recheck before
    final attachment. The callback must read its authoritative session ledger.
    """
    execution_plan = build_execution_plan(
        plan, run_id=run_id, current_session_id=current_session_id,
        current_revision=current_revision, current_effective_request=current_effective_request,
        expected_compilation_binding_digest=expected_compilation_binding_digest,
        policy=policy, award_capability=award_capability, cash_capability=cash_capability,
    )
    by_logical = {query.logical_query_ids[0]: query for query in execution_plan.queries
                  if query.provider == "seats_aero"}
    cash_by_probe: dict[str, list[ProviderQuery]] = defaultdict(list)
    for query in execution_plan.queries:
        if query.role == "direct_cash":
            cash_by_probe[query.logical_use_ids[0]].append(query)
    mandatory_ids = _mandatory_order(plan, by_logical)
    probe_order = [use.probe_id for logical_id in mandatory_ids
                   for use in plan.mandatory_query_uses if use.query_id == logical_id]
    direct_cash = [query for sample_index in range(
        max((len(items) for items in cash_by_probe.values()), default=0))
        for probe_id in probe_order
        for query in cash_by_probe[probe_id][sample_index:sample_index + 1]]
    timezones: Mapping[str, str] = (
        CatalogTimezoneResolver(plan, timezone_repository)
        if timezone_repository is not None else
        {item.airport_iata: item.timezone for item in plan.airport_directory})
    award_usage = ResourceUsage()
    cash_usage = ResourceUsage()
    query_receipts: dict[str, CoverageReceipt] = {}
    transports: list[TransportReceipt] = []
    observations: list[ProviderObservation] = []
    stopped: dict[str, bool] = {"seats_aero": False, "gfly": False}

    def authority_fresh() -> bool:
        authority = current_authority() if current_authority is not None else (
            current_session_id, current_revision, current_effective_request,
            expected_compilation_binding_digest)
        return _fresh(plan, *authority)

    def run(query: ProviderQuery, *, reserve_initial_calls: int = 0) -> None:
        nonlocal award_usage, cash_usage
        if query.query_id in query_receipts:
            return
        provider = query.provider
        if not authority_fresh():
            query_receipts[query.query_id] = CoverageReceipt(
                unit_id=f"detail:{query.query_id}" if query.role == "award_detail" else
                f"cash:{query.query_id}" if provider == "gfly" else
                query.logical_query_ids[0], status="omitted", reason="stale_handoff")
            return
        if stopped[provider]:
            query_receipts[query.query_id] = CoverageReceipt(
                unit_id=f"detail:{query.query_id}" if query.role == "award_detail" else
                f"cash:{query.query_id}" if provider == "gfly" else
                query.logical_query_ids[0], status="omitted", reason="provider_hard_stop")
            return
        usage = award_usage if provider == "seats_aero" else cash_usage
        budget = policy.award_budget if provider == "seats_aero" else policy.cash_budget
        if reserve_initial_calls:
            budget = budget.model_copy(update={
                "requests": budget.requests - reserve_initial_calls,
                "attempts": budget.attempts - reserve_initial_calls,
                "pages": budget.pages - reserve_initial_calls,
            })
        if not _fits(usage, budget, detail=query.role == "award_detail"):
            query_receipts[query.query_id] = CoverageReceipt(
                unit_id=f"detail:{query.query_id}" if query.role == "award_detail" else
                f"cash:{query.query_id}" if provider == "gfly" else
                query.logical_query_ids[0], status="omitted", reason="resource_budget_exhausted")
            return
        receipt, new_transports, new_observations, usage = _execute_query(
            query, award_adapter if provider == "seats_aero" else cash_adapter,
            policy=policy, budget=budget, usage=usage, timezones=timezones,
            fresh=authority_fresh)
        query_receipts[query.query_id] = receipt
        transports.extend(new_transports)
        observations.extend(new_observations)
        if provider == "seats_aero":
            award_usage = usage
        else:
            cash_usage = usage
        if any(t.status in {"blocked", "rate_limited", "schema_drift", "malformed"}
               for t in new_transports):
            stopped[provider] = True

    # Every mandatory logical query executes once, even if supplemental uses
    # share its physical acquisition.
    for logical_id in mandatory_ids:
        run(by_logical[logical_id])
    mandatory_details = _detail_queries(
        execution_plan, tuple(by_logical[logical_id] for logical_id in mandatory_ids),
        tuple(observations),
        {qid for qid, receipt in query_receipts.items() if receipt.status == "completed"})
    for query in direct_cash:
        run(query)

    uses_by_strategy: dict[str, set[str]] = defaultdict(set)
    for use in plan.strategy_query_uses:
        uses_by_strategy[use.strategy_id].add(use.query_id)
    served_pairs: dict[tuple[str, str], int] = defaultdict(int)
    remaining = {s.strategy_id: s for s in plan.supplemental_strategies}
    while remaining:
        ordered = _supplemental_order(plan, set(query_receipts), served_pairs, by_logical)
        strategy = next(s for s in ordered if s.strategy_id in remaining)
        del remaining[strategy.strategy_id]
        logical_ids = sorted(uses_by_strategy[strategy.strategy_id])
        if any(
            by_logical[q].query_id in query_receipts and
            query_receipts[by_logical[q].query_id].status not in {"completed", "empty"}
            for q in logical_ids
        ):
            continue
        new_queries = [by_logical[q] for q in logical_ids
                       if by_logical[q].query_id not in query_receipts]
        # Atomic admission: do not start a multi-query strategy with known
        # insufficient request/attempt/page capacity.
        if (stopped["seats_aero"] or
            award_usage.requests + len(new_queries) > policy.award_budget.requests or
            award_usage.attempts + len(new_queries) > policy.award_budget.attempts or
            award_usage.pages + len(new_queries) > policy.award_budget.pages or
            (new_queries and not _fits(award_usage, policy.award_budget))):
            continue
        for index, query in enumerate(new_queries):
            run(query, reserve_initial_calls=len(new_queries) - index - 1)
        pairs = [(p.origin_airport_fact_id, p.destination_airport_fact_id)
                 for p in strategy.supported_original_endpoint_pairs]
        if pairs:
            selected_pair = min(pairs, key=lambda pair: (served_pairs[pair], pair))
            served_pairs[selected_pair] += 1

    for query in execution_plan.queries:
        if (query.provider == "seats_aero" and query.role != "award_detail" and
            query.query_id not in query_receipts):
            query_receipts[query.query_id] = CoverageReceipt(
                unit_id=query.logical_query_ids[0], status="omitted",
                reason="supplemental_budget_or_activation")
    supplemental_details = _detail_queries(
        execution_plan,
        tuple(by_logical[logical_id] for logical_id in sorted(by_logical)
              if by_logical[logical_id].role == "supplemental_award"),
        tuple(observations),
        {qid for qid, receipt in query_receipts.items() if receipt.status == "completed"})
    ordered_details = _ordered_details(
        plan, mandatory_details, supplemental_details,
        tuple(observations), current_effective_request)
    if ordered_details:
        execution_plan = execution_plan.model_copy(update={
            "queries": execution_plan.queries + ordered_details,
            "coverage_units": execution_plan.coverage_units + tuple(
                CoverageUnit(unit_id=f"detail:{query.query_id}", kind="detail_query",
                             logical_query_ids=query.logical_query_ids)
                for query in ordered_details),
        })
        for query in ordered_details:
            run(query)
    usable_award_observations = tuple(
        observation for observation in observations
        if observation.provider == "seats_aero" and
        query_receipts[observation.query_id].status == "completed")
    activated_cash = _positioning_queries(
        plan, execution_plan,
        usable_award_observations,
        current_effective_request)
    if activated_cash:
        cash_units = tuple(CoverageUnit(unit_id=f"cash:{q.query_id}", kind="cash_query")
                           for q in activated_cash)
        execution_plan = execution_plan.model_copy(update={
            "queries": execution_plan.queries + activated_cash,
            "coverage_units": execution_plan.coverage_units + cash_units,
        })
        for query in activated_cash:
            run(query)

    receipts: list[CoverageReceipt] = []
    award_by_logical = {q.logical_query_ids[0]: q.query_id for q in execution_plan.queries
                        if q.provider == "seats_aero" and q.role != "award_detail"}
    cash_by_dep: dict[str, list[str]] = defaultdict(list)
    for query in activated_cash:
        for dep_id in query.positioning_dependency_ids:
            cash_by_dep[dep_id].append(query.query_id)
    disposition_by_id = {d.relationship_id: d for d in plan.relationship_dispositions}
    for unit in execution_plan.coverage_units:
        if unit.kind == "cash_query":
            receipts.append(query_receipts.get(unit.unit_id.removeprefix("cash:"),
                           CoverageReceipt(unit_id=unit.unit_id, status="omitted",
                                           reason="cash_budget_or_provider_stop")))
        elif unit.kind == "detail_query":
            receipts.append(query_receipts.get(unit.unit_id.removeprefix("detail:"),
                           CoverageReceipt(unit_id=unit.unit_id, status="omitted",
                                           reason="detail_budget_or_provider_stop")))
        elif unit.kind == "logical_query":
            receipts.append(query_receipts[award_by_logical[unit.unit_id]])
        elif unit.kind in {"mandatory_use", "strategy_use"}:
            qid = unit.logical_query_ids[0]
            receipts.append(_derived_receipt(unit, query_receipts,
                                             (award_by_logical[qid],), reason="shared_award_query"))
        elif unit.kind == "relationship":
            disposition = disposition_by_id[unit.unit_id]
            if not disposition.query_ids:
                receipts.append(CoverageReceipt(unit_id=unit.unit_id, status="omitted",
                                                reason=",".join(disposition.reason_codes)))
            else:
                physical_ids = tuple(sorted({award_by_logical[q]
                                             for q in disposition.query_ids}))
                receipts.append(_derived_receipt(unit, query_receipts, physical_ids,
                                                 reason="relationship_query_coverage"))
        else:
            deps = tuple(cash_by_dep[unit.unit_id])
            receipts.append(_derived_receipt(unit, query_receipts, deps,
                                             reason="no_observed_award_activation"))
    fresh = authority_fresh()
    if not fresh:
        status = "stale"
    elif all(r.status in {"completed", "empty"} for r in receipts):
        status = "completed"
    elif any(r.status == "failed" for r in receipts) and not any(
        r.status in {"completed", "empty"} for r in receipts
    ):
        status = "failed"
    else:
        status = "partial"
    findings = () if fresh else (ValidationFinding(
        code="stale_attachment", severity="error",
        message="authoritative request or plan identity changed during provider execution"),)
    return ProviderResultSet(execution_plan=execution_plan, status=cast(Literal["completed", "partial", "failed", "stale"], status),
                             observations=tuple(observations),
                             transport_receipts=tuple(transports),
                             coverage=tuple(receipts), award_usage=award_usage,
                             cash_usage=cash_usage, findings=findings)


def validate_result_attachment(
    plan: CompiledSearchPlan, result: ProviderResultSet, *,
    current_session_id: str, current_revision: int,
    current_effective_request: EffectiveRequest,
    expected_compilation_binding_digest: str, policy: ExecutionPolicy,
    award_capability: ProviderCapability, cash_capability: ProviderCapability,
) -> ProviderResultSet:
    """Fail closed if a replay result differs from its current M2C projection.

    The caller must invoke this immediately before attaching the result to its
    session ledger, using values read from that authoritative ledger.
    """
    result = ProviderResultSet.model_validate(result.model_dump(mode="json", round_trip=True))
    if result.status == "stale":
        raise ValueError("stale provider result cannot be attached")
    expected = build_execution_plan(
        plan, run_id=result.execution_plan.binding.run_id,
        current_session_id=current_session_id, current_revision=current_revision,
        current_effective_request=current_effective_request,
        expected_compilation_binding_digest=expected_compilation_binding_digest,
        policy=policy, award_capability=award_capability, cash_capability=cash_capability,
    )
    actual = result.execution_plan
    if actual.binding != expected.binding or actual.policy != expected.policy or \
            actual.award_capability != expected.award_capability or \
            actual.cash_capability != expected.cash_capability or \
            actual.deferred_constraints != expected.deferred_constraints:
        raise ValueError("provider result binding or capability differs from current plan")
    expected_base = {query.query_id: query for query in expected.queries}
    actual_queries = {query.query_id: query for query in actual.queries}
    if any(actual_queries.get(qid) != query for qid, query in expected_base.items()):
        raise ValueError("provider result changed an M2C-derived query")
    actual_coverage = {receipt.unit_id: receipt for receipt in result.coverage}
    complete_award_queries = {
        f"award:{logical.query_id}" for logical in plan.logical_queries
        if actual_coverage[logical.query_id].status == "completed"
    }
    expected_by_logical = {query.logical_query_ids[0]: query for query in expected.queries
                           if query.provider == "seats_aero"}
    mandatory_detail_queries = _detail_queries(
        expected,
        tuple(expected_by_logical[logical_id] for logical_id in _mandatory_order(
            plan, expected_by_logical)),
        tuple(result.observations), complete_award_queries)
    supplemental_detail_queries = _detail_queries(
        expected,
        tuple(expected_by_logical[logical_id] for logical_id in sorted(expected_by_logical)
              if expected_by_logical[logical_id].role == "supplemental_award"),
        tuple(result.observations), complete_award_queries)
    expected_details = mandatory_detail_queries + supplemental_detail_queries
    complete_detail_queries = {
        query.query_id for query in expected_details
        if actual_coverage[f"detail:{query.query_id}"].status == "completed"
    }
    activated = _positioning_queries(
        plan, expected,
        tuple(o for o in result.observations if o.provider == "seats_aero" and
              o.query_id in complete_award_queries | complete_detail_queries),
        current_effective_request,
    )
    expected_all = {**expected_base,
                    **{query.query_id: query for query in expected_details + activated}}
    if actual_queries != expected_all:
        raise ValueError("provider result cash activation is not justified by award evidence")
    expected_units = {unit.unit_id: unit for unit in expected.coverage_units}
    expected_units.update({f"detail:{query.query_id}": CoverageUnit(
        unit_id=f"detail:{query.query_id}", kind="detail_query",
        logical_query_ids=query.logical_query_ids) for query in expected_details})
    expected_units.update({f"cash:{query.query_id}": CoverageUnit(
        unit_id=f"cash:{query.query_id}", kind="cash_query") for query in activated})
    if {unit.unit_id: unit for unit in actual.coverage_units} != expected_units:
        raise ValueError("provider result changed compiled graph coverage units")
    award_physical = {logical_id: f"award:{logical_id}"
                      for logical_id in (q.query_id for q in plan.logical_queries)}
    expected_links: dict[str, set[str]] = {}
    for unit in expected.coverage_units:
        if unit.kind in {"logical_query", "mandatory_use", "strategy_use"}:
            expected_links[unit.unit_id] = {award_physical[unit.logical_query_ids[0]]}
        elif unit.kind == "relationship":
            expected_links[unit.unit_id] = {award_physical[q]
                                            for q in unit.logical_query_ids}
        elif unit.kind == "cash_query":
            expected_links[unit.unit_id] = {unit.unit_id.removeprefix("cash:")}
        else:
            expected_links[unit.unit_id] = {query.query_id for query in activated
                                             if unit.unit_id in query.positioning_dependency_ids}
    for query in activated:
        expected_links[f"cash:{query.query_id}"] = {query.query_id}
    for query in expected_details:
        expected_links[f"detail:{query.query_id}"] = {query.query_id}
    for unit_id, allowed in expected_links.items():
        linked = set(actual_coverage[unit_id].query_ids)
        if not linked <= allowed or (linked and linked != allowed):
            raise ValueError("provider coverage query links differ from the compiled graph")
        if not linked and actual_coverage[unit_id].status != "omitted":
            raise ValueError("non-omitted provider coverage requires its exact query links")
    return result
