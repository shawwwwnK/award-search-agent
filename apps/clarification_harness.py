"""Local Streamlit harness for one-way award testing from intent through Results.

Run with ``streamlit run apps/clarification_harness.py`` after installing the
optional ``harness`` dependency.  This module deliberately keeps Streamlit out
of the package dependencies and has no state beyond ``st.session_state``.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from award_agent.clarification import (
    ClarificationCommandError,
    ClarificationCompositionPending,
    ClarificationInterpretationError,
    ClarificationInterpretationPending,
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationComposerConfig,
    OpenAIClarificationInterpretationError,
    OpenAIClarificationInterpreterConfig,
    OpenAIClarificationPromptComposer,
    apply_clarification_answer,
    retry_prompt_composition,
    start_clarification,
)
from award_agent.domain import (
    BlockingRequirement,
    ClarificationAnswerCommand,
    ClarificationSession,
    RawRequest,
    RequestContext,
    RequestUnderstandingResult,
)
from award_agent.intent import (
    NagerHolidayProvider,
    OpenAISemanticIntentConfig,
    OpenAISemanticIntentInterpreter,
    understand_request,
)

_SESSION_KEY = "clarification_session"
_COMPOSITION_PENDING_KEY = "clarification_harness_composition_pending"
_INITIAL_PENDING_KEY = "clarification_harness_initial_pending"
_ERROR_KEY = "clarification_harness_error"
_TELEMETRY_KEY = "clarification_harness_model_telemetry"
_PRIVATE_TRACE_KEY = "clarification_harness_private_local_traces"
_ANSWER_KEY_PREFIX = "clarification_answer"
_DEFAULT_TIMEZONE = "America/Los_Angeles"
_INITIAL_PENDING_STAGE = "semantic_intent"
_INITIAL_PENDING_CODE = "initial_intent_retryable"
_WORKFLOW_KEY = "award_harness_workflow"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _sync_workflow(st: Any, session: ClarificationSession | None) -> dict[str, Any]:
    """Discard artifacts when their authoritative session revision changes."""
    from award_agent.harness.pipeline import session_binding

    binding = session_binding(session) if session is not None else None
    state = st.session_state.get(_WORKFLOW_KEY)
    if state is None or state["binding"] != binding:
        state = {"binding": binding}
        st.session_state[_WORKFLOW_KEY] = state
    return cast(dict[str, Any], state)


def _workflow_archive(state: Mapping[str, Any]) -> bytes:
    """Export private local artifacts and response bodies without credentials."""
    files: dict[str, bytes] = {}
    for key in ("session", "bundle", "planning", "providers", "ranking", "results"):
        item = state.get(key)
        if item is None:
            continue
        if key == "planning":
            models = {"planning-input": item.planning_input, "planning-result": item.result}
        elif key == "providers":
            models = {"provider-result": item.result, "tape": item.tape}
            files.update(item.evidence_files)
        elif key == "ranking":
            models = {"matched": item.matched, "ranked": item.ranked, "solutions": item.projection}
        else:
            models = {key: item}
        for name, model in models.items():
            if model is not None:
                files[f"{name}.json"] = model.model_dump_json(indent=2).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def _render_workflow(st: Any, session: ClarificationSession | None) -> None:
    """Explicit event surface for the application pipeline; reruns only render."""
    from award_agent.cli.provider_results import ProviderInputBundle
    from award_agent.harness.pipeline import (
        HarnessSettings,
        PlanningRun,
        acquire_and_rank,
        author,
        plan_session,
        run_from_ready,
    )
    from award_agent.providers.replay import ReplayTape
    from award_agent.results import ResultsConfig, ResultsDocument, replay_results

    state = _sync_workflow(st, session)
    st.subheader("3. Run the search")
    st.caption(
        "Run stages explicitly. Ordinary reruns make no model or flight-provider calls. "
        "Partial coverage and validation notices remain visible."
    )
    with st.sidebar.expander("Search and Results settings"):
        selector_model = st.text_input("Endpoint-airport selector model", "gpt-5.6-luna")
        gateway_model = st.text_input("Gateway discovery model", "gpt-5.6-luna")
        catalog = st.text_input(
            "Catalog release", str(_REPO_ROOT / "data/search_planning/catalogs/m1a-3cb7981519612945")
        )
        provider_settings = st.text_input(
            "Provider capability and budget file",
            str(_REPO_ROOT / "data/provider_capabilities/provider-stage-current.json"),
        )
        fx = st.text_input("Ranking FX snapshot", str(_REPO_ROOT / "data/ranking/m2/fx-2026-09-29.json"))
        gfly_executable = st.text_input(
            "Reviewed gfly Python interpreter", "/private/tmp/gfly-live-py312/bin/python",
            help="The repository compatibility launcher verifies this pinned installation before searching.",
        )
        st.caption(
            "Results values below start from the October 8 Luna diagnostic settings. "
            "They are editable run settings, not an adopted model policy. Live Results counts "
            "the complete input before authoring and permits at most one correction."
        )
        config_text = st.text_area(
            "ResultsConfig JSON",
            value=json.dumps({
                "model": "gpt-6-luna", "max_output_tokens": 16384,
                "timeout_seconds": 300, "context_limit_tokens": 1050000,
                "prompt_overhead_tokens": 2048, "max_input_tokens": 922000,
            }, indent=2), height=220,
        )
        try:
            st.json(json.loads(Path(provider_settings).read_text()))
        except (OSError, ValueError):
            st.caption("Provider settings file unavailable or invalid; execution will report the error.")
    settings = HarnessSettings(
        catalog_path=Path(catalog), selector_model=selector_model, gateway_model=gateway_model,
        provider_settings_path=Path(provider_settings), fx_path=Path(fx),
        gfly_executable=Path(gfly_executable),
    )
    ready = session is not None and session.status.value == "ready"
    if not ready:
        st.info("Resolve the request to ready before running new planning or live provider searches.")

    run_all = st.button("Run ready request through Results (live)", disabled=not ready, type="primary")
    with st.expander("Run individual stages or retry") as stage_controls:
        st.caption("For inspecting or retrying one stage at a time. Start with planning, then search providers, then author Results.")
        plan_only = st.button("Run search planning only", disabled=not ready)
    if run_all or plan_only:
        # A fresh planning event invalidates every downstream artifact first.
        binding = state["binding"]
        state.clear()
        state["binding"] = binding
        try:
            assert session is not None
            if run_all:
                config = ResultsConfig.model_validate_json(config_text)
                with st.status("Running ready request through Results", expanded=True) as progress:
                    for stage, stage_artifact in run_from_ready(session, settings, config):
                        state[stage] = stage_artifact
                        if isinstance(stage_artifact, PlanningRun):
                            state["bundle"] = stage_artifact.bundle
                        progress.write(f"{stage}: complete")
                    delivered = state.get("results") is not None and state["results"].delivery_outcome == "delivered"
                    progress.update(
                        label="Results delivered; inspect checks below" if delivered else "Run stopped before Results delivery; inspect outcomes below",
                        state="complete" if delivered else "error",
                    )
            else:
                with st.spinner("Selecting endpoint airports, discovering gateways and compiling searches…"):
                    state["planning"] = plan_session(session, settings)
                    state["bundle"] = state["planning"].bundle
        except Exception as exc:  # noqa: BLE001 - keep completed stages available for inspection.
            state["error"] = f"Workflow stopped ({type(exc).__name__}): {exc}"

    with st.expander("Test a saved search (offline)"):
        root = _REPO_ROOT / "evidence/provider-stage/saved-searches/runs"
        cases = sorted(path.name for path in root.iterdir() if (path / "bundle.json").is_file())
        case = st.selectbox("Saved search", cases)
        st.caption("Replay uses the saved request and historical observations; it replaces the downstream run shown here.")
        replay_clicked = st.button("Replay providers and run ranking (offline)", disabled=not cases)
    with stage_controls:
        search_clicked = st.button(
            "Search providers and run ranking (live)",
            disabled=not ready or state.get("bundle") is None or "saved_case" in state,
        )
    if replay_clicked or search_clicked:
        try:
            if replay_clicked:
                folder = root / case
                bundle = ProviderInputBundle.model_validate_json((folder / "bundle.json").read_text())
                tape = ReplayTape.model_validate_json((folder / "tape.json").read_text())
                binding = state["binding"]
                state.clear()
                state.update(binding=binding, bundle=bundle, saved_case=case)
            else:
                if "saved_case" in state:
                    raise ValueError("Run new planning for the ready request before live acquisition.")
                bundle, tape = state["bundle"], None
                for key in ("providers", "ranking", "results", "error"):
                    state.pop(key, None)
            with st.status("Acquiring observations and ranking", expanded=True) as progress:
                for stage, stage_artifact in acquire_and_rank(bundle, settings, tape=tape):
                    state[stage] = stage_artifact
                    progress.write(f"{stage}: complete")
                progress.update(label="Acquisition and ranking finished", state="complete")
        except Exception as exc:  # noqa: BLE001
            state["error"] = f"Acquisition/ranking stopped ({type(exc).__name__}): {exc}"

    with stage_controls:
        st.write("Answer authoring")
        mode = st.radio("Results mode", ("Live writer", "Frozen draft (offline)"))
        draft_text = correction_text = ""
        if mode == "Frozen draft (offline)":
            draft_text = st.text_area("ResultsDocument JSON (offline)", height=180)
            correction_text = st.text_area("Correction ResultsDocument JSON (optional)", height=120)
        else:
            st.caption("Uses the Results model and limits in the sidebar. Requires a completed ranking run.")
        author_clicked = st.button("Author Results", disabled=state.get("ranking") is None)
    if author_clicked:
        state.pop("results", None)
        state.pop("error", None)
        try:
            config = ResultsConfig.model_validate_json(config_text)
            draft = ResultsDocument.model_validate_json(draft_text) if mode == "Frozen draft (offline)" else None
            correction = ResultsDocument.model_validate_json(correction_text) if draft is not None and correction_text.strip() else None
            with st.spinner("Preparing, checking and authoring Results…"):
                state["results"] = author(state["ranking"].projection, config, draft=draft, correction=correction)
        except Exception as exc:  # noqa: BLE001
            state["error"] = f"Results stopped ({type(exc).__name__}): {exc}"

    if state.get("error"):
        st.error(state["error"])
    if state.get("saved_case"):
        st.info(f"Showing offline saved search: {state['saved_case']}. This is separate from the current intent session.")
    if state.get("planning") is not None:
        st.caption(f"Planning: {state['planning'].result.outcome.value}")
    if state.get("providers") is not None:
        provider_result = state["providers"].result
        st.caption(f"Provider coverage: {provider_result.status} · {len(provider_result.observations)} observations")
    st.subheader("4. Answer")
    artifact = state.get("results")
    if artifact is not None:
        st.write(f"Results: `{artifact.delivery_outcome}`; validation: `{artifact.validation_outcome}`; generation: `{artifact.generation_outcome}`")
        if artifact.delivery_outcome == "delivered":
            markdown = replay_results(artifact)
            st.markdown(markdown)
            st.download_button("Download answer Markdown", markdown, "answer.md", "text/markdown")
        else:
            st.error(f"No Results document delivered: {artifact.selection_reason}")
        with st.expander("Results checks, notices and usage"):
            st.json({
                "notices": [item.model_dump(mode="json") for item in artifact.notices],
                "attempts": [item.model_dump(mode="json", exclude={"writer_receipt", "document"}) for item in artifact.attempts],
                "usage": [item.writer_receipt.usage if item.writer_receipt else {} for item in artifact.attempts],
            })
    else:
        st.caption("Your answer will appear here after a run reaches Results.")
    with st.expander("Search evidence: planning, provider coverage and ranking"):
        planning = state.get("planning")
        if planning is not None:
            st.write(f"Search planning: `{planning.result.outcome.value}`")
            st.write("Planning evidence and issues")
            st.json(planning.result.model_dump(mode="json"))
            st.json(planning.diagnostics)
        providers = state.get("providers")
        if providers is not None:
            st.write(f"Provider search: `{providers.result.status}`; {len(providers.result.observations)} observations")
            st.write("Provider coverage and receipts")
            st.json(providers.result.model_dump(mode="json"))
        ranking = state.get("ranking")
        if ranking is not None:
            st.write("Ranking accounting")
            st.json(ranking.matched.accounting.model_dump(mode="json"))
            st.write("Ranked solutions and factual export")
            st.json(ranking.projection.model_dump(mode="json"))
    if state.get("bundle") is not None:
        st.caption("Downloads contain private travel requests, observations and Results drafts. Stored only in this local session unless you download them.")
        export_state = dict(state)
        if session is not None and "saved_case" not in state:
            export_state["session"] = session
        st.download_button("Download run artifacts and replay evidence", _workflow_archive(export_state), "award-harness-run.zip", "application/zip")


def _local_message_id(*, session_id: str, revision: int) -> str:
    """Return a stable, session-scoped ID for the next local answer."""

    return f"local-clarification:{session_id}:answer:{revision + 1}"


def _is_initial_intent_pending(result: RequestUnderstandingResult) -> bool:
    """Do not turn a typed initial receiver fault into a clarification session."""

    outcome = getattr(result, "outcome", None)
    return getattr(outcome, "value", outcome) == "pending_retryable"


def _show_error(st: object) -> None:
    """Render the latest local validation/controller/interpreter error."""

    if st.session_state.get(_INITIAL_PENDING_KEY) is not None:  # type: ignore[attr-defined]
        return
    error = st.session_state.get(_ERROR_KEY)  # type: ignore[attr-defined]
    if error:
        st.error(error)  # type: ignore[attr-defined]


def _record_error(st: object, message: str) -> None:
    """Retain and display an error in the same Streamlit rerun."""

    st.session_state[_ERROR_KEY] = message  # type: ignore[attr-defined]
    st.error(message)  # type: ignore[attr-defined]


def _set_initial_pending(
    st: object,
    *,
    request_text: str,
    reference_date: date,
    timezone: str,
    intent_model: str,
    composer_model: str,
) -> None:
    """Retain a retryable initial request without exposing model/provider detail.

    This state is deliberately local to the harness.  It is not a clarification
    session and it contains only the request context needed for an explicit,
    user-triggered retry.
    """

    st.session_state[_INITIAL_PENDING_KEY] = {  # type: ignore[attr-defined]
        "request_text": request_text,
        "reference_date": reference_date.isoformat(),
        "timezone": timezone,
        "intent_model": intent_model,
        "composer_model": composer_model,
        "stage": _INITIAL_PENDING_STAGE,
        "code": _INITIAL_PENDING_CODE,
    }
    # A pending request is sessionless.  Do not leave a prior request visible
    # behind the retry surface or accidentally reuse it after a rerun.
    st.session_state.pop(_SESSION_KEY, None)  # type: ignore[attr-defined]
    st.session_state.pop(_COMPOSITION_PENDING_KEY, None)  # type: ignore[attr-defined]
    # A pending outcome is not a user-facing error and must never expose a
    # stale raw exception from a prior interaction.
    st.session_state.pop(_ERROR_KEY, None)  # type: ignore[attr-defined]


def _render_initial_pending(st: object) -> None:
    """Render a stable, non-sensitive retry surface for initial pending state."""

    pending = st.session_state.get(_INITIAL_PENDING_KEY)  # type: ignore[attr-defined]
    if not isinstance(pending, Mapping):
        return

    st.warning(  # type: ignore[attr-defined]
        "Initial interpretation is temporarily unavailable. No clarification session was "
        "created; your request and date context are preserved locally."
    )
    st.write(f"Stage: `{pending.get('stage', _INITIAL_PENDING_STAGE)}`")  # type: ignore[attr-defined]
    st.write(f"Status code: `{pending.get('code', _INITIAL_PENDING_CODE)}`")  # type: ignore[attr-defined]

    request_text = pending.get("request_text")
    if not isinstance(request_text, str) or not request_text:
        st.caption(  # type: ignore[attr-defined]
            "Retry is available from the original request form when its request context is present."
        )
        return

    if not st.button("Retry initial interpretation"):  # type: ignore[attr-defined]
        return

    intent_interpreter: OpenAISemanticIntentInterpreter | None = None
    composer: OpenAIClarificationPromptComposer | None = None
    retry_error: BaseException | None = None
    try:
        composer = OpenAIClarificationPromptComposer(
            OpenAIClarificationComposerConfig(model=str(pending.get("composer_model", ""))),
            capture_llm_io=True,
        )
        intent_context_date = date.fromisoformat(str(pending["reference_date"]))
        session, intent_interpreter = _start_from_raw_request(
            request_text=request_text,
            reference_date=intent_context_date,
            timezone=str(pending["timezone"]),
            intent_model=str(pending["intent_model"]),
            composer=composer,
        )
    except Exception as exc:  # noqa: BLE001 - retain generic retryable state.
        retry_error = exc
        # Keep the same request/context and stable status surface.  Raw
        # exception text belongs only to private traces/telemetry.
    else:
        if session is not None:
            st.session_state[_SESSION_KEY] = session  # type: ignore[attr-defined]
            st.session_state.pop(_INITIAL_PENDING_KEY, None)  # type: ignore[attr-defined]
            st.session_state.pop(_ERROR_KEY, None)  # type: ignore[attr-defined]
            st.rerun()  # type: ignore[attr-defined]
    finally:
        _record_model_diagnostics(
            st,
            event="initial_retry",
            stage="semantic_intent",
            model=str(pending.get("intent_model", "")),
            adapter=intent_interpreter,
            error=retry_error,
        )
        _record_model_diagnostics(
            st,
            event="initial_retry",
            stage="prompt_composer",
            model=str(pending.get("composer_model", "")),
            adapter=composer,
            error=retry_error,
        )


def _render_terminal_message(st: object, terminal_message: str | None) -> None:
    """Make product-owned unsupported-scope guidance visible above diagnostics."""

    if terminal_message is None:
        return
    st.subheader("One-way award request guidance")  # type: ignore[attr-defined]
    st.error(terminal_message)  # type: ignore[attr-defined]


def _render_requirements(st: object, requirements: tuple[BlockingRequirement, ...]) -> None:
    """Render the typed requirements sent to the interpreter boundary."""

    st.caption(  # type: ignore[attr-defined]
        "Interpreter inputs: answer message, active typed blockers, and "
        "date-free temporal catalogs:"
    )
    st.json(  # type: ignore[attr-defined]
        [requirement.model_dump(mode="json") for requirement in requirements]
    )


def _start_from_raw_request(
    *,
    request_text: str,
    reference_date: date,
    timezone: str,
    intent_model: str,
    composer: OpenAIClarificationPromptComposer,
) -> tuple[ClarificationSession | None, OpenAISemanticIntentInterpreter]:
    """Compose the active one-way request workflow with the session boundary."""

    request = RawRequest(
        text=request_text,
        context=RequestContext(reference_date=reference_date, timezone=timezone),
    )
    interpreter = OpenAISemanticIntentInterpreter(
        OpenAISemanticIntentConfig(model=intent_model),
        capture_llm_io=True,
    )
    initial = understand_request(request, interpreter, NagerHolidayProvider())
    return _start_from_initial_result(initial, composer=composer), interpreter


def _start_from_initial_result(
    initial: RequestUnderstandingResult,
    *,
    composer: OpenAIClarificationPromptComposer,
) -> ClarificationSession | None:
    """Apply the initial-result/session boundary used by both raw and JSON paths.

    Completed initial results—whether ready, unsupported/stopped, or blocked and
    requiring clarification—always enter the additive session controller.  Only
    the typed operational/model pending outcome remains sessionless.
    """

    if _is_initial_intent_pending(initial):
        return None
    return start_clarification(initial, composer=composer)


def _render_session_state(st: object, session: ClarificationSession) -> None:
    """Render the authoritative current revision and append-only history."""

    revision = session.current_revision
    st.subheader("Effective request")  # type: ignore[attr-defined]
    st.json(revision.effective_request.model_dump(mode="json"))  # type: ignore[attr-defined]
    st.subheader("Clarification history")  # type: ignore[attr-defined]
    st.json(  # type: ignore[attr-defined]
        [item.model_dump(mode="json") for item in session.revisions]
    )


def _trace_has_error(traces: list[Mapping[str, Any]]) -> bool:
    return any(trace.get("error") is not None for trace in traces)


def _record_model_diagnostics(
    st: object,
    *,
    event: str,
    stage: str,
    model: str,
    adapter: object | None,
    error: BaseException | None = None,
) -> None:
    """Capture one event-scoped model stage outside the domain session.

    Aggregate telemetry is displayed locally; exact call payloads/responses are
    retained separately under a private-local label and never enter session JSON.
    The adapter accessors are deliberately called from event ``finally`` blocks
    so failed calls are recorded too.
    """

    traces: list[Mapping[str, Any]] = []
    usage: dict[str, int] | None = None
    accessor_error: BaseException | None = None
    if adapter is not None:
        try:
            traces = list(adapter.take_call_traces())  # type: ignore[attr-defined]
            usage = adapter.take_usage()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 - diagnostics must not affect the harness.
            accessor_error = exc

    calls = int(usage.get("calls", 0)) if usage else len(traces)
    usage_summary = usage or {
        "calls": calls,
        "captured_calls": 0,
        "missing_calls": calls,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    latency_seconds = round(
        sum(float(trace.get("latency_seconds") or 0.0) for trace in traces),
        3,
    )
    trace_error_type = next(
        (
            str(trace["error"].get("type"))
            for trace in traces
            if isinstance(trace.get("error"), Mapping) and trace["error"].get("type")
        ),
        None,
    )
    if error is not None or accessor_error is not None or _trace_has_error(traces):
        status = "error"
    elif adapter is None:
        status = "not_constructed"
    elif calls == 0:
        status = "not_called"
    else:
        status = "ok"
    record: dict[str, Any] = {
        "schema_version": 1,
        "event": event,
        "stage": stage,
        "model": model,
        "status": status,
        "calls": calls,
        "usage": usage_summary,
        "latency_seconds": latency_seconds,
        "error_type": (
            type(error).__name__
            if error is not None
            else type(accessor_error).__name__
            if accessor_error is not None
            else trace_error_type
        ),
        "private_local_trace_count": len(traces),
    }
    state = st.session_state  # type: ignore[attr-defined]
    state.setdefault(_TELEMETRY_KEY, []).append(record)
    state.setdefault(_PRIVATE_TRACE_KEY, []).append(
        {
            "privacy": "private_local_only",
            "event": event,
            "stage": stage,
            "traces": traces,
        }
    )


def _render_model_diagnostics(st: object) -> None:
    """Render aggregate stage telemetry without exposing private raw traces."""

    records = st.session_state.get(_TELEMETRY_KEY, [])  # type: ignore[attr-defined]
    if not records:
        return
    with st.expander("Intent and clarification model usage"):  # type: ignore[attr-defined]
        st.caption(  # type: ignore[attr-defined]
            "Event-scoped receiver/composer telemetry (local only; raw traces "
            "are private and not shown):"
        )
        st.json(records)  # type: ignore[attr-defined]


def _render_prompt_diagnostics(st: object, session: object) -> None:
    """Render prompt provenance and active answer-derived assumptions.

    The diagnostics are deliberately read from the authoritative current
    revision/effective request.  They remain visible after a ready transition,
    where there is no next prompt to render.
    """

    revision = session.current_revision  # type: ignore[attr-defined]
    with st.expander("Clarification diagnostics"):  # type: ignore[attr-defined]
        prompt = revision.prompt
        if prompt is None:
            st.write(  # type: ignore[attr-defined]
                "Prompt composition: `none (session is ready or stopped)`"
            )
        else:
            st.write(  # type: ignore[attr-defined]
                f"Prompt composition: `{prompt.composition_source.value}`"
            )
            if prompt.fallback_code is not None:
                st.write(f"Fallback code: `{prompt.fallback_code}`")  # type: ignore[attr-defined]
            st.caption(  # type: ignore[attr-defined]
                "Authoritative issue records for the active blockers:"
            )
            st.json(  # type: ignore[attr-defined]
                [issue.model_dump(mode="json") for issue in prompt.issues]
            )
            st.caption(  # type: ignore[attr-defined]
                "This copy was generated after deterministic blocker recomputation."
            )

        disclosures = []
        for contribution in revision.effective_request.temporal_contributions:
            provenance = contribution.interpretation_provenance
            if provenance is None or provenance.assumption_disclosure is None:
                continue
            disclosures.append(provenance.assumption_disclosure.model_dump(mode="json"))
        st.caption("Active assumption disclosures:")  # type: ignore[attr-defined]
        if disclosures:
            st.json(disclosures)  # type: ignore[attr-defined]
        else:
            st.write("None")  # type: ignore[attr-defined]


def main() -> None:
    # Keeping this import local makes the harness dependency genuinely optional
    # for package users and the normal test suite.
    import streamlit as st

    # Match the existing local CLI convention without copying credentials into
    # code, session state, logs, or model-facing payloads.
    load_dotenv()
    st.set_page_config(page_title="One-way award end-to-end harness", layout="wide")
    st.title("One-way award end-to-end harness")
    st.caption("Enter a request, resolve any questions, run the search, then inspect the answer. Settings are in the sidebar.")
    st.sidebar.header("Run settings")
    st.sidebar.caption("Local testing only. Model and provider calls require an explicit button click.")
    st.sidebar.caption("ADR 0017 semantic-intent · ADR 0016 one-way award boundary")
    with st.sidebar.expander("Intent and clarification models"):
        intent_model = st.text_input(
            "Initial semantic intent model",
            value="gpt-5.6-luna",
            help="Explicit model for the initial one-way request semantic interpretation.",
        )
        clarification_model = st.text_input(
            "Clarification receiver model",
            value="gpt-5.6-luna",
            help="Interprets an answer only after Submit answer.",
        )
        composer_model = st.text_input(
            "Follow-up prompt composer model",
            value="gpt-5.6-luna",
            help="Authors each initial or post-reduction follow-up prompt.",
        )

    st.subheader("1. Travel request")
    st.caption("One-way awards: include origin, destination, departure dates and travelers. Submit the return as a separate one-way request; cash-only requests are not supported.")
    with (
        st.expander("Enter or replace the request", expanded=st.session_state.get(_SESSION_KEY) is None),
        st.form("initial-request"),
    ):
        request_text = st.text_area("One-way award request", height=120)
        reference_date = st.date_input(
            "Reference date",
            value=datetime.now(ZoneInfo(_DEFAULT_TIMEZONE)).date(),
            help="Editable deterministic context for relative dates such as 'next month'.",
        )
        timezone = st.text_input("Timezone", value=_DEFAULT_TIMEZONE)
        initial_submitted = st.form_submit_button("Understand request and start session")
    if initial_submitted:
        if not request_text.strip():
            _record_error(st, "Enter a travel request before starting a session.")
        else:
            intent_interpreter: OpenAISemanticIntentInterpreter | None = None
            composer: OpenAIClarificationPromptComposer | None = None
            initial_error: BaseException | None = None
            try:
                composer = OpenAIClarificationPromptComposer(
                    OpenAIClarificationComposerConfig(model=composer_model),
                    capture_llm_io=True,
                )
                session, intent_interpreter = _start_from_raw_request(
                    request_text=request_text,
                    reference_date=reference_date,
                    timezone=timezone,
                    intent_model=intent_model,
                    composer=composer,
                )
                if session is None:
                    _set_initial_pending(
                        st,
                        request_text=request_text,
                        reference_date=reference_date,
                        timezone=timezone,
                        intent_model=intent_model,
                        composer_model=composer_model,
                    )
                else:
                    st.session_state[_SESSION_KEY] = session
                    st.session_state.pop(_INITIAL_PENDING_KEY, None)
                    st.session_state.pop(_COMPOSITION_PENDING_KEY, None)
            except Exception as exc:  # noqa: BLE001 - retain generic retryable state.
                initial_error = exc
                _set_initial_pending(
                    st,
                    request_text=request_text,
                    reference_date=reference_date,
                    timezone=timezone,
                    intent_model=intent_model,
                    composer_model=composer_model,
                )
            else:
                if session is not None:
                    st.session_state.pop(_ERROR_KEY, None)
            finally:
                _record_model_diagnostics(
                    st,
                    event="initial_start",
                    stage="semantic_intent",
                    model=intent_model,
                    adapter=intent_interpreter,
                    error=initial_error,
                )
                _record_model_diagnostics(
                    st,
                    event="initial_start",
                    stage="prompt_composer",
                    model=composer_model,
                    adapter=composer,
                    error=initial_error,
                )

    with st.expander("Advanced: import an understood request (JSON)"):
        raw_initial = st.text_area(
            "RequestUnderstandingResult JSON",
            help="Paste JSON produced by the active semantic initial-intent workflow.",
            height=220,
        )
        start_from_json = st.button("Start from ADR 0017 JSON")
    if start_from_json:
        composer = None
        composer_error = None
        try:
            initial = RequestUnderstandingResult.model_validate(json.loads(raw_initial))
            if _is_initial_intent_pending(initial):
                # Imported pending results do not carry enough original request
                # context for this harness to retry them.  Keep the failure
                # generic and sessionless rather than exposing validation text.
                st.session_state[_INITIAL_PENDING_KEY] = {
                    "stage": _INITIAL_PENDING_STAGE,
                    "code": _INITIAL_PENDING_CODE,
                }
                st.session_state.pop(_ERROR_KEY, None)
                st.session_state.pop(_SESSION_KEY, None)
            else:
                composer = OpenAIClarificationPromptComposer(
                    OpenAIClarificationComposerConfig(model=composer_model),
                    capture_llm_io=True,
                )
                session = _start_from_initial_result(initial, composer=composer)
                assert session is not None
                st.session_state[_SESSION_KEY] = session
                st.session_state.pop(_INITIAL_PENDING_KEY, None)
                st.session_state.pop(_COMPOSITION_PENDING_KEY, None)
        except Exception as exc:  # noqa: BLE001 - retain the prior session on setup failures.
            composer_error = exc
            _record_error(st, f"Initial result was not accepted: {exc}")
        else:
            st.session_state.pop(_ERROR_KEY, None)
        finally:
            _record_model_diagnostics(
                st,
                event="json_start",
                stage="prompt_composer",
                model=composer_model,
                adapter=composer,
                error=composer_error,
            )

    _show_error(st)
    if st.session_state.get(_INITIAL_PENDING_KEY) is not None:
        # A pending initial request owns the visible surface until it succeeds
        # or the user submits a different request.  Any prior session remains
        # local but is never used as the pending request's state.
        _render_initial_pending(st)
        _render_model_diagnostics(st)
        return
    session = st.session_state.get(_SESSION_KEY)
    if session is None:
        # A typed initial pending outcome has no session by design, but its
        # local request/context and aggregate receiver diagnostics must remain
        # inspectable.  The retry button is the only route back into intent.
        st.subheader("2. Clarify and review")
        st.caption("Start a request above to resolve any missing details, or use a saved search below for offline testing.")
        _render_workflow(st, None)
        _render_model_diagnostics(st)
        return

    revision = session.current_revision
    st.subheader("2. Clarify and review")
    st.caption(f"Session revision {revision.revision} · Status: {revision.status.value}")

    if revision.stop_reason is not None:
        st.write(f"Terminal reason: `{revision.stop_reason.value}`")
    _render_terminal_message(st, revision.terminal_message)

    if revision.prompt is not None:
        st.subheader("Next clarification prompt")
        st.text(revision.prompt.message)
        _render_requirements(st, revision.prompt.requirements)

        composition_pending = st.session_state.get(_COMPOSITION_PENDING_KEY)
        if composition_pending is not None:
            # The answer was already interpreted and deterministically reduced.
            # Only its presentation retry remains; accepting another answer here
            # would obscure that immutable transition boundary.
            st.warning(
                "Your answer was applied, but the next clarification prompt needs to be "
                "composed again. Retry composition without reinterpreting your answer."
            )
            retry_composition = st.button("Retry prompt composition")
            if retry_composition:
                retry_composer: OpenAIClarificationPromptComposer | None = None
                retry_error: BaseException | None = None
                try:
                    retry_composer = OpenAIClarificationPromptComposer(
                        OpenAIClarificationComposerConfig(model=composer_model),
                        capture_llm_io=True,
                    )
                    retry_transition = retry_prompt_composition(
                        session,
                        composition_pending.pending,
                        retry_composer,
                    )
                except Exception as exc:  # noqa: BLE001 - retain retryable pending state.
                    retry_error = exc
                    _record_error(
                        st,
                        f"Prompt composition retry failed ({type(exc).__name__}): {exc}",
                    )
                else:
                    if isinstance(retry_transition, ClarificationCompositionPending):
                        st.session_state[_COMPOSITION_PENDING_KEY] = retry_transition
                        _record_error(
                            st,
                            "The follow-up prompt could not be composed. Retry when you are ready; "
                            "your answer remains applied.",
                        )
                    else:
                        st.session_state[_SESSION_KEY] = retry_transition.session
                        st.session_state.pop(_COMPOSITION_PENDING_KEY, None)
                        st.session_state.pop(_ERROR_KEY, None)
                        st.rerun()
                finally:
                    _record_model_diagnostics(
                        st,
                        event="prompt_composition_retry",
                        stage="prompt_composer",
                        model=composer_model,
                        adapter=retry_composer,
                        error=retry_error,
                    )
        else:
            # A form is the sole answer submission route.  Code that constructs an
            # interpreter or invokes the controller is intentionally nested below
            # its explicit submit event, so ordinary Streamlit reruns cannot call a
            # model or change a session.
            answer_key = f"{_ANSWER_KEY_PREFIX}:{session.session_id}:{revision.revision}"
            with st.form("clarification-answer"):
                answer = st.text_area("Answer", key=answer_key)
                submitted = st.form_submit_button("Submit answer")
            if submitted:
                if not answer.strip():
                    st.warning("Enter an answer before submitting.")
                else:
                    interpreter: OpenAIClarificationAnswerInterpreter | None = None
                    answer_composer: OpenAIClarificationPromptComposer | None = None
                    interpreter_error: BaseException | None = None
                    command = ClarificationAnswerCommand(
                        session_id=session.session_id,
                        expected_revision=revision.revision,
                        prompt_id=revision.prompt.prompt_id,
                        message_id=_local_message_id(
                            session_id=session.session_id,
                            revision=revision.revision,
                        ),
                        text=answer,
                    )
                    try:
                        interpreter = OpenAIClarificationAnswerInterpreter(
                            OpenAIClarificationInterpreterConfig(model=clarification_model),
                            # Exact model payloads stay in private local diagnostics.
                            capture_llm_io=True,
                        )
                        answer_composer = OpenAIClarificationPromptComposer(
                            OpenAIClarificationComposerConfig(model=composer_model),
                            capture_llm_io=True,
                        )
                        transition = apply_clarification_answer(
                            session, command, interpreter, composer=answer_composer
                        )
                    except (
                        ClarificationCommandError,
                        ClarificationInterpretationError,
                        OpenAIClarificationInterpretationError,
                        ValueError,
                    ) as exc:
                        interpreter_error = exc
                        # Do not assign a new session on any controller or model
                        # error.  The old revision remains visible and retryable.
                        _record_error(
                            st,
                            f"Answer was not applied ({type(exc).__name__}): {exc}",
                        )
                    except Exception as exc:  # noqa: BLE001
                        interpreter_error = exc
                        # This includes local OpenAI-client setup failures.  Keep
                        # the same atomic UI rule for unexpected infrastructure
                        # errors while exposing their concrete class locally.
                        _record_error(
                            st,
                            f"Answer processing failed ({type(exc).__name__}): {exc}",
                        )
                    else:
                        if isinstance(transition, ClarificationInterpretationPending):
                            st.warning(
                                "Your answer was not applied because the receiver needs a retry "
                                f"({transition.code}). The current question is unchanged; submit again "
                                "when you are ready."
                            )
                        elif isinstance(transition, ClarificationCompositionPending):
                            st.session_state[_COMPOSITION_PENDING_KEY] = transition
                            _record_error(
                                st,
                                "The follow-up prompt could not be composed. Retry when you are ready; "
                                "your answer remains applied.",
                            )
                        else:
                            st.session_state[_SESSION_KEY] = transition.session
                            st.session_state.pop(_COMPOSITION_PENDING_KEY, None)
                            st.session_state.pop(_ERROR_KEY, None)
                            st.rerun()
                    finally:
                        _record_model_diagnostics(
                            st,
                            event="answer_submit",
                            stage="answer_interpreter",
                            model=clarification_model,
                            adapter=interpreter,
                            error=interpreter_error,
                        )
                        _record_model_diagnostics(
                            st,
                            event="answer_submit",
                            stage="prompt_composer",
                            model=composer_model,
                            adapter=answer_composer,
                            error=interpreter_error,
                        )
    elif revision.status.value == "ready":
        st.success("Request is ready for search planning and end-to-end testing.")
    else:
        st.warning("Session stopped. Review the request guidance above.")
    with st.expander("Review the resolved request and clarification history"):
        _render_session_state(st, session)
    _render_workflow(st, session)
    st.divider()
    st.subheader("Session diagnostics")
    _render_prompt_diagnostics(st, session)
    _render_model_diagnostics(st)
    with st.expander("Current session JSON"):
        st.json(session.model_dump(mode="json"))


if __name__ == "__main__":
    main()
