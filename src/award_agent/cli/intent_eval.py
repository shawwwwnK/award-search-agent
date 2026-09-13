"""Run the active LLM-owned initial-intent behavioral evaluation.

The live route has exactly one semantic receiver. This evaluator scores observable
action/property envelopes, not a receiver proposal or selector choice.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from dotenv import load_dotenv

from award_agent.domain import (
    RawRequest,
    RequestContext,
    RequestUnderstandingOutcome,
    RequestUnderstandingResult,
)
from award_agent.intent.holidays import NagerHolidayProvider
from award_agent.intent.openai_interpreter import (
    OpenAISemanticIntentConfig,
    OpenAISemanticIntentInterpreter,
    semantic_intent_adapter_contract_metadata,
)
from award_agent.intent.workflow import understand_request
from award_agent.observability.llm_trace import write_eval_llm_trace

DEFAULT_LLM_TRACE_DIR = Path("evals/intent/traces")
DEFAULT_ONE_WAY_AWARD_CASES = Path("evals/intent/one_way_award_behavior_cases_v1.yaml")
_CONTRACT_VERSION = "intent_behavior_v1"
_REQUIRED_COVERAGE_FAMILIES = frozenset(
    {
        "ready_exact_airports",
        "ready_whole_month",
        "ready_early_month",
        "ready_holiday_window",
        "ready_relative_next_month",
        "ready_relative_weekend",
        "typo_recognizable_date",
        "missing_origin",
        "missing_destination",
        "missing_departure",
        "missing_travelers",
        "unbounded_departure",
        "ambiguous_departure",
        "explicit_return_unsupported",
        "duration_return_unsupported",
        "relative_return_unsupported",
        "cash_only_unsupported",
        "mixed_award_cash_eligible",
        "default_award_home_airport_not_return",
    }
)
_ACTIONS = frozenset({"ready", "clarification", "unsupported", "pending_retryable"})


@dataclass(frozen=True)
class _PreflightedIntentCorpus:
    contract_version: str
    fixture_sha256: str
    scenarios: list[dict[str, Any]]


def _semantic_contract_metadata() -> dict[str, str]:
    """Bind artifacts to the strict text_format used by the OpenAI adapter."""

    return semantic_intent_adapter_contract_metadata()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one-receiver intent action/property evaluation."
    )
    parser.add_argument("--model", required=True, help="OpenAI model ID for the semantic receiver")
    parser.add_argument("--cases", type=Path, default=DEFAULT_ONE_WAY_AWARD_CASES)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_LLM_TRACE_DIR)
    parser.add_argument("--no-trace", action="store_true")
    parser.add_argument("--trace-all-calls", action="store_true")
    return parser


def _preflight_one_way_award_cases(path: Path) -> _PreflightedIntentCorpus:
    """Validate the disclosed behavioral corpus before a paid model call."""
    data = path.read_bytes()
    payload = yaml.safe_load(data)
    if not isinstance(payload, dict) or set(payload) != {
        "contract_version",
        "purpose",
        "scenarios",
    }:
        raise ValueError(
            "intent behavioral corpus must contain contract_version, purpose, and scenarios"
        )
    if payload["contract_version"] != _CONTRACT_VERSION:
        raise ValueError(f"intent eval corpus must use contract version {_CONTRACT_VERSION!r}")
    if not isinstance(payload["purpose"], str) or not payload["purpose"].strip():
        raise ValueError("intent eval corpus purpose must be non-empty")
    scenarios = payload["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) != len(_REQUIRED_COVERAGE_FAMILIES):
        raise ValueError("intent eval corpus does not contain the complete behavioral denominator")
    seen_ids: set[str] = set()
    seen_families: set[str] = set()
    for item in scenarios:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "coverage_family",
            "description",
            "input",
            "context",
            "oracle",
            "status",
        }:
            raise ValueError("each intent behavioral scenario has an invalid shape")
        identifier, family = item["id"], item["coverage_family"]
        if not isinstance(identifier, str) or not identifier or identifier in seen_ids:
            raise ValueError("intent behavioral scenario IDs must be unique and non-empty")
        if not isinstance(family, str) or not family or family in seen_families:
            raise ValueError("intent behavioral coverage families must be unique and non-empty")
        seen_ids.add(identifier)
        seen_families.add(family)
        if (
            item["status"] != "ready"
            or not isinstance(item["input"], str)
            or not item["input"].strip()
        ):
            raise ValueError(f"scenario {identifier!r} must be ready with input")
        context = item["context"]
        if not isinstance(context, dict) or set(context) != {"reference_date", "timezone"}:
            raise ValueError(f"scenario {identifier!r} has invalid context")
        try:
            date.fromisoformat(context["reference_date"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"scenario {identifier!r} has invalid reference_date") from exc
        if not isinstance(context["timezone"], str) or not context["timezone"]:
            raise ValueError(f"scenario {identifier!r} has invalid timezone")
        oracle = item["oracle"]
        required = {
            "acceptable_actions",
            "must_ground",
            "must_remain_blocked",
            "properties",
            "forbidden_outcomes",
        }
        if (
            not isinstance(oracle, dict)
            or not required <= set(oracle)
            or set(oracle) - (required | {"clarification_field"})
        ):
            raise ValueError(f"scenario {identifier!r} has invalid action/property oracle")
        actions = oracle["acceptable_actions"]
        if not isinstance(actions, list) or not actions or not set(actions) <= _ACTIONS:
            raise ValueError(f"scenario {identifier!r} has invalid acceptable_actions")
        for key in ("must_ground", "must_remain_blocked", "forbidden_outcomes"):
            if not isinstance(oracle[key], list) or not all(
                isinstance(value, str) for value in oracle[key]
            ):
                raise ValueError(f"scenario {identifier!r} oracle {key!r} must be a string list")
        if not isinstance(oracle["properties"], dict):
            raise TypeError(f"scenario {identifier!r} properties must be a mapping")
    if seen_families != _REQUIRED_COVERAGE_FAMILIES:
        raise ValueError("intent eval corpus coverage families do not match behavioral denominator")
    return _PreflightedIntentCorpus(_CONTRACT_VERSION, sha256(data).hexdigest(), scenarios)


def _load_ready_scenarios(path: Path) -> list[dict[str, Any]]:
    return _preflight_one_way_award_cases(path).scenarios


def _record(
    checks: list[dict[str, Any]], name: str, passed: bool, *, blocking: bool = True
) -> None:
    item: dict[str, Any] = {"name": name, "passed": passed}
    if not blocking:
        item["blocking"] = False
    checks.append(item)


def _action(result: RequestUnderstandingResult) -> str:
    # Forward-compatible with ADR 0017's future typed pending result without
    # treating an ordinary clarification as pending today.
    outcome = getattr(result, "outcome", None)
    if getattr(outcome, "value", outcome) == "pending_retryable":
        return "pending_retryable"
    if result.clarification is None:
        return "invalid_completed_result"
    return {"none": "ready", "ask": "clarification", "unsupported": "unsupported"}[
        result.clarification.action.value
    ]


def _location_matches(items: Sequence[Any], expected: Mapping[str, Any]) -> bool:
    return any(
        item.kind.value == expected.get("kind") and item.value == expected.get("value")
        for item in items
    )


def _grounded(result: RequestUnderstandingResult, field: str) -> bool:
    parsed = result.parsed_request
    if parsed is None:
        return False
    if field == "departure":
        return bool(parsed.temporal_evidence) and all(
            evidence.span.text == parsed.raw_text[evidence.span.start : evidence.span.end]
            for evidence in parsed.temporal_evidence
        )
    if field == "origin":
        return bool(parsed.origins) and all(
            item.raw_text and item.raw_text in parsed.raw_text for item in parsed.origins
        )
    if field == "destination":
        return bool(parsed.destinations) and all(
            item.raw_text and item.raw_text in parsed.raw_text for item in parsed.destinations
        )
    # Canonical non-temporal fact evidence is not public in ParsedRequest yet.
    return field not in {"travelers", "cabin", "mode"}


def _non_temporal_grounding_valid(result: RequestUnderstandingResult) -> bool:
    """Check all observable non-temporal location claims against source text.

    The current public result does not expose canonical evidence for traveler,
    cabin, or mode facts. This still ensures no emitted location claim bypasses
    exact source grounding; the offline semantic suite owns the hidden-fact
    provenance contract.
    """

    parsed = result.parsed_request
    if parsed is None:
        return False
    return all(
        item.raw_text and item.raw_text in parsed.raw_text
        for item in [*parsed.origins, *parsed.destinations]
    )


def _required_blockers(result: RequestUnderstandingResult) -> set[str]:
    if result.parsed_request is None:
        return set()
    return {
        item.field
        for item in result.parsed_request.unknowns
        if item.field in {"origin", "destination", "departure", "travelers"}
    }


def _forbidden(result: RequestUnderstandingResult, outcome: str) -> bool:
    parsed = result.parsed_request
    if outcome == "success_shaped_model_failure":
        return _action(result) == "pending_retryable" and (
            parsed is not None or result.clarification is not None
        )
    if parsed is None:
        return False
    if outcome == "return_or_duration_in_active_state":
        extraction = parsed.temporal_extraction
        return bool(
            extraction
            and any(item.applies_to.value != "departure" for item in extraction.temporal_phrases)
        )
    if outcome == "city_expanded_to_airports":
        return any(
            item.kind.value == "city" and len(item.value) == 3 and item.value.isupper()
            for item in [*parsed.origins, *parsed.destinations]
        )
    if outcome == "cash_coverage_claim":
        clarification = result.clarification
        if clarification is None:
            return False
        return bool(
            clarification.question
            and "cash" in clarification.question.lower()
            and _action(result) == "ready"
        )
    if outcome == "unbounded_departure_ready":
        return _action(result) == "ready" and parsed.departure_window is None
    raise ValueError(f"unknown forbidden outcome {outcome!r}")


def _score_result(
    oracle: Mapping[str, Any], result: RequestUnderstandingResult
) -> list[dict[str, Any]]:
    parsed, clarification, properties = (
        result.parsed_request,
        result.clarification,
        oracle["properties"],
    )
    checks: list[dict[str, Any]] = []
    _record(checks, "action", _action(result) in oracle["acceptable_actions"])
    if _action(result) == "pending_retryable":
        _record(
            checks,
            "pending_is_state_free",
            parsed is None and clarification is None,
        )
        return checks
    if parsed is None or clarification is None:
        _record(checks, "completed_result_has_state", False)
        return checks
    _record(checks, "non_temporal_grounding", _non_temporal_grounding_valid(result))
    for field in oracle["must_ground"]:
        _record(checks, f"grounding:{field}", _grounded(result, field))
    _record(
        checks,
        "required_blockers",
        set(oracle["must_remain_blocked"]) <= _required_blockers(result),
    )
    _record(
        checks,
        "no_unexpected_required_blockers",
        _required_blockers(result) <= set(oracle["must_remain_blocked"]),
    )
    if "clarification_field" in oracle:
        _record(
            checks,
            "clarification_field",
            clarification.field == oracle["clarification_field"],
        )
    if "travelers" in properties:
        _record(checks, "travelers", parsed.travelers in properties["travelers"])
    if "origin" in properties:
        _record(checks, "origin", _location_matches(parsed.origins, properties["origin"]))
    if "destination" in properties:
        _record(
            checks, "destination", _location_matches(parsed.destinations, properties["destination"])
        )
    if "modes" in properties:
        _record(
            checks,
            "modes",
            sorted(mode.value for mode in parsed.search_modes) == sorted(properties["modes"]),
        )
    if "departure_window" in properties:
        window, expected = parsed.departure_window, properties["departure_window"]
        matches_window = (
            window is not None
            and window.start.isoformat() == expected["start"]
            and window.end.isoformat() == expected["end"]
        )
        _record(
            checks,
            "departure_window",
            matches_window,
        )
    if "unsupported_codes" in properties:
        _record(
            checks,
            "unsupported_codes",
            sorted(item.code.value for item in parsed.unsupported_request_parts)
            == sorted(properties["unsupported_codes"]),
        )
    for outcome in oracle["forbidden_outcomes"]:
        _record(checks, f"forbidden:{outcome}", not _forbidden(result, outcome))
    return checks


def _hard_checks_pass(checks: Sequence[Mapping[str, Any]]) -> bool:
    return all(bool(item["passed"]) or item.get("blocking") is False for item in checks)


def _public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "id": record["id"],
        "trial": record["trial"],
        "status": record["status"],
        "checks": [{"name": c["name"], "passed": c["passed"]} for c in record.get("checks", [])],
        "failure_stage": record.get("failure_stage"),
        "failure_code": record.get("failure_code"),
        "action": record.get("action"),
        "latency_seconds": record["latency_seconds"],
        "usage": record.get("usage"),
        "stage_telemetry": record["stage_telemetry"],
    }
    if "llm_trace" in record:
        result["private_trace"] = record["llm_trace"]
    return result


def _usage_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int] | str:
    usage = [item["usage"] for item in records if item.get("usage")]
    if not usage:
        return "unavailable: SDK responses did not provide usage"
    return {
        key: sum(int(item.get(key, 0)) for item in usage)
        for key in (
            "calls",
            "captured_calls",
            "missing_calls",
            "input_tokens",
            "output_tokens",
            "total_tokens",
        )
    }


def _fault_injection_pending_metrics() -> dict[str, int | bool]:
    """Exercise the evaluator's state-free pending contract without a model call."""

    pending = RequestUnderstandingResult(
        outcome=RequestUnderstandingOutcome.PENDING_RETRYABLE,
        pending_detail="injected evaluator fault",
    )
    return {
        "numerator": int(
            _action(pending) == "pending_retryable"
            and pending.parsed_request is None
            and pending.clarification is None
        ),
        "denominator": 1,
    }


