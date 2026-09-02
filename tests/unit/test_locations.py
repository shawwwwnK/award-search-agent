from datetime import date

from award_agent.domain import (
    CoarseIntentExtraction,
    LocationKind,
    LocationRef,
    RawRequest,
    RequestContext,
)
from award_agent.intent.locations import preserve_explicit_airport_codes


def request(text: str) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 31), timezone="UTC"),
    )


def location(kind: LocationKind, value: str, raw_text: str) -> LocationRef:
    return LocationRef(kind=kind, value=value, raw_text=raw_text)


def test_preserves_model_classified_explicit_airport_code() -> None:
    extraction = CoarseIntentExtraction(
        origins=[
            location(
                LocationKind.AIRPORT,
                "Los Angeles International Airport",
                "LAX",
            )
        ]
    )

    result = preserve_explicit_airport_codes(
        request("Find award flights from LAX to Sydney."), extraction
    )

    assert result.origins[0].value == "LAX"
    assert result.origins[0].raw_text == "LAX"


def test_normalizes_explicit_airport_code_to_uppercase() -> None:
    extraction = CoarseIntentExtraction(
        destinations=[location(LocationKind.AIRPORT, "Los Angeles airport", "lax")]
    )

    result = preserve_explicit_airport_codes(request("Fly me to lax."), extraction)

    assert result.destinations[0].value == "LAX"
    assert result.destinations[0].raw_text == "lax"


def test_does_not_turn_city_abbreviation_into_airport() -> None:
    extraction = CoarseIntentExtraction(
        origins=[location(LocationKind.CITY, "San Francisco", "SF")]
    )

    result = preserve_explicit_airport_codes(request("Fly from SF."), extraction)

    assert result.origins[0].kind is LocationKind.CITY
    assert result.origins[0].value == "San Francisco"


def test_does_not_replace_named_airport_candidate() -> None:
    extraction = CoarseIntentExtraction(
        origins=[location(LocationKind.AIRPORT, "London Heathrow Airport", "Heathrow")]
    )

    result = preserve_explicit_airport_codes(request("Fly from Heathrow."), extraction)

    assert result.origins[0].value == "London Heathrow Airport"


def test_does_not_accept_airport_code_as_substring_evidence() -> None:
    extraction = CoarseIntentExtraction(
        origins=[location(LocationKind.AIRPORT, "Singapore Changi Airport", "SIN")]
    )

    result = preserve_explicit_airport_codes(
        request("Help me find flights using points."), extraction
    )

    assert result.origins[0].value == "Singapore Changi Airport"
