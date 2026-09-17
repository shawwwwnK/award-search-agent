"""Offline contract tests for the Milestone 2A airport selector seam."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from openai import OpenAI
from test_catalog_serving import _location, _ready_envelope, _release

from award_agent.domain import LocationKind
from award_agent.search_planning import (
    ORIGINAL_SIMPLE_AIRPORT_SELECTOR_PROMPT,
    AirportCandidateDisposition,
    AirportIdentityStatus,
    AirportSelectionCapPolicy,
    AirportSelectionPlanningInput,
    AirportSelectionProposal,
    AirportSelectionProposalOutcome,
    AirportSelectorModelInput,
    CatalogKnowledgeRepository,
    CityAirportDistanceConsistency,
    CityAirportDistanceStatus,
    CityServingStatus,
    GeographicMembershipStatus,
    OpenAIAirportSelector,
    OpenAIAirportSelectorConfig,
    OpenAIAirportSelectorError,
    PlanningPolicy,
    ResolvedEntityContext,
    SearchPlanningOutcome,
    airport_selection_record_digest,
    context_for_resolved_location,
    ground_endpoint,
    load_default_cached_search_capability,
    plan_searches_from_airport_selection_records,
    validate_airport_selection_proposal,
)


class _Responses:
    def __init__(self, output: object | Exception) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return SimpleNamespace(
            output_parsed=self.output,
            usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        )


class _Client:
    def __init__(self, output: object | Exception) -> None:
        self.responses = _Responses(output)


def _proposal(*codes: str) -> AirportSelectionProposal:
    return AirportSelectionProposal(
        outcome=AirportSelectionProposalOutcome.PROPOSED,
        airport_iata_codes=codes,
    )


def _context(
    repository: CatalogKnowledgeRepository, kind: LocationKind, value: str
) -> ResolvedEntityContext:
    result = ground_endpoint(_location(kind, value), "origin", repository, PlanningPolicy())
    return context_for_resolved_location(result.resolution, repository)


def test_openai_adapter_uses_structured_output_storage_off_and_private_capture() -> None:
    client = _Client(_proposal("TST"))
    selector = OpenAIAirportSelector(
        OpenAIAirportSelectorConfig(model="test-selector"),
        client=cast(OpenAI, client),
        capture_llm_io=True,
    )
    model_input = AirportSelectorModelInput.model_validate(
        {
            "entity_id": "geonames:2",
            "entity_label": "Test City",
            "entity_kind": "city",
            "category": "city_metropolitan",
            "category_basis": "entity_kind",
            "country_code": "US",
            "applicable_cap": 2,
        }
    )

    assert selector.propose(model_input).airport_iata_codes == ("TST",)
    request = client.responses.calls[0]
    assert request["store"] is False
    assert request["text_format"] is AirportSelectionProposal
    assert selector.take_usage() == {
        "calls": 1,
        "captured_calls": 1,
        "missing_calls": 0,
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
    }
    trace = selector.take_call_traces()[0]
    assert trace["stage"] == "airport_endpoint_selector"
    assert trace["request"]["store"] is False
    assert trace["adapter"]["response_schema_sha256"]

    original_client = _Client(_proposal("TST"))
    original = OpenAIAirportSelector(
        OpenAIAirportSelectorConfig(
            model="test-selector", prompt=ORIGINAL_SIMPLE_AIRPORT_SELECTOR_PROMPT
        ),
        client=cast(OpenAI, original_client),
    )
    assert original.propose(model_input).airport_iata_codes == ("TST",)
    original_request = original_client.responses.calls[0]
    assert original_request["text_format"] is AirportSelectionProposal
    assert original_request["store"] is False
    assert "no more than 5" in str(original_request["instructions"]).casefold()

    failing = OpenAIAirportSelector(
        OpenAIAirportSelectorConfig(model="test-selector"),
        client=cast(OpenAI, _Client(ValueError("transport"))),
    )
    try:
        failing.propose(model_input)
    except OpenAIAirportSelectorError:
        pass
    else:  # pragma: no cover - regression guard
        raise AssertionError("adapter did not raise its typed error")
    assert failing.take_usage() == {
        "calls": 1,
        "captured_calls": 0,
        "missing_calls": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def test_validation_records_duplicate_missing_identity_cap_and_country_evidence(
    tmp_path: Path,
) -> None:
    release = _release(tmp_path)
    with CatalogKnowledgeRepository(release) as repository:
        city = _context(repository, LocationKind.CITY, "Test City")
        standard = validate_airport_selection_proposal(
            role="origin",
            context=city,
            cap_policy=AirportSelectionCapPolicy(policy_version="test-cap-v1"),
            distance_policy=CityAirportDistanceConsistency(policy_version="distance-v1"),
            proposal=_proposal("TST", "TST", "ZZZ"),
            model="offline-test",
            repository=repository,
        )
        assert [item.disposition for item in standard.candidate_validations] == [
            AirportCandidateDisposition.ACCEPTED_FOR_EXPLORATORY_SEARCH,
            AirportCandidateDisposition.REJECTED_DUPLICATE,
            AirportCandidateDisposition.REJECTED_INVALID_IDENTITY,
        ]
        assert (
            standard.candidate_validations[1].identity_status is AirportIdentityStatus.NOT_EVALUATED
        )
        assert (
            standard.candidate_validations[1].city_serving_status is CityServingStatus.NOT_EVALUATED
        )
        assert (
            standard.candidate_validations[2].city_serving_status is CityServingStatus.UNAVAILABLE
        )
        assert standard.accepted_airports[0].airport_iata == "TST"

        capped = validate_airport_selection_proposal(
            role="origin",
            context=city,
            cap_policy=AirportSelectionCapPolicy(
                policy_version="test-cap-one", city_metropolitan_default_cap=1
            ),
            distance_policy=CityAirportDistanceConsistency(policy_version="distance-v1"),
            proposal=_proposal("TST", "ZZZ"),
            model="offline-test",
            repository=repository,
        )
        assert (
            capped.candidate_validations[1].disposition
            is AirportCandidateDisposition.REJECTED_OVER_CAP
        )

        country = _context(repository, LocationKind.COUNTRY, "United States")
        contradicted_context = ResolvedEntityContext.model_validate(
            {**country.model_dump(mode="python"), "country_code": "CA"}
        )
        contradiction = validate_airport_selection_proposal(
            role="destination",
            context=contradicted_context,
            cap_policy=AirportSelectionCapPolicy(policy_version="test-cap-v1"),
            distance_policy=CityAirportDistanceConsistency(policy_version="distance-v1"),
            proposal=_proposal("TST"),
            model="offline-test",
            repository=repository,
        )
        assert (
            contradiction.candidate_validations[0].geographic_membership
            is GeographicMembershipStatus.CONTRADICTED
        )
        assert not contradiction.accepted_airports
        assert (
            contradiction.candidate_validations[0].city_serving_status
            is CityServingStatus.NOT_APPLICABLE
        )


def test_city_distance_rejects_grossly_inconsistent_endpoint_without_claiming_service(
    tmp_path: Path,
) -> None:
    release = _release(tmp_path)
    with CatalogKnowledgeRepository(release) as repository:
        city = _context(repository, LocationKind.CITY, "Test City")
        far_city = ResolvedEntityContext.model_validate(
            {**city.model_dump(mode="python"), "latitude": 0.0, "longitude": 0.0}
        )
        record = validate_airport_selection_proposal(
            role="origin",
            context=far_city,
            cap_policy=AirportSelectionCapPolicy(policy_version="test-cap-v1"),
            distance_policy=CityAirportDistanceConsistency(policy_version="distance-v1"),
            proposal=_proposal("TST"),
            model="offline-test",
            repository=repository,
        )
        candidate = record.candidate_validations[0]
        assert (
            candidate.disposition
            is AirportCandidateDisposition.REJECTED_OUTSIDE_CITY_DISTANCE_POLICY
        )
        assert candidate.city_serving_status is CityServingStatus.MODEL_PROPOSED
        assert candidate.city_distance is not None
        assert candidate.city_distance.distance_km is not None


def test_planning_replays_supplied_records_without_model_and_binds_record_identity(
    tmp_path: Path,
) -> None:
    release = _release(tmp_path)
    policy = AirportSelectionCapPolicy(policy_version="test-cap-v1")
    distance = CityAirportDistanceConsistency(policy_version="distance-v1")
    with CatalogKnowledgeRepository(release) as repository:
        origin = _location(LocationKind.CITY, "Test City")
        destination = _location(LocationKind.COUNTRY, "United States")
        origin_context = _context(repository, LocationKind.CITY, "Test City")
        destination_context = _context(repository, LocationKind.COUNTRY, "United States")
        origin_record = validate_airport_selection_proposal(
            role="origin",
            context=origin_context,
            cap_policy=policy,
            distance_policy=distance,
            proposal=_proposal("TST"),
            model="offline-test",
            repository=repository,
        )
        destination_record = validate_airport_selection_proposal(
            role="destination",
            context=destination_context,
            cap_policy=policy,
            distance_policy=distance,
            proposal=_proposal("TST"),
            model="offline-test",
            repository=repository,
        )
        result = plan_searches_from_airport_selection_records(
            AirportSelectionPlanningInput(
                envelope=_ready_envelope(origin, destination),
                selection_records=(origin_record, destination_record),
            ),
            selection_cap_policy=policy,
            distance_policy=distance,
            policy=PlanningPolicy(max_source_evidence_age_days=3650),
            capability=load_default_cached_search_capability(),
            repository=repository,
        )
        assert result.planning_result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
        assert result.planning_result.plan is not None
        assert airport_selection_record_digest(origin_record) != airport_selection_record_digest(
            destination_record
        )
        assert {
            item.selection.kind.value
            for item in result.planning_result.plan.location_results
            if item.selection
        } == {"model_proposed"}

        stale_policy_result = plan_searches_from_airport_selection_records(
            AirportSelectionPlanningInput(
                envelope=_ready_envelope(origin, destination),
                selection_records=(origin_record, destination_record),
            ),
            selection_cap_policy=AirportSelectionCapPolicy(policy_version="other-policy"),
            distance_policy=distance,
            policy=PlanningPolicy(max_source_evidence_age_days=3650),
            capability=load_default_cached_search_capability(),
            repository=repository,
        )
        assert stale_policy_result.planning_result.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE


def test_replay_revalidates_forged_distance_and_binds_audit_identity(tmp_path: Path) -> None:
    release = _release(tmp_path)
    policy = AirportSelectionCapPolicy(policy_version="test-cap-v1")
    distance = CityAirportDistanceConsistency(policy_version="distance-v1")
    with CatalogKnowledgeRepository(release) as repository:
        origin = _location(LocationKind.CITY, "Test City")
        destination = _location(LocationKind.COUNTRY, "United States")
        origin_record = validate_airport_selection_proposal(
            role="origin",
            context=_context(repository, LocationKind.CITY, "Test City"),
            cap_policy=policy,
            distance_policy=distance,
            proposal=_proposal("TST"),
            model="offline-test",
            repository=repository,
        )
        destination_record = validate_airport_selection_proposal(
            role="destination",
            context=_context(repository, LocationKind.COUNTRY, "United States"),
            cap_policy=policy,
            distance_policy=distance,
            proposal=_proposal("TST"),
            model="offline-test",
            repository=repository,
        )
        valid_input = AirportSelectionPlanningInput(
            envelope=_ready_envelope(origin, destination),
            selection_records=(origin_record, destination_record),
        )
        valid = plan_searches_from_airport_selection_records(
            valid_input,
            selection_cap_policy=policy,
            distance_policy=distance,
            policy=PlanningPolicy(max_source_evidence_age_days=3650),
            capability=load_default_cached_search_capability(),
            repository=repository,
        )
        altered_record = origin_record.model_copy(
            update={
                "model": "different-pinned-model",
            }
        )
        altered = plan_searches_from_airport_selection_records(
            valid_input.model_copy(
                update={"selection_records": (altered_record, destination_record)}
            ),
            selection_cap_policy=policy,
            distance_policy=distance,
            policy=PlanningPolicy(max_source_evidence_age_days=3650),
            capability=load_default_cached_search_capability(),
            repository=repository,
        )
        assert valid.replay_receipt.record_digests != altered.replay_receipt.record_digests

        original_candidate = origin_record.candidate_validations[0]
        assert original_candidate.city_distance is not None
        forged_distance = original_candidate.city_distance.model_copy(
            update={
                "status": CityAirportDistanceStatus.OUTSIDE_POLICY_DISTANCE,
                "distance_km": 999.0,
            }
        )
        forged_candidate = original_candidate.model_copy(update={"city_distance": forged_distance})
        forged_record = origin_record.model_copy(
            update={"candidate_validations": (forged_candidate,)}
        )
        forged = plan_searches_from_airport_selection_records(
            valid_input.model_copy(
                update={"selection_records": (forged_record, destination_record)}
            ),
            selection_cap_policy=policy,
            distance_policy=distance,
            policy=PlanningPolicy(max_source_evidence_age_days=3650),
            capability=load_default_cached_search_capability(),
            repository=repository,
        )
        assert forged.planning_result.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE

        destination_candidate = destination_record.candidate_validations[0].model_copy(
            update={"geographic_membership": GeographicMembershipStatus.CONTRADICTED}
        )
        membership_forged = destination_record.model_copy(
            update={"candidate_validations": (destination_candidate,)}
        )
        forged_membership = plan_searches_from_airport_selection_records(
            valid_input.model_copy(
                update={"selection_records": (origin_record, membership_forged)}
            ),
            selection_cap_policy=policy,
            distance_policy=distance,
            policy=PlanningPolicy(max_source_evidence_age_days=3650),
            capability=load_default_cached_search_capability(),
            repository=repository,
        )
        assert forged_membership.planning_result.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE
