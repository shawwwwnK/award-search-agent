"""Offline tests for the diagnostic M2A live-evaluation harness."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from test_catalog_serving import _release

from award_agent.evaluation.airport_selector_live import (
    DEFAULT_AIRPORT_SELECTOR_LIVE_FIXTURES,
    AirportSelectorLiveFixtureError,
    load_airport_selector_live_cases,
    run_airport_selector_live_eval,
)
from award_agent.search_planning.airport_selector import (
    AirportSelectionProposal,
    AirportSelectionProposalOutcome,
    OpenAIAirportSelectorConfig,
)


class _FakeSelector:
    def __init__(
        self, config: OpenAIAirportSelectorConfig, *, error: Exception | None = None
    ) -> None:
        self.config = config
        self._error = error

    def propose(self, _model_input: object) -> AirportSelectionProposal:
        if self._error is not None:
            raise self._error
        return AirportSelectionProposal(
            outcome=AirportSelectionProposalOutcome.PROPOSED,
            airport_iata_codes=("TST",),
        )

    def take_usage(self) -> dict[str, int]:
        return {
            "calls": 1,
            "captured_calls": 1,
            "missing_calls": 0,
            "input_tokens": 7,
            "output_tokens": 3,
            "total_tokens": 10,
        }

    def take_call_traces(self) -> list[dict[str, Any]]:
        return [
            {
                "request": {
                    "instructions": self.config.prompt.instructions,
                    "input": "Test City",
                },
                "response_json": "private selector response",
            }
        ]


def _fixture(path: Path) -> Path:
    path.write_text(
        """contract_version: airport_selector_development_v3
development: true
scenarios:
  - id: test_city
    entity_id: geonames:2
    role: origin
    expectations:
      must_consider_any_of: [TST]
      acceptable: [TST]
      unacceptable: [ZZZ]
      review_focus: synthetic offline test context
""",
        encoding="utf-8",
    )
    return path


def test_casebook_loads_and_disclosed_cases_use_human_selection_envelopes() -> None:
    cases = load_airport_selector_live_cases()

    assert DEFAULT_AIRPORT_SELECTOR_LIVE_FIXTURES == Path(
        "evals/airport_selector/development_cases_v3.yaml"
    )
    assert len(cases) >= 14
    assert {case["id"] for case in cases} >= {
        "san_francisco_city_metro_override_cap_3",
        "new_york_city_metro_override_cap_3",
        "london_city_metro_override_cap_5",
        "los_angeles_city_metro_override_cap_5",
        "united_states_country_international_gateway_override_cap_10",
        "china_country_international_gateway_override_cap_6",
        "india_country_international_gateway_override_cap_6",
        "middle_east_geographic_region_broad_fallback_cap_8",
    }
    for case in cases:
        expectations = case["expectations"]
        assert "must_consider_any_of" in expectations
        assert "acceptable" in expectations
        assert "unacceptable" in expectations
        assert "exact_airport_list" not in expectations


def test_casebook_rejects_exact_list_oracle_shape(tmp_path: Path) -> None:
    fixture = tmp_path / "bad.yaml"
    fixture.write_text(
        """contract_version: airport_selector_development_v3
development: true
scenarios:
  - id: bad
    entity_id: geonames:2
    role: origin
    expectations:
      exact_airport_list: [TST]
