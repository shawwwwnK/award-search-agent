import inspect
import json
from datetime import date
from types import SimpleNamespace

import pytest

from award_agent.clarification.controller import ClarificationCommandError, start_clarification
from award_agent.domain import Holiday, LocationKind, RawRequest, RequestContext, SearchMode
from award_agent.intent.openai_interpreter import (
    OpenAISemanticIntentConfig,
    OpenAISemanticIntentError,
    OpenAISemanticIntentInterpreter,
    WireCabin,
    WireCalendarPeriodDeparture,
    WireDestination,
    WireIntentProposal,
    WireLiteralSingleDeparture,
    WireMode,
    WireOrigin,
    WireTravelers,
    WireUnresolved,
)
from award_agent.intent.semantic import (
    SemanticFact,
    SemanticIntentInput,
    SemanticIntentProposal,
    SemanticScopeNotice,
    SemanticTemporalFact,
    SemanticUnresolved,
    SemanticValidationIssue,
)
from award_agent.intent.workflow import understand_request
from award_agent.observability.llm_trace import response_schema_sha256


class Holidays:
    def holiday_date(self, _holiday: Holiday, year: int) -> date:
        # Thanksgiving 2026 is Nov 26; this is deliberately a deterministic test receipt.
        return date(year, 11, 26)


class Interpreter:
    def __init__(self, proposal: SemanticIntentProposal) -> None:
        self.proposal = proposal

    def interpret(self, _input: object) -> SemanticIntentProposal:
        return self.proposal


def _request(text: str) -> RawRequest:
    return RawRequest(
        text=text, context=RequestContext(reference_date=date(2026, 1, 1), timezone="UTC")
    )


def _base_facts() -> tuple[SemanticFact, ...]:
    return (
        SemanticFact(
            target="origin", quote="SFO", location_kind=LocationKind.AIRPORT, location_value="sfo"
        ),
        SemanticFact(
            target="destination",
            quote="Tokyo",
            location_kind=LocationKind.CITY,
            location_value="Tokyo",
        ),
        SemanticFact(target="travelers", quote="two", travelers=2),
        SemanticFact(target="search_mode", quote="award", search_mode=SearchMode.AWARD),
    )


def test_semantic_plan_evaluates_friday_after_thanksgiving_without_phrase_parser() -> None:
    request = _request("two award seats SFO to Tokyo on the Fridai after Thanskgiving")
    proposal = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="departure",
                target="departure",
                quote="Fridai after Thanskgiving",
                operation="recurring_interval",
                anchor_kind="holiday",
                anchor_holiday="thanksgiving",
                weekday=4,
                strictly_after=True,
            ),
        ),
    )
    result = understand_request(request, Interpreter(proposal), Holidays())

    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.start == date(2026, 11, 27)
    assert result.clarification.action.value == "none"


def test_unbounded_semantic_timing_defers_to_departure_clarification() -> None:
    request = _request("two award seats SFO to Tokyo whenever works")
    proposal = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="departure",
                target="departure",
                quote="whenever works",
                operation="unresolved",
                reason="The timing is unbounded.",
            ),
        ),
    )

    result = understand_request(request, Interpreter(proposal))

    assert result.clarification.field == "departure"
    assert any(
        item.field == "departure" and item.reason.value == "unresolved"
        for item in result.parsed_request.unknowns
    )


def test_yearless_literal_recheck_repairs_to_next_occurrence_ready() -> None:
    first = SemanticIntentProposal(
        facts=_base_facts(),
        unresolved=(
            SemanticUnresolved(
                component_id="departure",
                field="departure",
                quote="October 5",
                reason="calendar operation needs recheck",
                operation_recheck=True,
            ),
        ),
    )
    repaired = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="departure",
                component_id="departure",
                target="departure",
                quote="October 5",
                operation="literal_interval",
                start_month=10,
                start_day=5,
            ),
        ),
    )

    class Repairing(Interpreter):
        def __init__(self) -> None:
            super().__init__(first)
            self.calls = 0

        def repair(self, _input: object, **_kwargs: object) -> SemanticIntentProposal:
            self.calls += 1
            return repaired

    interpreter = Repairing()
    result = understand_request(_request("two award seats SFO to Tokyo October 5"), interpreter)
    assert interpreter.calls == 1
    assert result.clarification is not None and result.clarification.action.value == "none"
    assert result.parsed_request is not None
    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.start == date(2026, 10, 5)


