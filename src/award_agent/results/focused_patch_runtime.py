"""V17 low draft and bounded medium editorial patch over frozen Results facts."""

from __future__ import annotations

import json
import time
from typing import Literal, cast

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection

from .authoring import verify_authoring_view
from .comparison_registry import validate_temporal_registry
from .contracts import (
    InputTokenReceipt,
    ResultsConfig,
    ResultsInputMeasurer,
    ResultsWriterError,
    WriterReceipt,
)
from .core import prepare_results
from .currency import FxAcquisition
from .focused import (
    SELECTOR_SETTINGS,
    _pass,
    _receipt,
    _replay_pass,
    _request,
    _within,
    prepare_focused_selector,
)
from .focused_comparison_contracts import (
    FocusedComparisonPass,
    FocusedComparisonPreparedInput,
    ResolvedFocusedComparisonAnswer,
    TemporalComparisonRegistry,
)
from .focused_comparison_runtime import (
    _aliases,
    _composer_request,
    _failure_consistency,
    _replay_composition,
    _run_composition,
    prepare_focused_v11_composer,
)
from .focused_comparison_wire import decode, findings, resolve_focused_comparison_document
from .focused_contracts import FocusedPass
from .focused_patch import apply_patch, decode_patch, patch_schema
from .focused_patch_contracts import FocusedPatchPass, FocusedResultsArtifactV12
from .focused_records import writer_packet
from .focused_selection_plan import decode as decode_planned_selection
from .focused_v4 import LOW_SELECTOR_SETTINGS, MEDIUM_SETTINGS
from .focused_wire import alias_for_canonical
from .interactive import _response_text, _returned_tier, _validate_recoverable_response
from .interactive_contracts import InteractiveSettings, InteractiveWriter
from .presentation import resolve_workspace
from .runner import RequestEnvelope
from .workspace_contracts import WorkspaceEvidence

_LOW = InteractiveSettings(reasoning_effort="low", service_tier="fast")


