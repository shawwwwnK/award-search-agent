from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from award_agent.clarification.controller import ClarificationTransition
from award_agent.cli import one_way_award_live_eval as live_cli
from award_agent.domain import RequestUnderstandingOutcome, RequestUnderstandingResult
from award_agent.evaluation import one_way_award_live


def test_fixed_v2_live_corpus_preflight_covers_required_multistep_cases() -> None:
    cases = one_way_award_live.preflight_one_way_award_live_cases()

    assert len(cases) == 12
    by_id = {case["id"]: case for case in cases}
    assert len(by_id["all_four_one_way_blockers_completed_in_three_turns"]["answers"]) == 3
    assert len(by_id["no_progress_stops_after_limit"]["answers"]) == 2
    for identifier in (
        "return_only_answer_stops_with_scope_notice",
        "duration_only_answer_stops_with_scope_notice",
        "departure_and_return_stops_without_partial_mutation",
    ):
        turn = by_id[identifier]["expected"]["turns"][0]
        assert turn["stop_reason"] == "unsupported_request_scope"
        assert turn["scope_notice_codes"] == ["one_way.return_or_duration"]
        assert turn["effective_request_unchanged"] is True


def test_live_preflight_rejects_nonfrozen_or_drifted_v2_corpus(tmp_path: Path) -> None:
    fixture = one_way_award_live.DEFAULT_ONE_WAY_AWARD_LIVE_FIXTURES
    payload = yaml.safe_load(fixture.read_text())
    payload["frozen"] = False
    invalid = tmp_path / "not-frozen.yaml"
    invalid.write_text(yaml.safe_dump(payload))

    with pytest.raises(one_way_award_live.OneWayAwardLiveFixtureError, match="frozen"):
        one_way_award_live.preflight_one_way_award_live_cases(invalid)
    payload["frozen"] = True
    payload["scenarios"].pop()
    invalid.write_text(yaml.safe_dump(payload))
    with pytest.raises(one_way_award_live.OneWayAwardLiveFixtureError, match="scenario count"):
        one_way_award_live.preflight_one_way_award_live_cases(invalid)


def test_live_cli_has_no_selector_model_option() -> None:
    with pytest.raises(SystemExit):
        live_cli._parser().parse_args(
            ["--model", "receiver", "--selector-model", "retired", "--output", "run.json"]
        )


def test_pending_initial_result_is_not_a_completed_clarification_input() -> None:
    pending = SimpleNamespace(outcome=SimpleNamespace(value="pending_retryable"))
    completed = SimpleNamespace(outcome=SimpleNamespace(value="completed"))

    assert one_way_award_live._is_pending_initial_result(pending) is True
    assert one_way_award_live._is_pending_initial_result(completed) is False


def test_live_runner_records_state_free_pending_without_starting_a_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenario = {
        "id": "pending",
        "input": "Find an award flight.",
        "context": {"reference_date": "2026-01-01", "timezone": "UTC"},
        "answers": ["October 5"],
        "expected": {
            "initial": {"action": "ask", "field": "departure", "unsupported_codes": []},
            "turns": [
                {
                    "status": "ready",
                    "stop_reason": None,
                    "blockers": [],
                    "scope_notice_codes": [],
                    "departure_state": "present",
                    "effective_request_unchanged": False,
                }
            ],
            "composer_call_count": 0,
        },
    }

    class Adapter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def take_usage(self) -> None:
            return None

        def take_call_traces(self) -> list[dict[str, Any]]:
            return []

    monkeypatch.setattr(one_way_award_live, "_load", lambda _path: ([scenario], {}))
    monkeypatch.setattr(one_way_award_live, "OpenAISemanticIntentInterpreter", Adapter)
    monkeypatch.setattr(one_way_award_live, "OpenAIClarificationPromptComposer", Adapter)
    monkeypatch.setattr(one_way_award_live, "OpenAIClarificationAnswerInterpreter", Adapter)
    monkeypatch.setattr(
        one_way_award_live,
        "understand_request",
        lambda *_args: RequestUnderstandingResult(
            outcome=RequestUnderstandingOutcome.PENDING_RETRYABLE,
            pending_detail="injected pending",
        ),
    )
    monkeypatch.setattr(
        one_way_award_live,
        "start_clarification",
        lambda *_args, **_kwargs: pytest.fail("pending initial result must not start a session"),
    )

    artifact = one_way_award_live.run_one_way_award_live_eval(
        model="test-model", trace_dir=tmp_path
    )

    assert artifact["records"][0]["status"] == "failed"
    assert artifact["records"][0]["initial"] == {
        "action": None,
        "field": None,
        "outcome": "pending_retryable",
        "unsupported_codes": [],
    }
    assert artifact["records"][0]["checks"]["initial"] is False


@dataclass(frozen=True)
class _Effective:
    departure_window: object | None = None
    serial: int = 0


