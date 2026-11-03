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
from award_agent.results.category import category_profiles
from award_agent.results.contracts import (
    CheckFinding,
    PreparedResultsInput,
    ResultsArtifact,
    ResultsConfig,
    ResultsDocument,
)
from award_agent.results.core import prepare_results, replay_results, run_results
from award_agent.results.default import DEFAULT_RESULTS_PROFILE, run_default_results
from award_agent.results.focused_comparison_contracts import FocusedResultsArtifactV11
from award_agent.results.focused_contracts import (
    FocusedResultsArtifact,
    FocusedResultsArtifactV9,
    FocusedResultsArtifactV10,
)
from award_agent.results.focused_patch_contracts import FocusedResultsArtifactV12


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
        command.add_argument("--legacy", action="store_true",
                             help="Use the original Results channel for live authoring or measurement.")
        command.add_argument("--interactive", action="store_true",
                             help=f"Use an interactive Results profile; defaults to {DEFAULT_RESULTS_PROFILE}.")
        command.add_argument("--reasoning-effort", choices=("none", "low", "medium"))
        command.add_argument("--service-tier", choices=("standard", "fast"))
        command.add_argument("--packet-profile", choices=("indexed-v1", "joined-v2", "joined-v3",
                                                        "joined-v4", "focused-v1", "focused-v2",
                                                        "focused-v3", "focused-v4", "focused-v5",
                                                        "focused-v6", "focused-v7", "focused-v8",
                                                        "focused-v9", "focused-v10", "focused-v11",
                                                        "focused-v12", "focused-v13", "focused-v14",
                                                        "focused-v15", "focused-v16", "focused-v17",
                                                        "focused-v18", "focused-v19", "focused-v20", "focused-v21", "focused-v22", "focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28", "focused-v29", "focused-v30"))
        command.add_argument("--category-profile", choices=category_profiles(),
                             help="Use an explicit category-led Results experiment.")
        if name == "author":
            mode = command.add_mutually_exclusive_group(required=True)
            mode.add_argument("--draft", type=Path, help="Offline frozen initial ResultsDocument.")
            mode.add_argument("--live", action="store_true", help="Make bounded writer API calls.")
            command.add_argument("--correction", type=Path,
                                 help="Offline corrected ResultsDocument; requires --draft.")
    replay = commands.add_parser("replay")
    replay.add_argument("--artifact", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command != "replay" and args.legacy and (
            args.structured or args.interactive or args.reasoning_effort is not None or
            args.service_tier is not None or args.packet_profile is not None or
            args.category_profile is not None):
        parser.error("--legacy cannot be combined with another Results channel or profile")
    if args.command != "replay" and args.category_profile is not None and (
            args.structured or args.interactive or args.reasoning_effort is not None or
            args.service_tier is not None or args.packet_profile is not None):
        parser.error("--category-profile owns the Results channel and model settings")
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
        if json.loads(raw).get("contract_version") == "results-category-artifact-v1":
            from award_agent.results.category import (
                parse_category_artifact,
                replay_category_results,
            )

            category_artifact = parse_category_artifact(raw)
            category_answer = replay_category_results(category_artifact)
            rendered = ("null" if category_answer is None else
                        category_answer.model_dump_json(indent=2))
            summary = {"delivery_outcome": category_artifact.delivery_outcome,
                       "resolved_digest": category_artifact.resolved_digest}
        elif json.loads(raw).get("contract_version") in {
                "results-artifact-v8", "results-artifact-v9", "results-artifact-v10",
                "results-artifact-v11", "results-artifact-v12"}:
            from award_agent.results.focused import parse_focused_artifact, replay_focused_results

            focused_artifact = parse_focused_artifact(raw)
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
    elif args.category_profile is not None:
        from award_agent.results.category import measure_category_results, run_category_results

        projection = SolutionProjection.model_validate_json(read(args.projection))
        config = ResultsConfig.model_validate_json(read(args.config))
        if args.command == "measure":
            summary = measure_category_results(projection, config,
                                               profile=args.category_profile)
            rendered = json.dumps(summary, indent=2)
        else:
            if not args.live or args.correction:
                parser.error("category author requires --live and no --correction")
            from openai import OpenAI

            from award_agent.results.interactive_adapter import OpenAIInteractiveResultsWriter

            client = OpenAI(max_retries=0, timeout=config.timeout_seconds)
            try:
                category_run = run_category_results(projection, config,
                    OpenAIInteractiveResultsWriter(client),
                    input_measurer=OpenAIResultsInputMeasurer(client),
                    profile=args.category_profile)
            finally:
                client.close()
            rendered = category_run.model_dump_json(indent=2)
            summary = {"generation_outcome": category_run.generation_outcome,
                       "validation_outcome": category_run.validation_outcome,
                       "delivery_outcome": category_run.delivery_outcome,
                       "passes": len(category_run.passes),
                       "runtime_seconds": category_run.runtime_seconds,
                       "profile": category_run.profile}
    elif args.interactive or (not args.legacy and not args.structured and
                              (args.command == "measure" or args.live)):
        default_profile = args.packet_profile is None
        if args.packet_profile is None:
            args.packet_profile = DEFAULT_RESULTS_PROFILE
        if args.packet_profile in {"focused-v1", "focused-v2", "focused-v3",
                                   "focused-v4", "focused-v5", "focused-v6", "focused-v7",
                                   "focused-v8", "focused-v9", "focused-v10", "focused-v11",
                                   "focused-v12", "focused-v13", "focused-v14", "focused-v15", "focused-v16", "focused-v17", "focused-v18", "focused-v19", "focused-v20", "focused-v21", "focused-v22", "focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28", "focused-v29", "focused-v30"}:
            from award_agent.results.focused import prepare_focused_selector, run_focused_results
            from award_agent.results.interactive_adapter import OpenAIInteractiveResultsWriter

            if args.structured or args.reasoning_effort is not None or args.service_tier is not None:
                parser.error("focused Results owns reasoning and service tier; use --interactive only")
            selection_format: Literal["roles-v1", "roles-v2", "roles-v3", "roles-v4",
                                      "roles-v5", "roles-v6", "roles-v7", "roles-v8",
                                      "roles-v9", "roles-v10", "roles-v11", "roles-v12",
                                      "roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"] = (
                "roles-v30" if args.packet_profile == "focused-v30" else
                "roles-v29" if args.packet_profile == "focused-v29" else
                "roles-v27" if args.packet_profile == "focused-v28" else
                "roles-v25" if args.packet_profile == "focused-v27" else
                "roles-v24" if args.packet_profile == "focused-v26" else
                "roles-v23" if args.packet_profile == "focused-v25" else
                "roles-v22" if args.packet_profile == "focused-v24" else
                "roles-v21" if args.packet_profile in {"focused-v22", "focused-v23"} else
                "roles-v20" if args.packet_profile == "focused-v21" else
                "roles-v19" if args.packet_profile == "focused-v20" else
                "roles-v18" if args.packet_profile == "focused-v19" else
                "roles-v17" if args.packet_profile == "focused-v18" else
                "roles-v16" if args.packet_profile == "focused-v17" else
                "roles-v15" if args.packet_profile == "focused-v16" else
                "roles-v14" if args.packet_profile == "focused-v15" else
                "roles-v13" if args.packet_profile == "focused-v14" else
                "roles-v12" if args.packet_profile == "focused-v13" else
                "roles-v11" if args.packet_profile == "focused-v12" else
                "roles-v10" if args.packet_profile == "focused-v11" else
                "roles-v9" if args.packet_profile == "focused-v10" else
                "roles-v8" if args.packet_profile == "focused-v9" else
                "roles-v7" if args.packet_profile == "focused-v8" else
                "roles-v6" if args.packet_profile == "focused-v7" else
                "roles-v5" if args.packet_profile == "focused-v6" else
                "roles-v4" if args.packet_profile == "focused-v5" else
                "roles-v3" if args.packet_profile == "focused-v4" else
                "roles-v2" if args.packet_profile in {"focused-v2", "focused-v3"} else
                "roles-v1")
            projection = SolutionProjection.model_validate_json(read(args.projection))
            config = ResultsConfig.model_validate_json(read(args.config))
            if args.packet_profile == "focused-v28" and any(
                    item.status in {"admitted", "conditional"} for item in projection.view.alternatives):
                selection_format = "roles-v26"
            if args.packet_profile == "focused-v29" and any(
                    item.status in {"admitted", "conditional"} for item in projection.view.alternatives):
                selection_format = "roles-v28"
            if args.packet_profile == "focused-v30" and any(
                    item.status in {"admitted", "conditional"} for item in projection.view.alternatives):
                selection_format = "roles-v28"
            if args.packet_profile in {"focused-v24", "focused-v25", "focused-v26", "focused-v27"} and any(
                    item.status in {"admitted", "conditional"} for item in projection.view.alternatives):
                selection_format = "roles-v21"
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
                focused_run: (FocusedResultsArtifact | FocusedResultsArtifactV9 |
                              FocusedResultsArtifactV10 | FocusedResultsArtifactV11 |
                              FocusedResultsArtifactV12)
                if default_profile:
                    focused_run = run_default_results(projection, config)
                elif args.packet_profile in {"focused-v4", "focused-v5", "focused-v6",
                                           "focused-v7", "focused-v8", "focused-v9",
                                           "focused-v10", "focused-v11", "focused-v12",
                                           "focused-v13", "focused-v14", "focused-v15", "focused-v16",
                                           "focused-v17", "focused-v18", "focused-v19", "focused-v20", "focused-v21", "focused-v22", "focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28", "focused-v29", "focused-v30"}:
                    focused_run = run_focused_results(projection, config,
                        OpenAIInteractiveResultsWriter(), input_measurer=OpenAIResultsInputMeasurer(),
                        profile="focused-v30" if args.packet_profile == "focused-v30" else
                        "focused-v29" if args.packet_profile == "focused-v29" else
                        "focused-v28" if args.packet_profile == "focused-v28" else
                        "focused-v27" if args.packet_profile == "focused-v27" else
                        "focused-v26" if args.packet_profile == "focused-v26" else
                        "focused-v25" if args.packet_profile == "focused-v25" else
                        "focused-v24" if args.packet_profile == "focused-v24" else
                        "focused-v23" if args.packet_profile == "focused-v23" else
                        "focused-v22" if args.packet_profile == "focused-v22" else
                        "focused-v21" if args.packet_profile == "focused-v21" else
                        "focused-v20" if args.packet_profile == "focused-v20" else
                        "focused-v19" if args.packet_profile == "focused-v19" else
                        "focused-v18" if args.packet_profile == "focused-v18" else
                        "focused-v17" if args.packet_profile == "focused-v17" else
                        "focused-v16" if args.packet_profile == "focused-v16" else
                        "focused-v15" if args.packet_profile == "focused-v15" else
                        "focused-v14" if args.packet_profile == "focused-v14" else
                        "focused-v13" if args.packet_profile == "focused-v13" else
                        "focused-v12" if args.packet_profile == "focused-v12" else
                        "focused-v11" if args.packet_profile == "focused-v11" else
                        "focused-v10" if args.packet_profile == "focused-v10" else
                        "focused-v9" if args.packet_profile == "focused-v9" else
                        "focused-v8" if args.packet_profile == "focused-v8" else
                        "focused-v7" if args.packet_profile == "focused-v7" else
                        "focused-v6" if args.packet_profile == "focused-v6" else
                        "focused-v5" if args.packet_profile == "focused-v5"
                        else "focused-v4")
                else:
                    legacy_selection_format: Literal["roles-v1", "roles-v2"] = (
                        "roles-v2" if args.packet_profile in {"focused-v2", "focused-v3"}
                        else "roles-v1")
                    focused_run = run_focused_results(projection, config,
                        OpenAIInteractiveResultsWriter(), input_measurer=OpenAIResultsInputMeasurer(),
                        selection_format=legacy_selection_format,
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
