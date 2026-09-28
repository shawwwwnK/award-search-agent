from types import SimpleNamespace
from typing import Any, cast

import pytest

from award_agent.providers.timezones import CatalogTimezoneResolver
from award_agent.search_planning.compilation_contracts import CompiledSearchPlan
from award_agent.search_planning.knowledge import PlanningKnowledgeRepository


class FakeRepository:
    def __init__(self, receipt: object) -> None:
        self.knowledge_receipt = receipt
        self.lookups: list[str] = []
        self.airports = {
            "SFO": SimpleNamespace(airport_id="sfo-id", iata="SFO", timezone="America/Los_Angeles"),
            "BKK": SimpleNamespace(airport_id="bkk-id", iata="BKK", timezone="Asia/Bangkok"),
            "NRT": SimpleNamespace(airport_id="nrt-id", iata="NRT", timezone="Asia/Tokyo"),
        }

    def lookup_airport_iata(self, iata: str) -> Any:
        self.lookups.append(iata)
        return self.airports.get(iata)


def _plan(receipt: object) -> CompiledSearchPlan:
    return cast(
        CompiledSearchPlan,
        SimpleNamespace(
            identity=SimpleNamespace(catalog_receipt=receipt),
            airport_directory=(
                SimpleNamespace(
                    airport_id="sfo-id", airport_iata="SFO", timezone="America/Los_Angeles"
                ),
                SimpleNamespace(airport_id="bkk-id", airport_iata="BKK", timezone="Asia/Bangkok"),
            ),
        ),
    )


def test_intermediate_airport_is_lazily_resolved_from_bound_catalog() -> None:
    receipt = object()
    repo = FakeRepository(receipt)
    zones = CatalogTimezoneResolver(_plan(receipt), cast(PlanningKnowledgeRepository, repo))
    assert repo.lookups == ["SFO", "BKK"]
    assert zones["NRT"] == "Asia/Tokyo"
    assert zones.get("NRT") == "Asia/Tokyo"
    assert repo.lookups.count("NRT") == 1
    assert zones.get("XXX") is None
    assert zones.get("XXX") is None
    assert repo.lookups.count("XXX") == 1


def test_wrong_receipt_or_inconsistent_directory_fails_closed() -> None:
    receipt = object()
    repo = FakeRepository(receipt)
    with pytest.raises(ValueError, match="catalog receipt"):
        CatalogTimezoneResolver(_plan(object()), cast(PlanningKnowledgeRepository, repo))
    repo.airports["SFO"].timezone = "America/New_York"
    with pytest.raises(ValueError, match="compiled airport differs"):
        CatalogTimezoneResolver(_plan(receipt), cast(PlanningKnowledgeRepository, repo))
