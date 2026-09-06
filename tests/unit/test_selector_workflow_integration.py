from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from award_agent.cli import selector_workflow_integration_eval as integration_cli
from award_agent.evaluation.frozen_selector_cases import frozen_selector_case_registry
from award_agent.evaluation.selector_workflow_integration import (
    DEFAULT_SELECTOR_WORKFLOW_MANIFEST,
    SelectorWorkflowFixtureError,
    _run_case,
    preflight_selector_workflow_cases,
    run_selector_workflow_integration_eval,
)
from award_agent.intent.model_views import (
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
    TemporalSelectorInput,
    TemporalSelectorOutput,
)
from award_agent.intent.temporal_candidates import CandidateRelation, TemporalCandidateCatalog
from award_agent.intent.temporal_selector import (
    TemporalSelectorValidationError,
    plan_temporal_selection,
)
from award_agent.intent.workflow import (
    _understand_request_with_frozen_catalog,
    understand_request,
)


class OracleSelector:
    """Test selector that maps a private fixture oracle to its public opaque handles."""

    def __init__(self) -> None:
        self.calls: list[TemporalSelectorInput] = []

        self.reset_calls = 0

    def reset_capture(self) -> None:
        self.reset_calls += 1

    def take_usage(self) -> dict[str, int]:
        return {
            "calls": 1,
            "captured_calls": 1,
            "missing_calls": 0,
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
        }

    def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
        self.calls.append(model_input)
        private_candidates = set(model_input._candidate_handles.values())
        case = next(
            item
            for item in frozen_selector_case_registry().values()
            if private_candidates
            == {
                candidate.handle
                for candidate in item.catalog.candidates
                if candidate.exclusive_group
                in plan_temporal_selection(item.catalog).selector_groups
            }
        )
        oracle = set(case.oracle_candidates)
        return TemporalSelectorOutput(
            selected_candidates=[
                public
                for public, private in model_input._candidate_handles.items()
                if private in oracle
            ]
        )


def test_public_workflow_signature_exposes_no_evaluation_catalog_or_policy_override() -> None:
    parameters = set(inspect.signature(understand_request).parameters)

    assert parameters == {"request", "extractor", "temporal_selector", "holiday_provider"}


def test_integration_preflight_reuses_every_frozen_manual_case() -> None:
    cases = preflight_selector_workflow_cases()

    assert len(cases) == 12
    assert {case.identifier for case in cases} == set(frozen_selector_case_registry())
    manifest = DEFAULT_SELECTOR_WORKFLOW_MANIFEST.read_text()
    assert "manual:" not in manifest
    assert "oracle" not in manifest.casefold()
    assert "October" not in manifest


def test_integration_runs_only_selector_through_real_workflow_and_redacts_artifact() -> None:
    selector = OracleSelector()
    artifact = run_selector_workflow_integration_eval(
        selector_model="explicit-luna-id",
        selector_factory=lambda _model: selector,
    )

    assert artifact["evaluation"] == "selector_workflow_integration_test_only"
    assert artifact["selector_model"] == "explicit-luna-id"
    assert artifact["scenario_count"] == 12
    assert artifact["summary"] == {
        "runs": 12,
        "completed": 12,
        "errors": 0,
        "selector_oracle_matches": 12,
        "workflow_oracle_matches": 12,
        "selector_attempts": 12,
        "latency_seconds": artifact["summary"]["latency_seconds"],
    }
    assert artifact["frozen_selector_fixture"] == {
        "path": "evals/selector/frozen_cases_v2.yaml",
        "sha256": artifact["frozen_selector_fixture"]["sha256"],
        "contract_version": "v2",
    }
    assert len(artifact["frozen_selector_fixture"]["sha256"]) == 64
    assert len(selector.calls) == 12
    assert selector.reset_calls == 12
    assert all(record["workflow"]["paired_output_match"] for record in artifact["results"])
    assert all(record["selector"]["attempted"] for record in artifact["results"])
    assert all(record["selector"]["public_output"] for record in artifact["results"])
    serialized = json.dumps(artifact)
    for forbidden in ("manual:", "slot:", "October", "Thanksgiving", "Labor Day", "Leave "):
        assert forbidden not in serialized


