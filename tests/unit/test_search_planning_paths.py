"""Offline path, temporal, and budget invariants for search planning.

Every route edge here is visibly synthetic test-fixture evidence.  The default
knowledge snapshot intentionally carries no operational topology receipts.
"""

from __future__ import annotations

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
)
from award_agent.search_planning import (
    BudgetKind,
    ComponentPaymentMode,
    FilterObligationKind,
    KnowledgeSnapshot,
    ManualCashTemporalValidationKind,
    PlanningInputEnvelope,
    PlanningPolicy,
    PlanningSource,
    SearchPlan,
    SearchPlanningOutcome,
    SearchPlanningResult,
    SearchScope,
    load_default_cached_search_capability,
    load_default_knowledge_snapshot,
    plan_searches,
)

_CONTEXT = RequestContext(reference_date=date(2026, 9, 12), timezone="America/Los_Angeles")


def _location(kind: LocationKind, value: str) -> LocationRef:
    return LocationRef(kind=kind, value=value, raw_text=value)


def _request(**changes: Any) -> EffectiveRequest:
    request = EffectiveRequest(
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
    return request.model_copy(update=changes)


def _snapshot(*edges: tuple[str, str, str]) -> KnowledgeSnapshot:
    """Return the seed snapshot with explicitly synthetic directed test edges."""

    document = load_default_knowledge_snapshot().model_dump(mode="python", round_trip=True)
    document["sources"] = [
        *document["sources"],
        {
            "source_id": "synthetic-path-fixture",
            "title": "Synthetic path fixture only",
            "url": "https://example.test/synthetic-path-fixture",
            "license_note": "Synthetic test fixture only; not operational route evidence.",
            "verified_on": date(2026, 9, 12),
            "version_or_capture_id": "test-fixture-v1",
            "verification_scope": "Unit-test-only synthetic directed topology.",
        },
    ]
    document["route_edges"] = [
        {
            "edge_id": edge_id,
            "origin_airport_id": origin,
            "destination_airport_id": destination,
            "evidence_kind": "synthetic_test_fixture",
            "source_ids": ["synthetic-path-fixture"],
        }
        for edge_id, origin, destination in edges
    ]
    return KnowledgeSnapshot.model_validate(document)


def _plan(
    snapshot: KnowledgeSnapshot, *, policy: PlanningPolicy | None = None
) -> SearchPlanningResult:
    return plan_searches(
        PlanningInputEnvelope(
            source=PlanningSource(session_id="path-session", revision=1),
            effective_request=_request(),
        ),
        policy=policy or PlanningPolicy(),
        snapshot=snapshot,
        capability=load_default_cached_search_capability(),
    )


def test_directed_synthetic_edges_create_only_a_connected_two_component_path() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )

    assert result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert result.plan is not None
    assert len(result.plan.explicit_path_hypotheses) == 1
    path = result.plan.explicit_path_hypotheses[0]
    assert [
        (component.origin_endpoint.airport_iata, component.destination_endpoint.airport_iata)
        for component in path.components
    ] == [("SFO", "JFK"), ("JFK", "HND")]
    assert all(
        component.route_evidence_kind == "synthetic_test_fixture" for component in path.components
    )
    assert all(
        item.scope is SearchScope.EXPLICIT_PHYSICAL_COMPONENT
        for item in result.plan.award_search_items
        if item.item_id in {component.award_search_item_id for component in path.components}
    )
    for component in path.components:
        item = next(
            item
            for item in result.plan.award_search_items
            if item.item_id == component.award_search_item_id
        )
        assert {filter_.kind.value for filter_ in item.filter_obligations} == {
            "cabin_available_in",
            "direct_flight_available",
        }
        assert any(
            obligation.kind.value == "exact_physical_component_structure"
            for obligation in item.result_validation_obligations
        )
    assert [
        pattern.component_payment_modes for pattern in result.plan.payment_patterns
    ] == [(ComponentPaymentMode.AWARD, ComponentPaymentMode.AWARD)]
    assert not result.plan.manual_cash_check_templates


