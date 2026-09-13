"""Structural checks for the optional local Streamlit harness."""

from __future__ import annotations

import ast
import importlib.util
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace

from award_agent.clarification.calendar_plan import CalendarDay, LiteralIntervalOperation
from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.clarification.controller import apply_clarification_answer
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationSemanticFact,
)
from award_agent.clarification.semantic import SemanticTarget
from award_agent.domain import (
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
    ClarificationSessionStatus,
    DateWindow,
    DateWindowPrecision,
    LocationKind,
    LocationRef,
    MessageSpan,
    ParsedRequest,
    RequestContext,
    RequestUnderstandingOutcome,
    RequestUnderstandingResult,
    UnknownField,
    UnknownReason,
)

_HARNESS_PATH = Path(__file__).parents[2] / "apps" / "clarification_harness.py"


def _load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("clarification_harness", _HARNESS_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeComposer:
    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        return ClarificationPromptComposition(
            question_items=tuple(
                ClarificationQuestionItem(
                    requirement_id=requirement.requirement_id,
                    issue_ids=tuple(
                        issue.issue_id
                        for issue in input.issues
                        if issue.requirement_id == requirement.requirement_id
                    ),
                    question=f"Question for {requirement.requirement_id}?",
                )
                for requirement in input.requirements
            )
        )


class _FakeAnswerInterpreter:
    def __init__(self, interpretation: ClarificationAnswerInterpretation) -> None:
        self.interpretation = interpretation

    def interpret(self, _input: object) -> ClarificationAnswerInterpretation:
        return self.interpretation


def _initial_result(*, unknowns: list[UnknownField]) -> RequestUnderstandingResult:
    parsed = ParsedRequest(
        raw_text="Find an award seat from SFO to Tokyo",
        context=RequestContext(reference_date=date(2026, 9, 11), timezone="UTC"),
        travelers=1,
        origins=[LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        departure_expression=None,
        departure_window=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=unknowns,
        conflicts=[],
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=(ClarificationAction.ASK if unknowns else ClarificationAction.NONE),
            field="departure" if unknowns else None,
            question="When would you like to depart?" if unknowns else None,
        ),
    )


def test_harness_message_ids_are_deterministic_and_session_scoped() -> None:
    harness = _load_harness()

    assert (
        harness._local_message_id(session_id="session-one", revision=2)
        == "local-clarification:session-one:answer:3"
    )
    assert harness._local_message_id(
        session_id="session-two", revision=2
    ) != harness._local_message_id(session_id="session-one", revision=2)


def test_completed_incomplete_initial_result_starts_an_awaiting_answer_session() -> None:
    harness = _load_harness()
    initial = _initial_result(
        unknowns=[
            UnknownField(
                field="departure",
                reason=UnknownReason.MISSING,
                detail="departure is not stated",
            )
        ]
    )

    session = harness._start_from_initial_result(initial, composer=_FakeComposer())

    assert session is not None
    assert session.current_revision.status is ClarificationSessionStatus.AWAITING_ANSWER
    assert session.current_revision.prompt is not None
    assert session.current_revision.prompt.requirements[0].requirement_id == "departure"


def test_harness_session_answer_resolves_initial_blocker_and_reaches_ready() -> None:
    harness = _load_harness()
    session = harness._start_from_initial_result(
        _initial_result(
            unknowns=[
                UnknownField(
                    field="departure",
                    reason=UnknownReason.MISSING,
                    detail="departure is not stated",
                )
            ]
        ),
        composer=_FakeComposer(),
    )
    assert session is not None
    prompt = session.current_revision.prompt
    assert prompt is not None
    answer = "October 6"
    start = answer.index("October 6")
    interpretation = ClarificationAnswerInterpretation(
        facts=(
            ClarificationSemanticFact(
                fact_id="departure",
                span=MessageSpan(
                    message_id="answer-1",
                    start=start,
                    end=start + len("October 6"),
                    text="October 6",
                ),
                target=SemanticTarget.DEPARTURE_WINDOW,
                calendar_operation=LiteralIntervalOperation(start=CalendarDay(month=10, day=6)),
            ),
        )
    )
    transition = apply_clarification_answer(
        session,
        ClarificationAnswerCommand(
            session_id=session.session_id,
            expected_revision=session.current_revision.revision,
            prompt_id=prompt.prompt_id,
            message_id="answer-1",
            text=answer,
        ),
        _FakeAnswerInterpreter(interpretation),
    )

    assert transition.revision.status is ClarificationSessionStatus.READY
    assert transition.revision.effective_request.departure_window == DateWindow(
        start=date(2026, 10, 6),
        end=date(2026, 10, 6),
        precision=DateWindowPrecision.EXACT,
        raw_text="October 6",
    )
    assert len(transition.session.revisions) == 2


def test_completed_ready_initial_result_starts_a_ready_session() -> None:
    harness = _load_harness()
    session = harness._start_from_initial_result(
        _initial_result(unknowns=[]), composer=_FakeComposer()
    )

    assert session is not None
    assert session.current_revision.status is ClarificationSessionStatus.READY
    assert session.current_revision.prompt is None
    assert len(session.revisions) == 1


def test_harness_renders_effective_request_and_revision_history() -> None:
    harness = _load_harness()
    session = harness._start_from_initial_result(
        _initial_result(unknowns=[]), composer=_FakeComposer()
    )
    assert session is not None

    class FakeStreamlit:
        def __init__(self) -> None:
            self.subheaders: list[str] = []
            self.json_values: list[object] = []

        def subheader(self, value: str) -> None:
            self.subheaders.append(value)

        def json(self, value: object) -> None:
            self.json_values.append(value)

    st = FakeStreamlit()
    harness._render_session_state(st, session)

    assert st.subheaders == ["Effective request", "Clarification history"]
    assert st.json_values[0]["travelers"] == 1  # type: ignore[index]
    assert len(st.json_values[1]) == 1  # type: ignore[arg-type]


def test_pending_initial_result_is_sessionless_and_clears_prior_session() -> None:
    harness = _load_harness()

    class FakeStreamlit:
        def __init__(self) -> None:
            self.session_state: dict[str, object] = {
                harness._SESSION_KEY: object(),
                harness._COMPOSITION_PENDING_KEY: object(),
            }

    st = FakeStreamlit()
    harness._set_initial_pending(
        st,
        request_text="Find two award seats from SFO to BKK on October 5",
        reference_date=date(2026, 9, 11),
        timezone="America/Los_Angeles",
        intent_model="receiver",
        composer_model="composer",
    )

    assert (
        harness._start_from_initial_result(
            RequestUnderstandingResult(
                outcome=RequestUnderstandingOutcome.PENDING_RETRYABLE,
                pending_detail="provider unavailable",
            ),
            composer=_FakeComposer(),
        )
        is None
    )
    assert harness._SESSION_KEY not in st.session_state
    assert harness._COMPOSITION_PENDING_KEY not in st.session_state
    assert harness._INITIAL_PENDING_KEY in st.session_state


def test_harness_keeps_streamlit_import_lazy() -> None:
    tree = ast.parse(_HARNESS_PATH.read_text())

    assert not any(
        isinstance(node, ast.Import) and any(alias.name == "streamlit" for alias in node.names)
        for node in tree.body
    )
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module == "streamlit" for node in tree.body
    )


