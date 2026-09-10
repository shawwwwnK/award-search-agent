from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.cli.clarification_composer_experiment import _parser
from award_agent.evaluation.clarification_composer_experiment import (
    DEFAULT_COMPOSER_EXPERIMENT_FIXTURES,
    ClarificationComposerExperimentError,
    _load_bundles,
    run_clarification_composer_experiment,
)


class _FakeComposer:
    def __init__(self) -> None:
        self._traces: list[dict[str, Any]] = []

    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        questions = {
            "origin": "Which airport are you leaving from?",
            "destination": "Where would you like to go?",
            "departure": "When would you like to depart?",
            "return_or_duration": "When do you return, or how long is the trip?",
            "travelers": "How many travelers are going?",
            "conflict": "Which date choice should I use?",
        }
        self._traces.append({"latency_seconds": 0.01, "error": None})
        return ClarificationPromptComposition(
            question_items=tuple(
                ClarificationQuestionItem(
                    requirement_id=requirement.requirement_id,
                    issue_ids=tuple(
                        issue.issue_id
                        for issue in input.issues
                        if issue.requirement_id == requirement.requirement_id
                    ),
                    question=questions[requirement.kind.value],
                )
                for requirement in input.requirements
            )
        )

    def take_usage(self) -> dict[str, int]:
        return {
            "calls": 1,
            "captured_calls": 1,
            "missing_calls": 0,
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        }

    def take_call_traces(self) -> list[dict[str, Any]]:
        traces, self._traces = self._traces, []
        return traces


def test_composer_experiment_fixture_has_balanced_frozen_input_kinds() -> None:
    bundles, _ = _load_bundles(DEFAULT_COMPOSER_EXPERIMENT_FIXTURES)

    assert len(bundles) >= 8
    assert {issue.kind.value for bundle in bundles for issue in bundle.issues} == {
        "missing",
        "ambiguous",
        "unsupported",
        "conflict",
    }


def test_composer_experiment_requires_three_trials_and_valid_fixture(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least three"):
        run_clarification_composer_experiment(trials=2)

    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("contract_version: v1\nbundles: []\n")
    with pytest.raises(ClarificationComposerExperimentError, match="at least eight"):
        _load_bundles(invalid)


def test_composer_experiment_is_paired_randomized_and_redacted(tmp_path: Path) -> None:
    artifact = run_clarification_composer_experiment(
        trials=3,
        seed=4,
        trace_dir=tmp_path / "private-traces",
        composer_factory=lambda _model: _FakeComposer(),
    )

    encoded = json.dumps(artifact)
    assert "early or late oct" not in encoded
    assert artifact["fixture"]["redacted"] is True
    assert artifact["randomization"]["method"] == "per-pair shuffled arm order"
    assert artifact["llm_trace"]["sidecars"] == 2 * 3 * artifact["fixture"]["bundle_count"]
    assert len(list((tmp_path / "private-traces").rglob("*.json"))) == artifact["llm_trace"]["sidecars"]
    assert set(artifact["summary"]["arms"]) == {"luna", "gpt_4o_mini"}
    assert artifact["summary"]["paired_analysis"]["latency_seconds_mini_minus_luna"]["pairs"] == (
        3 * artifact["fixture"]["bundle_count"]
    )
    assert artifact["summary"]["decision"] == "not_decided_by_evaluator"


def test_composer_experiment_cli_defaults_to_preregistered_arms() -> None:
    args = _parser().parse_args(["--output", "out.json"])

    assert args.luna_model == "gpt-5.6-luna"
    assert args.gpt_4o_mini_model == "gpt-4o-mini"
    assert args.trials == 3
