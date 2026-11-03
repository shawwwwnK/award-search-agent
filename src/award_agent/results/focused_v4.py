"""Versioned focused Results with an optional source-check correction."""

from __future__ import annotations

import re
import time
from typing import Any, Literal, cast

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection

from .authoring import verify_authoring_view
from .contracts import CheckFinding, ResultsConfig, ResultsInputMeasurer
from .core import prepare_results
from .currency import FxAcquisition
from .focused import (
    COMPOSER_SETTINGS,
    SELECTOR_SETTINGS,
    _pass,
    _replay_pass,
    _request,
    prepare_focused_composer,
    prepare_focused_selector,
)
from .focused_contracts import FocusedPass, FocusedResultsArtifactV9
from .focused_packet import decode_selection_v2
from .focused_wire import decode as decode_focused_wire
from .interactive_contracts import InteractivePreparedInput, InteractiveSettings, InteractiveWriter
from .presentation import resolve_workspace
from .runner import choose_recoverable
from .structured import check_structured_document, resolve_structured_document
from .structured_contracts import ResolvedStructuredAnswer, StructuredDocument
from .workspace_contracts import WorkspaceEvidence

LOW_SELECTOR_SETTINGS = InteractiveSettings(reasoning_effort="low", service_tier="fast")
MEDIUM_SETTINGS = InteractiveSettings(reasoning_effort="medium", service_tier="fast")


def _findings(document: StructuredDocument, projection: SolutionProjection,
              prepared: InteractivePreparedInput) -> tuple[CheckFinding, ...]:
    findings = list(check_structured_document(document, projection, prepared.structured))
    alias_registry = cast(dict[str, str], prepared.packet["wire_aliases"])
    old_aliases = set(alias_registry.values())
    aliases = {item for item in old_aliases if re.fullmatch(r"[JAC]\d+", item)}
    alias_pattern = (re.compile(r"(?<!\w)(?:" + "|".join(
        re.escape(item) for item in sorted(aliases, key=len, reverse=True)) + r")(?!\w)")
        if aliases else None)
    selection_scope = cast(dict[str, Any], prepared.packet["selection_scope"])
    if selection_scope["journey_count"] and not document.selection.journey_ids:
        findings.append(CheckFinding(code="missing_complete_recommendation", outcome="failed",
            scope="shared", message="Show at least one complete eligible recommendation."))
    if selection_scope["benchmark_selected"] and document.selection.benchmark_observation_id is None:
        findings.append(CheckFinding(code="missing_cash_context", outcome="failed",
            scope="shared", message="Include the selected direct cash benchmark as context."))
    if not selection_scope["journey_count"] and selection_scope["lead_count"] and not \
            document.selection.incomplete_observation_ids:
        findings.append(CheckFinding(code="missing_incomplete_lead", outcome="failed",
            scope="shared", message="Explain at least one selected partial lead and its gap."))
    for index, block in enumerate(document.blocks):
        scope: Literal["shared", "journey", "benchmark", "incomplete"] = (
            "shared" if block.kind == "narrative" else
            "journey" if block.reference_kind == "journey" else
            "benchmark" if block.reference_kind == "benchmark" else "incomplete")
        if not block.text.strip() or (block.kind == "reference" and
                                      not (block.label or "").strip()):
            findings.append(CheckFinding(code="empty_explanation", outcome="failed",
                scope=scope, reference_id=block.reference_id, part_index=index,
                message="Every visible block needs a useful nonempty explanation and label."))
        visible = block.text + " " + (block.label or "")
        if alias_pattern is not None and alias_pattern.search(visible):
            findings.append(CheckFinding(code="visible_internal_alias", outcome="failed",
                scope=scope, reference_id=block.reference_id, part_index=index,
                message="Remove internal J/A/C identifiers from traveler prose and labels."))
    return tuple(findings)


def _chosen(passes: list[FocusedPass]) -> tuple[int | None, str]:
    recoverable = tuple((index, item.findings) for index, item in enumerate(passes)
                        if index >= 1 and item.outcome == "recoverable" and
                        item.document is not None)
    if not recoverable:
        return None, "no_recoverable_draft"
    relative, reason = choose_recoverable(tuple(
        (index - 1, findings) for index, findings in recoverable))
    return relative + 1, reason


