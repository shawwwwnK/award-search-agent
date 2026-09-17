"""Diagnostic live evaluation for model-proposed endpoint-airport selection.

The evaluator starts from a canonical catalog entity, not a user utterance. It
therefore measures the narrow selector boundary without reopening intent or
clarification behavior. Its public artifact is deliberately redacted: raw
model-facing input, raw provider response, and provider-error details remain
only in ignored local trace sidecars; validated proposal/selection codes may be
public evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import yaml

from award_agent.observability.llm_trace import write_eval_llm_trace
from award_agent.search_planning.airport_selection_policy import (
    AirportSelectionCapPolicy,
    airport_selection_cap_policy_digest,
    classify_resolved_entity,
    load_default_airport_selection_cap_policy,
)
from award_agent.search_planning.airport_selector import (
    AIRPORT_SELECTOR_ADAPTER_VERSION,
    AIRPORT_SELECTOR_RESPONSE_SCHEMA_SHA256,
    ORIGINAL_SIMPLE_AIRPORT_SELECTOR_PROMPT,
    REFINED_AIRPORT_SELECTOR_PROMPT,
    AirportSelectionRecord,
    AirportSelectorModelInput,
    AirportSelectorPrompt,
    OpenAIAirportSelector,
    OpenAIAirportSelectorConfig,
    airport_selection_distance_policy_digest,
    validate_airport_selection_proposal,
)
from award_agent.search_planning.distance_consistency import CityAirportDistanceConsistency
from award_agent.search_planning.knowledge import CatalogKnowledgeRepository

DEFAULT_AIRPORT_SELECTOR_LIVE_FIXTURES = Path("evals/airport_selector/development_cases_v3.yaml")
DEFAULT_AIRPORT_SELECTOR_LIVE_TRACE_DIR = Path("evals/airport_selector/traces-live")
DEFAULT_AIRPORT_SELECTOR_CATALOG_RELEASE = Path(
    "data/search_planning/catalogs/m1a-3cb7981519612945"
)
AIRPORT_SELECTOR_LIVE_EVALUATOR_VERSION = "airport_selector_live_eval_v3"
_FIXTURE_CONTRACT_VERSION = "airport_selector_development_v3"

_PROMPT_ARMS: dict[str, AirportSelectorPrompt] = {
    "original_simple": ORIGINAL_SIMPLE_AIRPORT_SELECTOR_PROMPT,
    "refined": REFINED_AIRPORT_SELECTOR_PROMPT,
}


class AirportSelectorLiveFixtureError(ValueError):
    """The disclosed selector development corpus has an invalid contract."""


def _fixture_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _required_mapping(value: object, *, label: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AirportSelectorLiveFixtureError(f"{label} has an invalid shape")
    return value


def _code_list(value: object, *, label: str, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise AirportSelectorLiveFixtureError(f"{label} must be a non-empty list")
    values = tuple(value)
    if any(not isinstance(code, str) or len(code) != 3 or not code.isupper() for code in values):
        raise AirportSelectorLiveFixtureError(f"{label} must contain uppercase IATA-shaped codes")
    if len(values) != len(set(values)):
        raise AirportSelectorLiveFixtureError(f"{label} contains duplicate codes")
    return values


def _load(path: Path) -> tuple[tuple[Mapping[str, Any], ...], dict[str, Any]]:
    try:
        payload = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise AirportSelectorLiveFixtureError("unable to load airport-selector casebook") from exc
    top = _required_mapping(
        payload,
        label="airport-selector casebook",
        keys={"contract_version", "development", "scenarios"},
    )
    if top["contract_version"] != _FIXTURE_CONTRACT_VERSION or top["development"] is not True:
        raise AirportSelectorLiveFixtureError("casebook must be the disclosed development corpus")
    raw_scenarios = top["scenarios"]
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise AirportSelectorLiveFixtureError("casebook needs at least one scenario")

    prepared: list[Mapping[str, Any]] = []
    identifiers: set[str] = set()
    for raw in raw_scenarios:
        scenario = _required_mapping(
            raw,
            label="airport-selector scenario",
            keys={"id", "entity_id", "role", "expectations"},
        )
        identifier = scenario["id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise AirportSelectorLiveFixtureError("scenario IDs must be unique non-empty strings")
        if not isinstance(scenario["entity_id"], str) or not scenario["entity_id"].strip():
            raise AirportSelectorLiveFixtureError("scenario entity IDs must be non-empty strings")
        if scenario["role"] not in {"origin", "destination"}:
            raise AirportSelectorLiveFixtureError("scenario role must be origin or destination")
        expectations = _required_mapping(
            scenario["expectations"],
            label=f"scenario {identifier!r} expectations",
            keys={"must_consider_any_of", "acceptable", "unacceptable", "review_focus"},
        )
        must_consider = _code_list(
            expectations["must_consider_any_of"], label=f"scenario {identifier!r} must-consider"
        )
        acceptable = _code_list(
            expectations["acceptable"], label=f"scenario {identifier!r} acceptable"
        )
        unacceptable = _code_list(
            expectations["unacceptable"], label=f"scenario {identifier!r} unacceptable"
        )
        if not set(must_consider).issubset(acceptable):
            raise AirportSelectorLiveFixtureError(
                "must-consider values must be acceptable alternatives"
            )
        if set(acceptable) & set(unacceptable):
            raise AirportSelectorLiveFixtureError("acceptable and unacceptable values overlap")
        if (
            not isinstance(expectations["review_focus"], str)
            or not expectations["review_focus"].strip()
        ):
            raise AirportSelectorLiveFixtureError(
                "scenario review focus must be a non-empty string"
            )
        identifiers.add(identifier)
        prepared.append(scenario)
    return tuple(prepared), {
        "path": str(path),
        "contract_version": _FIXTURE_CONTRACT_VERSION,
        "sha256": _fixture_sha256(path),
        "scenario_count": len(prepared),
        "visibility": "disclosed_development",
    }


def load_airport_selector_live_cases(
    fixture_path: Path = DEFAULT_AIRPORT_SELECTOR_LIVE_FIXTURES,
) -> tuple[Mapping[str, Any], ...]:
    """Load the disclosed casebook without model, network, or catalog access."""

    scenarios, _metadata = _load(fixture_path)
    return scenarios


def _drain(selector: Any) -> tuple[dict[str, int] | None, list[dict[str, Any]]]:
    """Drain opt-in capture once, after every attempted selector call."""

    return selector.take_usage(), selector.take_call_traces()


def _reconcile(usage: dict[str, int] | None, calls: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    attempted = 0 if usage is None else usage["calls"]
    captured = 0 if usage is None else usage["captured_calls"]
    missing = 0 if usage is None else usage["missing_calls"]
    return {
        "attempted_calls": attempted,
        "trace_calls": len(calls),
        "usage_captured_calls": captured,
        "missing_usage_calls": missing,
        "reconciled": attempted == len(calls) and captured == attempted and missing == 0,
    }


def _selection_summary(selection: AirportSelectionRecord) -> dict[str, Any]:
    return {
        "proposal_outcome": selection.proposal.outcome.value,
        "proposed_iata_codes": list(selection.proposal.airport_iata_codes),
        "accepted_iata_codes": [airport.airport_iata for airport in selection.accepted_airports],
        "candidate_dispositions": [
            {
                "iata": candidate.proposed_iata,
                "disposition": candidate.disposition.value,
                "identity": candidate.identity_status.value,
                "facility": candidate.facility_status.value,
                "geographic_membership": candidate.geographic_membership.value,
                "city_distance": (
                    None
                    if candidate.city_distance is None
                    else candidate.city_distance.status.value
                ),
            }
            for candidate in selection.candidate_validations
        ],
    }


def _criteria_summary(
    scenario: Mapping[str, Any], selection: AirportSelectionRecord
) -> dict[str, Any]:
    expectations = scenario["expectations"]
    assert isinstance(expectations, Mapping)  # guaranteed by _load
    accepted = {airport.airport_iata for airport in selection.accepted_airports}
    must_consider = tuple(expectations["must_consider_any_of"])
    acceptable = tuple(expectations["acceptable"])
    unacceptable = tuple(expectations["unacceptable"])
    return {
        "must_consider_any_of": list(must_consider),
        "must_consider_present": bool(accepted & set(must_consider)),
        "accepted_outside_acceptable_envelope": sorted(accepted - set(acceptable)),
        "unacceptable_accepted": sorted(accepted & set(unacceptable)),
        # The criterion is intentionally not reduced to an aggregate pass/fail.
        # A human reviews useful coverage, omissions, and weak extras separately.
        "manual_semantic_review_required": True,
    }


def _prompt_for_arm(prompt_arm: str) -> AirportSelectorPrompt:
    try:
        return _PROMPT_ARMS[prompt_arm]
    except KeyError as exc:
        raise ValueError(f"unknown airport-selector prompt arm: {prompt_arm}") from exc


def _default_selector_factory(config: OpenAIAirportSelectorConfig) -> OpenAIAirportSelector:
    return OpenAIAirportSelector(config, capture_llm_io=True)


def run_airport_selector_live_eval(
    *,
    model: str = "gpt-5.6-luna",
    trials: int = 3,
    prompt_arms: Sequence[str] = ("original_simple", "refined"),
    fixture_path: Path = DEFAULT_AIRPORT_SELECTOR_LIVE_FIXTURES,
    catalog_release: Path = DEFAULT_AIRPORT_SELECTOR_CATALOG_RELEASE,
    trace_dir: Path = DEFAULT_AIRPORT_SELECTOR_LIVE_TRACE_DIR,
    max_cases: int | None = None,
    cap_policy: AirportSelectionCapPolicy | None = None,
    distance_policy: CityAirportDistanceConsistency | None = None,
    selector_factory: Callable[[OpenAIAirportSelectorConfig], Any] = _default_selector_factory,
    repository_factory: Callable[[Path], Any] = CatalogKnowledgeRepository,
) -> dict[str, Any]:
    """Run bounded diagnostic trials; never retry, refill, or claim qualification.

    ``selector_factory`` and ``repository_factory`` make all tests fully offline.
    The default path creates a live OpenAI adapter only when this function is
    explicitly invoked by the CLI or a caller.
    """

    if trials < 1:
        raise ValueError("trials must be positive")
    if max_cases is not None and max_cases < 1:
        raise ValueError("max_cases must be positive when supplied")
    if not prompt_arms:
        raise ValueError("at least one prompt arm is required")
    prompts = tuple((arm, _prompt_for_arm(arm)) for arm in prompt_arms)
    if len({arm for arm, _prompt in prompts}) != len(prompts):
        raise ValueError("prompt arms must be unique")
    scenarios, fixture = _load(fixture_path)
    if max_cases is not None:
        scenarios = scenarios[:max_cases]
    cap_policy = cap_policy or load_default_airport_selection_cap_policy()
    distance_policy = distance_policy or CityAirportDistanceConsistency(
        policy_version="city-airport-distance-consistency-v1"
    )
    generated_at = datetime.now(UTC).isoformat()
    run_trace_dir = (
        trace_dir / f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    )
    records: list[dict[str, Any]] = []

    with repository_factory(catalog_release) as repository:
        for trial in range(1, trials + 1):
            for scenario in scenarios:
                entity = repository.get_entity(str(scenario["entity_id"]))
                if entity is None:
                    raise AirportSelectorLiveFixtureError(
                        f"scenario {scenario['id']!r} entity is absent from selected catalog"
                    )
                context = classify_resolved_entity(
                    entity, repository.entity_selection_metadata(entity.entity_id)
                )
                cap = cap_policy.applicable_cap_for(context)
                model_input = AirportSelectorModelInput.from_context(context, cap)
                for prompt_arm, prompt in prompts:
                    selector = selector_factory(
                        OpenAIAirportSelectorConfig(model=model, prompt=prompt)
                    )
                    started = perf_counter()
                    record: dict[str, Any] = {
                        "id": scenario["id"],
                        "trial": trial,
                        "prompt_arm": prompt_arm,
                        # No entity label, request text, or model instructions are public.
                        "resolved_entity": {
                            "entity_id": context.entity_id,
                            "entity_kind": context.entity_kind.value,
                            "category": context.category.value,
                            "category_basis": context.category_basis.value,
                        },
                        "applicable_cap": cap.model_dump(mode="json"),
                    }
                    calls: list[dict[str, Any]] = []
                    usage: dict[str, int] | None = None
                    try:
                        proposal = selector.propose(model_input)
                        selection = validate_airport_selection_proposal(
                            role=scenario["role"],
                            context=context,
                            cap_policy=cap_policy,
                            distance_policy=distance_policy,
                            proposal=proposal,
                            model=model,
                            prompt_version=prompt.version,
                            repository=repository,
                        )
                        record.update(_selection_summary(selection))
                        record["criteria"] = _criteria_summary(scenario, selection)
                        record["status"] = "completed"
                    except Exception as exc:  # noqa: BLE001 - a bounded live diagnostic continues.
                        # A provider error can echo model input. Its message is private trace data only.
                        record.update({"status": "error", "error_type": type(exc).__name__})
                    finally:
                        usage, calls = _drain(selector)
                    record["usage"] = usage
                    record["trace_reconciliation"] = _reconcile(usage, calls)
                    record["latency_seconds"] = round(perf_counter() - started, 3)
                    # No pricing constants are injected here. Do not silently turn a stale
                    # remembered price into an official cost estimate.
                    record["cost_estimate"] = {
                        "status": "not_estimated_no_versioned_price_card",
                        "amount_usd": None,
                        "price_card_version": None,
                    }
                    trace_path = write_eval_llm_trace(
                        run_trace_dir, scenario=scenario, record=record, calls=calls
                    )
                    record["private_trace"] = {"path": str(trace_path), "calls": len(calls)}
                    records.append(record)

    errors = sum(record["status"] == "error" for record in records)
    reconciled = sum(record["trace_reconciliation"]["reconciled"] for record in records)
    return {
        "schema_version": AIRPORT_SELECTOR_LIVE_EVALUATOR_VERSION,
        "diagnostic_only": True,
        "generated_at": generated_at,
        "models": {"selector": model},
        "prompt_arms": [{"name": arm, "prompt_version": prompt.version} for arm, prompt in prompts],
        "selector_contract": {
            "adapter_version": AIRPORT_SELECTOR_ADAPTER_VERSION,
            "response_schema_sha256": AIRPORT_SELECTOR_RESPONSE_SCHEMA_SHA256,
            "storage": False,
            "retry_or_refill": "none",
        },
        "fixture": fixture,
        "catalog": {
            "release_path": str(catalog_release),
            "snapshot_id": repository.snapshot_id,
            "knowledge_receipt": repository.knowledge_receipt.model_dump(mode="json"),
        },
        "cap_policy": {
            "version": cap_policy.policy_version,
            "sha256": airport_selection_cap_policy_digest(cap_policy),
        },
        "distance_policy": {
            "version": distance_policy.policy_version,
            "sha256": airport_selection_distance_policy_digest(distance_policy),
            "maximum_distance_km": distance_policy.maximum_distance_km,
        },
        "trials": trials,
        "records": records,
        "summary": {
            "runs": len(records),
            "completed": sum(record["status"] == "completed" for record in records),
            "errors": errors,
            "trace_reconciled": reconciled,
            "mechanically_completed": errors == 0 and reconciled == len(records),
            "semantic_qualification": "not_claimed_manual_review_required",
        },
    }
