"""V9 exact source details retain connection and original-quote association."""

import json
from pathlib import Path

from award_agent.providers.contracts import RawField
from award_agent.results.contracts import ResultsConfig
from award_agent.results.focused import prepare_focused_composer, prepare_focused_selector
from award_agent.results.focused_details import _connection, _quote
from award_agent.results.presentation import resolve_workspace
from award_agent.results.structured_contracts import StructuredResultsArtifact, StructuredSelection
from award_agent.results.workspace_contracts import ConnectionView

SOURCE = Path("evidence/results-stage/m2/structured/2026-10-25-cost-experiments/luna-retest/round-1")


def _case(name):
    saved = StructuredResultsArtifact.model_validate_json(
        (SOURCE / name / "artifact.json").read_bytes())
    projection = saved.evidence.source
    config = ResultsConfig.model_validate_json((SOURCE / name / "config.json").read_bytes())
    config = config.model_copy(update={"model": "gpt-6-luna"})
    evidence = resolve_workspace(projection)
    selector = prepare_focused_selector(projection, config, evidence,
                                        selection_format="roles-v8")
    return projection, evidence, selector


def test_conditional_ist_140_and_420_minute_connections_keep_award_identity() -> None:
    projection, evidence, selector = _case("conditional")
    refs = selector.structured.references
    short_by_candidate = {canonical: short for short, canonical in refs.journeys.items()}
    source_journeys = [j for j in evidence.journeys if any(
        c.kind == "award_connection" and c.airport == "IST" and
        c.wait_minutes in {140, 420} for c in j.connections)]
    short_140 = next(short_by_candidate[j.candidate_id] for j in source_journeys
                     if any(c.wait_minutes == 140 for c in j.connections if c.airport == "IST"))
    short_420 = next(short_by_candidate[j.candidate_id] for j in source_journeys
                     if any(c.wait_minutes == 420 for c in j.connections if c.airport == "IST"))
    details = selector.packet["exact_details"]
    award_140 = details["journey_components"][short_140]["award_ref"]
    award_420 = details["journey_components"][short_420]["award_ref"]
    assert award_140 != award_420
    assert {row["wait_minutes"] for row in details["award_connections"][award_140]
            if row["airport"] == "IST"} == {140}
    assert {row["wait_minutes"] for row in details["award_connections"][award_420]
            if row["airport"] == "IST"} == {420}
    assert all(row["kind"] != "award_connection" for row in
               details["journey_connections"][short_140])
    selected = StructuredSelection(journey_ids=(refs.journeys[short_140],
                                                refs.journeys[short_420]))
    focus = prepare_focused_composer(selected, selector, projection, evidence,
                                      composition_format="complete-v6")
    selected_details = focus.packet["selected_details"]
    assert len(selected_details["journey_components"]) == 2
    assert {row["wait_minutes"] for rows in selected_details["award_connections"].values()
            for row in rows if row["airport"] == "IST"} == {140, 420}
    assert len(json.dumps(selected_details)) < len(json.dumps(details))


def test_original_minor_quotes_have_exact_major_display_and_unknown_scope() -> None:
    _, evidence, selector = _case("incomplete")
    details = selector.packet["exact_details"]["component_quotes"]
    reverse = {canonical: short for short, canonical in
               (selector.structured.references.awards |
                selector.structured.references.cash).items()}
    expected = (("CAD", 11650, "CAD 116.50"),
                ("USD", 2820, "USD 28.20"),
                ("USD", 5090, "USD 50.90"))
    for currency, minor, display in expected:
        component = next(c for c in evidence.components
                         if c.tax_currency.state == "value" and
                         c.tax_currency.value == currency and
                         c.taxes_fees.state == "value" and
                         c.taxes_fees.value == minor and
                         c.taxes_fees_unit == "minor" and
                         c.observation_id in reverse)
        quote = details[reverse[component.observation_id]]
        assert quote["display"] == display
        assert quote["source_unit"] == "minor"
        assert quote["price_scope"] == "unknown"


def test_unknown_wait_and_unsupported_minor_unit_stay_unknown() -> None:
    connection = ConnectionView(airport="IST", arriving_observation_id="a",
        departing_observation_id="b", wait_minutes=None, kind="award_connection",
        unknown_reason="time_not_reported")
    assert _connection(connection) == {"kind": "award_connection", "airport": "IST",
                                      "wait_minutes": None,
                                      "unknown_reason": "time_not_reported"}
    _, evidence, _ = _case("incomplete")
    component = next(c for c in evidence.components if c.taxes_fees_unit == "minor" and
                     c.taxes_fees.state == "value")
    unsupported = component.model_copy(update={
        "tax_currency": RawField(state="value", value="JPY", source_field="currency")})
    quote = _quote(unsupported, kind="award_taxes")
    assert quote["display"] is None
    assert quote["source_unit"] == "minor"
    precise = component.model_copy(update={
        "cash_amount": RawField(state="value", value="1.234", source_field="price"),
        "cash_currency": RawField(state="value", value="BHD", source_field="currency")})
    cash_quote = _quote(precise, kind="cash_fare")
    assert cash_quote["display"] == "BHD 1.234"
