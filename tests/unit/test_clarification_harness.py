"""Structural checks for the optional local Streamlit harness."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

_HARNESS_PATH = Path(__file__).parents[2] / "apps" / "clarification_harness.py"


def _load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("clarification_harness", _HARNESS_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_harness_message_ids_are_deterministic_and_session_scoped() -> None:
    harness = _load_harness()

    assert (
        harness._local_message_id(session_id="session-one", revision=2)
        == "local-clarification:session-one:answer:3"
    )
    assert harness._local_message_id(session_id="session-two", revision=2) != harness._local_message_id(
        session_id="session-one", revision=2
    )


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
    assert call_names.count("OpenAIClarificationPromptComposer") == 0
    assert call_names.count("OpenAIClarificationComposerConfig") == 0
    assert call_names.count("understand_request") == 1
    assert call_names.count("OpenAIIntentExtractor") == 2

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
    assert "OpenAIClarificationPromptComposer" not in submit_call_names
    assert "OpenAIClarificationComposerConfig" not in submit_call_names

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
    assert "OpenAIClarificationPromptComposer" not in initial_call_names
    assert "OpenAIClarificationComposerConfig" not in initial_call_names

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
    assert "OpenAIClarificationPromptComposer" not in json_start_call_names
    assert "OpenAIClarificationComposerConfig" not in json_start_call_names

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
    assert initial_helper_call_names.count("OpenAIIntentExtractor") == 2


def test_harness_renders_prompt_and_assumption_diagnostics() -> None:
    source = _HARNESS_PATH.read_text()

    assert "composition_source" in source
    assert "fallback_code" in source
    assert "prompt.issues" in source
    assert "assumption_disclosure" in source
    assert "Prompt composition: `none (session is ready or stopped)`" in source


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
    assert "OpenAIClarificationPromptComposer" not in branch_call_names
    assert "start_clarification" in branch_call_names
