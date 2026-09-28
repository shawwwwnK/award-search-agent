"""Provider replay integrity and unknown-state contract gates."""

from datetime import UTC, date, datetime

import pytest
from pydantic import JsonValue, ValidationError

from award_agent.providers.contracts import (
    CoverageReceipt,
    CoverageUnit,
    EvidenceRef,
    ExecutionBinding,
    ExecutionPolicy,
    ProviderCapability,
    ProviderExecutionPlan,
    ProviderObservation,
    ProviderQuery,
    ProviderResultSet,
    RawField,
    ResourceBudget,
    ResourceUsage,
    TransportReceipt,
    content_digest,
)


def execution_plan() -> ProviderExecutionPlan:
    budget = ResourceBudget(
        requests=4, attempts=4, pages=4, detail_calls=0, rows=100, bytes=10000,
        elapsed_seconds=20,
    )
    policy = ExecutionPolicy(
        version="synthetic-test-v1", award_budget=budget, cash_budget=budget,
        budget_evidence=("synthetic contract test; not live acceptance",),
        direct_cash_samples=1, positioning_cash_samples=0, page_size=100,
        request_timeout_seconds=5,
    )
    award = ProviderCapability(
        provider="seats_aero", version="test", backend="test", operation="search",
    )
    cash = ProviderCapability(
        provider="gfly", version="test", backend="test", operation="search",
    )
    return ProviderExecutionPlan(
        binding=ExecutionBinding(
            run_id="test", session_id="session", revision=0, effective_request_digest="a" * 64,
            compilation_binding_digest="b" * 64, plan_digest="c" * 64,
            policy_digest=content_digest(policy), award_capability_digest=content_digest(award),
            cash_capability_digest=content_digest(cash),
        ),
        policy=policy, award_capability=award, cash_capability=cash,
        queries=(ProviderQuery(
            query_id="physical", provider="seats_aero", role="mandatory_award",
            origins=("SFO",), destinations=("BKK",), start_date=date(2027, 5, 1),
            end_date=date(2027, 5, 1), travelers=2, logical_query_ids=("logical",),
        ),),
        coverage_units=(CoverageUnit(
            unit_id="logical", kind="logical_query", logical_query_ids=("logical",),
        ),),
    )


def test_raw_field_absence_null_unknown_and_zero_are_distinct() -> None:
    values = (
        RawField.from_mapping({}, "seats"),
        RawField.from_mapping({"seats": None}, "seats"),
        RawField(state="unknown", source_field="seats"),
        RawField.from_mapping({"seats": 0}, "seats"),
    )
    assert [value.state for value in values] == ["absent", "null", "unknown", "value"]
    assert values[-1].value == 0
    assert len({content_digest(value) for value in values}) == 4
    with pytest.raises(ValidationError, match="supplied null"):
        RawField(state="value")


def test_raw_nested_values_are_copy_isolated() -> None:
    source: dict[str, JsonValue] = {"unknown_shape": [1]}
    value = RawField(state="value", value=source)
    source["unknown_shape"] = [1, 2]
    exported = value.value
    assert isinstance(exported, dict)
    exported["changed"] = True
    assert value.value == {"unknown_shape": [1]}


def test_policy_identity_revalidated_after_serialization() -> None:
    plan = execution_plan()
    assert ProviderExecutionPlan.model_validate_json(plan.model_dump_json()) == plan
    payload = plan.model_dump(mode="json")
    payload["policy"]["direct_cash_samples"] = 3
    with pytest.raises(ValidationError, match="policy digest"):
        ProviderExecutionPlan.model_validate(payload)


def test_complete_coverage_required_even_without_attempts() -> None:
    plan = execution_plan()
    with pytest.raises(ValidationError, match="exactly one"):
        ProviderResultSet(execution_plan=plan, status="partial")
    result = ProviderResultSet(
        execution_plan=plan, status="partial",
        coverage=(CoverageReceipt(unit_id="logical", status="omitted", reason="budget"),),
    )
    assert ProviderResultSet.model_validate_json(result.model_dump_json()) == result


def test_partial_stream_cannot_be_called_empty() -> None:
    with pytest.raises(ValidationError, match="complete pair stream"):
        CoverageReceipt(
            unit_id="logical", status="empty", pair_coverage="empty", reason="no rows",
        )


def test_evidence_path_and_timestamp_are_bounded() -> None:
    with pytest.raises(ValidationError, match="evidence root"):
        EvidenceRef(
            sha256="a" * 64, relative_path="../private.json", retrieved_at=datetime.now(UTC),
        )
    with pytest.raises(ValidationError, match="timezone"):
        EvidenceRef(
            sha256="a" * 64, relative_path="safe.json",
            retrieved_at=datetime(2026, 1, 1, tzinfo=None),  # noqa: DTZ001 -- invalid input gate
        )


def test_unaccepted_capability_cannot_claim_rectangle_acceptance() -> None:
    with pytest.raises(ValidationError, match="comparison evidence"):
        ProviderCapability(
            provider="seats_aero", version="test", backend="test", operation="search",
            rectangle_batching_accepted=True,
        )


