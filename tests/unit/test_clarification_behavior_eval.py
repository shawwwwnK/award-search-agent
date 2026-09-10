"""Property-oriented checks for disclosed ADR 0014 typed semantic cases."""

from award_agent.evaluation.clarification_semantic_guardrails import (
    preflight_clarification_semantic_guardrail_cases,
)


def test_disclosed_cases_cover_safety_and_accepting_metamorphic_families() -> None:
    cases = preflight_clarification_semantic_guardrail_cases()
    families = {item["family"] for item in cases}

    assert families == {
        "schema_span_grounding",
        "authority_and_state",
        "temporal_compilation",
        "accepting_provenance",
        "reduction_and_session",
        "composer_and_privacy",
        "static_boundary",
    }


def test_disclosed_cases_do_not_specify_natural_language_meaning() -> None:
    cases = preflight_clarification_semantic_guardrail_cases()

    assert all("text" not in item and "fragment" not in item for item in cases)
    assert all(item["evidence"].startswith("opaque-") for item in cases)
    assert all("check" in item for item in cases)