def run_eval(
    model: str,
    cases_path: Path,
    trials: int,
    trace_dir: Path | None = DEFAULT_LLM_TRACE_DIR,
    trace_all_calls: bool = False,
) -> dict[str, Any]:
    if trials < 1:
        raise ValueError("trials must be positive")
    if trace_all_calls and trace_dir is None:
        raise ValueError("trace_all_calls requires trace_dir")
    corpus = _preflight_one_way_award_cases(cases_path)
    contract_metadata = _semantic_contract_metadata()
    generated_at = datetime.now(UTC).isoformat()
    trace_run_dir = (
        None
        if trace_dir is None
        else trace_dir / f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    )
    if trace_run_dir:
        trace_run_dir.mkdir(parents=True, exist_ok=True)
    interpreter = OpenAISemanticIntentInterpreter(
        OpenAISemanticIntentConfig(model=model), capture_llm_io=True
    )
    provider, private, public, trace_count = NagerHolidayProvider(), [], [], 0
    for trial in range(1, trials + 1):
        for scenario in corpus.scenarios:
            interpreter.reset_capture()
            started = time.perf_counter()
            record: dict[str, Any] = {"id": scenario["id"], "trial": trial}
            try:
                context = scenario["context"]
                result = understand_request(
                    RawRequest(
                        text=scenario["input"].strip(),
                        context=RequestContext(
                            reference_date=date.fromisoformat(context["reference_date"]),
                            timezone=context["timezone"],
                        ),
                    ),
                    interpreter,
                    provider,
                )
                checks = _score_result(scenario["oracle"], result)
                record.update(
                    {
                        "status": "passed" if _hard_checks_pass(checks) else "failed",
                        "checks": checks,
                        "action": _action(result),
                        "output": result.model_dump(mode="json"),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - one case must not abort the diagnostic run
                record.update(
                    {
                        "status": "error",
                        "failure_stage": "workflow",
                        "failure_code": type(exc).__name__,
                    }
                )
            usage, calls = interpreter.take_usage(), interpreter.take_call_traces()
            record["usage"] = usage
            record["stage_telemetry"] = {
                "semantic_receiver": {
                    "enabled": True,
                    "configured": True,
                    "model": model,
                    "attempts": len(calls),
                    "latency_seconds": round(
                        sum(float(call.get("latency_seconds", 0) or 0) for call in calls), 3
                    ),
                    "usage": usage,
                    **contract_metadata,
                }
            }
            record["latency_seconds"] = round(time.perf_counter() - started, 3)
            if trace_run_dir:
                path = write_eval_llm_trace(
                    trace_run_dir, scenario=scenario, record=record, calls=calls
                )
                record["llm_trace"] = {"path": str(path), "calls": len(calls)}
                trace_count += 1
            private.append(record)
            public.append(_public_record(record))
            print(f"trial={trial} id={scenario['id']} status={record['status']}", flush=True)
    passed, failed, errors = (
        sum(item["status"] == status for item in public) for status in ("passed", "failed", "error")
    )
    stage = {
        "semantic_receiver": {
            "enabled": True,
            "configured": True,
            "model": model,
            "attempts": sum(
                item["stage_telemetry"]["semantic_receiver"]["attempts"] for item in private
            ),
            "latency_seconds": round(
                sum(
                    item["stage_telemetry"]["semantic_receiver"]["latency_seconds"]
                    for item in private
                ),
                3,
            ),
            **contract_metadata,
        }
    }
    ordinary_language_pending = sum(item.get("action") == "pending_retryable" for item in private)
    pending_denominator = len(private)
    fault_injection_metrics = _fault_injection_pending_metrics()
    artifact: dict[str, Any] = {
        "schema_version": 9,
        "generated_at": generated_at,
        "model": model,
        "architecture": "one_llm_semantic_receiver",
        "request_scope": "one_way_award_v1",
        "contract_version": corpus.contract_version,
        "semantic_contract": contract_metadata,
        "cases_path": str(cases_path),
        "fixture_sha256": corpus.fixture_sha256,
        "scenario_count": len(corpus.scenarios),
        "trials": trials,
        "summary": {
            "runs": len(public),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": passed / len(public) if public else 0.0,
            "ordinary_language_pending": ordinary_language_pending,
            "operational_outcomes": {
                "ordinary_language_pending": {
                    "numerator": ordinary_language_pending,
                    "denominator": pending_denominator,
                },
                "fault_injection_pending": fault_injection_metrics,
            },
            "usage": _usage_summary(private),
            "cost": "not calculated",
        },
        "results": public,
        "stage_telemetry": stage,
    }
    if trace_run_dir:
        artifact["llm_trace"] = {
            "mode": "all_calls",
            "directory": str(trace_run_dir),
            "case_count": trace_count,
        }
    return artifact


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    artifact = run_eval(
        args.model,
        args.cases,
        args.trials,
        None if args.no_trace else args.trace_dir,
        args.trace_all_calls,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 and artifact["summary"]["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
