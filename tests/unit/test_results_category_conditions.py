"""C11 exact source condition applicability without authored placement policy."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from award_agent.results.category import (
    _condition_applicability,
    _document_schema,
    _requests,
    _writer_input,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt
from award_agent.results.interactive_contracts import InteractiveSettings

ROOT = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")


def _saved(case: str) -> Any:
    return parse_category_artifact((ROOT / case / "artifact.json").read_bytes())


def _indexed(packet: dict[str, Any]) -> dict[tuple[str, str], set[str]]:
    return {(row["code"], row["state"]): set(row["applies_to"])
            for row in packet["condition_applicability"]}


def test_c11_q028_singleton_business_and_omitted_pool_member() -> None:
    saved = _saved("c10-scout-prior-admitted")
    assert saved.focus_prepared is not None and saved.resolved is not None
    packet = cast(dict[str, Any], _writer_input(saved.focus_prepared, profile="category-c11"))
    records = cast(dict[str, Any], packet["authoring_records"])
    assert len([record for record in records.values() if record["role"] == "journey"]) == 3
    business = next(alias for alias, record in records.items()
                    if record["role"] == "journey" and
                    record["facts"]["award_cabin"] == "business")
    journeys = {alias for alias, record in records.items() if record["role"] == "journey"}
    scope = _indexed(packet)
    assert scope[("award_tax_amount", "unknown")] == {business}
    assert scope[("award_party_support", "unknown")] == {business}
    assert scope[("separate_ticket_obligation", "unknown")] == {business}
    assert scope[("positioning_permission_unknown", "unknown")] == {business}
    assert scope[("award_price_scope", "unknown")] == journeys
    assert scope[("award_tax_quote_scope", "unknown")] == journeys
    assert scope[("positioning_cash_quote_scope", "unknown")] == {business}
    assert all(set(row["applies_to"]) <= set(records)
               for row in packet["condition_applicability"])
    displayed = {block.canonical_id for block in saved.resolved.blocks
                 if block.kind == "journey_card"}
    omitted = {alias for alias, record in records.items()
               if record["role"] == "journey" and
               saved.focus_prepared.structured.references.journeys.get(
                   saved.focus_prepared.packet["wire_aliases"][alias]) not in displayed}
    assert len(omitted) == 1
    assert omitted <= scope[("award_price_scope", "unknown")]
    assert business not in omitted


def test_c11_q029_lead_schedule_and_scope_shared_across_exact_leads() -> None:
    saved = _saved("c10-scout-prior-conditional")
    assert saved.focus_prepared is not None
    packet = cast(dict[str, Any], _writer_input(saved.focus_prepared, profile="category-c11"))
    records = cast(dict[str, Any], packet["authoring_records"])
    leads = {alias for alias, record in records.items() if record["role"] == "lead"}
    journeys = {alias for alias, record in records.items() if record["role"] == "journey"}
    benchmarks = {alias for alias, record in records.items() if record["role"] == "benchmark"}
    scope = _indexed(packet)
    assert len(leads) == 2 and len(journeys) == 2 and len(benchmarks) == 1
    assert scope[("lead_schedule", "date_only")] == leads
    assert scope[("lead_award_tax_quote_scope", "unknown")] == leads
    assert scope[("separate_ticket_obligation", "unknown")] == journeys
    assert scope[("award_tax_amount", "unknown")] == journeys
    assert scope[("benchmark_cash_quote_scope", "unknown")] == benchmarks


def test_c11_states_remain_distinct_and_missing_fields_do_not_become_conditions() -> None:
    base: dict[str, Any] = {"role": "journey", "facts": {"award": {"price_scope": "per_traveler"},
        "caveats": [], "award_cabin": "economy"},
        "award_component": {"quote": {"kind": "award_taxes",
                                       "price_scope": "party", "amount_state": "value",
                                       "display": "USD 0.00"}},
        "traveler_evidence": {"award_support_for_requested_party": "passed"}}
    unknown = deepcopy(base)
    unknown["award_component"]["quote"].update(
        {"price_scope": "unknown", "amount_state": "unknown", "display": None})
    unknown["traveler_evidence"]["award_support_for_requested_party"] = "unknown"
    absent = deepcopy(base)
    absent["award_component"]["quote"].update(
        {"amount_state": "absent", "display": None})
    absent["facts"]["award"]["seats"] = 0  # no party-support inference from raw seats
    rows = _condition_applicability({"Jknown": base, "Junknown": unknown,
                                    "Jabsent": absent, "Jmissing": {"role": "journey"}})
    scope = {(row["code"], row["state"]): set(cast(list[str], row["applies_to"]))
             for row in rows}
    assert scope[("award_tax_amount", "unknown")] == {"Junknown"}
    assert scope[("award_tax_amount", "absent")] == {"Jabsent"}
    assert scope[("award_tax_quote_scope", "unknown")] == {"Junknown"}
    assert scope[("award_party_support", "unknown")] == {"Junknown"}
    assert not any("Jknown" in cast(list[str], row["applies_to"]) or
                   "Jmissing" in cast(list[str], row["applies_to"])
                   for row in rows)
    assert not any(code == "award_party_support" and "Jabsent" in aliases
                   for (code, _), aliases in scope.items())


def test_c11_scope_roles_are_not_merged() -> None:
    records: dict[str, dict[str, Any]] = {
        "Jposition": {"role": "journey", "cash_component": {"quote": {
            "kind": "cash_fare", "price_scope": "unknown"}}, "facts": {"caveats": [
            {"code": "separate_ticket_obligation", "state": "unknown"},
            {"code": "positioning_permission_unknown", "state": "unknown"}]}},
        "Alead": {"role": "lead", "facts": {"schedule_state": "date_only"},
                  "quote": {"kind": "award_taxes", "price_scope": "unknown"}},
        "Clead": {"role": "lead", "facts": {},
                  "quote": {"kind": "cash_fare", "price_scope": "unknown"}},
        "Cbenchmark": {"role": "benchmark", "quote": {
            "kind": "cash_fare", "price_scope": "unknown"}},
    }
    rows = _condition_applicability(records)
    scope = {(row["code"], row["state"]): set(cast(list[str], row["applies_to"]))
             for row in rows}
    assert scope[("positioning_cash_quote_scope", "unknown")] == {"Jposition"}
    assert scope[("separate_ticket_obligation", "unknown")] == {"Jposition"}
    assert scope[("positioning_permission_unknown", "unknown")] == {"Jposition"}
    assert scope[("lead_schedule", "date_only")] == {"Alead"}
    assert scope[("lead_award_tax_quote_scope", "unknown")] == {"Alead"}
    assert scope[("lead_cash_quote_scope", "unknown")] == {"Clead"}
    assert scope[("benchmark_cash_quote_scope", "unknown")] == {"Cbenchmark"}


def test_c11_request_only_adds_condition_table_and_guide() -> None:
    saved = _saved("c10-scout-prior-conditional")
    focus = saved.focus_prepared
    assert focus is not None
    old = _requests(saved.evidence.source, saved.config, saved.selector_prepared,
                    focus, "category-c10")
    new = _requests(saved.evidence.source, saved.config, saved.selector_prepared,
                    focus, "category-c11")
    assert old.request["reasoning"] == new.request["reasoning"] == {"effort": "medium"}
    assert old.request["text"] == new.request["text"]
    assert _document_schema(focus, "category-c10") == _document_schema(focus, "category-c11")
    old_input = json.loads(cast(str, old.request["input"]))
    new_input = json.loads(cast(str, new.request["input"]))
    assert "condition_applicability" not in old_input["packet"]
    assert new_input["packet"].pop("condition_applicability")
    assert new_input == old_input
    assert old.request["instructions"] != new.request["instructions"]


def test_c11_replays_same_raw_answer_with_source_table() -> None:
    saved = _saved("c10-scout-prior-conditional")
    raw_wires = [item.raw_wire for item in saved.passes]
    assert len(raw_wires) == 2 and all(isinstance(raw, str) for raw in raw_wires)

    class SavedWriter:
        def __init__(self) -> None:
            self.calls = 0
            self.pending: WriterReceipt | None = None

        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: InteractiveSettings) -> str:
            raw = raw_wires[self.calls]
            assert isinstance(raw, str)
            self.calls += 1
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
            return raw

        def take_receipt(self) -> WriterReceipt | None:
            result, self.pending = self.pending, None
            return result

    artifact = run_category_results(saved.evidence.source, saved.config,
                                    SavedWriter(), profile="category-c11")
    assert artifact.resolved == saved.resolved
    assert artifact.composer_settings.reasoning_effort == "medium"
    assert artifact.validation_outcome == saved.validation_outcome
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved
