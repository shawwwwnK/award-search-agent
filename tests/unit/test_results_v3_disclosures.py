"""V3 shared journey disclosures and short rejected notes, with legacy replay guards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import (
    PreparedResultsInput,
    ResultsArtifact,
    ResultsConfig,
    ResultsDocument,
    ResultsPart,
    ResultsSelection,
    SharedDisclosureBinding,
    authoring_payload,
    check_document,
    prepare_results,
    render_results,
    replay_results,
    run_results,
)
from award_agent.results.request import response_schema, token_request


@pytest.fixture(scope="module")
def projection() -> SolutionProjection:
    return SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/sfo_to_bkk_positioning.json").read_text())


@pytest.fixture(scope="module")
def config() -> ResultsConfig:
    return ResultsConfig(model="offline-v3", max_output_tokens=10000, timeout_seconds=20,
                         context_limit_tokens=10_000_000, prompt_overhead_tokens=100)


class Writer:
    def __init__(self, document: ResultsDocument) -> None:
        self.document = document

    def author(self, prepared: PreparedResultsInput, config: ResultsConfig,
               feedback: tuple = (), previous_document: ResultsDocument | None = None,
               ) -> ResultsDocument:
        return self.document


def _ids(projection: SolutionProjection) -> tuple[str, str, str]:
    good = [alt.candidate_id for alt in projection.view.alternatives
            if alt.status in {"admitted", "conditional"}]
    rejected = next(alt.candidate_id for alt in projection.view.alternatives
                    if alt.status == "rejected")
    return good[0], good[1], rejected


def _document(projection: SolutionProjection, config: ResultsConfig, *,
              binding: SharedDisclosureBinding | None = None,
              shared_text: str | None = None,
              extra_bindings: tuple[SharedDisclosureBinding, ...] = (),
              omit_journey_key: str | None = None) -> ResultsDocument:
    first, second, _ = _ids(projection)
    prepared = prepare_results(projection, config)
    binding = binding or SharedDisclosureBinding(key="booking_obligation",
                                                  journey_ids=(first, second))
    shared_text = shared_text or ("Options A and B share booking terms: "
                                  "{{fact:booking_obligation}}. "
                                  "{{fact:coverage}} {{fact:provider_status}} "
                                  "{{fact:benchmark_status}}")
    parts = [ResultsPart(scope="shared", markdown=shared_text,
                         shared_disclosures=(binding, *extra_bindings))]
    for rid, label in ((first, "A"), (second, "B")):
        keys = set(prepared.slots[f"journey:{rid}"]) - {"booking_obligation"}
        if omit_journey_key:
            keys.discard(omit_journey_key)
        parts.append(ResultsPart(scope="journey", reference_id=rid, identifier=label,
            markdown=f"Option {label}. " + " ".join(f"{{{{fact:{key}}}}}" for key in sorted(keys))))
    return ResultsDocument(selection=ResultsSelection(journey_ids=(first, second)),
                           parts=tuple(parts))


def _failed(document: ResultsDocument, projection: SolutionProjection) -> set[str]:
    return {finding.code for finding in check_document(document, projection)
            if finding.outcome == "failed"}


def test_shared_equal_slot_credits_both_targets_and_maps_both_sources(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    first, second, _ = _ids(projection)
    document = _document(projection, config)
    assert not _failed(document, projection)
    rendered, facts = render_results(document, projection)
    booking = [fact for fact in facts if fact.key == "booking_obligation"]
    assert len(booking) == 2
    assert {(fact.part_index, fact.scope, fact.reference_id) for fact in booking} == {
        (0, "journey", first), (0, "journey", second)}
    assert booking[0].value in rendered
    artifact = run_results(projection, config, Writer(document))
    assert artifact.contract_version == "results-artifact-v3"
    assert artifact.prepared.contract_version == "results-prepared-v2"
    assert artifact.validation_outcome == "clean"
    assert replay_results(artifact) == artifact.rendered_markdown


@pytest.mark.parametrize(("binding", "text", "code"), [
    (lambda a, b, r: SharedDisclosureBinding(key="journey_id", journey_ids=(a, b)),
     "Options A and B: {{fact:journey_id}}.", "shared_binding_value"),
    (lambda a, b, r: SharedDisclosureBinding(key="booking_obligation", journey_ids=(a, a)),
     "Options A and B: {{fact:booking_obligation}}.", "shared_binding_targets"),
    (lambda a, b, r: SharedDisclosureBinding(key="booking_obligation", journey_ids=(a, r)),
     "Options A and B: {{fact:booking_obligation}}.", "shared_binding_targets"),
    (lambda a, b, r: SharedDisclosureBinding(key="booking_obligation", journey_ids=(a, "unknown")),
     "Options A and B: {{fact:booking_obligation}}.", "shared_binding_targets"),
    (lambda a, b, r: SharedDisclosureBinding(key="booking_obligation", journey_ids=(a, b)),
     "Only option A: {{fact:booking_obligation}}.", "shared_binding_identity"),
    (lambda a, b, r: SharedDisclosureBinding(key="booking_obligation", journey_ids=(a, b)),
     "Options A and B share terms.", "shared_binding_hidden"),
])
def test_invalid_shared_binding_never_credits_or_renders_first_target(
    projection: SolutionProjection, config: ResultsConfig,
    binding: object, text: str, code: str,
) -> None:
    first, second, rejected = _ids(projection)
    assert callable(binding)
    document = _document(projection, config, binding=binding(first, second, rejected),
                         shared_text=text)
    failed = _failed(document, projection)
    assert code in failed
    assert "missing_disclosure:booking_obligation" in failed or code == "shared_binding_value"
    rendered, facts = render_results(document, projection)
    assert not any(fact.part_index == 0 and fact.scope == "journey" for fact in facts)
    if "{{fact:" in text:
        assert "Details unavailable" in rendered


def test_duplicate_key_and_wrong_scope_do_not_credit(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    first, second, _ = _ids(projection)
    binding = SharedDisclosureBinding(key="booking_obligation", journey_ids=(first, second))
    duplicate = _document(projection, config, extra_bindings=(binding,))
    assert "shared_binding_key" in _failed(duplicate, projection)
    assert "missing_disclosure:booking_obligation" in _failed(duplicate, projection)
    original = _document(projection, config)
    parts = list(original.parts)
    parts[0] = parts[0].model_copy(update={"shared_disclosures": ()})
    parts[1] = parts[1].model_copy(update={"shared_disclosures": (binding,)})
    wrong_scope = original.model_copy(update={"parts": tuple(parts)})
    assert "shared_binding_scope" in _failed(wrong_scope, projection)
    assert "missing_disclosure:booking_obligation" in _failed(wrong_scope, projection)


def test_shared_binding_needs_friendly_ids_visible_in_their_own_parts(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    original = _document(projection, config)
    parts = list(original.parts)
    parts[1] = parts[1].model_copy(update={"markdown": parts[1].markdown.replace(
        "Option A.", "Award details.")})
    parts[2] = parts[2].model_copy(update={"markdown": parts[2].markdown.replace(
        "Option B.", "Business details.")})
    document = original.model_copy(update={"parts": tuple(parts)})
    assert "shared_binding_identity" in _failed(document, projection)
    assert "missing_disclosure:booking_obligation" in _failed(document, projection)
    _, facts = render_results(document, projection)
    assert not any(fact.part_index == 0 and fact.scope == "journey" for fact in facts)


def test_shared_binding_allows_unlabeled_contiguous_journey_continuation(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    original = _document(projection, config)
    first = original.parts[1]
    continuation = ResultsPart(scope="journey", reference_id=first.reference_id,
                               markdown=" Additional explanation for this same option. ")
    document = original.model_copy(update={"parts": (
        original.parts[0], first, continuation, original.parts[2])})
    assert not _failed(document, projection)
    _, facts = render_results(document, projection)
    assert len([fact for fact in facts if fact.part_index == 0 and
                fact.key == "booking_obligation"]) == 2


def test_selected_friendly_identity_survives_identical_text_split_without_raw_id(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    original = _document(projection, config, omit_journey_key="journey_id")
    assert not _failed(original, projection)
    first = original.parts[1]
    anchor = "Option A. "
    assert first.markdown.startswith(anchor)
    split = first.model_copy(update={"markdown": anchor})
    continuation = ResultsPart(scope="journey", reference_id=first.reference_id,
                               markdown=first.markdown[len(anchor):])
    changed = original.model_copy(update={"parts": (
        original.parts[0], split, continuation, original.parts[2])})
    assert not _failed(changed, projection)
    assert render_results(changed, projection)[0] == render_results(original, projection)[0]

    conflict = continuation.model_copy(update={"identifier": "Option X",
        "markdown": "Option X. " + continuation.markdown})
    conflicted = original.model_copy(update={"parts": (
        original.parts[0], split, conflict, original.parts[2])})
    assert "identifier_changed" in _failed(conflicted, projection)
    assert "missing_disclosure:journey_id" in _failed(conflicted, projection)


def test_shared_binding_rejects_changed_or_reused_friendly_ids(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    original = _document(projection, config)
    first = original.parts[1]
    changed_part = ResultsPart(scope="journey", reference_id=first.reference_id,
                               identifier="Option X", markdown="Option X continues.")
    changed = original.model_copy(update={"parts": (
        original.parts[0], first, changed_part, original.parts[2])})
    assert "identifier_changed" in _failed(changed, projection)
    assert "shared_binding_identity" in _failed(changed, projection)
    reused_second = original.parts[2].model_copy(update={
        "identifier": "A", "markdown": original.parts[2].markdown.replace("Option B.", "Option A.")})
    reused = original.model_copy(update={"parts": (
        original.parts[0], first, reused_second)})
    assert "identifier_reused" in _failed(reused, projection)
    assert "shared_binding_identity" in _failed(reused, projection)


def test_repeated_valid_shared_occurrences_remain_source_bound(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    original = _document(projection, config)
    shared = original.parts[0]
    repeated = shared.model_copy(update={"markdown": shared.markdown +
        " Options A and B still share {{fact:booking_obligation}}."})
    document = original.model_copy(update={"parts": (repeated, shared, *original.parts[1:])})
    assert not _failed(document, projection)
    _, facts = render_results(document, projection)
    assert len([fact for fact in facts if fact.key == "booking_obligation"]) == 6


def test_recommended_journey_still_needs_its_other_scoped_facts(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    document = _document(projection, config, omit_journey_key="award_program")
    assert "missing_disclosure:award_program" in _failed(document, projection)


def test_rejected_short_note_requires_manifest_identity_status_and_reason(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    _, _, rejected = _ids(projection)
    shared = ResultsPart(scope="shared", markdown="{{fact:coverage}} "
        "{{fact:provider_status}} {{fact:benchmark_status}}")
    note = ResultsPart(scope="journey", reference_id=rejected,
        markdown="Excluded {{fact:journey_id}}: {{fact:status}}; {{fact:requirements}}.")
    document = ResultsDocument(selection=ResultsSelection(excluded_journey_ids=(rejected,)),
                               parts=(shared, note))
    failed = _failed(document, projection)
    assert not any(code.startswith("missing_disclosure:") and code not in {
        "missing_disclosure:no_complete_journeys"} for code in failed)
    assert "rejected_identity" not in failed
    for key in ("journey_id", "status", "requirements"):
        changed = note.model_copy(update={"markdown": note.markdown.replace(
            f"{{{{fact:{key}}}}}", "omitted")})
        variant = document.model_copy(update={"parts": (shared, changed)})
        expected = ("rejected_identity" if key == "journey_id" else
                    f"missing_disclosure:{key}")
        assert expected in _failed(variant, projection)
    selected = document.model_copy(update={"selection": ResultsSelection(journey_ids=(rejected,))})
    assert "invalid_selection" in _failed(selected, projection)
    assert "missing_disclosure:award_program" in _failed(selected, projection)


def test_rejected_short_note_accepts_stable_visible_friendly_id(
    projection: SolutionProjection,
) -> None:
    _, _, rejected = _ids(projection)
    shared = ResultsPart(scope="shared", markdown="{{fact:coverage}} "
        "{{fact:provider_status}} {{fact:benchmark_status}}")
    note = ResultsPart(scope="journey", reference_id=rejected, identifier="Option R",
        markdown="Option R is {{fact:status}}: {{fact:requirements}}.")
    document = ResultsDocument(selection=ResultsSelection(excluded_journey_ids=(rejected,)),
                               parts=(shared, note))
    assert not _failed(document, projection)
    resumed = note.model_copy(update={"identifier": "Option Q",
        "markdown": "Option Q remains {{fact:status}}: {{fact:requirements}}."})
    changed = document.model_copy(update={"parts": (shared, note, resumed)})
    assert "identifier_changed" in _failed(changed, projection)
    assert "rejected_identity" in _failed(changed, projection)

    literal = note.model_copy(update={"identifier": None,
        "markdown": f"Excluded {rejected}: "
        "{{fact:status}}; {{fact:requirements}}."})
    literal_doc = document.model_copy(update={"parts": (shared, literal)})
    assert not _failed(literal_doc, projection)


@pytest.mark.parametrize("status", ["admitted", "conditional"])
def test_unselected_eligible_note_keeps_upstream_status_without_full_disclosures(
    projection: SolutionProjection, status: str,
) -> None:
    candidate = next(alt.candidate_id for alt in projection.view.alternatives
                     if alt.status == status)
    shared = ResultsPart(scope="shared", markdown="{{fact:coverage}} "
        "{{fact:provider_status}} {{fact:benchmark_status}}")
    note = ResultsPart(scope="journey", reference_id=candidate,
        markdown="Additional option {{fact:journey_id}} has status {{fact:status}}; "
                 "requirements: {{fact:requirements}}.")
    document = ResultsDocument(selection=ResultsSelection(excluded_journey_ids=(candidate,)),
                               parts=(shared, note))
    assert not _failed(document, projection)
    rendered, _ = render_results(document, projection)
    assert f"status {status}" in rendered
    assert "rejected" not in rendered.split("status ", 1)[1].split(";", 1)[0]
    selected = document.model_copy(update={"selection": ResultsSelection(
        journey_ids=(candidate,))})
    assert "missing_disclosure:award_program" in _failed(selected, projection)


@pytest.mark.parametrize("status", ["admitted", "rejected"])
def test_unselected_friendly_note_survives_contiguous_split_without_raw_id(
    projection: SolutionProjection, status: str,
) -> None:
    candidate = next(alt.candidate_id for alt in projection.view.alternatives
                     if alt.status == status)
    shared = ResultsPart(scope="shared", markdown="{{fact:coverage}} "
        "{{fact:provider_status}} {{fact:benchmark_status}}")
    note = ResultsPart(scope="journey", reference_id=candidate, identifier="Option C",
        markdown="Option C is {{fact:status}}: {{fact:requirements}}.")
    original = ResultsDocument(selection=ResultsSelection(excluded_journey_ids=(candidate,)),
                               parts=(shared, note))
    assert not _failed(original, projection)
    split = note.model_copy(update={"markdown": "Option C "})
    continuation = ResultsPart(scope="journey", reference_id=candidate,
                               markdown=note.markdown[len("Option C "):])
    changed = original.model_copy(update={"parts": (shared, split, continuation)})
    assert not _failed(changed, projection)
    assert render_results(changed, projection)[0] == render_results(original, projection)[0]


def test_versioned_schema_payload_and_legacy_binding_rejection(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    document = _document(projection, config)
    v3 = prepare_results(projection, config)
    v2 = prepare_results(projection, config, version="results-artifact-v2")
    assert "shared_disclosures" in json.dumps(response_schema(v3.contract_version))
    assert "shared_disclosures" not in json.dumps(response_schema(v2.contract_version))
    assert "shared_disclosures" in json.dumps(token_request(v3, config, authoring_payload(v3)))
    assert "shared_disclosures" in authoring_payload(v3, previous_document=document)
    with pytest.raises(ValueError, match="legacy correction"):
        authoring_payload(v2, previous_document=document)
    with pytest.raises(ValueError, match="legacy artifact"):
        check_document(document, projection, version="results-artifact-v2")
    with pytest.raises(ValueError, match="legacy artifact"):
        render_results(document, projection, render_version="results-artifact-v2")

    old = ResultsArtifact.model_validate_json(Path(
        "evidence/results-stage/m2/sfo_to_bkk_positioning.annotated.artifact.json").read_text())
    assert old.contract_version == "results-artifact-v1"
    replay_results(old)
