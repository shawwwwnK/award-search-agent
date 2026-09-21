"""Bounded live diagnostic from the active Intent corpus through M2C.

This is connector/evaluation code only.  It supplies no clarification answers,
does not construct a travel-provider client, and does not alter workflow policy.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

from award_agent.clarification import (
    OpenAIClarificationComposerConfig,
    OpenAIClarificationPromptComposer,
    start_clarification,
)
from award_agent.domain import (
    ClarificationSessionStatus,
    EffectiveRequest,
    LocationKind,
    RawRequest,
    RequestContext,
    RequestUnderstandingOutcome,
)
from award_agent.intent import (
    OpenAISemanticIntentConfig,
    OpenAISemanticIntentInterpreter,
    understand_request,
)
from award_agent.intent.holidays import NagerHolidayProvider
from award_agent.observability.llm_trace import write_eval_llm_trace
from award_agent.search_planning.airport_selection_policy import (
    airport_selection_cap_policy_digest,
    context_for_resolved_location,
    load_default_airport_selection_cap_policy,
)
from award_agent.search_planning.airport_selector import (
    REFINED_AIRPORT_SELECTOR_PROMPT,
    AirportSelectionRecord,
    AirportSelectorModelInput,
    OpenAIAirportSelector,
    OpenAIAirportSelectorConfig,
    airport_selection_distance_policy_digest,
    airport_selection_record_digest,
    validate_airport_selection_proposal,
)
from award_agent.search_planning.compilation_contracts import (
    DirectGroundingSource,
    M2ASelectionRecordSource,
    SearchPlanningInput,
    SelectionRecordIdBinding,
)
from award_agent.search_planning.contracts import (
    EndpointRole,
    LocationResolutionStatus,
    PlanningInputEnvelope,
    PlanningSource,
    ResolvedLocation,
    SelectedAirport,
)
from award_agent.search_planning.distance_consistency import CityAirportDistanceConsistency
from award_agent.search_planning.gateway_discovery import (
    GatewayDiscoveryGeneratorConfiguration,
    GatewayDiscoveryInput,
    GatewayDiscoveryResult,
    discover_gateway_candidates,
    gateway_discovery_result_digest,
    replay_gateway_discovery_result,
)
from award_agent.search_planning.gateway_generator import (
    DEFAULT_GATEWAY_GENERATOR_PROMPT,
    GATEWAY_GENERATOR_ADAPTER_VERSION,
    GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
    GatewayOutboundDateContext,
    OpenAIGatewayGenerator,
    OpenAIGatewayGeneratorConfig,
)
from award_agent.search_planning.handoff import PlanHandoffStatus, check_plan_handoff
from award_agent.search_planning.knowledge import (
    CatalogKnowledgeRepository,
    normalize_location_alias,
)
from award_agent.search_planning.market_policy import (
    load_default_planning_market_policy,
    planning_market_policy_digest,
)
from award_agent.search_planning.planner import plan_searches
from award_agent.search_planning.policy import PlanningPolicy

DEFAULT_CORPUS = Path("evals/intent/one_way_award_behavior_cases_v1.yaml")
DEFAULT_CATALOG = Path("data/search_planning/catalogs/m1a-3cb7981519612945")
DEFAULT_PRIVATE_ROOT = Path("evals/intent_to_search_planning/traces-live")
CORPUS_SHA256 = "52a98b9ca316b9a2744c21072d6d0d603bcf4265f45328b6358ef2f1a238607a"
CONTRACT_VERSION = "intent_behavior_v1"
EVALUATOR_VERSION = "intent_to_search_planning_live_v2"
PINNED_MODEL = "gpt-5.6-luna"
MAX_TRIALS = 1
MAX_CALLS_PER_CASE = 6  # intent repair + composer + two selectors + gateway


class EndToEndFixtureError(ValueError):
    """The disclosed corpus or local evidence identity failed preflight."""


def _load_corpus(path: Path) -> tuple[Mapping[str, Any], ...]:
    # Reuse the active Intent evaluator's exact contract validation, then bind
    # the disclosed bytes so a same-shape replacement cannot silently run.
    from award_agent.cli.intent_eval import _preflight_one_way_award_cases

    corpus = _preflight_one_way_award_cases(path)
    if (
        corpus.contract_version != CONTRACT_VERSION
        or corpus.fixture_sha256 != CORPUS_SHA256
        or len(corpus.scenarios) != 19
    ):
        raise EndToEndFixtureError("active Intent behavioral corpus identity drifted")
    return tuple(corpus.scenarios)


def _score_intent(
    oracle: Mapping[str, Any], understanding: Any
) -> tuple[str, list[dict[str, Any]], bool]:
    """Use the active Intent evaluator's scoring contract without forking it."""
    from award_agent.cli.intent_eval import _action, _hard_checks_pass, _score_result

    checks = _score_result(oracle, understanding)
    return _action(understanding), checks, _hard_checks_pass(checks)


