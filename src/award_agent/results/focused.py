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
    InputTokenReceipt,
    ResultsConfig,
    ResultsInputMeasurer,
    ResultsWriterError,
    WriterReceipt,
)
from .core import prepare_results
from .currency import FxAcquisition
from .focused_contracts import FocusedPass, FocusedResultsArtifact
from .focused_packet import (
    build_packet as build_focus_packet,
)
from .focused_packet import (
    decode_selection,
    decode_selection_v2,
    selection_instructions,
    selection_instructions_v2,
    selection_schema,
    selection_schema_v2,
)
from .focused_wire import decode as decode_focused_wire
from .focused_wire import instructions as focused_instructions
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
                             selection_format: Literal["roles-v1", "roles-v2"] = "roles-v1",
                             ) -> InteractivePreparedInput:
    trusted = SolutionProjection.model_validate(projection.model_dump(mode="json"))
    workspace = evidence or resolve_workspace(trusted)
    structured = prepare_structured_results(trusted, config)
    packet = build_indexed_packet(structured, trusted, workspace)
    if selection_format == "roles-v2":
        packet["selection_format"] = "roles-v2"
    elif selection_format != "roles-v1":
        raise ValueError("unknown focused selection format")
    return _prepared(packet, structured)


def prepare_focused_composer(selection: StructuredSelection,
                             selector: InteractivePreparedInput,
                             projection: SolutionProjection,
                             evidence: WorkspaceEvidence, *,
                             composition_format: Literal["source-v1", "comparisons-v1"] = "source-v1",
                             ) -> InteractivePreparedInput:
    packet = build_focus_packet(selection, selector.structured, projection, evidence,
        selection_format=_selector_format(selector), composition_format=composition_format)
    if packet.get("format") != "focused-v1":
        raise ValueError("focused packet builder returned an unexpected format")
    return _prepared(packet, selector.structured)


def _selector_format(prepared: InteractivePreparedInput) -> Literal["roles-v1", "roles-v2"]:
    value = prepared.packet.get("selection_format", "roles-v1")
    if value not in {"roles-v1", "roles-v2"}:
        raise ValueError("unknown focused selection format")
    return value


def _request(prepared: InteractivePreparedInput, config: ResultsConfig,
             settings: InteractiveSettings, phase: Literal["selection", "composition"],
             projection: SolutionProjection) -> RequestEnvelope:
    if phase == "selection":
        if _selector_format(prepared) == "roles-v2":
            instructions = selection_instructions_v2(prepared.structured, projection)
            schema = selection_schema_v2(prepared.structured, projection)
        else:
            instructions = selection_instructions(prepared.structured, projection)
            schema = selection_schema(prepared.structured, projection)
        payload = json.dumps({"packet": prepared.packet}, sort_keys=True,
                             ensure_ascii=False, separators=(",", ":"))
        name = "FocusedResultsSelection"
    else:
        instructions = focused_instructions(prepared)
        schema = focused_schema(prepared)
        packet = {key: value for key, value in prepared.packet.items() if key != "wire_aliases"}
        payload = json.dumps({"packet": packet}, sort_keys=True,
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


def _pass(phase: Literal["selection", "composition"], envelope: RequestEnvelope,
          config: ResultsConfig, settings: InteractiveSettings, writer: InteractiveWriter,
          measurer: ResultsInputMeasurer | None,
          decode: Callable[[str], StructuredSelection | StructuredDocument],
          *, projection: SolutionProjection,
          prepared: InteractivePreparedInput) -> FocusedPass:
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
        findings = check_structured_document(parsed, projection, prepared.structured)
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
                        ) -> FocusedResultsArtifact:
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


def replay_focused_results(artifact: FocusedResultsArtifact) -> ResolvedStructuredAnswer | None:
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


def _replay_pass(item: FocusedPass, envelope: RequestEnvelope, config: ResultsConfig,
                 decode: Callable[[str], StructuredSelection | StructuredDocument],
                 projection: SolutionProjection, prepared: InteractivePreparedInput) -> None:
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
                    item.findings != check_structured_document(parsed, projection,
                                                               prepared.structured):
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
