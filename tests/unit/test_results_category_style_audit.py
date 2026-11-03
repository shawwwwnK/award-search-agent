"""C07 explicit style witnesses select exact source members without quotas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from test_results_category import CategoryWriter, _config, _source

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.category import (
    _decode_selection,
    _focus,
    _selection_findings,
    _selection_schema,
    _style_aliases,
    _writer_input,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt
from award_agent.results.focused import prepare_focused_selector
from award_agent.results.presentation import resolve_workspace


def _source_q120() -> SolutionProjection:
    path = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/"
                "review-bundles/q120/evidence.json")
    return SolutionProjection.model_validate(json.loads(path.read_text())["source"])


def _prepared(source: SolutionProjection) -> Any:
    return prepare_focused_selector(source, _config(), resolve_workspace(source),
                                    selection_format="roles-v20")


def _wire(time: str | None, premium: str | None,
          *, choices: list[dict[str, str]] | None = None,
          time_reason: str = "", premium_reason: str = "") -> str:
    return json.dumps({"choices": choices or [], "style_audit": {
        "time": {"r": time, "omission_reason": time_reason},
        "cost": {"r": None, "omission_reason": ""},
        "premium": {"r": premium, "omission_reason": premium_reason}}})


def test_c07_schema_requires_each_style_and_witness_selects_without_free_choice() -> None:
    source = _source()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    schema = cast(dict[str, Any], _selection_schema(selector, source, "category-c07"))
    assert schema["required"] == ["choices", "style_audit"]
    assert schema["properties"]["choices"]["minItems"] == 0
    audit = schema["properties"]["style_audit"]
    assert audit["required"] == ["time", "cost", "premium"]
    assert audit["properties"]["premium"]["properties"]["r"]["anyOf"][0]["enum"] == aliases["premium"]
    assert aliases["time"] and aliases["premium"]
    selected = _decode_selection(_wire(aliases["time"][0], aliases["premium"][0]),
                                 selector, source, "category-c07")
    refs = selector.structured.references.journeys
    assert set(selected.journey_ids) == {refs[aliases["time"][0]],
                                         refs[aliases["premium"][0]]}
    assert {row.code for row in _selection_findings(
        _wire(aliases["time"][0], aliases["premium"][0]),
        selected, source, "category-c07")} == {"cash_context_omitted"}


def test_c07_overlap_deduplicates_witness_and_keeps_free_alternative() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    extra = next(alias for alias in selector.structured.references.journeys
                 if alias != overlap)
    raw = _wire(overlap, overlap, choices=[{"k": "j", "r": extra}])
    selected = _decode_selection(raw, selector, source, "category-c07")
    refs = selector.structured.references.journeys
    assert selected.journey_ids == (refs[overlap], refs[extra])
    assert {row.code for row in _selection_findings(raw, selected, source,
                                                   "category-c07")} == {"cash_context_omitted"}


def test_c07_missing_wrong_style_and_overfull_union_fail_explicitly() -> None:
    source = _source()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    valid = json.loads(_wire(aliases["time"][0], aliases["premium"][0]))
    del valid["style_audit"]["premium"]
    with pytest.raises(ValueError, match="every style audit"):
        _decode_selection(json.dumps(valid), selector, source, "category-c07")
    wrong = next(alias for alias in aliases["time"] if alias not in aliases["premium"])
    with pytest.raises(ValueError, match="not a source style member"):
        _decode_selection(_wire(aliases["time"][0], wrong), selector, source,
                          "category-c07")
    with pytest.raises(ValueError, match="omission requires"):
        _decode_selection(_wire(None, aliases["premium"][0]), selector, source,
                          "category-c07")
    invalid_absent = json.loads(_wire(aliases["time"][0], aliases["premium"][0]))
    invalid_absent["style_audit"]["cost"]["omission_reason"] = "No cost choice"
    with pytest.raises(ValueError, match="omission requires"):
        _decode_selection(json.dumps(invalid_absent), selector, source,
                          "category-c07")
    extras = [alias for alias in selector.structured.references.journeys
              if alias not in {aliases["time"][0], aliases["premium"][0]}][:5]
    assert len(extras) == 5
    with pytest.raises(ValueError, match="reference bundle|six nonbenchmark"):
        _decode_selection(_wire(aliases["time"][0], aliases["premium"][0],
                                choices=[{"k": "j", "r": alias} for alias in extras]),
                          selector, source, "category-c07")


def test_c07_incidental_overlap_makes_omission_audit_spurious() -> None:
    source = _source_q120()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    overlap = next(alias for alias in aliases["time"] if alias in aliases["premium"])
    raw = _wire(None, overlap, time_reason="No distinct time benefit")
    selected = _decode_selection(raw, selector, source, "category-c07")
    assert "spurious_category_omission" in {
        row.code for row in _selection_findings(raw, selected, source, "category-c07")}


def test_c07_available_omission_is_audited_without_passing_reason_to_author() -> None:
    source = _source()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    time_only = next(alias for alias in aliases["time"] if alias not in aliases["premium"])
    raw = _wire(time_only, None, premium_reason="No separate premium benefit for this brief",
                choices=[{"k": "b", "r": selector.packet["benchmark_refs"][0]}])
    selected = _decode_selection(raw, selector, source, "category-c07")
    findings = _selection_findings(raw, selected, source, "category-c07")
    assert len(findings) == 1 and findings[0].code == "category_omitted"
    assert findings[0].outcome == "unchecked"
    packet = _writer_input(_focus(selected, selector, source, resolve_workspace(source),
                                  profile="category-c07"), profile="category-c07")
    assert "No separate premium benefit" not in json.dumps(packet)


def test_c07_cash_quote_keeps_major_unit_without_irrelevant_fee_unit() -> None:
    source = _source()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    benchmark = selector.packet["benchmark_refs"][0]
    selected = _decode_selection(_wire(aliases["time"][0], aliases["premium"][0],
                                       choices=[{"k": "b", "r": benchmark}]),
                                 selector, source, "category-c07")
    evidence = resolve_workspace(source)
    old_focus = _focus(selected, selector, source, evidence, profile="category-c06")
    new_focus = _focus(selected, selector, source, evidence, profile="category-c07")
    old = _writer_input(old_focus, profile="category-c06")
    new = _writer_input(new_focus, profile="category-c07")
    old_cash = next(record for record in cast(dict[str, Any], old["authoring_records"]).values()
                    if record["role"] == "benchmark")
    new_cash = next(record for record in cast(dict[str, Any], new["authoring_records"]).values()
                    if record["role"] == "benchmark")
    assert old_cash["facts"]["fee_unit"] == "unknown"
    assert "fee_unit" not in new_cash["facts"]
    assert old_cash["quote"] == new_cash["quote"]
    assert any(group["facts"].get("fee_unit") == "unknown"
               for group in cast(dict[str, Any], new_focus.packet)["benchmarks"])


def test_c07_run_and_replay_with_style_witnesses() -> None:
    source = _source()
    selector = _prepared(source)
    aliases = _style_aliases(selector, source)
    benchmark = selector.packet["benchmark_refs"][0]
    selection_raw = _wire(aliases["time"][0], aliases["premium"][0],
                          choices=[{"k": "b", "r": benchmark}])

    class StyleWriter(CategoryWriter):
        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: object) -> str:
            if self.requests:
                return super().author(request, config, settings)
            self.requests.append(request)
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text",
                                                     "text": selection_raw}]}]}))
            return selection_raw

    artifact = run_category_results(source, _config(), StyleWriter(), profile="category-c07")
    assert artifact.validation_outcome == "clean"
    assert artifact.resolved is not None
    assert len(artifact.passes) == 2
    assert artifact.focus_prepared is not None
    cash = next(record for record in cast(dict[str, Any], _writer_input(
        artifact.focus_prepared, profile="category-c07")["authoring_records"]).values()
        if record["role"] == "benchmark")
    assert cash["quote"]["kind"] == "cash_fare"
    assert cash["quote"]["source_unit"] == "major"
    assert "fee_unit" not in cash["facts"]
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved
