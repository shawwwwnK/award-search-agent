"""C15 indexes only the model's selected choices; audits add no references."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator
from test_results_category import _config
from test_results_category_c14_pool import _prepared, _source_q120

from award_agent.results.category import (
    _decode_selection,
    _focus,
    _requests,
    _selection_findings,
    _selection_schema,
    _style_aliases,
    _writer_input,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import CheckFinding, ResultsConfig, WriterReceipt
from award_agent.results.interactive_contracts import InteractiveSettings
from award_agent.results.presentation import resolve_workspace

RUNS = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")


def _saved(case: str) -> Any:
    return parse_category_artifact((RUNS / case / "artifact.json").read_bytes())


def _wire(choices: list[dict[str, str]], benchmark: str | None,
          time: int | None, premium: int | None, *,
          cost: int | None = None, time_reason: str | None = None,
          premium_reason: str | None = None, cost_reason: str | None = None) -> str:
    return json.dumps({"choices": choices, "benchmark_alias": benchmark, "style_audit": {
        "time": {"choice_index": time, "omission_reason": time_reason},
        "cost": {"choice_index": cost, "omission_reason": cost_reason},
        "premium": {"choice_index": premium, "omission_reason": premium_reason}}})


def test_c15_schema_indexes_only_choices_and_separates_cash() -> None:
    source = _source_q120()
    selector = _prepared(source)
    schema = cast(dict[str, Any], _selection_schema(selector, source, "category-c15"))
    assert schema["required"] == ["choices", "benchmark_alias", "style_audit"]
    assert schema["properties"]["choices"]["maxItems"] == 3
    kinds = {branch["properties"]["k"]["enum"][0]
             for branch in schema["properties"]["choices"]["items"]["anyOf"]}
    assert kinds == {"j", "l"}
    assert schema["properties"]["benchmark_alias"]["anyOf"][0]["enum"] == \
        selector.packet["benchmark_refs"]
    audit = schema["properties"]["style_audit"]
    assert audit["required"] == ["time", "cost", "premium"]
    assert audit["properties"]["time"]["anyOf"][0]["properties"][
        "choice_index"]["enum"] == [0, 1, 2]
    assert audit["properties"]["cost"]["properties"]["choice_index"] == {
        "type": "null"}


def test_c15_disjoint_styles_cash_and_overlap_normalize_without_added_refs() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    time = next(alias for alias in aliases["time"] if alias not in aliases["premium"])
    premium = next(alias for alias in aliases["premium"] if alias not in aliases["time"])
    cost = next(alias for alias in selector.structured.references.journeys
                if alias not in aliases["time"] and alias not in aliases["premium"])
    indexes = source.view.indexes.model_copy(update={"cost": (
        selector.structured.references.journeys[cost],)})
    synthetic = source.model_copy(update={"view": source.view.model_copy(update={
        "indexes": indexes})})
    cash = selector.packet["benchmark_refs"][0]
    raw = _wire([{"k": "j", "r": alias} for alias in (time, cost, premium)],
                cash, 0, 2, cost=1)
    assert Draft202012Validator(_selection_schema(selector, synthetic, "category-c15")).is_valid(
        json.loads(raw))
    selection = _decode_selection(raw, selector, synthetic, "category-c15")
    assert selection.journey_ids == tuple(selector.structured.references.journeys[alias]
                                          for alias in (time, cost, premium))
    assert selection.benchmark_observation_id is not None
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    one = _wire([{"k": "j", "r": overlap}], cash, 0, 0)
    selected = _decode_selection(one, selector, source, "category-c15")
    assert selected.journey_ids == (selector.structured.references.journeys[overlap],)
    assert selected.benchmark_observation_id is not None
    assert not _selection_findings(one, selected, source, "category-c15")


def test_c15_three_leads_plus_cash_and_source_omission_audit() -> None:
    saved = _saved("c12-scout-prior-incomplete")
    source, selector = saved.evidence.source, saved.selector_prepared
    leads = list(selector.structured.references.awards)[:3]
    cash = selector.packet["benchmark_refs"][0]
    raw = _wire([{"k": "l", "r": alias} for alias in leads], cash, None, None)
    assert Draft202012Validator(_selection_schema(selector, source, "category-c15")).is_valid(
        json.loads(raw))
    selected = _decode_selection(raw, selector, source, "category-c15")
    assert len(selected.incomplete_observation_ids) == 3 and not selected.journey_ids
    assert selected.benchmark_observation_id is not None
    focus = _focus(selected, selector, source, saved.evidence, profile="category-c15")
    packet = _writer_input(focus, profile="category-c15")
    assert len([row for row in cast(dict[str, dict[str, Any]], packet[
        "authoring_records"]).values() if row["role"] == "lead"]) == 3
    assert not any(cast(dict[str, Any], packet["category_landscape"])[
        "selected_members"].values())

    complete = _source_q120()
    complete_selector = _prepared(complete)
    aliases = _style_aliases(complete_selector, complete)
    time_only = next(alias for alias in aliases["time"] if alias not in aliases["premium"])
    omitted = _wire([{"k": "j", "r": time_only}], None, 0, None,
                    premium_reason="No separate premium perspective adds value")
    audited = _decode_selection(omitted, complete_selector, complete, "category-c15")
    findings = _selection_findings(omitted, audited, complete, "category-c15")
    assert [(item.code, item.outcome) for item in findings] == [
        ("cash_context_omitted", "failed"), ("category_omitted", "unchecked")]


@pytest.mark.parametrize(("bad_index", "schema_valid"), [
    (True, False), (1.0, True), (1.5, False), (-1, False), (3, False), (1, True),
])
def test_c15_rejects_boolean_fractional_negative_and_out_of_range_index(
        bad_index: object, schema_valid: bool) -> None:
    source = _source_q120()
    selector = _prepared(source)
    overlap = next(alias for alias in _style_aliases(selector, source)["time"]
                   if alias in _style_aliases(selector, source)["premium"])
    value = json.loads(_wire([{"k": "j", "r": overlap}], None, 0, 0))
    value["style_audit"]["time"]["choice_index"] = bad_index
    assert Draft202012Validator(_selection_schema(selector, source, "category-c15")).is_valid(
        value) is schema_valid
    with pytest.raises(ValueError, match="witness"):
        _decode_selection(json.dumps(value), selector, source, "category-c15")


def test_c15_rejects_lead_index_wrong_style_false_omission_and_invalid_aliases() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    premium_only = next(alias for alias in aliases["premium"] if alias not in aliases["time"])
    lead = next(iter(selector.structured.references.awards))
    base = json.loads(_wire([{"k": "j", "r": overlap}], None, 0, 0))
    invalid = []
    wrong = deepcopy(base)
    wrong["choices"][0]["r"] = premium_only
    invalid.append(wrong)
    lead_index = deepcopy(base)
    lead_index["choices"][0] = {"k": "l", "r": lead}
    invalid.append(lead_index)
    false_omission = deepcopy(base)
    false_omission["style_audit"]["premium"] = {
        "choice_index": None, "omission_reason": "Premium omitted"}
    invalid.append(false_omission)
    incidental = deepcopy(base)
    time_only = next(alias for alias in aliases["time"] if alias not in aliases["premium"])
    incidental["choices"] = [{"k": "j", "r": time_only},
                             {"k": "j", "r": premium_only}]
    incidental["style_audit"]["premium"] = {
        "choice_index": None, "omission_reason": "Premium omitted"}
    invalid.append(incidental)
    absent_reason = deepcopy(base)
    absent_reason["style_audit"]["cost"]["omission_reason"] = "No cost style"
    invalid.append(absent_reason)
    blank_omission = deepcopy(base)
    blank_omission["choices"] = [{"k": "j", "r": time_only}]
    blank_omission["style_audit"]["premium"] = {
        "choice_index": None, "omission_reason": "  "}
    invalid.append(blank_omission)
    null_omission = deepcopy(blank_omission)
    null_omission["style_audit"]["premium"]["omission_reason"] = None
    invalid.append(null_omission)
    wrong_role = deepcopy(base)
    wrong_role["choices"][0]["k"] = "b"
    invalid.append(wrong_role)
    wrong_alias = deepcopy(base)
    wrong_alias["choices"][0]["r"] = "J999999"
    invalid.append(wrong_alias)
    duplicate = deepcopy(base)
    duplicate["choices"].append(duplicate["choices"][0])
    invalid.append(duplicate)
    bad_cash = deepcopy(base)
    bad_cash["benchmark_alias"] = lead
    invalid.append(bad_cash)
    positioning = next(alias for alias in selector.structured.references.cash
                       if alias not in selector.packet["benchmark_refs"])
    bad_positioning_cash = deepcopy(base)
    bad_positioning_cash["benchmark_alias"] = positioning
    invalid.append(bad_positioning_cash)
    for value in invalid:
        with pytest.raises(ValueError):
            _decode_selection(json.dumps(value), selector, source, "category-c15")
    too_many = deepcopy(base)
    too_many["choices"] += [{"k": "j", "r": alias}
                            for alias in list(selector.structured.references.journeys)[1:4]]
    assert len(too_many["choices"]) == 4
    assert not Draft202012Validator(_selection_schema(selector, source, "category-c15")).is_valid(
        too_many)
    with pytest.raises(ValueError, match="3 nonbenchmark"):
        _decode_selection(json.dumps(too_many), selector, source, "category-c15")


def test_c15_same_normalized_pool_keeps_c14_focus_author_and_repair() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    extra = next(alias for alias in selector.structured.references.journeys
                 if alias != overlap)
    cash = selector.packet["benchmark_refs"][0]
    c14_raw = json.dumps({"choices": [{"k": "j", "r": extra}, {"k": "b", "r": cash}],
        "style_audit": {"time": {"r": overlap, "omission_reason": None},
                        "cost": {"r": None, "omission_reason": None},
                        "premium": {"r": overlap, "omission_reason": None}}})
    c15_raw = _wire([{"k": "j", "r": overlap}, {"k": "j", "r": extra}], cash, 0, 0)
    old = _decode_selection(c14_raw, selector, source, "category-c14")
    new = _decode_selection(c15_raw, selector, source, "category-c15")
    assert old == new
    evidence = resolve_workspace(source)
    old_focus = _focus(old, selector, source, evidence, profile="category-c14")
    new_focus = _focus(new, selector, source, evidence, profile="category-c15")
    assert old_focus == new_focus
    assert _writer_input(old_focus, profile="category-c14") == _writer_input(
        new_focus, profile="category-c15")
    old_author = _requests(source, _config(), selector, old_focus, "category-c14")
    new_author = _requests(source, _config(), selector, new_focus, "category-c15")
    assert old_author == new_author
    assert new_author.request["reasoning"] == {"effort": "medium"}
    finding = CheckFinding(code="duplicate_cash_sentence_in_prose", outcome="failed",
                           scope="benchmark", message="Duplicate cash sentence")
    old_repair = _requests(source, _config(), selector, old_focus, "category-c14",
                           previous_wire='{"blocks":[]}', feedback=(finding,))
    new_repair = _requests(source, _config(), selector, new_focus, "category-c15",
                           previous_wire='{"blocks":[]}', feedback=(finding,))
    assert old_repair == new_repair
    assert new_repair.request["reasoning"] == {"effort": "low"}


def test_c15_offline_run_replay_and_selector_wire_tamper() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    cash = selector.packet["benchmark_refs"][0]
    selector_raw = _wire([{"k": "j", "r": overlap}], cash, 0, 0)

    class SavedWriter:
        def __init__(self) -> None:
            self.calls = 0
            self.pending: WriterReceipt | None = None

        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: InteractiveSettings) -> str:
            if self.calls == 0:
                raw = selector_raw
            else:
                schema = cast(dict[str, Any], cast(dict[str, Any], request["text"])[
                    "format"])["schema"]
                branches = schema["properties"]["blocks"]["items"]["anyOf"]
                journey = next(branch["properties"]["r"]["enum"][0]
                               for branch in branches if branch["properties"]["k"]["enum"] == ["p", "a"])
                benchmark = next(branch["properties"]["r"]["enum"][0]
                                 for branch in branches if branch["properties"]["k"]["enum"] == ["b"])
                raw = json.dumps({"blocks": [
                    {"k": "p", "r": journey, "n": "Business option",
                     "v": "Consider the cabin and timing if they suit you."},
                    {"k": "b", "r": benchmark, "n": "Cash comparison",
                     "v": "A cash itinerary was quoted at USD 440, with its total unconfirmed."}]})
            self.calls += 1
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
            return raw

        def take_receipt(self) -> WriterReceipt | None:
            pending, self.pending = self.pending, None
            return pending

    artifact = run_category_results(source, _config(), SavedWriter(), profile="category-c15")
    assert artifact.resolved is not None and len(artifact.passes) == 2
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == \
        artifact.resolved
    tampered = json.loads(artifact.model_dump_json())
    tampered["passes"][0]["request"]["text"]["format"]["schema"]["properties"][
        "choices"]["maxItems"] = 4
    with pytest.raises(ValueError):
        replay_category_results(parse_category_artifact(json.dumps(tampered)))
    old_overflow = _saved("c14-scout-prior-admitted")
    assert old_overflow.delivery_outcome == "not_delivered"
    assert replay_category_results(old_overflow) is None


def test_c15_invalid_index_stops_after_one_selection_call_and_replays_failure() -> None:
    source = _source_q120()
    selector = _prepared(source)
    overlap = next(alias for alias in _style_aliases(selector, source)["time"]
                   if alias in _style_aliases(selector, source)["premium"])
    raw = _wire([{"k": "j", "r": overlap}], None, 1, 0)
    assert Draft202012Validator(_selection_schema(selector, source, "category-c15")).is_valid(
        json.loads(raw))

    class OneCallWriter:
        def __init__(self) -> None:
            self.calls = 0
            self.pending: WriterReceipt | None = None

        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: InteractiveSettings) -> str:
            self.calls += 1
            assert self.calls == 1
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
            return raw

        def take_receipt(self) -> WriterReceipt | None:
            pending, self.pending = self.pending, None
            return pending

    writer = OneCallWriter()
    artifact = run_category_results(source, _config(), writer, profile="category-c15")
    assert writer.calls == len(artifact.passes) == 1
    assert artifact.resolved is None and artifact.focus_prepared is None
    assert artifact.delivery_outcome == "not_delivered"
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) is None
