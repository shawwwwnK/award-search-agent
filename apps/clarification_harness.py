"""Local, ephemeral Streamlit validation harness for ADR 0014 sessions.

Run with ``streamlit run apps/clarification_harness.py`` after installing the
optional ``harness`` dependency.  This module deliberately keeps Streamlit out
of the package dependencies and has no state beyond ``st.session_state``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from award_agent.clarification import (
    ClarificationCommandError,
    ClarificationInterpretationError,
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationComposerConfig,
    OpenAIClarificationInterpretationError,
    OpenAIClarificationInterpreterConfig,
    OpenAIClarificationPromptComposer,
    apply_clarification_answer,
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
    OpenAIExtractorConfig,
    OpenAIIntentExtractor,
    understand_request,
)

_SESSION_KEY = "clarification_session"
_ERROR_KEY = "clarification_harness_error"
_TELEMETRY_KEY = "clarification_harness_model_telemetry"
_PRIVATE_TRACE_KEY = "clarification_harness_private_local_traces"
_ANSWER_KEY_PREFIX = "clarification_answer"
_DEFAULT_TIMEZONE = "America/Los_Angeles"


def _local_message_id(*, session_id: str, revision: int) -> str:
    """Return a stable, session-scoped ID for the next local answer."""

    return f"local-clarification:{session_id}:answer:{revision + 1}"


def _show_error(st: object) -> None:
    """Render the latest local validation/controller/interpreter error."""

    error = st.session_state.get(_ERROR_KEY)  # type: ignore[attr-defined]
    if error:
        st.error(error)  # type: ignore[attr-defined]


def _record_error(st: object, message: str) -> None:
    """Retain and display an error in the same Streamlit rerun."""

    st.session_state[_ERROR_KEY] = message  # type: ignore[attr-defined]
    st.error(message)  # type: ignore[attr-defined]


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
    extraction_model: str,
    selector_model: str,
    composer: OpenAIClarificationPromptComposer,
) -> ClarificationSession:
    """Compose the frozen initial workflow with the additive session boundary."""

    request = RawRequest(
        text=request_text,
        context=RequestContext(reference_date=reference_date, timezone=timezone),
    )
    initial = understand_request(
        request,
        OpenAIIntentExtractor(OpenAIExtractorConfig(model=extraction_model)),
        OpenAIIntentExtractor(OpenAIExtractorConfig(model=selector_model)),
        NagerHolidayProvider(),
    )
    return start_clarification(initial, composer=composer)


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
            if isinstance(trace.get("error"), Mapping)
            and trace["error"].get("type")
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
    with st.expander("Clarification diagnostics", expanded=True):  # type: ignore[attr-defined]
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
    st.set_page_config(page_title="Clarification session harness", layout="wide")
    st.title("Clarification session harness")
    st.caption(
        "Local validation only: no persistence, search calls, or rerun-triggered model calls."
    )
    st.caption(
        "Named U.S. federal holidays in the initial request may use the existing Nager calendar "
        "boundary; no flight or award-inventory provider is called."
    )
    extraction_model = st.text_input(
        "Initial extraction model",
        value="gpt-5.6-luna",
        help="Explicit model for frozen initial non-temporal extraction.",
    )
    selector_model = st.text_input(
        "Temporal selector model",
        value="gpt-5.6-luna",
        help="Explicit model for frozen initial opaque temporal-candidate selection.",
    )
    clarification_model = st.text_input(
        "Clarification receiver model",
        value="gpt-5.6-luna",
        help="Interprets an answer only after Submit answer.",
    )
    composer_model = st.text_input(
        "Clarification composer model",
        value="gpt-5.6-luna",
        help="Authors each initial or post-reduction follow-up prompt.",
    )

    st.subheader("Start from a raw request")
    with st.form("initial-request"):
        request_text = st.text_area("Travel request", height=120)
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
            composer: OpenAIClarificationPromptComposer | None = None
            composer_error: BaseException | None = None
            try:
                composer = OpenAIClarificationPromptComposer(
                    OpenAIClarificationComposerConfig(model=composer_model),
                    capture_llm_io=True,
                )
                st.session_state[_SESSION_KEY] = _start_from_raw_request(
                    request_text=request_text,
                    reference_date=reference_date,
                    timezone=timezone,
                    extraction_model=extraction_model,
                    selector_model=selector_model,
                    composer=composer,
                )
            except Exception as exc:  # noqa: BLE001 - local harness must surface setup failures.
                composer_error = exc
                _record_error(
                    st,
                    f"Initial request was not accepted ({type(exc).__name__}): {exc}",
                )
            else:
                st.session_state.pop(_ERROR_KEY, None)
            finally:
                _record_model_diagnostics(
                    st,
                    event="initial_start",
                    stage="prompt_composer",
                    model=composer_model,
                    adapter=composer,
                    error=composer_error,
                )

    with st.expander("Or start from frozen RequestUnderstandingResult JSON"):
        raw_initial = st.text_area(
            "Frozen RequestUnderstandingResult JSON",
            help="Paste JSON produced by the frozen initial request-understanding workflow.",
            height=220,
        )
        start_from_json = st.button("Start from frozen JSON")
    if start_from_json:
        composer = None
        composer_error = None
        try:
            initial = RequestUnderstandingResult.model_validate(json.loads(raw_initial))
            composer = OpenAIClarificationPromptComposer(
                OpenAIClarificationComposerConfig(model=composer_model),
                capture_llm_io=True,
            )
            st.session_state[_SESSION_KEY] = start_clarification(initial, composer=composer)
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
    session = st.session_state.get(_SESSION_KEY)
    if session is None:
        return

    _render_model_diagnostics(st)

    revision = session.current_revision
    st.subheader(f"Session revision {revision.revision}")
    st.write(f"Status: `{revision.status.value}`")

    if revision.stop_reason is not None:
        st.write(f"Terminal reason: `{revision.stop_reason.value}`")

    _render_prompt_diagnostics(st, session)

    if revision.prompt is not None:
        st.subheader("Next clarification prompt")
        st.text(revision.prompt.message)
        _render_requirements(st, revision.prompt.requirements)

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
                composer: OpenAIClarificationPromptComposer | None = None
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
                    composer = OpenAIClarificationPromptComposer(
                        OpenAIClarificationComposerConfig(model=composer_model),
                        capture_llm_io=True,
                    )
                    transition = apply_clarification_answer(
                        session, command, interpreter, composer=composer
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
                    st.session_state[_SESSION_KEY] = transition.session
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
                        adapter=composer,
                        error=interpreter_error,
                    )
    else:
        st.success("Session is terminal.")
    with st.expander("Current session JSON"):
        st.json(session.model_dump(mode="json"))


if __name__ == "__main__":
    main()
