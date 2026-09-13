"""Focused offline tests for endpoint-market search-plan compilation."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from award_agent.domain import (
    CabinClass,
    DateWindow,
    DateWindowPrecision,
    EffectiveField,
    EffectiveRequest,
    FieldProvenance,
    InitialSnapshotSource,
    LocationKind,
    LocationRef,
    RequestContext,
    SearchMode,
    UnknownField,
    UnknownReason,
)
from award_agent.search_planning import (
    BudgetKind,
    CachedSearchCapability,
    FilterObligation,
    FilterObligationKind,
    KnowledgeSnapshot,
    PlanningInputEnvelope,
    PlanningIssueCategory,
    PlanningIssueCode,
    PlanningPolicy,
    PlanningSource,
    SearchPlanningIssue,
    SearchPlanningIssueCode,
    SearchPlanningOutcome,
    SearchPlanningResult,
    capability_receipt_matches,
    default_capability_path,
    effective_request_digest,
    load_cached_search_capability,
    load_default_cached_search_capability,
    load_default_knowledge_snapshot,
    plan_searches,
    plan_searches_with_default_capability,
)

_CONTEXT = RequestContext(reference_date=date(2026, 9, 12), timezone="America/Los_Angeles")


def _location(kind: LocationKind, value: str) -> LocationRef:
    return LocationRef(kind=kind, value=value, raw_text=value)


def _request(**changes: Any) -> EffectiveRequest:
    baseline = EffectiveRequest(
        raw_text="Two business award seats from SFO to Japan October 5 through 7.",
        context=_CONTEXT,
        travelers=2,
        origins=(_location(LocationKind.AIRPORT, "SFO"),),
        destinations=(_location(LocationKind.COUNTRY, "Japan"),),
        departure_window=DateWindow(
            start=date(2026, 10, 5),
            end=date(2026, 10, 7),
            precision=DateWindowPrecision.WINDOW,
            raw_text="October 5 through 7",
        ),
        cabins=(CabinClass.BUSINESS,),
        search_modes=(SearchMode.AWARD,),
        field_provenance=(
            FieldProvenance(
                field=EffectiveField.CABIN,
                source=InitialSnapshotSource(field=EffectiveField.CABIN),
            ),
        ),
    )
    return baseline.model_copy(update=changes)


def _envelope(
    request: EffectiveRequest, *, expected_digest: str | None = None
) -> PlanningInputEnvelope:
    return PlanningInputEnvelope(
        source=PlanningSource(
            session_id="session-123",
            revision=4,
            expected_effective_request_digest=expected_digest,
        ),
        effective_request=request,
    )


def _plan(
    request: EffectiveRequest, *, policy: PlanningPolicy | None = None
) -> SearchPlanningResult:
    return plan_searches(
        _envelope(request),
        policy=policy or PlanningPolicy(),
        snapshot=load_default_knowledge_snapshot(),
        capability=load_default_cached_search_capability(),
    )


def test_endpoint_plan_is_atomic_reusable_and_has_no_provider_payload_contract() -> None:
    request = _request(
        hard_constraints=("Avoid overnight layovers",),
        search_modes=(SearchMode.AWARD, SearchMode.CASH),
        repositioning_allowed=False,
        unknowns=(
            UnknownField(
                field="cabin_preference_detail",
                reason=UnknownReason.MISSING,
                detail="No seat-style preference supplied",
            ),
        ),
        field_provenance=(
            FieldProvenance(
                field=EffectiveField.CABIN,
                source=InitialSnapshotSource(field=EffectiveField.CABIN),
            ),
            FieldProvenance(
                field=EffectiveField.HARD_CONSTRAINTS,
                source=InitialSnapshotSource(field=EffectiveField.HARD_CONSTRAINTS),
            ),
        ),
    )

    result = _plan(request)

    assert result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert result.plan is not None
    plan = result.plan
    assert [
        (probe.origin_endpoint.airport_iata, probe.destination_endpoint.airport_iata)
        for probe in plan.endpoint_probes
    ] == [
        ("SFO", "HND"),
        ("SFO", "NRT"),
        ("SFO", "KIX"),
    ]
    assert len(plan.award_search_items) == len(plan.endpoint_probes) == 3
    assert all(item.automated_mode == "award" for item in plan.award_search_items)
    assert all(item.date_envelope.inclusive for item in plan.award_search_items)
    assert {item.date_envelope.timezone for item in plan.award_search_items} == {
        "America/Los_Angeles"
    }
    assert all(item.date_envelope.start == date(2026, 10, 5) for item in plan.award_search_items)
    assert all(item.date_envelope.end == date(2026, 10, 7) for item in plan.award_search_items)
    assert all(
        item.result_validation_obligations[0].minimum_seats == 2 for item in plan.award_search_items
    )
    assert all(
        item.filter_obligations[0].kind is FilterObligationKind.CABIN_AVAILABLE_IN
        and item.filter_obligations[0].values == ("business",)
        for item in plan.award_search_items
    )
    assert plan.deferred_constraints[0].text == "Avoid overnight layovers"
    assert plan.deferred_constraints[0].field_provenance is not None
    assert plan.deferred_constraints[0].evidence_status == "not_verified"
    assert {issue.code for issue in plan.nonblocking_issues} == {
        SearchPlanningIssueCode.NONBLOCKING_UNKNOWN,
        SearchPlanningIssueCode.REPOSITIONING_POLICY_NOT_CONSUMED,
    }
    serialized = plan.model_dump(mode="json")
    assert "origin_airport" not in serialized
    assert "destination_airport" not in serialized
    assert "seat_count" not in serialized


def test_unspecified_cabin_is_not_a_blocker_or_filter() -> None:
    result = _plan(_request(cabins=()))

    assert result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert result.plan is not None
    assert all(not item.filter_obligations for item in result.plan.award_search_items)


def test_malformed_user_filter_provenance_is_a_typed_planning_failure() -> None:
    result = _plan(_request(field_provenance=()))

    assert result.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert [issue.code for issue in result.issues] == [
        SearchPlanningIssueCode.INVALID_FILTER_OBLIGATION
    ]


def test_duplicate_location_alternatives_deduplicate_complete_endpoint_market_items() -> None:
    result = _plan(
        _request(
            origins=(
                _location(LocationKind.AIRPORT, "SFO"),
                _location(LocationKind.AIRPORT, "SFO"),
            )
        )
    )

    assert result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert result.plan is not None
    assert len(result.plan.endpoint_probes) == len(result.plan.award_search_items) == 3


def test_digest_is_computed_and_mismatch_is_typed_unplannable() -> None:
    request = _request()
    matching = _envelope(request, expected_digest=effective_request_digest(request))
    matching_result = plan_searches(
        matching,
        policy=PlanningPolicy(),
        snapshot=load_default_knowledge_snapshot(),
        capability=load_default_cached_search_capability(),
    )
    mismatched_result = plan_searches(
        _envelope(request, expected_digest="wrong"),
        policy=PlanningPolicy(),
        snapshot=load_default_knowledge_snapshot(),
        capability=load_default_cached_search_capability(),
    )

    assert matching_result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert matching_result.plan is not None
    assert matching_result.plan.identity.effective_request_digest == effective_request_digest(
        request
    )
    assert mismatched_result.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert [issue.code for issue in mismatched_result.issues] == [
        SearchPlanningIssueCode.REQUEST_DIGEST_MISMATCH
    ]


def test_endpoint_item_cannot_change_destination_from_its_linked_probe() -> None:
    planned = _plan(_request())
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    document["award_search_items"][0]["destination_airport_fact_id"] = "airport:nrt"

    with pytest.raises(ValidationError, match="linked probe endpoints"):
        SearchPlanningResult.model_validate(
            {
                "outcome": planned.outcome,
                "plan": document,
                "exclusions": planned.exclusions,
            }
        )


def test_product_admission_remains_stricter_than_cached_search_inputs() -> None:
    result = _plan(_request(travelers=None, search_modes=(SearchMode.CASH,)))

    assert result.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert {issue.code for issue in result.issues} == {
        SearchPlanningIssueCode.MISSING_TRAVELERS,
        SearchPlanningIssueCode.AWARD_MODE_REQUIRED,
    }


def test_input_window_overflow_returns_structured_observed_limit_receipt() -> None:
    request = _request(
        departure_window=DateWindow(
            start=date(2026, 10, 5),
            end=date(2026, 11, 5),
            precision=DateWindowPrecision.WINDOW,
            raw_text="October 5 through November 5",
        )
    )

    result = _plan(request)

    assert result.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert [issue.code for issue in result.issues] == [
        SearchPlanningIssueCode.INPUT_WINDOW_EXCEEDS_BUDGET
    ]
    assert [
        (receipt.kind, receipt.observed, receipt.limit, receipt.disposition)
        for receipt in result.budget_receipts
    ] == [(BudgetKind.INPUT_WINDOW_DAYS, 32, 31, "exceeded")]


def test_required_endpoint_pair_budget_never_silently_prunes_coverage() -> None:
    result = _plan(_request(), policy=PlanningPolicy(max_endpoint_pairs=2))

    assert result.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert [issue.code for issue in result.issues] == [
        SearchPlanningIssueCode.ENDPOINT_PAIR_BUDGET_EXCEEDED
    ]


def test_unresolved_location_is_unplannable_without_a_guessed_airport() -> None:
    result = _plan(_request(destinations=(_location(LocationKind.CITY, "Atlantis"),)))

    assert result.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert result.plan is None
    assert result.issues[0].code.value == "unresolved_location"


def test_mixed_unresolved_and_missing_airport_issues_prioritize_evidence_failure() -> None:
    result = _plan(
        _request(
            origins=(
                _location(LocationKind.CITY, "Atlantis"),
                _location(LocationKind.AIRPORT, "ZZZ"),
            )
        )
    )

    assert result.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE
    assert result.plan is None
    assert {issue.code for issue in result.issues} == {
        # Both issues are retained; evidence failure is only the outcome priority.
        PlanningIssueCode.UNRESOLVED_LOCATION,
        # An unknown explicit IATA is reported as missing airport evidence.
        PlanningIssueCode.MISSING_AIRPORT_EVIDENCE,
    }


def test_mixed_unresolved_and_stale_airport_issues_prioritize_evidence_failure() -> None:
    document = load_default_knowledge_snapshot().model_dump(mode="python", round_trip=True)
    document["sources"] = [
        *document["sources"],
        {
            "source_id": "stale-zzz-source",
            "title": "Synthetic stale ZZZ source",
            "url": "https://example.test/stale-zzz",
            "license_note": "Synthetic test fixture only.",
            "verified_on": date(2020, 1, 1),
            "version_or_capture_id": "synthetic-stale-v1",
            "verification_scope": "Synthetic stale-airport test fixture.",
        },
    ]
    document["airports"] = [
        *document["airports"],
        {
            "airport_id": "airport:zzz",
            "iata": "ZZZ",
            "label": "Synthetic Stale Airport",
            "country_entity_id": "country:us",
            "timezone": "America/Los_Angeles",
            "aliases": ["ZZZ"],
            "source_ids": ["stale-zzz-source"],
        },
    ]
    snapshot = KnowledgeSnapshot.model_validate(document)
    result = plan_searches(
        _envelope(
            _request(
                origins=(
                    _location(LocationKind.CITY, "Atlantis"),
                    _location(LocationKind.AIRPORT, "ZZZ"),
                )
            )
        ),
        policy=PlanningPolicy(),
        snapshot=snapshot,
        capability=load_default_cached_search_capability(),
    )

    assert result.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE
    assert {issue.code for issue in result.issues} == {
        PlanningIssueCode.STALE_KNOWLEDGE,
        PlanningIssueCode.UNRESOLVED_LOCATION,
    }


@pytest.mark.parametrize(
    ("effective_request", "policy"),
    [
        (_request(origins=(_location(LocationKind.COUNTRY, "USA"),)), PlanningPolicy()),
        (_request(), PlanningPolicy(max_automatic_group_airports=2)),
    ],
)
def test_missing_required_selection_configuration_is_an_evidence_failure(
    effective_request: EffectiveRequest, policy: PlanningPolicy
) -> None:
    result = _plan(effective_request, policy=policy)

    assert result.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE
    assert result.plan is None


def test_outcome_variants_are_strictly_shaped() -> None:
    with pytest.raises(ValidationError):
        SearchPlanningResult(outcome=SearchPlanningOutcome.PLANNED)
    with pytest.raises(ValidationError):
        SearchPlanningResult(
            outcome=SearchPlanningOutcome.REDUCED_COVERAGE,
            plan=None,
            exclusions=("missing topology",),
        )


def test_failure_outcomes_accept_only_their_issue_categories() -> None:
    with pytest.raises(ValidationError, match="at least one evidence issue"):
        SearchPlanningResult(
            outcome=SearchPlanningOutcome.EVIDENCE_FAILURE,
            issues=(
                SearchPlanningIssue(
                    code=SearchPlanningIssueCode.MISSING_ORIGIN,
                    message="origin missing",
                ),
            ),
        )
    mixed_evidence_failure = SearchPlanningResult(
        outcome=SearchPlanningOutcome.EVIDENCE_FAILURE,
        issues=(
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.CAPABILITY_EVIDENCE_FAILURE,
                message="capability unavailable",
            ),
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.MISSING_ORIGIN,
                message="origin unresolved",
            ),
            SearchPlanningIssue(
                code=SearchPlanningIssueCode.ENDPOINT_PAIR_BUDGET_EXCEEDED,
                message="coverage budget exceeded",
            ),
        ),
    )
    assert {issue.category for issue in mixed_evidence_failure.issues} == {
        PlanningIssueCategory.EVIDENCE,
        PlanningIssueCategory.INPUT,
        PlanningIssueCategory.COVERAGE,
    }
    with pytest.raises(ValidationError, match="unplannable outcomes"):
        SearchPlanningResult(
            outcome=SearchPlanningOutcome.UNPLANNABLE,
            issues=(
                SearchPlanningIssue(
                    code=SearchPlanningIssueCode.CAPABILITY_EVIDENCE_FAILURE,
                    message="capability unavailable",
                ),
            ),
        )
    with pytest.raises(ValidationError, match="evidence-failure outcomes"):
        SearchPlanningResult(
            outcome=SearchPlanningOutcome.EVIDENCE_FAILURE,
            issues=(
                SearchPlanningIssue(
                    code=SearchPlanningIssueCode.ENDPOINT_PAIR_BUDGET_EXCEEDED,
                    message="coverage budget exceeded",
                ),
            ),
        )
    assert (
        SearchPlanningIssue(
            code=SearchPlanningIssueCode.MISSING_ORIGIN,
            message="origin missing",
        ).category
        is PlanningIssueCategory.INPUT
    )
    with pytest.raises(ValidationError):
        SearchPlanningResult(
            outcome=SearchPlanningOutcome.UNPLANNABLE,
            plan=_plan(_request()).plan,
            issues=(
                SearchPlanningIssue(
                    code=SearchPlanningIssueCode.MISSING_ORIGIN,
                    message="origin missing",
                ),
            ),
        )


def test_filter_operands_and_origins_are_kind_specific() -> None:
    with pytest.raises(ValidationError):
        FilterObligation(
            kind=FilterObligationKind.DIRECT_FLIGHT_AVAILABLE,
            values=("false",),
            origin="planner_structure",
        )
    with pytest.raises(ValidationError):
        FilterObligation(
            kind=FilterObligationKind.CABIN_AVAILABLE_IN,
            values=("suite",),
            origin="user_requirement",
        )
    with pytest.raises(ValidationError, match="field provenance"):
        FilterObligation(
            kind=FilterObligationKind.CABIN_AVAILABLE_IN,
            values=("business",),
            origin="user_requirement",
        )
    with pytest.raises(ValidationError, match="field provenance"):
        FilterObligation(
            kind=FilterObligationKind.CARRIER_INVOLVEMENT_MATCH,
            values=("UA",),
            origin="user_requirement",
        )
    with pytest.raises(ValidationError, match="field provenance"):
        FilterObligation(
            kind=FilterObligationKind.REDEMPTION_PROGRAM_IN,
            values=("aeroplan",),
            origin="user_requirement",
        )
    with pytest.raises(ValidationError, match="field provenance"):
        FilterObligation(
            kind=FilterObligationKind.MIN_REPORTED_CABIN_DISTANCE_PERCENT,
            values=("100",),
            origin="user_requirement",
        )
    with pytest.raises(ValidationError, match="only direct-flight"):
        FilterObligation(
            kind=FilterObligationKind.CARRIER_INVOLVEMENT_MATCH,
            values=("UA",),
            origin="planner_structure",
        )


def test_filter_operands_are_canonicalized_and_deduplicated() -> None:
    provenance = FieldProvenance(
        field=EffectiveField.HARD_CONSTRAINTS,
        source=InitialSnapshotSource(field=EffectiveField.HARD_CONSTRAINTS),
    )

    assert FilterObligation(
        kind=FilterObligationKind.CARRIER_INVOLVEMENT_MATCH,
        values=(" UA ", "ua", "AA"),
        origin="user_requirement",
        field_provenance=provenance,
    ).values == ("aa", "ua")
    assert FilterObligation(
        kind=FilterObligationKind.MIN_REPORTED_CABIN_DISTANCE_PERCENT,
        values=("0100", "100"),
        origin="user_requirement",
        field_provenance=provenance,
    ).values == ("100",)
    assert FilterObligation(
        kind=FilterObligationKind.DIRECT_FLIGHT_AVAILABLE,
        values=(" TRUE ", "true"),
        origin="planner_structure",
    ).values == ("true",)


def test_search_plan_receipt_identity_and_budget_receipts_are_exact() -> None:
    result = _plan(_request())
    assert result.plan is not None
    document = result.plan.model_dump(mode="python", round_trip=True)

    mismatched_capability = dict(document)
    mismatched_capability["capability_id"] = "other.capability"
    with pytest.raises(ValidationError, match="capability ID"):
        SearchPlanningResult.model_validate({"outcome": "planned", "plan": mismatched_capability})

    duplicate_budget = dict(document)
    duplicate_budget["budget_receipts"] = [
        document["budget_receipts"][0],
        document["budget_receipts"][0],
    ]
    with pytest.raises(ValidationError, match="exactly one receipt"):
        SearchPlanningResult.model_validate({"outcome": "planned", "plan": duplicate_budget})


@pytest.mark.parametrize(
    ("outcome", "extra"),
    [
        ("planned", {}),
        ("reduced_coverage", {"exclusions": ["optional topology expansion omitted"]}),
    ],
)
def test_success_outcomes_reject_exceeded_budget_receipts(
    outcome: str, extra: dict[str, object]
) -> None:
    result = _plan(_request())
    assert result.plan is not None
    document = result.plan.model_dump(mode="python", round_trip=True)
    document["budget_receipts"] = [
        {
            **receipt,
            "observed": receipt["limit"] + 1,
            "disposition": "exceeded",
        }
        if receipt["kind"] == "endpoint_pair_count"
        else receipt
        for receipt in document["budget_receipts"]
    ]

    with pytest.raises(ValidationError, match="cannot contain exceeded budget receipts"):
        SearchPlanningResult.model_validate({"outcome": outcome, "plan": document, **extra})


def test_search_plan_requires_knowledge_receipt_as_of_to_match_identity() -> None:
    result = _plan(_request())
    assert result.plan is not None
    document = result.plan.model_dump(mode="python", round_trip=True)
    document["identity"]["knowledge_receipt"]["snapshot_as_of"] = "2026-09-11"

    with pytest.raises(ValidationError, match="snapshot as-of"):
        SearchPlanningResult.model_validate({"outcome": "planned", "plan": document})


def test_capability_record_pins_endpoint_and_rejects_duplicate_sources() -> None:
    capability_document = load_default_cached_search_capability().model_dump(
        mode="python", round_trip=True
    )
    capability_document["provider"] = "other_provider"
    with pytest.raises(ValidationError):
        CachedSearchCapability.model_validate(capability_document)

    duplicate_source_document = load_default_cached_search_capability().model_dump(
        mode="python", round_trip=True
    )
    duplicate_source_document["sources"] = [
        *duplicate_source_document["sources"],
        duplicate_source_document["sources"][0],
    ]
    with pytest.raises(ValidationError, match="source IDs must be unique"):
        CachedSearchCapability.model_validate(duplicate_source_document)

    malformed_source_document = load_default_cached_search_capability().model_dump(
        mode="python", round_trip=True
    )
    malformed_source_document["sources"] = [{}]
    with pytest.raises(ValidationError):
        CachedSearchCapability.model_validate(malformed_source_document)


def test_capability_record_is_local_evidence_for_exactly_the_reviewed_filters() -> None:
    capability = load_cached_search_capability(default_capability_path())

    assert capability.capability_id == "seats_aero.cached_search.v1"
    assert set(capability.supported_filters) == set(FilterObligationKind)
    assert set(capability.required_dimensions) == {
        "origin_airport_list",
        "destination_airport_list",
    }
    assert any("seat-count" in caveat for caveat in capability.caveats)


def test_capability_receipt_fingerprints_the_exact_record_and_changes_plan_identity() -> None:
    request = _request()
    baseline_capability = load_default_cached_search_capability()
    changed_document = baseline_capability.model_dump(mode="python", round_trip=True)
    changed_document["caveats"] = [*changed_document["caveats"], "Test-only changed caveat."]
    changed_capability = CachedSearchCapability.model_validate(changed_document)

    baseline = plan_searches(
        _envelope(request),
        policy=PlanningPolicy(),
        snapshot=load_default_knowledge_snapshot(),
        capability=baseline_capability,
    )
    changed = plan_searches(
        _envelope(request),
        policy=PlanningPolicy(),
        snapshot=load_default_knowledge_snapshot(),
        capability=changed_capability,
    )

    assert baseline.plan is not None and changed.plan is not None
    assert capability_receipt_matches(
        baseline_capability, baseline.plan.identity.capability_receipt
    )
    assert not capability_receipt_matches(
        changed_capability, baseline.plan.identity.capability_receipt
    )
    assert (
        baseline.plan.identity.capability_receipt.content_sha256
        != changed.plan.identity.capability_receipt.content_sha256
    )


def test_default_capability_wrapper_returns_typed_evidence_failure_for_corrupt_record(
    tmp_path: Any,
) -> None:
    corrupt = tmp_path / "corrupt-capability.json"
    corrupt.write_text("not-json", encoding="utf-8")

    result = plan_searches_with_default_capability(
        _envelope(_request()),
        policy=PlanningPolicy(),
        snapshot=load_default_knowledge_snapshot(),
        capability_path=corrupt,
    )

    assert result.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE
    assert [issue.code for issue in result.issues] == [
        SearchPlanningIssueCode.CAPABILITY_EVIDENCE_FAILURE
    ]


def test_plan_retains_provenance_and_structured_budget_and_repositioning_receipts() -> None:
    provenance = tuple(
        FieldProvenance(field=field, source=InitialSnapshotSource(field=field))
        for field in (
            EffectiveField.ORIGIN,
            EffectiveField.DESTINATION,
            EffectiveField.DEPARTURE,
            EffectiveField.TRAVELERS,
            EffectiveField.CABIN,
            EffectiveField.REPOSITIONING,
        )
    )
    result = _plan(_request(repositioning_allowed=False, field_provenance=provenance))

    assert result.plan is not None
    plan = result.plan
    assert all(item.field_provenance is not None for item in plan.location_results)
    assert all(item.date_envelope.field_provenance is not None for item in plan.award_search_items)
    assert all(
        item.result_validation_obligations[0].field_provenance is not None
        and item.result_validation_obligations[0].responsible_stage == "provider_result_validation"
        and item.result_validation_obligations[0].disposition == "not_verified"
        for item in plan.award_search_items
    )
    assert plan.repositioning_policy_receipt.requested_value is False
    assert plan.repositioning_policy_receipt.decision == "enabled_not_consumed_v1"
    assert {
        (receipt.kind.value, receipt.observed, receipt.limit) for receipt in plan.budget_receipts
    } == {
        ("input_window_days", 3, 31),
        ("endpoint_pair_count", 3, 25),
        ("path_candidate_count", 0, 20),
        ("path_hypothesis_count", 0, 12),
        ("total_award_search_item_count", 3, 40),
        ("date_expanded_work_days", 9, 1400),
    }


def test_budget_overflow_returns_observed_and_limit_receipts() -> None:
    result = _plan(_request(), policy=PlanningPolicy(max_endpoint_pairs=2))

    assert result.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert {
        (receipt.kind.value, receipt.observed, receipt.limit, receipt.disposition)
        for receipt in result.budget_receipts
    } == {
        ("input_window_days", 3, 31, "within_limit"),
        ("endpoint_pair_count", 3, 2, "exceeded"),
    }


def test_empty_constraint_and_unknown_detail_are_typed_not_validation_exceptions() -> None:
    invalid_constraint = _plan(_request(hard_constraints=("",)))
    unknown_detail = _plan(
        _request(
            unknowns=(UnknownField(field="cabin_detail", reason=UnknownReason.MISSING, detail=""),)
        )
    )

    assert invalid_constraint.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert [issue.code for issue in invalid_constraint.issues] == [
        SearchPlanningIssueCode.INVALID_HARD_CONSTRAINT
    ]
    assert unknown_detail.plan is not None
    assert (
        unknown_detail.plan.nonblocking_issues[0].message
        == "nonblocking unknown preserved without detail"
    )
    assert unknown_detail.plan.nonblocking_issues[0].preserved_value == ""


def test_unordered_alternatives_and_capability_source_order_produce_canonical_plan_bytes() -> None:
    request = _request(
        origins=(
            _location(LocationKind.AIRPORT, "SFO"),
            _location(LocationKind.CITY, "NYC"),
        )
    )
    reversed_request = request.model_copy(update={"origins": tuple(reversed(request.origins))})
    capability_document = load_default_cached_search_capability().model_dump(
        mode="python", round_trip=True
    )
    second_source = dict(capability_document["sources"][0])
    second_source.update(
        {
            "source_id": "seats-aero-concepts-local-2026-09-08",
            "content_sha256": "f" * 64,
        }
    )
    capability_document["sources"] = [*capability_document["sources"], second_source]
    capability = CachedSearchCapability.model_validate(capability_document)
    reversed_document = capability.model_dump(mode="python", round_trip=True)
    reversed_document["sources"] = list(reversed(reversed_document["sources"]))
    reversed_capability = CachedSearchCapability.model_validate(reversed_document)

    first = plan_searches(
        _envelope(request),
        policy=PlanningPolicy(),
        snapshot=load_default_knowledge_snapshot(),
        capability=capability,
    )
    second = plan_searches(
        _envelope(reversed_request),
        policy=PlanningPolicy(),
        snapshot=load_default_knowledge_snapshot(),
        capability=reversed_capability,
    )

    assert first.plan is not None and second.plan is not None
    assert json.dumps(first.plan.model_dump(mode="json"), sort_keys=True) == json.dumps(
        second.plan.model_dump(mode="json"), sort_keys=True
    )


def test_full_plan_read_path_is_copy_isolated_and_never_exposes_provider_payload_keys() -> None:
    result = _plan(_request())
    assert result.plan is not None
    plan = result.plan
    plan.location_results[0].resolution.location.value = "MUTATED"
    assert plan.location_results[0].resolution.location.value == "SFO"

    def _keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(_keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(_keys(item) for item in value)) if value else set()
        return set()

    assert {"origin_airport", "destination_airport", "seat_count"}.isdisjoint(
        _keys(plan.model_dump(mode="json"))
    )
