from datetime import date

from award_agent.cli.intent_eval import _score_result
from award_agent.domain import (
    ClarificationAction,
    ClarificationDecision,
    CoarseIntentExtraction,
    DateResolutionProposal,
    DateWindow,
    DateWindowPrecision,
    InterpretedDuration,
    LocationKind,
    LocationRef,
    ParsedRequest,
    ProposedDateWindow,
    RequestContext,
    RequestUnderstandingResult,
    SearchMode,
    UnknownField,
    UnknownReason,
)


def _result() -> RequestUnderstandingResult:
    return RequestUnderstandingResult(
        parsed_request=ParsedRequest(
            raw_text="Two travelers from LAX to Tokyo in October for a week using miles.",
            context=RequestContext(reference_date=date(2026, 8, 29), timezone="UTC"),
            travelers=2,
            origins=[LocationRef(kind=LocationKind.AIRPORT, value="LAX", raw_text="LAX")],
            destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
            departure_expression=None,
            return_expression=None,
            departure_window=DateWindow(
                start=date(2026, 10, 1),
                end=date(2026, 10, 31),
                precision=DateWindowPrecision.MONTH,
                raw_text="in October",
            ),
            return_window=DateWindow(
                start=date(2026, 10, 8),
                end=date(2026, 11, 7),
                precision=DateWindowPrecision.DERIVED,
                raw_text="for a week",
            ),
            duration=None,
            cabins=[],
            search_modes=[SearchMode.AWARD],
            date_flexibility=[],
            repositioning_allowed=None,
            hard_constraints=[],
            unknowns=[
                UnknownField(
                    field="cabin",
                    reason=UnknownReason.MISSING,
                    detail="No cabin preference was stated.",
                )
            ],
            conflicts=[],
            temporal_extraction=CoarseIntentExtraction(travelers=2),
            date_resolution=DateResolutionProposal(
                departure=ProposedDateWindow(
                    start=date(2026, 10, 1),
                    end=date(2026, 10, 31),
                    supporting_text=["October"],
                    interpretation="Whole month.",
                ),
                return_date=ProposedDateWindow(
                    start=date(2026, 10, 8),
                    end=date(2026, 11, 7),
                    supporting_text=["for a week"],
                    interpretation="Seven days.",
                ),
                interpreted_duration=InterpretedDuration(
                    raw_text="for a week", minimum_days=7, maximum_days=7
                ),
            ),
        ),
        clarification=ClarificationDecision(
            action=ClarificationAction.NONE,
            reason="Enough constraints.",
        ),
    )


def test_score_result_checks_supported_golden_expectations() -> None:
    expected = {
        "travelers": 2,
        "origin": {"kind": "airport", "value": "LAX"},
        "destination": {"kind": "city", "value": "Tokyo"},
        "search_modes": ["award"],
        "departure_window": {"start": "2026-10-01", "end": "2026-10-31"},
        "return_window": {"start": "2026-10-08", "end": "2026-11-07"},
        "interpreted_duration": {"minimum_days": 7, "maximum_days": 7},
        "unknowns": ["cabin"],
        "clarification": {"action": "none"},
    }

    checks = _score_result(expected, _result())

    assert checks
    assert all(check["passed"] for check in checks)


def test_score_result_reports_mismatches() -> None:
    checks = _score_result({"travelers": 3}, _result())

    assert checks == [
        {"name": "travelers", "passed": False, "expected": 3, "actual": 2}
    ]


def test_score_result_accepts_only_explicit_location_candidate_aliases() -> None:
    expected = {
        "destination": {
            "kind": "city",
            "raw_text": "Tokyo",
            "accepted_values": ["Tokyo", "Tōkyō"],
        }
    }

    checks = _score_result(expected, _result())

    assert checks[0]["passed"] is True


def test_score_result_does_not_fuzzy_match_location_candidates() -> None:
    expected = {
        "destination": {
            "kind": "city",
            "raw_text": "Tokyo",
            "accepted_values": ["Tōkyō"],
        }
    }

    checks = _score_result(expected, _result())

    assert checks[0]["passed"] is False


def test_score_result_still_requires_exact_location_evidence() -> None:
    expected = {
        "destination": {
            "kind": "city",
            "raw_text": "Tokio",
            "accepted_values": ["Tokyo"],
        }
    }

    checks = _score_result(expected, _result())

    assert checks[0]["passed"] is False


def test_score_result_rejects_invalid_location_candidate_alias_contract() -> None:
    expected = {
        "destination": {
            "kind": "city",
            "accepted_values": [],
        }
    }

    try:
        _score_result(expected, _result())
    except ValueError as exc:
        assert str(exc) == "location accepted_values must be a non-empty list of strings"
    else:
        raise AssertionError("invalid accepted_values should fail explicitly")