def test_mixed_mode_reuses_path_and_award_items_with_dormant_manual_cash_templates() -> None:
    snapshot = _snapshot(
        ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
        ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
    )
    request = _request(search_modes=(SearchMode.AWARD, SearchMode.CASH))
    result = plan_searches(
        PlanningInputEnvelope(
            source=PlanningSource(session_id="mixed-path-session", revision=1),
            effective_request=request,
        ),
        policy=PlanningPolicy(),
        snapshot=snapshot,
        capability=load_default_cached_search_capability(),
    )

    assert result.plan is not None
    plan = result.plan
    path = plan.explicit_path_hypotheses[0]
    assert len(plan.explicit_path_hypotheses) == 1
    assert {
        pattern.component_payment_modes for pattern in plan.payment_patterns
    } == {
        (ComponentPaymentMode.AWARD, ComponentPaymentMode.AWARD),
        (ComponentPaymentMode.AWARD, ComponentPaymentMode.MANUAL_CASH),
        (ComponentPaymentMode.MANUAL_CASH, ComponentPaymentMode.AWARD),
    }
    assert len(plan.manual_cash_check_templates) == 2
    assert all(item.automated_mode == "award" for item in plan.award_search_items)
    templates_by_index = {
        template.manual_component_index: template for template in plan.manual_cash_check_templates
    }
    cash_first = templates_by_index[1]
    assert cash_first.manual_component_id == path.components[0].component_id
    assert cash_first.relevant_award_search_item_id == path.components[1].award_search_item_id
    assert (
        cash_first.temporal_validation_kind
        is ManualCashTemporalValidationKind.FIRST_COMPONENT_WITHIN_ORIGINAL_WINDOW
    )
    assert cash_first.traveler_count == 2
    assert cash_first.requested_cabins == (CabinClass.BUSINESS,)
    assert cash_first.activation == "after_relevant_award_observation"
    assert cash_first.automation == "manual_only"
    assert cash_first.pricing_status == "unpriced"
    assert cash_first.verification_status == "not_verified"
    assert (
        path.components[0].date_envelope.start,
        path.components[0].date_envelope.end,
    ) == (date(2026, 10, 5), date(2026, 10, 7))

    award_first = templates_by_index[2]
    assert award_first.manual_component_id == path.components[1].component_id
    assert award_first.relevant_award_search_item_id == path.components[0].award_search_item_id
    assert (
        award_first.temporal_validation_kind
        is ManualCashTemporalValidationKind.LATER_COMPONENT_REQUIRES_ASSEMBLED_JOURNEY_VALIDATION
    )


def test_payment_contract_rejects_all_cash_and_hybrid_without_dormant_template() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )
    assert result.plan is not None
    all_cash = result.plan.model_dump(mode="python", round_trip=True)
    # The award-only pattern cannot be replaced by all cash even before any
    # provider stage exists.
    all_cash["payment_patterns"][0]["component_payment_modes"] = [
        ComponentPaymentMode.MANUAL_CASH,
        ComponentPaymentMode.MANUAL_CASH,
    ]
    with pytest.raises(ValidationError, match="retain at least one award"):
        SearchPlan.model_validate(all_cash)

    mixed_request = _request(search_modes=(SearchMode.AWARD, SearchMode.CASH))
    mixed_result = plan_searches(
        PlanningInputEnvelope(
            source=PlanningSource(session_id="mixed-template-session", revision=1),
            effective_request=mixed_request,
        ),
        policy=PlanningPolicy(),
        snapshot=_snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        ),
        capability=load_default_cached_search_capability(),
    )
    assert mixed_result.plan is not None
    missing_template = mixed_result.plan.model_dump(mode="python", round_trip=True)
    missing_template["manual_cash_check_templates"] = []
    with pytest.raises(ValidationError, match="hybrid payment pattern"):
        SearchPlan.model_validate(missing_template)