def test_harness_loads_the_local_environment_without_exposing_credentials() -> None:
    tree = ast.parse(_HARNESS_PATH.read_text())
    main = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    call_names = [
        node.func.id
        for node in ast.walk(main)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]

    assert call_names.count("load_dotenv") == 1
    assert "OPENAI_API_KEY" not in _HARNESS_PATH.read_text()


def test_harness_model_paths_are_confined_to_explicit_form_submissions() -> None:
    tree = ast.parse(_HARNESS_PATH.read_text())
    call_names = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert call_names.count("apply_clarification_answer") == 1
    assert call_names.count("OpenAIClarificationAnswerInterpreter") == 1
    assert call_names.count("OpenAIClarificationPromptComposer") == 5
    assert call_names.count("OpenAIClarificationComposerConfig") == 5
    assert call_names.count("understand_request") == 1
    assert call_names.count("OpenAISemanticIntentInterpreter") == 1

    submit_branch = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "submitted"
    )
    submit_call_names = [
        node.func.id
        for node in ast.walk(submit_branch)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "apply_clarification_answer" in submit_call_names
    assert "OpenAIClarificationAnswerInterpreter" in submit_call_names
    assert "OpenAIClarificationPromptComposer" in submit_call_names
    assert "OpenAIClarificationComposerConfig" in submit_call_names

    initial_submit_branch = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "initial_submitted"
    )
    initial_call_names = [
        node.func.id
        for node in ast.walk(initial_submit_branch)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "_start_from_raw_request" in initial_call_names
    assert "OpenAIClarificationPromptComposer" in initial_call_names
    assert "OpenAIClarificationComposerConfig" in initial_call_names

    json_start_branch = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "start_from_json"
    )
    json_start_call_names = [
        node.func.id
        for node in ast.walk(json_start_branch)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "OpenAIClarificationPromptComposer" in json_start_call_names
    assert "OpenAIClarificationComposerConfig" in json_start_call_names

    initial_helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_start_from_raw_request"
    )
    initial_helper_call_names = [
        node.func.id
        for node in ast.walk(initial_helper)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "understand_request" in initial_helper_call_names
    assert initial_helper_call_names.count("OpenAISemanticIntentInterpreter") == 1


def test_harness_composition_retry_uses_only_a_fresh_composer() -> None:
    tree = ast.parse(_HARNESS_PATH.read_text())
    retry_branch = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "retry_composition"
    )
    retry_call_names = [
        node.func.id
        for node in ast.walk(retry_branch)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]

    assert "retry_prompt_composition" in retry_call_names
    assert "OpenAIClarificationPromptComposer" in retry_call_names
    assert "OpenAIClarificationComposerConfig" in retry_call_names
    assert "OpenAIClarificationAnswerInterpreter" not in retry_call_names
    assert "apply_clarification_answer" not in retry_call_names

    source = _HARNESS_PATH.read_text()
    assert "_COMPOSITION_PENDING_KEY" in source
    assert "st.session_state.pop(_COMPOSITION_PENDING_KEY, None)" in source
    assert "your answer remains applied" in source


