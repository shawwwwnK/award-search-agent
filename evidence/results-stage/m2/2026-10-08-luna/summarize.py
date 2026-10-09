"""Verify and summarize every retained Luna generation attempt, without API calls."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.contracts import ResultsArtifact, ResultsConfig
from award_agent.results.core import replay_results

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CASES = (
    ("baseline", "sfo_to_bkk_positioning"),
    ("guided", "sfo_to_bkk_positioning"),
    ("guided", "exact_business"),
    ("guided", "mixed_access"),
    ("bound", "sfo_to_bkk_positioning"),
    ("bound", "exact_business"),
    ("bound", "mixed_access"),
    ("declared", "sfo_to_bkk_positioning"),
    ("declared", "exact_business"),
    ("declared", "mixed_access"),
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cost(input_tokens: int, output_tokens: int, cached_tokens: int) -> tuple[str, float]:
    tier = "long" if input_tokens > 272_000 else "short"
    input_rate, output_rate = ((0.20, 0.75) if tier == "long" else (0.10, 0.50))
    amount = ((input_tokens - cached_tokens) * input_rate +
              cached_tokens * input_rate * 0.10 + output_tokens * output_rate) / 1_000_000
    return tier, amount


def main() -> None:
    rows: list[dict[str, object]] = []
    totals: Counter[str] = Counter()
    total_cost = 0.0
    for label, case in CASES:
        stem = case if label == "baseline" else f"{case}.{label}"
        artifact_path = OUT / f"{stem}.artifact.json"
        markdown_path = OUT / f"{stem}.md"
        config_path = OUT / ("baseline.original.config.json" if label == "baseline"
                             else f"{label}.config.json")
        source_path = ROOT / "evidence/ranking-stage/m2/solutions" / f"{case}.json"
        artifact = ResultsArtifact.model_validate_json(artifact_path.read_text())
        replayed = replay_results(artifact).encode("utf-8")
        saved = markdown_path.read_bytes()
        if replayed != saved:
            raise ValueError(f"{stem}: saved Markdown differs from exact replay")
        source = SolutionProjection.model_validate_json(source_path.read_text())
        if artifact.projection != source:
            raise ValueError(f"{stem}: projection differs from retained Ranking source")
        config = ResultsConfig.model_validate_json(config_path.read_text())
        config_matches_artifact = artifact.config == config
        attempts: list[dict[str, object]] = []
        for attempt in artifact.attempts:
            receipt = attempt.writer_receipt
            raw = json.loads(receipt.raw_response) if receipt and receipt.raw_response else None
            usage = raw.get("usage") if isinstance(raw, dict) else None
            if not isinstance(usage, dict):
                usage = receipt.usage if receipt else {}
            input_tokens = int(usage.get("input_tokens", 0))
            output_tokens = int(usage.get("output_tokens", 0))
            details = usage.get("input_tokens_details", {})
            output_details = usage.get("output_tokens_details", {})
            cached = int(details.get("cached_tokens", 0)) if isinstance(details, dict) else 0
            cache_write = int(details.get("cache_write_tokens", 0)) if isinstance(details, dict) else 0
            reasoning = int(output_details.get("reasoning_tokens", 0)) if isinstance(output_details, dict) else 0
            tier, cost = _cost(input_tokens, output_tokens, cached)
            if attempt.writer_called:
                totals["writer_calls"] += 1
                totals["input_tokens"] += input_tokens
                totals["output_tokens"] += output_tokens
                totals["cached_input_tokens"] += cached
                totals["cache_write_tokens"] += cache_write
                totals["reasoning_output_tokens"] += reasoning
                total_cost += cost
            outcomes = dict(Counter(finding.outcome for finding in attempt.findings))
            attempts.append({
                "phase": attempt.phase,
                "outcome": attempt.outcome,
                "failure_subtype": attempt.failure_subtype,
                "error": attempt.error,
                "writer_called": attempt.writer_called,
                "counted_input_tokens": (attempt.input_token_receipt.input_tokens
                                         if attempt.input_token_receipt else None),
                "count_request_digest": (attempt.input_token_receipt.request_digest
                                         if attempt.input_token_receipt else None),
                "writer_status": receipt.status if receipt else None,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "reasoning_output_tokens": reasoning,
                "cached_input_tokens": cached,
                "cache_write_tokens": cache_write,
                "latency_seconds": receipt.latency_seconds if receipt else None,
                "finding_outcomes": outcomes,
                "failed_finding_codes": [finding.code for finding in attempt.findings
                                         if finding.outcome == "failed"],
                "rate_tier": tier if attempt.writer_called else None,
                "estimated_generation_cost_usd": round(cost, 8) if attempt.writer_called else 0,
                "raw_response_retained": bool(receipt and receipt.raw_response),
            })
        rows.append({
            "label": label, "case": case,
            "artifact": artifact_path.relative_to(ROOT).as_posix(),
            "artifact_sha256": _digest(artifact_path),
            "markdown": markdown_path.relative_to(ROOT).as_posix(),
            "markdown_sha256": _digest(markdown_path),
            "replay_bytes_equal": True,
            "replay_bytes": len(saved),
            "rendered_digest": artifact.rendered_digest,
            "projection": source_path.relative_to(ROOT).as_posix(),
            "projection_sha256": _digest(source_path),
            "config": config_path.relative_to(ROOT).as_posix(),
            "config_sha256": _digest(config_path),
            "config_matches_artifact": config_matches_artifact,
            "artifact_config": artifact.config.model_dump(mode="json"),
            "selected_attempt": artifact.selected_attempt,
            "selection_reason": artifact.selection_reason,
            "generation_outcome": artifact.generation_outcome,
            "validation_outcome": artifact.validation_outcome,
            "delivery_outcome": artifact.delivery_outcome,
            "notices": len(artifact.notices),
            "attempts": attempts,
        })
    summary = {
        "scope": "All retained Luna baseline, guided, bound and declared generation attempts; no provider refresh.",
        "baseline_config_note": "baseline.original.config.json was derived from the baseline artifact's embedded config after config.json gained max_input_tokens for later runs; it is not a pre-run declaration.",
        "cost_basis": "Per-call Luna short: $0.10 input/$0.50 output per million; long input >272000: $0.20 input/$0.75 output; cached input 10% of tier input rate. No discount for cache writes. Counting endpoint billing unclaimed.",
        "generation_totals": {**totals, "estimated_generation_cost_usd": round(total_cost, 8)},
        "runs": rows,
        "qualification": "Local model diagnostic and exact replay only; no M3 semantic or owner qualification.",
    }
    destination = OUT / "summary.json"
    if destination.exists():
        if json.loads(destination.read_text()) != summary:
            raise ValueError("saved Luna summary differs from retained evidence")
        print(json.dumps({"summary": str(destination), "verified_runs": len(rows),
                          **summary["generation_totals"]}))
        return
    destination.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"summary": str(destination), "runs": len(rows),
                      **summary["generation_totals"]}))


if __name__ == "__main__":
    main()
