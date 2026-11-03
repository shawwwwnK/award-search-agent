"""Controls for the four assumption failures in the stopped campaign verifier."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import ledger
import preview
import preview_loader
import pytest
import review_bundle
import run
import verify

from award_agent.results.contracts import ResultsConfig


def test_blind_selection_audit_preserves_style_witnesses_and_omissions() -> None:
    wire = {"choices": [{"k": "j", "r": "J2"}], "style_audit": {
        "time": {"r": "J1", "omission_reason": None},
        "cost": {"r": None, "omission_reason": "No useful price distinction"},
        "premium": {"r": None, "omission_reason": None}}}
    audit = review_bundle.selection_wire_audit(wire)
    assert audit["free_choices"] == wire["choices"]
    assert audit["style_audit"] == wire["style_audit"]
    assert audit["omitted_reasons"] == [
        {"style": "cost", "reason": "No useful price distinction"}]


def test_blind_selection_audit_preserves_legacy_omissions() -> None:
    wire = {"choices": [], "omitted": [{"style": "premium", "reason": "No added value"}]}
    audit = review_bundle.selection_wire_audit(wire)
    assert audit["style_audit"] is None
    assert audit["omitted_reasons"] == wire["omitted"]


def test_indexed_selection_audit_binds_only_returned_choices() -> None:
    artifact = ledger.read_json(run.RUNS / "c14-scout-prior-admitted" / "artifact.json")
    old_wire = json.loads(artifact["passes"][0]["raw_wire"])
    references = artifact["selector_prepared"]["structured"]["authoring_view"]["references"]
    old_audit = review_bundle.selection_wire_audit(old_wire, references=references)
    assert old_audit["free_choices"] == old_wire["choices"]
    assert old_audit["style_audit"] == old_wire["style_audit"]
    assert "indexed_witnesses" not in old_audit
    assert old_wire["style_audit"]["premium"]["r"] == "J217"

    indexed = {"choices": [{"k": "j", "r": "J13"},
                           {"k": "j", "r": "J7"},
                           {"k": "j", "r": "J217"}],
               "benchmark_alias": "C1",
               "style_audit": {
                   "time": {"choice_index": 1, "omission_reason": None},
                   "cost": {"choice_index": None, "omission_reason": None},
                   "premium": {"choice_index": 2, "omission_reason": None}}}
    audit = review_bundle.selection_wire_audit(indexed, references=references)
    assert audit["raw_selection_wire"] == indexed
    assert audit["free_choices"] == indexed["choices"]
    assert audit["style_audit"] == indexed["style_audit"]
    assert audit["omitted_reasons"] == []
    assert audit["indexed_witnesses"] == {
        "time": {"choice_index": 1, "alias": "J7",
                 "canonical_id": references["journeys"]["J7"]},
        "premium": {"choice_index": 2, "alias": "J217",
                    "canonical_id": references["journeys"]["J217"]}}
    assert audit["benchmark_alias"] == "C1"
    assert audit["benchmark_canonical_id"] == references["cash"]["C1"]

    omitted = dict(indexed, style_audit={**indexed["style_audit"],
        "premium": {"choice_index": None,
                    "omission_reason": "No distinct benefit in this answer"}})
    assert review_bundle.selection_wire_audit(omitted, references=references)[
        "omitted_reasons"] == [{"style": "premium",
                                "reason": "No distinct benefit in this answer"}]


def test_indexed_selection_audit_rejects_unbound_witness_or_benchmark() -> None:
    references = {"journeys": {"J1": "canonical-journey"},
                  "cash": {"C1": "canonical-cash"}}
    valid = {"choices": [{"k": "j", "r": "J1"}], "benchmark_alias": "C1",
             "style_audit": {"time": {"choice_index": 0,
                                      "omission_reason": None}}}
    for index in (1, True):
        invalid = dict(valid, style_audit={"time": {
            "choice_index": index, "omission_reason": None}})
        with pytest.raises(ValueError):
            review_bundle.selection_wire_audit(invalid, references=references)
    for choice in ({"k": "l", "r": "A1"}, {"k": "j", "r": "J2"}):
        with pytest.raises(ValueError):
            review_bundle.selection_wire_audit(dict(valid, choices=[choice]),
                                               references=references)
    with pytest.raises(ValueError):
        review_bundle.selection_wire_audit(dict(valid, benchmark_alias="C2"),
                                           references=references)


def test_undelivered_draw_reservations_keep_bundle_index_contract() -> None:
    index = ledger.read_json(review_bundle.INDEX)
    assert len({row["run"] for row in index.values()}) == len(index)
    for number, case in enumerate(("prior-admitted", "prior-conditional",
                                   "prior-incomplete"), 19):
        row = index[f"q{number:03d}"]
        name = f"c07-scout-{case}"
        assert row["run"] == name
        assert row["artifact_sha256"] == ledger.sha256(run.RUNS / name / "artifact.json")
        assert row["delivery"] == "not_delivered"
        assert "answer_sha256" not in row
        assert not (review_bundle.HERE / "review-bundles" / f"q{number:03d}").exists()


def test_observed_fault_code_is_exact() -> None:
    findings = [{"code": "visible_internal_alias", "outcome": "failed"}]
    assert verify.observed_fault_issues(
        expected_code="visible_internal_alias", first_findings=findings,
        correction_count=1) == []
    assert verify.observed_fault_issues(
        expected_code="empty_explanation", first_findings=findings,
        correction_count=1)
    assert verify.observed_fault_issues(
        expected_code="visible_internal_alias", first_findings=findings,
        correction_count=0)


def test_one_pass_api_incomplete_is_valid_failure() -> None:
    failed = SimpleNamespace(delivery_outcome="not_delivered", resolved=None,
                             passes=[SimpleNamespace(phase="selection", outcome="api_error")])
    assert verify.failure_shape_issues(failed) == []
    failed.resolved = object()
    assert verify.failure_shape_issues(failed)


def test_guidance_required_only_in_applicable_branch() -> None:
    marker = "same-program preference"
    complete = {"instructions": "explain supported Ranking perspectives"}
    incomplete = {"instructions": "explain the same-program preference"}
    assert verify.branch_guidance_issues(complete, incomplete=False, marker=marker) == []
    assert verify.branch_guidance_issues(incomplete, incomplete=True, marker=marker) == []
    assert verify.branch_guidance_issues(complete, incomplete=True, marker=marker)


def test_empty_comparison_pairs_valid_for_single_lead() -> None:
    assert verify.comparison_pairs_issues([], same_role_selected=1) == []
    assert verify.comparison_pairs_issues([], same_role_selected=2)
    assert verify.comparison_pairs_issues(None, same_role_selected=1)


def test_six_source_identities_include_three_distinct_ranking_exports() -> None:
    cases = run.source_registry()
    assert len(cases) == 6
    assert sum(row["kind"] == "ranking_projection" for row in cases.values()) == 3
    keys = {(run.projection_for(case).receipt.source_digest,
             run.projection_for(case).receipt.view_digest) for case in cases}
    assert len(keys) == 6


def test_preview_shows_real_flight_card_and_inline_cash() -> None:
    path = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/review-bundles/q119/evidence.json")
    evidence = json.loads(path.read_text())
    journey = evidence["journeys"][0]
    artifact = {"evidence": evidence, "resolved": {"blocks": [
        {"kind": "narrative", "text": "A shorter trip may fit you."},
        {"kind": "journey_card", "label": "Aeroplan via Hong Kong",
         "canonical_id": journey["candidate_id"], "journey": journey,
         "award_component": next(c for c in evidence["components"]
                                 if c["observation_id"] == journey["award_observation_id"]),
         "text": "The shorter journey, with an overnight departure."},
        {"kind": "cash_sentence", "text": "A separate cash fare was quoted at USD 440."},
    ]}}
    markdown = preview.render_markdown(artifact)
    page = preview.render_html(artifact)
    assert "Flight card" in markdown and "SFO–BKK" in markdown
    assert "Jan 15" in markdown and "65,000 Aeroplan points" in markdown
    assert "Flights: SFO–HKG" in markdown
    assert "Source updated" in markdown and "Price basis unconfirmed" in markdown
    assert "USD 440" in markdown and markdown.count("Flight card") == 1
    assert "The shorter journey" in markdown
    assert "<article aria-label='Flight card'>" in page
    assert "Aeroplan via Hong Kong" in page


def test_preview_cash_context_is_inline_even_without_cash_word_in_model_text() -> None:
    sentence = "For SFO to BKK, the source quotes USD 686; the quote scope is unknown."
    artifact = {"resolved": {"blocks": [
        {"kind": "cash_sentence", "text": sentence}]}}
    markdown = preview.render_markdown(artifact)
    page = preview.render_html(artifact)
    assert markdown == f"Cash comparison: {sentence}\n"
    assert f"<p>Cash comparison: {sentence}</p>" in page
    assert "<article" not in page
    assert markdown.count("USD 686") == 1


def test_journey_card_award_tax_state_is_source_resolved_in_markdown_and_html() -> None:
    def rendered(state: str, amount: int | None = None) -> tuple[str, str]:
        taxes = {"kind": "award_taxes", "scope": "per_traveler", "unit": "major",
                 "raw_amount": {"state": state, "value": amount},
                 "raw_currency": {"state": "value", "value": "USD"}}
        artifact = {"resolved": {"blocks": [{"kind": "journey_card",
            "label": "Flight option", "journey": {"origin": "SFO", "destination": "BKK",
                "money": {"award_taxes": taxes}}}]}}
        return preview.render_markdown(artifact), preview.render_html(artifact)

    unknown = rendered("unknown")
    absent = rendered("absent")
    zero = rendered("value", 0)
    for markdown, page in (unknown, absent, zero):
        assert "Flight card" in markdown and "<article aria-label='Flight card'>" in page
    assert "Award taxes: amount unconfirmed" in unknown[0]
    assert "Award taxes: amount unconfirmed" in unknown[1]
    assert "Award taxes: amount not provided" in absent[0]
    assert "Award taxes: amount not provided" in absent[1]
    assert "Taxes USD 0.00 quote per traveler" in zero[0]
    assert "Taxes USD 0.00 quote per traveler" in zero[1]
    assert "amount unconfirmed" not in zero[0]
    assert "amount not provided" not in zero[0]


def test_unformatted_known_award_tax_is_not_called_unreported() -> None:
    taxes = {"kind": "award_taxes", "scope": "unknown", "unit": "unknown",
             "raw_amount": {"state": "value", "value": 59},
             "raw_currency": {"state": "unknown", "value": None}}
    assert preview._award_tax_row(taxes) is None
    assert preview._award_tax_row(dict(taxes, kind="cash_fare",
                                       raw_amount={"state": "unknown", "value": None})) is None


def test_award_lead_tax_status_preserves_cash_role_and_benchmark_boundary() -> None:
    def rendered(kind: str, state: str, amount: int | None = None) -> tuple[str, str]:
        money = {"kind": kind, "scope": "party", "unit": "major",
                 "raw_amount": {"state": state, "value": amount},
                 "raw_currency": {"state": "value", "value": "USD"}}
        artifact = {"resolved": {"blocks": [{"kind": "lead_card",
            "label": "Flight to check", "lead_component": {"origin": "SFO",
                "destination": "BKK", "money": money}}]}}
        return preview.render_markdown(artifact), preview.render_html(artifact)

    unknown = rendered("award_taxes", "unknown")
    absent = rendered("award_taxes", "absent")
    zero = rendered("award_taxes", "value", 0)
    cash = rendered("cash_fare", "unknown")
    assert all("Award taxes: amount unconfirmed" in value for value in unknown)
    assert all("Award taxes: amount not provided" in value for value in absent)
    assert all("Taxes USD 0.00 quote for the party" in value for value in zero)
    assert all("Award taxes:" not in value for value in cash)
    benchmark = {"resolved": {"blocks": [{"kind": "cash_sentence",
        "text": "The cash fare is USD 686.",
        "benchmark_component": {"money": {"kind": "award_taxes",
            "raw_amount": {"state": "unknown", "value": None}}}}]}}
    assert "Award taxes:" not in preview.render_markdown(benchmark)
    assert "Award taxes:" not in preview.render_html(benchmark)


def test_blind_condition_sidecars_match_exact_saved_author_packets() -> None:
    for name, bundle in (("c11-scout-prior-admitted", "q031"),
                         ("c11-scout-prior-conditional", "q032"),
                         ("c11-scout-prior-incomplete", "q033"),
                         ("confirm-c11-prior-admitted", "q034"),
                         ("confirm-c11-prior-conditional", "q035"),
                         ("confirm-c11-prior-incomplete", "q036"),
                         ("confirm-c11-ranking-positioning", "q037"),
                         ("confirm-c11-ranking-mixed", "q038"),
                         ("confirm-c11-ranking-business", "q039")):
        request = ledger.read_json(run.RUNS / name
                                   / "pass-02/generation-request.json")
        expected = review_bundle.condition_sidecar(request)
        actual = ledger.read_json(review_bundle.HERE / "review-bundles" / bundle
                                  / "condition-applicability.json")
        assert actual == expected
        assert set(actual) == {"condition_applicability", "alias_members"}
    assert review_bundle.condition_sidecar({"input": '{"packet": {}}'}) is None


def test_campaign_cap_is_separate_from_stopped_campaign() -> None:
    settings = ledger.campaign()
    assert settings["maximum_iterations"] == 20
    assert settings["maximum_generation_calls"] == 600
    assert ledger.CAMPAIGN.parent.name == "2026-10-29-category-led"


def test_preview_does_not_present_opaque_component_as_flight() -> None:
    reported = {"origin": "SFO", "destination": "HKG", "reported": True,
                "departure": {"local_iso": "2027-01-01T08:00:00-08:00"},
                "arrival": {"local_iso": "2027-01-02T10:00:00+08:00"},
                "flight_number": {"state": "value", "value": "UA1"},
                "cabin": {"state": "absent", "value": None}}
    opaque = dict(reported, reported=False)
    assert len(preview._legs([reported])) == 1
    assert preview._legs([opaque]) == []


def test_lead_card_keeps_cash_fare_role_and_known_scope() -> None:
    lead = {"kind": "lead_card", "label": "Positioning flight to check",
            "lead": {"missing_information": ["no_complete_matched_journey"]},
            "lead_component": {"origin": "SFO", "destination": "LAX",
                "departure_date": "2027-01-01", "cabin": {"state": "absent"},
                "points": {"state": "absent"}, "program": {"state": "absent"},
                "seats": {"state": "absent"},
                "money": {"kind": "cash_fare", "unit": "major", "scope": "per_traveler",
                    "raw_amount": {"state": "value", "value": 59},
                    "raw_currency": {"state": "value", "value": "USD"}},
                "legs": [{"origin": "SFO", "destination": "LAX", "reported": False}]}}
    rows = preview._card(lead, {}, 1)
    assert "Cash fare USD 59.00 quote per traveler" in rows
    assert not any(row.startswith("Taxes ") for row in rows)
    assert not any(row.startswith("Reported flights:") for row in rows)


def test_cabin_enum_is_traveler_language() -> None:
    field = {"state": "value", "value": "premium_economy"}
    assert preview._cabin(field) == "premium economy"
    assert preview._cabin({"state": "absent", "value": None}) is None


def test_cash_component_endpoint_schedule_without_invented_leg() -> None:
    component = {"kind": "cash_itinerary", "origin": "SFO", "destination": "LAX",
                 "legs": [{"reported": False, "origin": "SFO", "destination": "LAX",
                           "departure": {"local_iso": "2027-01-08T08:55:00-08:00"},
                           "arrival": {"local_iso": "2027-01-08T10:31:00-08:00"},
                           "flight_number": {"state": "absent"}}]}
    sentence = preview._cash_component_schedule(component)
    assert sentence is not None
    assert "departs 8:55 AM, Jan 8, 2027 (SFO local)" in sentence
    assert "arrives 10:31 AM, Jan 8, 2027 (LAX local)" in sentence
    assert "Individual flight details unreported" in sentence
    assert "Flight" not in sentence.split(":", 1)[0]
    date_only = dict(component, departure_date="2027-01-08", legs=[{
        "reported": False, "origin": "SFO", "destination": "LAX",
        "departure": {"local_iso": None}, "arrival": {"local_iso": None}}])
    assert preview._cash_component_schedule(date_only) == (
        "Separately booked SFO–LAX component: 2027-01-08; exact flight times unavailable.")


def test_old_run_uses_its_archived_preview_source() -> None:
    path = run.RUNS / "c01-scout-prior-conditional"
    if not path.exists():
        return
    from award_agent.results.category import parse_category_artifact

    artifact = parse_category_artifact((path / "artifact.json").read_bytes())
    archived_markdown, archived_html = preview_loader.render_saved(path, artifact)
    assert archived_markdown == (path / "answer-preview.md").read_text()
    assert archived_html == (path / "answer-preview.html").read_text()
    assert "Separately booked SFO–LAX component:" not in archived_markdown
    assert "Separately booked SFO–LAX component:" in preview.render_markdown(artifact)


def test_archived_source_config_and_profile_bind_to_artifact(tmp_path: Path) -> None:
    case = "ranking-business"
    source_bytes = run.source_path(case).read_bytes()
    config_bytes = run.CONFIG.read_bytes()
    source = run.projection_for(case)
    config = ResultsConfig.model_validate_json(config_bytes)
    artifact = SimpleNamespace(evidence=SimpleNamespace(source=source), config=config,
        profile="category-c01", resolved=None, generation_outcome="api_error",
        validation_outcome="unavailable", delivery_outcome="not_delivered",
        selected_pass_index=None, selection_findings=())
    recorded = {"case": case, "candidate": "category-c01",
                "source_sha256": ledger.sha256(run.source_path(case))}
    summary = {"source_sha256": recorded["source_sha256"], "case": case,
               "candidate": "category-c01", "generation_outcome": "api_error",
               "validation_outcome": "unavailable", "delivery_outcome": "not_delivered",
               "selected_pass_index": None, "selection_failed_findings": []}
    check = lambda: verify._artifact_bindings_issues(
        artifact, summary, recorded, source_bytes, config_bytes, tmp_path)
    assert check() == []
    artifact.profile = "category-c02"
    assert "artifact profile differs from run settings" in check()
    artifact.profile = "category-c01"
    summary["delivery_outcome"] = "delivered"
    assert "summary delivery_outcome differs from artifact" in check()
    summary["delivery_outcome"] = "not_delivered"
    altered = source.model_copy(update={"receipt": source.receipt.model_copy(
        update={"source_digest": "0" * 64})})
    artifact.evidence.source = altered
    assert "artifact source differs from archived source" in check()


def test_pass_requests_bind_to_saved_api_files(tmp_path: Path) -> None:
    request = {"model": "gpt-6-luna", "input": "frozen source"}
    ledger.write_new(tmp_path / "pass-01" / "count-request.json", request)
    ledger.write_new(tmp_path / "pass-01" / "count-receipt.json", {"input_tokens": 10})
    ledger.write_new(tmp_path / "pass-01" / "generation-request.json", {
        **request, "max_output_tokens": 8192, "store": False,
        "truncation": "disabled", "stream": True, "service_tier": "fast"})
    ledger.write_new(tmp_path / "pass-01" / "writer-receipt.json", {"status": "completed"})
    receipt = SimpleNamespace(model_dump=lambda **_: {"input_tokens": 10})
    writer_receipt = SimpleNamespace(model_dump=lambda **_: {"status": "completed"})
    item = SimpleNamespace(request=request, writer_called=True, phase="selection",
                           input_token_receipt=receipt, writer_receipt=writer_receipt)
    settings = SimpleNamespace(service_tier="fast")
    artifact = SimpleNamespace(passes=(item,), config=SimpleNamespace(max_output_tokens=8192),
        selector_settings=settings, composer_settings=settings, correction_settings=settings)
    assert verify._pass_bindings_issues(artifact, tmp_path,
                                       {"count": 1, "generation": 1}) == []
    item.request = {"model": "gpt-6-luna", "input": "forged source"}
    assert any("request differs" in issue for issue in
               verify._pass_bindings_issues(artifact, tmp_path,
                                            {"count": 1, "generation": 1}))
