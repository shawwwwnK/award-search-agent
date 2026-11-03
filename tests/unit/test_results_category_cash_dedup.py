"""Profile-scoped mechanical control for repeated inline cash prose."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_results_category import CategoryWriter, _config, _source

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.category import (
    _PROFILE_INSTRUCTIONS,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt

SAVED_C03 = Path(
    "evidence/results-stage/m2/structured/2026-10-29-category-led/"
    "runs/c03-scout-prior-incomplete/artifact.json"
)


class RepeatedCashWriter(CategoryWriter):
    def __init__(self, *, repeated_text: str, repair: bool = False) -> None:
        super().__init__()
        self.repeated_text = repeated_text
        self.repair = repair

    def author(self, request: dict[str, object], config: ResultsConfig,
               settings: object) -> str:
        raw = super().author(request, config, settings)
        if len(self.requests) != 2 or self.repair:
            return raw
        document = json.loads(raw)
        cash = next(block["v"] for block in document["blocks"] if block["k"] == "b")
        repeated = cash if self.repeated_text == "exact" else (
            f"For context, {cash} This is separate from the awards."
            if self.repeated_text == "embedded" else
            "A separate cash search gives some context for the award choices.")
        document["blocks"].insert(-1, {"k": "t", "v": repeated})
        raw = json.dumps(document)
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority", "output": [
                {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
        return raw


def test_saved_c03_duplicate_keeps_original_clean_replay() -> None:
    artifact = parse_category_artifact(SAVED_C03.read_bytes())
    assert artifact.profile == "category-c03"
    assert artifact.validation_outcome == "clean"
    assert replay_category_results(artifact) == artifact.resolved


@pytest.mark.parametrize("repeated_text", ["exact", "embedded"])
def test_c04_exact_cash_sentence_in_other_block_triggers_one_repair(
        repeated_text: str) -> None:
    class RepairWriter(RepeatedCashWriter):
        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: object) -> str:
            self.repair = len(self.requests) >= 2
            return super().author(request, config, settings)

    artifact = run_category_results(_source(), _config(),
                                    RepairWriter(repeated_text=repeated_text),
                                    profile="category-c04")
    assert len(artifact.passes) == 3
    assert "duplicate_cash_sentence_in_prose" in {
        finding.code for finding in artifact.passes[1].findings}
    assert not any(finding.outcome == "failed" for finding in artifact.passes[2].findings)
    assert artifact.selected_pass_index == 2
    assert artifact.validation_outcome == "clean"
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


def test_c04_distinct_cash_context_does_not_trigger_correction() -> None:
    artifact = run_category_results(_source(), _config(),
                                    RepeatedCashWriter(repeated_text="different"),
                                    profile="category-c04")
    assert len(artifact.passes) == 2
    assert "duplicate_cash_sentence_in_prose" not in {
        finding.code for finding in artifact.passes[1].findings}
    assert artifact.validation_outcome == "clean"
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


def test_c04_opening_guidance_names_overlap_without_claiming_prose_validation() -> None:
    source = SolutionProjection.model_validate(json.loads(Path(
        "evidence/results-stage/m2/structured/2026-10-28-fast-default/"
        "review-bundles/q120/evidence.json").read_text())["source"])
    assert set(source.view.indexes.time).intersection(source.view.indexes.premium)
    guide = _PROFILE_INSTRUCTIONS["category-c04"][1]
    assert "if one journey offers both earlier arrival and a premium cabin" in guide
    assert "do not present them as opposing choices" in guide
