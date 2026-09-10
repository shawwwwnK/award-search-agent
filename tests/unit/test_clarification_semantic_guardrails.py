"""Hard offline checks for ADR 0014's typed semantic boundary."""

from award_agent.evaluation.clarification_semantic_guardrails import (
    audit_continuation_raw_answer_boundary,
    find_openai_converter_semantic_parser_violations,
    find_raw_answer_semantic_parser_violations,
    run_offline_clarification_semantic_guardrails,
)


def test_semantic_guardrail_gate_passes_without_live_model_access() -> None:
    artifact = run_offline_clarification_semantic_guardrails()

    assert artifact["passed"] is True
    assert [item["id"] for item in artifact["checks"]] == [
        "static_no_raw_answer_parser",
        "schema_and_span_grounding",
        "receiver_repair_unavailability",
        "repair_and_interpretation_pending_safety",
        "set_replace_authorization",
        "temporal_calendar_ranges_and_dependencies",
        "fuzzy_assumption_disclosure",
        "conflict_preservation_sibling_atomicity",
        "immutable_revisions_concurrency_idempotency_ready_policy",
        "composer_coverage_linkage_failure_and_redaction",
    ]
    assert artifact["owner_held_holdout"] == {
        "status": "not_executed",
        "reason": "inaccessible_to_implementation",
    }


def test_raw_answer_parser_audit_covers_the_real_deterministic_boundary() -> None:
    assert audit_continuation_raw_answer_boundary() == ()


def test_raw_answer_parser_audit_rejects_retired_normalizer_imports_and_calls() -> None:
    violations = find_raw_answer_semantic_parser_violations(
        {
            "reducer.py": (
                "from award_agent.clarification.temporal import normalize_temporal_amendment\n"
                "normalize_temporal_amendment(value)\n"
            )
        }
    )

    assert [(item.line, item.detail) for item in violations] == [
        (1, "forbidden semantic import: award_agent.clarification.temporal"),
        (2, "forbidden semantic call: normalize_temporal_amendment"),
    ]


def test_raw_answer_parser_audit_rejects_regex_recovery_hooks() -> None:
    violations = find_raw_answer_semantic_parser_violations(
        {"controller.py": "import re\nre.search('x', answer)\n"}
    )

    assert [(item.line, item.detail) for item in violations] == [
        (1, "forbidden semantic import: re"),
        (2, "forbidden answer-text operation: search"),
    ]


def test_raw_answer_parser_audit_rejects_phrase_processing_hooks() -> None:
    violations = find_raw_answer_semantic_parser_violations(
        {"controller.py": "answer = answer_text.casefold()\n"}
    )

    assert [(item.line, item.detail) for item in violations] == [
        (1, "forbidden answer-text operation: casefold"),
    ]


def test_openai_adapter_audit_allows_only_structural_text_exemptions() -> None:
    assert (
        find_openai_converter_semantic_parser_violations(
            """
class OpenAIClarificationInterpreterConfig:
    def __post_init__(self):
        return self.model.strip()

def _span(text, quote, cursor):
    return text.find(quote, cursor)

def _is_provider_schema_rejection(error):
    return str(error).casefold()
"""
        )
        == ()
    )


def test_openai_adapter_audit_covers_non_converter_helpers() -> None:
    violations = find_openai_converter_semantic_parser_violations(
        """
def _helper(text):
    return text.casefold()

def _another_helper(text):
    return text.strip()
"""
    )
    assert [(item.line, item.detail) for item in violations] == [
        (3, "forbidden converter text operation: casefold"),
        (6, "forbidden converter text operation: strip"),
    ]
