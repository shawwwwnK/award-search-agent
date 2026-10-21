"""Traveler-facing Results v4 formatting and identity checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from award_agent.providers.contracts import RawField
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import (
    CheckFinding,
    ResultsConfig,
    ResultsDocument,
    ResultsPart,
    ResultsSelection,
    authoring_payload,
    check_document as _check_document,
    prepare_results as _prepare_results,
    render_results as _render_results,
)
from award_agent.results.core import _display_money, _notice


def prepare_results(*args, **kwargs):
    kwargs.setdefault("version", "results-artifact-v4")
    return _prepare_results(*args, **kwargs)


def check_document(*args, **kwargs):
    kwargs.setdefault("version", "results-artifact-v4")
    return _check_document(*args, **kwargs)


def render_results(*args, **kwargs):
    kwargs.setdefault("render_version", "results-artifact-v4")
    return _render_results(*args, **kwargs)


def _projection(name: str = "sfo_to_bkk_positioning") -> SolutionProjection:
    return SolutionProjection.model_validate_json(Path(
        f"evidence/ranking-stage/m2/solutions/{name}.json").read_text())


def _config() -> ResultsConfig:
    return ResultsConfig(model="offline", max_output_tokens=1000, timeout_seconds=10,
                         context_limit_tokens=10_000_000, prompt_overhead_tokens=0)


def _shared() -> ResultsPart:
    return ResultsPart(scope="shared", markdown=(
        "Search: {{fact:coverage}}. {{fact:provider_status}}. "
        "Cash comparison: {{fact:benchmark_status}}.\n\n"))


def test_v4_slots_use_local_times_and_currency_amounts() -> None:
    projection = _projection("mixed_access")
    prepared = prepare_results(projection, _config())
    assert prepared.contract_version == "results-prepared-v3"
    assert "source IDs" in prepared.instructions
    journey = next(item for item in projection.view.alternatives
                   if item.status == "admitted" and item.cash_observation_id is None)
    slots = prepared.slots[f"journey:{journey.candidate_id}"]
    assert "UTC" not in slots["departure"]
    assert "Los Angeles time" in slots["departure"]
    assert "T" not in slots["departure"]
    assert "points" in slots["points"]
    assert "minor units" not in slots["fees"]
    assert "minor units" not in prepared.slots[f"benchmark:{projection.view.direct_cash_observation_ids[0]}"]["cash"]
    assert "cash_query" not in prepared.slots["shared"]["coverage"]


def test_v4_request_carries_actual_display_words_without_full_slot_dump() -> None:
    prepared = prepare_results(_projection(), _config())
    payload = json.loads(authoring_payload(prepared))
    source = payload["prepared"]["source"]
    assert "slots" not in payload["prepared"]
    vocabulary = source["display_slot_vocabulary"]
    for key in ("status", "award_price_scope", "provider_status", "requirements"):
        expected = sorted({slot[key] for slot in prepared.slots.values() if key in slot})
        assert vocabulary[key]["values"] == expected
        assert vocabulary[key]["usage"]
    assert "The provider search was incomplete" in vocabulary["provider_status"]["values"][0]
    legacy = prepare_results(_projection(), _config(), version="results-artifact-v3")
    assert "display_slot_vocabulary" not in legacy.source


def test_v4_accepts_visible_option_label_and_exact_equal_schedule_alias() -> None:
    projection = _projection("mixed_access")
    journey = next(item for item in projection.view.alternatives
                   if item.status == "admitted" and item.cash_observation_id is None and
                   item.departure == next(c for c in projection.view.components
                                          if c.observation_id == item.award_observation_id).departure)
    slots = prepare_results(projection, _config()).slots[f"journey:{journey.candidate_id}"]
    required = cast("dict[str, object]", prepare_results(projection, _config()).source[
        "presentation_required_keys"])
    selected = cast("dict[str, list[str]]", required["selected_journey_by_id"])
    assert not {"award_route", "award_departure", "award_arrival"} & set(
        selected[journey.candidate_id])
    omitted = {"journey_id", "award_route", "award_departure", "award_arrival"}
    prose = "Option A. " + " ".join(f"{{{{fact:{key}}}}}" for key in slots if key not in omitted)
    document = ResultsDocument(selection=ResultsSelection(journey_ids=(journey.candidate_id,)),
        parts=(_shared(), ResultsPart(scope="journey", reference_id=journey.candidate_id,
                                      identifier="Option A", markdown=prose)))
    findings = check_document(document, projection)
    codes = {finding.code for finding in findings if finding.outcome == "failed"}
    assert not codes & {"missing_disclosure:journey_id", "missing_disclosure:award_route",
                        "missing_disclosure:award_departure", "missing_disclosure:award_arrival",
                        "missing_visible_option_label"}
    rendered, _ = render_results(document, projection)
    assert journey.candidate_id not in rendered


def test_v4_observation_labels_replace_visible_source_ids_and_must_be_unique() -> None:
    projection = _projection()
    first, second = projection.view.award_summary_observation_ids[:2]
    prepared = prepare_results(projection, _config())
    assert "departure_date" in prepared.slots[f"incomplete:{first}"]
    def part(observation_id: str, label: str) -> ResultsPart:
        slots = prepared.slots[f"incomplete:{observation_id}"]
        return ResultsPart(scope="incomplete", reference_id=observation_id,
            identifier=label, markdown=label + ". " + " ".join(
                f"{{{{fact:{key}}}}}" for key in slots if key != "observation_id"))
    document = ResultsDocument(selection=ResultsSelection(
        incomplete_observation_ids=(first, second)),
        parts=(_shared(), part(first, "Award lead A"), part(second, "Award lead B")))
    findings = check_document(document, projection)
    codes = {finding.code for finding in findings if finding.outcome == "failed"}
    assert "missing_disclosure:observation_id" not in codes
    assert "unavailable_fact" not in codes
    rendered, _ = render_results(document, projection)
    assert first not in rendered and second not in rendered
    reused = document.model_copy(update={"parts": (
        _shared(), part(first, "Award lead A"), part(second, "Award lead A"))})
    assert any(finding.code == "identifier_reused" for finding in check_document(reused, projection))
    resumed = document.model_copy(update={"parts": (
        _shared(), part(first, "Award lead A"), part(second, "Award lead B"),
        part(first, "Award lead A").model_copy(update={"identifier": None}))})
    assert any(finding.code == "resumed_identity" for finding in check_document(resumed, projection))


def test_v4_money_preserves_known_amount_precision_and_unknown_currency() -> None:
    amount = RawField(state="value", value=11320)
    cad = RawField(state="value", value="CAD")
    assert _display_money(amount, cad, "minor") == "113.20 CAD"
    assert _display_money(RawField(state="value", value=0), cad, "minor") == "0.00 CAD"
    assert _display_money(RawField(), cad, "minor") == "Amount not reported"
    kwd = RawField(state="value", value="KWD")
    assert _display_money(RawField(state="value", value="1.234"), kwd) == "1.234 KWD"
    assert "currency not reported" in _display_money(amount, RawField(), "minor")


def test_v4_failed_price_scope_notice_names_award_and_cash_scope() -> None:
    projection = _projection()
    candidate = next(item for item in projection.view.alternatives
                     if item.cash_observation_id)
    finding = CheckFinding(code="claim:price_scope:party_total", outcome="failed",
        scope="journey", reference_id=candidate.candidate_id, part_index=1,
        message="The assertion ‘All prices cover the party’ is failed.",
        supplied_fact="Quote scopes: per_traveler, party.")
    notice = _notice(finding, projection, "results-artifact-v4")
    assert "All prices cover the party" in notice.text
    assert "Award quote" in notice.text
    assert "Cash quote" in notice.text
    assert candidate.candidate_id not in notice.text


def test_v4_zero_journey_notice_and_partial_status_do_not_imply_results() -> None:
    projection = _projection()
    finding = CheckFinding(code="missing_disclosure:no_complete_journeys", outcome="failed",
        scope="shared", message="No complete journey finding was omitted.")
    notice = _notice(finding, projection, "results-artifact-v4")
    assert "No complete award journey was found" in notice.text
    assert "No complete journey finding was omitted" not in notice.text
    slots = prepare_results(projection, _config()).slots["shared"]
    assert "returned results" not in slots["provider_status"]


def test_v4_mixed_journey_cannot_use_single_award_schedule_alias() -> None:
    projection = _projection()
    journey = next(item for item in projection.view.alternatives
                   if item.status in {"admitted", "conditional"} and item.cash_observation_id)
    keys = prepare_results(projection, _config()).slots[f"journey:{journey.candidate_id}"]
    required = cast("dict[str, object]", prepare_results(projection, _config()).source[
        "presentation_required_keys"])
    selected = cast("dict[str, list[str]]", required["selected_journey_by_id"])
    assert {"award_route", "award_departure", "award_arrival"} <= set(
        selected[journey.candidate_id])
    omitted = {"journey_id", "award_route", "award_departure", "award_arrival"}
    document = ResultsDocument(selection=ResultsSelection(journey_ids=(journey.candidate_id,)),
        parts=(_shared(), ResultsPart(scope="journey", reference_id=journey.candidate_id,
            identifier="Option A", markdown="Option A. " + " ".join(
                f"{{{{fact:{key}}}}}" for key in keys if key not in omitted))))
    codes = {finding.code for finding in check_document(document, projection)
             if finding.outcome == "failed"}
    assert {"missing_disclosure:award_route", "missing_disclosure:award_departure",
            "missing_disclosure:award_arrival"} <= codes


def test_v4_flags_heading_joined_to_previous_part() -> None:
    projection = _projection()
    lead = projection.view.award_summary_observation_ids[0]
    document = ResultsDocument(selection=ResultsSelection(incomplete_observation_ids=(lead,)),
        parts=(ResultsPart(scope="shared", markdown="These leads need checking."),
               ResultsPart(scope="incomplete", reference_id=lead,
                           identifier="Award lead A", markdown="### Award lead A\n\nDetails.")))
    assert any(finding.code == "boundary_spacing" for finding in check_document(document, projection))
    spaced = document.model_copy(update={"parts": (document.parts[0],
        document.parts[1].model_copy(update={"markdown": "\n### Award lead A\n\nDetails."}))})
    assert not any(finding.code == "boundary_spacing" for finding in check_document(spaced, projection))