def test_yearless_literal_recheck_twice_becomes_completed_clarification() -> None:
    first = SemanticIntentProposal(
        facts=_base_facts(),
        unresolved=(SemanticUnresolved(component_id="departure", field="departure", quote="October 5", reason="recheck", operation_recheck=True),),
    )

    class Repairing(Interpreter):
        def __init__(self) -> None:
            super().__init__(first)
            self.calls = 0

        def repair(self, _input: object, **_kwargs: object) -> SemanticIntentProposal:
            self.calls += 1
            return first

    interpreter = Repairing()
    result = understand_request(_request("two award seats SFO to Tokyo October 5"), interpreter)
    assert interpreter.calls == 1
    assert result.outcome.value == "completed"
    assert result.clarification is not None and result.clarification.field == "departure"


def test_explicit_literal_year_is_grounded_and_not_next_occurrence() -> None:
    proposal = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(SemanticTemporalFact(fact_id="departure", target="departure", quote="October 5 2027", operation="literal_interval", start_year=2027, start_month=10, start_day=5),),
    )
    result = understand_request(_request("two award seats SFO to Tokyo October 5 2027"), Interpreter(proposal))
    assert result.parsed_request is not None
    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.start == date(2027, 10, 5)


def test_yearless_literal_prompt_and_wire_schema_make_zero_year_explicit() -> None:
    from award_agent.intent.openai_interpreter import _INSTRUCTIONS

    assert "start_year 0" in _INSTRUCTIONS
    schema = WireLiteralSingleDeparture.model_json_schema()
    assert "next occurrence" in schema["properties"]["start_year"]["description"]
    assert WireUnresolved.model_json_schema()["properties"]["operation_recheck"]["type"] == "boolean"


def test_return_duration_and_cash_only_are_scope_notices_not_active_state() -> None:
    request = _request("two cash seats SFO to Tokyo June 2 returning June 9 for 7 days")
    proposal = SemanticIntentProposal(
        facts=(
            SemanticFact(
                target="origin",
                quote="SFO",
                location_kind=LocationKind.AIRPORT,
                location_value="SFO",
            ),
            SemanticFact(
                target="destination",
                quote="Tokyo",
                location_kind=LocationKind.CITY,
                location_value="Tokyo",
            ),
            SemanticFact(target="travelers", quote="two", travelers=2),
            SemanticFact(target="search_mode", quote="cash", search_mode=SearchMode.CASH),
        ),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="out",
                target="departure",
                quote="June 2",
                operation="literal_interval",
                start_month=6,
                start_day=2,
            ),
            SemanticTemporalFact(
                fact_id="back",
                target="return",
                quote="June 9",
                operation="literal_interval",
                start_month=6,
                start_day=9,
            ),
            SemanticTemporalFact(
                fact_id="duration",
                target="duration",
                quote="7 days",
                operation="unresolved",
                reason="Trip duration",
            ),
        ),
    )
    result = understand_request(request, Interpreter(proposal))

    assert result.clarification.action.value == "unsupported"
    assert {item.code.value for item in result.parsed_request.unsupported_request_parts} == {
        "return_or_duration_not_supported",
        "cash_only_not_supported",
    }
    assert result.parsed_request.temporal_extraction is not None
    assert all(
        item.applies_to.value == "departure"
        for item in result.parsed_request.temporal_extraction.temporal_phrases
    )
    assert all("return" not in item.field for item in result.parsed_request.unknowns)


def test_active_workflow_has_no_scanner_or_selector_dependency() -> None:
    source = inspect.getsource(__import__("award_agent.intent.workflow", fromlist=["*"]))
    assert "scan_temporal_request" not in source
    assert "build_temporal_candidates" not in source
    assert "select_candidates" not in source


def test_model_failure_is_typed_pending_not_a_fake_user_clarification() -> None:
    class Broken:
        def interpret(self, _input: object) -> SemanticIntentProposal:
            raise RuntimeError("provider unavailable")

    result = understand_request(_request("SFO to Tokyo"), Broken())

    assert result.outcome.value == "pending_retryable"
    assert result.pending_detail is not None
    assert result.parsed_request is None
    assert result.clarification is None
    try:
        start_clarification(result)
    except ClarificationCommandError:
        pass
    else:  # pragma: no cover
        raise AssertionError("pending result must not start clarification")


