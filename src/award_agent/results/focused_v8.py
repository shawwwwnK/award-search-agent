"""Three fixed Luna tasks: selected evidence, draft, and editorial revision."""

from __future__ import annotations

import time
from typing import Literal, cast

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection

from .authoring import verify_authoring_view
from .contracts import ResultsConfig, ResultsInputMeasurer
from .core import prepare_results
from .currency import FxAcquisition
from .focused import (
    COMPOSER_SETTINGS,
    _pass,
    _replay_pass,
    _request,
    prepare_focused_composer,
    prepare_focused_selector,
)
from .focused_contracts import FocusedPass, FocusedResultsArtifactV10
from .focused_packet import decode_selection_v2
from .focused_v4 import LOW_SELECTOR_SETTINGS, MEDIUM_SETTINGS, _findings, _outcome
from .focused_wire import decode as decode_focused_wire
from .interactive_contracts import InteractivePreparedInput, InteractiveSettings, InteractiveWriter
from .presentation import resolve_workspace
from .runner import choose_recoverable
from .structured_contracts import ResolvedStructuredAnswer

NONE_DRAFT_SETTINGS = InteractiveSettings(reasoning_effort="none", service_tier="fast")


def _chosen(passes: list[FocusedPass]) -> tuple[int | None, str]:
    recoverable = tuple((index - 1, item.findings) for index, item in enumerate(passes)
                        if index >= 1 and item.outcome == "recoverable" and
                        item.document is not None)
    if not recoverable:
        return None, "no_recoverable_draft"
    index, reason = choose_recoverable(recoverable)
    return index + 1, {"correction_fewer_failures": "revision_fewer_failures",
                       "correction_tie": "revision_tie"}.get(reason, reason)


def run_focused_v8(projection: SolutionProjection, config: ResultsConfig,
                   writer: InteractiveWriter,
                   input_measurer: ResultsInputMeasurer | None = None, *,
                   fx_acquisition: FxAcquisition | None = None,
                   profile: Literal["focused-v8", "focused-v9", "focused-v10"] = "focused-v8",
                   ) -> FocusedResultsArtifactV10:
    started = time.perf_counter()
    if config.model != "gpt-6-luna":
        raise ValueError("focused-v8 requires explicit gpt-6-luna")
    if profile not in {"focused-v8", "focused-v9", "focused-v10"}:
        raise ValueError("unknown three-pass focused profile")
    selector_format: Literal["roles-v7", "roles-v8", "roles-v9"] = (
        "roles-v9" if profile == "focused-v10" else
        "roles-v8" if profile == "focused-v9" else "roles-v7")
    composition_format: Literal["complete-v5", "complete-v6", "complete-v7"] = (
        "complete-v7" if profile == "focused-v10" else
        "complete-v6" if profile == "focused-v9" else "complete-v5")
    composer_settings = NONE_DRAFT_SETTINGS if profile == "focused-v10" else COMPOSER_SETTINGS
    revision_settings = (COMPOSER_SETTINGS if profile == "focused-v9"
                         else MEDIUM_SETTINGS)
    evidence = resolve_workspace(projection, fx_acquisition=fx_acquisition)
    selector = prepare_focused_selector(projection, config, evidence,
                                        selection_format=selector_format)
    first = _pass("selection", _request(selector, config, LOW_SELECTOR_SETTINGS,
        "selection", projection), config, LOW_SELECTOR_SETTINGS, writer,
        input_measurer, lambda raw: decode_selection_v2(raw, selector.structured, projection),
        projection=projection, prepared=selector)
    passes = [first]
    focus: InteractivePreparedInput | None = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        focus = prepare_focused_composer(first.selection, selector, projection, evidence,
                                          composition_format=composition_format)
        second = _pass("composition", _request(focus, config, composer_settings,
            "composition", projection), config, composer_settings, writer,
            input_measurer, lambda raw: decode_focused_wire(raw, focus, projection),
            projection=projection, prepared=focus, checker=_findings)
        passes.append(second)
        if second.outcome == "recoverable":
            assert second.raw_wire is not None
            failures = tuple(f for f in second.findings if f.outcome == "failed")
            revision = _pass("revision", _request(focus, config, revision_settings,
                "revision", projection, feedback=failures,
                previous_wire=second.raw_wire), config, revision_settings, writer,
                input_measurer, lambda raw: decode_focused_wire(raw, focus, projection),
                projection=projection, prepared=focus, checker=_findings)
            passes.append(revision)
    selected, reason = _chosen(passes)
    resolved, validation, delivery = _outcome(passes, selected, evidence, focus)
    generation = "success" if selected is not None else passes[-1].outcome
    artifact = FocusedResultsArtifactV10(evidence=evidence, config=config,
        selector_settings=LOW_SELECTOR_SETTINGS, composer_settings=composer_settings,
        revision_settings=revision_settings,
        revision_trigger="editorial_revision" if len(passes) == 3 else None,
        selector_prepared=selector, focus_prepared=focus, passes=tuple(passes),
        selected_pass_index=selected,
        selection_reason=cast(Literal["initial_only", "revision_fewer_failures",
                                      "revision_tie", "initial_fewer_failures",
                                      "no_recoverable_draft"], reason),
        generation_outcome=cast(Literal["success", "api_error", "generation_error",
                                        "context_limit", "measurement_error"], generation),
        validation_outcome=cast(Literal["clean", "annotated", "unavailable"], validation),
        delivery_outcome=cast(Literal["delivered", "not_delivered"], delivery),
        resolved=resolved,
        resolved_digest=content_digest(resolved.model_dump(mode="json")) if resolved else None,
        runtime_seconds=0)
    return artifact.model_copy(update={"runtime_seconds": time.perf_counter() - started})


