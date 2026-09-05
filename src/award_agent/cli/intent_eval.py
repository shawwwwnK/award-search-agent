"""Run and score the ready live-model intent evaluation corpus."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from dotenv import load_dotenv

from award_agent.domain import RawRequest, RequestContext, RequestUnderstandingResult
from award_agent.experiments.one_pass_intent import OnePassIntentExperiment
from award_agent.intent.evidence import (
    TemporalEvidenceValidationError,
    TemporalResolutionValidationError,
)
from award_agent.intent.evidence_eval import (
    compile_evidence_expectations,
    evaluate_evidence_support,
)
from award_agent.intent.holidays import NagerHolidayProvider
from award_agent.intent.openai_extractor import (
    DateResolutionError,
    IntentExtractionError,
    NonTemporalExtractionError,
    OpenAIExtractorConfig,
    OpenAIIntentExtractor,
    TemporalSelectionError,
)
from award_agent.intent.temporal_compiler import TemporalCandidateValidationError
from award_agent.intent.temporal_selector import (
    DEFAULT_TEMPORAL_SELECTOR_POLICY,
    TemporalSelectorPolicy,
    TemporalSelectorValidationError,
)
from award_agent.intent.workflow import understand_request
from award_agent.observability.llm_trace import write_eval_llm_trace

DEFAULT_LLM_TRACE_DIR = Path("evals/intent/traces")


class _EvalArgumentParser(argparse.ArgumentParser):
    """Reject model-stage combinations that cannot run under the selected strategy."""

    def parse_args(self, args: Any = None, namespace: Any = None) -> Any:
        parsed = super().parse_args(args, namespace)
        error = _strategy_model_error(
            parsed.strategy,
            parsed.pass_one_model,
            parsed.pass_two_model,
            parsed.selector_model,
            parsed.selector_policy,
        )
        if error is not None:
            self.error(error)
        return parsed


def _strategy_model_error(
    strategy: str,
    pass_one_model: str | None,
    pass_two_model: str | None,
    selector_model: str | None,
    selector_policy: str = DEFAULT_TEMPORAL_SELECTOR_POLICY,
) -> str | None:
    """Return the stable incompatibility message shared by CLI and direct callers."""

    if selector_policy not in {"ambiguous_only", "supported_or_unresolved"}:
        return f"unsupported selector policy: {selector_policy}"
    if strategy == "compiler_select_v1":
        if pass_two_model is not None:
            return "--pass-two-model is only compatible with --strategy two_pass"
        if selector_policy == "supported_or_unresolved" and selector_model is None:
            return (
                "--selector-model is required when "
                "--selector-policy supported_or_unresolved"
            )
        return None
    if strategy == "two_pass":
        if selector_model is not None:
            return "--selector-model is only compatible with --strategy compiler_select_v1"
        if selector_policy != DEFAULT_TEMPORAL_SELECTOR_POLICY:
            return "--selector-policy is only compatible with --strategy compiler_select_v1"
        return None
    if strategy == "one_pass":
        if selector_policy != DEFAULT_TEMPORAL_SELECTOR_POLICY:
            return "--selector-policy is only compatible with --strategy compiler_select_v1"
        supplied = [
            flag
            for flag, value in (
                ("--pass-one-model", pass_one_model),
                ("--pass-two-model", pass_two_model),
                ("--selector-model", selector_model),
            )
            if value is not None
        ]
        if supplied:
            return f"{' '.join(supplied)} is incompatible with --strategy one_pass"
        return None
    return f"unsupported eval strategy: {strategy}"


def _parser() -> argparse.ArgumentParser:
    parser = _EvalArgumentParser(description="Run the ready intent-evaluation scenarios.")
    parser.add_argument("--model", required=True, help="OpenAI model ID to evaluate")
    parser.add_argument(
        "--pass-one-model",
        default=None,
        help="Optional model override for Pass 1; defaults to --model",
    )
    parser.add_argument(
        "--pass-two-model",
        default=None,
        help="Optional model override for Pass 2; defaults to --model",
    )
    parser.add_argument(
        "--selector-model",
        default=None,
        help=(
            "Optional independently configured compiler temporal-selector model; "
            "enables selector calls only for compiler ambiguities"
        ),
    )
    parser.add_argument(
        "--selector-policy",
        choices=("ambiguous_only", "supported_or_unresolved"),
        default=DEFAULT_TEMPORAL_SELECTOR_POLICY,
        help=(
            "Compiler selector policy; supported_or_unresolved is experiment-only and "
            "asks the selector to choose supported interpretations versus unresolved"
        ),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("evals/intent/cases.yaml"),
        help="YAML scenario corpus",
    )
    parser.add_argument("--output", required=True, type=Path, help="Baseline JSON output path")
    parser.add_argument("--trials", type=int, default=1, help="Runs per ready scenario")
    parser.add_argument(
        "--strategy",
        choices=("two_pass", "compiler_select_v1", "one_pass"),
        default="two_pass",
        help="Workflow arm to evaluate",
    )
    parser.add_argument(
        "--trace-dir",
        type=Path,
        default=DEFAULT_LLM_TRACE_DIR,
        help=(
            "Directory for per-case LLM call sidecars; non-passing cases are captured by default"
        ),
    )
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="Disable local LLM call sidecars for this eval run",
    )
    parser.add_argument(
        "--trace-all-calls",
        action="store_true",
        help="With tracing enabled, capture calls for passing cases too",
    )
    return parser


def _record_check(
    checks: list[dict[str, Any]],
    name: str,
    expected: Any,
    actual: Any,
    passed: bool,
    *,
    blocking: bool = True,
) -> None:
    check = {"name": name, "passed": passed, "expected": expected, "actual": actual}
    if not blocking:
        check["blocking"] = False
    checks.append(check)


def _location_matches(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    accepted_values = expected.get("accepted_values")
    exact_fields = {key: value for key, value in expected.items() if key != "accepted_values"}
    if not all(actual.get(key) == value for key, value in exact_fields.items()):
        return False
    if accepted_values is None:
        return True
    if (
        not isinstance(accepted_values, list)
        or not accepted_values
        or not all(isinstance(value, str) and value for value in accepted_values)
    ):
        raise ValueError("location accepted_values must be a non-empty list of strings")
    return actual.get("value") in accepted_values


def _partial_mapping_matches(actual: Any, expected: Any) -> bool:
    """Match semantic invariants without requiring evidence-span segmentation equality."""

    if isinstance(expected, Mapping):
        return isinstance(actual, Mapping) and all(
            key in actual and _partial_mapping_matches(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and all(
            any(_partial_mapping_matches(candidate, wanted) for candidate in actual)
            for wanted in expected
        )
    return bool(actual == expected)


def _score_result(
    expected: Mapping[str, Any], result: RequestUnderstandingResult
) -> list[dict[str, Any]]:
    parsed = result.parsed_request
    actual = result.model_dump(mode="json")
    parsed_actual = actual["parsed_request"]
    checks: list[dict[str, Any]] = []

    if "travelers" in expected:
        _record_check(
            checks,
            "travelers",
            expected["travelers"],
            parsed.travelers,
            parsed.travelers == expected["travelers"],
        )

    for singular, plural in (("origin", "origins"), ("destination", "destinations")):
        if singular in expected:
            expected_location = expected[singular]
            actual_locations = parsed_actual[plural]
            _record_check(
                checks,
                singular,
                expected_location,
                actual_locations,
                any(_location_matches(item, expected_location) for item in actual_locations),
            )

    if "destinations" in expected:
        expected_locations = expected["destinations"]
        actual_locations = parsed_actual["destinations"]
        passed = len(actual_locations) == len(expected_locations) and all(
            any(_location_matches(item, wanted) for item in actual_locations)
            for wanted in expected_locations
        )
        _record_check(checks, "destinations", expected_locations, actual_locations, passed)

    if "cabin" in expected:
        _record_check(
            checks,
            "cabin",
            expected["cabin"],
            parsed_actual["cabins"],
            expected["cabin"] in parsed_actual["cabins"],
        )

    if "search_modes" in expected:
        wanted_modes = sorted(expected["search_modes"])
        actual_modes = sorted(parsed_actual["search_modes"])
        _record_check(
            checks, "search_modes", wanted_modes, actual_modes, wanted_modes == actual_modes
        )

    if "repositioning_allowed" in expected:
        wanted = expected["repositioning_allowed"]
        _record_check(
            checks,
            "repositioning_allowed",
            wanted,
            parsed.repositioning_allowed,
            wanted == parsed.repositioning_allowed,
        )

    for expected_name, actual_name in (
        ("departure_window", "departure_window"),
        ("return_window", "return_window"),
    ):
        if expected_name not in expected:
            continue
        wanted = expected[expected_name]
        window = parsed_actual[actual_name]
        observed = None if window is None else {"start": window["start"], "end": window["end"]}
        _record_check(checks, expected_name, wanted, observed, wanted == observed)

    if "interpreted_duration" in expected:
        resolution = parsed_actual["date_resolution"]
        duration = None if resolution is None else resolution["interpreted_duration"]
        observed = (
            None
            if duration is None
            else {
                "minimum_days": duration["minimum_days"],
                "maximum_days": duration["maximum_days"],
            }
        )
        wanted = expected["interpreted_duration"]
        _record_check(checks, "interpreted_duration", wanted, observed, wanted == observed)

    if "temporal_relations" in expected:
        relations = parsed_actual.get("temporal_relations") or {"constraints": []}
        actual_constraints = relations["constraints"]
        wanted_constraints = expected["temporal_relations"]
        _record_check(
            checks,
            "temporal_relations",
            wanted_constraints,
            actual_constraints,
            _partial_mapping_matches(actual_constraints, wanted_constraints),
        )

    if "literal_duration" in expected:
        relations = parsed_actual.get("temporal_relations") or {"constraints": []}
        durations = [item for item in relations["constraints"] if item.get("kind") == "duration"]
        wanted_duration = expected["literal_duration"]
        _record_check(
            checks,
            "literal_duration",
            wanted_duration,
            durations,
            any(_partial_mapping_matches(item, wanted_duration) for item in durations),
        )

    if "unknowns" in expected:
        wanted_unknowns = set(expected["unknowns"])
        actual_unknowns = {item["field"] for item in parsed_actual["unknowns"]}
        _record_check(
            checks,
            "unknowns",
            sorted(wanted_unknowns),
            sorted(actual_unknowns),
            wanted_unknowns <= actual_unknowns,
        )

    if "conflicts" in expected:
        wanted_conflicts = sorted(expected["conflicts"])
        actual_conflicts = sorted(item["code"] for item in parsed_actual["conflicts"])
        _record_check(
            checks,
            "conflicts",
            wanted_conflicts,
            actual_conflicts,
            wanted_conflicts == actual_conflicts,
        )

    if "clarification" in expected:
        wanted_clarification = expected["clarification"]
        actual_clarification = actual["clarification"]
        passed = all(
            actual_clarification.get(key) == value for key, value in wanted_clarification.items()
        )
        _record_check(
            checks,
            "clarification",
            wanted_clarification,
            actual_clarification,
            passed,
        )

    extraction = parsed_actual["temporal_extraction"] or {}
    if "date_anchor" in expected:
        wanted_anchor = dict(expected["date_anchor"])
        explicit_year = wanted_anchor.pop("explicit_year", "not_checked")
        anchors = extraction.get("date_anchors", [])
        matching = [item for item in anchors if _location_matches(item, wanted_anchor)]
        passed = bool(matching)
        if explicit_year != "not_checked":
            passed = passed and any(item.get("year") == explicit_year for item in matching)
        _record_check(checks, "date_anchor", expected["date_anchor"], anchors, passed)

    if "forbidden_date_anchor_kinds" in expected:
        forbidden = set(expected["forbidden_date_anchor_kinds"])
        anchors = extraction.get("date_anchors", [])
        forbidden_observed = sorted({item["kind"] for item in anchors if item["kind"] in forbidden})
        _record_check(
            checks,
            "forbidden_date_anchor_kinds",
            [],
            forbidden_observed,
            not forbidden_observed,
        )

    if "temporal_phrases" in expected:
        raise ValueError("exact temporal_phrases scoring was removed; use evidence_expectations")

    if "evidence_expectations" in expected:
        compiled = compile_evidence_expectations(
            parsed.raw_text,
            expected["evidence_expectations"],
        )
        evidence_result = evaluate_evidence_support(
            parsed.raw_text,
            parsed.temporal_evidence,
            compiled,
        )
        evidence_actual = evidence_result.model_dump(mode="json")
        _record_check(
            checks,
            "grounding_valid",
            True,
            evidence_result.grounding_valid,
            evidence_result.grounding_valid,
        )
        _record_check(
            checks,
            "evidence_support_valid",
            True,
            evidence_actual,
            evidence_result.evidence_support_valid,
        )
        _record_check(
            checks,
            "preferred_boundary_exact_match",
            True,
            evidence_result.preferred_boundary_exact_match,
            evidence_result.preferred_boundary_exact_match,
            blocking=False,
        )

    if "resolved_anchor" in expected:
        wanted_anchor = expected["resolved_anchor"]
        resolved = parsed_actual["resolved_date_anchors"]
        passed = any(
            item["anchor"].get("holiday") == wanted_anchor.get("holiday")
            and item["start"] == wanted_anchor.get("date")
            for item in resolved
        )
        _record_check(checks, "resolved_anchor", wanted_anchor, resolved, passed)

    return checks


def _load_ready_scenarios(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text())
    scenarios = payload.get("scenarios") if isinstance(payload, dict) else None
    if not isinstance(scenarios, list):
        raise TypeError("eval corpus must contain a scenarios list")
    ready = [scenario for scenario in scenarios if scenario.get("status") == "ready"]
    for scenario in ready:
        expected = scenario.get("expected", {})
        if "temporal_phrases" in expected:
            raise ValueError(
                f"scenario {scenario.get('id')!r} uses removed temporal_phrases scoring"
            )
        if "evidence_expectations" in expected:
            compile_evidence_expectations(
                str(scenario["input"]).strip(),
                expected["evidence_expectations"],
            )
        if "literal_duration" in expected:
            literal = expected["literal_duration"]
            required = {
                "stated_minimum_quantity",
                "stated_maximum_quantity",
                "unit",
                "modifier",
            }
            if not isinstance(literal, Mapping) or set(literal) != required:
                raise ValueError(
                    f"scenario {scenario.get('id')!r} has an invalid literal_duration contract"
                )
            if literal["stated_maximum_quantity"] < literal["stated_minimum_quantity"]:
                raise ValueError(
                    f"scenario {scenario.get('id')!r} has reversed literal duration quantities"
                )
        if "forbidden_date_anchor_kinds" in expected:
            forbidden = expected["forbidden_date_anchor_kinds"]
            allowed = {"exact_date", "month", "holiday"}
            if (
                not isinstance(forbidden, list)
                or not forbidden
                or any(kind not in allowed for kind in forbidden)
            ):
                raise ValueError(
                    f"scenario {scenario.get('id')!r} has invalid forbidden anchor kinds"
                )
    return ready


def _hard_checks_pass(checks: Sequence[Mapping[str, Any]]) -> bool:
    return all(check["passed"] or check.get("blocking") is False for check in checks)


def _evaluation_summary(checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_name = {str(check["name"]): check for check in checks}
    semantic_names = {
        "travelers",
        "origin",
        "destination",
        "destinations",
        "cabin",
        "search_modes",
        "repositioning_allowed",
        "unknowns",
        "date_anchor",
        "forbidden_date_anchor_kinds",
        "temporal_relations",
        "literal_duration",
    }
    deterministic_names = {
        "departure_window",
        "return_window",
        "interpreted_duration",
        "conflicts",
        "resolved_anchor",
    }

    def category_valid(names: set[str]) -> bool:
        selected = [check for check in checks if check["name"] in names]
        return all(bool(check["passed"]) for check in selected)

    evidence_diagnostics = by_name.get("evidence_support_valid", {}).get("actual", {})
    return {
        "schema_valid": True,
        "grounding_valid": bool(by_name.get("grounding_valid", {}).get("passed", True)),
        "semantic_fields_valid": category_valid(semantic_names),
        "evidence_support_valid": bool(
            by_name.get("evidence_support_valid", {}).get("passed", True)
        ),
        "deterministic_outputs_valid": category_valid(deterministic_names),
        "preferred_boundary_exact_match": bool(
            by_name.get("preferred_boundary_exact_match", {}).get("passed", True)
        ),
        "missing_expected_claims": evidence_diagnostics.get("missing_expected_claims", []),
        "unsupported_claims": evidence_diagnostics.get("unsupported_claims", []),
        "overbroad_spans": evidence_diagnostics.get("overbroad_spans", []),
        "insufficient_spans": evidence_diagnostics.get("insufficient_spans", []),
    }


def _repair_attempt_summary(
    repair_trace: Mapping[str, Any] | None,
    *,
    completed: bool,
) -> dict[str, int | bool]:
    """Flatten successful-workflow repair traces into stable evaluator counters."""

    traces = (
        []
        if repair_trace is None
        else [
            trace
            for name in ("pass_one", "pass_two")
            if isinstance((trace := repair_trace.get(name)), Mapping)
        ]
    )
    if not traces and isinstance(repair_trace, Mapping):
        traces = [repair_trace]
    return {
        "first_attempt_completed": completed
        and (not traces or all(bool(trace.get("first_attempt_valid")) for trace in traces)),
        "repair_attempts": sum(bool(trace.get("repair_ran")) for trace in traces),
        "repair_successes": sum(bool(trace.get("repair_succeeded")) for trace in traces),
    }


def _failure_flags(record: Mapping[str, Any]) -> set[str]:
    """Classify independently useful failure dimensions without collapsing root causes."""

    flags: set[str] = set()
    stage = record.get("failure_stage")
    if isinstance(stage, str):
        if stage.startswith("pass_one_") or stage == "compiler_non_temporal_pass_one":
            flags.add("pass_one_failures")
        if stage == "temporal_candidate_selector":
            flags.add("selector_failures")
        if stage == "pass_two_wire_conversion":
            flags.add("pass_two_wire_failures")
        if stage in {"pass_two_conformance", "pass_two_dependency_validation"}:
            flags.add("semantic_validation_failures")
        if stage == "deterministic_evaluation":
            flags.add("deterministic_output_failures")
        if stage == "pass_one_grounding":
            flags.add("grounding_failures")

    evaluation = record.get("evaluation")
    if stage is None and isinstance(evaluation, Mapping):
        if not bool(evaluation.get("grounding_valid", True)):
            flags.add("grounding_failures")
        if not bool(evaluation.get("semantic_fields_valid", True)):
            flags.add("semantic_validation_failures")
        if not bool(evaluation.get("deterministic_outputs_valid", True)):
            flags.add("deterministic_output_failures")

    checks = record.get("checks")
    if isinstance(checks, Sequence) and any(
        isinstance(check, Mapping)
        and check.get("name") == "clarification"
        and not bool(check.get("passed"))
        for check in checks
    ):
        flags.add("clarification_failures")
    return flags


def _aggregate_results(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build completion, repair, and owning-stage metrics for a run matrix."""

    completed = [item for item in results if "output" in item]
    first_attempt_completed = sum(
        bool((item.get("attempts") or {}).get("first_attempt_completed")) for item in completed
    )
    repair_attempts = sum(
        int((item.get("attempts") or {}).get("repair_attempts", 0)) for item in results
    )
    repair_successes = sum(
        int((item.get("attempts") or {}).get("repair_successes", 0)) for item in results
    )
    failure_flags = [_failure_flags(item) for item in results]
    run_count = len(results)
    return {
        "first_attempt_completion": {
            "runs": first_attempt_completed,
            "rate": first_attempt_completed / run_count if run_count else 0.0,
        },
        "final_completion": {
            "runs": len(completed),
            "rate": len(completed) / run_count if run_count else 0.0,
        },
        "repair_attempts": repair_attempts,
        "repair_successes": repair_successes,
        "pass_one_failures": sum("pass_one_failures" in flags for flags in failure_flags),
        "selector_failures": sum("selector_failures" in flags for flags in failure_flags),
        "pass_two_wire_failures": sum("pass_two_wire_failures" in flags for flags in failure_flags),
        "grounding_failures": sum("grounding_failures" in flags for flags in failure_flags),
        "semantic_validation_failures": sum(
            "semantic_validation_failures" in flags for flags in failure_flags
        ),
        "deterministic_output_failures": sum(
            "deterministic_output_failures" in flags for flags in failure_flags
        ),
        "clarification_failures": sum("clarification_failures" in flags for flags in failure_flags),
    }