""",
        encoding="utf-8",
    )

    with pytest.raises(AirportSelectorLiveFixtureError, match="invalid shape"):
        load_airport_selector_live_cases(fixture)


def test_active_casebook_entities_match_selected_catalog_identity_labels_and_kinds() -> None:
    expected = {
        "geonames:5391959": ("San Francisco", "city"),
        "geonames:5128581": ("New York City", "city"),
        "geonames:2643743": ("London", "city"),
        "geonames:5368361": ("Los Angeles", "city"),
        "geonames:6252001": ("United States", "country"),
        "geonames:1814991": ("China", "country"),
        "geonames:1269750": ("India", "country"),
    }
    active_ids = {str(case["entity_id"]) for case in load_airport_selector_live_cases()}
    catalog = Path("data/search_planning/catalogs/m1a-3cb7981519612945/catalog.sqlite")
    connection = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    try:
        rows = {
            str(row[0]): (str(row[1]), str(row[2]))
            for row in connection.execute(
                "SELECT entity_id, label, entity_kind FROM entity "
                "WHERE entity_id IN (?, ?, ?, ?, ?, ?, ?)",
                tuple(expected),
            )
        }
    finally:
        connection.close()

    assert set(expected).issubset(active_ids)
    assert rows == expected


@pytest.mark.parametrize(
    ("path", "expected_sha256"),
    [
        (
            "evals/airport_selector/development_cases_v1.yaml",
            "8c40c805c55cb73efe762c9a4bdb5b9dd82eaa4f5efcd5b5a3d0a049c4b1d6b3",
        ),
        (
            (
                "evals/airport_selector/baseline/"
                "2026-09-17-gpt-5.6-luna-original-simple-vs-refined-development-3-trials.json"
            ),
            "f97add6ffa024d7485b50753052c836ca4e79a42fed70ee0552dbdc272832afc",
        ),
        (
            "evals/airport_selector/development_cases_v2.yaml",
            "f6ffa81f43b3970df192a2df5ea156c4dde894d28a35638dcb245a78331f1bb6",
        ),
        (
            (
                "evals/airport_selector/baseline/"
                "2026-09-17-gpt-5.6-luna-original-simple-vs-refined-active-cap-overrides-v2-3-trials.json"
            ),
            "d7bb80b2ef1ea7ed3ae73cc3965dd3f77ca97eec614ef5b483a4361644908b9f",
        ),
    ],
)
def test_historical_casebooks_and_artifacts_are_byte_pinned(
    path: str, expected_sha256: str
) -> None:
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected_sha256


def test_live_artifact_redacts_model_input_and_reconciles_trace(tmp_path: Path) -> None:
    release = _release(tmp_path)
    fixture = _fixture(tmp_path / "cases.yaml")

    artifact = run_airport_selector_live_eval(
        model="offline-test-model",
        trials=1,
        prompt_arms=("refined",),
        fixture_path=fixture,
        catalog_release=release,
        trace_dir=tmp_path / "traces-live",
        selector_factory=lambda config: _FakeSelector(config),
    )

    record = artifact["records"][0]
    public = json.dumps(artifact)
    assert record["status"] == "completed"
    assert record["criteria"]["must_consider_present"] is True
    assert record["criteria"]["manual_semantic_review_required"] is True
    assert record["trace_reconciliation"] == {
        "attempted_calls": 1,
        "trace_calls": 1,
        "usage_captured_calls": 1,
        "missing_usage_calls": 0,
        "reconciled": True,
    }
    assert artifact["summary"] == {
        "runs": 1,
        "completed": 1,
        "errors": 0,
        "trace_reconciled": 1,
        "mechanically_completed": True,
        "semantic_qualification": "not_claimed_manual_review_required",
    }
    assert REFINED_INSTRUCTIONS_NOT_PUBLIC not in public
    assert "Test City" not in public
    assert "private selector response" not in public
    private_trace = Path(record["private_trace"]["path"])
    assert private_trace.exists()
    assert REFINED_INSTRUCTIONS_NOT_PUBLIC in private_trace.read_text(encoding="utf-8")


REFINED_INSTRUCTIONS_NOT_PUBLIC = "Propose useful initial airport-search endpoints"


def test_two_prompt_arms_write_distinct_private_traces_with_matching_raw_prompt(
    tmp_path: Path,
) -> None:
    release = _release(tmp_path)
    fixture = _fixture(tmp_path / "cases.yaml")

    artifact = run_airport_selector_live_eval(
        model="offline-test-model",
        trials=1,
        prompt_arms=("original_simple", "refined"),
        fixture_path=fixture,
        catalog_release=release,
        trace_dir=tmp_path / "traces-live",
        selector_factory=lambda config: _FakeSelector(config),
    )

    records = {record["prompt_arm"]: record for record in artifact["records"]}
    simple_path = Path(records["original_simple"]["private_trace"]["path"])
    refined_path = Path(records["refined"]["private_trace"]["path"])
    assert simple_path != refined_path
    assert simple_path.exists() and refined_path.exists()
    simple = json.loads(simple_path.read_text(encoding="utf-8"))
    refined = json.loads(refined_path.read_text(encoding="utf-8"))
    assert simple["evaluation_record"]["prompt_arm"] == "original_simple"
    assert refined["evaluation_record"]["prompt_arm"] == "refined"
    assert "What are the common airports" in simple["calls"][0]["request"]["instructions"]
    assert REFINED_INSTRUCTIONS_NOT_PUBLIC in refined["calls"][0]["request"]["instructions"]


def test_live_artifact_hides_provider_error_message_and_marks_run_incomplete(
    tmp_path: Path,
) -> None:
    release = _release(tmp_path)
    fixture = _fixture(tmp_path / "cases.yaml")

    artifact = run_airport_selector_live_eval(
        model="offline-test-model",
        trials=1,
        prompt_arms=("original_simple",),
        fixture_path=fixture,
        catalog_release=release,
        trace_dir=tmp_path / "traces-live",
        selector_factory=lambda config: _FakeSelector(
            config, error=RuntimeError("provider repeated Test City verbatim")
        ),
    )

    record = artifact["records"][0]
    assert record["status"] == "error"
    assert record["error_type"] == "RuntimeError"
    assert "provider repeated Test City verbatim" not in json.dumps(artifact)
    assert artifact["summary"]["mechanically_completed"] is False