def _default_intent(config: OpenAISemanticIntentConfig) -> Any:
    return OpenAISemanticIntentInterpreter(config, capture_llm_io=True)


def _default_composer(config: OpenAIClarificationComposerConfig) -> Any:
    return OpenAIClarificationPromptComposer(config, capture_llm_io=True)


def _default_selector(config: OpenAIAirportSelectorConfig) -> Any:
    return OpenAIAirportSelector(config, capture_llm_io=True)


def _default_gateway(config: OpenAIGatewayGeneratorConfig) -> Any:
    return OpenAIGatewayGenerator(config, capture_llm_io=True)


def _drain(adapter: Any, usages: list[dict[str, int]], calls: list[dict[str, Any]]) -> None:
    usage = adapter.take_usage()
    if usage is not None:
        usages.append(cast(dict[str, int], usage))
    calls.extend(cast(list[dict[str, Any]], adapter.take_call_traces()))


class _GatewayTraceTee:
    def __init__(self, inner: Any, calls: list[dict[str, Any]]) -> None:
        self.inner, self.calls = inner, calls

    def propose(self, model_input: Any) -> Any:
        return self.inner.propose(model_input)

    def take_usage(self) -> dict[str, int] | None:
        return cast(dict[str, int] | None, self.inner.take_usage())

    def take_call_traces(self) -> list[dict[str, Any]]:
        calls = cast(list[dict[str, Any]], self.inner.take_call_traces())
        self.calls.extend(calls)
        return calls


def _direct(repository: Any, iata: str) -> SelectedAirport | None:
    airport = repository.lookup_airport_iata(iata)
    if airport is None:
        return None
    return SelectedAirport(
        airport_id=airport.airport_id,
        airport_iata=airport.iata,
        airport_evidence_source_ids=airport.source_ids,
    )


def _usage_total(usages: Sequence[Mapping[str, int]]) -> dict[str, int]:
    keys = ("calls", "input_tokens", "output_tokens", "total_tokens")
    return {key: sum(item.get(key, 0) for item in usages) for key in keys}


def _gateway_outbound_date(request: EffectiveRequest) -> GatewayOutboundDateContext:
    """Project the effective outbound window without weakening replay identity."""

    window = request.departure_window
    assert window is not None
    return GatewayOutboundDateContext(
        start=window.start,
        end=window.end,
        timezone=request.context.timezone,
        effective_window_precision=window.precision.value,
    )


def _private_record(
    path: Path,
    *,
    scenario: Mapping[str, Any],
    understanding: Any,
    session: Any,
    selections: Sequence[AirportSelectionRecord],
    gateway: GatewayDiscoveryResult | None,
    planning_result: Any,
    error: Exception | None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "scenario": scenario,
                "understanding": None
                if understanding is None
                else understanding.model_dump(mode="json"),
                "clarification_session": None
                if session is None
                else session.model_dump(mode="json"),
                "airport_selection_records": [item.model_dump(mode="json") for item in selections],
                "gateway_discovery_result": None
                if gateway is None
                else gateway.model_dump(mode="json"),
                "search_planning_result": None
                if planning_result is None
                else planning_result.model_dump(mode="json"),
                "exception": None
                if error is None
                else {"type": type(error).__name__, "message": str(error)},
            },
            indent=2,
        )
        + "\n"
    )