def test_blank_request_is_completed_missing_clarification_without_model_call() -> None:
    class MustNotCall:
        def interpret(self, _input: object) -> SemanticIntentProposal:
            raise AssertionError("blank input must not reach model")

    result = understand_request(_request(""), MustNotCall())

    assert result.outcome.value == "completed"
    assert result.clarification.field == "origin"


def test_scope_notice_short_circuits_bad_unrelated_outbound_plan() -> None:
    request = _request("SFO to Tokyo June 2 and return June 9")
    malformed = SemanticTemporalFact.model_construct(
        fact_id="out", target="departure", quote="June 2", operation="literal_interval"
    )
    proposal = SemanticIntentProposal.model_construct(
        facts=(),
        temporal_facts=(malformed,),
        unresolved=(),
        scope_notices=(SemanticScopeNotice(kind="return", quote="June 9"),),
    )

    result = understand_request(request, Interpreter(proposal))

    assert result.outcome.value == "completed"
    assert result.clarification.action.value == "unsupported"
    assert result.parsed_request.unsupported_request_parts[0].evidence[0].span.text == "June 9"
    assert result.parsed_request.temporal_evidence == []


def test_grounded_scope_survives_ungrounded_outbound_quote() -> None:
    request = _request("SFO to Tokyo return June 9")
    bad_outbound = SemanticTemporalFact.model_construct(
        fact_id="out", target="departure", quote="not in request", operation="literal_interval"
    )
    proposal = SemanticIntentProposal.model_construct(
        facts=(),
        temporal_facts=(bad_outbound,),
        unresolved=(),
        scope_notices=(SemanticScopeNotice(kind="return", quote="June 9"),),
    )

    result = understand_request(request, Interpreter(proposal))

    assert result.outcome.value == "completed"
    assert result.clarification is not None and result.clarification.action.value == "unsupported"
    assert result.parsed_request is not None and result.parsed_request.temporal_evidence == []


def test_scope_notice_preserves_valid_outbound_siblings() -> None:
    request = _request("two award seats SFO to Tokyo June 2 and return June 9")
    proposal = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="out",
                target="departure",
                quote="June 2",
                operation="literal_interval",
                start_month=6,
                start_day=2,
            ),
        ),
        scope_notices=(SemanticScopeNotice(kind="return", quote="June 9"),),
    )
    result = understand_request(request, Interpreter(proposal))

    assert result.parsed_request is not None
    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.origins[0].value == "SFO"
    assert result.clarification is not None and result.clarification.action.value == "unsupported"


def test_grounded_scope_notice_dominates_ungrounded_mode_sibling() -> None:
    proposal = SemanticIntentProposal(
        facts=(
            SemanticFact(
                component_id="bad-mode",
                target="search_mode",
                quote="not in request",
                search_mode="cash",
            ),
        ),
        scope_notices=(SemanticScopeNotice(component_id="return", kind="return", quote="return June 9"),),
    )
    result = understand_request(
        _request("SFO to Tokyo return June 9"), Interpreter(proposal)
    )
    assert result.outcome.value == "completed"
    assert result.clarification is not None
    assert result.clarification.action.value == "unsupported"
    assert result.parsed_request is not None
    assert result.parsed_request.unsupported_request_parts[0].raw_text == "return June 9"


def test_scope_outcome_drops_hallucinated_outbound_year_without_hiding_return_notice() -> None:
    proposal = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="outbound",
                target="departure",
                quote="October 5",
                operation="literal_interval",
                start_year=2027,
                start_month=10,
                start_day=5,
            ),
        ),
        scope_notices=(SemanticScopeNotice(kind="return", quote="return October 12"),),
    )
    result = understand_request(
        _request("two award seats SFO to Tokyo October 5 return October 12"), Interpreter(proposal)
    )
    assert result.outcome.value == "completed"
    assert result.clarification is not None and result.clarification.action.value == "unsupported"
    assert result.parsed_request is not None
    assert result.parsed_request.departure_window is None
    assert result.parsed_request.unsupported_request_parts[0].raw_text == "return October 12"


def test_invalid_quote_repair_receives_typed_issue_and_preserves_repaired_fact() -> None:
    request = _request("two award seats SFO to Tokyo in October")
    bad = SemanticIntentProposal(
        facts=(
            SemanticFact(
                target="origin",
                quote="not in request",
                location_kind="airport",
                location_value="SFO",
            ),
        )
    )
    repaired = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="october",
                target="departure",
                quote="October",
                operation="calendar_period",
                period_month=10,
                period_slice="whole",
            ),
        ),
    )

    class Repairing(Interpreter):
        def __init__(self) -> None:
            super().__init__(bad)
            self.errors = ()

        def repair(
            self, _input: object, *, proposal: SemanticIntentProposal, errors: tuple[object, ...]
        ) -> SemanticIntentProposal:
            assert proposal is bad
            assert errors and errors[0].code == "semantic_proposal_validation_failed"
            self.errors = errors
            return repaired

    interpreter = Repairing()
    result = understand_request(request, interpreter)

    assert interpreter.errors
    assert result.outcome.value == "completed"
    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.calendar_receipts[0].operation == "calendar_period"


def test_holiday_provider_failure_is_typed_pending_without_leaking_provider_detail() -> None:
    class FailingHolidays:
        def holiday_date(self, _holiday: Holiday, _year: int) -> date:
            raise RuntimeError("private provider response: bad gateway")

    request = _request("two award seats SFO to Tokyo Friday after Thanksgiving")
    proposal = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="departure",
                target="departure",
                quote="Friday after Thanksgiving",
                operation="recurring_interval",
                anchor_kind="holiday",
                anchor_holiday="thanksgiving",
                weekday=4,
                strictly_after=True,
            ),
        ),
    )

    class MustNotRepair(Interpreter):
        def repair(self, *_args: object, **_kwargs: object) -> SemanticIntentProposal:
            raise AssertionError("operational provider failure must not spend semantic repair")

    result = understand_request(request, MustNotRepair(proposal), FailingHolidays())

    assert result.outcome.value == "pending_retryable"
    assert "gateway" not in (result.pending_detail or "")


def test_ungrounded_temporal_quote_gets_one_repair_then_completed_clarification() -> None:
    proposal = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="departure",
                target="departure",
                quote="made up timing",
                operation="literal_interval",
                start_month=10,
                start_day=2,
            ),
        ),
    )

    class ExhaustedRepair(Interpreter):
        def __init__(self) -> None:
            super().__init__(proposal)
            self.calls = 0

        def repair(self, _input: object, **_kwargs: object) -> SemanticIntentProposal:
            self.calls += 1
            return proposal

    interpreter = ExhaustedRepair()
    result = understand_request(_request("two award seats SFO to Tokyo October"), interpreter)

    assert interpreter.calls == 1
    assert result.outcome.value == "completed"
    assert result.parsed_request is not None
    assert result.clarification is not None and result.clarification.field == "departure"


def test_explicit_year_not_in_quote_degrades_to_completed_clarification() -> None:
    proposal = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="departure",
                target="departure",
                quote="October",
                operation="calendar_period",
                period_month=10,
                period_year=2030,
                period_slice="whole",
            ),
        ),
    )
    result = understand_request(
        _request("two award seats SFO to Tokyo October"), Interpreter(proposal)
    )

    assert result.outcome.value == "completed"
    assert result.clarification is not None and result.clarification.field == "departure"


def test_next_month_is_request_relative_period_without_model_calculated_date() -> None:
    proposal = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="next-month",
                target="departure",
                quote="next month",
                operation="calendar_period",
                period_offset_months=1,
                period_slice="whole",
            ),
        ),
    )
    result = understand_request(
        _request("two award seats SFO to Tokyo next month"), Interpreter(proposal)
    )

    assert result.parsed_request is not None
    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.start == date(2026, 2, 1)


