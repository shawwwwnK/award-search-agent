"""Public Results M2 behavior on a frozen Ranking export and deterministic writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast

import pytest

from award_agent.providers.contracts import RawField, content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import (
    DeclaredClaim,
    ResultsConfig,
    ResultsDocument,
    ResultsPart,
    ResultsSelection,
    ResultsWriterError,
    authoring_payload,
    prepare_results,
    replay_results,
    run_results,
)
from award_agent.results.core import check_document


@pytest.fixture(scope="module")
def projection() -> SolutionProjection:
    path = Path("evidence/ranking-stage/m2/solutions/exact_business.json")
    return SolutionProjection.model_validate(json.loads(path.read_text()))


@pytest.fixture(scope="module")
def config() -> ResultsConfig:
    return ResultsConfig(model="offline-test", max_output_tokens=10000, timeout_seconds=30,
                         context_limit_tokens=10_000_000, prompt_overhead_tokens=100)


class FakeWriter:
    def __init__(self, *documents: ResultsDocument | Exception) -> None:
        self.documents = documents
        self.calls: list[tuple[object, object]] = []

    def author(self, prepared: object, config: object, feedback: tuple = (),
               previous_document: ResultsDocument | None = None) -> ResultsDocument:
        self.calls.append((feedback, previous_document))
        result = self.documents[len(self.calls) - 1]
        if isinstance(result, Exception):
            raise result
        return result


def _journey(projection: SolutionProjection) -> str:
    return next(item.candidate_id for item in projection.view.alternatives
                if item.status in {"admitted", "conditional"})


def _document(journey: str, *, claim: DeclaredClaim | None = None,
              full: bool = True) -> ResultsDocument:
    disclosures = (
        "journey_id", "status", "styles", "route", "departure", "arrival", "elapsed",
        "award_program", "award_route", "award_departure", "award_arrival",
        "award_carrier", "award_cabin", "award_leg_cabins", "points",
        "fees", "award_price_scope", "price_completeness", "booking_obligation",
        "requirements", "award_observed_at", "transfer", "cash", "cash_cabin",
        "cash_leg_cabins", "cash_route", "cash_departure", "cash_arrival",
        "cash_price_scope", "cash_observed_at",
    ) if full else ()
    return ResultsDocument(selection=ResultsSelection(journey_ids=(journey,)), parts=(
        ResultsPart(scope="shared", markdown="# Options\n\nCoverage: {{fact:coverage}}. "
                    "Provider: {{fact:provider_status}}. "
                    "Benchmark: {{fact:benchmark_status}}.\n\n"),
        ResultsPart(scope="journey", reference_id=journey,
                    markdown="{{fact:route}} through {{fact:award_program}}.\n\n"
                             "Departure {{fact:departure}}.\n\n" +
                             (" ".join("{{fact:" + key + "}}" for key in disclosures)
                              if full else "") + ("\n\n" + claim.text if claim else ""),
                    claims=(claim,) if claim else (), disclosures=disclosures),
    ))


def test_preparation_retains_every_alternative_and_measures_complete_input(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    prepared = prepare_results(projection, config)
    alternatives = prepared.source["alternatives"]
    assert isinstance(alternatives, list)
    assert len(alternatives) == len(projection.view.alternatives)
    assert len(prepared.slots) >= len(projection.view.alternatives)
    assert prepared.estimated_total_tokens > prepared.input_bytes
    payload = json.loads(authoring_payload(prepared))
    assert len(payload["prepared"]["source"]["alternatives"]) == len(projection.view.alternatives)
    assert "slots" not in payload["prepared"]
    assert "slot_key_catalog" in payload["prepared"]["source"]


def test_valid_authored_document_delivers_and_replays_exactly(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    writer = FakeWriter(_document(journey))
    artifact = run_results(projection, config, writer)
    assert len(writer.calls) == 1
    assert artifact.delivery_outcome == "delivered"
    assert artifact.validation_outcome == "clean"
    assert "Departure" in artifact.rendered_markdown
    assert journey in artifact.rendered_markdown
    assert replay_results(artifact) == artifact.rendered_markdown
    assert artifact.inserted_facts


def test_failed_claim_is_corrected_with_all_failures_and_replayed(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    wrong = DeclaredClaim(claim_id="eligibility", kind="eligibility",
                          proposition="no_unresolved_requirements", scope_ids=(journey,),
                          text="No conditions apply")
    writer = FakeWriter(_document(journey, claim=wrong), _document(journey))
    artifact = run_results(projection, config, writer)
    assert len(writer.calls) == 2
    assert writer.calls[1][0]
    assert writer.calls[1][1] == writer.documents[0]
    assert artifact.selected_attempt == 1
    assert artifact.validation_outcome == "clean"
    assert replay_results(artifact) == artifact.rendered_markdown


def test_correction_api_failure_keeps_initial_annotated_content(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    wrong = DeclaredClaim(claim_id="eligibility", kind="eligibility",
                          proposition="no_unresolved_requirements", scope_ids=(journey,),
                          text="No conditions apply")
    writer = FakeWriter(_document(journey, claim=wrong),
                        ResultsWriterError("api_error", "transport unavailable"))
    artifact = run_results(projection, config, writer)
    assert artifact.selected_attempt == 0
    assert artifact.delivery_outcome == "delivered"
    assert artifact.validation_outcome == "annotated"
    assert artifact.attempts[1].failure_subtype == "api_error"
    assert "Validation:" in artifact.rendered_markdown
    assert replay_results(artifact) == artifact.rendered_markdown


def test_no_recoverable_draft_is_generation_failure(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    writer = FakeWriter(ResultsWriterError("refusal", "refused"))
    artifact = run_results(projection, config, writer)
    assert len(writer.calls) == 1
    assert artifact.delivery_outcome == "not_delivered"
    assert artifact.generation_outcome == "generation_error"
    assert artifact.attempts[0].failure_subtype == "refusal"


def test_context_limit_fails_before_writer_call(projection: SolutionProjection) -> None:
    config = ResultsConfig(model="offline-test", max_output_tokens=1, timeout_seconds=1,
                           context_limit_tokens=1, prompt_overhead_tokens=0)
    writer = FakeWriter()
    artifact = run_results(projection, config, writer)
    assert artifact.generation_outcome == "context_limit"
    assert writer.calls == []


def test_source_error_prevents_writer_call(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    bad_receipt = projection.receipt.model_copy(update={"view_digest": "0" * 64})
    bad = projection.model_copy(update={"receipt": bad_receipt})
    writer = FakeWriter()
    with pytest.raises(ValueError, match="receipt"):
        run_results(bad, config, writer)
    assert writer.calls == []


def test_unknown_claim_is_not_a_pass_or_material_failure_and_disclosure_still_applies(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    claim = DeclaredClaim(claim_id="all-legs", kind="cabin", proposition="all_legs_business",
                          scope_ids=(journey,), text="Every award leg is business")
    document = _document(journey, claim=claim, full=False)
    findings = check_document(document, projection)
    outcome = next(item.outcome for item in findings if item.claim_id == "all-legs")
    assert outcome in {"insufficient_evidence", "failed", "supported"}
    assert any(item.code.startswith("missing_disclosure:") for item in findings)
    writer = FakeWriter(document, document)
    artifact = run_results(projection, config, writer)
    assert artifact.delivery_outcome == "delivered"
    assert any(item.code.startswith("missing_disclosure:") for item in artifact.attempts[0].findings)


def test_interleaved_parts_keep_exact_scope_and_aggregate_disclosures(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    ids = [item.candidate_id for item in projection.view.alternatives
           if item.status in {"admitted", "conditional"}][:2]
    one = _document(ids[0]).parts[1]
    two = _document(ids[1]).parts[1]
    document = ResultsDocument(selection=ResultsSelection(journey_ids=tuple(ids)), parts=(
        _document(ids[0]).parts[0],
        one.model_copy(update={"markdown": "{{fact:journey_id}} {{fact:route}}\n\n"}),
        two,
        one.model_copy(update={"markdown": one.markdown.replace("{{fact:route}}", "")}),
    ))
    artifact = run_results(projection, config, FakeWriter(document))
    assert artifact.delivery_outcome == "delivered"
    assert artifact.validation_outcome == "clean"
    assert ids[0] in artifact.rendered_markdown
    assert ids[1] in artifact.rendered_markdown
    assert replay_results(artifact) == artifact.rendered_markdown


def test_unknown_and_malformed_slots_get_local_notices_preserving_prose(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    base = _document(journey)
    broken = base.parts[1].model_copy(update={"markdown": base.parts[1].markdown +
        " More context {{fact:missing_key}} and {{fact:BAD}} remains.\n\n"})
    document = base.model_copy(update={"parts": (base.parts[0], broken)})
    artifact = run_results(projection, config, FakeWriter(document, document))
    assert artifact.validation_outcome == "annotated"
    assert "More context Details unavailable and Details unavailable remains" in artifact.rendered_markdown
    assert artifact.rendered_markdown.count("Validation:") >= 2
    assert replay_results(artifact) == artifact.rendered_markdown


@pytest.mark.parametrize(("kind", "proposition", "expected"), [
    ("cabin", "journey_business", "supported"),
    ("cabin", "all_legs_business", "insufficient_evidence"),
    ("connection_protection", "protected_connection", "failed"),
    ("price_scope", "party_total", "insufficient_evidence"),
    ("comparison", "fastest", "failed"),
    ("comparison", "cheapest", "insufficient_evidence"),
    ("eligibility", "no_unresolved_requirements", "failed"),
    ("other", "personal_redeemability", "unchecked"),
])
def test_selected_claim_families_distinguish_four_outcomes(
    projection: SolutionProjection, kind: str, proposition: str, expected: str,
) -> None:
    journey = _journey(projection)
    claim = DeclaredClaim(claim_id="claim", kind=cast("Literal['cabin', 'connection_protection', 'price_scope', 'comparison', 'eligibility', 'other']", kind), proposition=proposition,
                          scope_ids=projection.view.comparison_pool_ids if kind == "comparison"
                          else (journey,), text="This option has a material assertion")
    finding = next(item for item in check_document(_document(journey, claim=claim), projection)
                   if item.claim_id == "claim")
    assert finding.outcome == expected


def test_fastest_supported_only_with_complete_supplied_pool(
    projection: SolutionProjection,
) -> None:
    journey = next(item.candidate_id for item in projection.view.alternatives
                   if item.elapsed_minutes == projection.view.time_reference_minutes
                   and item.status in {"admitted", "conditional"})
    claim = DeclaredClaim(claim_id="fastest", kind="comparison", proposition="fastest",
                          scope_ids=projection.view.comparison_pool_ids,
                          text="Fastest in the supplied comparison pool")
    findings = check_document(_document(journey, claim=claim), projection)
    assert next(item.outcome for item in findings if item.claim_id == "fastest") == "supported"


def test_hidden_disclosure_does_not_waive_visible_obligation(
    projection: SolutionProjection,
) -> None:
    journey = _journey(projection)
    base = _document(journey)
    edited = base.parts[1].model_copy(update={
        "markdown": base.parts[1].markdown.replace("{{fact:points}}", "") +
        "[invisible](https://example.test/{{fact:points}}) `{{fact:fees}}`"
    })
    doc = base.model_copy(update={"parts": (base.parts[0], edited)})
    findings = check_document(doc, projection)
    assert any(item.code == "missing_disclosure:points" for item in findings)


def test_worse_correction_keeps_initial_and_tie_prefers_correction(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    original = _document(journey, full=False)
    worse = ResultsDocument(selection=original.selection, parts=(
        original.parts[0],
        original.parts[1].model_copy(update={"markdown": "{{fact:bad_key}}"}),
    ))
    artifact = run_results(projection, config, FakeWriter(original, worse))
    assert artifact.selected_attempt == 0
    assert artifact.selection_reason == "initial_fewer_failures"
    tie = run_results(projection, config, FakeWriter(original, original))
    assert tie.selected_attempt == 1
    assert tie.selection_reason == "correction_tie"


def test_benchmark_and_incomplete_lead_require_visible_scoped_facts(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    benchmark = projection.view.direct_cash_observation_ids[0]
    incomplete = projection.view.award_summary_observation_ids[0]
    shared = ResultsPart(scope="shared", markdown="Coverage {{fact:coverage}}. "
                         "Provider {{fact:provider_status}}.\n\n")
    benchmark_part = ResultsPart(scope="benchmark", reference_id=benchmark,
        markdown="Cash reference {{fact:observation_id}} {{fact:disposition}} "
                 "{{fact:route}} {{fact:departure}} {{fact:arrival}} {{fact:observed_at}} "
                 "{{fact:provider_updated_at}} {{fact:cash}} {{fact:price_scope}} "
                 "{{fact:carrier}} {{fact:cabin}} {{fact:leg_cabins}}.\n\n")
    lead_part = ResultsPart(scope="incomplete", reference_id=incomplete,
        markdown="Research lead {{fact:observation_id}} {{fact:disposition}} {{fact:route}} "
                 "{{fact:departure}} {{fact:arrival}} {{fact:observed_at}} "
                 "{{fact:provider_updated_at}}.\n\n")
    document = ResultsDocument(selection=ResultsSelection(benchmark_observation_id=benchmark,
        incomplete_observation_ids=(incomplete,)), parts=(shared, benchmark_part, lead_part))
    artifact = run_results(projection, config, FakeWriter(document))
    assert artifact.validation_outcome == "clean"
    assert "direct cash benchmark only" in artifact.rendered_markdown
    assert "incomplete research lead" in artifact.rendered_markdown
    assert replay_results(artifact) == artifact.rendered_markdown
    missing = document.model_copy(update={"parts": (shared, benchmark_part.model_copy(
        update={"markdown": "Cash price {{fact:cash}}"}), lead_part)})
    findings = check_document(missing, projection)
    assert any(item.scope == "benchmark" and item.code == "missing_disclosure:price_scope"
               for item in findings)


def test_replay_rejects_tampered_source_or_receipt(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    artifact = run_results(projection, config, FakeWriter(_document(_journey(projection))))
    tampered = artifact.model_copy(update={"rendered_markdown": artifact.rendered_markdown + "x"})
    with pytest.raises(ValueError, match="replay exactly"):
        replay_results(tampered)
    tampered_notice = artifact.model_copy(update={"notices": ("fake",)})
    with pytest.raises(ValueError, match="notices"):
        replay_results(tampered_notice)


def test_invalid_shared_reference_cannot_resolve_shared_slot(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    base = _document(journey)
    bad = base.parts[0].model_copy(update={"reference_id": "invented"})
    document = base.model_copy(update={"parts": (bad, base.parts[1])})
    artifact = run_results(projection, config, FakeWriter(document, document))
    assert "Coverage: Details unavailable" in artifact.rendered_markdown
    assert not any(fact.part_index == 0 for fact in artifact.inserted_facts)
    failed_codes = {item.code for item in artifact.attempts[0].findings if item.outcome == "failed"}
    assert "missing_disclosure:coverage" in failed_codes
    assert "missing_disclosure:provider_status" in failed_codes
    assert "missing_disclosure:benchmark_status" in failed_codes


def test_invalid_benchmark_reference_never_supplies_award_facts_as_cash(
    projection: SolutionProjection,
) -> None:
    award_id = projection.view.alternatives[0].award_observation_id
    doc = ResultsDocument(selection=ResultsSelection(), parts=(
        ResultsPart(scope="shared", markdown="{{fact:coverage}} {{fact:provider_status}} "
                    "{{fact:benchmark_status}}"),
        ResultsPart(scope="benchmark", reference_id=award_id,
                    markdown="Cash {{fact:cash}} {{fact:disposition}}"),
    ))
    findings = check_document(doc, projection)
    assert any(item.code == "unavailable_reference" and item.reference_id == award_id
               for item in findings)
    assert not any(item.code.startswith("missing_disclosure:") and item.scope == "benchmark"
                   and item.reference_id == award_id for item in findings)


def test_claim_scope_must_match_exact_journey_or_full_comparison_pool(
    projection: SolutionProjection,
) -> None:
    journey = _journey(projection)
    other = next(item.candidate_id for item in projection.view.alternatives
                 if item.candidate_id != journey)
    claim = DeclaredClaim(claim_id="extra", kind="cabin", proposition="journey_business",
                          scope_ids=(journey, other), text="Business cabin")
    findings = check_document(_document(journey, claim=claim), projection)
    assert any(item.code == "claim_scope_mismatch" and item.outcome == "failed"
               for item in findings)
    comparison = DeclaredClaim(claim_id="duplicate", kind="comparison", proposition="fastest",
        scope_ids=projection.view.comparison_pool_ids + (journey,), text="Fastest option")
    findings = check_document(_document(journey, claim=comparison), projection)
    assert any(item.code == "claim_scope_mismatch" and item.outcome == "failed"
               for item in findings)


def test_resumed_shared_route_needs_exact_variant_identity(
    projection: SolutionProjection,
) -> None:
    ids = [item.candidate_id for item in projection.view.alternatives
           if item.status in {"admitted", "conditional"}][:2]
    first = _document(ids[0])
    second = _document(ids[1])
    resumed = ResultsPart(scope="journey", reference_id=ids[0], markdown="{{fact:route}} more details")
    document = ResultsDocument(selection=ResultsSelection(journey_ids=tuple(ids)), parts=(
        first.parts[0], first.parts[1], second.parts[1], resumed))
    assert any(item.code == "resumed_identity" for item in check_document(document, projection))


def test_replay_rejects_attempt_measurement_or_selection_reason_tamper(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    artifact = run_results(projection, config, FakeWriter(_document(_journey(projection))))
    wrong = artifact.attempts[0].model_copy(update={"prompt_digest": "0" * 64})
    with pytest.raises(ValueError, match="measurement"):
        replay_results(artifact.model_copy(update={"attempts": (wrong,)}))
    with pytest.raises(ValueError, match="selection reason"):
        replay_results(artifact.model_copy(update={"selection_reason": "wrong"}))


def test_notice_survives_open_fence_and_split_table_row(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    base = _document(journey)
    fence = base.parts[1].model_copy(update={"markdown": "```\n" + base.parts[1].markdown})
    fenced = base.model_copy(update={"parts": (base.parts[0], fence)})
    artifact = run_results(projection, config, FakeWriter(fenced, fenced))
    assert "Validation:" in artifact.rendered_markdown
    assert artifact.rendered_markdown.count("```") == 0
    assert replay_results(artifact) == artifact.rendered_markdown

    split = ResultsDocument(selection=ResultsSelection(journey_ids=(journey,)), parts=(
        base.parts[0],
        ResultsPart(scope="journey", reference_id=journey,
                    markdown="| {{fact:journey_id}} | {{fact:route}} |"),
        ResultsPart(scope="journey", reference_id=journey,
                    markdown=" {{fact:points}} |\n| Next | row | value |\n"),
    ))
    artifact = run_results(projection, config, FakeWriter(split, split))
    first_line = next(line for line in artifact.rendered_markdown.splitlines()
                      if line.startswith("| " + journey))
    assert "Validation:" in first_line
    assert "| Next | row | value |" in artifact.rendered_markdown


def test_distinct_visible_labels_bind_same_route_variants(
    projection: SolutionProjection,
) -> None:
    ids = [item.candidate_id for item in projection.view.alternatives
           if item.status in {"admitted", "conditional"}][:2]
    first = _document(ids[0])
    second = _document(ids[1])
    a = first.parts[1].model_copy(update={"identifier": "Option A",
        "markdown": "Option A\n" + first.parts[1].markdown.replace("{{fact:journey_id}}", "")})
    b = second.parts[1].model_copy(update={"identifier": "Option B",
        "markdown": "Option B\n" + second.parts[1].markdown.replace("{{fact:journey_id}}", "")})
    resumed = ResultsPart(scope="journey", reference_id=ids[0], identifier="Option A",
                          markdown="Option A has another tradeoff.\n")
    document = ResultsDocument(selection=ResultsSelection(journey_ids=tuple(ids)), parts=(
        first.parts[0], a, b, resumed))
    findings = check_document(document, projection)
    assert not any(item.code in {"resumed_identity", "identifier_reused", "identifier_changed",
                                 "missing_disclosure:journey_id"} for item in findings)
    duplicate = document.model_copy(update={"parts": (first.parts[0], a,
        b.model_copy(update={"identifier": "Option A", "markdown": b.markdown.replace("Option B", "Option A")}),
        resumed)})
    assert any(item.code == "identifier_reused" for item in check_document(duplicate, projection))


def test_incomplete_cash_observation_is_not_called_benchmark(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    cash_id = next(item.cash_observation_id for item in projection.view.alternatives
                   if item.cash_observation_id is not None)
    assert cash_id is not None
    view = projection.view.model_copy(update={
        "unpaired_positioning_observation_ids": (cash_id,),
    })
    synthetic = SolutionProjection(view=view, receipt=projection.receipt.model_copy(
        update={"view_digest": content_digest(view)}))
    prepared = prepare_results(synthetic, config)
    assert "incomplete research lead" in prepared.slots[f"incomplete:{cash_id}"]["disposition"]
    assert "benchmark" not in prepared.slots[f"incomplete:{cash_id}"]["disposition"]


def test_positive_mixed_cabin_evidence_and_zero_are_distinct(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    alternative = next(item for item in projection.view.alternatives if item.candidate_id == journey)
    components = tuple(item.model_copy(update={"mixed_cabin_pct": RawField(state="value", value=20)})
        if item.observation_id == alternative.award_observation_id else item
        for item in projection.view.components)
    view = projection.view.model_copy(update={"components": components})
    synthetic = SolutionProjection(view=view, receipt=projection.receipt.model_copy(
        update={"view_digest": content_digest(view)}))
    claim = DeclaredClaim(claim_id="all", kind="cabin", proposition="all_legs_business",
        scope_ids=(journey,), text="All journey legs are business")
    findings = check_document(_document(journey, claim=claim), synthetic)
    assert next(item.outcome for item in findings if item.claim_id == "all") == "failed"
    assert any(item.code == "missing_disclosure:award_mixed_cabin_pct" for item in findings)
    slots = prepare_results(synthetic, config).slots[f"journey:{journey}"]
    assert "20% of distance below reported award cabin" in slots["award_mixed_cabin_pct"]
    zero_components = tuple(item.model_copy(update={"mixed_cabin_pct": RawField(state="value", value=0)})
        if item.observation_id == alternative.award_observation_id else item
        for item in projection.view.components)
    zero_view = projection.view.model_copy(update={"components": zero_components})
    zero = SolutionProjection(view=zero_view, receipt=projection.receipt.model_copy(
        update={"view_digest": content_digest(zero_view)}))
    assert "0%" in prepare_results(zero, config).slots[f"journey:{journey}"]["award_mixed_cabin_pct"]


def test_omitted_source_fact_notice_is_escaped_once(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    draft = _document(journey, full=False)
    artifact = run_results(projection, config, FakeWriter(draft, draft))
    assert "separate\\_tickets\\_unverified" in artifact.rendered_markdown
    assert "separate\\\\_tickets" not in artifact.rendered_markdown


def test_correction_context_limit_is_recorded_as_noninvocation(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    draft = _document(_journey(projection), full=False)
    measured = run_results(projection, config, FakeWriter(draft, draft))
    first, second = measured.attempts
    assert second.estimated_total_tokens > first.estimated_total_tokens
    bounded = config.model_copy(update={"context_limit_tokens": first.estimated_total_tokens})
    writer = FakeWriter(draft)
    artifact = run_results(projection, bounded, writer)
    assert len(writer.calls) == 1
    assert artifact.attempts[1].writer_called is False
    assert artifact.attempts[1].error == "context_limit"
    assert replay_results(artifact) == artifact.rendered_markdown


def test_benchmark_claim_uses_exact_component_quote_scope(
    projection: SolutionProjection,
) -> None:
    benchmark = projection.view.direct_cash_observation_ids[0]
    component = next(item for item in projection.view.components if item.observation_id == benchmark)
    claim = DeclaredClaim(claim_id="cash-price", kind="price_scope", proposition="party_total",
                          scope_ids=(benchmark,), text="This cash quote covers the whole party")
    document = ResultsDocument(selection=ResultsSelection(benchmark_observation_id=benchmark),
        parts=(ResultsPart(scope="shared", markdown="{{fact:coverage}} {{fact:provider_status}}"),
               ResultsPart(scope="benchmark", reference_id=benchmark,
                           markdown="{{fact:observation_id}} This cash quote covers the whole party",
                           claims=(claim,))))
    finding = next(item for item in check_document(document, projection)
                   if item.claim_id == "cash-price")
    assert finding.outcome == ("supported" if component.price_scope == "party" else
                               "insufficient_evidence" if component.price_scope == "unknown"
                               else "failed")


def test_mixed_journey_all_leg_claim_needs_cash_leg_reports_even_with_business_cash_cabin(
    projection: SolutionProjection,
) -> None:
    journey = _journey(projection)
    alternative = next(item for item in projection.view.alternatives if item.candidate_id == journey)
    components = []
    for component in projection.view.components:
        if component.observation_id == alternative.award_observation_id:
            component = component.model_copy(update={"legs": tuple(leg.model_copy(
                update={"cabin": RawField(state="value", value="business")})
                for leg in component.legs)})
        elif component.observation_id == alternative.cash_observation_id:
            component = component.model_copy(update={"cabin": RawField(state="value", value="business"),
                                             "legs": ()})
        components.append(component)
    view = projection.view.model_copy(update={"components": tuple(components)})
    synthetic = SolutionProjection(view=view, receipt=projection.receipt.model_copy(
        update={"view_digest": content_digest(view)}))
    claim = DeclaredClaim(claim_id="all", kind="cabin", proposition="all_legs_business",
        scope_ids=(journey,), text="Every journey leg is business")
    finding = next(item for item in check_document(_document(journey, claim=claim), synthetic)
                   if item.claim_id == "all")
    assert finding.outcome == "insufficient_evidence"


def test_split_side_by_side_table_notices_stay_in_affected_cell(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    ids = [item.candidate_id for item in projection.view.alternatives
           if item.status in {"admitted", "conditional"}][:2]
    doc = ResultsDocument(selection=ResultsSelection(journey_ids=tuple(ids)), parts=(
        ResultsPart(scope="shared", markdown="Coverage {{fact:coverage}} "
                    "{{fact:provider_status}} {{fact:benchmark_status}}\n"),
        ResultsPart(scope="journey", reference_id=ids[0], markdown="| A {{fact:journey_id}} |"),
        ResultsPart(scope="journey", reference_id=ids[1], markdown=" B {{fact:journey_id}} |\n"),
    ))
    artifact = run_results(projection, config, FakeWriter(doc, doc))
    row = next(line for line in artifact.rendered_markdown.splitlines() if line.startswith("| A "))
    assert row.index("Validation:") < row.index(ids[1])
    assert row.count("Validation:") >= 2


def test_table_cell_notice_does_not_move_to_clean_neighbor(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    ids = [item.candidate_id for item in projection.view.alternatives
           if item.status in {"admitted", "conditional"}][:2]
    slots = prepare_results(projection, config).slots
    a_slots = " ".join("{{fact:" + key + "}}" for key in slots[f"journey:{ids[0]}"])
    b_slots = " ".join("{{fact:" + key + "}}" for key in slots[f"journey:{ids[1]}"])
    claim = DeclaredClaim(claim_id="condition", kind="eligibility",
        proposition="no_unresolved_requirements", scope_ids=(ids[0],),
        text="No unresolved requirements")
    document = ResultsDocument(selection=ResultsSelection(journey_ids=tuple(ids)), parts=(
        ResultsPart(scope="shared", markdown="{{fact:coverage}} {{fact:provider_status}} "
                    "{{fact:benchmark_status}}\n"),
        ResultsPart(scope="journey", reference_id=ids[0],
                    markdown="| A " + a_slots + " No unresolved requirements |",
                    claims=(claim,)),
        ResultsPart(scope="journey", reference_id=ids[1],
                    markdown=" B " + b_slots + " |\n"),
    ))
    artifact = run_results(projection, config, FakeWriter(document, document))
    row = next(line for line in artifact.rendered_markdown.splitlines() if line.startswith("| A "))
    assert row.count("Validation:") == 1
    assert row.index("Validation:") < row.index(ids[1])


def test_table_notice_uses_first_unescaped_closing_pipe_across_parts(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    ids = [item.candidate_id for item in projection.view.alternatives
           if item.status in {"admitted", "conditional"}][:2]
    award_id = next(item.award_observation_id for item in projection.view.alternatives
                    if item.candidate_id == ids[0])
    components = tuple(item.model_copy(update={"program": RawField(state="value",
        value="Program|with pipe")}) if item.observation_id == award_id else item
        for item in projection.view.components)
    view = projection.view.model_copy(update={"components": components})
    synthetic = SolutionProjection(view=view, receipt=projection.receipt.model_copy(
        update={"view_digest": content_digest(view)}))
    slots = prepare_results(synthetic, config).slots
    a_slots = " ".join("{{fact:" + key + "}}" for key in slots[f"journey:{ids[0]}"])
    b_slots = " ".join("{{fact:" + key + "}}" for key in slots[f"journey:{ids[1]}"])
    claim = DeclaredClaim(claim_id="condition", kind="eligibility",
        proposition="no_unresolved_requirements", scope_ids=(ids[0],),
        text="No unresolved requirements")
    document = ResultsDocument(selection=ResultsSelection(journey_ids=tuple(ids)), parts=(
        ResultsPart(scope="shared", markdown="{{fact:coverage}} {{fact:provider_status}} "
                    "{{fact:benchmark_status}}\n| A | B |\n| --- | --- |\n"),
        ResultsPart(scope="journey", reference_id=ids[0],
                    markdown="| A " + a_slots + " No unresolved requirements",
                    claims=(claim,)),
        ResultsPart(scope="journey", reference_id=ids[1], markdown=" | B " + b_slots + " |\n"),
    ))
    artifact = run_results(synthetic, config, FakeWriter(document, document))
    lines = artifact.rendered_markdown.splitlines()
    assert "| A | B |" in lines
    assert "| --- | --- |" in lines
    row = next(line for line in lines if line.startswith("| A ") and ids[0] in line)
    assert "Program\\|with pipe" in row
    assert row.index("Validation:") < row.index(ids[1])


def test_nested_fact_marker_is_unavailable_without_hidden_fact_insertion(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey = _journey(projection)
    base = _document(journey)
    altered = base.parts[1].model_copy(update={"markdown": base.parts[1].markdown +
        "Nested {{fact:{{fact:points}}}} marker.\n"})
    document = base.model_copy(update={"parts": (base.parts[0], altered)})
    artifact = run_results(projection, config, FakeWriter(document, document))
    assert "Nested Details unavailable marker." in artifact.rendered_markdown
    assert sum(fact.key == "points" for fact in artifact.inserted_facts) == 1
    assert any(item.code == "malformed_fact_slot" for item in artifact.attempts[0].findings)
