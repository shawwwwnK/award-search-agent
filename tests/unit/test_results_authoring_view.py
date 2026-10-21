"""Independent preservation checks for the compact writer input."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.authoring import (
    alias_document,
    build_authoring_view,
    compact_payload,
    rebind_document,
    verify_authoring_view,
)
from award_agent.results.contracts import (
    CheckFinding,
    DeclaredClaim,
    PreparedResultsInput,
    ResultsDocument,
    ResultsPart,
    ResultsSelection,
)

ROOT = Path("evidence/end-to-end/presentation/iterations/006")


def _record(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


def _rows(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    assert all(isinstance(item, dict) for item in value)
    return cast("list[dict[str, Any]]", value)


def _saved(case: str) -> tuple[SolutionProjection, dict[str, object]]:
    artifact = json.loads((ROOT / case / "artifact.json").read_text())
    return SolutionProjection.model_validate(artifact["projection"]), artifact["prepared"]["source"]


@pytest.mark.parametrize(("case", "eligible", "rejected"), [
    ("admitted", 258, 360),
    ("conditional", 232, 296),
    ("incomplete", 0, 0),
])
def test_compact_view_preserves_every_eligible_choice_and_accounts_for_exclusions(
    case: str, eligible: int, rejected: int,
) -> None:
    artifact = json.loads((ROOT / case / "artifact.json").read_text())
    projection = SolutionProjection.model_validate(artifact["projection"])
    compact = build_authoring_view(projection, artifact["prepared"]["source"])
    canonical = {a.candidate_id for a in projection.view.alternatives
                 if a.status in {"admitted", "conditional"}}
    assert len(canonical) == eligible
    assert set(compact.references.journeys.values()) == canonical
    assert len(compact.references.journeys) == eligible
    assert _record(compact.view["exclusions"])["rejected_count"] == rejected
    assert len(_rows(compact.view["journeys"])) <= eligible
    assert len(_rows(compact.view["journeys"])) < len(projection.view.alternatives) or not eligible


def test_matching_observations_share_facts_but_each_member_remains_selectable() -> None:
    projection, source = _saved("admitted")
    compact = build_authoring_view(projection, source)
    groups = _rows(compact.view["journeys"])
    assert len(groups) == 142  # independent investigation of frozen candidate facts
    assert sum(len(group["members"]) for group in groups) == 258
    paired = next(group for group in groups if len(group["members"]) == 2)
    first, second = paired["members"]
    assert first["ref"] != second["ref"]
    assert first["cash"] != second["cash"]
    assert first["cash_observed_at"] != second["cash_observed_at"]
    original = {item.candidate_id: item for item in projection.view.alternatives}
    for member in paired["members"]:
        candidate = original[compact.references.journeys[member["ref"]]]
        assert compact.references.cash[member["cash"]] == candidate.cash_observation_id


def test_writer_sees_short_references_and_wrong_kind_never_binds() -> None:
    projection, source = _saved("admitted")
    compact = build_authoring_view(projection, source)
    saved = json.loads((ROOT / "admitted" / "artifact.json").read_text())
    prepared = PreparedResultsInput.model_validate(saved["prepared"]).model_copy(
        update={"authoring_view": compact})
    verify_authoring_view(projection, prepared)
    payload = compact_payload(prepared)
    assert compact.binding_digest not in payload
    assert next(iter(compact.references.journeys.values())) not in payload
    assert '"source_digest"' not in payload
    journey = next(iter(compact.references.journeys))
    cash = next(iter(compact.references.cash))
    draft = ResultsDocument(selection=ResultsSelection(journey_ids=(journey, cash)), parts=(
        ResultsPart(scope="shared", markdown="Coverage {{fact:coverage}}"),
        ResultsPart(scope="journey", reference_id=journey, markdown="{{fact:route}}"),
    ))
    rebound = rebind_document(prepared, draft)
    assert rebound.selection.journey_ids[0] == compact.references.journeys[journey]
    assert rebound.selection.journey_ids[1] == "invalid-authoring-reference:journey"
    assert rebound.parts[1].reference_id == compact.references.journeys[journey]


def test_compact_view_tampering_is_detected() -> None:
    projection, source = _saved("conditional")
    compact = build_authoring_view(projection, source)
    saved = json.loads((ROOT / "conditional" / "artifact.json").read_text())
    prepared = PreparedResultsInput.model_validate(saved["prepared"]).model_copy(
        update={"authoring_view": compact})
    changed = compact.model_copy(update={"view": compact.view | {"journeys": []}})
    with pytest.raises(ValueError, match="trusted source"):
        verify_authoring_view(projection, prepared.model_copy(update={"authoring_view": changed}))
    restored = PreparedResultsInput.model_validate_json(prepared.model_dump_json())
    assert restored.authoring_view == compact
    verify_authoring_view(projection, restored)


def test_rejection_summary_distinguishes_failures_from_unknown_caveats() -> None:
    projection, source = _saved("admitted")
    exclusions = _record(build_authoring_view(projection, source).view["exclusions"])
    assert exclusions["rejected_count"] == 360
    failed = {row["code"]: row for row in exclusions["failed_reasons"]}
    assert failed["transfer_negative"]["count"] == 280
    assert "leaves before" in failed["transfer_negative"]["detail"]
    assert "price_incomplete" not in failed
    assert any(row["code"] == "price_incomplete" for row in exclusions["unresolved_caveats"])


def test_correction_keeps_full_pool_as_p1_without_canonical_hashes() -> None:
    projection, source = _saved("admitted")
    compact = build_authoring_view(projection, source)
    saved = json.loads((ROOT / "admitted" / "artifact.json").read_text())
    prepared = PreparedResultsInput.model_validate(saved["prepared"]).model_copy(
        update={"authoring_view": compact})
    journey = next(iter(compact.references.journeys))
    draft = ResultsDocument(selection=ResultsSelection(journey_ids=(journey,)), parts=(
        ResultsPart(scope="shared", markdown="Coverage {{fact:coverage}}"),
        ResultsPart(scope="journey", reference_id=journey, markdown="{{fact:route}}",
                    claims=(DeclaredClaim(claim_id="comparison", kind="comparison",
                                         proposition="fastest", scope_ids=("P1",),
                                         text="Fastest option."),)),
    ))
    bound = rebind_document(prepared, draft)
    assert bound.parts[1].claims[0].scope_ids == projection.view.comparison_pool_ids
    assert alias_document(prepared, bound) == draft
    feedback = (CheckFinding(code="claim:comparison", outcome="failed", scope="journey",
                             reference_id=compact.references.journeys[journey],
                             message="Unsupported comparison."),)
    correction = compact_payload(prepared, feedback, bound)
    assert '"scope_ids":["P1"]' in correction
    assert '"reference_id":"' + journey + '"' in correction
    assert next(iter(compact.references.journeys.values())) not in correction


@pytest.mark.parametrize(("kind", "scope_ids"), [
    ("cabin", ("P1",)),
    ("comparison", ("P1", "J1")),
])
def test_full_pool_handle_cannot_expand_in_other_claim_scopes(
    kind: Literal["cabin", "comparison"], scope_ids: tuple[str, ...],
) -> None:
    projection, source = _saved("admitted")
    compact = build_authoring_view(projection, source)
    saved = json.loads((ROOT / "admitted" / "artifact.json").read_text())
    prepared = PreparedResultsInput.model_validate(saved["prepared"]).model_copy(
        update={"authoring_view": compact})
    journey = next(iter(compact.references.journeys))
    draft = ResultsDocument(selection=ResultsSelection(journey_ids=(journey,)), parts=(
        ResultsPart(scope="journey", reference_id=journey, markdown="{{fact:route}}",
                    claims=(DeclaredClaim(claim_id="bad", kind=kind, proposition="fastest",
                                         scope_ids=scope_ids, text="Claim."),)),
    ))
    rebound = rebind_document(prepared, draft)
    assert rebound.parts[0].claims[0].scope_ids[0] == "invalid-authoring-reference:claim"


def test_same_schedule_with_different_carrier_or_price_is_not_grouped() -> None:
    projection, source = _saved("admitted")
    compact = build_authoring_view(projection, source)
    cash_ids = {item.observation_id for item in projection.view.components
                if item.kind == "cash_itinerary" and item.origin == "SFO" and
                item.destination == "LAX" and item.departure.local_iso ==
                "2027-01-15T07:00:00-08:00" and item.arrival.local_iso ==
                "2027-01-15T08:40:00-08:00"}
    assert len(cash_ids) == 4
    aliases = {alias for alias, canonical in compact.references.cash.items() if canonical in cash_ids}
    matching_groups = [group for group in _rows(compact.view["components"])
                       if any(member["ref"] in aliases for member in group["members"])]
    assert len(matching_groups) == 2
    assert {tuple(group["facts"]["carriers"]) for group in matching_groups} == {
        ("United",), ("American",)}
    assert {group["facts"]["cash_amount"]["value"] for group in matching_groups} == {135, 176}


def test_available_instant_survives_missing_local_timestamp() -> None:
    projection, source = _saved("admitted")
    original = projection.view.alternatives[0]
    changed_time = original.departure.model_copy(update={"local_iso": None})
    changed = original.model_copy(update={"departure": changed_time})
    view = projection.view.model_copy(update={"alternatives": (changed, *projection.view.alternatives[1:])})
    synthetic = projection.model_copy(update={"view": view})
    source_copy = deepcopy(source)
    _record(_rows(source_copy["alternatives"])[0]["departure"])["local_iso"] = None
    compact = build_authoring_view(synthetic, source_copy)
    member = next(group for group in _rows(compact.view["journeys"]) if
                  any(row["ref"] == "J1" for row in group["members"]))
    assert original.departure.instant is not None
    assert member["facts"]["departure"]["instant"] == original.departure.instant.isoformat().replace(
        "+00:00", "Z")


def test_incomplete_leads_and_benchmarks_retain_original_dispositions() -> None:
    projection, source = _saved("incomplete")
    compact = build_authoring_view(projection, source)
    expected_leads = (set(projection.view.award_summary_observation_ids) |
                      set(projection.view.unmatched_award_observation_ids) |
                      set(projection.view.unpaired_positioning_observation_ids))
    actual_leads = {compact.references.awards.get(row["ref"],
                    compact.references.cash.get(row["ref"]))
                    for row in _rows(compact.view["incomplete_leads"])}
    assert actual_leads == expected_leads
    assert {compact.references.cash[ref] for ref in cast("list[str]", compact.view["benchmarks"])} == set(
        projection.view.direct_cash_observation_ids)
    assert compact.view["journeys"] == []
    assert all("kind" in row for row in _rows(compact.view["incomplete_leads"]))


def test_factored_disclosure_profiles_reconstruct_canonical_requirements() -> None:
    projection, source = _saved("conditional")
    compact = build_authoring_view(projection, source)
    expected = _record(_record(source["presentation_required_keys"])["selected_journey_by_id"])
    for group in _rows(compact.view["journeys"]):
        keys = _record(compact.view["disclosure_profiles"])[group["facts"]["disclosure_profile"]]
        for member in group["members"]:
            assert keys == expected[compact.references.journeys[member["ref"]]]


def test_component_uncertainty_findings_remain_visible_without_source_ids() -> None:
    projection, source = _saved("admitted")
    compact = build_authoring_view(projection, source)
    facts = [group["facts"] for group in _rows(compact.view["components"])]
    findings = [finding for component in facts for finding in component["findings"]]
    zero = next(item for item in findings if item["code"] == "seats_zero_ambiguous")
    assert zero == {"code": "seats_zero_ambiguous", "severity": "unknown",
                    "message": "zero may mean seat count is unavailable", "field": "seats"}
    assert all("observation_id" not in item for item in findings)