def test_search_plan_rejects_disagreeing_probe_requirements() -> None:
    planned = _plan(_snapshot())
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    document["endpoint_probes"][1]["traveler_count"] = 1

    with pytest.raises(ValidationError, match="endpoint probes must agree"):
        SearchPlan.model_validate(document)


def test_search_plan_rejects_tampered_physical_item_requirements() -> None:
    planned = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    component_item_id = document["explicit_path_hypotheses"][0]["components"][0][
        "award_search_item_id"
    ]
    component_item = next(
        item for item in document["award_search_items"] if item["item_id"] == component_item_id
    )
    component_item["result_validation_obligations"][0]["minimum_seats"] = 1

    with pytest.raises(ValidationError, match="exactly one matching minimum-seat obligation"):
        SearchPlan.model_validate(document)


def test_search_plan_rejects_tampered_manual_template_requirements_and_optional_item_link() -> None:
    mixed_request = _request(search_modes=(SearchMode.AWARD, SearchMode.CASH))
    mixed_result = plan_searches(
        PlanningInputEnvelope(
            source=PlanningSource(session_id="template-invariant-session", revision=1),
            effective_request=mixed_request,
        ),
        policy=PlanningPolicy(),
        snapshot=_snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        ),
        capability=load_default_cached_search_capability(),
    )
    assert mixed_result.plan is not None

    tampered_requirements = mixed_result.plan.model_dump(mode="python", round_trip=True)
    tampered_requirements["manual_cash_check_templates"][0]["traveler_count"] = 1
    with pytest.raises(ValidationError, match="global cabin and traveler requirements"):
        SearchPlan.model_validate(tampered_requirements)

    tampered_link = mixed_result.plan.model_dump(mode="python", round_trip=True)
    tampered_link["manual_cash_check_templates"][0][
        "manual_component_award_search_item_id"
    ] = "award:not-the-manual-component"
    with pytest.raises(ValidationError, match="optional component item must match its path"):
        SearchPlan.model_validate(tampered_link)


def test_empty_cabins_are_preserved_across_paths_and_manual_cash_templates() -> None:
    result = plan_searches(
        PlanningInputEnvelope(
            source=PlanningSource(session_id="empty-cabin-path-session", revision=1),
            effective_request=_request(cabins=(), search_modes=(SearchMode.AWARD, SearchMode.CASH)),
        ),
        policy=PlanningPolicy(),
        snapshot=_snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        ),
        capability=load_default_cached_search_capability(),
    )

    assert result.plan is not None
    assert all(probe.requested_cabins == () for probe in result.plan.endpoint_probes)
    assert all(item.requested_cabins == () for item in result.plan.award_search_items)
    assert all(
        not any(
            filter_.kind is FilterObligationKind.CABIN_AVAILABLE_IN
            for filter_ in item.filter_obligations
        )
        for item in result.plan.award_search_items
    )
    assert all(template.requested_cabins == () for template in result.plan.manual_cash_check_templates)


def test_reverse_and_airport_changing_edges_are_not_inferred() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:jfk-sfo", "airport:jfk", "airport:sfo"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )

    assert result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert result.plan is not None
    assert not result.plan.explicit_path_hypotheses
    assert any("topology is unavailable" in item for item in result.exclusions)


def test_country_destination_does_not_invent_an_onward_domestic_leg() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
            ("synthetic:hnd-nrt", "airport:hnd", "airport:nrt"),
        )
    )

    assert result.plan is not None
    destination_airport_ids = {
        airport.airport_id
        for location_result in result.plan.location_results
        if location_result.role == "destination" and location_result.selection is not None
        for airport in location_result.selection.airports
    }
    assert destination_airport_ids == {"airport:hnd", "airport:nrt", "airport:kix"}
    for hypothesis in result.plan.explicit_path_hypotheses:
        assert hypothesis.requested_destination_endpoint.airport_id in destination_airport_ids
        assert (
            hypothesis.components[-1].destination_endpoint.airport_id
            == hypothesis.requested_destination_endpoint.airport_id
        )
        assert len(hypothesis.components) == 2


def test_ground_transport_edge_is_rejected_as_non_airport_topology() -> None:
    document = _snapshot().model_dump(mode="python", round_trip=True)
    document["route_edges"] = [
        {
            "edge_id": "synthetic:sfo-ground-lax",
            "origin_airport_id": "airport:sfo",
            "destination_airport_id": "ground:lax",
            "evidence_kind": "synthetic_test_fixture",
            "source_ids": ["synthetic-path-fixture"],
        }
    ]

    with pytest.raises(ValidationError, match="unknown airport endpoint"):
        KnowledgeSnapshot.model_validate(document)


def test_later_component_uses_its_own_timezone_and_minus_one_plus_two_envelope() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )

    assert result.plan is not None
    first, later = result.plan.explicit_path_hypotheses[0].components
    assert (first.date_envelope.start, first.date_envelope.end, first.date_envelope.timezone) == (
        date(2026, 10, 5),
        date(2026, 10, 7),
        "America/Los_Angeles",
    )
    assert (later.date_envelope.start, later.date_envelope.end, later.date_envelope.timezone) == (
        date(2026, 10, 4),
        date(2026, 10, 9),
        "America/New_York",
    )
    assert later.temporal_derivation.note == "not_connection_or_schedule_evidence"


def test_path_budget_exhaustion_is_reduced_coverage_and_endpoint_probes_survive() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        ),
        policy=PlanningPolicy(max_path_candidate_exploration=0),
    )

    assert result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert result.plan is not None
    assert len(result.plan.endpoint_probes) == 3
    assert not result.plan.explicit_path_hypotheses
    assert any("candidate exploration reached" in item for item in result.exclusions)
    receipts = {receipt.kind: receipt for receipt in result.plan.budget_receipts}
    assert receipts[BudgetKind.PATH_CANDIDATE_COUNT].observed == 0


def test_route_record_order_does_not_change_canonical_plan() -> None:
    edges = (
        ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
        ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
    )
    one = _plan(_snapshot(*edges))
    two = _plan(_snapshot(*reversed(edges)))

    assert one.plan is not None and two.plan is not None
    assert one.plan.model_dump(mode="json") == two.plan.model_dump(mode="json")


def test_unknown_route_date_applicability_is_explicitly_disclosed() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )

    assert result.plan is not None
    assert all(
        component.route_date_applicability == "unknown"
        and component.date_applicability_disclosure == "date_applicability_unknown"
        for component in result.plan.explicit_path_hypotheses[0].components
    )


def test_stale_and_known_inapplicable_route_evidence_are_omitted() -> None:
    snapshot = _snapshot(
        ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
        ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
    )
    stale_document = snapshot.model_dump(mode="python", round_trip=True)
    stale_document["sources"][-1]["verified_on"] = date(2020, 1, 1)
    stale_result = _plan(KnowledgeSnapshot.model_validate(stale_document))

    assert stale_result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert stale_result.plan is not None
    assert not stale_result.plan.explicit_path_hypotheses
    assert any("stale route evidence" in exclusion for exclusion in stale_result.exclusions)

    interval_document = snapshot.model_dump(mode="python", round_trip=True)
    for edge in interval_document["route_edges"]:
        edge.update(
            {
                "date_applicability": "known_inclusive_interval",
                "applicable_start": date(2026, 1, 1),
                "applicable_end": date(2026, 1, 2),
            }
        )
    interval_result = _plan(KnowledgeSnapshot.model_validate(interval_document))

    assert interval_result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert interval_result.plan is not None
    assert not interval_result.plan.explicit_path_hypotheses
    assert any("known-inapplicable" in exclusion for exclusion in interval_result.exclusions)


