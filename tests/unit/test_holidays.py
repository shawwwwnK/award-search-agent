import json
from datetime import date

import pytest

from award_agent.domain import Holiday
from award_agent.intent.holidays import (
    HolidayDateResolutionError,
    NagerHolidayProvider,
)


def _response(entries: list[tuple[str, str]]) -> bytes:
    return json.dumps(
        [
            {
                "date": holiday_date,
                "name": name,
                "countryCode": "US",
                "nationalHoliday": True,
                "subdivisionCodes": None,
                "holidayTypes": ["Public"],
            }
            for name, holiday_date in entries
        ]
    ).encode()


def test_nager_provider_maps_every_supported_us_federal_holiday_and_caches_year() -> None:
    calls: list[tuple[str, float]] = []
    payload = _response(
        [
            ("New Year's Day", "2026-01-01"),
            ("Martin Luther King, Jr. Day", "2026-01-19"),
            ("Presidents Day", "2026-02-16"),
            ("Memorial Day", "2026-05-25"),
            ("Juneteenth National Independence Day", "2026-06-19"),
            ("Independence Day", "2026-07-04"),
            ("Labour Day", "2026-09-07"),
            ("Columbus Day", "2026-10-12"),
            ("Veterans Day", "2026-11-11"),
            ("Thanksgiving Day", "2026-11-26"),
            ("Christmas Day", "2026-12-25"),
        ]
    )

    def transport(url: str, timeout_seconds: float) -> bytes:
        calls.append((url, timeout_seconds))
        return payload

    provider = NagerHolidayProvider(transport=transport, timeout_seconds=3.0)

    results = {holiday: provider.holiday_date(holiday, 2026) for holiday in Holiday}

    assert results[Holiday.LABOR_DAY] == date(2026, 9, 7)
    assert results[Holiday.THANKSGIVING] == date(2026, 11, 26)
    assert calls == [("https://nagerholidays.com/api/v4/Holidays/US/2026", 3.0)]


def test_nager_provider_fails_explicitly_when_holiday_is_absent() -> None:
    provider = NagerHolidayProvider(transport=lambda _url, _timeout: b"[]")

    with pytest.raises(
        HolidayDateResolutionError,
        match="returned no labor_day date for US 2026",
    ):
        provider.holiday_date(Holiday.LABOR_DAY, 2026)


@pytest.mark.parametrize(
    "payload, message",
    [
        (b"{}", "response must be a JSON array"),
        (b"not json", "returned an invalid JSON response"),
        (
            _response([("Labor Day", "not-a-date")]),
            "returned an invalid holiday date",
        ),
    ],
)
def test_nager_provider_rejects_invalid_responses(payload: bytes, message: str) -> None:
    provider = NagerHolidayProvider(transport=lambda _url, _timeout: payload)

    with pytest.raises(HolidayDateResolutionError, match=message):
        provider.holiday_date(Holiday.LABOR_DAY, 2026)
