"""Optional Streamlit event checks and downstream artifact invalidation."""

from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from award_agent.harness import pipeline

APP = Path(__file__).parents[2] / "apps/clarification_harness.py"


def _harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("award_harness_ui", APP)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_changed_binding_discards_all_downstream_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = _harness()
    st = SimpleNamespace(session_state={})
    monkeypatch.setattr(pipeline, "session_binding", lambda session: session.binding)
    session = SimpleNamespace(binding=("session", 0, "digest-one"))
    state = harness._sync_workflow(st, session)
    state.update(results=object(), bundle=object(), error="old error")
    assert harness._sync_workflow(st, session) is state
    session.binding = ("session", 1, "digest-two")
    assert harness._sync_workflow(st, session) == {"binding": session.binding}
    assert harness._sync_workflow(st, None) == {"binding": None}


def test_archive_contains_replay_response_bodies_and_stage_models() -> None:
    harness = _harness()
    root = Path(__file__).parents[2] / "evidence/provider-stage/saved-searches/runs/exact_business"
    from award_agent.cli.provider_results import ProviderInputBundle
    from award_agent.providers.contracts import ProviderResultSet
    from award_agent.providers.replay import ReplayTape

    bundle = ProviderInputBundle.model_validate_json((root / "bundle.json").read_bytes())
    result = ProviderResultSet.model_validate_json((root / "result.json").read_bytes())
    tape = ReplayTape.model_validate_json((root / "tape.json").read_bytes())
    content = harness._workflow_archive({
        "bundle": bundle,
        "providers": pipeline.ProviderRun(result, tape, {"runtime/body.json": b'{"source":true}'}),
    })
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert set(archive.namelist()) == {
            "bundle.json", "provider-result.json", "tape.json", "runtime/body.json",
        }
        assert ProviderInputBundle.model_validate_json(archive.read("bundle.json")) == bundle
        assert ReplayTape.model_validate_json(archive.read("tape.json")) == tape
        assert archive.read("runtime/body.json") == b'{"source":true}'


def test_streamlit_reruns_do_not_execute_pipeline_and_replay_requires_click(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    calls: list[str] = []

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network/stage execution without an explicit event")

    def replay(bundle: Any, settings: Any, tape: Any = None) -> Any:
        assert tape is not None
        calls.append(bundle.current_session_id)
        return iter(())

    for name in ("plan_session", "author", "run_from_ready"):
        monkeypatch.setattr(pipeline, name, forbidden)
    monkeypatch.setattr(pipeline, "acquire_and_rank", replay)
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    app.run()
    assert not app.exception and calls == []
    button = next(item for item in app.button if item.label == "Replay providers and run ranking (offline)")
    button.click().run()
    assert not app.exception and len(calls) == 1
    app.run()
    assert not app.exception and len(calls) == 1
    assert any("offline saved search" in item.value for item in app.info)
