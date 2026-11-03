"""C19 changes only author guidance for known amounts and condition placement."""

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
CASES = ("c18-scout-prior-admitted", "c18-scout-prior-conditional",
         "c18-scout-prior-incomplete")
OLD = (
    "Preserve each quote's scope: incomplete or unknown-scope amounts do not "
    "establish a per-person fare, all-in trip cost or cheapest-overall choice. "
    "The condition_applicability table gives source condition codes, states "
    "and exact selected-pool aliases, not words to copy. Consider only the "
    "choices you actually show; explain each relevant condition once in "
    "natural language, locally when it changes that choice's next action or "
    "together when it applies across shown choices. Do not repeat a condition "
    "in both places or infer one from a missing field. "
)
NEW = (
    "Preserve each quote's meaning: a reported number and its pricing basis "
    "are different facts. Unknown scope does not make a known points, tax or "
    "cash amount unknown, and incomplete quotes or reported amounts with "
    "unknown scope do not "
    "establish a per-person fare, all-in trip cost or cheapest-overall choice. "
    "Use the condition_applicability table only for the specific source fields "
    "and shown choices to which each condition applies; keep amount "
    "uncertainty, quote basis, party support and separate cash roles distinct. "
    "Explain the practical consequence of a relevant condition once, in your "
    "own words. Its explanation may sit with a choice or comparison, or in "
    "shared prose; either placement is sufficient. If it is already qualified "
    "locally, a later shared paragraph should cover only the remaining "
    "distinct conditions, not restate that qualification as another check. "
    "Do not turn the table into an extra checklist after those conditions "
    "have already been explained. Do not group known reported amounts into "
    "a blanket 'these details are unknown' statement or infer a condition "
    "from a missing field. "
)


def _saved(case: str) -> Any:
    return parse_category_artifact((RUNS / case / "artifact.json").read_bytes())


@pytest.mark.parametrize("case", CASES)
def test_c19_actual_c18_requests_change_only_adopted_author_paragraph(case: str) -> None:
    saved = _saved(case)
    source, selector, focus = (saved.evidence.source, saved.selector_prepared,
                               saved.focus_prepared)
    assert focus is not None
    assert _requests(source, saved.config, selector, None, "category-c18") == _requests(
        source, saved.config, selector, None, "category-c19")
    old = _requests(source, saved.config, selector, focus, "category-c18")
    new = _requests(source, saved.config, selector, focus, "category-c19")
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
    old_repair = _requests(source, saved.config, selector, focus, "category-c18",
                           previous_wire=wire, feedback=(finding,))
    new_repair = _requests(source, saved.config, selector, focus, "category-c19",
                           previous_wire=wire, feedback=(finding,))
    assert new_repair.request["instructions"] == cast(str, old_repair.request[
        "instructions"]).replace(OLD, NEW)
    assert {key: value for key, value in old_repair.request.items() if key != "instructions"} == {
        key: value for key, value in new_repair.request.items() if key != "instructions"}
    assert old_repair.request["reasoning"] == new_repair.request["reasoning"] == {
        "effort": "low"}


def test_c19_offline_two_pass_replay_and_request_tamper() -> None:
    saved = _saved("c18-scout-prior-admitted")
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
                                    SavedWriter(), profile="category-c19")
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
