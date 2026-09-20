"""Focused contract tests for the Milestone 2C replacement boundary."""

from datetime import date

import pytest
from pydantic import ValidationError

from award_agent.search_planning.compilation_contracts import (
    CompilationBudgetKind,
    CompilationBudgetReceipt,
    CompilationCoverage,
    LogicalAwardQuery,
    SearchPlanningOutcome,
    SearchPlanningResult,
)
from award_agent.search_planning.contracts import (
    DateBasis,
    DateEnvelope,
    ResultValidationKind,
    ResultValidationObligation,
)
from award_agent.search_planning.gateway_discovery import (
    GatewayDiscoveryOutcome,
    GatewayMarketCoverage,
)
from award_agent.search_planning.policy import PlanningPolicy


def test_compilation_policy_defaults_cover_the_complete_maximum_baseline() -> None:
    policy = PlanningPolicy()

    assert policy.policy_version == "search-planning-compilation-v1"
    assert policy.max_input_window_days == 31
    assert policy.max_mandatory_endpoint_pairs == 100
    assert policy.max_supplemental_relationship_bundles == 24
    assert policy.max_unique_logical_queries == 128
    assert policy.max_query_date_days == 4000
    assert policy.strategy_type_priority == (
        "origin_access",
        "destination_access",
        "scoped_hub",
    )
    assert policy.max_query_date_days >= (
        policy.max_mandatory_endpoint_pairs * policy.max_input_window_days
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"max_unique_logical_queries": 99},
        {"max_query_date_days": 3099},
        {
            "strategy_type_priority": (
                "scoped_hub",
                "origin_access",
                "destination_access",
            )
        },
    ],
)
def test_compilation_policy_rejects_an_internally_incoherent_baseline(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        PlanningPolicy(**changes)


def test_compilation_budget_receipt_recomputes_observed_accounting() -> None:
    receipt = CompilationBudgetReceipt(
        kind=CompilationBudgetKind.UNIQUE_LOGICAL_QUERIES,
        limit=128,
        mandatory_reserved=100,
        supplemental_admitted=28,
        shared_reused=4,
        observed=128,
        disposition="within_limit",
    )

    assert receipt.observed == 128
    with pytest.raises(ValidationError):
        receipt.model_copy(update={"observed": 127}).__class__.model_validate(
            receipt.model_copy(update={"observed": 127}).model_dump()
        )


def test_coverage_requires_complete_accounting_of_every_accepted_relationship() -> None:
    valid = CompilationCoverage(
        mandatory_required_pairs=2,
        mandatory_covered_pairs=2,
        mandatory_complete=True,
        accepted_relationships=4,
        admitted_relationships=1,
        omitted_budget_relationships=1,
        suppressed_positioning_refusal_relationships=1,
        unsupported_rule_relationships=1,
        discovery_outcome=GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE,
        market_coverage=GatewayMarketCoverage.CANDIDATE_MAPPING_GAPS,
    )

    assert valid.accepted_relationships == 4
    with pytest.raises(ValidationError):
        CompilationCoverage.model_validate(
            {**valid.model_dump(), "unsupported_rule_relationships": 0}
        )


def test_logical_query_refuses_route_evidenced_component_validation() -> None:
    with pytest.raises(ValidationError):
        LogicalAwardQuery(
            query_id="logical-award:" + "a" * 64,
            origin_airport_fact_id="airport:SFO",
            destination_airport_fact_id="airport:NRT",
            date_envelope=DateEnvelope(
                start=date(2026, 10, 1),
                end=date(2026, 10, 2),
                basis=DateBasis.FIRST_ORIGIN_AIRPORT_LOCAL,
                timezone="America/Los_Angeles",
                effective_window_precision="window",
            ),
            result_validation_obligations=(
                ResultValidationObligation(
                    kind=ResultValidationKind.EXACT_PHYSICAL_COMPONENT_STRUCTURE,
                    expected_origin_airport_fact_id="airport:SFO",
                    expected_destination_airport_fact_id="airport:NRT",
                ),
            ),
        )


def test_no_plan_outcomes_are_explicit_and_success_requires_a_plan() -> None:
    result = SearchPlanningResult(outcome=SearchPlanningOutcome.EVIDENCE_FAILURE)
    assert result.plan is None

    with pytest.raises(ValidationError):
        SearchPlanningResult(outcome=SearchPlanningOutcome.PLANNED)
