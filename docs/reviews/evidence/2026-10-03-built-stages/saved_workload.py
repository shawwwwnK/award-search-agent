"""Project recorded diagnostics into workload summaries; run from repo root.

These are recorded stage metrics, not a benchmark or end-to-end latency
measurement. The intent corpus and provider runs are different workloads and
must not be added into a composed-app latency or dollar-cost claim. This
script reads local evidence only and makes no network, model, provider, or
credential calls. Required metric keys fail explicitly when absent.
"""

import json
from pathlib import Path
from statistics import median


INTENT_PATH = Path(
    "evals/intent_to_search_planning/baseline/"
    "2026-09-20-gpt-5.6-luna-active-intent-corpus-1-trial.json"
)
PROVIDER_ROOT = Path("evidence/provider-stage/saved-searches/runs")
PROVIDER_RUNS = ("mixed_access", "exact_business", "sfo_to_bkk_positioning")
USAGE_KEYS = ("calls", "input_tokens", "output_tokens", "total_tokens")


def require(mapping, key, context):
    if key not in mapping:
        raise KeyError(f"missing required field {context}.{key}")
    return mapping[key]


def intent_summary(records):
    latencies = [require(record, "latency_seconds", "record") for record in records]
    usage_totals = {
        key: sum(require(require(record, "usage", "record"), key, "usage") for record in records)
        for key in USAGE_KEYS
    }
    return {
        "n": len(records),
        "intent_behavior_passed": sum(
            require(record, "intent_behavior_passed", "record") is True for record in records
        ),
        "latency_seconds": {
            "sum": round(sum(latencies), 3),
            "median": round(median(latencies), 3) if latencies else None,
        },
        "usage": usage_totals,
    }


intent = json.loads(INTENT_PATH.read_text())
records = require(intent, "records", "intent corpus")
groups = {
    "all": records,
    "planning_eligible": [r for r in records if require(r, "planning_eligible", "record") is True],
    "not_planning_eligible": [r for r in records if require(r, "planning_eligible", "record") is False],
}
result = {
    "scope": "recorded per-stage metrics; no benchmark rerun",
    "intent_source": str(INTENT_PATH),
    "intent": {name: intent_summary(group) for name, group in groups.items()},
    "provider_source_root": str(PROVIDER_ROOT),
    "provider_runs": {},
    "interpretation": (
        "Intent and provider observations are different workloads. Do not sum them as composed-app "
        "latency or dollar costs. Provider transport receipt elapsed totals are recorded acquisition "
        "durations and are not a measured user-facing end-to-end latency."
    ),
}

for run_name in PROVIDER_RUNS:
    path = PROVIDER_ROOT / run_name / "result.json"
    saved = json.loads(path.read_text())
    award = require(saved, "award_usage", run_name)
    cash = require(saved, "cash_usage", run_name)
    receipts = require(saved, "transport_receipts", run_name)
    result["provider_runs"][run_name] = {
        "source": str(path),
        "award_usage": {
            "requests": require(award, "requests", f"{run_name}.award_usage"),
            "elapsed_seconds": require(award, "elapsed_seconds", f"{run_name}.award_usage"),
        },
        "cash_usage": {
            "requests": require(cash, "requests", f"{run_name}.cash_usage"),
            "elapsed_seconds": require(cash, "elapsed_seconds", f"{run_name}.cash_usage"),
        },
        "transport_receipt_count": len(receipts),
        "transport_receipt_elapsed_seconds_sum": round(
            sum(require(receipt, "elapsed_seconds", f"{run_name}.transport_receipt") for receipt in receipts),
            3,
        ),
    }

print(json.dumps(result, indent=2))
