from pathlib import Path

import yaml

from award_agent.cli.intent_eval import _load_ready_scenarios
from award_agent.intent.evidence_eval import compile_evidence_expectations


def test_all_intent_eval_cases_have_executable_expectations() -> None:
    path = Path("evals/intent/cases.yaml")
    payload = yaml.safe_load(path.read_text())
    scenarios = payload["scenarios"]

    assert len(scenarios) == 138
    assert len({scenario["id"] for scenario in scenarios}) == len(scenarios)
    assert all("clarification" in scenario["expected"] for scenario in scenarios)

    ready_scenarios = [scenario for scenario in scenarios if scenario.get("status") == "ready"]
    candidate_scenarios = [scenario for scenario in scenarios if "status" not in scenario]

    assert len(ready_scenarios) == 16
    assert len(candidate_scenarios) == 122
    assert all("layer" in scenario for scenario in candidate_scenarios)
    assert all(
        scenario.get("evaluator", {}).get("type") in {"exact", "invariant", "repeated_live_run"}
        for scenario in candidate_scenarios
    )


def test_ready_location_aliases_are_explicit_nonempty_string_lists() -> None:
    payload = yaml.safe_load(Path("evals/intent/cases.yaml").read_text())
    ready_scenarios = [
        scenario for scenario in payload["scenarios"] if scenario.get("status") == "ready"
    ]

    aliased_locations = []
    for scenario in ready_scenarios:
        expected = scenario["expected"]
        for field in ("origin", "destination"):
            location = expected.get(field)
            if isinstance(location, dict) and "accepted_values" in location:
                aliased_locations.append(location)

    assert aliased_locations
    assert all(
        isinstance(location["accepted_values"], list)
        and location["accepted_values"]
        and all(isinstance(value, str) and value for value in location["accepted_values"])
        and isinstance(location.get("raw_text"), str)
        and location["raw_text"]
        for location in aliased_locations
    )


def test_ready_scenarios_compile_claim_level_evidence_expectations() -> None:
    scenarios = _load_ready_scenarios(Path("evals/intent/cases.yaml"))
    labor_day = next(
        scenario for scenario in scenarios if scenario["id"] == "labor_day_thursday_flexibility"
    )

    expected = labor_day["expected"]
    assert "temporal_phrases" not in expected
    compiled = compile_evidence_expectations(
        labor_day["input"].strip(),
        expected["evidence_expectations"],
    )

    assert {item.claim_id.value for item in compiled} == {
        "departure_anchor",
        "departure_period",
        "approximate_duration",
        "alternate_departure_day",
    }
    assert all(
        span.text == labor_day["input"].strip()[span.start : span.end]
        for item in compiled
        for span in [
            *item.allowed_envelopes,
            *item.required_all,
            *item.preferred_spans,
            *(fragment for group in item.required_any_groups for fragment in group),
        ]
    )


def test_ready_golden_set_separates_literal_semantics_from_calendar_outputs() -> None:
    scenarios = {
        scenario["id"]: scenario
        for scenario in _load_ready_scenarios(Path("evals/intent/cases.yaml"))
    }

    next_month = scenarios["adversarial_schema_instruction"]["expected"]
    assert next_month["forbidden_date_anchor_kinds"] == [
        "exact_date",
        "month",
        "holiday",
    ]
    assert next_month["temporal_relations"] == [
        {
            "kind": "relative_calendar_period",
            "target": "departure",
            "reference": {
                "kind": "symbolic_context",
                "key": "context:request_date",
            },
            "direction": "after",
            "unit": "month",
            "ordinal": 1,
            "period_semantics": "whole",
        }
    ]
    assert next_month["departure_window"] == {
        "start": "2026-09-01",
        "end": "2026-09-30",
    }

    exact_weeks = scenarios["whole_month_with_exact_duration"]["expected"]
    assert exact_weeks["literal_duration"] == {
        "stated_minimum_quantity": 2,
        "stated_maximum_quantity": 2,
        "unit": "week",
        "modifier": "exact",
    }
    assert exact_weeks["interpreted_duration"] == {
        "minimum_days": 14,
        "maximum_days": 14,
    }


def test_unsupported_temporal_policies_remain_explicit_in_golden_set() -> None:
    payload = yaml.safe_load(Path("evals/intent/cases.yaml").read_text())
    scenarios = {scenario["id"]: scenario for scenario in payload["scenarios"]}

    first_week = scenarios["approximate_duration"]
    assert first_week["status"] == "ready"
    assert first_week["expected"]["unsupported_temporal_policy"] == "first_week_of_month"
    assert first_week["expected"]["departure_window"] is None
    assert first_week["expected"]["return_window"] is None
    assert first_week["expected"]["clarification"] == {
        "action": "ask",
        "field": "departure",
    }

    next_spring = scenarios["repositioning_allowed"]["expected"]
    assert next_spring["temporal_relations"] == [{"kind": "unresolved", "target": "departure"}]
    assert "departure" in next_spring["unknowns"]

    assert (
        scenarios["p2_couple_weeks_past_thanksgiving_loose_offset"]["contract_status"]
        == "unsupported_pending_loose_offset_vocabulary"
    )
    for scenario_id in (
        "p2_bounded_after_before_dates_nonexclusive_policy",
        "p2_noncontiguous_exact_departure_alternatives",
        "p2_multiple_return_date_alternatives",
        "live_noncontiguous_departure_alternatives",
        "stability_discrete_date_alternatives",
        "metamorphic_alternative_dates_order",
    ):
        assert (
            scenarios[scenario_id]["contract_status"] == "unsupported_pending_relation_composition"
        )


def test_unapproved_calendar_cases_are_marked_deferred_without_rewriting_history() -> None:
    payload = yaml.safe_load(Path("evals/intent/cases.yaml").read_text())
    scenarios = {scenario["id"]: scenario for scenario in payload["scenarios"]}

    expected_markers = {
        "enrich_leap_day_next_valid_occurrence": (
            "deferred_pending_yearless_leap_day_policy",
            "2028-02-29",
        ),
        "enrich_invalid_calendar_date": (
            "deferred_pending_invalid_calendar_date_contract",
            "invalid_calendar_date",
        ),
        "enrich_yearless_month_current_partly_elapsed": (
            "deferred_pending_current_month_clipping_policy",
            "2026-08-29",
        ),
    }
    for scenario_id, (marker, historical_value) in expected_markers.items():
        scenario = scenarios[scenario_id]
        assert scenario["contract_status"] == marker
        assert historical_value in str(scenario["expected"])
