"""Isolated saved-request latency probe; no runtime edits or automatic retries."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from award_agent.results.contracts import ResultsConfig
from award_agent.results.structured import (
    check_structured_document,
    prepare_structured_results,
    resolve_structured_document,
)
from award_agent.results.structured_contracts import StructuredDocument, StructuredResultsArtifact

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
SOURCE = ROOT.parent / "2026-10-25-cost-experiments/luna-retest/round-1"


def save(path: Path, value: object) -> None:
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def run(case: str, effort: str, variant: str, name: str) -> None:
    directory = ROOT / name
    directory.mkdir(exist_ok=False)
    source = SOURCE / case
    request_bytes = (source / "01-request.json").read_bytes()
    request = json.loads(request_bytes)
    assert request["model"] == "gpt-6-luna"
    request["reasoning"] = {"effort": effort}
    if variant != "original":
        request = json.loads((ROOT / f"{case}-{variant}-request.json").read_text())
        request["reasoning"] = {"effort": effort}
    request.update(max_output_tokens=32768, store=False, truncation="disabled", stream=True)
    save(directory / "request.json", request)
    save(directory / "source.json", {
        "case": case, "effort": effort, "variant": variant,
        "original_request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "source_artifact_sha256": hashlib.sha256((source / "artifact.json").read_bytes()).hexdigest(),
    })
    load_dotenv(REPO / ".env")
    client = OpenAI(max_retries=0, timeout=240)
    # Reserve before invocation; failed/transport calls consume the bound too.
    for index in range(1, 9):
        try:
            save(ROOT / f"call-{index:02}.json", {"name": name, "status": "reserved"})
            break
        except FileExistsError:
            continue
    else:
        raise ValueError("eight-call experiment bound reached")
    started = time.perf_counter()
    first_event = first_text = None
    response = None
    try:
        with client.responses.create(**request) as events:
            for event in events:
                elapsed = time.perf_counter() - started
                if first_event is None:
                    first_event = elapsed
                if event.type == "response.output_text.delta" and first_text is None:
                    first_text = elapsed
                if event.type == "response.completed" or event.type == "response.incomplete":
                    response = event.response
        elapsed = time.perf_counter() - started
        if response is None:
            raise ValueError("stream ended without final response")
        save(directory / "response.json", response.model_dump(mode="json"))
        metrics = {"case": case, "effort": effort, "variant": variant,
                   "first_event_seconds": first_event, "first_text_seconds": first_text,
                   "full_response_seconds": elapsed, "status": response.status,
                   "usage": None if response.usage is None else response.usage.model_dump(mode="json"),
                   "returned_reasoning": response.reasoning.model_dump(mode="json") if response.reasoning else None}
        save(directory / "timing.json", metrics)
        artifact = StructuredResultsArtifact.model_validate_json((source / "artifact.json").read_text())
        document = StructuredDocument.model_validate_json(response.output_text)
        config = ResultsConfig.model_validate_json((source / "config.json").read_text())
        prepared = prepare_structured_results(artifact.evidence.source, config)
        findings = check_structured_document(document, artifact.evidence.source, prepared)
        resolved = resolve_structured_document(document, prepared, artifact.evidence, findings)
        save(directory / "document.json", document.model_dump(mode="json"))
        save(directory / "findings.json", [f.model_dump(mode="json") for f in findings])
        save(directory / "resolved.json", resolved.model_dump(mode="json"))
        preview = []
        for block in resolved.blocks:
            preview.append(block.text)
            if block.kind == "reference":
                preview.append(f"[Display: {block.label}; {block.reference_kind}; {block.canonical_id}]")
        (directory / "answer-preview.md").write_text("\n\n".join(preview) + "\n")
        print(json.dumps(metrics), flush=True)
    except Exception as exc:
        save(directory / "error.json", {"type": type(exc).__name__,
             "elapsed_seconds": time.perf_counter() - started,
             "first_event_seconds": first_event, "first_text_seconds": first_text})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("admitted", "conditional", "incomplete"), required=True)
    parser.add_argument("--effort", choices=("medium", "low", "none"), required=True)
    parser.add_argument("--variant", default="original")
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    run(args.case, args.effort, args.variant, args.name)
