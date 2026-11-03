"""C13 keeps C12 authoring fixed and changes only composer reasoning effort."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from award_agent.results.category import (
    _SETTINGS,
    _requests,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt
from award_agent.results.interactive_contracts import InteractiveSettings

RUNS = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")
CASES = ("c12-scout-prior-admitted", "c12-scout-prior-conditional",
         "c12-scout-prior-incomplete")


def _saved(case: str) -> Any:
    return parse_category_artifact((RUNS / case / "artifact.json").read_bytes())


@pytest.mark.parametrize("case", CASES)
def test_c13_request_equals_c12_except_composer_effort(case: str) -> None:
    saved = _saved(case)
    source, selector, focus = (saved.evidence.source, saved.selector_prepared,
                               saved.focus_prepared)
    assert focus is not None
    old_selector = _requests(source, saved.config, selector, None, "category-c12")
    new_selector = _requests(source, saved.config, selector, None, "category-c13")
    assert old_selector == new_selector
    old = _requests(source, saved.config, selector, focus, "category-c12")
    new = _requests(source, saved.config, selector, focus, "category-c13")
    assert {key: value for key, value in old.request.items() if key != "reasoning"} == {
        key: value for key, value in new.request.items() if key != "reasoning"}
    assert old.request["reasoning"] == {"effort": "medium"}
    assert new.request["reasoning"] == {"effort": "low"}
    assert old.schema_digest == new.schema_digest
    assert old.input_bytes == new.input_bytes
    assert old.prompt_digest == new.prompt_digest


def test_c13_offline_correction_is_low_and_exact_replay_is_phase_bound() -> None:
    saved = _saved("c12-scout-prior-admitted")
    selector_raw, clean_raw = (part.raw_wire for part in saved.passes)
    assert isinstance(selector_raw, str) and isinstance(clean_raw, str)
    dirty = json.loads(clean_raw)
    cash = next(row["v"] for row in dirty["blocks"] if row["k"] == "b")
    dirty["blocks"].insert(-1, {"k": "t", "v": cash})
    wires = [selector_raw, json.dumps(dirty), clean_raw]

    class SavedWriter:
        def __init__(self) -> None:
            self.calls = 0
            self.efforts: list[str] = []
            self.pending: WriterReceipt | None = None

        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: InteractiveSettings) -> str:
            self.efforts.append(settings.reasoning_effort)
            wire = wires[self.calls]
            self.calls += 1
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": wire}]}]}))
            return wire

        def take_receipt(self) -> WriterReceipt | None:
            pending, self.pending = self.pending, None
            return pending

    writer = SavedWriter()
    artifact = run_category_results(saved.evidence.source, saved.config, writer,
                                    profile="category-c13")
    assert writer.efforts == ["low", "low", "low"]
    assert artifact.selector_settings == artifact.composer_settings == \
        artifact.correction_settings == _SETTINGS
    assert len(artifact.passes) == 3
    assert any(row.code == "duplicate_cash_sentence_in_prose"
               for row in artifact.passes[1].findings)
    assert artifact.validation_outcome == "clean"
    assert artifact.resolved == saved.resolved
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == \
        artifact.resolved
    tampered = artifact.model_copy(update={
        "composer_settings": InteractiveSettings(reasoning_effort="medium",
                                                 service_tier="fast")})
    with pytest.raises(ValueError, match="profile/settings differ"):
        replay_category_results(tampered)
    raw = json.loads(artifact.model_dump_json())
    raw["passes"][1]["request"]["reasoning"] = {"effort": "medium"}
    with pytest.raises(ValueError):
        replay_category_results(parse_category_artifact(json.dumps(raw)))
