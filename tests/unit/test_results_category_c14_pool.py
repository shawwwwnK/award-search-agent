"""C14 caps the selector's authoring pool, without changing source inventory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator
from test_results_category import _config

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.category import (
    _decode_selection,
    _document_findings,
    _focus,
    _requests,
    _selection_schema,
    _style_aliases,
    _writer_input,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import CheckFinding, ResultsConfig, WriterReceipt
from award_agent.results.focused import prepare_focused_selector
from award_agent.results.focused_wire import decode as decode_document
from award_agent.results.interactive_contracts import InteractiveSettings
from award_agent.results.presentation import resolve_workspace

RUNS = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")


def _saved(case: str) -> Any:
    return parse_category_artifact((RUNS / case / "artifact.json").read_bytes())


def _source_q120() -> SolutionProjection:
    path = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/"
                "review-bundles/q120/evidence.json")
    return SolutionProjection.model_validate(json.loads(path.read_text())["source"])


def _prepared(source: SolutionProjection) -> Any:
    return prepare_focused_selector(source, _config(), resolve_workspace(source),
                                    selection_format="roles-v20")


def _wire(time: str | None, cost: str | None, premium: str | None,
          choices: list[dict[str, str]] | None = None) -> str:
    return json.dumps({"choices": choices or [], "style_audit": {
        "time": {"r": time, "omission_reason": None},
        "cost": {"r": cost, "omission_reason": None},
        "premium": {"r": premium, "omission_reason": None}}})


def test_c14_three_disjoint_style_witnesses_fit_with_one_cash() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    time = next(alias for alias in aliases["time"] if alias not in aliases["premium"])
    premium = next(alias for alias in aliases["premium"] if alias not in aliases["time"])
    cost = next(alias for alias in selector.structured.references.journeys
                if alias not in aliases["time"] and alias not in aliases["premium"])
    # Synthetic style membership isolates the three-way cap, without editing saved evidence.
    indexes = source.view.indexes.model_copy(update={"cost": (
        selector.structured.references.journeys[cost],)})
    synthetic = source.model_copy(update={"view": source.view.model_copy(update={
        "indexes": indexes})})
    cash = selector.packet["benchmark_refs"][0]
    selected = _decode_selection(_wire(time, cost, premium,
                                       [{"k": "b", "r": cash}]),
                                 selector, synthetic, "category-c14")
    assert len(selected.journey_ids) == 3
    assert selected.benchmark_observation_id is not None
    assert set(selected.journey_ids) == {
        selector.structured.references.journeys[alias] for alias in (time, cost, premium)}
    schema = cast(dict[str, Any], _selection_schema(selector, synthetic, "category-c14"))
    assert schema["properties"]["choices"]["maxItems"] == 4
    assert len(selector.structured.references.journeys) == 232  # full inventory retained


def test_c14_overlap_dedup_optional_choices_and_overflow_are_explicit() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    extras = [alias for alias in selector.structured.references.journeys
              if alias != overlap][:3]
    cash = selector.packet["benchmark_refs"][0]
    selected = _decode_selection(_wire(overlap, None, overlap, [
        {"k": "j", "r": overlap}, {"k": "j", "r": extras[0]},
        {"k": "j", "r": extras[1]}, {"k": "b", "r": cash}]),
        selector, source, "category-c14")
    assert selected.journey_ids == tuple(selector.structured.references.journeys[alias]
                                         for alias in (overlap, extras[0], extras[1]))
    assert selected.benchmark_observation_id is not None
    without_cash = _decode_selection(_wire(overlap, None, overlap, [
        {"k": "j", "r": extras[0]}, {"k": "j", "r": extras[1]}]),
        selector, source, "category-c14")
    assert len(without_cash.journey_ids) == 3
    with pytest.raises(ValueError, match="3 nonbenchmark"):
        _decode_selection(_wire(overlap, None, overlap, [
            {"k": "j", "r": alias} for alias in extras]),
            selector, source, "category-c14")
    with pytest.raises(ValueError, match="4-reference bundle"):
        _decode_selection(_wire(overlap, None, overlap, [
            {"k": "j", "r": alias} for alias in extras] +
            [{"k": "b", "r": cash}]), selector, source, "category-c14")
    old = _decode_selection(_wire(overlap, None, overlap, [
        {"k": "j", "r": alias} for alias in extras] +
        [{"k": "b", "r": cash}]), selector, source, "category-c12")
    assert len(old.journey_ids) == 4  # old profile retains its wider bound
    with pytest.raises(ValueError, match="more than one cash benchmark"):
        _decode_selection(_wire(overlap, None, overlap, [
            {"k": "b", "r": first} for first in selector.packet["benchmark_refs"][:2]]),
            selector, source, "category-c14")


def test_c14_schema_valid_witness_union_overflow_stops_after_selection_call() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    extras = [alias for alias in selector.structured.references.journeys
              if alias != overlap][:3]
    raw = _wire(overlap, None, overlap, [{"k": "j", "r": alias} for alias in extras])
    schema = _selection_schema(selector, source, "category-c14")
    assert Draft202012Validator(schema).is_valid(json.loads(raw))

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
    artifact = run_category_results(source, _config(), writer, profile="category-c14")
    assert writer.calls == len(artifact.passes) == 1
    assert artifact.passes[0].selection is None
    assert artifact.focus_prepared is None and artifact.resolved is None
    assert artifact.delivery_outcome == "not_delivered"
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) is None


def test_c14_preserves_old_six_reference_failure_text() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    extras = [alias for alias in selector.structured.references.journeys
              if alias != overlap][:6]
    raw = _wire(overlap, None, overlap, [{"k": "j", "r": alias} for alias in extras])
    with pytest.raises(ValueError, match="category selection exceeds six nonbenchmark references"):
        _decode_selection(raw, selector, source, "category-c12")


def test_c14_three_leads_and_cash_preserve_incomplete_source_roles() -> None:
    saved = _saved("c12-scout-prior-incomplete")
    selector, source = saved.selector_prepared, saved.evidence.source
    leads = list(selector.structured.references.awards)[:3]
    cash = selector.packet["benchmark_refs"][0]
    raw = _wire(None, None, None, [{"k": "l", "r": alias} for alias in leads] +
                [{"k": "b", "r": cash}])
    assert Draft202012Validator(_selection_schema(selector, source, "category-c14")).is_valid(
        json.loads(raw))
    selected = _decode_selection(raw, selector, source, "category-c14")
    assert not selected.journey_ids
    assert len(selected.incomplete_observation_ids) == 3
    assert selected.benchmark_observation_id is not None
    focus = _focus(selected, selector, source, saved.evidence, profile="category-c14")
    packet = _writer_input(focus, profile="category-c14")
    records = cast(dict[str, dict[str, Any]], packet["authoring_records"])
    landscape = cast(dict[str, Any], packet["category_landscape"])
    assert len([record for record in records.values()
                if record["role"] == "lead"]) == 3
    assert not landscape["selected_members"]["time"]
    assert not landscape["selected_members"]["cost"]
    assert not landscape["selected_members"]["premium"]


def test_c14_optional_display_and_existing_category_coverage_check() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    extra = next(alias for alias in selector.structured.references.journeys
                 if alias != overlap)
    cash = selector.packet["benchmark_refs"][0]
    selected = _decode_selection(_wire(overlap, None, overlap, [
        {"k": "j", "r": extra}, {"k": "b", "r": cash}]),
        selector, source, "category-c14")
    focus = _focus(selected, selector, source, resolve_workspace(source), profile="category-c14")
    records = cast(dict[str, dict[str, Any]], _writer_input(
        focus, profile="category-c14")["authoring_records"])
    overlap_long = next(alias for alias in records if alias.startswith(f"{overlap}@"))
    cash_long = next(alias for alias, record in records.items() if record["role"] == "benchmark")
    document = decode_document(json.dumps({"blocks": [
        {"k": "p", "r": overlap_long, "n": "One overlapping option",
         "v": "Consider the timing and cabin if they suit you."},
        {"k": "b", "r": cash_long, "n": "Cash comparison",
         "v": "A cash itinerary was quoted at USD 440, with its total unconfirmed."}]}),
        focus, source)
    assert not any(finding.outcome == "failed" for finding in _document_findings(
        document, source, focus, exact_cash_dedup=True))

    time_only = next(alias for alias in aliases["time"] if alias not in aliases["premium"])
    premium_only = next(alias for alias in aliases["premium"] if alias not in aliases["time"])
    selected2 = _decode_selection(_wire(time_only, None, premium_only, [
        {"k": "b", "r": cash}]), selector, source, "category-c14")
    focus2 = _focus(selected2, selector, source, resolve_workspace(source), profile="category-c14")
    records2 = cast(dict[str, dict[str, Any]], _writer_input(
        focus2, profile="category-c14")["authoring_records"])
    time_long = next(alias for alias in records2 if alias.startswith(f"{time_only}@"))
    cash_long2 = next(alias for alias, record in records2.items() if record["role"] == "benchmark")
    document2 = decode_document(json.dumps({"blocks": [
        {"k": "p", "r": time_long, "n": "Time option",
         "v": "Consider this for its shorter journey."},
        {"k": "b", "r": cash_long2, "n": "Cash comparison",
         "v": "A cash itinerary was quoted at USD 440, with its total unconfirmed."}]}),
        focus2, source)
    assert any(finding.code == "selected_category_not_shown" and finding.outcome == "failed"
               for finding in _document_findings(document2, source, focus2,
                                                 exact_cash_dedup=True))


def test_c14_same_valid_pool_keeps_c12_composer_and_correction_exact() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    cash = selector.packet["benchmark_refs"][0]
    selected = _decode_selection(_wire(overlap, None, overlap, [
        {"k": "b", "r": cash}]), selector, source, "category-c14")
    evidence = resolve_workspace(source)
    c12_focus = _focus(selected, selector, source, evidence, profile="category-c12")
    c14_focus = _focus(selected, selector, source, evidence, profile="category-c14")
    assert c12_focus == c14_focus
    c12 = _requests(source, _config(), selector, c12_focus, "category-c12")
    c14 = _requests(source, _config(), selector, c14_focus, "category-c14")
    assert c12 == c14
    assert c14.request["reasoning"] == {"effort": "medium"}
    finding = CheckFinding(code="duplicate_cash_sentence_in_prose", outcome="failed",
                           scope="benchmark", message="Duplicate cash sentence")
    c12_repair = _requests(source, _config(), selector, c12_focus, "category-c12",
                           previous_wire='{"blocks":[]}', feedback=(finding,))
    c14_repair = _requests(source, _config(), selector, c14_focus, "category-c14",
                           previous_wire='{"blocks":[]}', feedback=(finding,))
    assert c12_repair == c14_repair
    assert c14_repair.request["reasoning"] == {"effort": "low"}


@pytest.mark.parametrize("case", ["c12-scout-prior-admitted",
                                      "c12-scout-prior-conditional",
                                      "c12-scout-prior-incomplete"])
def test_c14_c12_requests_differ_only_in_selector_bound(case: str) -> None:
    saved = _saved(case)
    source, selector, focus = (saved.evidence.source, saved.selector_prepared,
                               saved.focus_prepared)
    assert focus is not None
    old = _requests(source, saved.config, selector, None, "category-c12")
    new = _requests(source, saved.config, selector, None, "category-c14")
    old_schema = cast(dict[str, Any], cast(dict[str, Any], old.request["text"])[
        "format"])["schema"]
    new_schema = cast(dict[str, Any], cast(dict[str, Any], new.request["text"])[
        "format"])["schema"]
    assert old_schema["properties"]["choices"]["maxItems"] == 7
    assert new_schema["properties"]["choices"]["maxItems"] == 4
    old_schema["properties"]["choices"]["maxItems"] = 4
    assert old_schema == new_schema
    assert old.request["input"] == new.request["input"]
    assert old.request["reasoning"] == new.request["reasoning"] == {"effort": "low"}
    assert cast(str, old.request["instructions"]).replace(
        "six nonbenchmark", "three nonbenchmark") == new.request["instructions"]
    old_author = _requests(source, saved.config, selector, focus, "category-c12")
    new_author = _requests(source, saved.config, selector, focus, "category-c14")
    assert old_author.request == new_author.request
    assert old_author.request["reasoning"] == {"effort": "medium"}
    assert _writer_input(focus, profile="category-c12") == _writer_input(
        focus, profile="category-c14")


def test_c14_offline_run_replay_and_cap_bound_request_tamper() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    cash = selector.packet["benchmark_refs"][0]
    selector_raw = _wire(overlap, None, overlap, [{"k": "b", "r": cash}])

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
                    {"k": "p", "r": journey, "n": "Shorter business option",
                     "v": "Business class is worth considering if cabin matters."},
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

    artifact = run_category_results(source, _config(), SavedWriter(),
                                    profile="category-c14")
    assert artifact.resolved is not None
    assert artifact.composer_settings.reasoning_effort == "medium"
    assert len(artifact.passes) == 2
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == \
        artifact.resolved
    tampered = json.loads(artifact.model_dump_json())
    tampered["passes"][0]["request"]["text"]["format"]["schema"]["properties"][
        "choices"]["maxItems"] = 7
    with pytest.raises(ValueError):
        replay_category_results(parse_category_artifact(json.dumps(tampered)))
