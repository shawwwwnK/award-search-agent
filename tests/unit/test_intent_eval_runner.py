from pathlib import Path
from typing import Any, Literal

import pytest

from award_agent.cli import intent_eval
from award_agent.domain import RequestUnderstandingResult
from award_agent.intent.evidence import TemporalResolutionValidationError
from award_agent.intent.model_views import NonTemporalIntentExtraction, TemporalSelectorOutput


def test_eval_parser_requires_independent_selector_model() -> None:
    with pytest.raises(SystemExit):
        intent_eval._parser().parse_args(["--model", "pass-one", "--output", "run.json"])

    args = intent_eval._parser().parse_args(
        ["--model", "pass-one", "--selector-model", "luna", "--output", "run.json"]
    )
    assert args.model == "pass-one"
    assert args.selector_model == "luna"
    with pytest.raises(SystemExit):
        intent_eval._parser().parse_args(
            [
                "--model",
                "pass-one",
                "--selector-model",
                "luna",
                "--strategy",
                "retired",
                "--output",
                "run.json",
            ]
        )


def test_eval_constructs_only_pass_one_and_selector_and_emits_v6_telemetry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instances: list[Any] = []

    class FakeExtractor:
        def __init__(self, *, config: Any, capture_llm_io: bool) -> None:
            assert capture_llm_io is True
            self.model = config.model
            self.calls: list[dict[str, Any]] = []
            instances.append(self)

        def reset_capture(self) -> None:
            self.calls = []

        def extract_non_temporal(self, _input: object) -> NonTemporalIntentExtraction:
            self.calls.append({"stage": "compiler_non_temporal_pass_one", "latency_seconds": 0.1})
            return NonTemporalIntentExtraction()

        def select_candidates(self, _input: object) -> TemporalSelectorOutput:
            self.calls.append({"stage": "temporal_candidate_selector", "latency_seconds": 0.2})
            return TemporalSelectorOutput(selected_candidates=[])

        def take_usage(self) -> None:
            return None

        def take_call_traces(self) -> list[dict[str, Any]]:
            return [
                {
                    "stage": (
                        "compiler_non_temporal_pass_one"
                        if self.model == "pass-one"
                        else "temporal_candidate_selector"
                    ),
                    "latency_seconds": 0.1,
                }
            ]

    def fake_understand(
        _request: object,
        pass_one: FakeExtractor,
        selector: FakeExtractor,
        _holiday_provider: object,
    ) -> RequestUnderstandingResult:
        pass_one.extract_non_temporal(object())
        selector.select_candidates(object())
        return RequestUnderstandingResult.model_construct()

    cases = tmp_path / "cases.yaml"
    cases.write_text(
        "scenarios:\n  - id: one\n    status: ready\n    input: Fly\n    context: {reference_date: '2026-01-01', timezone: UTC}\n    expected: {}\n"
    )
    monkeypatch.setattr(intent_eval, "OpenAIIntentExtractor", FakeExtractor)
    monkeypatch.setattr(intent_eval, "understand_request", fake_understand)
    monkeypatch.setattr(intent_eval, "_score_result", lambda _expected, _result: [])

    artifact = intent_eval.run_eval("pass-one", cases, 1, selector_model="luna", trace_dir=None)

    assert [instance.model for instance in instances] == ["pass-one", "luna"]
    assert artifact["schema_version"] == 6
    assert artifact["architecture"] == "selector_only"
    assert set(artifact["stage_telemetry"]) == {"pass_one", "selector"}
    assert artifact["stage_telemetry"]["pass_one"]["attempts"] == 1
    assert artifact["stage_telemetry"]["selector"]["attempts"] == 1


@pytest.mark.parametrize(
    ("stage", "code"),
    [
        ("temporal_graph_validation", "unknown_anchor_id"),
        ("temporal_dependency_validation", "unresolved_dependency"),
    ],
)
def test_eval_preserves_structured_compiler_validation_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: Literal["temporal_graph_validation", "temporal_dependency_validation"],
    code: str,
) -> None:
    class FakeExtractor:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def reset_capture(self) -> None:
            pass

        def take_usage(self) -> None:
            return None

        def take_call_traces(self) -> list[dict[str, Any]]:
            return []

    def fail_compiler(*_args: object) -> RequestUnderstandingResult:
        raise TemporalResolutionValidationError(
            "compiler validation failed", stage=stage, error_code=code
        )

    monkeypatch.setattr(intent_eval, "OpenAIIntentExtractor", FakeExtractor)
    monkeypatch.setattr(intent_eval, "understand_request", fail_compiler)
    monkeypatch.setattr(
        intent_eval,
        "_load_ready_scenarios",
        lambda _path: [
            {
                "id": "one",
                "input": "Fly",
                "context": {"reference_date": "2026-01-01", "timezone": "UTC"},
                "expected": {},
            }
        ],
    )

    artifact = intent_eval.run_eval(
        "pass-one", tmp_path / "unused.yaml", 1, selector_model="luna", trace_dir=None
    )

    record = artifact["results"][0]
    assert record["structured_error"] == {
        "stage": stage,
        "error_code": code,
        "relation_index": None,
        "constraint_index": None,
        "selected_relation_kind": None,
        "collection": None,
        "missing_fields": (),
        "contradictory_fields": (),
        "evidence_id": None,
        "reference_id": None,
        "validation_cause": "compiler validation failed",
    }
    assert record["failure_stage"] == stage
    assert record["failure_code"] == code