def _editor_request(prepared: FocusedComparisonPreparedInput, config: ResultsConfig,
                    draft: FocusedComparisonPass, settings: InteractiveSettings) -> RequestEnvelope:
    if draft.raw_wire is None or draft.document is None:
        raise ValueError("editorial revision requires a recoverable complete draft")
    original = json.loads(draft.raw_wire)
    if not isinstance(original, dict) or not isinstance(original.get("blocks"), list):
        raise TypeError("editorial draft wire is malformed")
    guide = (
        "Edit the complete traveler answer using the SAME frozen source records, editorial plan, "
        "and temporal comparison registry. The plan is unverified; every factual or comparative "
        "claim must agree with the exact referenced authoring record. Check the opening against "
        "the body and every visible option; remove false earliest, lowest, cabin, fee, traveler, "
        "or scope claims. Preserve supported gains and real downsides, improve weak comparison "
        "reasoning, and keep applicable shared limits. Numerical prose is allowed when accurate. "
        "The numbered draft contains original block positions. Return ONLY {edits:[{start,end,blocks}]} "
        "where each edit replaces original blocks in [start,end) with complete valid wire blocks. "
        "Use sorted, distinct, nonoverlapping original positions; start=end inserts, blocks=[] deletes, "
        "[0,N) may rewrite all. Prefer local edits. Empty edits mean no change, not a verified approval. "
        "Do not return a score, review prose, clean bill of health, or a full document wrapper. "
        "The supplied feedback contains only actual mechanical findings and may be empty."
    )
    v19 = prepared.packet.get("composition_format") == "complete-v16"
    v20 = prepared.packet.get("composition_format") in {"complete-v17", "complete-v18", "complete-v19"}
    v18 = prepared.packet.get("composition_format") in {"complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19"}
    if v19 or v20:
        guide = (
            "Repair factual errors and answer coherence against the SAME frozen source records "
            "and comparison_pairs. The editorial_plan contains identities and comparison targets "
            "only, never source facts or a mandate to recommend every selected record. "
            "Recheck each sentence against the exact referenced option, including program, cabin, "
            "carriers, connection wait, time metric and original quote scope. A temporal card "
            "supports only its exact pair and metric, not surrounding prose. Remove unsupported "
            "claims and contradictions; keep useful supported tradeoffs and applicable limits. "
            "You may delete a weak or redundant option, but also repair or delete dependent "
            "comparison cards. Do not invent a benefit for every alternative. "
            "The previous_wire.blocks entries each carry an original index and one original block. "
            "Return ONLY {edits:[{start,end,blocks}]}: each edit must have end=start+1 and "
            "blocks containing zero or one complete replacement block. No insertion, multi-block "
            "replacement or multi-block range is allowed. Use original positions in sorted order. "
            "Empty edits mean no change, not factual approval. Keep internal J/A/C/T/JP/CP aliases "
            "out of traveler prose and labels; keep them only in wire reference fields. "
            "Feedback lists actual failed mechanical findings and may be empty."
        )
        if v20:
            guide += (
                " The requested traveler count is known from the request; use each selected "
                "journey's traveler_evidence to identify award versus cash component support "
                "that remains unverified. Missing returned travelers is not a failed seat "
                "check, and cash echo does not verify award support. Repair a missing central "
                "decision reason when the exact source supports one, especially a conditional "
                "next-check preference among incomplete leads by date, program, or comparable "
                "original quote. Do not invent program access, balances, total savings, or a "
                "benefit from surplus seats above the requested party. Preserve factual repair "
                "priority; one existing paragraph may be rewritten as one block."
            )
    elif v18:
        guide += (
            " Never print internal J/A/C/T/JP/CP identifiers in traveler-facing prose "
            "or labels. Reuse natural traveler labels to name visible choices and "
            "comparisons. Keep exact source identifiers only in the wire r fields. "
            " For each alternative, explain why a traveler might choose it over "
            "the lead and what they give up. Do not merely say it is later, "
            "longer or worse. Ground each gain and loss in that option's exact "
            "record and frame any preference conditionally; do not invent the "
            "traveler's balance or preferences. If no meaningful supported "
            "benefit exists, reject the weak editorial intent, use another "
            "selected option, or omit it while keeping a coherent complete "
            "answer and valid comparison endpoints. Prefer repairing explanations "
            "to unnecessary reference or card removal; reconcile dependent "
            "comparison cards whenever referenced journeys change. "
            "The previous_wire.blocks entries each carry an original index and "
            "one original block; patch start/end positions refer to those indexes."
        )
    if config.authoring_guidance and config.authoring_guidance.strip():
        guide += "\n" + config.authoring_guidance
    feedback: list[dict[str, object]] = []
    for finding in draft.findings:
        if finding.outcome != "failed":
            continue
        row = finding.model_dump(mode="json")
        if finding.reference_id is not None:
            row["reference_id"] = (alias_for_canonical(prepared, finding.reference_id) or
                                   finding.reference_id)
        feedback.append(row)
    input_data = {
        "packet": writer_packet(prepared),
        "previous_wire": ({"blocks": [{"index": index, "block": block}
                              for index, block in enumerate(original["blocks"])]}
                          if v18 else original),
        "draft_digest": content_digest(draft.raw_wire),
        "feedback": feedback,
        "revision_trigger": "editorial_revision",
    }
    if not v18:
        input_data["numbered_draft"] = [{"index": index, "block": block}
                                        for index, block in enumerate(original["blocks"])]
    payload = json.dumps(input_data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    shape = patch_schema(prepared)
    shape_text = json.dumps(shape, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    prompt = guide + payload
    size = len(prompt.encode()) + len(shape_text.encode())
    request: dict[str, object] = {
        "model": config.model, "reasoning": {"effort": settings.reasoning_effort},
        "instructions": guide, "input": payload,
        "text": {"format": {"type": "json_schema", "name": "FocusedResultsEditorialPatch",
                            "strict": True, "schema": shape}},
    }
    return RequestEnvelope(request, size, size + config.prompt_overhead_tokens +
                           config.max_output_tokens, content_digest(prompt), content_digest(shape_text))


def _editor_pass(envelope: RequestEnvelope, config: ResultsConfig, writer: InteractiveWriter,
                 measurer: ResultsInputMeasurer | None, prepared: FocusedComparisonPreparedInput,
                 projection: SolutionProjection, registry: TemporalComparisonRegistry,
                 draft: FocusedComparisonPass, settings: InteractiveSettings) -> FocusedPatchPass:
    assert draft.raw_wire is not None
    common: dict[str, object] = {
        "request": envelope.request, "request_digest": content_digest(envelope.request),
        "input_bytes": envelope.input_bytes,
        "estimated_total_tokens": envelope.estimated_total_tokens,
        "prompt_digest": envelope.prompt_digest, "schema_digest": envelope.schema_digest,
        "draft_digest": content_digest(draft.raw_wire),
    }
    count: InputTokenReceipt | None = None
    if measurer is not None:
        try:
            measured = measurer.measure(envelope.request, config)
            count = InputTokenReceipt.model_validate(measured.model_dump(mode="json"))
            if count.request_digest != common["request_digest"]:
                raise ValueError("editorial token receipt request digest differs")
        except (AttributeError, ResultsWriterError, ValueError, TypeError):
            return FocusedPatchPass.model_validate({**common, "outcome": "measurement_error",
                "writer_called": False, "error": "input_token_measurement_failed"})
    if not _within(envelope, config, count):
        return FocusedPatchPass.model_validate({**common, "outcome": "context_limit",
            "writer_called": False, "input_token_receipt": count, "error": "context_limit"})
    raw: str | None = None
    try:
        raw = writer.author(envelope.request, config, settings)
        atomic = prepared.packet.get("composition_format") in {"complete-v16", "complete-v17", "complete-v18", "complete-v19"}
        patch = decode_patch(raw, atomic=atomic)
        complete = apply_patch(draft.raw_wire, patch, atomic=atomic)
        document = decode(complete, prepared, projection)
        receipt = _receipt(writer)
        checks = findings(document, projection, prepared, registry)
        return FocusedPatchPass.model_validate({**common, "outcome": "recoverable",
            "writer_called": True, "input_token_receipt": count, "writer_receipt": receipt,
            "returned_service_tier": _returned_tier(receipt), "raw_patch": raw,
            "patch": patch, "materialized_wire": complete,
            "materialized_digest": content_digest(complete), "document": document,
            "findings": checks})
    except ResultsWriterError as exc:
        receipt = _receipt(writer) or WriterReceipt(raw_response=exc.raw_response)
        return FocusedPatchPass.model_validate({**common,
            "outcome": "api_error" if exc.outcome == "api_error" else "generation_error",
            "writer_called": True, "input_token_receipt": count, "writer_receipt": receipt,
            "returned_service_tier": _returned_tier(receipt), "raw_patch": raw,
            "error": str(exc), "failure_subtype": exc.outcome})
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        receipt = _receipt(writer)
        return FocusedPatchPass.model_validate({**common, "outcome": "generation_error",
            "writer_called": True, "input_token_receipt": count, "writer_receipt": receipt,
            "returned_service_tier": _returned_tier(receipt), "raw_patch": raw,
            "error": f"schema_error: {exc}", "failure_subtype": "schema_error"})


def _choice(passes: list[FocusedComparisonPass | FocusedPatchPass]) -> tuple[int | None, str]:
    if len(passes) < 2 or passes[1].outcome != "recoverable":
        return None, "no_recoverable_draft"
    if len(passes) != 3 or passes[2].outcome != "recoverable":
        return 1, "revision_unrecoverable"
    initial = sum(f.outcome == "failed" for f in passes[1].findings)
    revised = sum(f.outcome == "failed" for f in passes[2].findings)
    if revised < initial:
        return 2, "revision_fewer_failures"
    if revised == initial:
        return 2, "revision_tie"
    return 1, "initial_fewer_failures"


def _deliver(passes: list[FocusedComparisonPass | FocusedPatchPass], index: int | None,
             focus: FocusedComparisonPreparedInput | None, registry: TemporalComparisonRegistry | None,
             evidence: WorkspaceEvidence) -> tuple[ResolvedFocusedComparisonAnswer | None, str, str]:
    if index is None:
        return None, "unavailable", "not_delivered"
    assert focus is not None and registry is not None
    document = passes[index].document
    assert document is not None
    resolved = resolve_focused_comparison_document(document, focus, evidence, registry,
                                                    passes[index].findings)
    validation = "annotated" if any(f.outcome == "failed" for f in passes[index].findings) else "clean"
    return resolved, validation, "delivered"


def run_focused_v17(projection: SolutionProjection, config: ResultsConfig,
                    writer: InteractiveWriter, input_measurer: ResultsInputMeasurer | None = None,
                    *, fx_acquisition: FxAcquisition | None = None,
                    profile: Literal["focused-v17", "focused-v18", "focused-v19", "focused-v20", "focused-v21", "focused-v22"] = "focused-v17",
                    ) -> FocusedResultsArtifactV12:
    started = time.perf_counter()
    if config.model != "gpt-6-luna":
        raise ValueError("focused-v17 requires explicit gpt-6-luna")
    evidence = resolve_workspace(projection, fx_acquisition=fx_acquisition)
    if profile not in {"focused-v17", "focused-v18", "focused-v19", "focused-v20", "focused-v21", "focused-v22"}:
        raise ValueError("unknown focused patch profile")
    selector_format: Literal["roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21"] = (
        "roles-v21" if profile == "focused-v22" else
        "roles-v20" if profile == "focused-v21" else
        "roles-v19" if profile == "focused-v20" else
        "roles-v18" if profile == "focused-v19" else
        "roles-v17" if profile == "focused-v18" else "roles-v16")
    editor_settings = MEDIUM_SETTINGS if profile in {"focused-v17", "focused-v21", "focused-v22"} else _LOW
    selector_settings = SELECTOR_SETTINGS if profile in {"focused-v21", "focused-v22"} else LOW_SELECTOR_SETTINGS
    selector = prepare_focused_selector(projection, config, evidence,
                                        selection_format=selector_format)
    first = FocusedComparisonPass.model_validate(_pass("selection", _request(selector, config,
        selector_settings, "selection", projection), config, selector_settings,
        writer, input_measurer, lambda raw: decode_planned_selection(raw, selector.structured,
        projection, max_references=4 if profile == "focused-v22" else 8),
        projection=projection, prepared=selector).model_dump(mode="json"))
    passes: list[FocusedComparisonPass | FocusedPatchPass] = [first]
    focus: FocusedComparisonPreparedInput | None = None
    registry: TemporalComparisonRegistry | None = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        focus, registry = prepare_focused_v11_composer(first.selection, selector,
            projection, evidence, raw_selection_wire=first.raw_wire)
        second = _run_composition("composition", _composer_request(focus, config,
            "composition", _LOW), config, _LOW, writer, input_measurer,
            focus, projection, registry)
        passes.append(second)
        if second.outcome == "recoverable":
            passes.append(_editor_pass(_editor_request(focus, config, second,
                editor_settings), config, writer, input_measurer, focus, projection,
                registry, second, editor_settings))
    selected, reason = _choice(passes)
    resolved, validation, delivery = _deliver(passes, selected, focus, registry, evidence)
    generation = "success" if selected is not None else passes[-1].outcome
    artifact = FocusedResultsArtifactV12(evidence=evidence, config=config,
        selector_settings=selector_settings, composer_settings=_LOW,
        revision_settings=editor_settings,
        revision_trigger="editorial_revision" if len(passes) == 3 else None,
        selector_prepared=selector, focus_prepared=focus, comparison_registry=registry,
        passes=tuple(passes), selected_pass_index=selected,
        selection_reason=cast(Literal["revision_fewer_failures", "revision_tie",
            "initial_fewer_failures", "revision_unrecoverable", "no_recoverable_draft"], reason),
        generation_outcome=cast(Literal["success", "api_error", "generation_error",
            "context_limit", "measurement_error"], generation),
        validation_outcome=cast(Literal["clean", "annotated", "unavailable"], validation),
        delivery_outcome=cast(Literal["delivered", "not_delivered"], delivery),
        resolved=resolved,
        resolved_digest=content_digest(resolved.model_dump(mode="json")) if resolved else None,
        runtime_seconds=0)
    return artifact.model_copy(update={"runtime_seconds": time.perf_counter() - started})


def _replay_editor(item: FocusedPatchPass, envelope: RequestEnvelope, config: ResultsConfig,
                   focus: FocusedComparisonPreparedInput, projection: SolutionProjection,
                   registry: TemporalComparisonRegistry, draft: FocusedComparisonPass) -> None:
    assert draft.raw_wire is not None
    if (item.request != envelope.request or item.request_digest != content_digest(envelope.request)
            or item.input_bytes != envelope.input_bytes or
            item.estimated_total_tokens != envelope.estimated_total_tokens or
            item.prompt_digest != envelope.prompt_digest or item.schema_digest != envelope.schema_digest or
            item.draft_digest != content_digest(draft.raw_wire)):
        raise ValueError("saved V17 editor request or draft binding differs")
    count = item.input_token_receipt
    if count is not None and count.request_digest != item.request_digest:
        raise ValueError("saved V17 editor token count differs")
    within = _within(envelope, config, count)
    if item.returned_service_tier != _returned_tier(item.writer_receipt):
        raise ValueError("saved V17 editor response tier differs")
    if item.raw_patch is not None and _response_text(item.writer_receipt) != item.raw_patch:
        raise ValueError("saved V17 raw patch differs from response")
    if item.writer_called and not within:
        raise ValueError("saved V17 editor exceeded context")
    if not item.writer_called:
        if item.raw_patch is not None or item.writer_receipt is not None:
            raise ValueError("saved V17 uncalled editor has generation evidence")
        if item.outcome == "context_limit" and not within and item.error == "context_limit":
            return
        if item.outcome == "measurement_error" and count is None and \
                item.error == "input_token_measurement_failed":
            return
        raise ValueError("saved V17 uncalled editor outcome differs")
    if item.outcome == "recoverable":
        if item.raw_patch is None or item.patch is None or item.materialized_wire is None:
            raise ValueError("saved V17 recoverable editor lacks patch")
        _validate_recoverable_response(item.writer_receipt)
        atomic = focus.packet.get("composition_format") in {"complete-v16", "complete-v17", "complete-v18", "complete-v19"}
        patch = decode_patch(item.raw_patch, atomic=atomic)
        complete = apply_patch(draft.raw_wire, patch, atomic=atomic)
        document = decode(complete, focus, projection)
        if (item.patch != patch or item.materialized_wire != complete or
                item.materialized_digest != content_digest(complete) or
                item.document != document or item.findings != findings(document, projection,
                                                                      focus, registry)):
            raise ValueError("saved V17 materialized answer or findings differ")
        return
    if item.outcome not in {"api_error", "generation_error"}:
        raise ValueError("saved V17 called editor outcome differs")
    if item.outcome == "api_error" and item.failure_subtype != "api_error":
        raise ValueError("saved V17 API failure subtype differs")
    if item.outcome == "generation_error" and item.failure_subtype not in {
            "refusal", "incomplete", "schema_error"}:
        raise ValueError("saved V17 generation failure subtype differs")
    old_shape = item.model_dump(mode="json", exclude={"draft_digest", "raw_patch", "patch",
        "materialized_wire", "materialized_digest"})
    old_shape.update({"phase": "correction", "raw_wire": item.raw_patch})
    _failure_consistency(FocusedComparisonPass.model_validate(old_shape))
    if item.failure_subtype == "schema_error" and item.raw_patch is not None:
        try:
            atomic = focus.packet.get("composition_format") in {"complete-v16", "complete-v17", "complete-v18", "complete-v19"}
            patch = decode_patch(item.raw_patch, atomic=atomic)
            complete = apply_patch(draft.raw_wire, patch, atomic=atomic)
            decode(complete, focus, projection)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
        else:
            raise ValueError("saved V17 schema failure decoded successfully")


def replay_focused_v17(artifact: FocusedResultsArtifactV12) -> ResolvedFocusedComparisonAnswer | None:
    marker = artifact.selector_prepared.packet.get("selection_format")
    if marker not in {"roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21"}:
        raise ValueError("saved patch profile marker differs")
    editor_settings = MEDIUM_SETTINGS if marker in {"roles-v16", "roles-v20", "roles-v21"} else _LOW
    selector_settings = SELECTOR_SETTINGS if marker in {"roles-v20", "roles-v21"} else LOW_SELECTOR_SETTINGS
    if (artifact.config.model != "gpt-6-luna" or
            artifact.selector_settings != selector_settings or
            artifact.composer_settings != _LOW or artifact.revision_settings != editor_settings):
        raise ValueError("saved V17 profile marker or settings differ")
    projection = SolutionProjection.model_validate(artifact.evidence.source.model_dump(mode="json"))
    evidence = resolve_workspace(projection, fx_acquisition=artifact.evidence.fx_acquisition)
    if artifact.evidence != evidence:
        raise ValueError("saved V17 workspace differs from source")
    verify_authoring_view(projection, prepare_results(projection, artifact.config))
    selector = prepare_focused_selector(projection, artifact.config, evidence,
                                        selection_format=marker)
    if artifact.selector_prepared != selector:
        raise ValueError("saved V17 selector differs")
    passes = list(artifact.passes)
    first = passes[0]
    if not isinstance(first, FocusedComparisonPass):
        raise TypeError("saved V17 selection pass has wrong contract")
    _failure_consistency(first)
    _replay_pass(FocusedPass.model_validate(first.model_dump(mode="json")),
        _request(selector, artifact.config, selector_settings, "selection", projection),
        artifact.config, lambda raw: decode_planned_selection(raw, selector.structured,
        projection, max_references=4 if marker == "roles-v21" else 8),
        projection, selector)
    focus: FocusedComparisonPreparedInput | None = None
    registry: TemporalComparisonRegistry | None = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        focus, registry = prepare_focused_v11_composer(first.selection, selector,
            projection, evidence, raw_selection_wire=first.raw_wire)
        expected_format = ("complete-v19" if marker == "roles-v21" else
                           "complete-v18" if marker == "roles-v20" else
                           "complete-v17" if marker == "roles-v19" else
                           "complete-v16" if marker == "roles-v18" else
                           "complete-v15" if marker == "roles-v17" else "complete-v14")
        if focus.packet.get("composition_format") != expected_format or len(passes) < 2:
            raise ValueError("saved V17 composer marker or pass differs")
        second = passes[1]
        if not isinstance(second, FocusedComparisonPass):
            raise ValueError("saved V17 draft pass has wrong contract")
        _replay_composition(second, _composer_request(focus, artifact.config,
            "composition", _LOW), artifact.config, focus, projection, registry)
        if second.outcome == "recoverable":
            if len(passes) != 3 or not isinstance(passes[2], FocusedPatchPass):
                raise ValueError("saved V17 mandatory editorial pass is missing")
            _replay_editor(passes[2], _editor_request(focus, artifact.config, second,
                editor_settings),
                           artifact.config, focus, projection, registry, second)
        elif len(passes) != 2:
            raise ValueError("saved V17 editor ran after failed draft")
        validate_temporal_registry(registry, evidence, first.selection.journey_ids,
                                   _aliases(focus, first.selection))
    elif len(passes) != 1:
        raise ValueError("saved V17 draft ran after failed selection")
    if artifact.focus_prepared != focus or artifact.comparison_registry != registry:
        raise ValueError("saved V17 authoring source differs")
    selected, reason = _choice(passes)
    if artifact.selected_pass_index != selected or artifact.selection_reason != reason:
        raise ValueError("saved V17 selected draft differs")
    resolved, validation, delivery = _deliver(passes, selected, focus, registry, evidence)
    generation = "success" if selected is not None else passes[-1].outcome
    if (artifact.generation_outcome != generation or artifact.validation_outcome != validation or
            artifact.delivery_outcome != delivery or artifact.resolved != resolved or
            artifact.resolved_digest != (content_digest(resolved.model_dump(mode="json"))
                                         if resolved else None)):
        raise ValueError("saved V17 outcome differs")
    return resolved