def test_outgoing_route_retrieval_is_bounded_per_endpoint_pair_with_receipt() -> None:
    routes = [
        ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
        ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
    ]
    # NRT and KIX are airport records in the seed fixture; their outgoing
    # edges need not form paths to demonstrate bounded source retrieval.
    routes.extend(
        (f"synthetic:sfo-{iata.lower()}", "airport:sfo", f"airport:{iata.lower()}")
        for iata in ("EWR", "LGA", "NRT", "KIX")
    )
    result = _plan(
        _snapshot(*routes),
        policy=PlanningPolicy(max_outgoing_route_edges_per_endpoint_pair=1),
    )

    assert result.plan is not None
    receipts = result.plan.path_exploration_receipts
    assert len(receipts) == len(result.plan.endpoint_probes)
    assert all(receipt.outgoing_edge_limit == 1 for receipt in receipts)
    assert all(len(receipt.examined_edge_ids) <= 1 for receipt in receipts)
    assert any(receipt.overflow for receipt in receipts)
    assert any("per-pair edge limit" in exclusion for exclusion in result.exclusions)


def test_hypothesis_budget_preflight_never_commits_a_partial_path() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
            ("synthetic:sfo-ewr", "airport:sfo", "airport:ewr"),
            ("synthetic:ewr-hnd", "airport:ewr", "airport:hnd"),
        ),
        # Three required endpoint items leave room for exactly one complete
        # two-item optional hypothesis, not one-and-a-half paths.
        policy=PlanningPolicy(max_total_award_search_items=5),
    )

    assert result.plan is not None
    assert len(result.plan.explicit_path_hypotheses) == 1
    component_item_ids = {
        component.award_search_item_id
        for path in result.plan.explicit_path_hypotheses
        for component in path.components
    }
    optional_items = [
        item
        for item in result.plan.award_search_items
        if item.scope is SearchScope.EXPLICIT_PHYSICAL_COMPONENT
    ]
    assert {item.item_id for item in optional_items} == component_item_ids
    assert len(optional_items) == 2
    assert any("total search-item budget" in exclusion for exclusion in result.exclusions)


def test_shared_component_searches_are_deduplicated_across_path_hypotheses() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
            ("synthetic:jfk-nrt", "airport:jfk", "airport:nrt"),
        )
    )

    assert result.plan is not None
    paths = result.plan.explicit_path_hypotheses
    assert len(paths) == 2
    first_component_ids = {path.components[0].award_search_item_id for path in paths}
    assert len(first_component_ids) == 1
    optional_items = [
        item
        for item in result.plan.award_search_items
        if item.scope is SearchScope.EXPLICIT_PHYSICAL_COMPONENT
    ]
    assert len(optional_items) == 3


def test_search_plan_rejects_malformed_global_ids_and_component_links() -> None:
    planned = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )
    assert planned.plan is not None

    duplicate_id = planned.plan.model_dump(mode="python", round_trip=True)
    duplicate_id["explicit_path_hypotheses"][0]["components"][0]["component_id"] = duplicate_id[
        "endpoint_probes"
    ][0]["probe_id"]
    with pytest.raises(ValidationError, match="globally unique"):
        SearchPlan.model_validate(duplicate_id)

    malformed_link = planned.plan.model_dump(mode="python", round_trip=True)
    malformed_link["explicit_path_hypotheses"][0]["components"][0]["date_envelope"]["start"] = date(
        2026, 10, 6
    )
    with pytest.raises(ValidationError, match="exactly match its temporal derivation"):
        SearchPlan.model_validate(malformed_link)


def test_search_plan_rejects_airport_changing_transfer_between_components() -> None:
    planned = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    components = document["explicit_path_hypotheses"][0]["components"]
    second_component = components[1]
    second_component["origin_endpoint"] = {
        **second_component["origin_endpoint"],
        "airport_id": "airport:ewr",
        "airport_iata": "EWR",
    }
    # Keep the component internally shaped so the hypothesis-level
    # connectivity invariant is the rejection under test.
    second_component["temporal_derivation"]["origin_airport_fact_id"] = "airport:ewr"

    assert (
        components[0]["destination_endpoint"]["airport_iata"],
        components[1]["origin_endpoint"]["airport_iata"],
    ) == ("JFK", "EWR")
    with pytest.raises(
        ValidationError,
        match="explicit path components must meet at the declared intermediate airport",
    ):
        SearchPlan.model_validate(document)


