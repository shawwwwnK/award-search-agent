"""Measure, author, or replay a local Results M2 artifact."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from award_agent.cli._atomic_output import write_new_atomic
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.adapter import OpenAIResultsWriter
from award_agent.results.contracts import (
    CheckFinding,
    PreparedResultsInput,
    ResultsArtifact,
    ResultsConfig,
    ResultsDocument,
)
from award_agent.results.core import prepare_results, replay_results, run_results


class _FrozenWriter:
    def __init__(self, initial: ResultsDocument, correction: ResultsDocument | None) -> None:
        self.initial = initial
        self.correction = correction

    def author(self, prepared: PreparedResultsInput, config: ResultsConfig,
               feedback: tuple[CheckFinding, ...] = (),
               previous_document: ResultsDocument | None = None) -> ResultsDocument:
        return self.correction or self.initial if previous_document is not None else self.initial


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("measure", "author"):
        command = commands.add_parser(name)
        command.add_argument("--projection", type=Path, required=True)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name == "author":
            mode = command.add_mutually_exclusive_group(required=True)
            mode.add_argument("--draft", type=Path, help="Offline frozen initial ResultsDocument.")
            mode.add_argument("--live", action="store_true", help="Make up to two writer API calls.")
            command.add_argument("--correction", type=Path,
                                 help="Offline corrected ResultsDocument; requires --draft.")
    replay = commands.add_parser("replay")
    replay.add_argument("--artifact", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("output path must be new; existing evidence is immutable")

    inputs: dict[Path, bytes] = {}

    def read(path: Path) -> bytes:
        content = path.read_bytes()
        inputs[path] = content
        return content

    if args.command == "replay":
        artifact = ResultsArtifact.model_validate_json(read(args.artifact))
        rendered = replay_results(artifact)
        summary: dict[str, object] = {"delivery_outcome": artifact.delivery_outcome,
                                      "rendered_digest": artifact.rendered_digest}
    else:
        projection = SolutionProjection.model_validate_json(read(args.projection))
        config = ResultsConfig.model_validate_json(read(args.config))
        if args.command == "measure":
            prepared = prepare_results(projection, config)
            summary = {
                "source_digest": prepared.source_digest,
                "alternatives": len(projection.view.alternatives),
                "eligible_alternatives": projection.receipt.eligible_alternatives,
                "input_bytes": prepared.input_bytes,
                "estimated_input_tokens": prepared.estimated_input_tokens,
                "max_output_tokens": config.max_output_tokens,
                "estimated_total_tokens": prepared.estimated_total_tokens,
                "context_limit_tokens": config.context_limit_tokens,
                "token_measurement": "conservative_utf8_upper_bound",
                "within_conservative_bound": (
                    prepared.estimated_total_tokens <= config.context_limit_tokens),
                "qualification": "Input measurement only; no model context-fit qualification.",
            }
            rendered = json.dumps(summary, indent=2)
        else:
            if args.correction and not args.draft:
                parser.error("--correction requires --draft")
            if args.live:
                writer = OpenAIResultsWriter()
                artifact = run_results(projection, config, writer)
            else:
                initial = ResultsDocument.model_validate_json(read(args.draft))
                correction = (ResultsDocument.model_validate_json(read(args.correction))
                              if args.correction else None)
                artifact = run_results(projection, config, _FrozenWriter(initial, correction))
            rendered = artifact.model_dump_json(indent=2)
            summary = {"generation_outcome": artifact.generation_outcome,
                       "validation_outcome": artifact.validation_outcome,
                       "delivery_outcome": artifact.delivery_outcome,
                       "attempts": len(artifact.attempts)}
    if any(path.read_bytes() != content for path, content in inputs.items()):
        raise ValueError("Results input changed during processing")
    write_new_atomic(args.output, rendered, trailing_newline=args.command != "replay")
    print(json.dumps({"output": str(args.output), **summary}))
    if args.command == "author" and artifact.delivery_outcome != "delivered":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