def _usage_summary(results: Sequence[Mapping[str, Any]]) -> dict[str, int] | str:
    usage_records = [item["usage"] for item in results if item.get("usage") is not None]
    if not usage_records:
        return "unavailable: SDK responses did not provide usage"
    return {
        "captured_runs": len(usage_records),
        "missing_runs": len(results) - len(usage_records),
        "input_tokens": sum(item.get("input_tokens", 0) for item in usage_records),
        "output_tokens": sum(item.get("output_tokens", 0) for item in usage_records),
        "total_tokens": sum(
            item.get(
                "total_tokens",
                item.get("input_tokens", 0) + item.get("output_tokens", 0),
            )
            for item in usage_records
        ),
        "calls": sum(item.get("calls", 1) for item in usage_records),
        "captured_calls": sum(item.get("captured_calls", 1) for item in usage_records),
        "missing_calls": sum(item.get("missing_calls", 0) for item in usage_records),
    }


def _combine_usage(*usage_records: Mapping[str, int] | None) -> dict[str, int] | None:
    """Combine usage from split model passes for one evaluated workflow run."""

    captured = [item for item in usage_records if item is not None]
    if not captured:
        return None
    return {
        "calls": sum(item.get("calls", 0) for item in captured),
        "captured_calls": sum(item.get("captured_calls", 0) for item in captured),
        "missing_calls": sum(item.get("missing_calls", 0) for item in captured),
        "input_tokens": sum(item.get("input_tokens", 0) for item in captured),
        "output_tokens": sum(item.get("output_tokens", 0) for item in captured),
        "total_tokens": sum(item.get("total_tokens", 0) for item in captured),
    }


