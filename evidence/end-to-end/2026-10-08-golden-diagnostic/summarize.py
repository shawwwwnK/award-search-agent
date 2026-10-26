"""Summarize saved SDK usage and estimated generation cost without live calls."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RATES = json.loads((HERE / "pricing-basis.json").read_text())["models"]


def price(model: str, usage: dict[str, int]) -> str | None:
    rates = RATES.get(model)
    if rates is None:
        return None
    bracket = rates["long_context" if usage["input_tokens"] > 272_000 else "short_context"]
    uncached = usage["input_tokens"] - usage["cached_input_tokens"] - usage["cache_write_tokens"]
    if uncached < 0:
        return None
    total = sum((Decimal(count) * Decimal(str(bracket[name])) / Decimal(1_000_000)
                 for name, count in (("input", uncached),
                                     ("cached_input", usage["cached_input_tokens"]),
                                     ("cache_write", usage["cache_write_tokens"]),
                                     ("output", usage["output_tokens"]))))
    return format(total, ".10f")


def response_usage(response: dict[str, Any]) -> dict[str, int] | None:
    raw = response.get("usage")
    if not isinstance(raw, dict):
        return None
    details = raw.get("input_tokens_details") or {}
    output_details = raw.get("output_tokens_details") or {}
    if not all(isinstance(raw.get(key), int) for key in ("input_tokens", "output_tokens")):
        return None
    return {
        "input_tokens": raw["input_tokens"],
        "output_tokens": raw["output_tokens"],
        "cached_input_tokens": int(details.get("cached_tokens", 0)),
        "cache_write_tokens": int(details.get("cache_creation_tokens", details.get("cache_write_tokens", 0))),
        "reasoning_output_tokens": int(output_details.get("reasoning_tokens", 0)),
    }


def summarize(campaign: str = "original") -> dict[str, Any]:
    cases: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "generation_calls": 0, "input_tokens": 0, "output_tokens": 0,
        "cached_input_tokens": 0, "cache_write_tokens": 0,
        "reasoning_output_tokens": 0, "generation_estimate_usd": Decimal(0),
        "model_api_seconds": 0.0, "missing_usage_calls": 0,
        "input_token_measurement_calls": 0, "attempts": [], "models": {},
        "calls": [],
    })
    seen_ids: set[str] = set()
    seen_unidentified_calls: set[str] = set()
    root = HERE / "runs" if campaign == "original" else HERE / campaign / "runs"
    for summary_path in sorted(root.rglob("summary.json")):
        directory = summary_path.parent
        case_path = directory / "case.json"
        if not case_path.is_file():
            continue
        case = json.loads(case_path.read_text())["source_fixture"]["id"]
        run = json.loads(summary_path.read_text())
        record = cases[case]
        record["attempts"].append({
            "directory": str(directory.relative_to(HERE)), "status": run.get("status"),
            "stages": run.get("stages", {}), "delivery": run.get("stages", {}).get("results", {}).get("delivery"),
            "provider_exact_replay": run.get("provider_exact_replay"),
            "results_exact_replay": run.get("results_exact_replay"),
            "wall_seconds": run.get("elapsed_seconds"),
            "live_pipeline_seconds": run.get("live_pipeline_seconds"),
        })
        index_path = directory / "model-calls" / "index.json"
        if not index_path.is_file():
            continue
        for item in json.loads(index_path.read_text()):
            call_path = directory / "model-calls" / f"call-{item['sequence']:03d}.json"
            if not call_path.is_file():
                continue
            call = json.loads(call_path.read_text())
            call_fingerprint = sha256(json.dumps(call, sort_keys=True).encode()).hexdigest()
            if call["kind"] == "client.post":
                if (call.get("request", {}).get("args") or [None])[0] == "/responses/input_tokens":
                    if call_fingerprint in seen_unidentified_calls:
                        continue
                    seen_unidentified_calls.add(call_fingerprint)
                    record["input_token_measurement_calls"] += 1
                    record["calls"].append({"path": str(call_path.relative_to(HERE)),
                        "purpose": "input_token_measurement", "stage": call.get("stage"),
                        "latency_seconds": call.get("latency_seconds"),
                        "input_tokens_counted": (call.get("response") or {}).get("input_tokens"),
                        "billable_cost": "unknown; excluded from generation estimate"})
                continue
            response = call.get("response") or {}
            response_id = response.get("id") if isinstance(response, dict) else None
            if response_id is not None:
                if response_id in seen_ids:
                    continue
                seen_ids.add(response_id)
            elif call_fingerprint in seen_unidentified_calls:
                continue
            else:
                seen_unidentified_calls.add(call_fingerprint)
            model = call.get("request", {}).get("kwargs", {}).get("model", "unknown")
            record["generation_calls"] += 1
            record["model_api_seconds"] += float(call.get("latency_seconds") or 0)
            usage = response_usage(response) if isinstance(response, dict) else None
            call_record: dict[str, Any] = {"path": str(call_path.relative_to(HERE)),
                "purpose": "generation", "stage": call.get("stage"), "model": model,
                "response_id": response_id, "latency_seconds": call.get("latency_seconds"),
                "pricing_bracket": None if usage is None else (
                    "long_context" if usage["input_tokens"] > 272_000 else "short_context"),
                "usage": usage}
            if usage is None:
                record["missing_usage_calls"] += 1
                call_record["estimate_usd"] = None
                record["calls"].append(call_record)
                continue
            for key in ("input_tokens", "output_tokens", "cached_input_tokens",
                        "cache_write_tokens", "reasoning_output_tokens"):
                record[key] += usage[key]
            estimate = price(model, usage)
            if estimate is None:
                record["missing_usage_calls"] += 1
            else:
                record["generation_estimate_usd"] += Decimal(estimate)
            call_record["estimate_usd"] = estimate
            record["calls"].append(call_record)
            record["models"][model] = record["models"].get(model, 0) + 1
    payload: dict[str, Any] = {"schema_version": 1,
        "campaign": campaign,
        "basis": "pricing-basis.json; Standard generation response usage, one long-context decision per call",
        "limitations": ["Generation estimates exclude /responses/input_tokens count-endpoint billing and provider charges.",
                        "Calls without SDK usage have unknown cost. Cache-write tokens are zero only where the SDK reports no such class; undisclosed account caching is unmeasured.",
                        "Attempt wall times are reported individually because continuations and preserved copies are not additive."],
        "cases": {}}
    for key, value in sorted(cases.items()):
        value["generation_estimate_usd"] = format(value["generation_estimate_usd"], ".10f")
        value["model_api_seconds"] = round(value["model_api_seconds"], 3)
        payload["cases"][key] = value
    output = HERE / "usage-summary.json" if campaign == "original" else HERE / campaign / "usage-summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", choices=("original", "early-2027"), default="original")
    result = summarize(parser.parse_args().campaign)
    print(json.dumps({case: {"calls": data["generation_calls"],
                             "estimate_usd": data["generation_estimate_usd"]}
                      for case, data in result["cases"].items()}, indent=2))
