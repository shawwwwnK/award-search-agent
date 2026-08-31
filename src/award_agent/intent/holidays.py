"""Holiday-date lookup through the Nager.Holidays Community API."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from award_agent.domain import Holiday

NagerTransport = Callable[[str, float], bytes]


class HolidayDateResolutionError(RuntimeError):
    """Raised when an authoritative holiday date cannot be resolved."""


class HolidayDateProvider(Protocol):
    """Narrow boundary used by deterministic date-window arithmetic."""

    def holiday_date(self, holiday: Holiday, year: int) -> date:
        """Return the calendar date for a supported holiday and year."""


_NAGER_NAMES: dict[Holiday, frozenset[str]] = {
    Holiday.NEW_YEARS_DAY: frozenset({"New Year's Day"}),
    Holiday.MARTIN_LUTHER_KING_JR_DAY: frozenset(
        {"Martin Luther King, Jr. Day", "Martin Luther King Jr. Day"}
    ),
    Holiday.WASHINGTONS_BIRTHDAY: frozenset(
        {"Washington's Birthday", "Presidents Day", "Presidents' Day"}
    ),
    Holiday.MEMORIAL_DAY: frozenset({"Memorial Day"}),
    Holiday.JUNETEENTH: frozenset({"Juneteenth National Independence Day", "Juneteenth"}),
    Holiday.INDEPENDENCE_DAY: frozenset({"Independence Day"}),
    Holiday.LABOR_DAY: frozenset({"Labor Day", "Labour Day"}),
    Holiday.COLUMBUS_DAY: frozenset({"Columbus Day"}),
    Holiday.VETERANS_DAY: frozenset({"Veterans Day"}),
    Holiday.THANKSGIVING: frozenset({"Thanksgiving Day", "Thanksgiving"}),
    Holiday.CHRISTMAS: frozenset({"Christmas Day", "Christmas"}),
}


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _urlopen_transport(url: str, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "award-travel-agent/0.1",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload: bytes = response.read()
            return payload
    except (HTTPError, URLError, TimeoutError) as exc:
        raise HolidayDateResolutionError(f"Nager.Holidays request failed: {exc}") from exc


class NagerHolidayProvider:
    """Resolve U.S. federal-holiday dates using Nager.Holidays API v4."""

    def __init__(
        self,
        *,
        country_code: str = "US",
        base_url: str = "https://nagerholidays.com/api/v4",
        timeout_seconds: float = 10.0,
        transport: NagerTransport = _urlopen_transport,
    ) -> None:
        normalized_country = country_code.upper()
        if normalized_country != "US":
            raise ValueError("the current Holiday contract supports U.S. federal holidays only")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._country_code = normalized_country
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._cache: dict[int, tuple[tuple[str, date], ...]] = {}

    def holiday_date(self, holiday: Holiday, year: int) -> date:
        holidays = self._holidays_for_year(year)
        accepted_names = {_normalized_name(name) for name in _NAGER_NAMES[holiday]}
        matches = {
            holiday_date
            for name, holiday_date in holidays
            if _normalized_name(name) in accepted_names
        }
        if not matches:
            raise HolidayDateResolutionError(
                f"Nager.Holidays returned no {holiday.value} date for {self._country_code} {year}"
            )
        if len(matches) > 1:
            values = ", ".join(sorted(item.isoformat() for item in matches))
            raise HolidayDateResolutionError(
                f"Nager.Holidays returned conflicting {holiday.value} dates for "
                f"{self._country_code} {year}: {values}"
            )
        return next(iter(matches))

    def _holidays_for_year(self, year: int) -> tuple[tuple[str, date], ...]:
        if year in self._cache:
            return self._cache[year]

        url = f"{self._base_url}/Holidays/{self._country_code}/{year}"
        try:
            payload = json.loads(self._transport(url, self._timeout_seconds))
        except HolidayDateResolutionError:
            raise
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise HolidayDateResolutionError(
                "Nager.Holidays returned an invalid JSON response"
            ) from exc
        if not isinstance(payload, list):
            raise HolidayDateResolutionError("Nager.Holidays response must be a JSON array")

        parsed: list[tuple[str, date]] = []
        for item in payload:
            if not isinstance(item, dict):
                raise HolidayDateResolutionError(
                    "Nager.Holidays response contains a non-object holiday"
                )
            name = item.get("name")
            raw_date = item.get("date")
            country_code = item.get("countryCode")
            if not isinstance(name, str) or not isinstance(raw_date, str):
                raise HolidayDateResolutionError(
                    "Nager.Holidays holiday entries require string name and date fields"
                )
            if country_code != self._country_code:
                raise HolidayDateResolutionError(
                    "Nager.Holidays response country does not match the requested country"
                )
            try:
                parsed_date = date.fromisoformat(raw_date)
            except ValueError as exc:
                raise HolidayDateResolutionError(
                    f"Nager.Holidays returned an invalid holiday date: {raw_date}"
                ) from exc
            if parsed_date.year != year:
                raise HolidayDateResolutionError(
                    "Nager.Holidays response contains a holiday outside the requested year"
                )
            parsed.append((name, parsed_date))

        result = tuple(parsed)
        self._cache[year] = result
        return result
