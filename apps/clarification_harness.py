"""Local, ephemeral Streamlit validation harness for ADR 0011 sessions.

Run with ``streamlit run apps/clarification_harness.py`` after installing the
optional ``harness`` dependency.  This module deliberately keeps Streamlit out
of the package dependencies and has no state beyond ``st.session_state``.
"""

from __future__ import annotations

import json

from award_agent.clarification import (
    ClarificationCommandError,
    ClarificationInterpretationError,
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationInterpretationError,
    OpenAIClarificationInterpreterConfig,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.domain import ClarificationAnswerCommand, RequestUnderstandingResult

_SESSION_KEY = "clarification_session"
_ERROR_KEY = "clarification_harness_error"


def _local_message_id(*, session_id: str, revision: int) -> str:
    """Return a stable, session-scoped ID for the next local answer."""

    return f"local-clarification:{session_id}:answer:{revision + 1}"


def _show_error(st: object) -> None:
    """Render the latest local validation/controller/interpreter error."""

    error = st.session_state.get(_ERROR_KEY)  # type: ignore[attr-defined]
    if error:
        st.error(error)  # type: ignore[attr-defined]


def _render_requirements(st: object, requirements: tuple[object, ...]) -> None:
    """Render the exact typed requirement objects sent to the interpreter."""

    st.caption(  # type: ignore[attr-defined]
        "Active typed blockers (the model receives only these and the answer message):"
    )
    st.json([requirement.model_dump(mode="json") for requirement in requirements])  # type: ignore[attr-defined]


def main() -> None:
    # Keeping this import local makes the harness dependency genuinely optional
    # for package users and the normal test suite.
    import streamlit as st

    st.set_page_config(page_title="Clarification session harness", layout="wide")
    st.title("Clarification session harness")
    st.caption(
        "Local validation only: no persistence, provider calls, or rerun-triggered model calls."
    )
    model = st.text_input(
        "Clarification model",
        value="gpt-5.6-luna",
        help="This model is selected explicitly and is used only after Submit answer.",
    )
    raw_initial = st.text_area(
        "Frozen RequestUnderstandingResult JSON",
        help="Paste JSON produced by the frozen initial request-understanding workflow.",
        height=220,
    )
    if st.button("Start session", type="primary"):
        try:
            initial = RequestUnderstandingResult.model_validate(json.loads(raw_initial))
            st.session_state[_SESSION_KEY] = start_clarification(initial)
        except (json.JSONDecodeError, ValueError) as exc:
            st.session_state[_ERROR_KEY] = f"Initial result was not accepted: {exc}"
        else:
            st.session_state.pop(_ERROR_KEY, None)

    _show_error(st)
    session = st.session_state.get(_SESSION_KEY)
    if session is None:
        return

    revision = session.current_revision
    st.subheader(f"Session revision {revision.revision}")
    st.write(f"Status: `{revision.status.value}`")

    if revision.stop_reason is not None:
        st.write(f"Terminal reason: `{revision.stop_reason.value}`")

    if revision.prompt is not None:
        st.subheader("Next deterministic prompt")
        st.text(revision.prompt.message)
        _render_requirements(st, revision.prompt.requirements)

        # A form is the sole answer submission route.  Code that constructs an
        # interpreter or invokes the controller is intentionally nested below
        # its explicit submit event, so ordinary Streamlit reruns cannot call a
        # model or change a session.
        with st.form("clarification-answer", clear_on_submit=True):
            answer = st.text_area("Answer")
            submitted = st.form_submit_button("Submit answer")
        if submitted:
            if not answer.strip():
                st.warning("Enter an answer before submitting.")
            else:
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
                        OpenAIClarificationInterpreterConfig(model=model)
                    )
                    transition = apply_clarification_answer(session, command, interpreter)
                except (
                    ClarificationCommandError,
                    ClarificationInterpretationError,
                    OpenAIClarificationInterpretationError,
                    ValueError,
                ) as exc:
                    # Do not assign a new session on any controller or model
                    # error.  The old revision remains visible and retryable.
                    st.session_state[_ERROR_KEY] = (
                        f"Answer was not applied ({type(exc).__name__}): {exc}"
                    )
                except Exception as exc:  # noqa: BLE001
                    # This includes local OpenAI-client setup failures.  Keep
                    # the same atomic UI rule for unexpected infrastructure
                    # errors while exposing their concrete class locally.
                    st.session_state[_ERROR_KEY] = (
                        f"Answer processing failed ({type(exc).__name__}): {exc}"
                    )
                else:
                    st.session_state[_SESSION_KEY] = transition.session
                    st.session_state.pop(_ERROR_KEY, None)
                    st.rerun()
    else:
        st.success("Session is terminal.")
    with st.expander("Current session JSON"):
        st.json(session.model_dump(mode="json"))


if __name__ == "__main__":
    main()
