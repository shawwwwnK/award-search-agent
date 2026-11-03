"""V11 focused Results with optional source-owned temporal comparison cards."""

from __future__ import annotations

import json
import time
from typing import Literal, cast

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection

from .authoring import verify_authoring_view
from .comparison_registry import build_temporal_registry, validate_temporal_registry
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
from .focused import (
    COMPOSER_SETTINGS,
    SELECTOR_SETTINGS,
    _pass,
    _prepared,
    _receipt,
    _replay_pass,
    _request,
    _within,
    prepare_focused_composer,
    prepare_focused_selector,
)
from .focused_comparison_contracts import (
    FocusedComparisonPass,
    FocusedComparisonPreparedInput,
    FocusedResultsArtifactV11,
    ResolvedFocusedComparisonAnswer,
    TemporalComparisonRegistry,
)
from .focused_comparison_wire import (
    decode,
    findings,
    instructions,
    resolve_focused_comparison_document,
    schema,
)
from .focused_contracts import FocusedPass
from .focused_packet import decode_selection_v2
from .focused_pair_dossier import build_pair_dossiers
from .focused_records import writer_packet
from .focused_selection_plan import decode as decode_planned_selection
from .focused_selection_plan import editorial_plan
from .focused_traveler_evidence import build_traveler_evidence
from .focused_v4 import LOW_SELECTOR_SETTINGS, MEDIUM_SETTINGS
from .focused_wire import alias_for_canonical
from .interactive import _response_text, _returned_tier, _validate_recoverable_response
from .interactive_contracts import InteractivePreparedInput, InteractiveSettings, InteractiveWriter
from .presentation import resolve_workspace
from .runner import RequestEnvelope, choose_recoverable
from .structured_contracts import StructuredSelection
from .workspace_contracts import WorkspaceEvidence


def _aliases(prepared: InteractivePreparedInput, selection: StructuredSelection) -> dict[str, str]:
    bindings = prepared.packet.get("wire_aliases")
    if not isinstance(bindings, dict):
        raise TypeError("focused V11 composer lacks exact alias bindings")
    short_to_canonical = prepared.structured.references.journeys
    groups = cast(list[dict[str, object]], prepared.packet["journeys"])
    refs = {member["ref"] for group in groups
            for member in cast(list[dict[str, str]], group["members"])}
    aliases = {long: short_to_canonical[short] for long, short in bindings.items()
               if long in refs}
    if set(aliases) != refs or set(aliases.values()) != set(selection.journey_ids):
        raise ValueError("focused V11 journey aliases differ from selection")
    return aliases


def _projection(registry: TemporalComparisonRegistry) -> list[dict[str, object]]:
    return [{"id": fact.comparison_id, "metric": fact.metric,
             "first_ref": fact.first_alias, "second_ref": fact.second_alias,
             "relation": fact.relation,
             "difference_minutes": str(fact.difference_minutes)}
            for fact in registry.facts]


