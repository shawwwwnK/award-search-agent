"""C18 changes only the complete-journey explanation paragraph."""

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
CASES = ("c17-scout-prior-admitted", "c17-scout-prior-conditional",
         "c17-scout-prior-incomplete")
OLD = (
    "For complete journeys, explain the supported benefit that distinguishes "
    "each shown choice, such as a shorter trip, cabin or connection buffer. "
    "Use Ranking's time/cost/premium memberships as source facts, but describe "
    "the traveler benefit in ordinary language, with no empty category notices "
    "or mandatory headings. Time membership means a qualifying duration band, "
    "not earlier arrival or dominance over another selected journey. Use "
    "selected_temporal_relations for relative departure, arrival or duration "
    "claims; preserve equal arrivals as equal and do not substitute one metric "
    "for another. Category overlap does not create an overall winner. "
)
NEW = (
    "For each shown complete journey, explain when a traveler might choose it "
    "using a supported fact, such as cabin, timing, trip duration, connection "
    "details or a scope-qualified cost or point quote. Put "
    "that decision reason in k=p or a's v; a relevant local condition may "
    "accompany it, but a checklist alone is not a reason. Use Ranking's "
    "time/cost/premium memberships to preserve the useful perspectives, and "
    "express overlapping strengths once in traveler language rather than "
    "explaining category qualification. One journey can be enough; do not "
    "invent a benefit or add a comparison just to fill a pattern. Keep these "
    "evidence limits in your reasoning: time membership alone proves neither "
    "earlier arrival nor superiority over another shown journey, and overlap "
    "is not an overall winner. For any relative departure, arrival or duration "
    "claim, use selected_temporal_relations, preserve equal arrivals as equal "
    "and do not substitute one metric for another. If no useful supported "
    "comparison is being made, omit it rather than adding a disclaimer about "
    "a comparison the answer never makes. "
)


def _saved(case: str) -> Any:
    return parse_category_artifact((RUNS / case / "artifact.json").read_bytes())


@pytest.mark.parametrize("case", CASES)
def test_c18_actual_c17_requests_change_only_adopted_author_paragraph(case: str) -> None:
    saved = _saved(case)
    source, selector, focus = (saved.evidence.source, saved.selector_prepared,
                               saved.focus_prepared)
    assert focus is not None
    old_selector = _requests(source, saved.config, selector, None, "category-c17")
    new_selector = _requests(source, saved.config, selector, None, "category-c18")
    assert old_selector == new_selector

    old = _requests(source, saved.config, selector, focus, "category-c17")
    new = _requests(source, saved.config, selector, focus, "category-c18")
    assert OLD in cast(str, old.request["instructions"])
    assert new.request["instructions"] == cast(str, old.request[
        "instructions"]).replace(OLD, NEW)
    assert {key: value for key, value in old.request.items() if key != "instructions"} == {
        key: value for key, value in new.request.items() if key != "instructions"}
    assert old.request["reasoning"] == new.request["reasoning"] == {"effort": "medium"}
    assert old.schema_digest == new.schema_digest
    assert old.request["input"] == new.request["input"]

    wire = saved.passes[1].raw_wire
    assert isinstance(wire, str)
    finding = CheckFinding(code="duplicate_cash_sentence_in_prose", outcome="failed",
                           scope="benchmark", message="Duplicate cash sentence")
    old_repair = _requests(source, saved.config, selector, focus, "category-c17",
                           previous_wire=wire, feedback=(finding,))
    new_repair = _requests(source, saved.config, selector, focus, "category-c18",
                           previous_wire=wire, feedback=(finding,))
    assert new_repair.request["instructions"] == cast(str, old_repair.request[
        "instructions"]).replace(OLD, NEW)
    assert {key: value for key, value in old_repair.request.items() if key != "instructions"} == {
        key: value for key, value in new_repair.request.items() if key != "instructions"}
    assert old_repair.request["reasoning"] == new_repair.request["reasoning"] == {
        "effort": "low"}


def test_c18_offline_two_pass_replay_and_request_tamper() -> None:
    saved = _saved("c17-scout-prior-admitted")
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
                                    SavedWriter(), profile="category-c18")
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
