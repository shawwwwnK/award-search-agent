"""Focused one-way clarification-session contract tests."""

from datetime import date

import pytest
from pydantic import ValidationError

from award_agent.clarification.projection import project_initial_request
from award_agent.domain import (
    AnswerMessageSource,
    DateWindow,
    DateWindowPrecision,
    EffectiveField,
    FieldProvenance,
    InitialSnapshotSource,
    LocationKind,
    LocationRef,
    MessageSpan,
    ParsedRequest,
    RequestContext,
    ScopeNotice,
    TemporalContribution,
    TemporalContributionKind,
)


def _parsed() -> ParsedRequest:
    return ParsedRequest(
        raw_text="SFO to Tokyo October 6, return October 15",
        context=RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles"),
        travelers=2,
        origins=[LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        departure_expression=None,
        departure_window=DateWindow(
            start=date(2026, 10, 6), end=date(2026, 10, 6), precision=DateWindowPrecision.EXACT, raw_text="October 6"
        ),
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=[],
        conflicts=[],
    )


def test_effective_request_projects_only_one_way_values() -> None:
    parsed = _parsed()
    effective = project_initial_request(parsed)
    assert effective.departure_window == parsed.departure_window
    assert [item.contribution_id for item in effective.temporal_contributions] == ["initial:departure_window"]
    assert {item.field for item in effective.field_provenance} == {
        EffectiveField.ORIGIN,
        EffectiveField.DESTINATION,
        EffectiveField.DEPARTURE,
        EffectiveField.TRAVELERS,
    }
    assert "return_window" not in effective.model_dump()
    assert "interpreted_duration" not in effective.model_dump()


def test_temporal_contribution_accepts_only_departure_window() -> None:
    source = InitialSnapshotSource(field=EffectiveField.DEPARTURE)
    value = TemporalContribution(
        contribution_id="initial:departure_window",
        kind=TemporalContributionKind.DEPARTURE_WINDOW,
        source=source,
        date_window=DateWindow(
            start=date(2026, 10, 6),
            end=date(2026, 10, 6),
            precision=DateWindowPrecision.EXACT,
            raw_text="October 6",
        ),
    )
    assert value.date_window.start == date(2026, 10, 6)
    with pytest.raises(ValidationError):
        TemporalContribution.model_validate(
            {
                "contribution_id": "bad",
                "kind": "return_window",
                "source": source.model_dump(mode="python"),
                "date_window": value.date_window.model_dump(mode="python"),
            }
        )


def test_scope_notice_is_grounded_and_has_fixed_policy_copy() -> None:
    notice = ScopeNotice(
        span=MessageSpan(message_id="m1", start=0, end=9, text="returning")
    )
    assert "separate one-way request" in notice.message
    with pytest.raises(ValidationError):
        ScopeNotice(
            message="anything else",
            span=MessageSpan(message_id="m1", start=0, end=9, text="returning"),
        )


def test_answer_provenance_requires_an_amendment_id() -> None:
    with pytest.raises(ValidationError, match="requires an amendment ID"):
        FieldProvenance(
            field=EffectiveField.DEPARTURE,
            source=AnswerMessageSource(
                span=MessageSpan(message_id="m1", start=0, end=9, text="October 6")
            ),
        )