def replay_focused_v8(artifact: FocusedResultsArtifactV10) -> ResolvedStructuredAnswer | None:
    selector_format = artifact.selector_prepared.packet.get("selection_format")
    if selector_format == "roles-v9":
        composer_settings = NONE_DRAFT_SETTINGS
        revision_settings = MEDIUM_SETTINGS
        composition_format: Literal["complete-v5", "complete-v6", "complete-v7"] = "complete-v7"
    elif selector_format == "roles-v8":
        composer_settings = COMPOSER_SETTINGS
        revision_settings = COMPOSER_SETTINGS
        composition_format = "complete-v6"
    elif selector_format == "roles-v7":
        composer_settings = COMPOSER_SETTINGS
        revision_settings = MEDIUM_SETTINGS
        composition_format = "complete-v5"
    else:
        raise ValueError("saved three-pass focused profile marker differs")
    if artifact.config.model != "gpt-6-luna" or \
            artifact.selector_settings != LOW_SELECTOR_SETTINGS or \
            artifact.composer_settings != composer_settings or \
            artifact.revision_settings != revision_settings:
        raise ValueError("saved focused-v8 profile settings differ")
    projection = SolutionProjection.model_validate(artifact.evidence.source.model_dump(mode="json"))
    evidence = resolve_workspace(projection, fx_acquisition=artifact.evidence.fx_acquisition)
    if evidence != artifact.evidence:
        raise ValueError("saved focused-v8 workspace differs")
    verify_authoring_view(projection, prepare_results(projection, artifact.config))
    selector = prepare_focused_selector(projection, artifact.config, evidence,
                                        selection_format=selector_format)
    if selector != artifact.selector_prepared:
        raise ValueError("saved focused-v8 selector differs")
    passes = list(artifact.passes)
    if not 1 <= len(passes) <= 3 or [item.phase for item in passes] != [
            "selection", "composition", "revision"][:len(passes)]:
        raise ValueError("saved focused-v8 pass sequence is invalid")
    if artifact.revision_trigger != ("editorial_revision" if len(passes) == 3 else None):
        raise ValueError("saved focused-v8 revision trigger differs from pass sequence")
    first = passes[0]
    _replay_pass(first, _request(selector, artifact.config, LOW_SELECTOR_SETTINGS,
        "selection", projection), artifact.config,
        lambda raw: decode_selection_v2(raw, selector.structured, projection),
        projection, selector)
    focus: InteractivePreparedInput | None = None
    if first.outcome == "recoverable":
        assert first.selection is not None
        focus = prepare_focused_composer(first.selection, selector, projection, evidence,
                                          composition_format=composition_format)
        if len(passes) < 2:
            raise ValueError("saved focused-v8 draft is missing")
        second = passes[1]
        _replay_pass(second, _request(focus, artifact.config, composer_settings,
            "composition", projection), artifact.config,
            lambda raw: decode_focused_wire(raw, focus, projection),
            projection, focus, _findings)
        if second.outcome == "recoverable":
            if len(passes) != 3 or second.raw_wire is None:
                raise ValueError("saved focused-v8 editorial revision is missing")
            failures = tuple(f for f in second.findings if f.outcome == "failed")
            _replay_pass(passes[2], _request(focus, artifact.config, revision_settings,
                "revision", projection, feedback=failures,
                previous_wire=second.raw_wire), artifact.config,
                lambda raw: decode_focused_wire(raw, focus, projection),
                projection, focus, _findings)
        elif len(passes) != 2:
            raise ValueError("saved focused-v8 revision followed an unrecoverable draft")
    elif len(passes) != 1:
        raise ValueError("saved focused-v8 draft followed an unrecoverable selection")
    if artifact.focus_prepared != focus:
        raise ValueError("saved focused-v8 selected source differs")
    selected, reason = _chosen(passes)
    if artifact.selected_pass_index != selected or artifact.selection_reason != reason:
        raise ValueError("saved focused-v8 selected draft differs")
    resolved, validation, delivery = _outcome(passes, selected, evidence, focus)
    generation = "success" if selected is not None else passes[-1].outcome
    if (artifact.generation_outcome != generation or
            artifact.validation_outcome != validation or
            artifact.delivery_outcome != delivery or artifact.resolved != resolved or
            artifact.resolved_digest != (content_digest(resolved.model_dump(mode="json"))
                                         if resolved else None)):
        raise ValueError("saved focused-v8 outcome differs")
    return resolved
