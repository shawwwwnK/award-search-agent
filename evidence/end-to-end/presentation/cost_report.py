"""Estimate this session's Results writer spend from saved raw usage receipts."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MILLION = Decimal(1_000_000)
THRESHOLD = 272_000
# Standard rates published for the 2026-10-09 run; dollars per million tokens.
# Tuple order: ordinary input, cached input read, cache write, output.
RATES = {
    "gpt-6-luna": {
        "short": ("0.10", "0.01", "0.125", "0.50"),
        "long": ("0.20", "0.02", "0.25", "0.75"),
    },
    "gpt-6.1-sol": {
        "short": ("2", "0.10", "2.50", "10"),
        "long": ("4", "0.20", "5", "15"),
    },
}


def money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.00000001')):,.8f}"


def main() -> None:
    attempts: list[dict] = []
    for iteration in sorted((ROOT / "iterations").iterdir()):
        if not iteration.is_dir() or not (iteration / "config.json").exists():
            continue
        model = json.loads((iteration / "config.json").read_text())["model"]
        if model not in RATES:
            raise ValueError(f"unknown rate for {model}")
        for case in sorted(iteration.iterdir()):
            artifact_path = case / "artifact.json"
            if not artifact_path.exists():
                continue
            artifact = json.loads(artifact_path.read_text())
            for number, attempt in enumerate(artifact["attempts"], 1):
                count = attempt.get("input_token_receipt")
                writer = attempt.get("writer_receipt")
                usage = None
                if writer and writer.get("raw_response"):
                    raw = json.loads(writer["raw_response"])
                    usage = raw.get("usage")
                if not usage and writer and writer.get("usage"):
                    raise ValueError(f"{iteration.name}/{case.name}/{number}: raw usage missing")
                estimated = None
                ordinary = read_cached = write_cached = output = 0
                rate_tier = None
                if usage:
                    input_total = usage["input_tokens"]
                    details = usage.get("input_tokens_details", {})
                    read_cached = details.get("cached_tokens", 0)
                    write_cached = details.get("cache_write_tokens", 0)
                    ordinary = input_total - read_cached - write_cached
                    output = usage["output_tokens"]
                    if ordinary < 0:
                        raise ValueError("cache tokens exceed reported input")
                    rate_tier = "long" if input_total > THRESHOLD else "short"
                    rates = [Decimal(value) for value in RATES[model][rate_tier]]
                    estimated = sum((Decimal(tokens) * rate / MILLION
                                     for tokens, rate in zip((ordinary, read_cached,
                                                              write_cached, output), rates)),
                                    Decimal(0))
                attempts.append({
                    "iteration": iteration.name,
                    "case": case.name,
                    "attempt": number,
                    "phase": attempt["phase"],
                    "model": model,
                    "rate_tier": rate_tier,
                    "measurement_call": count is not None,
                    "measured_input_tokens": count["input_tokens"] if count else None,
                    "writer_called": attempt["writer_called"],
                    "writer_usage": usage,
                    "ordinary_input_tokens": ordinary,
                    "cached_read_tokens": read_cached,
                    "cache_write_tokens": write_cached,
                    "output_tokens": output,
                    "estimated_writer_usd": str(estimated) if estimated is not None else None,
                })
    by_model: dict[str, Decimal] = {}
    for attempt in attempts:
        if attempt["estimated_writer_usd"] is not None:
            model = attempt["model"]
            by_model[model] = by_model.get(model, Decimal(0)) + Decimal(
                attempt["estimated_writer_usd"])
    overall = sum(by_model.values(), Decimal(0))
    report = {
        "scope": "live Results authoring calls in presentation/iterations only",
        "rate_date": "2026-10-09",
        "pricing_url": "https://developers.openai.com/api/docs/pricing",
        "long_context_threshold_input_tokens": THRESHOLD,
        "rate_usd_per_million": RATES,
        "measurement_calls": sum(attempt["measurement_call"] for attempt in attempts),
        "writer_calls": sum(attempt["writer_called"] for attempt in attempts),
        "estimated_writer_usd_by_model": {model: str(total) for model, total in by_model.items()},
        "estimated_writer_usd_total": str(overall),
        "attempts": attempts,
    }
    (ROOT / "cost-report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Results presentation API usage and estimated writer cost", "",
             "Scope: live Results authoring in `iterations/` only. This excludes the original",
             "end-to-end diagnostic, offline fixtures, other sessions, and any cost of the",
             "input-token measurement endpoint. It is a rate-based estimate, not an invoice.", "",
             "Rates: [OpenAI API pricing](https://developers.openai.com/api/docs/pricing),",
             "Standard tier as recorded for October 9, 2026. Sixteen writer requests",
             "exceeded 272,000 input tokens and use long-context rates for the entire request;",
             "the final incomplete-case request used 253,293 input tokens and short-context rates.",
             "Ordinary input is reported input minus cached-read and cache-write tokens;",
             "output already includes reasoning tokens. Cache writes are billed separately.", "",
             "| Iteration | Case | Attempt | Model | Input | Cached read | Cache write | Output | Estimated writer cost |",
             "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for item in attempts:
        cost = (money(Decimal(item["estimated_writer_usd"]))
                if item["estimated_writer_usd"] is not None else "No writer usage")
        input_total = (item["writer_usage"] or {}).get("input_tokens", 0)
        lines.append(f"| {item['iteration']} | {item['case']} | {item['phase']} | {item['model']} | "
                     f"{input_total:,} | {item['cached_read_tokens']:,} | "
                     f"{item['cache_write_tokens']:,} | {item['output_tokens']:,} | {cost} |")
    lines += ["", f"Writer calls: **{report['writer_calls']}**. Input-token measurement calls: "
              f"**{report['measurement_calls']}**. Estimated writer cost by model: " +
              "; ".join(f"{model} {money(total)}" for model, total in by_model.items()) +
              f". Total: **{money(overall)}**.", "",
              "`cost-report.json` preserves each attempt's complete raw usage object, its",
              "token categories, rate tier and unrounded calculated amount. It does not",
              "estimate the cost of the separate measurement endpoint or reconcile an invoice.", ""]
    (ROOT / "cost-report.md").write_text("\n".join(lines))
    print(f"{len(attempts)} attempts, {report['writer_calls']} writer calls, "
          f"{report['measurement_calls']} measurement calls, {money(overall)} estimated writer cost")


if __name__ == "__main__":
    main()
