"""Run and score the ready live-model intent evaluation corpus."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from award_agent.domain import RawRequest, RequestContext, RequestUnderstandingResult
from award_agent.experiments.one_pass_intent import OnePassIntentExperiment
from award_agent.intent.holidays import NagerHolidayProvider
from award_agent.intent.openai_extractor import OpenAIExtractorConfig, OpenAIIntentExtractor
from award_agent.intent.workflow import understand_request


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the ready intent-evaluation scenarios.")
    parser.add_argument("--model", required=True, help="OpenAI model ID to evaluate")
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
        choices=("two_pass", "one_pass"),
        default="two_pass",
        help="Workflow arm to evaluate",
    )
    return parser


def _record_check(
    checks: list[dict[str, Any]],
    name: str,
    expected: Any,
    actual: Any,
    passed: bool,
) -> None:
    checks.append(
        {"name": name, "passed": passed, "expected": expected, "actual": actual}
    )


def _location_matches(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    accepted_values = expected.get("accepted_values")
    exact_fields = {
        key: value for key, value in expected.items() if key != "accepted_values"
    }
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
        _record_check(checks, "search_modes", wanted_modes, actual_modes, wanted_modes == actual_modes)

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
            actual_clarification.get(key) == value
            for key, value in wanted_clarification.items()
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

    if "temporal_phrases" in expected:
        wanted_phrases = set(expected["temporal_phrases"])
        actual_phrases = {item["raw_text"] for item in extraction.get("temporal_phrases", [])}
        _record_check(
            checks,
            "temporal_phrases",
            sorted(wanted_phrases),
            sorted(actual_phrases),
            wanted_phrases <= actual_phrases,
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
    return [scenario for scenario in scenarios if scenario.get("status") == "ready"]


def run_eval(
    model: str,
    cases_path: Path,
    trials: int,
    strategy: str = "two_pass",
) -> dict[str, Any]:
    if trials < 1:
        raise ValueError("trials must be positive")
    if strategy not in {"two_pass", "one_pass"}:
        raise ValueError(f"unsupported eval strategy: {strategy}")
    scenarios = _load_ready_scenarios(cases_path)
    extractor = OpenAIIntentExtractor(config=OpenAIExtractorConfig(model=model))
    one_pass = OnePassIntentExperiment(model=model)
    holiday_provider = NagerHolidayProvider()
    results: list[dict[str, Any]] = []

    for trial in range(1, trials + 1):
        for scenario in scenarios:
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
                    output, usage = one_pass.run(request)
                else:
                    output = understand_request(
                        request,
                        extractor,
                        extractor,
                        holiday_provider,
                    )
                checks = _score_result(scenario["expected"], output)
                record.update(
                    {
                        "status": "passed" if all(item["passed"] for item in checks) else "failed",
                        "checks": checks,
                        "unscored_invariants": scenario["expected"].get("invariants", []),
                        "output": output.model_dump(mode="json"),
                        "usage": usage,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - one failed case must not abort the baseline
                record.update(
                    {
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            record["latency_seconds"] = round(time.perf_counter() - started, 3)
            results.append(record)
            print(f"trial={trial} id={scenario['id']} status={record['status']}", flush=True)

    passed = sum(item["status"] == "passed" for item in results)
    failed = sum(item["status"] == "failed" for item in results)
    errors = sum(item["status"] == "error" for item in results)
    usage_records = [item["usage"] for item in results if item.get("usage") is not None]
    total_input_tokens = sum(item.get("input_tokens", 0) for item in usage_records)
    total_output_tokens = sum(item.get("output_tokens", 0) for item in usage_records)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": model,
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
            "latency_seconds": round(sum(item["latency_seconds"] for item in results), 3),
            "usage": (
                {
                    "captured_runs": len(usage_records),
                    "missing_runs": len(results) - len(usage_records),
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                }
                if usage_records
                else "unavailable: the current two-pass adapter does not retain response usage"
            ),
            "cost": "not calculated; token usage is partial when failed parses omit usage",
        },
        "results": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    artifact = run_eval(args.model, args.cases, args.trials, args.strategy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    print(f"saved={args.output}")
    return 0 if artifact["summary"]["failed"] == 0 and artifact["summary"]["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
