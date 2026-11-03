"""C17 combines only source-proven points and award-tax quote scope rows."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from award_agent.results.category import (
    _condition_applicability,
    _requests,
    _writer_input,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt
from award_agent.results.interactive_contracts import InteractiveSettings

RUNS = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")
CASES = ("c16-scout-prior-admitted", "c16-scout-prior-conditional",
         "c16-scout-prior-incomplete")


def _saved(case: str) -> Any:
    return parse_category_artifact((RUNS / case / "artifact.json").read_bytes())


def _rows(records: dict[str, dict[str, Any]], *, merge: bool) -> dict[tuple[str, str], set[str]]:
    return {(cast(str, row["code"]), cast(str, row["state"])):
            set(cast(list[str], row["applies_to"]))
            for row in _condition_applicability(records, merge_award_scope=merge)}


def test_c17_q052_exact_award_identity_provenance_and_table_merge() -> None:
    saved = _saved("c16-scout-prior-admitted")
    assert saved.focus_prepared is not None
    old = cast(dict[str, Any], _writer_input(saved.focus_prepared, profile="category-c16"))
    new = cast(dict[str, Any], _writer_input(saved.focus_prepared, profile="category-c17"))
    assert len(old["condition_applicability"]) == 8
    assert len(new["condition_applicability"]) == 7
    records = cast(dict[str, dict[str, Any]], new["authoring_records"])
    journey_aliases = {alias for alias, record in records.items()
                       if record["role"] == "journey"}
    assert {alias.split("@")[0] for alias in journey_aliases} == {"J1", "J82"}
    source_by_id = {item.observation_id: item
                    for item in saved.evidence.source.view.components}
    view_by_id = {item.observation_id: item for item in saved.evidence.components}
    short_aliases = saved.focus_prepared.packet["wire_aliases"]
    source_refs = saved.focus_prepared.structured.references.awards
    for alias in journey_aliases:
        record = records[alias]
        award_ref = record["member"]["award_ref"]
        assert award_ref and award_ref == record["award_component"]["ref"]
        canonical = source_refs[short_aliases[award_ref]]
        assert record["facts"]["award"]["price_scope"] == \
            record["award_component"]["quote"]["price_scope"] == \
            source_by_id[canonical].price_scope == view_by_id[canonical].price_scope == "unknown"
        assert record["award_component"]["quote"]["kind"] == "award_taxes"
    rows = _rows(records, merge=True)
    assert rows[("award_points_and_tax_quote_scope", "unknown")] == journey_aliases
    assert not any(code in {"award_price_scope", "award_tax_quote_scope"}
                   for code, _ in rows)
    assert rows[("award_tax_amount", "unknown")] == {
        alias for alias in journey_aliases if alias.startswith("J82@")}
    assert rows[("positioning_cash_quote_scope", "unknown")] == {
        alias for alias in journey_aliases if alias.startswith("J82@")}
    assert rows[("benchmark_cash_quote_scope", "unknown")] == {
        alias for alias, record in records.items() if record["role"] == "benchmark"}


def test_c17_partial_merge_requires_exact_identity_kind_and_both_unknown_states() -> None:
    saved = _saved("c16-scout-prior-admitted")
    assert saved.focus_prepared is not None
    packet = _writer_input(saved.focus_prepared, profile="category-c16")
    original = next(record for record in cast(dict[str, dict[str, Any]], packet[
        "authoring_records"]).values() if record["role"] == "journey")
    records: dict[str, dict[str, Any]] = {}
    for alias in ("merged", "mismatch", "empty_ref", "missing_ref", "wrong_kind",
                  "points_only", "tax_only", "neither", "tax_unknown", "tax_absent",
                  "tax_null", "zero_known"):
        records[alias] = deepcopy(original)
    records["mismatch"]["member"]["award_ref"] = "A-different"
    records["empty_ref"]["member"]["award_ref"] = ""
    del records["missing_ref"]["award_component"]["ref"]
    records["wrong_kind"]["award_component"]["quote"]["kind"] = "cash_fare"
    records["points_only"]["award_component"]["quote"]["price_scope"] = "party"
    records["tax_only"]["facts"]["award"]["price_scope"] = "party"
    records["neither"]["facts"]["award"]["price_scope"] = "party"
    records["neither"]["award_component"]["quote"]["price_scope"] = "party"
    records["tax_unknown"]["award_component"]["quote"]["amount_state"] = "unknown"
    records["tax_absent"]["award_component"]["quote"]["amount_state"] = "absent"
    records["tax_null"]["award_component"]["quote"]["amount_state"] = "null"
    records["zero_known"]["award_component"]["quote"].update(
        {"amount_state": "value", "display": "USD 0.00"})
    before = deepcopy(records)
    rows = _rows(records, merge=True)
    assert rows[("award_points_and_tax_quote_scope", "unknown")] == {
        "merged", "tax_unknown", "tax_absent", "tax_null", "zero_known"}
    assert rows[("award_price_scope", "unknown")] == {
        "mismatch", "empty_ref", "missing_ref", "wrong_kind", "points_only"}
    assert rows[("award_tax_quote_scope", "unknown")] == {
        "mismatch", "empty_ref", "missing_ref", "tax_only"}
    assert rows[("award_tax_amount", "unknown")] == {"tax_unknown"}
    assert rows[("award_tax_amount", "absent")] == {"tax_absent"}
    assert rows[("award_tax_amount", "null")] == {"tax_null"}
    assert "neither" not in set().union(*rows.values())
    assert records == before and records["zero_known"]["award_component"][
        "quote"]["display"] == "USD 0.00"
    assert _rows(records, merge=False)[("award_price_scope", "unknown")] >= {
        "merged", "zero_known"}


@pytest.mark.parametrize("case", CASES)
def test_c17_actual_requests_only_change_condition_table(case: str) -> None:
    saved = _saved(case)
    source, selector, focus = (saved.evidence.source, saved.selector_prepared,
                               saved.focus_prepared)
    assert focus is not None
    assert _requests(source, saved.config, selector, None, "category-c16") == _requests(
        source, saved.config, selector, None, "category-c17")
    old = _requests(source, saved.config, selector, focus, "category-c16")
    new = _requests(source, saved.config, selector, focus, "category-c17")
    assert old.request["instructions"] == new.request["instructions"]
    assert old.request["text"] == new.request["text"]
    assert old.request["reasoning"] == new.request["reasoning"] == {"effort": "medium"}
    old_input = json.loads(cast(str, old.request["input"]))
    new_input = json.loads(cast(str, new.request["input"]))
    assert old_input["packet"].pop("condition_applicability")
    assert new_input["packet"].pop("condition_applicability")
    assert old_input == new_input
    assert old.schema_digest == new.schema_digest
    assert old.prompt_digest != new.prompt_digest if case != "c16-scout-prior-incomplete" else \
        old.prompt_digest == new.prompt_digest
    wire = saved.passes[1].raw_wire
    assert isinstance(wire, str)
    old_repair = _requests(source, saved.config, selector, focus, "category-c16",
                           previous_wire=wire)
    new_repair = _requests(source, saved.config, selector, focus, "category-c17",
                           previous_wire=wire)
    assert old_repair.request["instructions"] == new_repair.request["instructions"]
    assert old_repair.request["text"] == new_repair.request["text"]
    assert old_repair.request["reasoning"] == new_repair.request["reasoning"] == {
        "effort": "low"}
    old_repair_input = json.loads(cast(str, old_repair.request["input"]))
    new_repair_input = json.loads(cast(str, new_repair.request["input"]))
    old_repair_input["packet"].pop("condition_applicability")
    new_repair_input["packet"].pop("condition_applicability")
    assert old_repair_input == new_repair_input


def test_c17_offline_run_replay_and_table_request_tamper() -> None:
    saved = _saved("c16-scout-prior-admitted")
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
                                    SavedWriter(), profile="category-c17")
    assert artifact.resolved == saved.resolved
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == \
        artifact.resolved
    tampered = json.loads(artifact.model_dump_json())
    payload = json.loads(tampered["passes"][1]["request"]["input"])
    payload["packet"]["condition_applicability"][0]["code"] = "invented"
    tampered["passes"][1]["request"]["input"] = json.dumps(payload)
    with pytest.raises(ValueError):
        replay_category_results(parse_category_artifact(json.dumps(tampered)))