def test_integration_keeps_invalid_selector_output_explicit_and_redacted() -> None:
    class BadSelector:
        def select_candidates(self, _model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
            return TemporalSelectorOutput(selected_candidates=["unknown"])

    artifact = run_selector_workflow_integration_eval(
        selector_model="explicit-luna-id",
        selector_factory=lambda _model: BadSelector(),
    )

    assert artifact["summary"]["errors"] == 12
    assert {record["error_code"] for record in artifact["results"]} == {
        "selector_selection_validation_failed"
    }
    assert "manual:" not in json.dumps(artifact)


def test_workflow_rejects_an_injected_catalog_for_different_request_text() -> None:
    case = frozen_selector_case_registry()["target-forward"]
    mismatched = case.request.model_copy(update={"text": "Leave October 6."})

    with pytest.raises(ValueError, match="request text must exactly match"):
        _understand_request_with_frozen_catalog(
            mismatched,
            object(),  # type: ignore[arg-type]
            OracleSelector(),
            None,
            catalog=case.catalog,
        )


def test_workflow_surfaces_a_structurally_invalid_injected_catalog() -> None:
    class StaticNonTemporalExtractor:
        def extract_non_temporal(
            self, _model_input: NonTemporalExtractionInput
        ) -> NonTemporalIntentExtraction:
            return NonTemporalIntentExtraction()

    case = frozen_selector_case_registry()["target-forward"]
    invalid_catalog = TemporalCandidateCatalog(
        scan=case.catalog.scan,
        candidates=tuple(
            candidate
            for candidate in case.catalog.candidates
            if candidate.relation is not CandidateRelation.UNRESOLVED
        ),
    )

    with pytest.raises(TemporalSelectorValidationError, match="exactly one unresolved"):
        _understand_request_with_frozen_catalog(
            case.request,
            StaticNonTemporalExtractor(),
            OracleSelector(),
            None,
            catalog=invalid_catalog,
        )


def test_integration_does_not_count_a_selector_attempt_before_the_proxy_is_called() -> None:
    class NeverCalledSelector:
        def select_candidates(self, _model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
            raise AssertionError("invalid catalog must fail before the selector")

    case = frozen_selector_case_registry()["target-forward"]
    invalid_catalog = TemporalCandidateCatalog(
        scan=case.catalog.scan,
        candidates=tuple(
            candidate
            for candidate in case.catalog.candidates
            if candidate.relation is not CandidateRelation.UNRESOLVED
        ),
    )
    invalid_case = case.__class__(
        identifier=case.identifier,
        category=case.category,
        pair=case.pair,
        request=case.request,
        catalog=invalid_catalog,
        oracle_candidates=case.oracle_candidates,
    )

    record, result = _run_case(invalid_case, NeverCalledSelector())

    assert result is None
    assert record["selector"] == {"attempted": False, "public_output": None}
    assert record["error_code"] == "selector_selection_validation_failed"


def test_integration_manifest_rejects_private_oracle_fields(tmp_path: Path) -> None:
    copied = tmp_path / "integration.yaml"
    copied.write_text(
        DEFAULT_SELECTOR_WORKFLOW_MANIFEST.read_text().replace(
            "  pair: target\n", "  pair: target\n  oracle: c0\n", 1
        )
    )

    with pytest.raises(SelectorWorkflowFixtureError, match="only id, category, and pair"):
        preflight_selector_workflow_cases(copied)


def test_integration_cli_returns_nonzero_on_explicit_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact = {
        "summary": {
            "errors": 1,
            "selector_oracle_matches": 0,
            "workflow_oracle_matches": 0,
            "runs": 1,
        },
        "results": [{"workflow": {"paired_output_match": False}}],
    }
    monkeypatch.setattr(
        integration_cli,
        "run_selector_workflow_integration_eval",
        lambda **_kwargs: artifact,
    )
    output = tmp_path / "integration.json"

    assert integration_cli.main(["--selector-model", "luna-id", "--output", str(output)]) == 1
    assert json.loads(output.read_text())["summary"]["errors"] == 1