def test_harness_renders_prompt_and_assumption_diagnostics() -> None:
    source = _HARNESS_PATH.read_text()

    assert "composition_source" in source
    assert "fallback_code" in source
    assert "prompt.issues" in source
    assert "assumption_disclosure" in source
    assert "Prompt composition: `none (session is ready or stopped)`" in source


def test_harness_renders_terminal_scope_guidance_prominently() -> None:
    harness = _load_harness()

    class FakeStreamlit:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def subheader(self, value: str) -> None:
            self.calls.append(("subheader", value))

        def error(self, value: str) -> None:
            self.calls.append(("error", value))

    st = FakeStreamlit()
    harness._render_terminal_message(st, "Submit the return leg as a separate one-way request.")

    assert st.calls == [
        ("subheader", "One-way award request guidance"),
        ("error", "Submit the return leg as a separate one-way request."),
    ]

    empty = FakeStreamlit()
    harness._render_terminal_message(empty, None)
    assert empty.calls == []


def test_harness_ui_is_labeled_for_the_active_initial_semantic_and_one_way_boundaries() -> None:
    source = _HARNESS_PATH.read_text()

    assert "ADR 0017 semantic-intent" in source
    assert "ADR 0016 one-way award" in source
    assert "One-way award clarification harness" in source
    assert "Start from ADR 0017 JSON" in source
    assert "cash-only " in source
    assert "requests are not supported" in source


def test_harness_renders_initial_receiver_diagnostics_without_a_session() -> None:
    source = _HARNESS_PATH.read_text()

    assert "_is_initial_intent_pending" in source
    assert "Initial interpretation is temporarily unavailable" in source
    assert "_INITIAL_PENDING_KEY" in source
    assert "_set_initial_pending" in source
    assert "Retry initial interpretation" in source
    assert "Status code:" in source
    assert "if st.session_state.get(_INITIAL_PENDING_KEY) is not None" in source
    assert "_render_model_diagnostics(st)\n        return" in source


