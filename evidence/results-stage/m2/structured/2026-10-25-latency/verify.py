"""Recompute probe checks and integrity offline; summarize all attempts, including failures."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from factor import factor, restore
from pydantic import ValidationError

from award_agent.results.contracts import ResultsConfig
from award_agent.results.structured import (
    check_structured_document,
    prepare_structured_results,
    resolve_structured_document,
)
from award_agent.results.structured_contracts import StructuredDocument, StructuredResultsArtifact

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "2026-10-25-cost-experiments/luna-retest/round-1"


def read(path: Path):
    return json.loads(path.read_text())


def main() -> None:
    rows = []
    calls = [read(p) for p in sorted(ROOT.glob("call-*.json"))]
    assert len(calls) <= 8
    for call in calls:
        directory = ROOT / call["name"]
        meta = read(directory / "source.json")
        source = SOURCE / meta["case"]
        original_bytes = (source / "01-request.json").read_bytes()
        assert hashlib.sha256(original_bytes).hexdigest() == meta["original_request_sha256"]
        assert hashlib.sha256((source / "artifact.json").read_bytes()).hexdigest() == meta["source_artifact_sha256"]
        original = json.loads(original_bytes)
        expected = original if meta["variant"] == "original" else factor(original)
        if meta["variant"] != "original":
            assert restore(expected) == original
        expected = dict(expected, reasoning={"effort": meta["effort"]},
                        max_output_tokens=32768, store=False, truncation="disabled", stream=True)
        assert read(directory / "request.json") == expected
        if (directory / "error.json").exists():
            row = {"name": call["name"], "error": read(directory / "error.json"),
                   "request_integrity": "passed"}
            if (directory / "timing.json").exists():
                timing = read(directory / "timing.json")
                raw = read(directory / "response.json")
                assert raw["usage"] == timing["usage"]
                output = "".join(part["text"] for item in raw["output"] if item["type"] == "message"
                                 for part in item["content"] if part["type"] == "output_text")
                try:
                    StructuredDocument.model_validate_json(output)
                except ValidationError:
                    assert row["error"]["type"] == "ValidationError"
                    row["schema_failure_reproduced"] = True
                else:
                    raise AssertionError("saved schema error did not reproduce")
                row["timing"] = timing
            rows.append(row)
            continue
        response = read(directory / "response.json")
        timing = read(directory / "timing.json")
        assert response["usage"] == timing["usage"]
        assert response["reasoning"]["effort"] == meta["effort"]
        text = "".join(part["text"] for item in response["output"] if item["type"] == "message"
                       for part in item["content"] if part["type"] == "output_text")
        document = StructuredDocument.model_validate_json(text)
        assert document.model_dump(mode="json") == read(directory / "document.json")
        artifact = StructuredResultsArtifact.model_validate_json((source / "artifact.json").read_text())
        config = ResultsConfig.model_validate_json((source / "config.json").read_text())
        prepared = prepare_structured_results(artifact.evidence.source, config)
        findings = check_structured_document(document, artifact.evidence.source, prepared)
        assert [f.model_dump(mode="json") for f in findings] == read(directory / "findings.json")
        resolved = resolve_structured_document(document, prepared, artifact.evidence, findings)
        assert resolved.model_dump(mode="json") == read(directory / "resolved.json")
        usage = timing["usage"]
        rows.append({"name": call["name"], "case": meta["case"],
                     "effort": meta["effort"], "variant": meta["variant"],
                     "first_text_seconds": timing["first_text_seconds"],
                     "full_response_seconds": timing["full_response_seconds"],
                     "input_tokens": usage["input_tokens"],
                     "cached_tokens": usage["input_tokens_details"]["cached_tokens"],
                     "output_tokens": usage["output_tokens"],
                     "reasoning_tokens": usage["output_tokens_details"]["reasoning_tokens"],
                     "failed_checks": sum(f.outcome == "failed" for f in findings),
                     "request_integrity": "passed", "offline_resolution_recheck": "passed"})
    timings = [read(ROOT / call["name"] / "timing.json") for call in calls
               if (ROOT / call["name"] / "timing.json").exists()]
    cost = Decimal(0)
    for timing in timings:
        usage = timing["usage"]
        assert usage["input_tokens"] < 272000
        details = usage["input_tokens_details"]
        cached, writes = details["cached_tokens"], details["cache_write_tokens"]
        ordinary = usage["input_tokens"] - cached - writes
        assert ordinary >= 0
        cost += (Decimal(ordinary) * Decimal("0.10") + Decimal(cached) * Decimal("0.01")
                 + Decimal(writes) * Decimal("0.125")
                 + Decimal(usage["output_tokens"]) * Decimal("0.50")) / Decimal(1000000)
    report = {"generation_attempts": len(calls), "count_calls": 0,
              "total_input_tokens": sum(t["usage"]["input_tokens"] for t in timings),
              "total_output_tokens": sum(t["usage"]["output_tokens"] for t in timings),
              "estimated_generation_cost_usd": str(cost),
              "pricing_source": "https://developers.openai.com/api/docs/pricing",
              "cost_limits": "Estimate using default short-context 30m writes, not invoice; includes failed schema generation; excludes native Codex work.",
              "probes": rows,
              "limits": "Single draws; no correction; streamed JSON is usable only after parsing/checking. Not canonical runtime artifacts or historical replay qualification."}
    (ROOT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