def test_wire_shape_repair_makes_reasonable_sfo_bkk_request_ready_and_preserves_siblings() -> None:
    """A provider-safe but internally malformed first DTO is not user-visible pending."""
    first = WireIntentProposal(
        origins=(WireOrigin(component_id="origin", quote="SFO", location_kind="airport", location_value="SFO"),),
        destinations=(WireDestination(component_id="destination", quote="BKK", location_kind="airport", location_value="BKK"),),
        travelers=(WireTravelers(component_id="travelers", quote="two", travelers=2),),
        cabins=(WireCabin(component_id="cabin", quote="business", cabin="business"),),
        modes=(WireMode(component_id="award", quote="award", search_mode="award"),),
        # Inactive offset in a named month is a structural conversion fault,
        # not a raw-language failure.
        calendar_period_departures=(WireCalendarPeriodDeparture(component_id="departure", quote="October 5", basis="named_month", period_month=10, period_offset_months=1, period_slice="whole"),),
    )
    repaired = WireIntentProposal(
        literal_single_departures=(WireLiteralSingleDeparture(component_id="departure", quote="October 5", start_month=10, start_day=5),),
    )

    class Responses:
        def __init__(self) -> None:
            self.outputs = iter((first, repaired))
            self.calls = 0

        def parse(self, **_kwargs: object) -> SimpleNamespace:
            self.calls += 1
            return SimpleNamespace(output_parsed=next(self.outputs), usage=None)

    responses = Responses()
    interpreter = OpenAISemanticIntentInterpreter(
        OpenAISemanticIntentConfig(model="test"), client=SimpleNamespace(responses=responses)
    )
    result = understand_request(
        _request("Find two business award seats from SFO to BKK on October 5"), interpreter
    )

    assert responses.calls == 2
    assert result.outcome.value == "completed"
    assert result.parsed_request is not None
    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.start == date(2026, 10, 5)
    assert result.parsed_request.origins[0].value == "SFO"
    assert result.parsed_request.destinations[0].value == "BKK"
    assert result.parsed_request.travelers == 2
    assert result.clarification is not None and result.clarification.action.value == "none"


def test_wire_contract_has_no_nullable_or_union_shape_matrix() -> None:
    schema = json.dumps(WireIntentProposal.model_json_schema())
    assert "oneOf" not in schema
    assert "anyOf" not in schema
    assert '"type": "null"' not in schema


def test_sdk_strict_wire_schema_requires_yearless_literal_fields() -> None:
    from openai.lib._parsing import type_to_response_format_param

    strict = type_to_response_format_param(WireIntentProposal)["json_schema"]["schema"]
    assert "literal_single_departures" in strict["required"]
    literal_required = strict["$defs"]["WireLiteralSingleDeparture"]["required"]
    assert {"start_year", "start_month", "start_day"} <= set(literal_required)


def test_missing_provider_parsed_output_uses_one_representation_repair() -> None:
    repaired = WireIntentProposal(
        origins=(WireOrigin(component_id="origin", quote="SFO", location_kind="airport", location_value="SFO"),),
        destinations=(WireDestination(component_id="destination", quote="BKK", location_kind="airport", location_value="BKK"),),
        travelers=(WireTravelers(component_id="travelers", quote="two", travelers=2),),
        cabins=(WireCabin(component_id="cabin", quote="business", cabin="business"),),
        modes=(WireMode(component_id="award", quote="award", search_mode="award"),),
        literal_single_departures=(WireLiteralSingleDeparture(component_id="departure", quote="October 5", start_month=10, start_day=5),),
    )

    class Responses:
        def __init__(self) -> None:
            self.outputs = iter((None, repaired))
            self.calls = 0

        def parse(self, **_kwargs: object) -> SimpleNamespace:
            self.calls += 1
            return SimpleNamespace(output_parsed=next(self.outputs), usage=None)

    responses = Responses()
    interpreter = OpenAISemanticIntentInterpreter(
        OpenAISemanticIntentConfig(model="test"),
        client=SimpleNamespace(responses=responses),
        capture_llm_io=True,
    )
    result = understand_request(
        _request("two business award seats SFO to BKK October 5"),
        interpreter,
    )
    assert responses.calls == 2
    assert result.outcome.value == "completed"
    assert result.clarification is not None and result.clarification.action.value == "none"
    trace = interpreter.take_call_traces()[0]
    assert trace["adapter"]["provider_stage"] == "inference_reached_parse_failed"
    assert trace["error"]["type"] == "ValueError"


