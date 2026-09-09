"""Structural checks for the optional local Streamlit harness."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType

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


def test_harness_model_path_is_confined_to_explicit_form_submit() -> None:
    tree = ast.parse(_HARNESS_PATH.read_text())
    call_names = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert call_names.count("apply_clarification_answer") == 1
    assert call_names.count("OpenAIClarificationAnswerInterpreter") == 1

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