def test_known_route_applicability_must_cover_the_component_envelope() -> None:
    planned = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    component = document["explicit_path_hypotheses"][0]["components"][0]
    edge_id = component["route_edge_id"]
    component.update(
        {
            "route_date_applicability": "known_inclusive_interval",
            "route_applicable_start": date(2026, 10, 6),
            "route_applicable_end": date(2026, 10, 6),
            "date_applicability_disclosure": None,
        }
    )
    for receipt in document["path_exploration_receipts"]:
        for edge in receipt["available_edge_evidence"]:
            if edge["edge_id"] == edge_id:
                edge.update(
                    {
                        "route_date_applicability": "known_inclusive_interval",
                        "route_applicable_start": date(2026, 10, 6),
                        "route_applicable_end": date(2026, 10, 6),
                    }
                )
    with pytest.raises(ValidationError, match="cover the complete component date envelope"):
        SearchPlan.model_validate(document)


def test_path_route_evidence_must_be_canonical_and_in_knowledge_receipt() -> None:
    planned = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    document["explicit_path_hypotheses"][0]["components"][0][
        "route_evidence_source_ids"
    ] = ["unknown-route-source"]
    with pytest.raises(ValidationError, match="knowledge receipt"):
        SearchPlan.model_validate(document)


def test_path_route_evidence_binds_the_actual_directed_airport_pair() -> None:
    planned = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    component = document["explicit_path_hypotheses"][0]["components"][0]
    edge_id = component["route_edge_id"]
    for receipt in document["path_exploration_receipts"]:
        for edge in receipt["available_edge_evidence"]:
            if edge["edge_id"] == edge_id:
                edge["destination_airport_fact_id"] = "airport:hnd"
    with pytest.raises(ValidationError, match="bound directed route evidence"):
        SearchPlan.model_validate(document)


def test_path_exploration_receipts_must_cover_exactly_the_endpoint_pairs() -> None:
    planned = _plan(_snapshot())
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    document["path_exploration_receipts"] = list(document["path_exploration_receipts"][:-1])
    with pytest.raises(ValidationError, match="exactly the endpoint probe airport pairs"):
        SearchPlan.model_validate(document)


def test_budget_receipts_must_match_plan_derived_metrics() -> None:
    planned = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    for receipt in document["budget_receipts"]:
        if receipt["kind"] == BudgetKind.PATH_CANDIDATE_COUNT.value:
            receipt["observed"] += 1
            break
    with pytest.raises(ValidationError, match="plan-derived metrics"):
        SearchPlan.model_validate(document)


def test_physical_component_items_cannot_be_orphans() -> None:
    planned = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        )
    )
    assert planned.plan is not None
    document = planned.plan.model_dump(mode="python", round_trip=True)
    orphan = next(
        item
        for item in document["award_search_items"]
        if item["scope"] == SearchScope.EXPLICIT_PHYSICAL_COMPONENT.value
    )
    orphan = {**orphan, "item_id": "award:orphan-physical-component"}
    document["award_search_items"] = [*document["award_search_items"], orphan]
    with pytest.raises(ValidationError, match="linked by an explicit path component"):
        SearchPlan.model_validate(document)


def test_date_work_budget_rejection_does_not_commit_a_partial_hypothesis() -> None:
    result = _plan(
        _snapshot(
            ("synthetic:sfo-jfk", "airport:sfo", "airport:jfk"),
            ("synthetic:jfk-hnd", "airport:jfk", "airport:hnd"),
        ),
        policy=PlanningPolicy(max_date_expanded_work_days=17),
    )
    assert result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert result.plan is not None
    assert not result.plan.explicit_path_hypotheses
    assert not any(
        item.scope is SearchScope.EXPLICIT_PHYSICAL_COMPONENT
        for item in result.plan.award_search_items
    )
    assert any("date-expanded work" in item for item in result.exclusions)
