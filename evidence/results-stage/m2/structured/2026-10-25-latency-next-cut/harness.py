"""Bounded, isolated Luna Results latency experiment on saved projections.

This is a diagnostic, not a Results artifact writer. It uses the production
preparation, checks, resolution and bounded attempt runner, while keeping
experimental request transforms and parallel analysis out of the runtime.
No endpoint is called without --live and a pre-existing campaign.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import httpx
from dotenv import load_dotenv
from openai import APIError, OpenAI

from award_agent.providers.contracts import content_digest
from award_agent.results.contracts import (
    CheckFinding,
    InputTokenReceipt,
    ResultsConfig,
    ResultsWriterError,
    WriterReceipt,
)
from award_agent.results.presentation import resolve_workspace
from award_agent.results.runner import RequestEnvelope, run_attempts
from award_agent.results.structured import (
    _bound_document,
    check_structured_document,
    prepare_structured_results,
    resolve_structured_document,
    structured_payload,
    structured_token_request,
)
from award_agent.results.structured_contracts import (
    StructuredDocument,
    StructuredPreparedInput,
    StructuredResultsArtifact,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"
CAMPAIGN = HERE / "campaign.json"
CASES = ("admitted", "conditional", "incomplete")
Variant = Literal["original", "candidate", "parallel"]
CandidateVersion = Literal["v1", "v2"]

WORKER_SCHEMA: dict[str, object] = {
    "type": "object", "additionalProperties": False,
    "properties": {"findings": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"refs": {"type": "array", "items": {"type": "string"}},
                       "finding": {"type": "string"}},
        "required": ["refs", "finding"]}}},
    "required": ["findings"],
}

WORKER_INSTRUCTIONS = {
    "choices": ("Read every relevant eligible journey in the supplied prepared Results evidence. "
        "Return a short JSON list of decision-changing comparisons with exact J aliases. "
        "Look across cabin choices, especially equal-schedule economy/business options, "
        "and distinguish same schedule from identical flight or booking facts. Check full "
        "arrival dates and points programs. Do not select an exclusive shortlist or author prose."),
    "limits": ("Read the supplied prepared Results evidence. Return a short JSON list of "
        "applicable limits tied to exact J, C, or A aliases: price scope, cabin, traveler, "
        "separate tickets, and dated availability. Preserve unknowns. Do not recommend "
        "journeys, select a benchmark, or author the answer."),
}

FINAL_WORKER_GUIDANCE = ("\nThe two analysis reports in input are fallible aids, not source "
    "facts or a shortlist. Check their exact aliases and claims against prepared evidence; "
    "retain access to every eligible journey. You still own the complete choice argument, "
    "selection, narrative, references, and limitations.\n")

V2_WORKER_FACT_GUIDE = (
    "\nFor each J alias, choice.identity repeats that exact member's full dated "
    "journey route, schedule, duration, cabin and booking obligation. "
    "choice.award_quote.carriers and cabin are reported component facts; the "
    "points program is not a flight carrier. choice.traveler_seat_assessment "
    "lists that journey's traveler and minimum-seat reason states. Interpret these "
    "separately from price_scope and preserve unknown evidence.\n"
)
V2_WORKER_REFERENCE_GUIDE = (
    "Each refs array item must be one existing exact J, A or C alias, or an existing "
    "comparison-pool alias only when it maps to the entire eligible journey pool. "
    "Do not use ranges (such as J1–J232), comma-joined aliases, or prose in refs. "
    "P1 describes the whole eligible pool, never a separate-ticket subset. For a "
    "subset, enumerate exact aliases or name clearly scoped examples in finding "
    "without claiming exhaustive coverage. Do not invent or expand aliases.\n"
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reserve(kind: Literal["count", "generation"], label: str,
            campaign: dict[str, Any], *, run_name: str,
            request_digest: str) -> int:
    """Reserve an attempted paid call atomically before sending it."""
    limit = campaign["maximum_input_count_calls" if kind == "count"
                     else "maximum_generation_calls"]
    for index in range(1, limit + 1):
        try:
            write_json(HERE / "calls" / f"{kind}-{index:03}.json",
                       {"run_name": run_name, "label": label,
                        "request_digest": request_digest,
                        "reserved_at_utc": datetime.now(UTC).isoformat(),
                        "status": "reserved_before_invocation"})
        except FileExistsError:
            continue
        return index
    raise ValueError(f"campaign {kind} bound exhausted ({limit})")


def _schema_digest(request: dict[str, object]) -> str:
    return cast(str, content_digest(cast(dict[str, object], request["text"])["format"]))


def _envelope(request: dict[str, object], config: ResultsConfig) -> RequestEnvelope:
    prompt = cast(str, request["instructions"]) + cast(str, request["input"])
    schema_bytes = len(json.dumps(request["text"], sort_keys=True).encode())
    size = len(prompt.encode()) + schema_bytes
    return RequestEnvelope(request=request, input_bytes=size,
        estimated_total_tokens=size + config.prompt_overhead_tokens + config.max_output_tokens,
        prompt_digest=content_digest(prompt), schema_digest=_schema_digest(request))


class Endpoint:
    def __init__(self, directory: Path, campaign: dict[str, Any],
                 config: ResultsConfig, client: OpenAI) -> None:
        self.directory, self.campaign, self.config, self.client = (
            directory, campaign, config, client)
        self.count_seconds = 0.0
        self.generation_seconds = 0.0

    def count(self, request: dict[str, object], label: str) -> InputTokenReceipt:
        directory = self.directory / label
        directory.mkdir(parents=True, exist_ok=True)
        write_json(directory / "count-request.json", request)
        reserve("count", label, self.campaign, run_name=self.directory.name,
                request_digest=content_digest(request))
        started = time.perf_counter()
        try:
            raw = self.client.with_options(max_retries=0,
                timeout=self.config.timeout_seconds).post(
                    "/responses/input_tokens", body=request, cast_to=dict[str, object])
            if not isinstance(raw, dict) or raw.get("object") != "response.input_tokens":
                raise ValueError("invalid input token response object")
            count = raw.get("input_tokens")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("invalid input token count")
            receipt = InputTokenReceipt(request_digest=content_digest(request),
                input_tokens=count, raw_response=raw)
            write_json(directory / "count-receipt.json", receipt.model_dump(mode="json"))
            write_json(directory / "count-timing.json", {
                "full_response_seconds": time.perf_counter() - started})
            return receipt
        except (APIError, KeyError, TypeError, ValueError) as exc:
            write_json(directory / "count-error.json", {"type": type(exc).__name__,
                "elapsed_seconds": time.perf_counter() - started})
            raise ResultsWriterError("api_error", "input token measurement failed") from exc
        finally:
            self.count_seconds += time.perf_counter() - started

    def generate(self, request: dict[str, object], label: str,
                 *, max_output_tokens: int) -> tuple[str, WriterReceipt]:
        directory = self.directory / label
        directory.mkdir(parents=True, exist_ok=True)
        full_request = dict(request, max_output_tokens=max_output_tokens,
                            store=False, truncation="disabled", stream=True)
        write_json(directory / "generation-request.json", full_request)
        reserve("generation", label, self.campaign, run_name=self.directory.name,
                request_digest=content_digest(full_request))
        started = time.perf_counter()
        first_event = first_text = None
        events_seen = text_delta_events = 0
        response = None
        try:
            with self.client.with_options(max_retries=0,
                timeout=self.config.timeout_seconds).responses.create(**cast(Any, full_request)) as events:
                for event in events:
                    elapsed = time.perf_counter() - started
                    events_seen += 1
                    if first_event is None:
                        first_event = elapsed
                    if event.type == "response.output_text.delta":
                        text_delta_events += 1
                        if first_text is None:
                            first_text = elapsed
                    if event.type in ("response.completed", "response.incomplete"):
                        response = event.response
            if response is None:
                raise ValueError("stream ended without a final response")
            elapsed = time.perf_counter() - started
            raw = response.model_dump(mode="json")
            write_json(directory / "response.json", raw)
            write_json(directory / "generation-timing.json", {
                "first_event_seconds": first_event, "first_text_seconds": first_text,
                "full_response_seconds": elapsed, "status": response.status,
                "usage": raw.get("usage"), "returned_reasoning": raw.get("reasoning")})
            if response.status != "completed":
                subtype = "incomplete" if response.status == "incomplete" else "schema_error"
                raise ResultsWriterError(subtype, "writer response was not completed")
            if any(item.get("type") == "message" and
                   any(part.get("type") == "refusal" for part in item.get("content", []))
                   for item in raw.get("output", [])):
                raise ResultsWriterError("refusal", "writer declined the request")
            receipt = WriterReceipt(status=response.status,
                usage={key: value for key, value in (raw.get("usage") or {}).items()
                       if key in ("input_tokens", "output_tokens", "total_tokens")},
                latency_seconds=elapsed)
            return response.output_text, receipt
        except (APIError, httpx.HTTPError, ValueError) as exc:
            write_json(directory / "generation-error.json", {
                "type": type(exc).__name__,
                "elapsed_seconds": time.perf_counter() - started,
                "first_event_seconds": first_event,
                "first_text_seconds": first_text,
                "events_seen": events_seen,
                "text_delta_events": text_delta_events})
            raise ResultsWriterError("api_error", "generation failed") from exc
        finally:
            self.generation_seconds += time.perf_counter() - started


def worker_request(base: dict[str, object], role: str,
                   effort: str, *, candidate_version: CandidateVersion = "v1") -> dict[str, object]:
    from candidate import GUIDE

    instructions = (WORKER_INSTRUCTIONS[role] +
                    GUIDE.split("Reference contract:", 1)[0])
    if candidate_version == "v2":
        instructions += V2_WORKER_FACT_GUIDE + V2_WORKER_REFERENCE_GUIDE
    return {"model": base["model"],
            "reasoning": {"effort": effort},
            "instructions": instructions,
            "input": base["input"],
            "text": {"format": {"type": "json_schema", "name": "AnalysisFindings",
                                "strict": True, "schema": WORKER_SCHEMA}}}


def parse_worker(text: str, prepared: StructuredPreparedInput, *,
                 candidate_version: CandidateVersion = "v1") -> dict[str, object]:
    report = json.loads(text)
    if not isinstance(report, dict) or not isinstance(report.get("findings"), list):
        raise TypeError("worker response has no findings array")
    known = (set(prepared.references.journeys) | set(prepared.references.cash) |
             set(prepared.references.awards))
    if candidate_version == "v2":
        full_pool = set(prepared.references.journeys.values())
        known.update(alias for alias, members in prepared.references.comparison_pools.items()
                     if len(members) == len(full_pool) and set(members) == full_pool)
    for finding in report["findings"]:
        if not isinstance(finding, dict) or not isinstance(finding.get("finding"), str) \
                or not isinstance(finding.get("refs"), list) or \
                any(not isinstance(ref, str) or ref not in known
                    for ref in finding["refs"]):
            raise ValueError("worker finding lacks valid exact references")
    return cast(dict[str, object], report)


def build_final_request(prepared: StructuredPreparedInput, config: ResultsConfig,
                        variant: Variant, effort: str,
                        feedback: tuple[CheckFinding, ...] = (),
                        previous: StructuredDocument | None = None,
                        workers: dict[str, object] | None = None,
                        *, candidate_version: CandidateVersion = "v1") -> dict[str, object]:
    request = structured_token_request(prepared, config,
                                       structured_payload(prepared, feedback, previous))
    if variant != "original":
        if candidate_version == "v1":
            from candidate import transform
        else:
            from candidate_v2 import transform
        request = transform(request, prepared)
    if workers is not None:
        body = json.loads(cast(str, request["input"]))
        # Preserve the prepared prefix across correction attempts. The final
        # writer still receives its own prior draft and feedback after worker aids.
        body = {"prepared": body["prepared"], "worker_analysis": workers,
                "feedback": body["feedback"],
                "previous_document": body["previous_document"]}
        request["input"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        request["instructions"] = cast(str, request["instructions"]) + FINAL_WORKER_GUIDANCE
    request["reasoning"] = {"effort": effort}
    return cast(dict[str, object], request)


def _preview(resolved: Any) -> str:
    rows = []
    for block in resolved.blocks:
        rows.append(block.text)
        if block.kind == "reference":
            rows.append(f"[Display: {block.label}; {block.reference_kind}; {block.canonical_id}]")
    return "\n\n".join(rows) + "\n"


def run(case: str, variant: Variant, effort: str, name: str, *, live: bool,
        worker_effort: str = "low", candidate_version: CandidateVersion = "v1") -> dict[str, object]:
    if not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("name must contain only letters, digits, - or _")
    if variant == "original" and candidate_version != "v1":
        raise ValueError("original input has no v2 candidate; use candidate version v1")
    campaign = json.loads(CAMPAIGN.read_text())
    assert campaign["maximum_generation_calls"] == 60
    assert campaign["maximum_input_count_calls"] == 60
    source = SOURCE / case
    source_path = source / "artifact.json"
    config_path = source / "config.json"
    if not live:
        return {"case": case, "variant": variant, "effort": effort,
                "candidate_version": candidate_version if variant != "original" else None,
                "source_sha256": sha256(source_path), "mode": "offline"}
    directory = HERE / "runs" / name
    directory.mkdir(parents=True, exist_ok=False)
    runtime_files = sorted((REPO / "src/award_agent/results").glob("*.py"))
    candidate_paths = (() if variant == "original" else
                       (HERE / "candidate.py",) if candidate_version == "v1" else
                       (HERE / "candidate.py", HERE / "candidate_v2.py"))
    snapshot_paths = [Path(__file__), CAMPAIGN, source_path, config_path,
                      *runtime_files, *candidate_paths]
    write_json(directory / "settings.json", {"case": case, "variant": variant,
        "effort": effort, "worker_effort": worker_effort,
        "candidate_version": candidate_version if variant != "original" else None,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "source_sha256": sha256(source_path), "config_sha256": sha256(config_path),
        "harness_sha256": sha256(Path(__file__)),
        "candidate_sha256": sha256(candidate_paths[-1]) if candidate_paths else None,
        "candidate_dependency_sha256": (sha256(HERE / "candidate.py")
                                        if candidate_version == "v2" and candidate_paths else None)})
    write_json(directory / "source-snapshot.json", {
        str(path.relative_to(REPO)): sha256(path) for path in snapshot_paths})
    with zipfile.ZipFile(directory / "source-snapshot.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in snapshot_paths:
            archive.write(path, str(path.relative_to(REPO)))
    load_dotenv(REPO / ".env")
    client = OpenAI(max_retries=0, timeout=240)
    started = time.perf_counter()
    source_artifact = StructuredResultsArtifact.model_validate_json(source_path.read_text())
    projection = source_artifact.evidence.source
    config = ResultsConfig.model_validate_json(config_path.read_text()).model_copy(
        update={"model": "gpt-6-luna", "timeout_seconds": 240.0,
                "max_output_tokens": 32768})
    evidence = resolve_workspace(projection)
    prepared = prepare_structured_results(projection, config)
    preparation_seconds = time.perf_counter() - started
    endpoint = Endpoint(directory, campaign, config, client)
    workers: dict[str, object] | None = None
    worker_wall_seconds = 0.0
    if variant == "parallel":
        worker_started = time.perf_counter()
        base = build_final_request(prepared, config, "candidate", effort,
                                   candidate_version=candidate_version)

        def one_worker(role: str) -> tuple[str, dict[str, object]]:
            request = worker_request(base, role, worker_effort,
                                     candidate_version=candidate_version)
            receipt = endpoint.count(request, f"worker-{role}")
            if (config.max_input_tokens is not None and receipt.input_tokens > config.max_input_tokens) \
                    or receipt.input_tokens + 4096 + config.prompt_overhead_tokens > config.context_limit_tokens:
                raise ValueError(f"worker {role} context limit")
            text, _ = endpoint.generate(request, f"worker-{role}", max_output_tokens=4096)
            report = parse_worker(text, prepared, candidate_version=candidate_version)
            write_json(directory / f"worker-{role}" / "findings.json", report)
            return role, report

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(one_worker, role) for role in ("choices", "limits")]
                results = [future.result() for future in futures]
            workers = dict(results)
        except Exception as exc:
            elapsed = time.perf_counter() - started
            write_json(directory / "worker-failure.json", {"type": type(exc).__name__,
                "elapsed_seconds": elapsed})
            write_json(directory / "summary.json", {
                "case": case, "variant": variant, "effort": effort,
                "candidate_version": candidate_version,
                "generation_outcome": "worker_failure",
                "results_completion_seconds": elapsed,
                "timing_scope": "Saved projection through explicit worker failure; no final composer invoked.",
                "source_sha256": sha256(source_path)})
            raise
        finally:
            worker_wall_seconds = time.perf_counter() - worker_started

    final_count_seconds = 0.0
    final_generation_seconds = 0.0
    check_seconds = 0.0
    final_requests: list[dict[str, object]] = []
    receipts: list[WriterReceipt] = []
    generation_index = 0

    class Measurer:
        def measure(self, request: dict[str, object], _config: ResultsConfig) -> InputTokenReceipt:
            nonlocal final_count_seconds
            label = f"final-{len(final_requests):02d}"
            before = time.perf_counter()
            try:
                return endpoint.count(request, label)
            finally:
                final_count_seconds += time.perf_counter() - before

    def request_for(feedback: tuple[CheckFinding, ...],
                    previous: StructuredDocument | None) -> RequestEnvelope:
        request = build_final_request(prepared, config, variant, effort,
                                      feedback, previous, workers,
                                      candidate_version=candidate_version)
        final_requests.append(request)
        return _envelope(request, config)

    def invoke(_feedback: tuple[CheckFinding, ...],
               _previous: StructuredDocument | None) -> StructuredDocument:
        nonlocal final_generation_seconds, generation_index
        generation_index += 1
        index = generation_index
        request = final_requests[index - 1]
        before = time.perf_counter()
        try:
            raw, receipt = endpoint.generate(request, f"final-{index:02d}",
                                             max_output_tokens=config.max_output_tokens)
            receipts.append(receipt)
            return _bound_document(prepared, StructuredDocument.model_validate_json(raw))
        finally:
            final_generation_seconds += time.perf_counter() - before

    def take_receipt() -> WriterReceipt | None:
        return receipts.pop(0) if receipts else None

    def check(document: StructuredDocument) -> tuple[CheckFinding, ...]:
        nonlocal check_seconds
        before = time.perf_counter()
        try:
            return cast(tuple[CheckFinding, ...],
                        check_structured_document(document, projection, prepared))
        finally:
            check_seconds += time.perf_counter() - before

    outcome = run_attempts(config, Measurer(), request_for=request_for,
                           invoke=invoke,
                           check=check,
                           take_receipt=take_receipt)
    selected = outcome.selected_attempt
    resolution_started = time.perf_counter()
    resolved = None
    if selected is not None:
        attempt = outcome.attempts[selected]
        assert attempt.document is not None
        resolved = resolve_structured_document(attempt.document, prepared,
                                               evidence, attempt.findings)
    resolution_seconds = time.perf_counter() - resolution_started
    wall_seconds = time.perf_counter() - started
    for index, attempt in enumerate(outcome.attempts, 1):
        write_json(directory / f"attempt-{index:02d}.json", {
            "phase": attempt.phase, "outcome": attempt.outcome,
            "document": None if attempt.document is None else attempt.document.model_dump(mode="json"),
            "findings": [f.model_dump(mode="json") for f in attempt.findings],
            "error": attempt.error, "failure_subtype": attempt.failure_subtype,
            "writer_called": attempt.writer_called,
            "input_token_receipt": None if attempt.input_token_receipt is None else
                attempt.input_token_receipt.model_dump(mode="json"),
            "prompt_digest": attempt.prompt_digest,
            "writer_receipt": None if attempt.writer_receipt is None else
                attempt.writer_receipt.model_dump(mode="json")})
    if resolved is not None:
        write_json(directory / "resolved.json", resolved.model_dump(mode="json"))
        (directory / "answer-preview.md").write_text(_preview(resolved))
    summary = {"case": case, "variant": variant, "effort": effort,
        "candidate_version": candidate_version if variant != "original" else None,
        "worker_effort": worker_effort if workers is not None else None,
        "preparation_seconds": preparation_seconds,
        "worker_wall_seconds": worker_wall_seconds,
        "final_count_seconds": final_count_seconds,
        "final_generation_seconds": final_generation_seconds,
        "check_seconds": check_seconds,
        "resolution_seconds": resolution_seconds,
        "results_completion_seconds": wall_seconds,
        "timing_scope": "Saved projection to checked/resolved Results; includes worker and "
                        "bounded correction, excludes upstream intent/search/provider, "
                        "persistence/report I/O after resolution.",
        "attempts": len(outcome.attempts), "selected_attempt": selected,
        "selection_reason": outcome.selection_reason,
        "generation_outcome": outcome.generation_outcome,
        "validation_outcome": ("unavailable" if selected is None else
            "annotated" if any(f.outcome == "failed" for f in outcome.attempts[selected].findings)
            else "clean"),
        "failed_findings": ([] if selected is None else
            [f.model_dump(mode="json") for f in outcome.attempts[selected].findings
             if f.outcome == "failed"]),
        "selected_journey_ids": [] if resolved is None else list(resolved.selected_journey_ids),
        "source_sha256": sha256(source_path),
        "prepared_digest": prepared.authoring_view.binding_digest,
        "eligible_journeys": len(evidence.journeys),
        "input_counts": [a.input_token_receipt.input_tokens for a in outcome.attempts
                         if a.input_token_receipt is not None],
    }
    write_json(directory / "summary.json", summary)
    if sha256(source_path) != json.loads((directory / "settings.json").read_text())["source_sha256"]:
        raise ValueError("saved source changed during the run")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--variant", choices=("original", "candidate", "parallel"), required=True)
    parser.add_argument("--effort", choices=("medium", "low"), required=True)
    parser.add_argument("--worker-effort", choices=("medium", "low"), default="low")
    parser.add_argument("--candidate-version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--name", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    summary = run(args.case, args.variant, args.effort, args.name,
                  live=args.live, worker_effort=args.worker_effort,
                  candidate_version=args.candidate_version)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
