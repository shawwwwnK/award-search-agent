"""C16 changes only the composer meaning of cross-program point counts."""

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
CASES = ("c15-scout-prior-admitted", "c15-scout-prior-conditional",
         "c15-scout-prior-incomplete")


def _saved(case: str) -> Any:
    return parse_category_artifact((RUNS / case / "artifact.json").read_bytes())


@pytest.mark.parametrize("case", CASES)
def test_c16_actual_c15_requests_change_only_author_clause(case: str) -> None:
    saved = _saved(case)
    source, selector, focus = (saved.evidence.source, saved.selector_prepared,
                               saved.focus_prepared)
    assert focus is not None
    old_selector = _requests(source, saved.config, selector, None, "category-c15")
    new_selector = _requests(source, saved.config, selector, None, "category-c16")
    assert old_selector == new_selector

    old_author = _requests(source, saved.config, selector, focus, "category-c15")
    new_author = _requests(source, saved.config, selector, focus, "category-c16")
    old_clause = ("Do not force same-program pairs, a lowest-points rule, or "
                  "cross-program economic ranking. ")
    new_clause = ("Do not force same-program pairs, a lowest-points rule or a numerical "
                  "comparison. Points belong to their named loyalty programs: a smaller "
                  "raw count in a different program does not establish an advantage and "
                  "is not a reason to favor or investigate that lead. Conditional program "
                  "access, date or cabin suitability can supply the reason on its own. "
                  "Within one program, reported quotes may be compared while preserving "
                  "their scope and incomplete status. ")
    assert old_clause in cast(str, old_author.request["instructions"])
    assert new_author.request["instructions"] == cast(str, old_author.request[
        "instructions"]).replace(old_clause, new_clause)
    assert {key: value for key, value in old_author.request.items() if key != "instructions"} == {
        key: value for key, value in new_author.request.items() if key != "instructions"}
    assert old_author.request["reasoning"] == new_author.request["reasoning"] == {
        "effort": "medium"}
    assert old_author.schema_digest == new_author.schema_digest
    assert old_author.input_bytes != new_author.input_bytes

    wire = saved.passes[1].raw_wire
    assert isinstance(wire, str)
    finding = CheckFinding(code="duplicate_cash_sentence_in_prose", outcome="failed",
                           scope="benchmark", message="Duplicate cash sentence")
    old_repair = _requests(source, saved.config, selector, focus, "category-c15",
                           previous_wire=wire, feedback=(finding,))
    new_repair = _requests(source, saved.config, selector, focus, "category-c16",
                           previous_wire=wire, feedback=(finding,))
    assert new_repair.request["instructions"] == cast(str, old_repair.request[
        "instructions"]).replace(old_clause, new_clause)
    assert {key: value for key, value in old_repair.request.items() if key != "instructions"} == {
        key: value for key, value in new_repair.request.items() if key != "instructions"}
    assert old_repair.request["reasoning"] == new_repair.request["reasoning"] == {
        "effort": "low"}


def test_c16_offline_two_pass_replay_and_request_tamper() -> None:
    saved = _saved("c15-scout-prior-incomplete")
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
                                    SavedWriter(), profile="category-c16")
    assert artifact.resolved == saved.resolved
    assert artifact.composer_settings.reasoning_effort == "medium"
    assert artifact.correction_settings.reasoning_effort == "low"
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == \
        artifact.resolved
    tampered = json.loads(artifact.model_dump_json())
    tampered["passes"][1]["request"]["instructions"] += " Unexpected edit."
    with pytest.raises(ValueError):
        replay_category_results(parse_category_artifact(json.dumps(tampered)))
