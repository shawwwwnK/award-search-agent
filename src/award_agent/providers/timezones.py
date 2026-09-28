"""Catalog-bound timezone lookup for airports returned inside provider itineraries."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from award_agent.search_planning.compilation_contracts import CompiledSearchPlan
from award_agent.search_planning.knowledge import PlanningKnowledgeRepository


class CatalogTimezoneResolver(Mapping[str, str]):
    """Resolve plan airports eagerly and returned intermediate airports on demand.

    The catalog receipt binds each lookup to the same catalog release that produced
    the plan. Missing returned airports remain unknown to the observation parser.
    """

    def __init__(
        self,
        plan: CompiledSearchPlan,
        repository: PlanningKnowledgeRepository,
    ) -> None:
        if plan.identity.catalog_receipt != repository.knowledge_receipt:
            raise ValueError("timezone repository catalog receipt differs from compiled plan")
        self._repository = repository
        self._zones: dict[str, str] = {}
        self._missing: set[str] = set()
        for item in plan.airport_directory:
            airport = repository.lookup_airport_iata(item.airport_iata)
            if (
                airport is None
                or airport.airport_id != item.airport_id
                or airport.timezone != item.timezone
            ):
                raise ValueError(
                    f"compiled airport differs from bound catalog: {item.airport_iata}"
                )
            self._validate_timezone(airport.timezone)
            self._zones[item.airport_iata] = airport.timezone

    def __getitem__(self, iata: str) -> str:
        if iata in self._zones:
            return self._zones[iata]
        if iata in self._missing:
            raise KeyError(iata)
        airport = self._repository.lookup_airport_iata(iata)
        if airport is None:
            self._missing.add(iata)
            raise KeyError(iata)
        self._validate_timezone(airport.timezone)
        self._zones[iata] = airport.timezone
        return airport.timezone

    def __iter__(self) -> Iterator[str]:
        return iter(self._zones)

    def __len__(self) -> int:
        return len(self._zones)

    @staticmethod
    def _validate_timezone(name: str) -> None:
        try:
            ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"bound catalog contains invalid timezone: {name}") from exc