def test_harness_initial_pending_preserves_context_and_hides_raw_detail() -> None:
    harness = _load_harness()

    class FakeStreamlit:
        def __init__(self) -> None:
            self.session_state: dict[str, object] = {
                harness._ERROR_KEY: "private validation details",
            }
            self.calls: list[tuple[str, str]] = []

        def warning(self, value: str) -> None:
            self.calls.append(("warning", value))

        def write(self, value: str) -> None:
            self.calls.append(("write", value))

        def caption(self, value: str) -> None:
            self.calls.append(("caption", value))

        def button(self, value: str) -> bool:
            self.calls.append(("button", value))
            return False

    st = FakeStreamlit()
    harness._set_initial_pending(
        st,
        request_text="Find two award seats from SFO to BKK on October 5",
        reference_date=date(2026, 9, 11),
        timezone="America/Los_Angeles",
        intent_model="receiver",
        composer_model="composer",
    )
    harness._render_initial_pending(st)

    pending = st.session_state[harness._INITIAL_PENDING_KEY]
    assert pending["request_text"] == "Find two award seats from SFO to BKK on October 5"  # type: ignore[index]
    assert pending["reference_date"] == "2026-09-11"  # type: ignore[index]
    assert pending["timezone"] == "America/Los_Angeles"  # type: ignore[index]
    assert pending["stage"] == "semantic_intent"  # type: ignore[index]
    assert pending["code"] == "initial_intent_retryable"  # type: ignore[index]
    assert harness._ERROR_KEY not in st.session_state
    rendered = " ".join(value for _, value in st.calls)
    assert "private validation details" not in rendered
    assert "No clarification session was created" in rendered
    assert "Retry initial interpretation" in rendered


def test_harness_model_diagnostics_capture_failed_stage_and_keep_traces_private() -> None:
    harness = _load_harness()

    class FakeStreamlit:
        def __init__(self) -> None:
            self.session_state: dict[str, object] = {}

    class FakeAdapter:
        config = SimpleNamespace(model="gpt-5.6-luna")

        def take_call_traces(self) -> list[dict[str, object]]:
            return [
                {
                    "stage": "clarification_prompt_composition",
                    "latency_seconds": 0.25,
                    "error": {"type": "RuntimeError", "message": "local failure"},
                }
            ]

        def take_usage(self) -> dict[str, int]:
            return {
                "calls": 1,
                "captured_calls": 0,
                "missing_calls": 1,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }

    st = FakeStreamlit()
    harness._record_model_diagnostics(
        st,
        event="json_start",
        stage="prompt_composer",
        model="gpt-5.6-luna",
        adapter=FakeAdapter(),
    )

    record = st.session_state[harness._TELEMETRY_KEY][0]  # type: ignore[index]
    assert record["status"] == "error"
    assert record["error_type"] == "RuntimeError"
    assert record["calls"] == 1
    assert record["latency_seconds"] == 0.25
    assert record["private_local_trace_count"] == 1
    private = st.session_state[harness._PRIVATE_TRACE_KEY][0]  # type: ignore[index]
    assert private["privacy"] == "private_local_only"
    assert "clarification_harness_model_telemetry" not in record


def test_harness_frozen_json_start_surfaces_setup_failures_without_replacing_session() -> None:
    tree = ast.parse(_HARNESS_PATH.read_text())
    json_start_branch = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "start_from_json"
    )
    handlers = [node for node in ast.walk(json_start_branch) if isinstance(node, ast.ExceptHandler)]
    assert any(
        isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
        for handler in handlers
    )
    branch_call_names = [
        node.func.id
        for node in ast.walk(json_start_branch)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "_record_error" in branch_call_names
    assert "OpenAIClarificationPromptComposer" in branch_call_names
    assert "_start_from_initial_result" in branch_call_names
