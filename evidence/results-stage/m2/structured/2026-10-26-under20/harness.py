"""Isolated, bounded lean-wire Results experiment on frozen saved projections."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import httpx
from decision_packet import build_packet
from dotenv import load_dotenv
from openai import APIError, OpenAI
from wire import INSTRUCTIONS, WIRE_SCHEMA, decode_wire

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
    check_structured_document,
    prepare_structured_results,
    resolve_structured_document,
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


def require_two_attempt_headroom(campaign: dict[str, Any]) -> None:
    """The runner may need an initial attempt and one bounded correction."""
    for kind, key in (("count", "maximum_input_count_calls"),
                      ("generation", "maximum_generation_calls")):
        limit = campaign[key]
        reserved = len(list((HERE / "calls").glob(f"{kind}-*.json")))
        if limit - reserved < 2:
            raise ValueError(f"campaign {kind} requires two-call headroom before run")


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
                 config: ResultsConfig, client: OpenAI, service_tier: str = "standard") -> None:
        self.directory, self.campaign, self.config, self.client = (
            directory, campaign, config, client)
        self.service_tier = service_tier
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
        if self.service_tier == "fast":
            full_request["service_tier"] = "fast"
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
                "usage": raw.get("usage"), "returned_reasoning": raw.get("reasoning"),
                "requested_service_tier": self.service_tier,
                "returned_service_tier": raw.get("service_tier")})
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


def _correction_context(prepared: StructuredPreparedInput,
                        feedback: tuple[CheckFinding, ...],
                        previous: StructuredDocument | None) -> tuple[list[dict[str, object]],
                                                                     dict[str, object] | None]:
    """Express all correction identities in the same aliases as the packet."""
    refs = prepared.references
    reverse: dict[str, str] = {}
    for aliases in (refs.journeys, refs.awards, refs.cash):
        for alias, canonical in aliases.items():
            if canonical in reverse and reverse[canonical] != alias:
                raise ValueError("source identity has multiple correction aliases")
            reverse[canonical] = alias

    def alias_for(canonical: str | None) -> str | None:
        if canonical is None:
            return None
        if canonical not in reverse:
            raise ValueError("correction references unknown source identity")
        return reverse[canonical]

    problems = [{"code": item.code, "scope": item.scope,
                 "r": alias_for(item.reference_id), "part_index": item.part_index,
                 "message": item.message} for item in feedback]
    if previous is None:
        return problems, None
    selected = set(previous.selection.journey_ids)
    blocks: list[dict[str, str]] = []
    for block in previous.blocks:
        if block.kind == "narrative":
            blocks.append({"k": "t", "v": block.text})
            continue
        canonical = block.reference_id
        if canonical is None:
            raise ValueError("prior reference lacks source identity")
        kind = ("p" if canonical in selected else "a") if block.reference_kind == "journey" \
            else "b" if block.reference_kind == "benchmark" else "l"
        alias = alias_for(canonical)
        assert alias is not None
        blocks.append({"k": kind, "r": alias, "n": block.label or "", "v": block.text})
    return problems, {"blocks": blocks}


def request_for_packet(packet: dict[str, object], config: ResultsConfig, effort: str,
                       prepared: StructuredPreparedInput,
                       feedback: tuple[CheckFinding, ...] = (),
                       previous: StructuredDocument | None = None) -> dict[str, object]:
    problems, prior = _correction_context(prepared, feedback, previous)
    body = {"packet": packet, "feedback": problems, "previous_wire": prior}
    return {"model": config.model, "reasoning": {"effort": effort},
            "instructions": INSTRUCTIONS,
            "input": json.dumps(body, ensure_ascii=False, separators=(",", ":")),
            "text": {"format": {"type": "json_schema", "name": "LeanResultsWire",
                                "strict": True, "schema": WIRE_SCHEMA}}}


def _preview(resolved: Any) -> str:
    rows = []
    for block in resolved.blocks:
        rows.append(block.text)
        if block.kind == "reference":
            rows.append(f"[Display: {block.label}; {block.reference_kind}; {block.canonical_id}]")
    return "\n\n".join(rows) + "\n"


def run(case: str, effort: str, name: str, *, live: bool,
        service_tier: str = "standard") -> dict[str, object]:
    if case not in CASES or effort not in {"none", "low", "medium"}:
        raise ValueError("unknown case or effort")
    if service_tier not in {"standard", "fast"}:
        raise ValueError("unknown service tier")
    if not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("name must contain only letters, digits, - or _")
    source_path = SOURCE / case / "artifact.json"
    config_path = SOURCE / case / "config.json"
    if not live:
        return {"case": case, "effort": effort, "service_tier": service_tier,
                "source_sha256": sha256(source_path),
                "mode": "offline", "live_calls": 0}
    campaign = json.loads(CAMPAIGN.read_text())
    if campaign["maximum_generation_calls"] != 48 or campaign["maximum_input_count_calls"] != 48:
        raise ValueError("campaign must declare exact 48/48 ceilings")
    require_two_attempt_headroom(campaign)
    directory = HERE / "runs" / name
    directory.mkdir(parents=True, exist_ok=False)
    runtime_files = sorted((REPO / "src/award_agent/results").glob("*.py"))
    snapshot_paths = [Path(__file__), HERE / "wire.py", HERE / "decision_packet.py",
                      CAMPAIGN, source_path, config_path, *runtime_files]
    write_json(directory / "settings.json", {"case": case, "effort": effort,
        "service_tier": service_tier,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "source_sha256": sha256(source_path), "config_sha256": sha256(config_path),
        "harness_sha256": sha256(Path(__file__)), "wire_sha256": sha256(HERE / "wire.py"),
        "packet_sha256": sha256(HERE / "decision_packet.py"), "max_output_tokens": 8192,
        "timeout_seconds": 240, "max_retries": 0})
    write_json(directory / "source-snapshot.json", {
        str(path.relative_to(REPO)): sha256(path) for path in snapshot_paths})
    with zipfile.ZipFile(directory / "source-snapshot.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in snapshot_paths:
            archive.write(path, str(path.relative_to(REPO)))
    started = time.perf_counter()
    try:
        source_artifact = StructuredResultsArtifact.model_validate_json(source_path.read_text())
        projection = source_artifact.evidence.source
        base = ResultsConfig.model_validate_json(config_path.read_text())
        config = base.model_copy(update={"model": "gpt-6-luna", "timeout_seconds": 240.0,
                                         "max_output_tokens": 8192})
        evidence = resolve_workspace(projection)
        prepared = prepare_structured_results(projection, config)
        packet = build_packet(prepared, projection, evidence)
        write_json(directory / "decision-packet.json", packet)
        preparation_seconds = time.perf_counter() - started
        load_dotenv(REPO / ".env")
        endpoint = Endpoint(directory, campaign, config, OpenAI(max_retries=0, timeout=240),
                            service_tier)
        requests: list[dict[str, object]] = []
        receipts: list[WriterReceipt] = []
        generation_index = 0
        count_seconds = generation_seconds = check_seconds = 0.0

        class Measurer:
            def measure(self, request: dict[str, object], _config: ResultsConfig) -> InputTokenReceipt:
                nonlocal count_seconds
                before = time.perf_counter()
                try:
                    return endpoint.count(request, f"final-{len(requests):02d}")
                finally:
                    count_seconds += time.perf_counter() - before

        def make_request(feedback: tuple[CheckFinding, ...],
                         previous: StructuredDocument | None) -> RequestEnvelope:
            request = request_for_packet(packet, config, effort, prepared, feedback, previous)
            requests.append(request)
            return _envelope(request, config)

        def invoke(_feedback: tuple[CheckFinding, ...],
                   _previous: StructuredDocument | None) -> StructuredDocument:
            nonlocal generation_seconds, generation_index
            generation_index += 1
            index = generation_index
            # A schema/protocol failure terminates run_attempts, so this index
            # stays bound to the counted request even if the wire cannot decode.
            request = requests[index - 1]
            before = time.perf_counter()
            try:
                raw, receipt = endpoint.generate(request, f"final-{index:02d}",
                                                 max_output_tokens=config.max_output_tokens)
                receipts.append(receipt)
                (directory / f"final-{index:02d}" / "output-text.json").write_text(
                    json.dumps(raw, ensure_ascii=False))
                return decode_wire(raw, prepared, projection)
            finally:
                generation_seconds += time.perf_counter() - before

        def take_receipt() -> WriterReceipt | None:
            return receipts.pop(0) if receipts else None

        def check(document: StructuredDocument) -> tuple[CheckFinding, ...]:
            nonlocal check_seconds
            before = time.perf_counter()
            try:
                return tuple(check_structured_document(document, projection, prepared))
            finally:
                check_seconds += time.perf_counter() - before

        outcome = run_attempts(config, Measurer(), request_for=make_request,
                               invoke=invoke, check=check, take_receipt=take_receipt)
        selected = outcome.selected_attempt
        resolution_started = time.perf_counter()
        resolved = None
        if selected is not None:
            attempt = outcome.attempts[selected]
            assert attempt.document is not None
            resolved = resolve_structured_document(attempt.document, prepared, evidence,
                                                   attempt.findings)
        resolution_seconds = time.perf_counter() - resolution_started
        wall_seconds = time.perf_counter() - started
        for index, attempt in enumerate(outcome.attempts, 1):
            write_json(directory / f"attempt-{index:02d}.json", {
                "phase": attempt.phase, "outcome": attempt.outcome,
                "document": attempt.document.model_dump(mode="json") if attempt.document else None,
                "findings": [f.model_dump(mode="json") for f in attempt.findings],
                "error": attempt.error, "failure_subtype": attempt.failure_subtype,
                "writer_called": attempt.writer_called,
                "input_token_receipt": attempt.input_token_receipt.model_dump(mode="json")
                    if attempt.input_token_receipt else None,
                "prompt_digest": attempt.prompt_digest, "schema_digest": attempt.schema_digest,
                "writer_receipt": attempt.writer_receipt.model_dump(mode="json")
                    if attempt.writer_receipt else None})
        if resolved is not None:
            write_json(directory / "resolved.json", resolved.model_dump(mode="json"))
            (directory / "answer-preview.md").write_text(_preview(resolved))
        summary = {"case": case, "effort": effort, "service_tier": service_tier,
            "returned_service_tiers": [json.loads(path.read_text()).get("returned_service_tier")
                for path in sorted(directory.glob("final-*/generation-timing.json"))],
            "preparation_seconds": preparation_seconds,
            "count_seconds": count_seconds, "generation_seconds": generation_seconds,
            "check_seconds": check_seconds, "resolution_seconds": resolution_seconds,
            "results_completion_seconds": wall_seconds,
            "timing_scope": "Saved artifact parse through checked and resolved Results; excludes canonical end replay and upstream workflow.",
            "attempts": len(outcome.attempts), "selected_attempt": selected,
            "selection_reason": outcome.selection_reason,
            "generation_outcome": outcome.generation_outcome,
            "validation_outcome": "unavailable" if selected is None else
                "annotated" if any(f.outcome == "failed" for f in outcome.attempts[selected].findings) else "clean",
            "failed_findings": [] if selected is None else
                [f.model_dump(mode="json") for f in outcome.attempts[selected].findings if f.outcome == "failed"],
            "selected_journey_ids": [] if resolved is None else list(resolved.selected_journey_ids),
            "source_sha256": sha256(source_path), "packet_digest": content_digest(packet),
            "input_counts": [a.input_token_receipt.input_tokens for a in outcome.attempts
                             if a.input_token_receipt is not None]}
        write_json(directory / "summary.json", summary)
        if sha256(source_path) != json.loads((directory / "settings.json").read_text())["source_sha256"]:
            raise ValueError("saved source changed during run")
        return summary
    except Exception as exc:
        write_json(directory / "run-error.json", {"type": type(exc).__name__,
            "elapsed_seconds": time.perf_counter() - started})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--effort", choices=("none", "low", "medium"), required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--service-tier", choices=("standard", "fast"), default="standard")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.effort, args.name, live=args.live,
                         service_tier=args.service_tier), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


