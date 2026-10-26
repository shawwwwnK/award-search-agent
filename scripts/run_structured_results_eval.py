"""Bounded Results V6 diagnostic on saved evidence; offline unless --live is explicit."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Literal

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.adapter import OpenAIResultsInputMeasurer, OpenAIStructuredResultsWriter
from award_agent.results.contracts import (
    CheckFinding,
    InputTokenReceipt,
    ResultsConfig,
    WriterReceipt,
)
from award_agent.results.structured import (
    prepare_structured_results,
    replay_structured_results,
    run_structured_results,
)
from award_agent.results.structured_contracts import StructuredDocument, StructuredPreparedInput

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "evidence/results-stage/m2/structured/2026-10-24-luna"
SOURCE = REPO / "evidence/results-stage/m2/compact-input/2026-10-20-luna"
CASES = ("admitted", "conditional", "incomplete")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def reserve_call(root: Path, kind: Literal["count", "generation"], limit: int,
                 case: str, round_number: int) -> None:
    """Persist an attempted call before invoking a paid endpoint; never overwrite."""
    calls = root / "calls"
    calls.mkdir(parents=True, exist_ok=True)
    for index in range(1, limit + 1):
        path = calls / f"{kind}-{index:03d}.json"
        try:
            write_json(path, {"kind": kind, "case": case, "round": round_number,
                              "status": "reserved_before_invocation"})
        except FileExistsError:
            continue
        return
    raise ValueError(f"campaign {kind} limit reached ({limit}); no call made")


class RecordingMeasurer:
    def __init__(self, delegate: OpenAIResultsInputMeasurer, directory: Path,
                 case: str, round_number: int, limit: int, root: Path | None = None) -> None:
        self.delegate, self.directory = delegate, directory
        self.case, self.round_number, self.limit = case, round_number, limit
        self.root = ROOT if root is None else root
        self.calls = 0

    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
        self.calls += 1
        if self.calls > 2:
            raise ValueError("per-run count limit reached")
        write_json(self.directory / f"{self.calls:02d}-request.json", request)
        reserve_call(self.root, "count", self.limit, self.case, self.round_number)
        receipt = self.delegate.measure(request, config)
        write_json(self.directory / f"{self.calls:02d}-count.json", receipt.model_dump(mode="json"))
        return receipt


class RecordingWriter:
    def __init__(self, delegate: OpenAIStructuredResultsWriter, directory: Path,
                 case: str, round_number: int, limit: int, root: Path | None = None) -> None:
        self.delegate, self.directory = delegate, directory
        self.case, self.round_number, self.limit = case, round_number, limit
        self.root = ROOT if root is None else root
        self.calls = 0

    def author(self, prepared: StructuredPreparedInput, config: ResultsConfig,
               feedback: tuple[CheckFinding, ...] = (),
               previous_document: StructuredDocument | None = None) -> StructuredDocument:
        self.calls += 1
        if self.calls > 2:
            raise ValueError("per-run generation limit reached")
        reserve_call(self.root, "generation", self.limit, self.case, self.round_number)
        return self.delegate.author(prepared, config, feedback, previous_document)

    def take_receipt(self) -> WriterReceipt | None:
        receipt = self.delegate.take_receipt()
        if receipt is not None:
            write_json(self.directory / f"{self.calls:02d}-writer.json",
                       receipt.model_dump(mode="json"))
        return receipt


def run_case(case: str, round_number: int, *, live: bool,
             campaign_root: Path | None = None) -> dict[str, object]:
    root = ROOT if campaign_root is None else campaign_root
    campaign = json.loads((root / "campaign.json").read_text())
    settings = dict(campaign["settings"])
    guidance = campaign.get("round_guidance", {}).get(str(round_number))
    if guidance is not None:
        settings["authoring_guidance"] = guidance
    config = ResultsConfig.model_validate(settings)
    if not 1 <= round_number <= campaign["maximum_targeted_rounds"]:
        raise ValueError("round outside declared campaign")
    source_path = SOURCE / case / "artifact.json"
    source_bytes = source_path.read_bytes()
    projection = SolutionProjection.model_validate(json.loads(source_bytes)["projection"])
    prepared = prepare_structured_results(projection, config)
    summary: dict[str, object] = {
        "case": case, "round": round_number, "mode": "live" if live else "offline",
        "source_path": str(source_path.relative_to(REPO)),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_digest": prepared.source_digest,
        "eligible_candidates": projection.receipt.eligible_alternatives,
        "input_bytes": prepared.input_bytes,
        "estimated_total_tokens": prepared.estimated_total_tokens,
    }
    if not live:
        return summary

    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    directory = root / f"round-{round_number}" / case
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "config.json", config.model_dump(mode="json"))
    files = sorted((REPO / "src/award_agent/results").glob("*.py")) + [Path(__file__)]
    write_json(directory / "source-snapshot.json", {
        str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files})
    with zipfile.ZipFile(directory / "source-snapshot.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, str(path.relative_to(REPO)))
    write_json(directory / "source-receipt.json", summary)
    measurer = RecordingMeasurer(OpenAIResultsInputMeasurer(), directory, case, round_number,
                                 campaign["maximum_input_count_calls"], root)
    writer = RecordingWriter(OpenAIStructuredResultsWriter(), directory, case, round_number,
                             campaign["maximum_generation_calls"], root)
    artifact = run_structured_results(projection, config, writer, input_measurer=measurer)
    write_json(directory / "artifact.json", artifact.model_dump(mode="json"))
    resolved = replay_structured_results(artifact)
    write_json(directory / "resolved.json", None if resolved is None else resolved.model_dump(mode="json"))
    if source_bytes != source_path.read_bytes():
        raise ValueError("source changed during diagnostic")
    summary.update({
        "generation_calls": writer.calls, "input_count_calls": measurer.calls,
        "generation_outcome": artifact.generation_outcome,
        "validation_outcome": artifact.validation_outcome,
        "delivery_outcome": artifact.delivery_outcome,
        "selected_attempt": artifact.selected_attempt,
        "resolved_digest": artifact.resolved_digest,
        "workspace_candidates": len(artifact.evidence.journeys),
        "writer_input_tokens": sum(a.writer_receipt.usage.get("input_tokens", 0)
                                   for a in artifact.attempts if a.writer_receipt is not None),
        "writer_output_tokens": sum(a.writer_receipt.usage.get("output_tokens", 0)
                                    for a in artifact.attempts if a.writer_receipt is not None),
        "failed_findings": [] if resolved is None else [f.model_dump(mode="json")
            for f in resolved.findings if f.outcome == "failed"],
    })
    write_json(directory / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--campaign-root", type=Path, default=None)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    summary = run_case(args.case, args.round, live=args.live,
                       campaign_root=args.campaign_root)
    print(json.dumps(summary, indent=2), flush=True)
    return int(args.live and summary.get("delivery_outcome") != "delivered")


if __name__ == "__main__":
    raise SystemExit(main())