def run_intent_to_search_planning_live_eval(
    *,
    model: str = PINNED_MODEL,
    trials: int = 1,
    corpus_path: Path = DEFAULT_CORPUS,
    catalog_release: Path = DEFAULT_CATALOG,
    private_root: Path = DEFAULT_PRIVATE_ROOT,
    case_ids: Sequence[str] | None = None,
    preflight_only: bool = False,
    intent_factory: Callable[[OpenAISemanticIntentConfig], Any] = _default_intent,
    composer_factory: Callable[[OpenAIClarificationComposerConfig], Any] = _default_composer,
    selector_factory: Callable[[OpenAIAirportSelectorConfig], Any] = _default_selector,
    gateway_factory: Callable[[OpenAIGatewayGeneratorConfig], Any] = _default_gateway,
    repository_factory: Callable[[Path], Any] = CatalogKnowledgeRepository,
) -> dict[str, Any]:
    """Run the active 19-case corpus once, preserving truthful terminal states."""

    if model != PINNED_MODEL:
        raise ValueError(f"all model stages are pinned to {PINNED_MODEL}")
    if trials != 1 or trials > MAX_TRIALS:
        raise ValueError("this diagnostic permits exactly one bounded trial")
    scenarios = _load_corpus(corpus_path)
    known = {str(item["id"]) for item in scenarios}
    requested = tuple(case_ids or ())
    if len(requested) != len(set(requested)) or set(requested) - known:
        raise ValueError("case IDs must be unique members of the active corpus")
    selected = (
        scenarios if not requested else tuple(item for item in scenarios if item["id"] in requested)
    )

    cap_policy = load_default_airport_selection_cap_policy()
    distance_policy = CityAirportDistanceConsistency(
        policy_version="city-airport-distance-consistency-v1"
    )
    market_policy = load_default_planning_market_policy()
    compiler_policy = PlanningPolicy()
    generated_at = datetime.now(UTC).isoformat()
    run_dir = (
        private_root / f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    )
    records: list[dict[str, Any]] = []

    with repository_factory(catalog_release) as repository:
        identities = {
            "catalog": repository.knowledge_receipt.model_dump(mode="json"),
            "airport_selection_policy": [
                cap_policy.policy_version,
                airport_selection_cap_policy_digest(cap_policy),
            ],
            "distance_policy": [
                distance_policy.policy_version,
                airport_selection_distance_policy_digest(distance_policy),
            ],
            "market_policy": [
                market_policy.policy_version,
                planning_market_policy_digest(market_policy),
            ],
        }
        base = {
            "schema_version": EVALUATOR_VERSION,
            "diagnostic_only": True,
            "generated_at": generated_at,
            "preflight_only": preflight_only,
            "models": {
                stage: model
                for stage in ("intent", "clarification_composer", "m2a_selector", "m2b_gateway")
            },
            "corpus": {
                "path": str(corpus_path),
                "contract_version": CONTRACT_VERSION,
                "sha256": CORPUS_SHA256,
                "denominator": 19,
            },
            "selected_case_ids": [item["id"] for item in selected],
            "trials": 1,
            "call_ceiling": {
                "per_case": MAX_CALLS_PER_CASE,
                "selected_total": len(selected) * MAX_CALLS_PER_CASE,
            },
            "identities": identities,
            "compiler_policy": compiler_policy.model_dump(mode="json"),
            "travel_provider_calls": 0,
        }
        if preflight_only:
            return {
                **base,
                "records": [],
                "summary": {"preflight_passed": True, "runs": 0, "mechanically_completed": False},
            }

        run_dir.mkdir(parents=True, exist_ok=False)
        holiday_provider = NagerHolidayProvider()
        for scenario in selected:
            started = perf_counter()
            case_id = str(scenario["id"])
            calls: list[dict[str, Any]] = []
            usages: list[dict[str, int]] = []
            understanding = session = gateway = planning_result = None
            selections: list[AirportSelectionRecord] = []
            bindings: list[SelectionRecordIdBinding] = []
            error: Exception | None = None
            stage = "intent"
            public: dict[str, Any] = {
                "id": case_id,
                "coverage_family": scenario["coverage_family"],
                "trial": 1,
            }
            try:
                intent = intent_factory(OpenAISemanticIntentConfig(model=model))
                try:
                    context = cast(Mapping[str, str], scenario["context"])
                    understanding = understand_request(
                        RawRequest(
                            text=str(scenario["input"]),
                            context=RequestContext(
                                reference_date=date.fromisoformat(context["reference_date"]),
                                timezone=context["timezone"],
                            ),
                        ),
                        intent,
                        holiday_provider=holiday_provider,
                    )
                finally:
                    _drain(intent, usages, calls)
                action, checks, passed = _score_intent(
                    cast(Mapping[str, Any], scenario["oracle"]), understanding
                )
                public.update(
                    intent_action=action,
                    intent_checks=checks,
                    intent_behavior_passed=passed,
                )
                if understanding.outcome is RequestUnderstandingOutcome.PENDING_RETRYABLE:
                    public.update(
                        outcome_class="infrastructure_error",
                        terminal_stage="intent",
                        terminal_outcome="pending_retryable",
                        planning_eligible=False,
                    )
                else:
                    stage = "clarification"
                    composer = composer_factory(OpenAIClarificationComposerConfig(model=model))
                    try:
                        session = start_clarification(
                            understanding, session_id=f"intent-e2e:{case_id}:1", composer=composer
                        )
                    finally:
                        _drain(composer, usages, calls)
                    public["clarification_status"] = session.status.value
                    if session.status is not ClarificationSessionStatus.READY:
                        public.update(
                            outcome_class="behavioral_outcome",
                            terminal_stage="clarification",
                            terminal_outcome=session.status.value,
                            planning_eligible=False,
                        )
                    else:
                        request: EffectiveRequest = session.effective_request
                        stage = "catalog_grounding"
                        origins: list[SelectedAirport] = []
                        destinations: list[SelectedAirport] = []
                        limitation: dict[str, Any] | None = None
                        for role, locations, holder in (
                            ("origin", request.origins, origins),
                            ("destination", request.destinations, destinations),
                        ):
                            for index, location in enumerate(locations):
                                if location.kind is LocationKind.AIRPORT:
                                    direct = _direct(repository, location.value)
                                    if direct is None:
                                        limitation = {
                                            "code": "airport_absent_from_catalog",
                                            "role": role,
                                            "location_index": index,
                                        }
                                        break
                                    holder.append(direct)
                                    continue
                                normalized = normalize_location_alias(location.value)
                                candidates = repository.resolve_entities(location.kind, normalized)
                                if len(candidates) != 1:
                                    limitation = {
                                        "code": "catalog_ambiguity"
                                        if candidates
                                        else "catalog_absence",
                                        "role": role,
                                        "location_index": index,
                                        "candidate_count": len(candidates),
                                    }
                                    break
                                entity = candidates[0]
                                resolution = ResolvedLocation(
                                    location=location,
                                    status=LocationResolutionStatus.RESOLVED,
                                    normalized_alias=normalized,
                                    resolved_entity_id=entity.entity_id,
                                    evidence_source_ids=entity.source_ids,
                                    candidate_ids=(entity.entity_id,),
                                )
                                selector_context = context_for_resolved_location(
                                    resolution, repository
                                )
                                selector = selector_factory(
                                    OpenAIAirportSelectorConfig(
                                        model=model, prompt=REFINED_AIRPORT_SELECTOR_PROMPT
                                    )
                                )
                                stage = "m2a_selector"
                                try:
                                    proposal = selector.propose(
                                        AirportSelectorModelInput.from_context(
                                            selector_context,
                                            cap_policy.applicable_cap_for(selector_context),
                                        )
                                    )
                                    record = validate_airport_selection_proposal(
                                        role=cast(EndpointRole, role),
                                        context=selector_context,
                                        cap_policy=cap_policy,
                                        distance_policy=distance_policy,
                                        proposal=proposal,
                                        model=model,
                                        prompt_version=REFINED_AIRPORT_SELECTOR_PROMPT.version,
                                        repository=repository,
                                    )
                                finally:
                                    _drain(selector, usages, calls)
                                if not record.accepted_airports:
                                    limitation = {
                                        "code": "m2a_no_accepted_airports",
                                        "role": role,
                                        "location_index": index,
                                    }
                                    break
                                selections.append(record)
                                holder.extend(record.accepted_airports)
                                bindings.append(
                                    SelectionRecordIdBinding(
                                        upstream_record_id=f"m2a:{case_id}:{role}:{entity.entity_id}",
                                        record_digest=airport_selection_record_digest(record),
                                    )
                                )
                            if limitation is not None:
                                break
                        if limitation is not None:
                            public.update(
                                outcome_class="behavioral_outcome",
                                terminal_stage="catalog_grounding",
                                terminal_outcome="planning_ineligible",
                                planning_eligible=False,
                                input_limitation=limitation,
                            )
                        else:
                            stage = "m2b_gateway"
                            discovery_input = GatewayDiscoveryInput(
                                origin_endpoints=tuple(origins),
                                destination_endpoints=tuple(destinations),
                                outbound_date=_gateway_outbound_date(request),
                                upstream_selection_record_ids=tuple(
                                    item.upstream_record_id for item in bindings
                                ),
                                upstream_selection_record_digests=tuple(
                                    sorted(item.record_digest for item in bindings)
                                ),
                            )

                            def make_gateway(
                                call_holder: list[dict[str, Any]] = calls,
                            ) -> _GatewayTraceTee:
                                return _GatewayTraceTee(
                                    gateway_factory(OpenAIGatewayGeneratorConfig(model=model)),
                                    call_holder,
                                )

                            gateway = discover_gateway_candidates(
                                discovery_input=discovery_input,
                                policy=market_policy,
                                repository=repository,
                                generator_factory=make_gateway,
                                generator_configuration=GatewayDiscoveryGeneratorConfiguration(
                                    model=model,
                                    prompt_version=DEFAULT_GATEWAY_GENERATOR_PROMPT.version,
                                    response_schema_sha256=GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
                                    adapter_version=GATEWAY_GENERATOR_ADAPTER_VERSION,
                                ),
                            )
                            if (
                                replay_gateway_discovery_result(
                                    record=gateway, policy=market_policy, repository=repository
                                )
                                != gateway
                                or gateway.result_digest != gateway_discovery_result_digest(gateway)
                            ):
                                raise RuntimeError(
                                    "M2B immutable replay or digest reconciliation failed"
                                )
                            stage = "m2c_compile"
                            envelope = PlanningInputEnvelope(
                                source=PlanningSource(
                                    session_id=session.session_id,
                                    revision=session.current_revision.revision,
                                ),
                                effective_request=request,
                            )
                            compiler_input = SearchPlanningInput(
                                envelope=envelope,
                                endpoint_source=M2ASelectionRecordSource(
                                    selection_records=tuple(selections)
                                )
                                if selections
                                else DirectGroundingSource(),
                                upstream_selection_id_bindings=tuple(bindings),
                                gateway_discovery_result=gateway,
                            )
                            kwargs: dict[str, Any] = {
                                "policy": compiler_policy,
                                "repository": repository,
                                "market_policy": market_policy,
                            }
                            if selections:
                                kwargs.update(
                                    selection_cap_policy=cap_policy,
                                    selection_distance_policy=distance_policy,
                                )
                            planning_result = plan_searches(compiler_input, **kwargs)
                            if planning_result.plan is None:
                                raise RuntimeError("M2C compile did not produce a plan")
                            source_bundle_path = run_dir / f"{case_id}__trial-1__source-bundle.json"
                            source_bundle_path.write_text(
                                json.dumps(
                                    {
                                        "effective_request": request.model_dump(mode="json"),
                                        "session_id": session.session_id,
                                        "revision": session.current_revision.revision,
                                        "airport_selection_records": [
                                            item.model_dump(mode="json") for item in selections
                                        ],
                                        "selection_bindings": [
                                            item.model_dump(mode="json") for item in bindings
                                        ],
                                        "gateway_discovery_result": gateway.model_dump(mode="json"),
                                        "trusted_compilation_binding_digest": planning_result.plan.identity.compilation_binding_digest,
                                    },
                                    indent=2,
                                )
                                + "\n"
                            )
                            loaded = json.loads(source_bundle_path.read_text())
                            replay_request = EffectiveRequest.model_validate(
                                loaded["effective_request"]
                            )
                            replay_selections = tuple(
                                AirportSelectionRecord.model_validate(item)
                                for item in loaded["airport_selection_records"]
                            )
                            replay_bindings = tuple(
                                SelectionRecordIdBinding.model_validate(item)
                                for item in loaded["selection_bindings"]
                            )
                            replay_gateway = GatewayDiscoveryResult.model_validate(
                                loaded["gateway_discovery_result"]
                            )
                            replay_input = SearchPlanningInput(
                                envelope=PlanningInputEnvelope(
                                    source=PlanningSource(
                                        session_id=loaded["session_id"],
                                        revision=loaded["revision"],
                                    ),
                                    effective_request=replay_request,
                                ),
                                endpoint_source=M2ASelectionRecordSource(
                                    selection_records=replay_selections
                                )
                                if replay_selections
                                else DirectGroundingSource(),
                                upstream_selection_id_bindings=replay_bindings,
                                gateway_discovery_result=replay_gateway,
                            )
                            replay = plan_searches(replay_input, **kwargs)
                            if replay != planning_result:
                                raise RuntimeError(
                                    "M2C compile/replay did not produce one stable plan"
                                )
                            assert replay.plan is not None
                            handoff = check_plan_handoff(
                                replay.plan,
                                current_session_id=loaded["session_id"],
                                current_revision=loaded["revision"],
                                current_effective_request=replay_request,
                                expected_compilation_binding_digest=loaded[
                                    "trusted_compilation_binding_digest"
                                ],
                            )
                            if (
                                handoff.status is not PlanHandoffStatus.CURRENT
                                or not handoff.executable
                            ):
                                raise RuntimeError("M2C handoff was not current and executable")
                            public.update(
                                outcome_class="behavioral_outcome",
                                terminal_stage="m2c_handoff",
                                terminal_outcome=planning_result.outcome.value,
                                planning_eligible=True,
                                m2a={
                                    "record_count": len(selections),
                                    "origin_airports": [item.airport_iata for item in origins],
                                    "destination_airports": [
                                        item.airport_iata for item in destinations
                                    ],
                                },
                                m2b={
                                    "outcome": gateway.outcome.value,
                                    "market_coverage": gateway.market_coverage.value,
                                    "result_digest": gateway.result_digest,
                                },
                                m2c={
                                    "outcome": planning_result.outcome.value,
                                    "plan_digest": planning_result.plan.plan_digest,
                                    "logical_queries": len(planning_result.plan.logical_queries),
                                    "mandatory_complete": planning_result.plan.coverage.mandatory_complete,
                                },
                                handoff={
                                    "status": handoff.status.value,
                                    "executable": handoff.executable,
                                },
                            )
            except Exception as exc:  # noqa: BLE001 - diagnostic continues; detail is private
                error = exc
                public.update(
                    outcome_class="connector_or_harness_error"
                    if stage in {"intent", "clarification", "m2a_selector", "m2b_gateway"}
                    else "harness_error",
                    terminal_stage=stage,
                    terminal_outcome="error",
                    error_type=type(exc).__name__,
                )
            total_usage = _usage_total(usages)
            # M2B owns its usage receipt, while the tee owns its raw trace.
            if (
                gateway is not None
                and gateway.generator_invocation is not None
                and gateway.generator_invocation.usage is not None
            ):
                gateway_usage = cast(Mapping[str, int], gateway.generator_invocation.usage)
                total_usage = _usage_total((total_usage, gateway_usage))
            attempted = total_usage["calls"]
            public.update(
                latency_seconds=round(perf_counter() - started, 3),
                usage=total_usage,
                trace_reconciliation={
                    "attempted_calls": attempted,
                    "private_trace_calls": len(calls),
                    "within_ceiling": attempted <= MAX_CALLS_PER_CASE,
                    "reconciled": attempted == len(calls) and attempted <= MAX_CALLS_PER_CASE,
                },
            )
            trace_path = write_eval_llm_trace(
                run_dir, scenario=scenario, record=public, calls=calls
            )
            private_path = trace_path.with_name(f"{trace_path.stem}__records.json")
            _private_record(
                private_path,
                scenario=scenario,
                understanding=understanding,
                session=session,
                selections=selections,
                gateway=gateway,
                planning_result=planning_result,
                error=error,
            )
            records.append(public)

    infrastructure = sum(item["outcome_class"] != "behavioral_outcome" for item in records)
    intent_passes = sum(bool(item.get("intent_behavior_passed")) for item in records)
    return {
        **base,
        "records": records,
        "summary": {
            "preflight_passed": True,
            "runs": len(records),
            "intent_behavior_passes": intent_passes,
            "intent_behavior_denominator": len(records),
            "behavioral_outcomes": len(records) - infrastructure,
            "infrastructure_or_harness_errors": infrastructure,
            "planning_eligible": sum(bool(item.get("planning_eligible")) for item in records),
            "trace_reconciled": sum(
                bool(item["trace_reconciliation"]["reconciled"]) for item in records
            ),
            "attempted_calls": sum(
                item["trace_reconciliation"]["attempted_calls"] for item in records
            ),
            "mechanically_completed": infrastructure == 0
            and all(item["trace_reconciliation"]["reconciled"] for item in records),
            "semantic_qualification": "not_claimed_manual_review_required",
        },
    }
