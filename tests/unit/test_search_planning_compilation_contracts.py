"""Focused contract tests for the Milestone 2C replacement boundary."""

from datetime import date

import pytest
from pydantic import ValidationError

from award_agent.search_planning.compilation_contracts import (
    CompilationCoverage,
    CompilerStructuralLimitKind,
    CompilerStructuralLimitReceipt,
    LogicalAwardQuery,
    SearchPlanningOutcome,
    SearchPlanningResult,
    StrategyCompilationIssue,
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
from award_agent.search_planning.planner import _structural_limit_failure
from award_agent.search_planning.policy import PlanningPolicy


def test_compilation_policy_has_only_provider_neutral_all_or_nothing_guards() -> None:
    policy = PlanningPolicy()

    assert policy.policy_version == "search-planning-compilation-v3"
    assert policy.max_structural_endpoint_pairs == 100
    dumped = policy.model_dump()
    assert "max_supported_departure_window_days" not in dumped
    assert "max_supplemental_relationship_bundles" not in dumped
    assert "max_unique_logical_queries" not in dumped
    assert "max_query_date_days" not in dumped
    assert "strategy_type_priority" not in dumped
    assert "max_automatic_group_airports" not in dumped
    assert "hard_max_automatic_group_airports" not in dumped


def test_compilation_policy_rejects_removed_execution_budget_fields() -> None:
    with pytest.raises(ValidationError):
        PlanningPolicy.model_validate({"max_unique_logical_queries": 128})


def test_structural_limit_receipt_binds_classification_and_limit() -> None:
    receipt = CompilerStructuralLimitReceipt(
        kind=CompilerStructuralLimitKind.ENDPOINT_PAIR_CROSS_PRODUCT,
        classification="compiler_structural_safety",
        limit=100,
        observed=100,
        disposition="within_limit",
    )

    assert receipt.observed == 100
    with pytest.raises(ValidationError):
        receipt.model_copy(update={"classification": "supported_request_scope"}).__class__.model_validate(
            receipt.model_copy(update={"classification": "supported_request_scope"}).model_dump()
        )


def test_101_endpoint_pairs_fail_all_or_nothing_with_no_plan() -> None:
    result = _structural_limit_failure(
        CompilerStructuralLimitKind.ENDPOINT_PAIR_CROSS_PRODUCT,
        observed=101,
        limit=100,
    )

    assert result.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert result.plan is None
    assert result.structural_limit_receipts[0].observed == 101
    assert result.structural_limit_receipts[0].classification == (
        "compiler_structural_safety"
    )


def test_coverage_requires_complete_accounting_of_every_accepted_relationship() -> None:
    valid = CompilationCoverage(
        mandatory_required_pairs=2,
        mandatory_covered_pairs=2,
        mandatory_complete=True,
        accepted_relationships=4,
        compiled_relationships=2,
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
    issue = StrategyCompilationIssue(
        code="offline_evidence_failure",
        stage="input",
        severity="evidence_failure",
        message="offline evidence failed",
    )
    result = SearchPlanningResult(
        outcome=SearchPlanningOutcome.EVIDENCE_FAILURE,
        issues=(issue,),
    )
    assert result.plan is None

    with pytest.raises(ValidationError):
        SearchPlanningResult(outcome=SearchPlanningOutcome.PLANNED)
    with pytest.raises(ValidationError, match="outcome and issue severities must agree"):
        SearchPlanningResult(
            outcome=SearchPlanningOutcome.UNPLANNABLE,
            issues=(issue,),
        )
