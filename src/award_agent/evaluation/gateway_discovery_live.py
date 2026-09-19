"""Bounded, diagnostic M2B gateway-discovery evaluation.

The complete reviewed casebook is preflighted before any generator factory is
reachable. Public output is redacted; raw traces and immutable records are
ignored local sidecars for human review only.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

import yaml

from award_agent.observability.llm_trace import write_eval_llm_trace
from award_agent.search_planning.contracts import SelectedAirport
from award_agent.search_planning.gateway_discovery import (
    GatewayDiscoveryGeneratorConfiguration,
    GatewayDiscoveryInput,
    GatewayDiscoveryResult,
    discover_gateway_candidates,
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
from award_agent.search_planning.knowledge import CatalogKnowledgeRepository
from award_agent.search_planning.market_policy import (
    MarketGenerationGate,
    MarketGenerationGateStatus,
    classify_and_gate_airport_markets,
    default_planning_market_policy_path,
    load_planning_market_policy,
    planning_market_policy_digest,
)

DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES = Path("evals/gateway_discovery/development_cases_v1.yaml")
DEFAULT_GATEWAY_DISCOVERY_LIVE_TRACE_DIR = Path("evals/gateway_discovery/traces-live")
DEFAULT_GATEWAY_DISCOVERY_CATALOG_RELEASE = Path(
    "data/search_planning/catalogs/m1a-3cb7981519612945"
)
GATEWAY_DISCOVERY_LIVE_EVALUATOR_VERSION = "gateway_discovery_live_eval_v1"
_CONTRACT = "gateway_discovery_development_v1"
_LIVE_DEFAULTS = {
    "model": "gpt-5.6-luna",
    "trials": 2,
    "max_calls_per_trial": 7,
    "max_calls_total": 14,
    "retry_policy": "no_retry",
    "refill_policy": "no_refill",
    "judge_policy": "human_review_only",
}
_MAX_TRIALS = 2
_MAX_CALLS_PER_TRIAL = 7
_MAX_CALLS_TOTAL = 14


class GatewayDiscoveryLiveFixtureError(ValueError):
    """The disclosed development casebook is malformed or has drifted."""


@dataclass(frozen=True)
class _PreparedCase:
    scenario: Mapping[str, Any]
    discovery_input: GatewayDiscoveryInput
    gate: MarketGenerationGate


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _mapping(value: object, *, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise GatewayDiscoveryLiveFixtureError(f"{label} has an invalid shape")
    return value


def _codes(value: object, *, label: str, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise GatewayDiscoveryLiveFixtureError(f"{label} must be a non-empty code list")
    result = tuple(value)
    if any(not isinstance(x, str) or len(x) != 3 or not x.isupper() for x in result):
        raise GatewayDiscoveryLiveFixtureError(f"{label} must contain uppercase IATA-shaped codes")
    if len(result) != len(set(result)):
        raise GatewayDiscoveryLiveFixtureError(f"{label} has duplicate codes")
    return result


def _date_context(value: object, *, label: str) -> GatewayOutboundDateContext:
    mapping = _mapping(
        value, keys={"start", "end", "timezone", "effective_window_precision"}, label=label
    )
    try:
        return GatewayOutboundDateContext.model_validate(mapping)
    except ValueError as exc:
        raise GatewayDiscoveryLiveFixtureError(f"{label} is invalid") from exc


def _load(path: Path) -> tuple[tuple[Mapping[str, Any], ...], dict[str, Any], Mapping[str, Any]]:
    try:
        raw = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise GatewayDiscoveryLiveFixtureError("unable to load gateway-discovery casebook") from exc
    top = _mapping(
        raw,
        keys={
            "contract_version",
            "development_only",
            "casebook_id",
            "purpose",
            "catalog",
            "market_policy",
            "resolved_outbound_date_context",
            "live_run_defaults",
            "scenarios",
        },
        label="gateway casebook",
    )
    if (
        top["contract_version"] != _CONTRACT
        or top["development_only"] is not True
        or top["casebook_id"] != "m2b_gateway_discovery_development_v1"
        or top["purpose"] != "diagnostic_semantic_review_before_2c_search_plan_compilation"
    ):
        raise GatewayDiscoveryLiveFixtureError("casebook identity is not reviewed development v1")
    catalog = _mapping(
        top["catalog"],
        keys={"release_id", "logical_content_sha256", "source_role"},
        label="catalog",
    )
    policy = _mapping(
        top["market_policy"],
        keys={"policy_version", "digest", "source_role"},
        label="market policy",
    )
    if (
        not isinstance(catalog["release_id"], str)
        or len(str(catalog["logical_content_sha256"])) != 64
        or not isinstance(policy["policy_version"], str)
        or len(str(policy["digest"])) != 64
        or catalog["source_role"] != "endpoint_identity_and_market_classification_only"
        or policy["source_role"] != "deterministic_skip_or_generation_gate_only"
    ):
        raise GatewayDiscoveryLiveFixtureError("casebook catalog or policy identity is invalid")
    shared_date = _date_context(top["resolved_outbound_date_context"], label="date context")
    defaults = _mapping(top["live_run_defaults"], keys=set(_LIVE_DEFAULTS), label="live defaults")
    if dict(defaults) != _LIVE_DEFAULTS:
        raise GatewayDiscoveryLiveFixtureError("casebook live defaults must equal reviewed bounds")
    raw_scenarios = top["scenarios"]
    if not isinstance(raw_scenarios, list) or len(raw_scenarios) != 8:
        raise GatewayDiscoveryLiveFixtureError("casebook must contain its complete eight scenarios")
    required = {
        "id",
        "origins",
        "destinations",
        "outbound_date",
        "expected_gate",
        "expected_market_ids",
        "catalog_endpoints",
        "review_focus",
    }
    optional = {"eligible_not_required_iata_codes"}
    scenarios: list[Mapping[str, Any]] = []
    identifiers: set[str] = set()
    for scenario in raw_scenarios:
        if (
            not isinstance(scenario, Mapping)
            or set(scenario) - required - optional
            or not required.issubset(scenario)
        ):
            raise GatewayDiscoveryLiveFixtureError("scenario has an invalid shape")
        identifier = scenario["id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise GatewayDiscoveryLiveFixtureError("scenario IDs must be unique non-empty strings")
        origins = _codes(scenario["origins"], label="origins")
        destinations = _codes(scenario["destinations"], label="destinations")
        if scenario["expected_gate"] not in {"generation_required", "skip_single_market"}:
            raise GatewayDiscoveryLiveFixtureError("scenario expected gate is invalid")
        expected = _mapping(
            scenario["expected_market_ids"],
            keys={"origin", "destination", "union"},
            label="expected markets",
        )
        markets: dict[str, tuple[str, ...]] = {}
        for side in ("origin", "destination", "union"):
            values = expected[side]
            if (
                not isinstance(values, list)
                or values != sorted(set(values))
                or any(not isinstance(x, str) or not x for x in values)
            ):
                raise GatewayDiscoveryLiveFixtureError("expected markets must be sorted unique IDs")
            markets[side] = tuple(values)
        if markets["union"] != tuple(sorted(set(markets["origin"]) | set(markets["destination"]))):
            raise GatewayDiscoveryLiveFixtureError("expected union markets must derive from sides")
        metadata = scenario["catalog_endpoints"]
        if not isinstance(metadata, Mapping) or set(metadata) != set(origins + destinations):
            raise GatewayDiscoveryLiveFixtureError("catalog endpoints must exactly cover endpoints")
        for code, values in metadata.items():
            item = _mapping(
                values,
                keys={"airport_id", "country_code", "iso_region", "airport_type"},
                label="endpoint metadata",
            )
            if (
                not isinstance(code, str)
                or not isinstance(item["airport_id"], str)
                or not isinstance(item["country_code"], str)
                or len(item["country_code"]) != 2
                or not item["country_code"].isupper()
                or not isinstance(item["iso_region"], str)
                or not isinstance(item["airport_type"], str)
            ):
                raise GatewayDiscoveryLiveFixtureError("endpoint metadata values are invalid")
        if _date_context(scenario["outbound_date"], label="scenario date") != shared_date:
            raise GatewayDiscoveryLiveFixtureError(
                "scenario date differs from reviewed shared date"
            )
        eligible = _codes(
            scenario.get("eligible_not_required_iata_codes", []),
            label="eligible codes",
            allow_empty=True,
        )
        if set(eligible) & set(origins + destinations):
            raise GatewayDiscoveryLiveFixtureError(
                "eligible candidates cannot be original endpoints"
            )
        if not isinstance(scenario["review_focus"], str) or not scenario["review_focus"].strip():
            raise GatewayDiscoveryLiveFixtureError("review focus must be non-empty")
        identifiers.add(identifier)
        scenarios.append(scenario)
    if (
        sum(item["expected_gate"] == "skip_single_market" for item in scenarios) != 1
        or sum(item["expected_gate"] == "generation_required" for item in scenarios) != 7
    ):
        raise GatewayDiscoveryLiveFixtureError(
            "casebook must contain exactly one skip and seven generation cases"
        )
    fixture = {
        "path": str(path),
        "contract_version": _CONTRACT,
        "sha256": _sha(path),
        "scenario_count": len(scenarios),
        "visibility": "disclosed_development",
    }
    return tuple(scenarios), fixture, top


def load_gateway_discovery_live_cases(
    path: Path = DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES,
) -> tuple[Mapping[str, Any], ...]:
    """Load and structurally validate the corpus without catalog or model access."""
    return _load(path)[0]


class _TraceTee:
    def __init__(self, inner: Any, holder: list[dict[str, Any]]) -> None:
        self._inner, self._holder = inner, holder

    def propose(self, model_input: Any) -> Any:
        return self._inner.propose(model_input)

    def take_usage(self) -> dict[str, int] | None:
        return cast(dict[str, int] | None, self._inner.take_usage())

    def take_call_traces(self) -> list[dict[str, Any]]:
        calls = cast(list[dict[str, Any]], self._inner.take_call_traces())
        self._holder.extend(calls)
        return calls


def _default_generator_factory(config: OpenAIGatewayGeneratorConfig) -> OpenAIGatewayGenerator:
    return OpenAIGatewayGenerator(config, capture_llm_io=True)


def _selected(repository: Any, code: str, expected: Mapping[str, Any]) -> SelectedAirport:
    airport = repository.lookup_airport_iata(code)
    metadata = (
        None if airport is None else repository.airport_selection_metadata(airport.airport_id)
    )
    actual = (
        None
        if airport is None
        else {
            "airport_id": airport.airport_id,
            "country_code": None if metadata is None else metadata.country_code,
            "iso_region": None if metadata is None else metadata.iso_region,
            "airport_type": None if metadata is None else metadata.airport_type,
        }
    )
    if actual != dict(expected):
        raise GatewayDiscoveryLiveFixtureError(
            f"casebook endpoint {code} no longer matches pinned catalog metadata"
        )
    assert airport is not None
    return SelectedAirport(
        airport_id=airport.airport_id,
        airport_iata=airport.iata,
        airport_evidence_source_ids=airport.source_ids,
    )


def _markets(gate: MarketGenerationGate) -> dict[str, list[str]]:
    values = {
        role: sorted(
            {
                item.market_id
                for item in gate.assignments
                if item.role == role and item.market_id is not None
            }
        )
        for role in ("origin", "destination")
    }
    values["union"] = sorted(set(values["origin"]) | set(values["destination"]))
    return values


def _preflight(
    scenarios: Sequence[Mapping[str, Any]], *, policy: Any, repository: Any
) -> tuple[_PreparedCase, ...]:
    """Resolve all endpoints and reproduce all gates before model construction."""
    prepared: list[_PreparedCase] = []
    for scenario in scenarios:
        metadata = cast(Mapping[str, Mapping[str, Any]], scenario["catalog_endpoints"])
        origins = tuple(_selected(repository, code, metadata[code]) for code in scenario["origins"])
        destinations = tuple(
            _selected(repository, code, metadata[code]) for code in scenario["destinations"]
        )
        discovery_input = GatewayDiscoveryInput(
            origin_endpoints=origins,
            destination_endpoints=destinations,
            outbound_date=_date_context(scenario["outbound_date"], label="scenario date"),
        )
        gate = classify_and_gate_airport_markets(
            origin_endpoints=origins,
            destination_endpoints=destinations,
            policy=policy,
            repository=repository,
        )
        if (
            gate.status.value != scenario["expected_gate"]
            or _markets(gate) != scenario["expected_market_ids"]
        ):
            raise GatewayDiscoveryLiveFixtureError(
                f"scenario {scenario['id']!r} expected market gate does not reproduce"
            )
        prepared.append(_PreparedCase(scenario, discovery_input, gate))
    return tuple(prepared)


def _summary(result: GatewayDiscoveryResult) -> dict[str, Any]:
    return {
        "outcome": result.outcome.value,
        "generation_status": result.generation_status.value,
        "accepted": {
            "origin_access_gateways": [
                x.airport.airport_iata for x in result.accepted_origin_access_gateways
            ],
            "destination_access_gateways": [
                x.airport.airport_iata for x in result.accepted_destination_access_gateways
            ],
            "intermediate_hubs": [
                {
                    "iata": hub.airport.airport_iata,
                    "scopes": [
                        {
                            "origin_references": [x.airport_iata for x in scope.origin_side],
                            "destination_references": [
                                x.airport_iata for x in scope.destination_side
                            ],
                            "expanded_original_origins": list(
                                scope.expanded_original_origin_iata_codes
                            ),
                            "expanded_original_destinations": list(
                                scope.expanded_original_destination_iata_codes
                            ),
                        }
                        for scope in hub.scopes
                    ],
                }
                for hub in result.accepted_intermediate_hubs
            ],
        },
        "candidate_decisions": [
            {
                "pool": item.pool,
                "iata": item.proposed_airport_iata,
                "accepted": item.accepted,
                "issue_codes": [issue.code for issue in item.issues],
                "market_comparison": item.market_comparison.status.value,
                "scopes": [
                    {
                        "index": scope.scope_index,
                        "accepted": scope.accepted,
                        "issue_codes": [issue.code for issue in scope.issues],
                        "expanded_original_origins": list(
                            scope.expanded_original_origin_iata_codes
                        ),
                        "expanded_original_destinations": list(
                            scope.expanded_original_destination_iata_codes
                        ),
                    }
                    for scope in item.scope_decisions
                ],
            }
            for item in result.candidate_decisions
        ],
        "market_advisories": [
            {"iata": item.proposed_airport_iata, "status": item.market_comparison.status.value}
            for item in result.candidate_decisions
            if item.market_comparison.advisory
        ],
        "issue_codes": [item.code for item in result.issues],
        "result_digest": result.result_digest,
    }


def _reconcile(
    result: GatewayDiscoveryResult, calls: Sequence[Mapping[str, Any]], constructed: bool
) -> dict[str, Any]:
    attempted = result.market_gate.status is MarketGenerationGateStatus.GENERATION_REQUIRED
    invocation = result.generator_invocation
    if not attempted:
        return {
            "expected_calls": 0,
            "constructed": constructed,
            "provider_attempts": 0,
            "core_trace_count": 0,
            "private_trace_calls": len(calls),
            "usage": None,
            "reconciled": not constructed and invocation is None and not calls,
        }
    usage = None if invocation is None else invocation.usage
    capture_ok = (
        invocation is not None
        and invocation.usage_capture_status.value == "captured"
        and invocation.trace_capture_status.value == "captured"
        and invocation.trace_count == 1
        and usage is not None
        and usage.get("calls") == 1
        and usage.get("captured_calls") == 1
        and usage.get("missing_calls") == 0
    )
    return {
        "expected_calls": 1,
        "constructed": constructed,
        "provider_attempts": None if usage is None else usage.get("calls"),
        "core_trace_count": 0 if invocation is None else invocation.trace_count,
        "private_trace_calls": len(calls),
        "usage": usage,
        "reconciled": constructed and capture_ok and len(calls) == 1,
    }


def _write_private_record(
    trace_path: Path, *, result: GatewayDiscoveryResult | None, exception: Exception | None
) -> Path:
    path = trace_path.with_name(f"{trace_path.stem}__record.json")
    path.write_text(
        json.dumps(
            {
                "gateway_discovery_result": None
                if result is None
                else result.model_dump(mode="json"),
                "evaluator_exception": None
                if exception is None
                else {"type": type(exception).__name__, "message": str(exception)},
            },
            indent=2,
        )
        + "\n"
    )
    return path


def run_gateway_discovery_live_eval(
    *,
    model: str = "gpt-5.6-luna",
    trials: int = 2,
    fixture_path: Path = DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES,
    catalog_release: Path = DEFAULT_GATEWAY_DISCOVERY_CATALOG_RELEASE,
    policy_path: Path | None = None,
    trace_dir: Path = DEFAULT_GATEWAY_DISCOVERY_LIVE_TRACE_DIR,
    max_cases: int | None = None,
    generator_factory: Callable[[OpenAIGatewayGeneratorConfig], Any] = _default_generator_factory,
    repository_factory: Callable[[Path], Any] = CatalogKnowledgeRepository,
) -> dict[str, Any]:
    """Run the complete corpus or an explicit bounded smoke subset; never retry."""
    if trials < 1 or trials > _MAX_TRIALS:
        raise ValueError("trials must be within approved live bound")
    scenarios, fixture, top = _load(fixture_path)
    if model != _LIVE_DEFAULTS["model"]:
        raise ValueError("reviewed casebook pins the live model")
    policy_path = policy_path or default_planning_market_policy_path()
    policy = load_planning_market_policy(policy_path)
    if (
        policy.policy_version != top["market_policy"]["policy_version"]
        or planning_market_policy_digest(policy) != top["market_policy"]["digest"]
    ):
        raise GatewayDiscoveryLiveFixtureError("casebook does not bind selected market policy")
    generated_at = datetime.now(UTC).isoformat()
    trace_run = (
        trace_dir / f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    )
    with repository_factory(catalog_release) as repository:
        receipt = repository.knowledge_receipt
        if (
            receipt.release_id != top["catalog"]["release_id"]
            or receipt.logical_content_sha256 != top["catalog"]["logical_content_sha256"]
        ):
            raise GatewayDiscoveryLiveFixtureError("casebook does not bind selected catalog")
        all_prepared = _preflight(scenarios, policy=policy, repository=repository)
        if (
            sum(
                x.gate.status is MarketGenerationGateStatus.SKIP_SINGLE_MARKET for x in all_prepared
            )
            != 1
            or sum(
                x.gate.status is MarketGenerationGateStatus.GENERATION_REQUIRED
                for x in all_prepared
            )
            != 7
        ):
            raise GatewayDiscoveryLiveFixtureError("actual preflight case composition has drifted")
        if max_cases is not None and (max_cases < 1 or max_cases > len(all_prepared)):
            raise ValueError("max_cases must be within complete casebook")
        prepared = all_prepared if max_cases is None else all_prepared[:max_cases]
        per_trial_calls = sum(
            x.gate.status is MarketGenerationGateStatus.GENERATION_REQUIRED for x in prepared
        )
        if per_trial_calls > _MAX_CALLS_PER_TRIAL or per_trial_calls * trials > _MAX_CALLS_TOTAL:
            raise GatewayDiscoveryLiveFixtureError(
                "actual preflight call plan exceeds reviewed bounds"
            )
        records: list[dict[str, Any]] = []
        config = GatewayDiscoveryGeneratorConfiguration(
            model=model,
            prompt_version=DEFAULT_GATEWAY_GENERATOR_PROMPT.version,
            response_schema_sha256=GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
            adapter_version=GATEWAY_GENERATOR_ADAPTER_VERSION,
        )
        for trial in range(1, trials + 1):
            for case in prepared:
                raw_calls: list[dict[str, Any]] = []
                constructed = False

                def factory(holder: list[dict[str, Any]] = raw_calls) -> _TraceTee:
                    nonlocal constructed
                    constructed = True
                    return _TraceTee(
                        generator_factory(OpenAIGatewayGeneratorConfig(model=model)), holder
                    )

                scenario = case.scenario
                record: dict[str, Any] = {
                    "id": scenario["id"],
                    "trial": trial,
                    "resolved_endpoints": {
                        "origins": list(scenario["origins"]),
                        "destinations": list(scenario["destinations"]),
                    },
                    "expected_gate": scenario["expected_gate"],
                    "expected_market_ids": scenario["expected_market_ids"],
                }
                result: GatewayDiscoveryResult | None = None
                exception: Exception | None = None
                started = perf_counter()
                try:
                    result = discover_gateway_candidates(
                        discovery_input=case.discovery_input,
                        policy=policy,
                        repository=repository,
                        generator_factory=factory,
                        generator_configuration=config,
                    )
                    replay_gateway_discovery_result(
                        record=result, policy=policy, repository=repository
                    )
                    record.update(_summary(result))
                    record["gate_expectation_matches"] = (
                        result.market_gate == case.gate
                        and result.market_gate.status.value == scenario["expected_gate"]
                        and _markets(result.market_gate) == scenario["expected_market_ids"]
                    )
                    record["endpoint_preserved"] = result.input == case.discovery_input
                    record["status"] = "completed"
                except Exception as exc:  # noqa: BLE001 - public artifact remains type-only.
                    exception = exc
                    record.update(
                        {
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "gate_expectation_matches": False,
                            "endpoint_preserved": False,
                        }
                    )
                record["latency_seconds"] = round(perf_counter() - started, 3)
                record["trace_reconciliation"] = (
                    _reconcile(result, raw_calls, constructed)
                    if result is not None
                    else {
                        "expected_calls": 1
                        if case.gate.status is MarketGenerationGateStatus.GENERATION_REQUIRED
                        else 0,
                        "constructed": constructed,
                        "provider_attempts": None,
                        "core_trace_count": 0,
                        "private_trace_calls": len(raw_calls),
                        "usage": None,
                        "reconciled": False,
                    }
                )
                trace_path = write_eval_llm_trace(
                    trace_run, scenario=scenario, record=record, calls=raw_calls
                )
                private_record = _write_private_record(
                    trace_path, result=result, exception=exception
                )
                record["private_trace"] = {
                    "path": str(trace_path),
                    "record_path": str(private_record),
                    "calls": len(raw_calls),
                }
                record["cost_estimate"] = {
                    "status": "not_estimated_no_versioned_price_card",
                    "amount_usd": None,
                    "price_card_version": None,
                }
                records.append(record)
    expected_calls = per_trial_calls * trials
    errors = sum(x["status"] == "error" for x in records)
    reconciled = sum(bool(x["trace_reconciliation"]["reconciled"]) for x in records)
    attempted_calls = sum(x["trace_reconciliation"]["provider_attempts"] or 0 for x in records)
    constructed_calls = sum(bool(x["trace_reconciliation"]["constructed"]) for x in records)
    full_run = max_cases is None
    return {
        "schema_version": GATEWAY_DISCOVERY_LIVE_EVALUATOR_VERSION,
        "diagnostic_only": True,
        "generated_at": generated_at,
        "models": {"gateway_generator": model},
        "gateway_generator_contract": {
            "adapter_version": GATEWAY_GENERATOR_ADAPTER_VERSION,
            "prompt_version": DEFAULT_GATEWAY_GENERATOR_PROMPT.version,
            "response_schema_sha256": GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
            "storage": False,
            "retry_or_refill": "none",
        },
        "fixture": fixture,
        "catalog": {
            "release_path": str(catalog_release),
            "knowledge_receipt": receipt.model_dump(mode="json"),
        },
        "market_policy": {
            "path": str(policy_path),
            "version": policy.policy_version,
            "sha256": planning_market_policy_digest(policy),
        },
        "trials": trials,
        "full_run": full_run,
        "run_kind": "full" if full_run else "smoke_partial",
        "selected_case_ids": [x.scenario["id"] for x in prepared],
        "records": records,
        "summary": {
            "runs": len(records),
            "expected_calls": expected_calls,
            "constructed_calls": constructed_calls,
            "attempted_calls": attempted_calls,
            "completed": len(records) - errors,
            "errors": errors,
            "trace_reconciled": reconciled,
            "generation_failures": sum(x.get("outcome") == "generation_failure" for x in records),
            "empty_results": sum(x.get("outcome") == "success_empty" for x in records),
            "gate_expectations_matched": sum(
                bool(x.get("gate_expectation_matches")) for x in records
            ),
            "endpoint_preservation_matched": sum(
                bool(x.get("endpoint_preserved")) for x in records
            ),
            "mechanically_completed": errors == 0
            and reconciled == len(records)
            and attempted_calls == expected_calls
            and constructed_calls == expected_calls
            and all(
                x.get("gate_expectation_matches") and x.get("endpoint_preserved") for x in records
            ),
            "semantic_qualification": "not_claimed_manual_review_required",
        },
    }