class _FakeAdapter:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.calls = 0

    def take_usage(self) -> dict[str, int] | None:
        if not self.calls:
            return None
        calls = self.calls
        self.calls = 0
        return {
            "calls": calls,
            "captured_calls": calls,
            "missing_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def take_call_traces(self) -> list[dict[str, Any]]:
        return []


class _FakeSession:
    def __init__(self, scenario: dict[str, Any], session_id: str) -> None:
        self.scenario = scenario
        self.session_id = session_id
        self.turn_index = 0
        self.current_revision = _revision(
            status="awaiting_answer",
            stop_reason=None,
            blockers=_initial_blockers(scenario),
            scope_codes=[],
            effective=_Effective(),
            revision=0,
        )


def _initial_blockers(scenario: dict[str, Any]) -> list[str]:
    identifier = scenario["id"]
    if identifier == "all_four_one_way_blockers_completed_in_three_turns":
        return ["origin", "destination", "departure", "travelers"]
    return ["departure"]


def _revision(
    *,
    status: str,
    stop_reason: str | None,
    blockers: list[str],
    scope_codes: list[str],
    effective: _Effective,
    revision: int,
) -> SimpleNamespace:
    prompt = (
        SimpleNamespace(
            prompt_id=f"prompt-{revision}",
            requirements=[SimpleNamespace(requirement_id=blocker) for blocker in blockers],
        )
        if status == "awaiting_answer"
        else None
    )
    outcome = SimpleNamespace(scope_notices=[SimpleNamespace(code=code) for code in scope_codes])
    return SimpleNamespace(
        status=SimpleNamespace(value=status),
        stop_reason=None if stop_reason is None else SimpleNamespace(value=stop_reason),
        prompt=prompt,
        outcome=outcome,
        effective_request=effective,
        revision=revision,
    )


def test_live_runner_records_typed_oracles_and_redacts_fixture_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cases = {item["id"]: item for item in one_way_award_live.preflight_one_way_award_live_cases()}
    scenario_iterator = iter(cases.values())

    def fake_understand(raw: object, *_args: object, **_kwargs: object) -> SimpleNamespace:
        scenario = next(scenario_iterator)
        assert raw.text == scenario["input"]
        expected = scenario["expected"]["initial"]
        return SimpleNamespace(
            scenario=scenario,
            clarification=SimpleNamespace(
                action=SimpleNamespace(value=expected["action"]), field=expected["field"]
            ),
            parsed_request=SimpleNamespace(
                unsupported_request_parts=[
                    SimpleNamespace(code=SimpleNamespace(value=code))
                    for code in expected["unsupported_codes"]
                ]
            ),
        )

    def fake_start(
        result: SimpleNamespace, *, session_id: str, composer: _FakeAdapter
    ) -> _FakeSession:
        composer.calls += 1
        return _FakeSession(result.scenario, session_id)

    def fake_apply(
        session: _FakeSession,
        _command: object,
        _interpreter: object,
        *,
        composer: _FakeAdapter,
    ) -> ClarificationTransition:
        expected = session.scenario["expected"]["turns"][session.turn_index]
        before = session.current_revision.effective_request
        departure = (
            object() if expected["departure_state"] == "present" else before.departure_window
        )
        effective = (
            before
            if expected["effective_request_unchanged"]
            else _Effective(departure_window=departure, serial=before.serial + 1)
        )
        if expected["status"] == "awaiting_answer":
            composer.calls += 1
        session.turn_index += 1
        session.current_revision = _revision(
            status=expected["status"],
            stop_reason=expected["stop_reason"],
            blockers=expected["blockers"],
            scope_codes=expected["scope_notice_codes"],
            effective=effective,
            revision=session.turn_index,
        )
        return ClarificationTransition(session=session, revision=session.current_revision)

    monkeypatch.setattr(one_way_award_live, "OpenAISemanticIntentInterpreter", _FakeAdapter)
    monkeypatch.setattr(one_way_award_live, "OpenAIClarificationPromptComposer", _FakeAdapter)
    monkeypatch.setattr(one_way_award_live, "OpenAIClarificationAnswerInterpreter", _FakeAdapter)
    monkeypatch.setattr(one_way_award_live, "understand_request", fake_understand)
    monkeypatch.setattr(one_way_award_live, "start_clarification", fake_start)
    monkeypatch.setattr(one_way_award_live, "apply_clarification_answer", fake_apply)

    artifact = one_way_award_live.run_one_way_award_live_eval(
        model="test-model", trace_dir=tmp_path / "private-traces"
    )

    assert artifact["schema_version"] == "one_way_award_live_eval_v2"
    assert artifact["fixture"]["scenario_count"] == 12
    assert len(artifact["fixture"]["sha256"]) == 64
    assert artifact["semantic_contract"]["adapter_contract_version"] == "openai_semantic_intent_wire_v2"
    assert len(artifact["semantic_contract"]["adapter_sha256"]) == 64
    assert len(artifact["semantic_contract"]["strict_response_schema_sha256"]) == 64
    assert artifact["summary"] == {
        "runs": 12,
        "passed": 12,
        "failed": 0,
        "errors": 0,
        "mechanically_completed": True,
    }
    public = json.dumps(artifact)
    assert "October 5" not in public
    assert "Cancel this request" not in public
    assert all(
        record["private_trace"]["path"].startswith(str(tmp_path)) for record in artifact["records"]
    )