def test_transport_usage_must_be_reconciled() -> None:
    evidence = EvidenceRef(
        sha256="a" * 64, relative_path="test.json", retrieved_at=datetime.now(UTC),
        synthetic=True,
    )
    receipt = TransportReceipt(
        transport_id="transport", query_id="physical", provider="seats_aero",
        attempt=1, page=1, status="empty", evidence=evidence, elapsed_seconds=1,
        byte_count=20, returned_rows=0,
    )
    kwargs: dict[str, object] = {
        "execution_plan": execution_plan(), "status": "completed", "transport_receipts": (receipt,),
        "coverage": (CoverageReceipt(
            unit_id="logical", status="empty", query_ids=("physical",),
            transport_ids=("transport",), reason="complete singleton stream", stream_complete=True,
            pair_coverage="empty",
        ),),
    }
    with pytest.raises(ValidationError, match="resource usage"):
        ProviderResultSet.model_validate(kwargs)
    result = ProviderResultSet.model_validate({
        **kwargs, "award_usage": ResourceUsage(
            requests=1, attempts=1, pages=1, bytes=20, elapsed_seconds=1,
        ),
    })
    assert result.award_usage.requests == 1


def test_dangling_logical_use_attribution_fails_closed() -> None:
    payload = execution_plan().model_dump(mode="json")
    payload["queries"][0]["logical_use_ids"] = ["made-up-use"]
    with pytest.raises(ValidationError, match="logical use"):
        ProviderExecutionPlan.model_validate(payload)


def test_observations_cannot_appear_without_transport_evidence() -> None:
    evidence = EvidenceRef(
        sha256="a" * 64, relative_path="test.json", retrieved_at=datetime.now(UTC),
        synthetic=True,
    )
    observation = ProviderObservation(
        observation_id="orphan", provider="seats_aero", backend="test", provider_version="test",
        kind="award_summary", query_id="physical", logical_query_ids=("logical",),
        origin="SFO", destination="BKK", retrieved_at=evidence.retrieved_at,
        requested_travelers=2, evidence=(evidence,),
    )
    with pytest.raises(ValidationError, match="attributed to a transport"):
        ProviderResultSet(
            execution_plan=execution_plan(), status="partial", observations=(observation,),
            coverage=(CoverageReceipt(unit_id="logical", status="omitted", reason="budget"),),
        )


def test_coverage_cannot_claim_an_unrelated_existing_physical_query() -> None:
    payload = execution_plan().model_dump(mode="json")
    second_query = dict(payload["queries"][0])
    second_query.update(query_id="other-physical", logical_query_ids=["other-logical"])
    payload["queries"].append(second_query)
    payload["coverage_units"].append({
        "unit_id": "other-logical", "kind": "logical_query", "logical_query_ids": ["other-logical"],
    })
    plan = ProviderExecutionPlan.model_validate(payload)
    with pytest.raises(ValidationError, match="unrelated to the logical graph unit"):
        ProviderResultSet(
            execution_plan=plan, status="partial",
            coverage=(
                CoverageReceipt(
                    unit_id="logical", status="omitted", query_ids=("other-physical",), reason="budget",
                ),
                CoverageReceipt(unit_id="other-logical", status="omitted", reason="budget"),
            ),
        )


def test_reconciled_usage_cannot_hide_an_attempt_after_exhaustion() -> None:
    evidence = EvidenceRef(
        sha256="a" * 64, relative_path="test.json", retrieved_at=datetime.now(UTC),
        synthetic=True,
    )
    receipts = tuple(TransportReceipt(
        transport_id=f"page-{page}", query_id="physical", provider="seats_aero",
        attempt=page, page=page, status="completed", evidence=evidence,
        elapsed_seconds=1, byte_count=20, returned_rows=100 if page == 1 else 0,
    ) for page in (1, 2))
    with pytest.raises(ValidationError, match="after its resource budget was exhausted"):
        ProviderResultSet(
            execution_plan=execution_plan(), status="partial", transport_receipts=receipts,
            coverage=(CoverageReceipt(
                unit_id="logical", status="partial", reason="overrun",
                query_ids=("physical",), transport_ids=("page-1", "page-2"),
                pair_coverage="unknown",
            ),),
            award_usage=ResourceUsage(
                requests=1, attempts=2, pages=2, rows=100, bytes=40, elapsed_seconds=2,
            ),
        )


def test_success_coverage_cannot_override_a_failed_transport() -> None:
    evidence = EvidenceRef(
        sha256="a" * 64, relative_path="test.json", retrieved_at=datetime.now(UTC),
        synthetic=True,
    )
    receipt = TransportReceipt(
        transport_id="failed", query_id="physical", provider="seats_aero",
        attempt=1, page=1, status="failed", evidence=evidence,
        elapsed_seconds=1, byte_count=20, returned_rows=0,
    )
    with pytest.raises(ValidationError, match="successful complete transport streams"):
        ProviderResultSet(
            execution_plan=execution_plan(), status="completed", transport_receipts=(receipt,),
            coverage=(CoverageReceipt(
                unit_id="logical", status="empty", query_ids=("physical",),
                transport_ids=("failed",), reason="forged success", stream_complete=True,
                pair_coverage="empty",
            ),),
            award_usage=ResourceUsage(
                requests=1, attempts=1, pages=1, bytes=20, elapsed_seconds=1,
            ),
        )
