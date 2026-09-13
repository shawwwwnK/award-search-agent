from pathlib import Path
from typing import Any

import pytest

from award_agent.cli import intent_eval
from award_agent.domain import RequestUnderstandingOutcome, RequestUnderstandingResult


def _corpus() -> intent_eval._PreflightedIntentCorpus:
    return intent_eval._PreflightedIntentCorpus(
        contract_version="intent_behavior_v1",
        fixture_sha256="a" * 64,
        scenarios=[
            {
                "id": "one",
                "input": "secret request",
                "context": {"reference_date": "2026-01-01", "timezone": "UTC"},
                "oracle": {
                    "acceptable_actions": ["clarification"],
                    "must_ground": [],
                    "must_remain_blocked": [],
                    "properties": {},
                    "forbidden_outcomes": [],
                },
            }
        ],
    )


def test_eval_parser_constructs_one_receiver_and_has_no_selector_option() -> None:
    args = intent_eval._parser().parse_args(["--model", "receiver", "--output", "run.json"])
    assert args.model == "receiver"
    with pytest.raises(SystemExit):
        intent_eval._parser().parse_args(
            ["--model", "receiver", "--selector-model", "retired", "--output", "run.json"]
        )


def test_eval_constructs_only_one_semantic_receiver_and_emits_receiver_telemetry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instances: list[Any] = []

    class FakeInterpreter:
        def __init__(self, config: Any, *, capture_llm_io: bool) -> None:
            assert config.model == "receiver"
            assert capture_llm_io is True
            instances.append(self)

        def reset_capture(self) -> None:
            pass

        def take_usage(self) -> dict[str, int]:
            return {
                "calls": 1,
                "captured_calls": 1,
                "missing_calls": 0,
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
            }

        def take_call_traces(self) -> list[dict[str, Any]]:
            return [{"stage": "initial_semantic_intent", "latency_seconds": 0.1}]

    monkeypatch.setattr(intent_eval, "OpenAISemanticIntentInterpreter", FakeInterpreter)
    monkeypatch.setattr(
        intent_eval,
        "understand_request",
        lambda *_args: RequestUnderstandingResult.model_construct(
            outcome=RequestUnderstandingOutcome.COMPLETED
        ),
    )
    monkeypatch.setattr(intent_eval, "_score_result", lambda *_args: [])
    monkeypatch.setattr(intent_eval, "_preflight_one_way_award_cases", lambda _path: _corpus())

    artifact = intent_eval.run_eval("receiver", tmp_path / "cases.yaml", 1, trace_dir=None)

    assert len(instances) == 1
    assert artifact["schema_version"] == 9
    assert artifact["architecture"] == "one_llm_semantic_receiver"
    assert set(artifact["stage_telemetry"]) == {"semantic_receiver"}
    assert artifact["stage_telemetry"]["semantic_receiver"]["attempts"] == 1
    contract = artifact["semantic_contract"]
    assert contract["adapter_contract_version"] == "openai_semantic_intent_wire_v2"
    assert len(contract["adapter_sha256"]) == 64
    assert len(contract["strict_response_schema_sha256"]) == 64
    assert (
        artifact["stage_telemetry"]["semantic_receiver"]["strict_response_schema_sha256"]
        == contract["strict_response_schema_sha256"]
    )
    assert artifact["summary"]["operational_outcomes"] == {
        "ordinary_language_pending": {"numerator": 0, "denominator": 1},
        "fault_injection_pending": {
            "numerator": 1,
            "denominator": 1,
        },
    }


def test_eval_public_artifact_redacts_request_and_private_sidecar_keeps_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeInterpreter:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def reset_capture(self) -> None:
            pass

        def take_usage(self) -> None:
            return None

        def take_call_traces(self) -> list[dict[str, Any]]:
            return [{"stage": "initial_semantic_intent", "payload": "secret request"}]

    monkeypatch.setattr(intent_eval, "OpenAISemanticIntentInterpreter", FakeInterpreter)
    monkeypatch.setattr(
        intent_eval,
        "understand_request",
        lambda *_args: RequestUnderstandingResult.model_construct(
            outcome=RequestUnderstandingOutcome.COMPLETED
        ),
    )
    monkeypatch.setattr(intent_eval, "_score_result", lambda *_args: [])
    monkeypatch.setattr(intent_eval, "_preflight_one_way_award_cases", lambda _path: _corpus())

    artifact = intent_eval.run_eval("receiver", tmp_path / "cases.yaml", 1, trace_dir=tmp_path)

    assert "secret request" not in str(artifact)
    trace = Path(artifact["results"][0]["private_trace"]["path"])
    assert "secret request" in trace.read_text()


def test_pending_is_not_an_accepted_action_for_ordinary_language_oracle() -> None:
    result = RequestUnderstandingResult(
        outcome=RequestUnderstandingOutcome.PENDING_RETRYABLE,
        pending_detail="injected pending",
    )
    oracle = {
        "acceptable_actions": ["clarification"],
        "must_ground": [],
        "must_remain_blocked": [],
        "properties": {},
        "forbidden_outcomes": [],
    }

    checks = intent_eval._score_result(oracle, result)

    assert checks == [
        {"name": "action", "passed": False},
        {"name": "pending_is_state_free", "passed": True},
    ]


def test_pending_fault_cannot_be_success_shaped() -> None:
    result = RequestUnderstandingResult(
        outcome=RequestUnderstandingOutcome.PENDING_RETRYABLE,
        pending_detail="injected pending",
    )

    assert intent_eval._forbidden(result, "success_shaped_model_failure") is False
    assert intent_eval._fault_injection_pending_metrics() == {"numerator": 1, "denominator": 1}
