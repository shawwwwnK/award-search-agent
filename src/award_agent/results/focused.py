"""Two bounded Luna calls: source-wide choice followed by focused authored Results."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Literal, cast

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection

from .authoring import verify_authoring_view
from .contracts import (
    CheckFinding,
    InputTokenReceipt,
    ResultsConfig,
    ResultsInputMeasurer,
    ResultsWriterError,
    WriterReceipt,
)
from .core import prepare_results
from .currency import FxAcquisition
from .focused_comparison_contracts import FocusedResultsArtifactV11, ResolvedFocusedComparisonAnswer
from .focused_contracts import (
    FocusedPass,
    FocusedResultsArtifact,
    FocusedResultsArtifactV9,
    FocusedResultsArtifactV10,
)
from .focused_details import build_selected_details, build_selector_details
from .focused_packet import (
    build_packet as build_focus_packet,
)
from .focused_packet import (
    decode_selection,
    decode_selection_v2,
    selection_instructions,
    selection_instructions_v2,
    selection_instructions_v3,
    selection_instructions_v4,
    selection_instructions_v5,
    selection_instructions_v8,
    selection_schema,
    selection_schema_v2,
)
from .focused_patch_contracts import FocusedResultsArtifactV12
from .focused_selection_plan import instructions as planned_selection_instructions
from .focused_selection_plan import instructions_v15 as planned_selection_instructions_v15
from .focused_selection_plan import instructions_v16 as planned_selection_instructions_v16
from .focused_selection_plan import instructions_v20 as planned_selection_instructions_v20
from .focused_selection_plan import instructions_v21 as planned_selection_instructions_v21
from .focused_selection_plan import instructions_v22 as planned_selection_instructions_v22
from .focused_selection_plan import instructions_v26 as planned_selection_instructions_v26
from .focused_selection_plan import instructions_v27 as planned_selection_instructions_v27
from .focused_selection_plan import instructions_v29 as planned_selection_instructions_v29
from .focused_selection_plan import instructions_v30 as planned_selection_instructions_v30
from .focused_selection_plan import schema as planned_selection_schema
from .focused_selector_records import selector_packet
from .focused_wire import alias_for_canonical as focused_alias_for_canonical
from .focused_wire import decode as decode_focused_wire
from .focused_wire import instructions as focused_instructions
from .focused_wire import revision_instructions as focused_revision_instructions
from .focused_wire import schema as focused_schema
from .interactive import _response_text, _returned_tier, _validate_recoverable_response
from .interactive_contracts import InteractivePreparedInput, InteractiveSettings, InteractiveWriter
from .interactive_packet import build_packet as build_indexed_packet
from .presentation import resolve_workspace
from .runner import RequestEnvelope
from .structured import (
    check_structured_document,
    prepare_structured_results,
    resolve_structured_document,
)
from .structured_contracts import (
    ResolvedStructuredAnswer,
    StructuredDocument,
    StructuredPreparedInput,
    StructuredSelection,
)
from .workspace_contracts import WorkspaceEvidence

SELECTOR_SETTINGS = InteractiveSettings(reasoning_effort="none", service_tier="fast")
COMPOSER_SETTINGS = InteractiveSettings(reasoning_effort="low", service_tier="fast")


def _prepared(packet: dict[str, object], structured: StructuredPreparedInput) -> InteractivePreparedInput:
    frozen = json.loads(json.dumps(packet, ensure_ascii=False))
    return InteractivePreparedInput(structured=structured, packet=frozen,
        packet_digest=content_digest(frozen), source_digest=structured.source_digest)


def prepare_focused_selector(projection: SolutionProjection, config: ResultsConfig,
                             evidence: WorkspaceEvidence | None = None, *,
                             selection_format: Literal["roles-v1", "roles-v2", "roles-v3", "roles-v4", "roles-v5", "roles-v6", "roles-v7", "roles-v8", "roles-v9", "roles-v10", "roles-v11", "roles-v12", "roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"] = "roles-v1",
                             ) -> InteractivePreparedInput:
    trusted = SolutionProjection.model_validate(projection.model_dump(mode="json"))
    workspace = evidence or resolve_workspace(trusted)
    structured = prepare_structured_results(trusted, config)
    packet = build_indexed_packet(structured, trusted, workspace)
    if selection_format in {"roles-v2", "roles-v3", "roles-v4", "roles-v5", "roles-v6", "roles-v7", "roles-v8", "roles-v9", "roles-v10", "roles-v11", "roles-v12", "roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        packet["selection_format"] = selection_format
    elif selection_format != "roles-v1":
        raise ValueError("unknown focused selection format")
    if selection_format in {"roles-v8", "roles-v9", "roles-v10", "roles-v11", "roles-v12", "roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        packet["exact_details"] = build_selector_details(structured, workspace)
    return _prepared(packet, structured)


def prepare_focused_composer(selection: StructuredSelection,
                             selector: InteractivePreparedInput,
                             projection: SolutionProjection,
                             evidence: WorkspaceEvidence, *,
                             composition_format: Literal["source-v1", "comparisons-v1", "complete-v1", "complete-v2", "complete-v3", "complete-v4", "complete-v5", "complete-v6", "complete-v7", "complete-v8", "complete-v9", "complete-v10", "complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"] = "source-v1",
                             ) -> InteractivePreparedInput:
    packet = build_focus_packet(selection, selector.structured, projection, evidence,
        selection_format=_selector_format(selector), composition_format=composition_format)
    if packet.get("format") != "focused-v1":
        raise ValueError("focused packet builder returned an unexpected format")
    if composition_format in {"complete-v6", "complete-v7", "complete-v8", "complete-v9", "complete-v10", "complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}:
        expected = build_selector_details(selector.structured, evidence)
        if selector.packet.get("exact_details") != expected:
            raise ValueError("focused source detail index differs from selected source")
        packet["selected_details"] = build_selected_details(expected, packet)
    return _prepared(packet, selector.structured)


def _selector_format(prepared: InteractivePreparedInput) -> Literal["roles-v1", "roles-v2", "roles-v3", "roles-v4", "roles-v5", "roles-v6", "roles-v7", "roles-v8", "roles-v9", "roles-v10", "roles-v11", "roles-v12", "roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"]:
    value = prepared.packet.get("selection_format", "roles-v1")
    if value not in {"roles-v1", "roles-v2", "roles-v3", "roles-v4", "roles-v5", "roles-v6", "roles-v7", "roles-v8", "roles-v9", "roles-v10", "roles-v11", "roles-v12", "roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        raise ValueError("unknown focused selection format")
    return value


def _request(prepared: InteractivePreparedInput, config: ResultsConfig,
             settings: InteractiveSettings, phase: Literal["selection", "composition", "correction", "revision"],
             projection: SolutionProjection, *,
             feedback: tuple[CheckFinding, ...] = (), previous_wire: str | None = None,
             ) -> RequestEnvelope:
    if phase == "selection":
        if _selector_format(prepared) in {"roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
            instructions = (planned_selection_instructions_v30 if
                            _selector_format(prepared) == "roles-v30" else
                            planned_selection_instructions_v29 if
                            _selector_format(prepared) == "roles-v29" else
                            planned_selection_instructions_v27 if
                            _selector_format(prepared) == "roles-v27" else
                            planned_selection_instructions_v26 if
                            _selector_format(prepared) in {"roles-v26", "roles-v28"} else
                            planned_selection_instructions_v22 if
                            _selector_format(prepared) in {"roles-v22", "roles-v23", "roles-v24", "roles-v25"} else
                            planned_selection_instructions_v21 if
                            _selector_format(prepared) == "roles-v21" else
                            planned_selection_instructions_v20 if
                            _selector_format(prepared) in {"roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"} else
                            planned_selection_instructions_v16 if
                            _selector_format(prepared) in {"roles-v15", "roles-v16", "roles-v17", "roles-v18"} else
                            planned_selection_instructions_v15 if
                            _selector_format(prepared) == "roles-v14" else
                            planned_selection_instructions)(prepared.structured, projection)
            schema = planned_selection_schema(prepared.structured, projection,
                max_references=3 if _selector_format(prepared) in {"roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"} else
                4 if _selector_format(prepared) in {"roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25"} else 8)
        elif _selector_format(prepared) in {"roles-v2", "roles-v3", "roles-v4", "roles-v5", "roles-v6", "roles-v7", "roles-v8", "roles-v9", "roles-v10", "roles-v11", "roles-v12"}:
            instructions = ({"roles-v2": selection_instructions_v2,
                             "roles-v3": selection_instructions_v3,
                             "roles-v4": selection_instructions_v4,
                             "roles-v5": selection_instructions_v5,
                             "roles-v6": selection_instructions_v5,
                             "roles-v7": selection_instructions_v5,
                             "roles-v8": selection_instructions_v8,
                             "roles-v9": selection_instructions_v8,
                             "roles-v10": selection_instructions_v8,
                             "roles-v11": selection_instructions_v8,
                             "roles-v12": selection_instructions_v8}[_selector_format(prepared)]
                            (prepared.structured, projection))
            schema = selection_schema_v2(prepared.structured, projection)
        else:
            instructions = selection_instructions(prepared.structured, projection)
            schema = selection_schema(prepared.structured, projection)
        selection_packet = (selector_packet(prepared) if _selector_format(prepared) in {"roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}
                            else prepared.packet)
        payload = json.dumps({"packet": selection_packet}, sort_keys=True,
                             ensure_ascii=False, separators=(",", ":"))
        name = "FocusedResultsSelection"
    else:
        instructions = (focused_revision_instructions(prepared) if phase == "revision"
                        else focused_instructions(prepared))
        schema = focused_schema(prepared)
        packet = {key: value for key, value in prepared.packet.items() if key != "wire_aliases"}
        input_data: dict[str, object] = {"packet": packet}
        if phase in {"correction", "revision"}:
            if previous_wire is None or (phase == "correction" and not feedback):
                raise ValueError("focused correction requires a failed draft")
            input_data["previous_wire"] = json.loads(previous_wire)
            if phase == "revision":
                input_data["revision_trigger"] = "editorial_revision"
            rows = []
            for finding in feedback:
                row = finding.model_dump(mode="json")
                if finding.reference_id is not None:
                    row["reference_id"] = (focused_alias_for_canonical(prepared,
                        finding.reference_id) or finding.reference_id)
                rows.append(row)
            input_data["feedback"] = rows
        payload = json.dumps(input_data, sort_keys=True,
                             ensure_ascii=False, separators=(",", ":"))
        name = "FocusedResultsDocument"
    if config.authoring_guidance and config.authoring_guidance.strip():
        instructions += "\n" + config.authoring_guidance
    request: dict[str, object] = {
        "model": config.model, "reasoning": {"effort": settings.reasoning_effort},
        "instructions": instructions, "input": payload,
        "text": {"format": {"type": "json_schema", "name": name,
                            "strict": True, "schema": schema}},
    }
    schema_text = json.dumps(schema, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    prompt = instructions + payload
    size = len(prompt.encode()) + len(schema_text.encode())
    return RequestEnvelope(request, size, size + config.prompt_overhead_tokens +
                           config.max_output_tokens, content_digest(prompt),
                           content_digest(schema_text))


def _within(envelope: RequestEnvelope, config: ResultsConfig,
            count: InputTokenReceipt | None) -> bool:
    if count is None:
        return (envelope.estimated_total_tokens <= config.context_limit_tokens and
                (config.max_input_tokens is None or
                 envelope.estimated_total_tokens - config.max_output_tokens <=
                 config.max_input_tokens))
    return (count.input_tokens + config.max_output_tokens + config.prompt_overhead_tokens <=
            config.context_limit_tokens and
            (config.max_input_tokens is None or count.input_tokens <= config.max_input_tokens))


def _receipt(writer: InteractiveWriter) -> WriterReceipt | None:
    result = writer.take_receipt()
    return WriterReceipt.model_validate(result) if result is not None else None


def _new_pass(common: dict[str, object], **fields: object) -> FocusedPass:
    return FocusedPass.model_validate({**common, **fields})


def _pass(phase: Literal["selection", "composition", "correction", "revision"], envelope: RequestEnvelope,
          config: ResultsConfig, settings: InteractiveSettings, writer: InteractiveWriter,
          measurer: ResultsInputMeasurer | None,
          decode: Callable[[str], StructuredSelection | StructuredDocument],
          *, projection: SolutionProjection,
          prepared: InteractivePreparedInput,
          checker: Callable[[StructuredDocument, SolutionProjection,
                             InteractivePreparedInput], tuple[CheckFinding, ...]] | None = None,
          ) -> FocusedPass:
    common: dict[str, object] = {"phase": phase, "request": envelope.request,
              "request_digest": content_digest(envelope.request),
              "input_bytes": envelope.input_bytes,
              "estimated_total_tokens": envelope.estimated_total_tokens,
              "prompt_digest": envelope.prompt_digest, "schema_digest": envelope.schema_digest}
    count: InputTokenReceipt | None = None
    if measurer is not None:
        try:
            measured = measurer.measure(envelope.request, config)
            count = InputTokenReceipt.model_validate(measured.model_dump(mode="json"))
            if count.request_digest != common["request_digest"]:
                raise ValueError("input token receipt request digest differs")
        except (AttributeError, ResultsWriterError, ValueError, TypeError):
            return _new_pass(common, outcome="measurement_error", writer_called=False,
                               error="input_token_measurement_failed")
    if not _within(envelope, config, count):
        return _new_pass(common, outcome="context_limit", writer_called=False,
                           input_token_receipt=count, error="context_limit")
    raw: str | None = None
    try:
        raw = writer.author(envelope.request, config, settings)
        parsed = decode(raw)
        receipt = _receipt(writer)
        if phase == "selection":
            if not isinstance(parsed, StructuredSelection):
                raise ValueError("selector returned a non-selection document")
            return _new_pass(common, outcome="recoverable", writer_called=True,
                input_token_receipt=count, writer_receipt=receipt,
                returned_service_tier=_returned_tier(receipt), raw_wire=raw, selection=parsed)
        if not isinstance(parsed, StructuredDocument):
            raise TypeError("composer returned a non-document selection")
        findings = (checker(parsed, projection, prepared) if checker else
                    check_structured_document(parsed, projection, prepared.structured))
        return _new_pass(common, outcome="recoverable", writer_called=True,
            input_token_receipt=count, writer_receipt=receipt,
            returned_service_tier=_returned_tier(receipt), raw_wire=raw,
            document=parsed, findings=findings)
    except ResultsWriterError as exc:
        receipt = _receipt(writer) or WriterReceipt(raw_response=exc.raw_response)
        return _new_pass(common, outcome="api_error" if exc.outcome == "api_error" else
            "generation_error", writer_called=True, input_token_receipt=count,
            writer_receipt=receipt, returned_service_tier=_returned_tier(receipt),
            raw_wire=raw, error=str(exc), failure_subtype=exc.outcome)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        receipt = _receipt(writer)
        return _new_pass(common, outcome="generation_error", writer_called=True,
            input_token_receipt=count, writer_receipt=receipt,
            returned_service_tier=_returned_tier(receipt), raw_wire=raw,
            error=f"schema_error: {exc}", failure_subtype="schema_error")


def run_focused_results(projection: SolutionProjection, config: ResultsConfig,
                        writer: InteractiveWriter,
                        input_measurer: ResultsInputMeasurer | None = None,
                        *, fx_acquisition: FxAcquisition | None = None,
                        selection_format: Literal["roles-v1", "roles-v2"] = "roles-v1",
                        composition_format: Literal["source-v1", "comparisons-v1"] = "source-v1",
                        profile: Literal["focused-v4", "focused-v5", "focused-v6", "focused-v7", "focused-v8", "focused-v9", "focused-v10", "focused-v11", "focused-v12", "focused-v13", "focused-v14", "focused-v15", "focused-v16", "focused-v17", "focused-v18", "focused-v19", "focused-v20", "focused-v21", "focused-v22", "focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28", "focused-v29", "focused-v30"] | None = None,
                        ) -> FocusedResultsArtifact | FocusedResultsArtifactV9 | FocusedResultsArtifactV10 | FocusedResultsArtifactV11 | FocusedResultsArtifactV12:
    if profile in {"focused-v17", "focused-v18", "focused-v19", "focused-v20", "focused-v21", "focused-v22"}:
        from .focused_patch_runtime import run_focused_v17

        if selection_format != "roles-v1" or composition_format != "source-v1":
            raise ValueError("focused-v17 owns its selection and composition formats")
        return run_focused_v17(projection, config, writer, input_measurer,
                               fx_acquisition=fx_acquisition, profile=profile)
    if profile in {"focused-v11", "focused-v12", "focused-v13", "focused-v14", "focused-v15", "focused-v16", "focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28", "focused-v29", "focused-v30"}:
        from .focused_comparison_runtime import run_focused_v11

        if selection_format != "roles-v1" or composition_format != "source-v1":
            raise ValueError("focused-v11 owns its selection and composition formats")
        return run_focused_v11(projection, config, writer, input_measurer,
                              fx_acquisition=fx_acquisition, profile=profile)
    if profile in {"focused-v8", "focused-v9", "focused-v10"}:
        from .focused_v8 import run_focused_v8

        if selection_format != "roles-v1" or composition_format != "source-v1":
            raise ValueError("focused-v8 owns its selection and composition formats")
        return run_focused_v8(projection, config, writer, input_measurer,
                              fx_acquisition=fx_acquisition, profile=profile)
    if profile in {"focused-v4", "focused-v5", "focused-v6", "focused-v7"}:
        from .focused_v4 import run_focused_v4

        if selection_format != "roles-v1" or composition_format != "source-v1":
            raise ValueError("focused-v4 owns its selection and composition formats")
        return run_focused_v4(projection, config, writer, input_measurer,
                              fx_acquisition=fx_acquisition, profile=profile)
    if profile is not None:
        raise ValueError("unknown focused Results profile")
    started = time.perf_counter()
    if config.model != "gpt-6-luna":
        raise ValueError("focused Results requires explicit gpt-6-luna model")
    evidence = resolve_workspace(projection, fx_acquisition=fx_acquisition)
    selector = prepare_focused_selector(projection, config, evidence,
                                        selection_format=selection_format)
    first_envelope = _request(selector, config, SELECTOR_SETTINGS, "selection", projection)
    decode_selector = (decode_selection_v2 if selection_format == "roles-v2" else
                       decode_selection)
    first = _pass("selection", first_envelope, config, SELECTOR_SETTINGS, writer,
        input_measurer, lambda raw: decode_selector(raw, selector.structured, projection),
        projection=projection, prepared=selector)
    passes = [first]
    focus: InteractivePreparedInput | None = None
    resolved: ResolvedStructuredAnswer | None = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        focus = prepare_focused_composer(first.selection, selector, projection, evidence,
                                        composition_format=composition_format)
        second_envelope = _request(focus, config, COMPOSER_SETTINGS, "composition", projection)
        second = _pass("composition", second_envelope, config, COMPOSER_SETTINGS, writer,
            input_measurer, lambda raw: decode_focused_wire(raw, focus, projection),
            projection=projection, prepared=focus)
        passes.append(second)
        if second.outcome == "recoverable":
            assert second.document is not None
            resolved = resolve_structured_document(second.document, focus.structured,
                                                   evidence, second.findings)
    terminal = passes[-1]
    delivered = resolved is not None
    artifact = FocusedResultsArtifact(evidence=evidence, config=config,
        selector_settings=SELECTOR_SETTINGS, composer_settings=COMPOSER_SETTINGS,
        selector_prepared=selector, focus_prepared=focus, passes=tuple(passes),
        generation_outcome="success" if delivered else cast(
            Literal["api_error", "generation_error", "context_limit", "measurement_error"],
            terminal.outcome),
        validation_outcome="unavailable" if not delivered else "annotated" if any(
            finding.outcome == "failed" for finding in terminal.findings) else "clean",
        delivery_outcome="delivered" if delivered else "not_delivered", resolved=resolved,
        resolved_digest=content_digest(resolved.model_dump(mode="json")) if resolved else None,
        runtime_seconds=0)
    return artifact.model_copy(update={"runtime_seconds": time.perf_counter() - started})


def replay_focused_results(artifact: FocusedResultsArtifact | FocusedResultsArtifactV9 |
                           FocusedResultsArtifactV10 | FocusedResultsArtifactV11 | FocusedResultsArtifactV12,
                           ) -> ResolvedStructuredAnswer | ResolvedFocusedComparisonAnswer | None:
    if isinstance(artifact, FocusedResultsArtifactV12):
        from .focused_patch_runtime import replay_focused_v17

        return replay_focused_v17(artifact)
    if isinstance(artifact, FocusedResultsArtifactV11):
        from .focused_comparison_runtime import replay_focused_v11

        return replay_focused_v11(artifact)
    if isinstance(artifact, FocusedResultsArtifactV10):
        from .focused_v8 import replay_focused_v8

        return replay_focused_v8(artifact)
    if isinstance(artifact, FocusedResultsArtifactV9):
        from .focused_v4 import replay_focused_v4

        return replay_focused_v4(artifact)
    if artifact.config.model != "gpt-6-luna" or artifact.selector_settings != SELECTOR_SETTINGS or \
            artifact.composer_settings != COMPOSER_SETTINGS:
        raise ValueError("saved focused model settings differ")
    projection = SolutionProjection.model_validate(artifact.evidence.source.model_dump(mode="json"))
    evidence = resolve_workspace(projection, fx_acquisition=artifact.evidence.fx_acquisition)
    if artifact.evidence != evidence:
        raise ValueError("saved focused workspace differs from source")
    verify_authoring_view(projection, prepare_results(projection, artifact.config))
    selector_format = _selector_format(artifact.selector_prepared)
    selector = prepare_focused_selector(projection, artifact.config, evidence,
                                        selection_format=selector_format)
    if artifact.selector_prepared != selector:
        raise ValueError("saved focused selector preparation differs from source")
    if not 1 <= len(artifact.passes) <= 2 or artifact.passes[0].phase != "selection" or (
            len(artifact.passes) == 2 and artifact.passes[1].phase != "composition"):
        raise ValueError("saved focused pass sequence is invalid")
    first = artifact.passes[0]
    decode_selector = (decode_selection_v2 if selector_format == "roles-v2" else
                       decode_selection)
    _replay_pass(first, _request(selector, artifact.config, SELECTOR_SETTINGS, "selection", projection),
        artifact.config, lambda raw: decode_selector(raw, selector.structured, projection),
        projection, selector)
    focus: InteractivePreparedInput | None = None
    resolved = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        composition_format = (artifact.focus_prepared.packet.get("composition_format", "source-v1")
                              if artifact.focus_prepared is not None else "source-v1")
        if composition_format not in {"source-v1", "comparisons-v1"}:
            raise ValueError("unknown saved focused composition format")
        focus = prepare_focused_composer(first.selection, selector, projection, evidence,
                                        composition_format=composition_format)
        if len(artifact.passes) != 2:
            raise ValueError("saved focused composition pass is missing")
        second = artifact.passes[1]
        _replay_pass(second, _request(focus, artifact.config, COMPOSER_SETTINGS,
            "composition", projection), artifact.config,
            lambda raw: decode_focused_wire(raw, focus, projection), projection, focus)
        if second.outcome == "recoverable":
            assert second.document is not None
            resolved = resolve_structured_document(second.document, focus.structured,
                                                   evidence, second.findings)
    elif len(artifact.passes) != 1:
        raise ValueError("saved focused composer ran without a valid selection")
    if artifact.focus_prepared != focus:
        raise ValueError("saved focused packet differs from selected source")
    terminal = artifact.passes[-1]
    delivered = resolved is not None
    if (artifact.generation_outcome != ("success" if delivered else terminal.outcome) or
            artifact.validation_outcome != ("unavailable" if not delivered else
                "annotated" if any(f.outcome == "failed" for f in terminal.findings) else "clean") or
            artifact.delivery_outcome != ("delivered" if delivered else "not_delivered") or
            artifact.resolved != resolved or artifact.resolved_digest != (
                content_digest(resolved.model_dump(mode="json")) if resolved else None)):
        raise ValueError("saved focused outcome or answer differs")
    return resolved


def parse_focused_artifact(raw: bytes | str) -> (FocusedResultsArtifact |
                                                 FocusedResultsArtifactV9 |
                                                 FocusedResultsArtifactV10 |
                                                 FocusedResultsArtifactV11 |
                                                 FocusedResultsArtifactV12):
    """Parse an immutable focused run without version coercion."""
    value = json.loads(raw)
    if value.get("contract_version") == "results-artifact-v12":
        return FocusedResultsArtifactV12.model_validate(value)
    if value.get("contract_version") == "results-artifact-v11":
        return FocusedResultsArtifactV11.model_validate(value)
    if value.get("contract_version") == "results-artifact-v10":
        return FocusedResultsArtifactV10.model_validate(value)
    if value.get("contract_version") == "results-artifact-v9":
        return FocusedResultsArtifactV9.model_validate(value)
    if value.get("contract_version") == "results-artifact-v8":
        return FocusedResultsArtifact.model_validate(value)
    raise ValueError("unknown focused Results artifact version")


def _replay_pass(item: FocusedPass, envelope: RequestEnvelope, config: ResultsConfig,
                 decode: Callable[[str], StructuredSelection | StructuredDocument],
                 projection: SolutionProjection, prepared: InteractivePreparedInput,
                 checker: Callable[[StructuredDocument, SolutionProjection,
                                    InteractivePreparedInput], tuple[CheckFinding, ...]] | None = None,
                 ) -> None:
    if (item.request != envelope.request or item.request_digest != content_digest(envelope.request)
            or item.input_bytes != envelope.input_bytes or
            item.estimated_total_tokens != envelope.estimated_total_tokens or
            item.prompt_digest != envelope.prompt_digest or item.schema_digest != envelope.schema_digest):
        raise ValueError("saved focused pass request differs")
    count = item.input_token_receipt
    if count is not None and count.request_digest != item.request_digest:
        raise ValueError("saved focused token count differs")
    within = _within(envelope, config, count)
    if item.returned_service_tier != _returned_tier(item.writer_receipt):
        raise ValueError("saved focused response tier differs")
    if item.raw_wire is not None and _response_text(item.writer_receipt) != item.raw_wire:
        raise ValueError("saved focused raw wire differs from response")
    if item.writer_called and not within:
        raise ValueError("saved focused pass exceeded context")
    if not item.writer_called:
        if item.selection is not None or item.document is not None or item.raw_wire is not None or \
                item.writer_receipt is not None or item.findings:
            raise ValueError("saved focused uncalled pass has generation evidence")
        if item.outcome == "context_limit" and not within and item.error == "context_limit":
            return
        if item.outcome == "measurement_error" and count is None and \
                item.error == "input_token_measurement_failed":
            return
        raise ValueError("saved focused uncalled pass is invalid")
    if item.outcome == "recoverable":
        if item.raw_wire is None or item.error is not None or item.failure_subtype is not None:
            raise ValueError("saved focused recoverable pass has invalid metadata")
        _validate_recoverable_response(item.writer_receipt)
        parsed = decode(item.raw_wire)
        if item.phase == "selection":
            if parsed != item.selection or not isinstance(parsed, StructuredSelection):
                raise ValueError("saved focused selection differs from wire")
        else:
            if parsed != item.document or not isinstance(parsed, StructuredDocument) or \
                    item.findings != (checker(parsed, projection, prepared) if checker else
                                     check_structured_document(parsed, projection,
                                                               prepared.structured)):
                raise ValueError("saved focused document or checks differ from wire")
        return
    if item.selection is not None or item.document is not None or item.findings:
        raise ValueError("saved focused failed pass has a document")
    if item.outcome == "api_error" and item.failure_subtype != "api_error":
        raise ValueError("saved focused API failure subtype differs")
    if item.outcome == "generation_error" and item.failure_subtype not in {
            "refusal", "incomplete", "schema_error"}:
        raise ValueError("saved focused generation failure subtype differs")
    if item.outcome not in {"api_error", "generation_error"}:
        raise ValueError("saved focused called pass outcome is invalid")
    if item.failure_subtype == "schema_error" and item.raw_wire is not None:
        try:
            decode(item.raw_wire)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
        else:
            raise ValueError("saved focused schema failure decoded successfully")