def _outcome(passes: list[FocusedPass], chosen: int | None, evidence: WorkspaceEvidence,
             focus: InteractivePreparedInput | None,
             ) -> tuple[ResolvedStructuredAnswer | None, str, str]:
    if chosen is None:
        return None, "unavailable", "not_delivered"
    assert focus is not None
    document = passes[chosen].document
    assert document is not None
    resolved = resolve_structured_document(document,
                                           focus.structured, evidence,
                                           passes[chosen].findings)
    validation = ("annotated" if any(f.outcome == "failed" for f in
                                     passes[chosen].findings) else "clean")
    return resolved, validation, "delivered"


def run_focused_v4(projection: SolutionProjection, config: ResultsConfig,
                   writer: InteractiveWriter,
                   input_measurer: ResultsInputMeasurer | None = None, *,
                   fx_acquisition: FxAcquisition | None = None,
                   profile: Literal["focused-v4", "focused-v5", "focused-v6", "focused-v7"] = "focused-v4",
                   ) -> FocusedResultsArtifactV9:
    started = time.perf_counter()
    if config.model != "gpt-6-luna":
        raise ValueError("focused-v4 requires explicit gpt-6-luna")
    evidence = resolve_workspace(projection, fx_acquisition=fx_acquisition)
    selector_format: Literal["roles-v3", "roles-v4", "roles-v5", "roles-v6"] = (
        "roles-v6" if profile == "focused-v7" else
        "roles-v5" if profile == "focused-v6" else
        "roles-v4" if profile == "focused-v5" else "roles-v3")
    composition_format: Literal["complete-v1", "complete-v2", "complete-v3", "complete-v4"] = (
        "complete-v4" if profile == "focused-v7" else
        "complete-v3" if profile == "focused-v6" else
        "complete-v2" if profile == "focused-v5" else "complete-v1")
    selector_settings = (MEDIUM_SETTINGS if profile == "focused-v6" else
                         LOW_SELECTOR_SETTINGS if profile in {"focused-v5", "focused-v7"} else
                         SELECTOR_SETTINGS)
    composer_settings = (MEDIUM_SETTINGS if profile in {"focused-v6", "focused-v7"}
                         else COMPOSER_SETTINGS)
    selector = prepare_focused_selector(projection, config, evidence,
                                        selection_format=selector_format)
    decode_selector = lambda raw: decode_selection_v2(raw, selector.structured, projection)
    first = _pass("selection", _request(selector, config, selector_settings,
                   "selection", projection), config, selector_settings, writer,
                  input_measurer, decode_selector, projection=projection,
                  prepared=selector)
    passes = [first]
    focus = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        focus = prepare_focused_composer(first.selection, selector, projection, evidence,
                                          composition_format=composition_format)
        second = _pass("composition", _request(focus, config, composer_settings,
                       "composition", projection), config, composer_settings, writer,
                       input_measurer, lambda raw: decode_focused_wire(raw, focus, projection),
                       projection=projection, prepared=focus, checker=_findings)
        passes.append(second)
        failures = tuple(f for f in second.findings if f.outcome == "failed")
        if second.outcome == "recoverable" and failures:
            assert second.raw_wire is not None
            correction = _pass("correction", _request(focus, config, composer_settings,
                "correction", projection, feedback=failures,
                previous_wire=second.raw_wire), config, composer_settings, writer,
                input_measurer, lambda raw: decode_focused_wire(raw, focus, projection),
                projection=projection, prepared=focus, checker=_findings)
            passes.append(correction)
    selected, reason = _chosen(passes)
    resolved, validation, delivery = _outcome(passes, selected, evidence, focus)
    terminal = passes[-1]
    generation = "success" if selected is not None else terminal.outcome
    artifact = FocusedResultsArtifactV9(evidence=evidence, config=config,
        selector_settings=selector_settings, composer_settings=composer_settings,
        selector_prepared=selector, focus_prepared=focus, passes=tuple(passes),
        selected_pass_index=selected,
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


def replay_focused_v4(artifact: FocusedResultsArtifactV9) -> ResolvedStructuredAnswer | None:
    selector_format = artifact.selector_prepared.packet.get("selection_format")
    if selector_format == "roles-v6":
        selector_settings = LOW_SELECTOR_SETTINGS
        composer_settings = MEDIUM_SETTINGS
        composition_format: Literal["complete-v1", "complete-v2", "complete-v3", "complete-v4"] = "complete-v4"
    elif selector_format == "roles-v5":
        selector_settings = MEDIUM_SETTINGS
        composer_settings = MEDIUM_SETTINGS
        composition_format = "complete-v3"
    elif selector_format == "roles-v4":
        selector_settings = LOW_SELECTOR_SETTINGS
        composer_settings = COMPOSER_SETTINGS
        composition_format = "complete-v2"
    elif selector_format == "roles-v3":
        selector_settings = SELECTOR_SETTINGS
        composer_settings = COMPOSER_SETTINGS
        composition_format = "complete-v1"
    else:
        raise ValueError("saved focused V9 profile identity differs")
    if artifact.config.model != "gpt-6-luna" or artifact.selector_settings != selector_settings or \
            artifact.composer_settings != composer_settings:
        raise ValueError("saved focused-v4 model settings differ")
    projection = SolutionProjection.model_validate(artifact.evidence.source.model_dump(mode="json"))
    evidence = resolve_workspace(projection, fx_acquisition=artifact.evidence.fx_acquisition)
    if artifact.evidence != evidence:
        raise ValueError("saved focused-v4 workspace differs")
    verify_authoring_view(projection, prepare_results(projection, artifact.config))
    selector = prepare_focused_selector(projection, artifact.config, evidence,
                                        selection_format=selector_format)
    if artifact.selector_prepared != selector:
        raise ValueError("saved focused-v4 selector differs")
    passes = list(artifact.passes)
    if not 1 <= len(passes) <= 3 or [p.phase for p in passes] != [
            "selection", "composition", "correction"][:len(passes)]:
        raise ValueError("saved focused-v4 pass sequence is invalid")
    first = passes[0]
    _replay_pass(first, _request(selector, artifact.config, selector_settings,
        "selection", projection), artifact.config,
        lambda raw: decode_selection_v2(raw, selector.structured, projection),
        projection, selector)
    focus = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        focus = prepare_focused_composer(first.selection, selector, projection, evidence,
                                          composition_format=composition_format)
        if len(passes) < 2:
            raise ValueError("saved focused-v4 composition is missing")
        second = passes[1]
        _replay_pass(second, _request(focus, artifact.config, composer_settings,
            "composition", projection), artifact.config,
            lambda raw: decode_focused_wire(raw, focus, projection),
            projection, focus, _findings)
        failures = tuple(f for f in second.findings if f.outcome == "failed")
        if len(passes) == 3:
            if second.outcome != "recoverable" or not failures or second.raw_wire is None:
                raise ValueError("saved focused-v4 correction lacks failed draft")
            _replay_pass(passes[2], _request(focus, artifact.config, composer_settings,
                "correction", projection, feedback=failures,
                previous_wire=second.raw_wire), artifact.config,
                lambda raw: decode_focused_wire(raw, focus, projection),
                projection, focus, _findings)
        elif second.outcome == "recoverable" and failures:
            raise ValueError("saved focused-v4 correction is missing")
    elif len(passes) != 1:
        raise ValueError("saved focused-v4 composition ran after failed selection")
    if artifact.focus_prepared != focus:
        raise ValueError("saved focused-v4 source packet differs")
    selected, reason = _chosen(passes)
    if artifact.selected_pass_index != selected or artifact.selection_reason != reason:
        raise ValueError("saved focused-v4 selected draft differs")
    resolved, validation, delivery = _outcome(passes, selected, evidence, focus)
    generation = "success" if selected is not None else passes[-1].outcome
    if (artifact.generation_outcome != generation or
            artifact.validation_outcome != validation or
            artifact.delivery_outcome != delivery or artifact.resolved != resolved or
            artifact.resolved_digest != (content_digest(resolved.model_dump(mode="json"))
                                         if resolved else None)):
        raise ValueError("saved focused-v4 outcome differs")
    return resolved
