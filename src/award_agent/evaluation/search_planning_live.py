"""Bounded integrated M2A -> M2B -> M2C development evaluation.

The casebook and every local evidence identity are preflighted before an OpenAI
adapter is constructed.  Public results contain only redacted summaries;
complete typed records, raw model traces, and exception messages are written to
ignored private sidecars.  This module never constructs a travel-provider
client and M2C is replayed from the exact same immutable M2A/M2B records.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

import yaml

from award_agent.clarification import (
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationComposerConfig,
    OpenAIClarificationInterpreterConfig,
    OpenAIClarificationPromptComposer,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.domain import (
    CabinClass,
    ClarificationAnswerCommand,
    ClarificationSessionStatus,
    EffectiveRequest,
    LocationKind,
    RawRequest,
    RequestContext,
    SearchMode,
)
from award_agent.intent import (
    OpenAISemanticIntentConfig,
    OpenAISemanticIntentInterpreter,
    understand_request,
)
from award_agent.observability.llm_trace import write_eval_llm_trace
from award_agent.search_planning.airport_selection_policy import (
    AirportSelectionCapPolicy,
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
from award_agent.search_planning.capabilities import (
    CachedSearchCapability,
    capability_content_digest,
    load_default_cached_search_capability,
    verify_capability_source_artifacts,
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
    PlanningMarketPolicy,
    load_default_planning_market_policy,
    planning_market_policy_digest,
)
from award_agent.search_planning.planner import plan_searches
from award_agent.search_planning.policy import PlanningPolicy

DEFAULT_SEARCH_PLANNING_LIVE_CASEBOOK = Path("evals/search_planning_live/casebook-v1.yaml")
DEFAULT_SEARCH_PLANNING_LIVE_TRACE_DIR = Path("evals/search_planning_live/traces-live")
DEFAULT_SEARCH_PLANNING_LIVE_CATALOG = Path("data/search_planning/catalogs/m1a-3cb7981519612945")
SEARCH_PLANNING_LIVE_EVALUATOR_VERSION = "search_planning_live_eval_v1"
_CONTRACT_VERSION = "search-planning-live-casebook-v1"


class SearchPlanningLiveFixtureError(ValueError):
    """The integrated casebook or one of its pinned evidence identities drifted."""


def _mapping(value: object, *, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise SearchPlanningLiveFixtureError(f"{label} has an invalid shape")
    return value


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_casebook(path: Path) -> tuple[tuple[Mapping[str, Any], ...], Mapping[str, Any]]:
    try:
        raw = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise SearchPlanningLiveFixtureError("unable to load integrated casebook") from exc
    top = _mapping(
        raw,
        keys={
            "contract_version",
            "development_only",
            "casebook_id",
            "catalog",
            "airport_selection_policy",
            "distance_policy",
            "market_policy",
            "capability",
            "live_bounds",
            "cases",
        },
        label="integrated casebook",
    )
    if (
        top["contract_version"] != _CONTRACT_VERSION
        or top["development_only"] is not True
        or top["casebook_id"] != "m2a_m2b_m2c_integrated_development_v1"
    ):
        raise SearchPlanningLiveFixtureError("casebook identity is not integrated v1")
    for name, keys in (
        ("catalog", {"release_id", "logical_content_sha256"}),
        ("airport_selection_policy", {"version", "digest"}),
        ("distance_policy", {"version", "digest"}),
        ("market_policy", {"version", "digest"}),
        ("capability", {"id", "version", "digest"}),
        (
            "live_bounds",
            {
                "intent_model",
                "clarification_model",
                "selector_model",
                "gateway_model",
                "max_trials",
                "max_calls_per_trial",
                "max_calls_total",
            },
        ),
    ):
        _mapping(top[name], keys=keys, label=name)
    cases = top["cases"]
    if not isinstance(cases, list) or not cases:
        raise SearchPlanningLiveFixtureError("casebook requires cases")
    ids: set[str] = set()
    normalized: list[Mapping[str, Any]] = []
    expected_case_keys = {
        "id",
        "review_focus",
        "raw_request",
        "reference_date",
        "clarification_answers",
        "expected_trajectory",
        "origins",
        "destinations",
        "departure",
        "travelers",
        "cabins",
        "positioning_allowed",
        "gateway_call_possible",
    }
    for raw_case in cases:
        case = _mapping(raw_case, keys=expected_case_keys, label="case")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise SearchPlanningLiveFixtureError("case IDs must be unique non-empty strings")
        ids.add(case_id)
        _validate_locations(case["origins"], label=f"{case_id} origins")
        _validate_locations(case["destinations"], label=f"{case_id} destinations")
        departure = _mapping(
            case["departure"], keys={"start", "end", "timezone"}, label="departure"
        )
        try:
            start, end = (
                date.fromisoformat(str(departure["start"])),
                date.fromisoformat(str(departure["end"])),
            )
            RequestContext(reference_date=date(2026, 9, 19), timezone=departure["timezone"])
        except (TypeError, ValueError) as exc:
            raise SearchPlanningLiveFixtureError("case departure is invalid") from exc
        if end < start or (end - start).days + 1 > 31:
            raise SearchPlanningLiveFixtureError("case departure must be a bounded 31-day window")
        if not isinstance(case["gateway_call_possible"], bool):
            raise SearchPlanningLiveFixtureError("gateway_call_possible must be boolean")
        if not isinstance(case["raw_request"], str) or not case["raw_request"].strip():
            raise SearchPlanningLiveFixtureError("raw_request must be non-empty")
        if (
            not isinstance(case["review_focus"], str)
            or not case["review_focus"].strip()
            or not isinstance(case["travelers"], int)
            or isinstance(case["travelers"], bool)
            or case["travelers"] < 1
            or not isinstance(case["cabins"], list)
            or not case["cabins"]
            or any(item not in {cabin.value for cabin in CabinClass} for item in case["cabins"])
            or case["positioning_allowed"] not in {True, False, None}
        ):
            raise SearchPlanningLiveFixtureError("case planning expectations are invalid")
        try:
            date.fromisoformat(str(case["reference_date"]))
        except ValueError as exc:
            raise SearchPlanningLiveFixtureError("reference_date is invalid") from exc
        if not isinstance(case["clarification_answers"], list) or any(
            not isinstance(item, str) or not item.strip() for item in case["clarification_answers"]
        ):
            raise SearchPlanningLiveFixtureError("clarification answers must be non-empty strings")
        if case["expected_trajectory"] not in {"plan", "upstream_blocked"}:
            raise SearchPlanningLiveFixtureError("expected trajectory is invalid")
        normalized.append(case)
    return tuple(normalized), top


def _validate_locations(value: object, *, label: str) -> None:
    if not isinstance(value, list) or not value:
        raise SearchPlanningLiveFixtureError(f"{label} must be a non-empty list")
    for location in value:
        if not isinstance(location, Mapping) or set(location) not in (
            {"kind", "value"},
            {"kind", "value", "entity_id"},
        ):
            raise SearchPlanningLiveFixtureError(f"{label} location has invalid shape")
        if location["kind"] not in {item.value for item in LocationKind}:
            raise SearchPlanningLiveFixtureError(f"{label} location kind is invalid")
        geographic = location["kind"] != LocationKind.AIRPORT.value
        if geographic != ("entity_id" in location):
            raise SearchPlanningLiveFixtureError(
                f"{label} geographic locations require an entity ID"
            )


def load_search_planning_live_cases(
    path: Path = DEFAULT_SEARCH_PLANNING_LIVE_CASEBOOK,
) -> tuple[Mapping[str, Any], ...]:
    """Validate and return public case definitions without constructing adapters."""

    return _load_casebook(path)[0]


class _GatewayTraceTee:
    def __init__(self, inner: Any, holder: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._holder = holder

    def propose(self, model_input: Any) -> Any:
        return self._inner.propose(model_input)

    def take_usage(self) -> dict[str, int] | None:
        return cast(dict[str, int] | None, self._inner.take_usage())

    def take_call_traces(self) -> list[dict[str, Any]]:
        calls = cast(list[dict[str, Any]], self._inner.take_call_traces())
        self._holder.extend(calls)
        return calls


def _default_selector_factory(config: OpenAIAirportSelectorConfig) -> OpenAIAirportSelector:
    return OpenAIAirportSelector(config, capture_llm_io=True)


def _default_gateway_factory(config: OpenAIGatewayGeneratorConfig) -> OpenAIGatewayGenerator:
    return OpenAIGatewayGenerator(config, capture_llm_io=True)


def _default_intent_factory(config: OpenAISemanticIntentConfig) -> OpenAISemanticIntentInterpreter:
    return OpenAISemanticIntentInterpreter(config, capture_llm_io=True)


def _default_composer_factory(
    config: OpenAIClarificationComposerConfig,
) -> OpenAIClarificationPromptComposer:
    return OpenAIClarificationPromptComposer(config, capture_llm_io=True)


def _default_clarification_factory(
    config: OpenAIClarificationInterpreterConfig,
) -> OpenAIClarificationAnswerInterpreter:
    return OpenAIClarificationAnswerInterpreter(config, capture_llm_io=True)


def _calls_per_trial(cases: Sequence[Mapping[str, Any]]) -> int:
    # Intent and clarification interpreters each have one bounded repair call.
    intent_calls = len(cases) * 2
    selector_calls = sum(
        location["kind"] != "airport"
        for case in cases
        for side in ("origins", "destinations")
        for location in case[side]
    )
    gateway_calls = sum(bool(case["gateway_call_possible"]) for case in cases)
    clarification_calls = sum(
        (1 + len(case["clarification_answers"])) + 2 * len(case["clarification_answers"])
        for case in cases
        if case["clarification_answers"]
    )
    return cast(int, intent_calls + selector_calls + gateway_calls + clarification_calls)


class _UpstreamBlocked(RuntimeError):
    pass


def _drain_adapter(
    adapter: Any,
    *,
    usages: list[dict[str, int] | None],
    calls: list[dict[str, Any]],
) -> None:
    usages.append(cast(dict[str, int] | None, adapter.take_usage()))
    calls.extend(cast(list[dict[str, Any]], adapter.take_call_traces()))


def _validate_effective(case: Mapping[str, Any], request: EffectiveRequest) -> None:
    departure = cast(Mapping[str, Any], case["departure"])
    expected_origins = tuple((item["kind"], item["value"]) for item in case["origins"])
    expected_destinations = tuple((item["kind"], item["value"]) for item in case["destinations"])
    actual_origins = tuple((item.kind.value, item.value) for item in request.origins)
    actual_destinations = tuple((item.kind.value, item.value) for item in request.destinations)
    if actual_origins != expected_origins or actual_destinations != expected_destinations:
        raise _UpstreamBlocked("request-understanding endpoints differ from the reviewed case")
    if (
        request.travelers != case["travelers"]
        or request.departure_window is None
        or request.departure_window.start != date.fromisoformat(str(departure["start"]))
        or request.departure_window.end != date.fromisoformat(str(departure["end"]))
        or request.cabins != tuple(CabinClass(item) for item in case["cabins"])
        or request.repositioning_allowed != case["positioning_allowed"]
        or SearchMode.AWARD not in request.search_modes
    ):
        raise _UpstreamBlocked("ready request differs from the reviewed planning input")


def _accepted_relationship_count(gateway: GatewayDiscoveryResult) -> int:
    origin_access = sum(
        len(item.supported_original_origin_iata_codes)
        * len(item.applicable_original_destination_iata_codes)
        for item in gateway.accepted_origin_access_gateways
    )
    destination_access = sum(
        len(item.supported_original_destination_iata_codes)
        * len(item.applicable_original_origin_iata_codes)
        for item in gateway.accepted_destination_access_gateways
    )
    hubs = sum(
        len(scope.expanded_original_origin_iata_codes)
        * len(scope.expanded_original_destination_iata_codes)
        for item in gateway.accepted_intermediate_hubs
        for scope in item.scopes
    )
    return origin_access + destination_access + hubs


def _write_source_bundle(
    path: Path,
    *,
    request: EffectiveRequest,
    session_id: str,
    revision: int,
    selections: Sequence[AirportSelectionRecord],
    bindings: Sequence[SelectionRecordIdBinding],
    gateway: GatewayDiscoveryResult,
    compilation_binding_digest: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "effective_request": request.model_dump(mode="json"),
                "session_id": session_id,
                "revision": revision,
                "airport_selection_records": [item.model_dump(mode="json") for item in selections],
                "selection_bindings": [item.model_dump(mode="json") for item in bindings],
                "gateway_discovery_result": gateway.model_dump(mode="json"),
                "trusted_compilation_binding_digest": compilation_binding_digest,
            },
            indent=2,
        )
        + "\n"
    )


def _selected_direct(repository: Any, iata: str) -> SelectedAirport:
    airport = repository.lookup_airport_iata(iata)
    if airport is None:
        raise SearchPlanningLiveFixtureError(f"direct airport {iata} is absent from catalog")
    return SelectedAirport(
        airport_id=airport.airport_id,
        airport_iata=airport.iata,
        airport_evidence_source_ids=airport.source_ids,
    )


def _record_id(case_id: str, role: str, entity_id: str) -> str:
    return f"m2a:{case_id}:{role}:{entity_id}"


def _public_plan_summary(result: Any) -> dict[str, Any]:
    plan = result.plan
    if plan is None:
        return {
            "outcome": result.outcome.value,
            "issue_codes": [str(item.code) for item in result.issues],
        }
    return {
        "outcome": result.outcome.value,
        "plan_digest": plan.plan_digest,
        "mandatory_pairs": plan.coverage.mandatory_required_pairs,
        "mandatory_complete": plan.coverage.mandatory_complete,
        "accepted_relationships": plan.coverage.accepted_relationships,
        "admitted_relationships": plan.coverage.admitted_relationships,
        "omitted_budget_relationships": plan.coverage.omitted_budget_relationships,
        "suppressed_positioning_relationships": (
            plan.coverage.suppressed_positioning_refusal_relationships
        ),
        "unsupported_relationships": plan.coverage.unsupported_rule_relationships,
        "unique_queries": len(plan.logical_queries),
        "query_date_days": next(
            item.observed for item in plan.budget_receipts if item.kind.value == "query_date_days"
        ),
        "unresolved_obligations": len(plan.constraint_obligations),
        "mapping_gap": "gaps" in plan.discovery_receipt.market_coverage.value,
    }


def _write_private(
    trace_path: Path,
    *,
    request: EffectiveRequest | None,
    selections: Sequence[AirportSelectionRecord],
    gateway: GatewayDiscoveryResult | None,
    planning_result: Any | None,
    exception: Exception | None,
) -> Path:
    path = trace_path.with_name(f"{trace_path.stem}__records.json")
    path.write_text(
        json.dumps(
            {
                "effective_request": None if request is None else request.model_dump(mode="json"),
                "airport_selection_records": [item.model_dump(mode="json") for item in selections],
                "gateway_discovery_result": (
                    None if gateway is None else gateway.model_dump(mode="json")
                ),
                "search_planning_result": (
                    None if planning_result is None else planning_result.model_dump(mode="json")
                ),
                "exception": (
                    None
                    if exception is None
                    else {"type": type(exception).__name__, "message": str(exception)}
                ),
            },
            indent=2,
        )
        + "\n"
    )
    return path


def run_search_planning_live_eval(
    *,
    intent_model: str = "gpt-5.6-luna",
    clarification_model: str = "gpt-5.6-luna",
    selector_model: str = "gpt-5.6-luna",
    gateway_model: str = "gpt-5.6-luna",
    trials: int = 2,
    casebook_path: Path = DEFAULT_SEARCH_PLANNING_LIVE_CASEBOOK,
    catalog_release: Path = DEFAULT_SEARCH_PLANNING_LIVE_CATALOG,
    trace_dir: Path = DEFAULT_SEARCH_PLANNING_LIVE_TRACE_DIR,
    case_ids: Sequence[str] | None = None,
    preflight_only: bool = False,
    intent_factory: Callable[[OpenAISemanticIntentConfig], Any] = _default_intent_factory,
    composer_factory: Callable[
        [OpenAIClarificationComposerConfig], Any
    ] = _default_composer_factory,
    clarification_factory: Callable[
        [OpenAIClarificationInterpreterConfig], Any
    ] = _default_clarification_factory,
    selector_factory: Callable[[OpenAIAirportSelectorConfig], Any] = _default_selector_factory,
    gateway_factory: Callable[[OpenAIGatewayGeneratorConfig], Any] = _default_gateway_factory,
    repository_factory: Callable[[Path], Any] = CatalogKnowledgeRepository,
    cap_policy: AirportSelectionCapPolicy | None = None,
    distance_policy: CityAirportDistanceConsistency | None = None,
    market_policy: PlanningMarketPolicy | None = None,
    capability: CachedSearchCapability | None = None,
    compiler_policy: PlanningPolicy | None = None,
) -> dict[str, Any]:
    """Run a bounded integrated diagnostic or only its no-adapter preflight."""

    cases, casebook = _load_casebook(casebook_path)
    bounds = cast(Mapping[str, Any], casebook["live_bounds"])
    if trials < 1 or trials > bounds["max_trials"]:
        raise ValueError("trials exceed the reviewed casebook bound")
    if (
        intent_model != bounds["intent_model"]
        or clarification_model != bounds["clarification_model"]
        or selector_model != bounds["selector_model"]
        or gateway_model != bounds["gateway_model"]
    ):
        raise ValueError("models must match the reviewed casebook")
    all_calls = _calls_per_trial(cases)
    if all_calls > bounds["max_calls_per_trial"] or all_calls * trials > bounds["max_calls_total"]:
        raise SearchPlanningLiveFixtureError("full casebook call plan exceeds reviewed bounds")
    known_ids = {str(case["id"]) for case in cases}
    requested_ids = tuple(case_ids or ())
    if len(requested_ids) != len(set(requested_ids)) or set(requested_ids) - known_ids:
        raise ValueError("case IDs must be unique and present in the casebook")
    selected = (
        cases if not requested_ids else tuple(case for case in cases if case["id"] in requested_ids)
    )

    cap_policy = cap_policy or load_default_airport_selection_cap_policy()
    distance_policy = distance_policy or CityAirportDistanceConsistency(
        policy_version="city-airport-distance-consistency-v1"
    )
    market_policy = market_policy or load_default_planning_market_policy()
    capability = capability or load_default_cached_search_capability()
    compiler_policy = compiler_policy or PlanningPolicy()
    verify_capability_source_artifacts(capability)
    identities = {
        "airport_selection_policy": (
            cap_policy.policy_version,
            airport_selection_cap_policy_digest(cap_policy),
        ),
        "distance_policy": (
            distance_policy.policy_version,
            airport_selection_distance_policy_digest(distance_policy),
        ),
        "market_policy": (
            market_policy.policy_version,
            planning_market_policy_digest(market_policy),
        ),
        "capability": (
            capability.capability_id,
            capability.capability_version,
            capability_content_digest(capability),
        ),
    }
    expected_identities = {
        name: tuple(cast(Mapping[str, Any], casebook[name]).values())
        for name in (
            "airport_selection_policy",
            "distance_policy",
            "market_policy",
            "capability",
        )
    }
    if identities != expected_identities:
        raise SearchPlanningLiveFixtureError("casebook policy or capability identity drifted")

    generated_at = datetime.now(UTC).isoformat()
    run_dir = trace_dir / f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    records: list[dict[str, Any]] = []
    with repository_factory(catalog_release) as repository:
        receipt = repository.knowledge_receipt
        catalog_pin = cast(Mapping[str, Any], casebook["catalog"])
        if (
            receipt.release_id != catalog_pin["release_id"]
            or receipt.logical_content_sha256 != catalog_pin["logical_content_sha256"]
        ):
            raise SearchPlanningLiveFixtureError("casebook catalog identity drifted")
        # Resolve every geographic entity before any model adapter is reachable.
        for case in cases:
            for role in ("origins", "destinations"):
                for item in case[role]:
                    if item["kind"] == "airport":
                        _selected_direct(repository, item["value"])
                    else:
                        entity = repository.get_entity(item["entity_id"])
                        if entity is None or entity.label != item["value"]:
                            raise SearchPlanningLiveFixtureError("casebook entity identity drifted")
                        candidates = repository.resolve_entities(
                            LocationKind(item["kind"]),
                            normalize_location_alias(item["value"]),
                        )
                        if (
                            len(candidates) != 1
                            or candidates[0].entity_id != item["entity_id"]
                        ):
                            raise SearchPlanningLiveFixtureError(
                                "casebook geographic location is not one unambiguous catalog entity"
                            )
        selected_calls = _calls_per_trial(selected) * trials
        base = {
            "schema_version": SEARCH_PLANNING_LIVE_EVALUATOR_VERSION,
            "diagnostic_only": True,
            "generated_at": generated_at,
            "preflight_only": preflight_only,
            "full_run": not requested_ids,
            "run_kind": "preflight"
            if preflight_only
            else ("full" if not requested_ids else "smoke_partial"),
            "models": {
                "intent": intent_model,
                "clarification": clarification_model,
                "selector": selector_model,
                "gateway_generator": gateway_model,
            },
            "casebook": {
                "path": str(casebook_path),
                "sha256": _sha(casebook_path),
                "contract_version": _CONTRACT_VERSION,
                "case_count": len(cases),
            },
            "selected_case_ids": [case["id"] for case in selected],
            "trials": trials,
            "call_plan": {
                "full_casebook_per_trial": all_calls,
                "selected_total": selected_calls,
                "maximum_total": bounds["max_calls_total"],
            },
            "catalog": receipt.model_dump(mode="json"),
            "identities": {name: list(value) for name, value in identities.items()},
            "compiler_policy": compiler_policy.model_dump(mode="json"),
        }
        if preflight_only:
            return {
                **base,
                "records": [],
                "summary": {
                    "preflight_passed": True,
                    "planned_calls": selected_calls,
                    "attempted_calls": 0,
                    "mechanically_completed": False,
                    "semantic_qualification": "not_claimed_manual_review_required",
                },
            }

        remaining_call_reservations = selected_calls
        for trial in range(1, trials + 1):
            for case in selected:
                started = perf_counter()
                case_reservation = _calls_per_trial((case,))
                if case_reservation > remaining_call_reservations:
                    raise SearchPlanningLiveFixtureError(
                        "call ceiling exhausted before adapter construction"
                    )
                remaining_call_reservations -= case_reservation
                request: EffectiveRequest | None = None
                envelope: PlanningInputEnvelope | None = None
                selection_records: list[AirportSelectionRecord] = []
                bindings: list[SelectionRecordIdBinding] = []
                origins: list[SelectedAirport] = []
                destinations: list[SelectedAirport] = []
                raw_calls: list[dict[str, Any]] = []
                all_usage: list[dict[str, int] | None] = []
                gateway: GatewayDiscoveryResult | None = None
                planning_result: Any | None = None
                exception: Exception | None = None
                gateway_constructed = False
                public: dict[str, Any] = {
                    "id": case["id"],
                    "trial": trial,
                    "expected_trajectory": case["expected_trajectory"],
                }
                try:
                    intent = intent_factory(OpenAISemanticIntentConfig(model=intent_model))
                    try:
                        understanding = understand_request(
                            RawRequest(
                                text=case["raw_request"],
                                context=RequestContext(
                                    reference_date=date.fromisoformat(str(case["reference_date"])),
                                    timezone=cast(Mapping[str, Any], case["departure"])["timezone"],
                                ),
                            ),
                            intent,
                        )
                    finally:
                        _drain_adapter(intent, usages=all_usage, calls=raw_calls)
                    session_id = f"live:{case['id']}:{trial}"
                    answers = cast(Sequence[str], case["clarification_answers"])
                    if (
                        understanding.clarification is not None
                        and understanding.clarification.action.value == "ask"
                        and not answers
                    ):
                        raise _UpstreamBlocked(
                            "request understanding requires an unconfigured clarification"
                        )
                    composer: Any | None = None
                    if answers:
                        composer = composer_factory(
                            OpenAIClarificationComposerConfig(model=clarification_model)
                        )
                    try:
                        session = start_clarification(
                            understanding, session_id=session_id, composer=composer
                        )
                        if session.status is ClarificationSessionStatus.AWAITING_ANSWER:
                            if not answers:
                                raise _UpstreamBlocked(
                                    "clarification required but no answer supplied"
                                )
                            clarifier = clarification_factory(
                                OpenAIClarificationInterpreterConfig(model=clarification_model)
                            )
                            try:
                                for answer_index, answer in enumerate(answers, start=1):
                                    prompt = session.current_revision.prompt
                                    if prompt is None:
                                        break
                                    transition = apply_clarification_answer(
                                        session,
                                        ClarificationAnswerCommand(
                                            session_id=session.session_id,
                                            expected_revision=session.current_revision.revision,
                                            prompt_id=prompt.prompt_id,
                                            message_id=(
                                                f"{case['id']}:{trial}:answer:{answer_index}"
                                            ),
                                            text=answer,
                                        ),
                                        clarifier,
                                        composer=composer,
                                    )
                                    session = transition.session
                            finally:
                                _drain_adapter(clarifier, usages=all_usage, calls=raw_calls)
                    finally:
                        if composer is not None:
                            _drain_adapter(composer, usages=all_usage, calls=raw_calls)
                    if session.status is not ClarificationSessionStatus.READY:
                        raise _UpstreamBlocked(
                            f"request did not reach ready state: {session.status.value}"
                        )
                    request = session.effective_request
                    _validate_effective(case, request)
                    envelope = PlanningInputEnvelope(
                        source=PlanningSource(
                            session_id=session.session_id,
                            revision=session.current_revision.revision,
                        ),
                        effective_request=request,
                    )
                    for role, holder in (("origin", origins), ("destination", destinations)):
                        side = "origins" if role == "origin" else "destinations"
                        request_locations = (
                            request.origins if role == "origin" else request.destinations
                        )
                        for location_index, location in enumerate(case[side]):
                            if location["kind"] == "airport":
                                holder.append(_selected_direct(repository, location["value"]))
                                continue
                            entity = repository.get_entity(location["entity_id"])
                            assert entity is not None
                            request_location = request_locations[location_index]
                            normalized = normalize_location_alias(request_location.value)
                            candidates = repository.resolve_entities(
                                request_location.kind, normalized
                            )
                            chosen = tuple(
                                item
                                for item in candidates
                                if item.entity_id == location["entity_id"]
                            )
                            if len(chosen) != 1:
                                raise RuntimeError(
                                    "reviewed entity is not exactly one catalog alias candidate"
                                )
                            resolution = ResolvedLocation(
                                location=request_location,
                                status=LocationResolutionStatus.RESOLVED,
                                normalized_alias=normalized,
                                resolved_entity_id=entity.entity_id,
                                evidence_source_ids=chosen[0].source_ids,
                                candidate_ids=tuple(item.entity_id for item in candidates),
                            )
                            context = context_for_resolved_location(resolution, repository)
                            cap = cap_policy.applicable_cap_for(context)
                            selector = selector_factory(
                                OpenAIAirportSelectorConfig(
                                    model=selector_model, prompt=REFINED_AIRPORT_SELECTOR_PROMPT
                                )
                            )
                            try:
                                proposal = selector.propose(
                                    AirportSelectorModelInput.from_context(context, cap)
                                )
                                selection = validate_airport_selection_proposal(
                                    role=cast(EndpointRole, role),
                                    context=context,
                                    cap_policy=cap_policy,
                                    distance_policy=distance_policy,
                                    proposal=proposal,
                                    model=selector_model,
                                    prompt_version=REFINED_AIRPORT_SELECTOR_PROMPT.version,
                                    repository=repository,
                                )
                            finally:
                                _drain_adapter(selector, usages=all_usage, calls=raw_calls)
                            if not selection.accepted_airports:
                                raise RuntimeError("selector produced no accepted endpoint")
                            selection_records.append(selection)
                            holder.extend(selection.accepted_airports)
                            digest = airport_selection_record_digest(selection)
                            bindings.append(
                                SelectionRecordIdBinding(
                                    upstream_record_id=_record_id(
                                        str(case["id"]), role, context.entity_id
                                    ),
                                    record_digest=digest,
                                )
                            )
                    binding_digests = tuple(sorted(item.record_digest for item in bindings))
                    discovery_input = GatewayDiscoveryInput(
                        origin_endpoints=tuple(origins),
                        destination_endpoints=tuple(destinations),
                        outbound_date=GatewayOutboundDateContext(
                            start=cast(Mapping[str, Any], case["departure"])["start"],
                            end=cast(Mapping[str, Any], case["departure"])["end"],
                            timezone=cast(Mapping[str, Any], case["departure"])["timezone"],
                            effective_window_precision="window",
                        ),
                        upstream_selection_record_ids=tuple(
                            item.upstream_record_id for item in bindings
                        ),
                        upstream_selection_record_digests=binding_digests,
                    )

                    def make_gateway(
                        holder: list[dict[str, Any]] = raw_calls,
                        gateway_allowed: bool = bool(case["gateway_call_possible"]),
                    ) -> _GatewayTraceTee:
                        nonlocal gateway_constructed
                        if not gateway_allowed:
                            raise RuntimeError("actual market gate has no reserved gateway call")
                        gateway_constructed = True
                        return _GatewayTraceTee(
                            gateway_factory(OpenAIGatewayGeneratorConfig(model=gateway_model)),
                            holder,
                        )

                    gateway = discover_gateway_candidates(
                        discovery_input=discovery_input,
                        policy=market_policy,
                        repository=repository,
                        generator_factory=make_gateway,
                        generator_configuration=GatewayDiscoveryGeneratorConfiguration(
                            model=gateway_model,
                            prompt_version=DEFAULT_GATEWAY_GENERATOR_PROMPT.version,
                            response_schema_sha256=GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
                            adapter_version=GATEWAY_GENERATOR_ADAPTER_VERSION,
                        ),
                    )
                    replayed_gateway = replay_gateway_discovery_result(
                        record=gateway, policy=market_policy, repository=repository
                    )
                    if replayed_gateway != gateway:
                        raise RuntimeError("gateway replay changed the immutable record")
                    if (
                        gateway.market_gate.status.value == "generation_required"
                        and not case["gateway_call_possible"]
                    ):
                        raise RuntimeError("gateway call ceiling exhausted before construction")
                    if gateway_constructed and not case["gateway_call_possible"]:
                        raise RuntimeError("gateway call exceeded its preflight reservation")
                    endpoint_source: Any = (
                        M2ASelectionRecordSource(selection_records=tuple(selection_records))
                        if selection_records
                        else DirectGroundingSource()
                    )
                    compiler_input = SearchPlanningInput(
                        envelope=envelope,
                        endpoint_source=endpoint_source,
                        upstream_selection_id_bindings=tuple(bindings),
                        gateway_discovery_result=gateway,
                        capability=capability,
                    )
                    compiler_kwargs: dict[str, Any] = {
                        "policy": compiler_policy,
                        "repository": repository,
                        "market_policy": market_policy,
                    }
                    if selection_records:
                        compiler_kwargs.update(
                            selection_cap_policy=cap_policy,
                            selection_distance_policy=distance_policy,
                        )
                    planning_result = plan_searches(compiler_input, **compiler_kwargs)
                    if planning_result.plan is None:
                        raise RuntimeError(
                            f"M2C did not produce an executable plan: {planning_result.outcome.value}"
                        )
                    source_bundle_path = run_dir / (
                        f"{case['id']}__trial-{trial}__source-bundle.json"
                    )
                    _write_source_bundle(
                        source_bundle_path,
                        request=request,
                        session_id=envelope.source.session_id,
                        revision=envelope.source.revision,
                        selections=selection_records,
                        bindings=bindings,
                        gateway=gateway,
                        compilation_binding_digest=(
                            planning_result.plan.identity.compilation_binding_digest
                        ),
                    )
                    reloaded = json.loads(source_bundle_path.read_text())
                    reloaded_request = EffectiveRequest.model_validate(
                        reloaded["effective_request"]
                    )
                    reloaded_selections = tuple(
                        AirportSelectionRecord.model_validate(item)
                        for item in reloaded["airport_selection_records"]
                    )
                    reloaded_bindings = tuple(
                        SelectionRecordIdBinding.model_validate(item)
                        for item in reloaded["selection_bindings"]
                    )
                    reloaded_gateway = GatewayDiscoveryResult.model_validate(
                        reloaded["gateway_discovery_result"]
                    )
                    reloaded_input = SearchPlanningInput(
                        envelope=PlanningInputEnvelope(
                            source=PlanningSource(
                                session_id=reloaded["session_id"],
                                revision=reloaded["revision"],
                            ),
                            effective_request=reloaded_request,
                        ),
                        endpoint_source=(
                            M2ASelectionRecordSource(selection_records=reloaded_selections)
                            if reloaded_selections
                            else DirectGroundingSource()
                        ),
                        upstream_selection_id_bindings=reloaded_bindings,
                        gateway_discovery_result=reloaded_gateway,
                        capability=capability,
                    )
                    replay_result = plan_searches(reloaded_input, **compiler_kwargs)
                    if replay_result != planning_result:
                        raise RuntimeError("same-record M2C replay was not deterministic")
                    assert replay_result.plan is not None
                    handoff = check_plan_handoff(
                        replay_result.plan,
                        current_session_id=reloaded["session_id"],
                        current_revision=reloaded["revision"],
                        current_effective_request=reloaded_request,
                        expected_compilation_binding_digest=reloaded[
                            "trusted_compilation_binding_digest"
                        ],
                    )
                    if handoff.status is not PlanHandoffStatus.CURRENT or not handoff.executable:
                        raise RuntimeError("reloaded plan failed the execution handoff check")
                    public.update(
                        {
                            "status": "completed",
                            "trajectory_outcome": "plan",
                            "upstream": {
                                "status": session.status.value,
                                "revision": session.current_revision.revision,
                                "clarification_turns": len(answers),
                            },
                            "m2a": {
                                "record_bindings": [
                                    item.model_dump(mode="json") for item in bindings
                                ],
                                "accepted_endpoints": {
                                    "origins": [item.airport_iata for item in origins],
                                    "destinations": [item.airport_iata for item in destinations],
                                },
                            },
                            "m2b": {
                                "outcome": gateway.outcome.value,
                                "result_digest": gateway.result_digest,
                                "digest_verified": (
                                    gateway.result_digest
                                    == gateway_discovery_result_digest(gateway)
                                ),
                                "gateway_call_constructed": gateway_constructed,
                                "market_coverage": gateway.market_coverage.value,
                                "accepted_relationships": (_accepted_relationship_count(gateway)),
                                "advisory_count": sum(
                                    item.market_comparison.advisory
                                    for item in gateway.candidate_decisions
                                ),
                            },
                            "m2c": _public_plan_summary(planning_result),
                            "same_record_replay": {
                                "equal": True,
                                "plan_digest_equal": (
                                    planning_result.plan is not None
                                    and replay_result.plan is not None
                                    and planning_result.plan.plan_digest
                                    == replay_result.plan.plan_digest
                                ),
                                "source_bundle_reloaded": True,
                            },
                            "handoff": handoff.model_dump(mode="json"),
                            "private_source_bundle": str(source_bundle_path),
                        }
                    )
                except _UpstreamBlocked as exc:
                    exception = exc
                    expected_block = case["expected_trajectory"] == "upstream_blocked"
                    public.update(
                        {
                            "status": "completed" if expected_block else "upstream_blocked",
                            "trajectory_outcome": "upstream_blocked",
                            "trajectory_matches": expected_block,
                            "error_type": type(exc).__name__,
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - diagnostic continues; details stay private.
                    exception = exc
                    public.update({"status": "error", "error_type": type(exc).__name__})
                public["latency_seconds"] = round(perf_counter() - started, 3)
                public.setdefault(
                    "trajectory_matches",
                    public.get("trajectory_outcome") == case["expected_trajectory"],
                )
                attempted = sum(
                    0 if usage is None else usage.get("calls", 0) for usage in all_usage
                )
                if gateway is not None and gateway.generator_invocation is not None:
                    usage = gateway.generator_invocation.usage
                    attempted += 0 if usage is None else usage.get("calls", 0)
                public["trace_reconciliation"] = {
                    "reserved_calls": case_reservation,
                    "attempted_calls": attempted,
                    "private_trace_calls": len(raw_calls),
                    "within_ceiling": attempted <= case_reservation,
                    "reconciled": attempted == len(raw_calls) and attempted <= case_reservation,
                }
                trace_path = write_eval_llm_trace(
                    run_dir, scenario=case, record=public, calls=raw_calls
                )
                private_path = _write_private(
                    trace_path,
                    request=request,
                    selections=selection_records,
                    gateway=gateway,
                    planning_result=planning_result,
                    exception=exception,
                )
                public["private_trace"] = {
                    "path": str(trace_path),
                    "record_path": str(private_path),
                    "calls": len(raw_calls),
                }
                records.append(public)

    attempted_calls = sum(item["trace_reconciliation"]["attempted_calls"] for item in records)
    reconciled = sum(item["trace_reconciliation"]["reconciled"] for item in records)
    errors = sum(item["status"] != "completed" for item in records)
    full_run = not requested_ids
    return {
        **base,
        "records": records,
        "summary": {
            "runs": len(records),
            "planned_calls": selected_calls,
            "attempted_calls": attempted_calls,
            "completed": len(records) - errors,
            "errors": errors,
            "trace_reconciled": reconciled,
            "same_record_replays": sum(
                bool(item.get("same_record_replay", {}).get("equal")) for item in records
            ),
            "mechanically_completed": (
                full_run
                and errors == 0
                and attempted_calls <= selected_calls
                and reconciled == len(records)
                and all(
                    item.get("trajectory_matches") is True
                    and (
                        item.get("trajectory_outcome") == "upstream_blocked"
                        or (
                            item.get("same_record_replay", {}).get("equal")
                            and item.get("same_record_replay", {}).get("source_bundle_reloaded")
                            and item.get("handoff", {}).get("status") == "current"
                            and item.get("handoff", {}).get("executable") is True
                            and item.get("m2c", {}).get("mandatory_complete") is True
                            and item.get("m2c", {}).get("outcome")
                            in {"planned", "reduced_coverage"}
                        )
                    )
                    for item in records
                )
            ),
            "semantic_qualification": "not_claimed_manual_review_required",
        },
    }