def test_wrong_non_none_provider_parsed_output_uses_one_representation_repair() -> None:
    repaired = WireIntentProposal(
        origins=(WireOrigin(component_id="origin", quote="SFO", location_kind="airport", location_value="SFO"),),
        destinations=(WireDestination(component_id="destination", quote="BKK", location_kind="airport", location_value="BKK"),),
        travelers=(WireTravelers(component_id="travelers", quote="two", travelers=2),),
        cabins=(WireCabin(component_id="cabin", quote="business", cabin="business"),),
        modes=(WireMode(component_id="award", quote="award", search_mode="award"),),
        literal_single_departures=(WireLiteralSingleDeparture(component_id="departure", quote="October 5", start_month=10, start_day=5),),
    )

    class Responses:
        def __init__(self) -> None:
            self.outputs = iter(({}, repaired))
            self.calls = 0

        def parse(self, **_kwargs: object) -> SimpleNamespace:
            self.calls += 1
            return SimpleNamespace(output_parsed=next(self.outputs), usage=None)

    responses = Responses()
    result = understand_request(
        _request("two business award seats SFO to BKK October 5"),
        OpenAISemanticIntentInterpreter(OpenAISemanticIntentConfig(model="test"), client=SimpleNamespace(responses=responses)),
    )
    assert responses.calls == 2
    assert result.outcome.value == "completed"
    assert result.clarification is not None and result.clarification.action.value == "none"


