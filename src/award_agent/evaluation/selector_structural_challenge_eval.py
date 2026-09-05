"""Redacted evaluator for the public structural selector challenge fixture.

This is a deliberately single-model study.  It exercises the 28 checked-in public payloads
(four variants for each of seven topologies) and restores a selector response only in memory.
The emitted artifact contains public handles and aggregate measurements, never the private
catalog, request context, compiler oracle, or exception text.

The suite is a structural safety screen.  Its exact gate is intentionally descriptive rather
than a statistical generalization claim: every evaluated request, order pair, and repetition
must pass.  Cost is calculated only when the caller supplies a dated pricing snapshot.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import ValidationError

from award_agent.evaluation.frozen_selector_eval import StaticFrozenHolidayProvider
from award_agent.evaluation.selector_challenge_fixture import (
    DEFAULT_CONTROL_FIXTURE,
    DEFAULT_SELECTOR_CHALLENGE_FIXTURE,
    PreparedSelectorChallengeCase,
    preflight_selector_challenge_fixture,
    privacy_violations,
)
from award_agent.intent.extractor import TemporalCandidateSelector
from award_agent.intent.model_views import TemporalSelectorOutput
from award_agent.intent.openai_extractor import (
    OpenAIExtractorConfig,
    OpenAIIntentExtractor,
    TemporalSelectionError,
)
from award_agent.intent.temporal_compiler import compile_temporal_candidates
from award_agent.intent.temporal_selector import (
    plan_temporal_selection,
    restore_selector_output,
)


@runtime_checkable
class _CaptureSelector(Protocol):
    def reset_capture(self) -> None: ...

    def take_usage(self) -> dict[str, int] | None: ...


SelectorFactory = Callable[[str], TemporalCandidateSelector]


@dataclass(frozen=True)
class SelectorChallengePricing:
    """Caller-supplied token prices in USD per million tokens.

    The evaluator does not embed mutable vendor pricing.  ``snapshot`` should identify the
    owner's dated source/decision record.  Cached tokens default to zero when an adapter does
    not expose them, rather than pretending all input was cached.
    """

    input_usd_per_million: float
    output_usd_per_million: float
    cached_input_usd_per_million: float = 0.0
    snapshot: str = "caller_supplied"

    def __post_init__(self) -> None:
        if not self.snapshot:
            raise ValueError("pricing snapshot must be a non-empty identifier")
        if any(
            value < 0
            for value in (
                self.input_usd_per_million,
                self.cached_input_usd_per_million,
                self.output_usd_per_million,
            )
        ):
            raise ValueError("pricing values must be non-negative")


_PRIVATE_ARTIFACT_KEYS = frozenset(
    {
        "request",
        "reference_date",
        "timezone",
        "oracle_rationale",
        "candidate_rationales",
        "resolved_date",
        "source_start",
        "source_end",
        "canonical_id",
        "priority",
    }
)
_PRIVATE_TEXT = ("manual:", "private", "slot:", "catalog")
_RESOLVED_DATE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")


def _default_selector_factory(model: str) -> TemporalCandidateSelector:
    return OpenAIIntentExtractor(config=OpenAIExtractorConfig(model=model))


def _take_usage(selector: TemporalCandidateSelector) -> dict[str, int] | None:
    return selector.take_usage() if isinstance(selector, _CaptureSelector) else None


def _reset_capture(selector: TemporalCandidateSelector) -> None:
    if isinstance(selector, _CaptureSelector):
        selector.reset_capture()


def _selector_failure_code(exc: BaseException) -> str:
    if isinstance(exc, ValidationError):
        return "selector_parse_failed"
    if isinstance(exc, TemporalSelectionError) and (
        "no parsed" in str(exc) or "unexpected" in str(exc)
    ):
        return "selector_parse_failed"
    return "selector_call_failed"


def _record_error(record: dict[str, Any], *, stage: str, code: str) -> None:
    """Keep a stable classification without retaining exception text."""

    record.update(status="error", error_stage=stage, error_code=code)


def _metric(records: Sequence[Mapping[str, Any]], key: str) -> dict[str, float | int]:
    applicable = [record for record in records if record.get(key) is not None]
    passed = sum(bool(record.get(key)) for record in applicable)
    return {
        "runs": len(applicable),
        "passed": passed,
        "rate": passed / len(applicable) if applicable else 0.0,
    }


def _nearest_rank(values: Sequence[float], percentile: int) -> float:
    if not values:
        return 0.0
    ranked = sorted(values)
    index = max(0, (len(ranked) * percentile + 99) // 100 - 1)
    return ranked[index]


def _latency_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, float | int | str]:
    values = [float(record["latency_seconds"]) for record in records]
    return {
        "runs": len(values),
        "quantile_method": "nearest_rank",
        "total": round(sum(values), 3),
        "mean": round(sum(values) / len(values), 3) if values else 0.0,
        "p50": round(_nearest_rank(values, 50), 3),
        "p95": round(_nearest_rank(values, 95), 3),
        "p99": round(_nearest_rank(values, 99), 3),
        "max": round(max(values), 3) if values else 0.0,
    }


def _usage_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    usage_records = [record["usage"] for record in records if isinstance(record.get("usage"), Mapping)]
    attempts = sum(bool(record.get("selector_call_attempted")) for record in records)
    keys = (
        "calls",
        "captured_calls",
        "missing_calls",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "total_tokens",
    )
    return {
        "selector_call_attempts": attempts,
        "sdk_usage_captured_attempts": len(usage_records),
        "sdk_usage_missing_attempts": attempts - len(usage_records),
        **{key: sum(int(record.get(key, 0)) for record in usage_records) for key in keys},
    }


def _cost_summary(usage: Mapping[str, int], pricing: SelectorChallengePricing | None) -> dict[str, Any]:
    if pricing is None:
        return {
            "status": "not_calculated",
            "reason": "no_caller_supplied_pricing_snapshot",
        }
    cached = int(usage["cached_input_tokens"])
    input_tokens = int(usage["input_tokens"])
    output_tokens = int(usage["output_tokens"])
    non_cached = max(0, input_tokens - cached)
    cost = (
        non_cached * pricing.input_usd_per_million
        + cached * pricing.cached_input_usd_per_million
        + output_tokens * pricing.output_usd_per_million
    ) / 1_000_000
    return {
        "status": "calculated",
        "currency": "USD",
        "snapshot": pricing.snapshot,
        "rates_usd_per_million": {
            "input": pricing.input_usd_per_million,
            "cached_input": pricing.cached_input_usd_per_million,
            "output": pricing.output_usd_per_million,
        },
        "input_tokens_billed_non_cached": non_cached,
        "cached_input_tokens_billed": cached,
        "output_tokens_billed": output_tokens,
        "total_usd": round(cost, 9),
    }


def _summary(records: Sequence[Mapping[str, Any]], pricing: SelectorChallengePricing | None) -> dict[str, Any]:
    usage = _usage_summary(records)
    completed = [record for record in records if record.get("status") != "error"]
    return {
        "runs": len(records),
        "completed": len(completed),
        "errors": len(records) - len(completed),
        "parse": _metric(records, "parse_valid"),
        "membership": _metric(records, "membership_valid"),
        "compiler_completion": _metric(records, "compiler_completed"),
        "semantic_accuracy": _metric(records, "semantic_correct"),
        "latency_seconds": _latency_summary(records),
        "usage": usage,
        "cost": _cost_summary(usage, pricing),
    }


def _semantic_fingerprint(prepared: PreparedSelectorChallengeCase, selected: Sequence[str]) -> str:
    """Private in-memory comparator for variant pairing; never emitted to artifacts."""

    compiled = compile_temporal_candidates(
        prepared.surface.request,
        prepared.surface.catalog,
        selected,
        holiday_provider=StaticFrozenHolidayProvider(),
    )
    return hashlib.sha256(
        json.dumps(
            compiled.graph.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def _run_one(
    prepared: PreparedSelectorChallengeCase,
    *,
    selector: TemporalCandidateSelector,
    model: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    record: dict[str, Any] = {
        "id": prepared.identifier,
        "topology": prepared.topology,
        "subtype_id": prepared.subtype_id,
        "surface_id": prepared.surface_id,
        "order_variant": prepared.order_variant,
        "model": model,
        "repairs": 0,
        "parse_valid": False,
        "membership_valid": False,
        "compiler_completed": False,
        "semantic_correct": False,
        "selector_call_attempted": True,
    }
    try:
        response = selector.select_candidates(prepared.model_input)
        if not isinstance(response, TemporalSelectorOutput):
            response = TemporalSelectorOutput.model_validate(response)
        selected_public = response.selected_candidates
        record["parse_valid"] = True
    except Exception as exc:  # noqa: BLE001 - preserve remaining trial records
        _record_error(record, stage="selector", code=_selector_failure_code(exc))
        selected_public = []

    selected: tuple[str, ...] = ()
    if record.get("status") != "error":
        try:
            restored = restore_selector_output(
                prepared.model_input,
                TemporalSelectorOutput(selected_candidates=selected_public),
            )
            selected = (*plan_temporal_selection(prepared.surface.catalog).auto_selected, *restored)
            record["membership_valid"] = True
        except Exception:  # noqa: BLE001 - errors can contain private restoration values
            _record_error(record, stage="selection_validation", code="selector_selection_validation_failed")

    if record.get("status") != "error":
        try:
            fingerprint = _semantic_fingerprint(prepared, selected)
            record["compiler_completed"] = True
            record["semantic_correct"] = set(selected) == set(prepared.surface.oracle_candidates)
            record["status"] = "passed" if record["semantic_correct"] else "failed"
            # Only public opaque response handles cross into the artifact.
            record["selected_candidates"] = selected_public
            record["_semantic_fingerprint"] = fingerprint
        except Exception:  # noqa: BLE001 - compiler errors can disclose private IDs/slots
            _record_error(record, stage="compiler", code="selector_compiler_failed")

    record["usage"] = _take_usage(selector)
    record["latency_seconds"] = round(time.perf_counter() - started, 3)
    return record


def _group_summaries(
    records: Sequence[Mapping[str, Any]], pricing: SelectorChallengePricing | None
) -> dict[str, dict[str, dict[str, Any]]]:
    groups: dict[str, dict[str, list[Mapping[str, Any]]]] = {
        "topology": defaultdict(list),
        "subtype_id": defaultdict(list),
        "surface_id": defaultdict(list),
        "order_variant": defaultdict(list),
    }
    for record in records:
        for key, by_label in groups.items():
            by_label[str(record[key])].append(record)
    return {
        key: {label: _summary(runs, pricing) for label, runs in sorted(by_label.items())}
        for key, by_label in groups.items()
    }


def _pair_metric(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[int, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(int(record["trial"]), str(record["surface_id"]))].append(record)
    checks: list[bool] = []
    for variants in grouped.values():
        canonical = [item for item in variants if item["order_variant"] == "canonical"]
        permuted = [item for item in variants if item["order_variant"] == "permuted"]
        valid_shape = len(canonical) == 1 and len(permuted) == 1
        fingerprints = {item.get("_semantic_fingerprint") for item in variants}
        checks.append(
            valid_shape
            and all(bool(item.get("semantic_correct")) for item in variants)
            and len(fingerprints) == 1
            and None not in fingerprints
        )
    return {
        "pairs": len(grouped),
        "passed": sum(checks),
        "rate": sum(checks) / len(checks) if checks else 0.0,
    }


def _stability_metric(records: Sequence[Mapping[str, Any]], trials: int) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["id"])].append(record)
    checks: list[bool] = []
    for variants in grouped.values():
        responses = {
            tuple(item.get("selected_candidates", ()))
            for item in variants
            if item.get("status") != "error"
        }
        checks.append(
            len(variants) == trials
            and len(responses) == 1
            and all(bool(item.get("semantic_correct")) for item in variants)
        )
    return {
        "variants": len(grouped),
        "passed": sum(checks),
        "rate": sum(checks) / len(checks) if checks else 0.0,
    }


def payload_sufficiency_audit() -> dict[str, Any]:
    """Record an oracle-free, reviewable public-payload checklist.

    This intentionally avoids looking up a private oracle.  It records what a reviewer must
    inspect in the checked-in public fixture; semantic adequacy remains a human judgment, not a
    fabricated automatic proof.
    """

    return {
        "status": "manual_checklist_recorded",
        "oracle_free": True,
        "automatic_checks": {
            "fixture_preflight_required": True,
            "public_projection_only": True,
            "opaque_handle_namespaces": True,
            "candidate_summaries_present": True,
        },
        "manual_checklist": [
            "Each public candidate summary states a distinct interpretation and its local dependencies.",
            "Every endpoint distinction has a public endpoint cue or remains unresolved.",
            "Composition and dependency alternatives expose required and produced opaque slots.",
            "Unsupported alternatives make unresolved selection explicit without date arithmetic.",
            "No restricted request context, resolved calendar values, compiler oracle, or rationale appears in the payload.",
        ],
        "limitations": "Manual review records payload sufficiency; it does not claim population generalization.",
    }


def artifact_privacy_violations(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Return paths that could disclose private fixture/compiler state in an artifact."""

    violations: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_text = str(key)
                if key_text.casefold() in _PRIVATE_ARTIFACT_KEYS:
                    violations.append(f"{path}.{key_text}")
                visit(child, f"{path}.{key_text}")
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
        elif isinstance(value, str):
            lowered = value.casefold()
            # A pricing snapshot is expected to be dated.  It is not a resolved travel value.
            is_pricing_snapshot = path.endswith(".cost.snapshot")
            if any(marker in lowered for marker in _PRIVATE_TEXT) or (
                not is_pricing_snapshot and _RESOLVED_DATE.search(value)
            ):
                violations.append(path)

    visit(payload, "root")
    # Reuse the fixture scanner only when a caller embeds fixture-style scenario payloads.  The
    # artifact's audit prose necessarily uses words such as "oracle" while not containing one.
    if "scenarios" in payload:
        violations.extend(privacy_violations(payload))
    return tuple(sorted(set(violations)))


