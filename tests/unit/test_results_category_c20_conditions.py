"""C20 changes only the placement guidance for condition groups."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from award_agent.results.category import (
    _requests,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import CheckFinding, ResultsConfig, WriterReceipt
from award_agent.results.interactive_contracts import InteractiveSettings

RUNS = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")
CASES = ("c19-scout-prior-admitted", "c19-scout-prior-conditional",
         "c19-scout-prior-incomplete")
OLD = (
    "Explain the practical consequence of a relevant condition once, in your "
    "own words. Its explanation may sit with a choice or comparison, or in "
    "shared prose; either placement is sufficient. "
)
NEW = (
    "For each relevant condition_applicability row, consider only its "
    "applies_to choices that you actually show. Explain the condition's "
    "practical consequence once for that whole affected group, in your own "
    "words, not separately for each quote or card; make clear which shown "
    "choices it covers. A condition affecting only one shown choice can stay "
    "local. This explanation may sit in a caption, comparison, opening or "
    "other prose; no separate shared-limits block is required. "
)


def _saved(case: str) -> Any:
    return parse_category_artifact((RUNS / case / "artifact.json").read_bytes())


@pytest.mark.parametrize("case", CASES)
def test_c20_actual_c19_requests_change_only_adopted_author_span(case: str) -> None:
    saved = _saved(case)
    source, selector, focus = (saved.evidence.source, saved.selector_prepared,
                               saved.focus_prepared)
    assert focus is not None
    assert _requests(source, saved.config, selector, None, "category-c19") == _requests(
        source, saved.config, selector, None, "category-c20")
    old = _requests(source, saved.config, selector, focus, "category-c19")
    new = _requests(source, saved.config, selector, focus, "category-c20")
    assert OLD in cast(str, old.request["instructions"])
    assert new.request["instructions"] == cast(str, old.request[
        "instructions"]).replace(OLD, NEW)
    assert {key: value for key, value in old.request.items() if key != "instructions"} == {
        key: value for key, value in new.request.items() if key != "instructions"}
    assert old.request["reasoning"] == new.request["reasoning"] == {"effort": "medium"}
    assert old.request["input"] == new.request["input"]
    assert old.schema_digest == new.schema_digest

    wire = saved.passes[1].raw_wire
    assert isinstance(wire, str)
    finding = CheckFinding(code="duplicate_cash_sentence_in_prose", outcome="failed",
                           scope="benchmark", message="Duplicate cash sentence")
    old_repair = _requests(source, saved.config, selector, focus, "category-c19",
                           previous_wire=wire, feedback=(finding,))
    new_repair = _requests(source, saved.config, selector, focus, "category-c20",
                           previous_wire=wire, feedback=(finding,))
    assert new_repair.request["instructions"] == cast(str, old_repair.request[
        "instructions"]).replace(OLD, NEW)
    assert {key: value for key, value in old_repair.request.items() if key != "instructions"} == {
        key: value for key, value in new_repair.request.items() if key != "instructions"}
    assert old_repair.request["reasoning"] == new_repair.request["reasoning"] == {
        "effort": "low"}


def test_c20_offline_two_pass_replay_and_request_tamper() -> None:
    saved = _saved("c19-scout-prior-admitted")
    wires = [part.raw_wire for part in saved.passes]
    assert len(wires) == 2 and all(isinstance(wire, str) for wire in wires)

    class SavedWriter:
        def __init__(self) -> None:
            self.calls = 0
            self.pending: WriterReceipt | None = None

        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: InteractiveSettings) -> str:
            wire = wires[self.calls]
            assert isinstance(wire, str)
            self.calls += 1
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": wire}]}]}))
            return wire

        def take_receipt(self) -> WriterReceipt | None:
            pending, self.pending = self.pending, None
            return pending

    artifact = run_category_results(saved.evidence.source, saved.config,
                                    SavedWriter(), profile="category-c20")
    assert artifact.resolved == saved.resolved
    assert artifact.selector_settings.reasoning_effort == "low"
    assert artifact.composer_settings.reasoning_effort == "medium"
    assert artifact.correction_settings.reasoning_effort == "low"
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == \
        artifact.resolved
    tampered = json.loads(artifact.model_dump_json())
    tampered["passes"][1]["request"]["instructions"] += " Unexpected extra rule."
    with pytest.raises(ValueError):
        replay_category_results(parse_category_artifact(json.dumps(tampered)))