def prepare_focused_v11_composer(selection: StructuredSelection,
                                selector: InteractivePreparedInput,
                                projection: SolutionProjection,
                                evidence: WorkspaceEvidence,
                                *, raw_selection_wire: str | None = None,
                                ) -> tuple[FocusedComparisonPreparedInput, TemporalComparisonRegistry]:
    selector_format = selector.packet.get("selection_format")
    if selector_format not in {"roles-v10", "roles-v11", "roles-v12", "roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        raise ValueError("focused comparison selector has unknown profile marker")
    if selector_format in {"roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"} and (
            len(selection.journey_ids) + len(selection.incomplete_observation_ids) > 2 or
            len(selection.journey_ids) + len(selection.incomplete_observation_ids) +
            int(selection.benchmark_observation_id is not None) > 3):
        raise ValueError("V28 selection exceeds the authoring reference ceilings")
    if selector_format in {"roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25"} and (
            len(selection.journey_ids) + len(selection.incomplete_observation_ids) +
            int(selection.benchmark_observation_id is not None) > 4):
        raise ValueError("V22 selection exceeds the four-reference authoring bundle")
    composition_format: Literal["complete-v8", "complete-v9", "complete-v10", "complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"] = (
        "complete-v28" if selector_format == "roles-v30" else
        "complete-v27" if selector_format == "roles-v29" else
        "complete-v26" if selector_format == "roles-v28" else
        "complete-v25" if selector_format == "roles-v27" else
        "complete-v24" if selector_format == "roles-v26" else
        "complete-v23" if selector_format == "roles-v25" else
        "complete-v22" if selector_format == "roles-v24" else
        "complete-v21" if selector_format == "roles-v23" else
        "complete-v20" if selector_format == "roles-v22" else
        "complete-v19" if selector_format == "roles-v21" else
        "complete-v18" if selector_format == "roles-v20" else
        "complete-v17" if selector_format == "roles-v19" else
        "complete-v16" if selector_format == "roles-v18" else
        "complete-v15" if selector_format == "roles-v17" else
        "complete-v14" if selector_format == "roles-v16" else
        "complete-v13" if selector_format == "roles-v15" else
        "complete-v12" if selector_format == "roles-v14" else
        "complete-v11" if selector_format == "roles-v13" else
        "complete-v10" if selector_format == "roles-v12" else
        "complete-v9" if selector_format == "roles-v11" else "complete-v8")
    focus = prepare_focused_composer(selection, selector, projection, evidence,
                                    composition_format=composition_format)
    aliases = _aliases(focus, selection)
    registry = build_temporal_registry(evidence, selection.journey_ids, aliases)
    packet = dict(focus.packet)
    packet["temporal_comparisons"] = _projection(registry)
    if selector_format in {"roles-v12", "roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        selector_packet = selector.packet
        packet["source_scope"] = {
            "full_selectable_journey_count": len(cast(list[object], selector_packet["journey_rows"])),
            "full_selectable_lead_count": len(cast(list[object], selector_packet["lead_rows"])),
            "full_direct_cash_benchmark_count": len(cast(list[object], selector_packet["benchmark_refs"])),
            "selected_journey_count": len(selection.journey_ids),
            "selected_lead_count": len(selection.incomplete_observation_ids),
            "selected_benchmark_count": int(selection.benchmark_observation_id is not None),
            "meaning": "Authoring records are selected examples; these counts describe "
                       "source roles, not exhaustive availability or date coverage."}
    if selector_format in {"roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        if raw_selection_wire is None:
            raise ValueError("V14 composer requires the exact selector wire")
        packet["editorial_plan"] = editorial_plan(raw_selection_wire, selector,
            focus, selection, projection)
    if selector_format in {"roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        packet["traveler_evidence"] = build_traveler_evidence(
            focus.model_copy(update={"packet": packet}), evidence)
    if selector_format in {"roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        packet["comparison_pairs"] = build_pair_dossiers(
            focus.model_copy(update={"packet": packet}), evidence)
    return FocusedComparisonPreparedInput.model_validate(
        _prepared(packet, focus.structured).model_dump(mode="json")), registry


def _composer_request(prepared: InteractivePreparedInput, config: ResultsConfig,
                      phase: Literal["composition", "correction"],
                      settings: InteractiveSettings, *,
                      previous_wire: str | None = None,
                      feedback: tuple[CheckFinding, ...] = (),
                      ) -> RequestEnvelope:
    guide = instructions(prepared)
    if phase == "correction":
        guide += (" This is the one bounded correction after failed mechanical checks. "
                  "Use the SAME frozen source packet and temporal comparison IDs; "
                  "repair the supplied findings while rechecking the complete "
                  "answer. Return a full final blocks document, not a patch.")
    else:
        guide += " Write the full final traveler answer in this pass."
    if config.authoring_guidance and config.authoring_guidance.strip():
        guide += "\n" + config.authoring_guidance
    packet = (writer_packet(prepared) if prepared.packet.get("composition_format") in {"complete-v10", "complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}
              else {key: value for key, value in prepared.packet.items() if key != "wire_aliases"})
    input_data: dict[str, object] = {"packet": packet}
    if phase == "correction":
        if previous_wire is None or not feedback:
            raise ValueError("focused V11 correction needs a failed draft")
        input_data["previous_wire"] = json.loads(previous_wire)
        rows = []
        for finding in feedback:
            row = finding.model_dump(mode="json")
            if finding.reference_id is not None:
                row["reference_id"] = (alias_for_canonical(prepared,
                    finding.reference_id) or finding.reference_id)
            rows.append(row)
        input_data["feedback"] = rows
    payload = json.dumps(input_data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    shape = schema(prepared)
    schema_text = json.dumps(shape, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    request: dict[str, object] = {
        "model": config.model, "reasoning": {"effort": settings.reasoning_effort},
        "instructions": guide, "input": payload,
        "text": {"format": {"type": "json_schema", "name": "FocusedResultsComparisonDocument",
                            "strict": True, "schema": shape}},
    }
    prompt = guide + payload
    size = len(prompt.encode()) + len(schema_text.encode())
    return RequestEnvelope(request, size, size + config.prompt_overhead_tokens +
                           config.max_output_tokens, content_digest(prompt),
                           content_digest(schema_text))


def _run_composition(phase: Literal["composition", "correction"],
                     envelope: RequestEnvelope, config: ResultsConfig,
                     settings: InteractiveSettings,
                     writer: InteractiveWriter, measurer: ResultsInputMeasurer | None,
                     prepared: InteractivePreparedInput, projection: SolutionProjection,
                     registry: TemporalComparisonRegistry) -> FocusedComparisonPass:
    common: dict[str, object] = {"phase": phase, "request": envelope.request,
        "request_digest": content_digest(envelope.request), "input_bytes": envelope.input_bytes,
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
            return FocusedComparisonPass.model_validate({**common, "outcome": "measurement_error",
                "writer_called": False, "error": "input_token_measurement_failed"})
    if not _within(envelope, config, count):
        return FocusedComparisonPass.model_validate({**common, "outcome": "context_limit",
            "writer_called": False, "input_token_receipt": count, "error": "context_limit"})
    raw: str | None = None
    try:
        raw = writer.author(envelope.request, config, settings)
        document = decode(raw, prepared, projection)
        receipt = _receipt(writer)
        checks = findings(document, projection, prepared, registry)
        return FocusedComparisonPass.model_validate({**common, "outcome": "recoverable",
            "writer_called": True, "input_token_receipt": count, "writer_receipt": receipt,
            "returned_service_tier": _returned_tier(receipt), "raw_wire": raw,
            "document": document, "findings": checks})
    except ResultsWriterError as exc:
        receipt = _receipt(writer) or WriterReceipt(raw_response=exc.raw_response)
        return FocusedComparisonPass.model_validate({**common,
            "outcome": "api_error" if exc.outcome == "api_error" else "generation_error",
            "writer_called": True, "input_token_receipt": count, "writer_receipt": receipt,
            "returned_service_tier": _returned_tier(receipt), "raw_wire": raw,
            "error": str(exc), "failure_subtype": exc.outcome})
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        receipt = _receipt(writer)
        return FocusedComparisonPass.model_validate({**common, "outcome": "generation_error",
            "writer_called": True, "input_token_receipt": count, "writer_receipt": receipt,
            "returned_service_tier": _returned_tier(receipt), "raw_wire": raw,
            "error": f"schema_error: {exc}", "failure_subtype": "schema_error"})


def _selected(passes: list[FocusedComparisonPass]) -> tuple[int | None, str]:
    recoverable = tuple((index - 1, item.findings) for index, item in enumerate(passes)
                        if index >= 1 and item.outcome == "recoverable" and item.document is not None)
    if not recoverable:
        return None, "no_recoverable_draft"
    relative, reason = choose_recoverable(recoverable)
    return relative + 1, reason


def _outcome(passes: list[FocusedComparisonPass], selected: int | None,
             focus: InteractivePreparedInput | None, evidence: WorkspaceEvidence,
             registry: TemporalComparisonRegistry | None,
             ) -> tuple[ResolvedFocusedComparisonAnswer | None, str, str]:
    if selected is None:
        return None, "unavailable", "not_delivered"
    assert focus is not None and registry is not None
    document = passes[selected].document
    assert document is not None
    resolved = resolve_focused_comparison_document(document, focus, evidence,
                                                    registry, passes[selected].findings)
    validation = "annotated" if any(f.outcome == "failed" for f in passes[selected].findings) else "clean"
    return resolved, validation, "delivered"


def run_focused_v11(projection: SolutionProjection, config: ResultsConfig,
                    writer: InteractiveWriter,
                    input_measurer: ResultsInputMeasurer | None = None, *,
                    fx_acquisition: FxAcquisition | None = None,
                    profile: Literal["focused-v11", "focused-v12", "focused-v13", "focused-v14", "focused-v15", "focused-v16", "focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28", "focused-v29", "focused-v30"] = "focused-v11",
                    ) -> FocusedResultsArtifactV11:
    started = time.perf_counter()
    if config.model != "gpt-6-luna":
        raise ValueError("focused-v11 requires explicit gpt-6-luna")
    evidence = resolve_workspace(projection, fx_acquisition=fx_acquisition)
    if profile not in {"focused-v11", "focused-v12", "focused-v13", "focused-v14", "focused-v15", "focused-v16", "focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28", "focused-v29", "focused-v30"}:
        raise ValueError("unknown focused comparison profile")
    selector_format: Literal["roles-v10", "roles-v11", "roles-v12", "roles-v13", "roles-v14", "roles-v15", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"] = (
        ("roles-v28" if any(item.status in {"admitted", "conditional"}
         for item in projection.view.alternatives) else "roles-v30")
        if profile == "focused-v30" else
        ("roles-v28" if any(item.status in {"admitted", "conditional"}
         for item in projection.view.alternatives) else "roles-v29")
        if profile == "focused-v29" else
        ("roles-v26" if any(item.status in {"admitted", "conditional"}
         for item in projection.view.alternatives) else "roles-v27")
        if profile == "focused-v28" else
        ("roles-v21" if any(item.status in {"admitted", "conditional"}
                       for item in projection.view.alternatives) else
         "roles-v25" if profile == "focused-v27" else
         "roles-v24" if profile == "focused-v26" else
         "roles-v23" if profile == "focused-v25" else "roles-v22")
        if profile in {"focused-v24", "focused-v25", "focused-v26", "focused-v27"} else
        "roles-v21" if profile == "focused-v23" else
        "roles-v15" if profile == "focused-v16" else
        "roles-v14" if profile == "focused-v15" else
        "roles-v13" if profile == "focused-v14" else
        "roles-v12" if profile == "focused-v13" else
        "roles-v11" if profile == "focused-v12" else "roles-v10")
    composer_settings = (COMPOSER_SETTINGS if profile in {"focused-v12", "focused-v23", "focused-v24"}
                         or (profile == "focused-v28" and selector_format == "roles-v27")
                         or (profile == "focused-v29" and selector_format == "roles-v29")
                         or (profile == "focused-v30" and selector_format == "roles-v30")
                         or (profile in {"focused-v25", "focused-v26", "focused-v27"} and selector_format == "roles-v21")
                         else MEDIUM_SETTINGS)
    selector_settings = (SELECTOR_SETTINGS if profile in {"focused-v23", "focused-v24", "focused-v25"} or
                         (profile in {"focused-v26", "focused-v27"} and selector_format == "roles-v21") or
                         (profile == "focused-v28" and selector_format == "roles-v26") else
                         MEDIUM_SETTINGS if profile in {"focused-v14", "focused-v27", "focused-v28"} or
                         (profile in {"focused-v29", "focused-v30"} and selector_format in {"roles-v29", "roles-v30"}) else LOW_SELECTOR_SETTINGS)
    selector = prepare_focused_selector(projection, config, evidence,
                                        selection_format=selector_format)
    first = FocusedComparisonPass.model_validate(_pass("selection", _request(selector, config,
        selector_settings, "selection", projection), config, selector_settings,
        writer, input_measurer, lambda raw: (
            decode_planned_selection(raw, selector.structured, projection,
                                     max_references=3, max_nonbenchmark_references=2)
            if profile in {"focused-v28", "focused-v29", "focused-v30"} else
            decode_planned_selection(raw, selector.structured, projection, max_references=4)
            if profile in {"focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27"} else
            (decode_planned_selection if profile in {"focused-v14", "focused-v15", "focused-v16"}
             else decode_selection_v2)(raw, selector.structured, projection)),
        projection=projection, prepared=selector).model_dump(mode="json"))
    passes = [first]
    focus: FocusedComparisonPreparedInput | None = None
    registry: TemporalComparisonRegistry | None = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        focus, registry = prepare_focused_v11_composer(first.selection, selector,
            projection, evidence, raw_selection_wire=first.raw_wire)
        second = _run_composition("composition", _composer_request(focus, config,
            "composition", composer_settings), config, composer_settings, writer,
            input_measurer, focus, projection, registry)
        passes.append(second)
        failures = tuple(f for f in second.findings if f.outcome == "failed")
        if second.outcome == "recoverable" and failures:
            assert second.raw_wire is not None
            passes.append(_run_composition("correction", _composer_request(focus,
                config, "correction", COMPOSER_SETTINGS, previous_wire=second.raw_wire,
                feedback=failures), config, COMPOSER_SETTINGS, writer,
                input_measurer, focus, projection, registry))
    selected, reason = _selected(passes)
    resolved, validation, delivery = _outcome(passes, selected, focus, evidence, registry)
    terminal = passes[-1]
    generation = "success" if selected is not None else terminal.outcome
    artifact = FocusedResultsArtifactV11(evidence=evidence, config=config,
        selector_settings=selector_settings, composer_settings=composer_settings,
        correction_settings=COMPOSER_SETTINGS,
        selector_prepared=selector, focus_prepared=focus,
        comparison_registry=registry, passes=tuple(passes), selected_pass_index=selected,
        selection_reason=cast(Literal["initial_only", "correction_fewer_failures",
                                      "correction_tie", "initial_fewer_failures",
                                      "no_recoverable_draft"], reason),
        generation_outcome=cast(Literal["success", "api_error", "generation_error",
                                        "context_limit", "measurement_error"], generation),
        validation_outcome=cast(Literal["clean", "annotated", "unavailable"], validation),
        delivery_outcome=cast(Literal["delivered", "not_delivered"], delivery),
        resolved=resolved,
        resolved_digest=content_digest(resolved.model_dump(mode="json")) if resolved else None,
        runtime_seconds=0)
    return artifact.model_copy(update={"runtime_seconds": time.perf_counter() - started})


def _replay_composition(item: FocusedComparisonPass, envelope: RequestEnvelope,
                        config: ResultsConfig, prepared: InteractivePreparedInput,
                        projection: SolutionProjection,
                        registry: TemporalComparisonRegistry) -> None:
    if (item.request != envelope.request or item.request_digest != content_digest(envelope.request)
            or item.input_bytes != envelope.input_bytes or
            item.estimated_total_tokens != envelope.estimated_total_tokens or
            item.prompt_digest != envelope.prompt_digest or item.schema_digest != envelope.schema_digest):
        raise ValueError("saved V11 pass request differs")
    count = item.input_token_receipt
    if count is not None and count.request_digest != item.request_digest:
        raise ValueError("saved V11 token count differs")
    within = _within(envelope, config, count)
    if item.returned_service_tier != _returned_tier(item.writer_receipt):
        raise ValueError("saved V11 response tier differs")
    if item.raw_wire is not None and _response_text(item.writer_receipt) != item.raw_wire:
        raise ValueError("saved V11 raw wire differs from response")
    if item.writer_called and not within:
        raise ValueError("saved V11 pass exceeded context")
    if not item.writer_called:
        if item.document is not None or item.selection is not None or item.raw_wire is not None or \
                item.writer_receipt is not None or item.findings:
            raise ValueError("saved V11 uncalled pass has generation evidence")
        if item.outcome == "context_limit" and not within and item.error == "context_limit":
            return
        if item.outcome == "measurement_error" and count is None and \
                item.error == "input_token_measurement_failed":
            return
        raise ValueError("saved V11 uncalled pass is invalid")
    if item.outcome == "recoverable":
        if item.raw_wire is None or item.error is not None or item.failure_subtype is not None:
            raise ValueError("saved V11 recoverable pass metadata differs")
        _validate_recoverable_response(item.writer_receipt)
        document = decode(item.raw_wire, prepared, projection)
        if item.document != document or item.findings != findings(document, projection,
                                                                   prepared, registry):
            raise ValueError("saved V11 document or findings differ from wire")
        return
    if item.document is not None or item.selection is not None or item.findings:
        raise ValueError("saved V11 failed pass has a document")
    _failure_consistency(item)
    if item.outcome == "api_error" and item.failure_subtype != "api_error":
        raise ValueError("saved V11 API failure subtype differs")
    if item.outcome == "generation_error" and item.failure_subtype not in {
            "refusal", "incomplete", "schema_error"}:
        raise ValueError("saved V11 generation subtype differs")
    if item.outcome not in {"api_error", "generation_error"}:
        raise ValueError("saved V11 called pass outcome differs")
    if item.failure_subtype == "schema_error" and item.raw_wire is not None:
        try:
            decode(item.raw_wire, prepared, projection)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
        else:
            raise ValueError("saved V11 schema failure decoded successfully")


def _failure_consistency(item: FocusedComparisonPass) -> None:
    """A writer-raised failure cannot carry a returned author wire document."""
    if item.outcome not in {"api_error", "generation_error"}:
        return
    if item.failure_subtype != "schema_error" and item.raw_wire is not None:
        raise ValueError("saved V11 writer failure has a returned raw wire")
    if item.writer_receipt is None or item.writer_receipt.raw_response is None:
        return
    try:
        response = json.loads(item.writer_receipt.raw_response)
    except (ValueError, TypeError) as exc:
        raise ValueError("saved V11 writer failure has invalid response evidence") from exc
    if not isinstance(response, dict):
        raise TypeError("saved V11 writer failure response is not an object")
    status = response.get("status")
    if item.writer_receipt.status is not None and item.writer_receipt.status != status:
        raise ValueError("saved V11 writer failure status differs from receipt")
    expected_subtype: str | None
    if status == "incomplete":
        expected_subtype = "incomplete"
    elif status == "failed":
        expected_subtype = "api_error"
    else:
        output = response.get("output")
        refusal = isinstance(output, list) and any(
            isinstance(message, dict) and message.get("type") == "message" and
            isinstance(message.get("content"), list) and any(
                isinstance(part, dict) and part.get("type") == "refusal"
                for part in message["content"]) for message in output)
        expected_subtype = ("refusal" if refusal else
                            "schema_error" if status != "completed" or
                            not _response_text(item.writer_receipt) else None)
    if expected_subtype is not None and item.failure_subtype != expected_subtype:
        raise ValueError("saved V11 writer failure subtype differs from response")
    if item.failure_subtype == "schema_error" and item.raw_wire is None and \
            status == "completed" and _response_text(item.writer_receipt):
        raise ValueError("saved V11 schema failure hides completed author wire")
    if item.failure_subtype == "api_error" and status != "failed":
        raise ValueError("saved V11 API failure response status differs")
    if item.failure_subtype == "incomplete" and status != "incomplete":
        raise ValueError("saved V11 incomplete response status differs")
    if item.failure_subtype == "refusal":
        output = response.get("output")
        if not isinstance(output, list) or not any(
                isinstance(message, dict) and message.get("type") == "message" and
                any(isinstance(part, dict) and part.get("type") == "refusal"
                    for part in message.get("content", [])) for message in output):
            raise ValueError("saved V11 refusal lacks refusal content")


def replay_focused_v11(artifact: FocusedResultsArtifactV11) -> ResolvedFocusedComparisonAnswer | None:
    marker = artifact.selector_prepared.packet.get("selection_format")
    if marker not in {"roles-v10", "roles-v11", "roles-v12", "roles-v13", "roles-v14", "roles-v15", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"}:
        raise ValueError("saved V11 profile marker differs")
    composer_settings = COMPOSER_SETTINGS if marker in {"roles-v11", "roles-v21", "roles-v22", "roles-v27", "roles-v29", "roles-v30"} else MEDIUM_SETTINGS
    selector_settings = (SELECTOR_SETTINGS if marker in {"roles-v21", "roles-v22", "roles-v23"} else
                         MEDIUM_SETTINGS if marker in {"roles-v13", "roles-v25", "roles-v27", "roles-v29", "roles-v30"} else
                         SELECTOR_SETTINGS if marker == "roles-v26" else LOW_SELECTOR_SETTINGS)
    if artifact.config.model != "gpt-6-luna" or artifact.selector_settings != selector_settings or \
            artifact.composer_settings != composer_settings or \
            artifact.correction_settings != COMPOSER_SETTINGS:
        raise ValueError("saved V11 model settings differ")
    projection = SolutionProjection.model_validate(artifact.evidence.source.model_dump(mode="json"))
    if marker in {"roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v27", "roles-v29", "roles-v30"} and any(item.status in {"admitted", "conditional"}
                                    for item in projection.view.alternatives):
        raise ValueError("saved V24 incomplete selector has a complete journey source")
    if marker in {"roles-v26", "roles-v28"} and not any(item.status in {"admitted", "conditional"}
                                           for item in projection.view.alternatives):
        raise ValueError("saved V28 complete selector lacks a complete journey source")
    evidence = resolve_workspace(projection, fx_acquisition=artifact.evidence.fx_acquisition)
    if artifact.evidence != evidence:
        raise ValueError("saved V11 workspace differs from source")
    verify_authoring_view(projection, prepare_results(projection, artifact.config))
    selector = prepare_focused_selector(projection, artifact.config, evidence,
                                        selection_format=marker)
    if artifact.selector_prepared != selector:
        raise ValueError("saved V11 selector differs")
    passes = list(artifact.passes)
    if not 1 <= len(passes) <= 3 or [p.phase for p in passes] != [
            "selection", "composition", "correction"][:len(passes)]:
        raise ValueError("saved V11 pass sequence differs")
    first = passes[0]
    _failure_consistency(first)
    _replay_pass(FocusedPass.model_validate(first.model_dump(mode="json")),
        _request(selector, artifact.config, selector_settings,
        "selection", projection), artifact.config,
        lambda raw: (decode_planned_selection(raw, selector.structured, projection,
                      max_references=3, max_nonbenchmark_references=2)
                     if marker in {"roles-v26", "roles-v27", "roles-v28", "roles-v29", "roles-v30"} else
                     decode_planned_selection(raw, selector.structured, projection,
                      max_references=4) if marker in {"roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25"} else
                     (decode_planned_selection if marker in {"roles-v13", "roles-v14", "roles-v15"} else
                      decode_selection_v2)(raw, selector.structured, projection)),
        projection, selector)
    focus = None
    registry = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        focus, registry = prepare_focused_v11_composer(first.selection, selector,
            projection, evidence, raw_selection_wire=first.raw_wire)
        expected_format = ("complete-v28" if marker == "roles-v30" else
                           "complete-v27" if marker == "roles-v29" else
                           "complete-v26" if marker == "roles-v28" else
                           "complete-v25" if marker == "roles-v27" else
                           "complete-v24" if marker == "roles-v26" else
                           "complete-v23" if marker == "roles-v25" else
                           "complete-v22" if marker == "roles-v24" else
                           "complete-v21" if marker == "roles-v23" else
                           "complete-v20" if marker == "roles-v22" else
                           "complete-v19" if marker == "roles-v21" else
                           "complete-v13" if marker == "roles-v15" else
                           "complete-v12" if marker == "roles-v14" else
                           "complete-v11" if marker == "roles-v13" else
                           "complete-v10" if marker == "roles-v12" else
                           "complete-v9" if marker == "roles-v11" else "complete-v8")
        if focus.packet.get("composition_format") != expected_format:
            raise ValueError("saved V11 composer profile marker differs")
        if len(passes) < 2:
            raise ValueError("saved V11 composition is missing")
        second = passes[1]
        _replay_composition(second, _composer_request(focus, artifact.config,
            "composition", composer_settings), artifact.config, focus, projection, registry)
        failures = tuple(f for f in second.findings if f.outcome == "failed")
        if len(passes) == 3:
            if second.outcome != "recoverable" or not failures or second.raw_wire is None:
                raise ValueError("saved V11 correction lacks failed draft")
            _replay_composition(passes[2], _composer_request(focus, artifact.config,
                "correction", COMPOSER_SETTINGS, previous_wire=second.raw_wire,
                feedback=failures),
                artifact.config, focus, projection, registry)
        elif second.outcome == "recoverable" and failures:
            raise ValueError("saved V11 correction is missing")
    elif len(passes) != 1:
        raise ValueError("saved V11 composition ran after failed selection")
    if artifact.focus_prepared != focus or artifact.comparison_registry != registry:
        raise ValueError("saved V11 source packet or comparison registry differs")
    if registry is not None and first.selection is not None and focus is not None:
        validate_temporal_registry(registry, evidence, first.selection.journey_ids,
                                   _aliases(focus, first.selection))
    selected, reason = _selected(passes)
    if artifact.selected_pass_index != selected or artifact.selection_reason != reason:
        raise ValueError("saved V11 selected draft differs")
    resolved, validation, delivery = _outcome(passes, selected, focus, evidence, registry)
    generation = "success" if selected is not None else passes[-1].outcome
    if (artifact.generation_outcome != generation or artifact.validation_outcome != validation or
            artifact.delivery_outcome != delivery or artifact.resolved != resolved or
            artifact.resolved_digest != (content_digest(resolved.model_dump(mode="json"))
                                         if resolved else None)):
        raise ValueError("saved V11 outcome differs")
    return resolved