def _public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Strip in-memory comparison data before artifact privacy scanning/returning."""

    return {key: value for key, value in record.items() if not key.startswith("_")}


def run_selector_structural_challenge_eval(
    *,
    selector_model: str,
    trials: int = 1,
    fixture_path: Path = DEFAULT_SELECTOR_CHALLENGE_FIXTURE,
    control_path: Path = DEFAULT_CONTROL_FIXTURE,
    selector_factory: SelectorFactory | None = None,
    pricing: SelectorChallengePricing | None = None,
) -> dict[str, Any]:
    """Evaluate one explicit selector model against the 28 structural challenge payloads."""

    if not selector_model:
        raise ValueError("selector_model must be an explicit non-empty model ID")
    if trials < 1:
        raise ValueError("trials must be positive")
    prepared = preflight_selector_challenge_fixture(fixture_path, control_path=control_path)
    if len(prepared) != 28:
        raise AssertionError("structural challenge preflight must produce exactly 28 cases")
    selector = (selector_factory or _default_selector_factory)(selector_model)
    private_records: list[dict[str, Any]] = []
    for trial in range(1, trials + 1):
        for item in prepared:
            _reset_capture(selector)
            record = _run_one(item, selector=selector, model=selector_model)
            record["trial"] = trial
            private_records.append(record)

    overall = _summary(private_records, pricing)
    pair = _pair_metric(private_records)
    stability = _stability_metric(private_records, trials)
    public_records = [_public_record(record) for record in private_records]
    audit = payload_sufficiency_audit()
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "evaluation": "selector_structural_challenge",
        "scope": "structural_safety_screen_not_a_generalization_claim",
        "selector": {"model": selector_model, "calls_expected": len(prepared) * trials},
        "fixture": {
            "path": str(fixture_path),
            "sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
            "control_path": str(control_path),
            "control_sha256": hashlib.sha256(control_path.read_bytes()).hexdigest(),
            "scenario_count": len(prepared),
            "surface_count": len({item.surface_id for item in prepared}),
            "topology_count": len({item.topology for item in prepared}),
            "variants": ["canonical", "permuted"],
        },
        "trials": trials,
        "payload_sufficiency_audit": audit,
        "summary": {
            "overall": overall,
            "by_dimension": _group_summaries(private_records, pricing),
            "pair_equivalence": pair,
            "stability": stability,
            "repairs": {"attempts": 0, "zero_repairs": True},
        },
        "results": public_records,
    }
    artifact["privacy"] = {
        "checked": True,
        "violations": list(artifact_privacy_violations(artifact)),
    }
    exact_checks = {
        "parse": overall["parse"]["rate"] == 1.0,
        "semantic": overall["semantic_accuracy"]["rate"] == 1.0,
        "membership": overall["membership"]["rate"] == 1.0,
        "compiler": overall["compiler_completion"]["rate"] == 1.0,
        "pair_equivalence": pair["rate"] == 1.0,
        "stability": stability["rate"] == 1.0,
        "zero_repairs": all(record["repairs"] == 0 for record in private_records),
        "privacy": not artifact["privacy"]["violations"],
    }
    artifact["summary"]["exact_gate"] = {
        "kind": "all_observed_structural_cases_must_pass",
        "checks": exact_checks,
        "passed": all(exact_checks.values()),
        "note": "No confidence interval or population-generalization claim is made by this gate.",
    }
    return artifact


__all__ = [
    "SelectorChallengePricing",
    "artifact_privacy_violations",
    "payload_sufficiency_audit",
    "run_selector_structural_challenge_eval",
]