def _combine_call_traces(
    *trace_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Preserve pass order while assigning one run-level call sequence."""

    combined: list[dict[str, Any]] = []
    for trace_record in trace_records:
        combined.extend(dict(trace) for trace in trace_record)
    for sequence, trace in enumerate(combined, start=1):
        trace["sequence"] = sequence
    return combined


_STAGE_NAMES = ("pass_one", "selector", "pass_two", "one_pass")


def _stage_configuration(
    strategy: str,
    *,
    model: str,
    pass_one_model: str | None,
    pass_two_model: str | None,
    selector_model: str | None,
    selector_policy: TemporalSelectorPolicy,
) -> dict[str, dict[str, bool | str | None]]:
    """Describe the model boundaries intentionally constructed for an eval strategy."""

    configured_models: dict[str, str | None] = {
        "pass_one": (pass_one_model or model)
        if strategy in {"two_pass", "compiler_select_v1"}
        else None,
        "selector": selector_model if strategy == "compiler_select_v1" else None,
        "pass_two": (pass_two_model or model) if strategy == "two_pass" else None,
        "one_pass": model if strategy == "one_pass" else None,
    }
    return {
        stage: {
            "enabled": configured_models[stage] is not None,
            "configured": configured_models[stage] is not None,
            "model": configured_models[stage],
            "selector_policy": (
                selector_policy if stage == "selector" and strategy == "compiler_select_v1" else None
            ),
        }
        for stage in _STAGE_NAMES
    }


def _stage_telemetry(
    configuration: Mapping[str, Mapping[str, bool | str | None]],
    *,
    calls_by_stage: Mapping[str, Sequence[Mapping[str, Any]]],
    usage_by_stage: Mapping[str, Mapping[str, int] | None],
) -> dict[str, dict[str, Any]]:
    """Return public stage metrics without retaining any model-facing payload."""

    telemetry: dict[str, dict[str, Any]] = {}
    for stage in _STAGE_NAMES:
        calls = calls_by_stage.get(stage, ())
        telemetry[stage] = {
            **configuration[stage],
            "attempts": len(calls),
            "latency_seconds": round(
                sum(
                    float(call.get("latency_seconds", 0.0) or 0.0)
                    for call in calls
                ),
                3,
            ),
            "usage": usage_by_stage.get(stage),
        }
    return telemetry


def _aggregate_stage_telemetry(
    results: Sequence[Mapping[str, Any]],
    configuration: Mapping[str, Mapping[str, bool | str | None]],
) -> dict[str, dict[str, Any]]:
    """Aggregate per-run stage telemetry while retaining the configured model identity."""

    aggregated: dict[str, dict[str, Any]] = {}
    for stage in _STAGE_NAMES:
        stage_records = [
            item["stage_telemetry"][stage]
            for item in results
            if isinstance(item.get("stage_telemetry"), Mapping)
            and isinstance(item["stage_telemetry"].get(stage), Mapping)
        ]
        aggregated[stage] = {
            **configuration[stage],
            "attempts": sum(int(item.get("attempts", 0)) for item in stage_records),
            "latency_seconds": round(
                sum(float(item.get("latency_seconds", 0.0) or 0.0) for item in stage_records),
                3,
            ),
            "usage": _combine_usage(
                *(
                    item.get("usage")
                    for item in stage_records
                    if isinstance(item.get("usage"), Mapping)
                )
            ),
        }
    return aggregated


def _partition_stage_calls(
    calls: Sequence[Mapping[str, Any]],
    *,
    strategy: str,
) -> dict[str, list[dict[str, Any]]]:
    """Classify private traces locally; the public artifact retains metrics only."""

    stages: dict[str, list[dict[str, Any]]] = {stage: [] for stage in _STAGE_NAMES}
    stage_names = {
        "pass_one": {"pass_one", "pass_one_repair", "compiler_non_temporal_pass_one"},
        "selector": {"temporal_candidate_selector"},
        "pass_two": {"pass_two", "pass_two_repair"},
        "one_pass": {"one_pass"},
    }
    for call in calls:
        call_stage = call.get("stage")
        for stage, known_stages in stage_names.items():
            if call_stage in known_stages:
                stages[stage].append(dict(call))
                break
    # An unknown trace stage must never be attributed to an inactive boundary.
    if strategy == "compiler_select_v1":
        stages["pass_two"] = []
    return stages


def run_eval(
    model: str,
    cases_path: Path,
    trials: int,
    strategy: str = "two_pass",
    pass_one_model: str | None = None,
    pass_two_model: str | None = None,
    selector_model: str | None = None,
    selector_policy: TemporalSelectorPolicy = DEFAULT_TEMPORAL_SELECTOR_POLICY,
    trace_dir: Path | None = DEFAULT_LLM_TRACE_DIR,
    trace_all_calls: bool = False,
) -> dict[str, Any]:
    if trials < 1:
        raise ValueError("trials must be positive")
    strategy_error = _strategy_model_error(
        strategy, pass_one_model, pass_two_model, selector_model, selector_policy
    )
    if strategy_error is not None:
        raise ValueError(strategy_error)
    if trace_all_calls and trace_dir is None:
        raise ValueError("trace_all_calls requires trace_dir")
    scenarios = _load_ready_scenarios(cases_path)
    generated_at = datetime.now(UTC).isoformat()
    trace_run_dir = (
        None
        if trace_dir is None
        else trace_dir / f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    )
    if trace_run_dir is not None:
        trace_run_dir.mkdir(parents=True, exist_ok=True)
    trace_count = 0
    stage_configuration = _stage_configuration(
        strategy,
        model=model,
        pass_one_model=pass_one_model,
        pass_two_model=pass_two_model,
        selector_model=selector_model,
        selector_policy=selector_policy,
    )
    # Capture only in memory so --no-trace still reports attempts and latency.  Payloads are
    # never put in the baseline artifact and no sidecar is written when trace_dir is None.
    capture_metrics = True
    pass_one_extractor: OpenAIIntentExtractor | None = None
    pass_two_extractor: OpenAIIntentExtractor | None = None
    selector_extractor: OpenAIIntentExtractor | None = None
    one_pass: OnePassIntentExperiment | None = None
    if strategy in {"two_pass", "compiler_select_v1"}:
        pass_one_extractor = OpenAIIntentExtractor(
            config=OpenAIExtractorConfig(model=pass_one_model or model),
            capture_llm_io=capture_metrics,
        )
    if strategy == "two_pass":
        pass_two_extractor = OpenAIIntentExtractor(
            config=OpenAIExtractorConfig(model=pass_two_model or model),
            capture_llm_io=capture_metrics,
        )
    elif strategy == "compiler_select_v1" and selector_model is not None:
        selector_extractor = OpenAIIntentExtractor(
            config=OpenAIExtractorConfig(model=selector_model),
            capture_llm_io=capture_metrics,
        )
    elif strategy == "one_pass":
        one_pass = OnePassIntentExperiment(model=model, capture_llm_io=capture_metrics)
    holiday_provider = NagerHolidayProvider()
    results: list[dict[str, Any]] = []

    for trial in range(1, trials + 1):
        for scenario in scenarios:
            if pass_one_extractor is not None:
                pass_one_extractor.reset_capture()
            if pass_two_extractor is not None:
                pass_two_extractor.reset_capture()
            if selector_extractor is not None:
                selector_extractor.reset_capture()
            started = time.perf_counter()
            record: dict[str, Any] = {"id": scenario["id"], "trial": trial}
            try:
                context = scenario["context"]
                request = RawRequest(
                    text=scenario["input"].strip(),
                    context=RequestContext(
                        reference_date=date.fromisoformat(context["reference_date"]),
                        timezone=context["timezone"],
                    ),
                )
                usage: dict[str, Any] | None = None
                if strategy == "one_pass":
                    assert one_pass is not None
                    output, usage = one_pass.run(request)
                elif strategy == "compiler_select_v1":
                    assert pass_one_extractor is not None
                    output = understand_request(
                        request,
                        pass_one_extractor,
                        None,
                        holiday_provider,
                        temporal_strategy="compiler_select_v1",
                        temporal_selector=selector_extractor,
                        selector_policy=selector_policy,
                    )
                else:
                    assert pass_one_extractor is not None
                    assert pass_two_extractor is not None
                    output = understand_request(
                        request,
                        pass_one_extractor,
                        pass_two_extractor,
                        holiday_provider,
                    )
                checks = _score_result(scenario["expected"], output)
                repair_trace = (
                    None
                    if output.repair_trace is None
                    else output.repair_trace.model_dump(mode="json")
                )
                record.update(
                    {
                        "status": "passed" if _hard_checks_pass(checks) else "failed",
                        "checks": checks,
                        "evaluation": _evaluation_summary(checks),
                        "unscored_invariants": scenario["expected"].get("invariants", []),
                        "output": output.model_dump(mode="json"),
                        "usage": usage,
                        "repair_trace": repair_trace,
                        "attempts": _repair_attempt_summary(repair_trace, completed=True),
                    }
                )
            except TemporalEvidenceValidationError as exc:
                record.update(
                    {
                        "status": "failed",
                        "checks": [
                            {
                                "name": "grounding_valid",
                                "passed": False,
                                "expected": True,
                                "actual": {
                                    "code": exc.code.value,
                                    "claim_id": exc.claim_id,
                                    "quote": exc.quote,
                                    "reason": exc.reason,
                                    "ambiguous": exc.ambiguous,
                                },
                            }
                        ],
                        "evaluation": {
                            "schema_valid": True,
                            "grounding_valid": False,
                            "semantic_fields_valid": False,
                            "evidence_support_valid": False,
                            "deterministic_outputs_valid": False,
                            "preferred_boundary_exact_match": False,
                            "missing_expected_claims": [],
                            "unsupported_claims": [],
                            "overbroad_spans": [],
                            "insufficient_spans": [],
                        },
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "structured_error": exc.as_dict(),
                        "repair_trace": getattr(exc, "repair_trace", None),
                        "failure_stage": exc.details.stage,
                        "failure_code": exc.details.error_code,
                    }
                )
                record["attempts"] = _repair_attempt_summary(
                    record["repair_trace"], completed=False
                )
            except TemporalResolutionValidationError as exc:
                record.update(
                    {
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "structured_error": exc.as_dict(),
                        "repair_trace": getattr(exc, "repair_trace", None),
                        "failure_stage": exc.details.stage,
                        "failure_code": exc.details.error_code,
                    }
                )
                record["attempts"] = _repair_attempt_summary(
                    record["repair_trace"], completed=False
                )
            except Exception as exc:  # noqa: BLE001 - one failed case must not abort the baseline
                failure_stage = None
                failure_code = None
                if isinstance(exc, (IntentExtractionError, NonTemporalExtractionError)):
                    failure_stage = "pass_one_model_output"
                    failure_code = "missing_or_invalid_model_output"
                    if isinstance(exc, NonTemporalExtractionError):
                        failure_stage = "compiler_non_temporal_pass_one"
                elif isinstance(exc, DateResolutionError):
                    failure_stage = "pass_two_wire_conversion"
                    failure_code = "missing_or_invalid_model_output"
                elif isinstance(exc, TemporalSelectionError):
                    failure_stage = "temporal_candidate_selector"
                    failure_code = "selector_model_output"
                elif (
                    selector_extractor is not None
                    and isinstance(
                        exc, (TemporalSelectorValidationError, TemporalCandidateValidationError)
                    )
                ):
                    failure_stage = "temporal_candidate_selector"
                    failure_code = "selector_validation"
                record.update(
                    {
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error": (
                            "temporal candidate selection failed"
                            if failure_stage == "temporal_candidate_selector"
                            else str(exc)
                        ),
                        "attempts": _repair_attempt_summary(None, completed=False),
                    }
                )
                if failure_stage is not None:
                    record["failure_stage"] = failure_stage
                    record["failure_code"] = failure_code
            pass_one_usage = (
                None if pass_one_extractor is None else pass_one_extractor.take_usage()
            )
            selector_usage = (
                None if selector_extractor is None else selector_extractor.take_usage()
            )
            pass_two_usage = (
                None if pass_two_extractor is None else pass_two_extractor.take_usage()
            )
            one_pass_usage = None
            if strategy == "one_pass":
                # Retain the experiment's existing usage return when its adapter supplies one.
                record["usage"] = usage if usage is not None else one_pass_usage
            else:
                record["usage"] = _combine_usage(
                    pass_one_usage, selector_usage, pass_two_usage
                )
            call_traces = _combine_call_traces(
                () if pass_one_extractor is None else pass_one_extractor.take_call_traces(),
                () if selector_extractor is None else selector_extractor.take_call_traces(),
                () if pass_two_extractor is None else pass_two_extractor.take_call_traces(),
                () if one_pass is None else one_pass.take_call_traces(),
            )
            record["stage_telemetry"] = _stage_telemetry(
                stage_configuration,
                calls_by_stage=_partition_stage_calls(call_traces, strategy=strategy),
                usage_by_stage={
                    "pass_one": pass_one_usage,
                    "selector": selector_usage,
                    "pass_two": pass_two_usage,
                    "one_pass": usage if strategy == "one_pass" else one_pass_usage,
                },
            )
            record["failure_categories"] = sorted(_failure_flags(record))
            record["latency_seconds"] = round(time.perf_counter() - started, 3)
            if trace_run_dir is not None and (trace_all_calls or record["status"] != "passed"):
                trace_path = write_eval_llm_trace(
                    trace_run_dir,
                    scenario=scenario,
                    record=record,
                    calls=call_traces,
                )
                record["llm_trace"] = {
                    "path": str(trace_path),
                    "calls": len(call_traces),
                }
                trace_count += 1
            results.append(record)
            print(f"trial={trial} id={scenario['id']} status={record['status']}", flush=True)

    passed = sum(item["status"] == "passed" for item in results)
    failed = sum(item["status"] == "failed" for item in results)
    errors = sum(item["status"] == "error" for item in results)
    instrumentation = _aggregate_results(results)
    artifact: dict[str, Any] = {
        "schema_version": 5,
        "generated_at": generated_at,
        "model": model,
        "pass_one_model": stage_configuration["pass_one"]["model"],
        "pass_two_model": stage_configuration["pass_two"]["model"],
        "selector_model": stage_configuration["selector"]["model"],
        "selector_policy": selector_policy,
        "strategy": strategy,
        "cases_path": str(cases_path),
        "scenario_count": len(scenarios),
        "trials": trials,
        "summary": {
            "runs": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": passed / len(results) if results else 0.0,
            **instrumentation,
            "latency_seconds": round(sum(item["latency_seconds"] for item in results), 3),
            "usage": _usage_summary(results),
            "cost": "not calculated; token usage is partial when failed parses omit usage",
        },
        "results": results,
        "stage_telemetry": _aggregate_stage_telemetry(results, stage_configuration),
    }
    if trace_run_dir is not None:
        artifact["llm_trace"] = {
            "mode": "all_calls" if trace_all_calls else "failed_calls",
            "directory": str(trace_run_dir),
            "case_count": trace_count,
        }
    return artifact


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    artifact = run_eval(
        model=args.model,
        cases_path=args.cases,
        trials=args.trials,
        strategy=args.strategy,
        pass_one_model=args.pass_one_model,
        pass_two_model=args.pass_two_model,
        selector_model=args.selector_model,
        selector_policy=args.selector_policy,
        trace_dir=None if args.no_trace else args.trace_dir,
        trace_all_calls=args.trace_all_calls,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    print(f"saved={args.output}")
    return 0 if artifact["summary"]["failed"] == 0 and artifact["summary"]["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
