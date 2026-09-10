"""Paired, redacted live experiment for ADR 0014's composer model choice.

The experiment replays a frozen set of already-authoritative composer inputs.
It deliberately has no receiver, session, reducer, or mutable request state.
Raw prompts and model responses are retained only in private trace sidecars.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from math import sqrt
from pathlib import Path
from random import Random
from time import perf_counter
from typing import Any
from uuid import uuid4

import yaml

from award_agent.clarification.composer import (
    ClarificationPromptComposer,
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
)
from award_agent.clarification.openai_composer import (
    DEFAULT_CLARIFICATION_COMPOSER_MODEL,
    GPT_4O_MINI_CLARIFICATION_COMPOSER_MODEL,
    OpenAIClarificationComposerConfig,
    OpenAIClarificationPromptComposer,
)
from award_agent.domain import BlockingRequirement, ClarificationIssue
from award_agent.observability.llm_trace import write_eval_llm_trace

DEFAULT_COMPOSER_EXPERIMENT_FIXTURES = Path("evals/clarification/composer_inputs_v1.yaml")
DEFAULT_COMPOSER_EXPERIMENT_TRACE_DIR = Path("evals/clarification/traces-composer-experiment")
EVALUATOR_VERSION = "clarification_composer_experiment_v1"
_ARMS = ("luna", "gpt_4o_mini")
_USAGE_KEYS = (
    "calls",
    "captured_calls",
    "missing_calls",
    "input_tokens",
    "output_tokens",
    "total_tokens",
)


class ClarificationComposerExperimentError(ValueError):
    """The frozen composer-input fixture is not fit for a paired experiment."""


def _load_bundles(path: Path) -> tuple[list[ClarificationPromptComposerInput], bytes]:
    try:
        raw = path.read_bytes()
        payload = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise ClarificationComposerExperimentError("unable to load composer experiment fixture") from exc
    if not isinstance(payload, Mapping) or payload.get("contract_version") != "v1":
        raise ClarificationComposerExperimentError("composer experiment fixture must use contract_version v1")
    bundles = payload.get("bundles")
    if not isinstance(bundles, list) or len(bundles) < 8:
        raise ClarificationComposerExperimentError("composer experiment needs at least eight frozen bundles")
    identifiers: set[str] = set()
    prepared: list[ClarificationPromptComposerInput] = []
    issue_kinds: set[str] = set()
    for item in bundles:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ClarificationComposerExperimentError("each composer bundle needs a non-empty ID")
        identifier = str(item["id"])
        if identifier in identifiers:
            raise ClarificationComposerExperimentError("composer bundle IDs must be unique")
        identifiers.add(identifier)
        try:
            composed = ClarificationPromptComposerInput(
                requirements=tuple(BlockingRequirement.model_validate(value) for value in item["requirements"]),
                issues=tuple(ClarificationIssue.model_validate(value) for value in item["issues"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ClarificationComposerExperimentError("invalid frozen composer input bundle") from exc
        issue_kinds.update(issue.kind.value for issue in composed.issues)
        prepared.append(composed)
    if issue_kinds != {"missing", "ambiguous", "unsupported", "conflict"}:
        raise ClarificationComposerExperimentError(
            "composer experiment bundles must cover missing, ambiguous, unsupported, and conflict issues"
        )
    return prepared, raw


def _usage_and_traces(adapter: object | None) -> tuple[dict[str, int], list[dict[str, Any]]]:
    if adapter is None:
        return ({key: 0 for key in _USAGE_KEYS}, [])
    try:
        traceable = adapter  # Protocol is runtime-free; failures become evaluation failures below.
        usage = traceable.take_usage() or {}  # type: ignore[attr-defined]
        traces = traceable.take_call_traces()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - a broken diagnostic path is never hidden.
        return ({key: 0 for key in _USAGE_KEYS}, [])
    return ({key: int(usage.get(key, 0)) for key in _USAGE_KEYS}, list(traces))


def _quality_failures(
    input: ClarificationPromptComposerInput,
    composition: ClarificationPromptComposition,
) -> list[str]:
    """Small, disclosed proxy checks; naturalness remains human-reviewed."""

    failures: list[str] = []
    questions = [item.question.strip() for item in composition.question_items]
    if any(not question.endswith("?") for question in questions):
        failures.append("question_missing_question_mark")
    if len({question.casefold() for question in questions}) != len(questions):
        failures.append("duplicate_question_copy")
    question_by_requirement = {
        item.requirement_id: item.question.casefold() for item in composition.question_items
    }
    cues = {
        "origin": ("from", "departure", "airport", "where"),
        "destination": ("destination", "go", "where"),
        "departure": ("leave", "depart", "date", "when", "timing"),
        "return_or_duration": ("return", "trip", "long", "duration", "week", "day"),
        "travelers": ("traveler", "people", "passenger", "many"),
        "conflict": ("choose", "which", "conflict", "date"),
    }
    kinds = {item.requirement_id: item.kind.value for item in input.requirements}
    for requirement_id, question in question_by_requirement.items():
        if not any(cue in question for cue in cues[kinds[requirement_id]]):
            failures.append(f"missing_requirement_specific_cue:{requirement_id}")
    return failures


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def _paired_normal_ci(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {"pairs": 0, "mean": None, "lower_95": None, "upper_95": None}
    mean = sum(values) / len(values)
    if len(values) == 1:
        return {"pairs": 1, "mean": mean, "lower_95": None, "upper_95": None}
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    margin = 1.96 * sqrt(variance / len(values))
    return {"pairs": len(values), "mean": mean, "lower_95": mean - margin, "upper_95": mean + margin}


def run_clarification_composer_experiment(
    *,
    luna_model: str = DEFAULT_CLARIFICATION_COMPOSER_MODEL,
    gpt_4o_mini_model: str = GPT_4O_MINI_CLARIFICATION_COMPOSER_MODEL,
    trials: int = 3,
    fixture_path: Path = DEFAULT_COMPOSER_EXPERIMENT_FIXTURES,
    trace_dir: Path = DEFAULT_COMPOSER_EXPERIMENT_TRACE_DIR,
    seed: int = 20260910,
    composer_factory: Callable[[str], ClarificationPromptComposer] | None = None,
) -> dict[str, Any]:
    """Replay each frozen input against both arms in a randomized paired order."""

    if trials < 3:
        raise ValueError("composer experiment requires at least three trials per bundle")
    bundles, raw = _load_bundles(fixture_path)
    make_composer = composer_factory or (
        lambda model: OpenAIClarificationPromptComposer(
            OpenAIClarificationComposerConfig(model=model), capture_llm_io=True
        )
    )
    models = {"luna": luna_model, "gpt_4o_mini": gpt_4o_mini_model}
    generated_at = datetime.now(UTC).isoformat()
    trace_run_dir = trace_dir / f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    rng = Random(seed)
    records: list[dict[str, Any]] = []
    pair_values: dict[tuple[int, int], dict[str, dict[str, float]]] = defaultdict(dict)
    for trial in range(1, trials + 1):
        for bundle_index, input in enumerate(bundles, start=1):
            order = list(_ARMS)
            rng.shuffle(order)
            for order_index, arm in enumerate(order):
                adapter: ClarificationPromptComposer | None = None
                composition: ClarificationPromptComposition | None = None
                error_type: str | None = None
                started = perf_counter()
                try:
                    adapter = make_composer(models[arm])
                    composition = adapter.compose(input)
                except Exception as exc:  # noqa: BLE001 - explicit invalid/error output is a result.
                    error_type = type(exc).__name__
                wall_latency = perf_counter() - started
                usage, traces = _usage_and_traces(adapter)
                trace_latency = sum(float(trace.get("latency_seconds") or 0.0) for trace in traces)
                quality_failures = [] if composition is None else _quality_failures(input, composition)
                valid = composition is not None and error_type is None
                reconciled = (
                    usage["calls"] == len(traces)
                    and usage["captured_calls"] == len(traces)
                    and usage["missing_calls"] == 0
                    and not any(trace.get("error") is not None for trace in traces)
                )
                record = {
                    "bundle_index": bundle_index,
                    "trial": trial,
                    "arm": arm,
                    "order_index": order_index,
                    "valid_complete_coverage": valid,
                    "issue_linkage_correct": valid,
                    "invalid_or_error": not valid,
                    "quality_validator_failures": quality_failures,
                    "human_quality_review_required": valid,
                    "trace_reconciled": reconciled,
                    "latency_seconds": trace_latency if trace_latency else wall_latency,
                    "usage": usage,
                    "error_type": error_type,
                }
                # Sidecars identify a synthetic bundle index and arm only; exact
                # structured input/output stays private to the local trace tree.
                write_eval_llm_trace(
                    trace_run_dir,
                    scenario={"id": f"bundle-{bundle_index}-{arm}", "input": input.model_input()},
                    record=record,
                    calls=traces,
                )
                records.append(record)
                pair_values[(trial, bundle_index)][arm] = {
                    "valid": float(valid),
                    "linkage": float(valid),
                    "latency": float(record["latency_seconds"]),
                    "tokens": float(usage["total_tokens"]),
                }
    arm_summary: dict[str, dict[str, Any]] = {}
    for arm in _ARMS:
        arm_records = [record for record in records if record["arm"] == arm]
        total = len(arm_records)
        arm_summary[arm] = {
            "model": models[arm],
            "calls": total,
            "valid_complete_coverage": sum(bool(record["valid_complete_coverage"]) for record in arm_records),
            "issue_linkage_correct": sum(bool(record["issue_linkage_correct"]) for record in arm_records),
            "invalid_or_error": sum(bool(record["invalid_or_error"]) for record in arm_records),
            "quality_validator_failures": sum(len(record["quality_validator_failures"]) for record in arm_records),
            "human_quality_review_required": sum(bool(record["human_quality_review_required"]) for record in arm_records),
            "trace_reconciliation_failures": sum(not bool(record["trace_reconciled"]) for record in arm_records),
            "latency_seconds": {
                "p50": _percentile([float(record["latency_seconds"]) for record in arm_records], 0.50),
                "p95": _percentile([float(record["latency_seconds"]) for record in arm_records], 0.95),
            },
            "tokens": {key: sum(int(record["usage"][key]) for record in arm_records) for key in _USAGE_KEYS},
            "cost": None,
        }
    paired = [value for value in pair_values.values() if set(value) == set(_ARMS)]
    paired_analysis = {
        "valid_complete_coverage_mini_minus_luna": _paired_normal_ci(
            [pair["gpt_4o_mini"]["valid"] - pair["luna"]["valid"] for pair in paired]
        ),
        "issue_linkage_mini_minus_luna": _paired_normal_ci(
            [pair["gpt_4o_mini"]["linkage"] - pair["luna"]["linkage"] for pair in paired]
        ),
        "latency_seconds_mini_minus_luna": _paired_normal_ci(
            [pair["gpt_4o_mini"]["latency"] - pair["luna"]["latency"] for pair in paired]
        ),
        "tokens_mini_minus_luna": _paired_normal_ci(
            [pair["gpt_4o_mini"]["tokens"] - pair["luna"]["tokens"] for pair in paired]
        ),
    }
    return {
        "schema_version": "clarification_composer_experiment_v1",
        "fixture": {"sha256": sha256(raw).hexdigest(), "bundle_count": len(bundles), "redacted": True},
        "models": {arm: models[arm] for arm in _ARMS},
        "trials": trials,
        "randomization": {"seed": seed, "method": "per-pair shuffled arm order"},
        "generated_at": generated_at,
        "llm_trace": {"mode": "all_calls_private", "directory": str(trace_run_dir), "sidecars": len(records)},
        "summary": {
            "evaluator_version": EVALUATOR_VERSION,
            "arms": arm_summary,
            "paired_analysis": paired_analysis,
            "human_review": "required before a model-selection decision; no automatic naturalness score is claimed",
            "decision": "not_decided_by_evaluator",
        },
    }


__all__ = [
    "DEFAULT_COMPOSER_EXPERIMENT_FIXTURES",
    "DEFAULT_COMPOSER_EXPERIMENT_TRACE_DIR",
    "ClarificationComposerExperimentError",
    "run_clarification_composer_experiment",
]