def test_wire_repair_failure_preserves_initial_partial_siblings() -> None:
    first = WireIntentProposal(
        origins=(WireOrigin(component_id="origin", quote="SFO", location_kind="airport", location_value="SFO"),),
        destinations=(WireDestination(component_id="destination", quote="BKK", location_kind="airport", location_value="BKK"),),
        travelers=(WireTravelers(component_id="travelers", quote="two", travelers=2),),
        cabins=(WireCabin(component_id="cabin", quote="business", cabin="business"),),
        modes=(WireMode(component_id="award", quote="award", search_mode="award"),),
        calendar_period_departures=(WireCalendarPeriodDeparture(component_id="departure", quote="October", basis="named_month", period_month=10, period_offset_months=1, period_slice="whole"),),
    )

    class Responses:
        def __init__(self) -> None:
            self.outputs = iter((first, {}))

        def parse(self, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(output_parsed=next(self.outputs), usage=None)

    result = understand_request(
        _request("two business award seats SFO to BKK October"),
        OpenAISemanticIntentInterpreter(OpenAISemanticIntentConfig(model="test"), client=SimpleNamespace(responses=Responses())),
    )
    assert result.outcome.value == "completed"
    assert result.parsed_request is not None
    assert result.parsed_request.origins[0].value == "SFO"
    assert result.parsed_request.destinations[0].value == "BKK"
    assert result.parsed_request.travelers == 2
    assert result.clarification is not None and result.clarification.field == "departure"


def test_wire_repair_transport_failure_is_operational_pending() -> None:
    first = WireIntentProposal(
        origins=(WireOrigin(component_id="origin", quote="SFO", location_kind="airport", location_value="SFO"),),
        calendar_period_departures=(WireCalendarPeriodDeparture(component_id="departure", quote="October", basis="named_month", period_month=10, period_offset_months=1, period_slice="whole"),),
    )

    class Responses:
        def __init__(self) -> None:
            self.calls = 0

        def parse(self, **_kwargs: object) -> SimpleNamespace:
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(output_parsed=first, usage=None)
            raise RuntimeError("provider unavailable")

    result = understand_request(
        _request("SFO October"),
        OpenAISemanticIntentInterpreter(OpenAISemanticIntentConfig(model="test"), client=SimpleNamespace(responses=Responses())),
    )
    assert result.outcome.value == "pending_retryable"


def test_generic_interpreter_wrong_type_uses_its_one_internal_repair() -> None:
    repaired = SemanticIntentProposal(
        facts=_base_facts(),
        temporal_facts=(SemanticTemporalFact(fact_id="departure", target="departure", quote="October", operation="calendar_period", period_month=10, period_slice="whole"),),
    )

    class Generic:
        def __init__(self) -> None:
            self.calls = 0

        def interpret(self, _input: object) -> object:
            return {}

        def repair(self, _input: object, **_kwargs: object) -> SemanticIntentProposal:
            self.calls += 1
            return repaired

    interpreter = Generic()
    result = understand_request(_request("two award seats SFO to Tokyo October"), interpreter)
    assert interpreter.calls == 1
    assert result.outcome.value == "completed"
    assert result.clarification is not None and result.clarification.action.value == "none"


def test_representation_repair_consumes_shared_budget_then_degrades_to_clarification() -> None:
    first = WireIntentProposal(
        calendar_period_departures=(WireCalendarPeriodDeparture(component_id="departure", quote="October", basis="named_month", period_month=10, period_offset_months=1, period_slice="whole"),),
    )
    # Repair structurally succeeds but introduces an ungrounded outbound fact;
    # the workflow must not make a second repair call.
    repaired = WireIntentProposal(
        literal_single_departures=(WireLiteralSingleDeparture(component_id="departure", quote="not present", start_month=10, start_day=5),),
    )

    class Responses:
        def __init__(self) -> None:
            self.outputs = iter((first, repaired))
            self.calls = 0

        def parse(self, **_kwargs: object) -> SimpleNamespace:
            self.calls += 1
            return SimpleNamespace(output_parsed=next(self.outputs), usage=None)

    responses = Responses()
    result = understand_request(
        _request("two award seats SFO to Tokyo October"),
        OpenAISemanticIntentInterpreter(OpenAISemanticIntentConfig(model="test"), client=SimpleNamespace(responses=responses)),
    )
    assert responses.calls == 2
    assert result.outcome.value == "completed"
    assert result.clarification is not None and result.clarification.action.value == "ask"


def test_openai_repair_payload_includes_rejected_proposal_and_typed_errors() -> None:
    proposal = WireIntentProposal()

    class Responses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def parse(self, **kwargs: object) -> SimpleNamespace:
            self.kwargs = kwargs
            return SimpleNamespace(output_parsed=proposal, usage=None)

    responses = Responses()
    client = SimpleNamespace(responses=responses)
    interpreter = OpenAISemanticIntentInterpreter(
        OpenAISemanticIntentConfig(model="test"), client=client, capture_llm_io=True
    )
    rejected = SemanticIntentProposal(
        temporal_facts=(
            SemanticTemporalFact(
                fact_id="bad",
                target="departure",
                quote="October",
                operation="calendar_period",
                period_month=10,
                period_slice="whole",
            ),
        )
    )
    interpreter.repair(
        SemanticIntentInput(request_text="October"),
        proposal=rejected,
        errors=(
            SemanticValidationIssue(
                code="ungrounded_quote",
                path=("components", "bad"),
                detail="quote missing",
            ),
        ),
    )

    payload = json.loads(str(responses.kwargs["input"]))
    assert payload["rejected_wire_proposal"]["calendar_period_departures"][0]["component_id"] == "bad"
    assert payload["validation_errors"][0]["path"] == ["components", "bad"]
    assert interpreter.take_call_traces()[0]["stage"] == "initial_semantic_intent_repair"


def test_semantic_adapter_hash_and_traces_use_sdk_strict_schema_and_adapter_version() -> None:
    from hashlib import sha256

    from openai.lib._parsing import type_to_response_format_param

    strict_schema = type_to_response_format_param(WireIntentProposal)["json_schema"]
    expected_hash = sha256(
        json.dumps(strict_schema, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert response_schema_sha256(WireIntentProposal) == expected_hash

    class Responses:
        def parse(self, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(output_parsed=WireIntentProposal(), usage=None)

    interpreter = OpenAISemanticIntentInterpreter(
        OpenAISemanticIntentConfig(model="test"), client=SimpleNamespace(responses=Responses()), capture_llm_io=True
    )
    interpreter.interpret(SemanticIntentInput(request_text="hello"))
    trace = interpreter.take_call_traces()[0]
    assert trace["adapter"]["version"] == "openai_semantic_intent_wire_v2"
    assert trace["adapter"]["response_schema_sha256"] == expected_hash

    class FailingResponses:
        def parse(self, **_kwargs: object) -> SimpleNamespace:
            raise RuntimeError("preflight")

    failing = OpenAISemanticIntentInterpreter(
        OpenAISemanticIntentConfig(model="test"), client=SimpleNamespace(responses=FailingResponses()), capture_llm_io=True
    )
    with pytest.raises(OpenAISemanticIntentError):
        failing.interpret(SemanticIntentInput(request_text="hello"))
    error_trace = failing.take_call_traces()[0]
    assert error_trace["adapter"]["version"] == "openai_semantic_intent_wire_v2"
    assert error_trace["adapter"]["response_schema_sha256"] == expected_hash
