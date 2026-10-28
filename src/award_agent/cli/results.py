"""Measure, author, or replay a local Results M2 artifact."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from award_agent.cli._atomic_output import write_new_atomic
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.adapter import OpenAIResultsInputMeasurer, OpenAIResultsWriter
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


def _structured_output(args: argparse.Namespace,
                       read: Callable[[Path], bytes]) -> tuple[str, dict[str, object]]:
    from award_agent.results.structured import (
        prepare_structured_results,
        run_structured_results,
    )
    from award_agent.results.structured_contracts import StructuredDocument, StructuredPreparedInput

    projection = SolutionProjection.model_validate_json(read(args.projection))
    config = ResultsConfig.model_validate_json(read(args.config))
    if args.command == "measure":
        prepared = prepare_structured_results(projection, config)
        summary: dict[str, object] = {
            "prepared_version": prepared.contract_version,
            "source_digest": prepared.source_digest,
            "alternatives": len(projection.view.alternatives),
            "eligible_alternatives": projection.receipt.eligible_alternatives,
            "input_bytes": prepared.input_bytes,
            "estimated_input_tokens": prepared.estimated_input_tokens,
            "max_output_tokens": config.max_output_tokens,
            "estimated_total_tokens": prepared.estimated_total_tokens,
            "context_limit_tokens": config.context_limit_tokens,
            "token_measurement": "conservative_utf8_upper_bound",
            "within_conservative_bound": prepared.estimated_total_tokens <= config.context_limit_tokens,
            "qualification": "Input measurement only; no model context-fit qualification.",
        }
        return json.dumps(summary, indent=2), summary
    if args.correction and not args.draft:
        raise ValueError("--correction requires --draft")
    if args.live:
        from award_agent.results.adapter import OpenAIStructuredResultsWriter

        artifact = run_structured_results(projection, config, OpenAIStructuredResultsWriter(),
                                          input_measurer=OpenAIResultsInputMeasurer())
    else:
        initial = StructuredDocument.model_validate_json(read(args.draft))
        correction = (StructuredDocument.model_validate_json(read(args.correction))
                      if args.correction else None)

        class FrozenStructuredWriter:
            def author(self, prepared: StructuredPreparedInput, config: ResultsConfig,
                       feedback: tuple[CheckFinding, ...] = (),
                       previous_document: StructuredDocument | None = None) -> StructuredDocument:
                return (correction or initial) if previous_document is not None else initial

        artifact = run_structured_results(projection, config, FrozenStructuredWriter())
    return artifact.model_dump_json(indent=2), {
        "generation_outcome": artifact.generation_outcome,
        "validation_outcome": artifact.validation_outcome,
        "delivery_outcome": artifact.delivery_outcome,
        "attempts": len(artifact.attempts),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("measure", "author"):
        command = commands.add_parser(name)
        command.add_argument("--projection", type=Path, required=True)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--structured", action="store_true",
                             help="Use the versioned structured Results channel.")
        command.add_argument("--interactive", action="store_true",
                             help="Use the explicit interactive Results channel.")
        command.add_argument("--reasoning-effort", choices=("none", "low", "medium"))
        command.add_argument("--service-tier", choices=("standard", "fast"))
        command.add_argument("--packet-profile", choices=("indexed-v1", "joined-v2", "joined-v3",
                                                        "joined-v4", "focused-v1", "focused-v2",
                                                        "focused-v3"))
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
    if args.command != "replay" and not args.interactive and (
            args.reasoning_effort is not None or args.service_tier is not None or
            args.packet_profile is not None):
        parser.error("interactive settings require --interactive")
    if args.output.exists() or args.output.is_symlink():
        parser.error("output path must be new; existing evidence is immutable")

    inputs: dict[Path, bytes] = {}

    def read(path: Path) -> bytes:
        content = path.read_bytes()
        inputs[path] = content
        return content

    summary: dict[str, object]
    if args.command == "replay":
        raw = read(args.artifact)
        if json.loads(raw).get("contract_version") == "results-artifact-v8":
            from award_agent.results.focused import replay_focused_results
            from award_agent.results.focused_contracts import FocusedResultsArtifact

            focused_artifact = FocusedResultsArtifact.model_validate_json(raw)
            answer = replay_focused_results(focused_artifact)
            rendered = "null" if answer is None else answer.model_dump_json(indent=2)
            summary = {"delivery_outcome": focused_artifact.delivery_outcome,
                       "resolved_digest": focused_artifact.resolved_digest}
        elif json.loads(raw).get("contract_version") == "results-artifact-v7":
            from award_agent.results.interactive import replay_interactive_results
            from award_agent.results.interactive_contracts import InteractiveResultsArtifact

            interactive_artifact = InteractiveResultsArtifact.model_validate_json(raw)
            answer = replay_interactive_results(interactive_artifact)
            rendered = "null" if answer is None else answer.model_dump_json(indent=2)
            summary = {"delivery_outcome": interactive_artifact.delivery_outcome,
                       "resolved_digest": interactive_artifact.resolved_digest}
        elif json.loads(raw).get("contract_version") == "results-artifact-v6":
            from award_agent.results.structured import replay_structured_results
            from award_agent.results.structured_contracts import StructuredResultsArtifact

            structured_artifact = StructuredResultsArtifact.model_validate_json(raw)
            answer = replay_structured_results(structured_artifact)
            rendered = "null" if answer is None else answer.model_dump_json(indent=2)
            summary = {"delivery_outcome": structured_artifact.delivery_outcome,
                                          "resolved_digest": structured_artifact.resolved_digest}
        else:
            artifact = ResultsArtifact.model_validate_json(raw)
            rendered = replay_results(artifact)
            summary = {"delivery_outcome": artifact.delivery_outcome,
                       "rendered_digest": artifact.rendered_digest}
    elif args.interactive:
        if args.packet_profile in {"focused-v1", "focused-v2", "focused-v3"}:
            from award_agent.results.focused import prepare_focused_selector, run_focused_results
            from award_agent.results.interactive_adapter import OpenAIInteractiveResultsWriter

            if args.structured or args.reasoning_effort is not None or args.service_tier is not None:
                parser.error("focused Results owns reasoning and service tier; use --interactive only")
            selection_format: Literal["roles-v1", "roles-v2"] = (
                "roles-v2" if args.packet_profile in {"focused-v2", "focused-v3"} else "roles-v1")
            projection = SolutionProjection.model_validate_json(read(args.projection))
            config = ResultsConfig.model_validate_json(read(args.config))
            if args.command == "measure":
                focused_prepared = prepare_focused_selector(projection, config,
                    selection_format=selection_format)
                summary = {"prepared_version": focused_prepared.contract_version,
                           "source_digest": focused_prepared.source_digest,
                           "packet_digest": focused_prepared.packet_digest,
                           "qualification": "Selector preparation only; no model context-fit qualification."}
                rendered = json.dumps(summary, indent=2)
            else:
                if not args.live or args.correction:
                    parser.error("focused author requires --live and no --correction")
                focused_run = run_focused_results(projection, config,
                    OpenAIInteractiveResultsWriter(), input_measurer=OpenAIResultsInputMeasurer(),
                    selection_format=selection_format,
                    composition_format="comparisons-v1" if args.packet_profile == "focused-v3"
                    else "source-v1")
                rendered = focused_run.model_dump_json(indent=2)
                summary = {"generation_outcome": focused_run.generation_outcome,
                           "validation_outcome": focused_run.validation_outcome,
                           "delivery_outcome": focused_run.delivery_outcome,
                           "passes": len(focused_run.passes),
                           "runtime_seconds": focused_run.runtime_seconds}
        else:
            rendered, summary = _interactive_output(args, read, parser)
    elif args.structured:
        rendered, summary = _structured_output(args, read)
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
                artifact = run_results(projection, config, writer,
                                       input_measurer=OpenAIResultsInputMeasurer())
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
    if args.command == "author" and summary["delivery_outcome"] != "delivered":
        return 1
    return 0


def _interactive_output(args: argparse.Namespace, read: Callable[[Path], bytes],
                        parser: argparse.ArgumentParser) -> tuple[str, dict[str, object]]:
    """Existing v7 route kept separate from the additive focused-v1 dispatch."""
    from award_agent.results.interactive import (
        prepare_interactive_results,
        run_interactive_results,
    )
    from award_agent.results.interactive_adapter import OpenAIInteractiveResultsWriter
    from award_agent.results.interactive_contracts import InteractiveSettings

    if args.structured:
        parser.error("--interactive and --structured are mutually exclusive")
    if args.reasoning_effort is None:
        parser.error("--interactive requires --reasoning-effort")
    projection = SolutionProjection.model_validate_json(read(args.projection))
    config = ResultsConfig.model_validate_json(read(args.config))
    settings = InteractiveSettings(reasoning_effort=args.reasoning_effort,
                                   service_tier=args.service_tier or "standard")
    if args.command == "measure":
        interactive_prepared = prepare_interactive_results(projection, config,
            packet_profile=args.packet_profile or "indexed-v1")
        summary: dict[str, object] = {"prepared_version": interactive_prepared.contract_version,
                   "source_digest": interactive_prepared.source_digest,
                   "packet_digest": interactive_prepared.packet_digest,
                   "qualification": "Preparation only; no model context-fit qualification."}
        rendered = json.dumps(summary, indent=2)
    else:
        if not args.live or args.correction:
            parser.error("interactive author requires --live and no --correction")
        interactive_run = run_interactive_results(projection, config, settings,
            OpenAIInteractiveResultsWriter(), input_measurer=OpenAIResultsInputMeasurer(),
            packet_profile=args.packet_profile or "indexed-v1")
        rendered = interactive_run.model_dump_json(indent=2)
        summary = {"generation_outcome": interactive_run.generation_outcome,
                   "validation_outcome": interactive_run.validation_outcome,
                   "delivery_outcome": interactive_run.delivery_outcome,
                   "attempts": len(interactive_run.attempts),
                   "runtime_seconds": interactive_run.runtime_seconds}
    return rendered, summary


if __name__ == "__main__":
    raise SystemExit(main())
