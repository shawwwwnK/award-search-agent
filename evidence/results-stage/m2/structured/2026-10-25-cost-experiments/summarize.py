"""Recompute lower-cost experiment metadata from immutable writer receipts."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
RATES = {
    "gpt-6-luna": {"input": "0.10", "cached": "0.01", "write": "0.125", "output": "0.50"},
    "gpt-5.6-terra": {"input": "2.00", "cached": "0.20", "write": "2.50", "output": "12.00"},
    "gpt-6.1-sol": {"input": "2.00", "cached": "0.10", "write": "2.50", "output": "10.00"},
}


def collect(directory: Path) -> dict[str, Any]:
    rows = []
    for path in sorted(directory.glob("round-*/*/artifact.json")):
        artifact = json.loads(path.read_text())
        for index, attempt in enumerate(artifact["attempts"]):
            receipt = attempt["writer_receipt"]
            raw = json.loads(receipt["raw_response"])
            usage = raw["usage"]
            details = usage["input_tokens_details"]
            model = raw["model"]
            assert raw["service_tier"] == "default"
            assert usage["input_tokens"] < 272000
            assert attempt["input_token_receipt"]["input_tokens"] == usage["input_tokens"]
            cached = details["cached_tokens"]
            writes = details["cache_write_tokens"]
            ordinary = usage["input_tokens"] - cached - writes
            assert ordinary >= 0
            counts = {"input": ordinary, "cached": cached, "write": writes,
                      "output": usage["output_tokens"]}
            cost = sum(Decimal(n) * Decimal(RATES[model][key])
                       for key, n in counts.items()) / Decimal(1000000)
            rows.append({"model": model, "case": path.parent.name,
                         "round": int(path.parent.parent.name.split("-")[1]),
                         "phase": attempt["phase"], "attempt": index + 1,
                         "selected": index == artifact["selected_attempt"],
                         "input_tokens": usage["input_tokens"],
                         "ordinary_input_tokens": ordinary, "cached_input_tokens": cached,
                         "cache_write_tokens": writes, "output_tokens": usage["output_tokens"],
                         "reasoning_tokens": usage["output_tokens_details"]["reasoning_tokens"],
                         "latency_seconds": receipt["latency_seconds"],
                         "estimated_cost_usd": str(cost),
                         "failed_findings": sum(f["outcome"] == "failed"
                                                for f in attempt["findings"]),
                         "artifact": str(path.relative_to(REPO))})
    assert rows
    latency = [row["latency_seconds"] for row in rows]
    return {"runs": len({(row["round"], row["case"]) for row in rows}),
            "generations": len(rows), "count_requests": len(rows),
            "input_tokens": sum(row["input_tokens"] for row in rows),
            "output_tokens": sum(row["output_tokens"] for row in rows),
            "reasoning_tokens": sum(row["reasoning_tokens"] for row in rows),
            "cached_input_tokens": sum(row["cached_input_tokens"] for row in rows),
            "cache_write_tokens": sum(row["cache_write_tokens"] for row in rows),
            "estimated_cost_usd": str(sum(Decimal(row["estimated_cost_usd"]) for row in rows)),
            "summed_generation_seconds": sum(latency), "mean_generation_seconds": mean(latency),
            "median_generation_seconds": median(latency), "min_generation_seconds": min(latency),
            "max_generation_seconds": max(latency), "attempts": rows}


def main() -> None:
    experiments = {arm: collect(ROOT / arm) for arm in ("luna-retest", "terra")}
    baseline = collect(ROOT.parent / "2026-10-25-composition-sol")
    comparisons: dict[str, dict[str, dict[str, object]]] = {}
    for arm in experiments:
        comparisons[arm] = {}
        for case in {row["case"] for row in experiments[arm]["attempts"]}:
            candidate = [row for row in experiments[arm]["attempts"] if row["case"] == case]
            reference = [row for row in baseline["attempts"] if row["case"] == case]
            candidate_cost = sum(Decimal(row["estimated_cost_usd"]) for row in candidate)
            reference_cost = sum(Decimal(row["estimated_cost_usd"]) for row in reference)
            comparisons[arm][case] = {
                "candidate_cost_usd": str(candidate_cost), "sol_cost_usd": str(reference_cost),
                "candidate_generation_seconds": sum(row["latency_seconds"] for row in candidate),
                "sol_generation_seconds": sum(row["latency_seconds"] for row in reference),
                "cost_reduction_percent": float((1 - candidate_cost / reference_cost) * 100)}
    report = {"rates_per_million_usd": RATES,
              "pricing_sources": ["https://developers.openai.com/api/docs/pricing",
                                  "https://developers.openai.com/api/docs/guides/prompt-caching"],
              "assumptions": ["Estimated, not an invoice. Default 30-minute writes at1.25x ordinary input.",
                              "No request exceeds272000 tokens; returned service tier is default.",
                              "Output includes reasoning tokens, not billed twice.",
                              "Token-count fees/latency and native Codex work excluded.",
                              "Per-request generation latency excludes count calls and local processing.",
                              "Summed latency is not wall time; cases run concurrently.",
                              "Single saved-case draws do not establish quality consistency."],
              "experiments": experiments, "sol_baseline": baseline,
              "per_case_comparisons": comparisons}
    (ROOT / "metadata.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"experiments": {key: {k: v for k, v in value.items() if k != "attempts"}
                                       for key, value in experiments.items()},
                      "per_case_comparisons": comparisons}, indent=2))


if __name__ == "__main__":
    main()
