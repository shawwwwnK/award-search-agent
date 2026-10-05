"""Pre-extraction query identity values from a saved typed planning query."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import cast

import pytest
from pydantic import ValidationError

from award_agent.search_planning.compilation_contracts import (
    LogicalAwardQuery,
    _logical_query_identity_payload,
)
from award_agent.search_planning.planner import _query_identity_payload

_QUERY_ID = "logical-award:2ad70e19d273b707742e58127a0468148a579ee61925c47acc1673e98334c012"
_CANONICAL_BYTES = (
    b'{"award_mode":"award","connection_semantics":"provider_returned_connections_allowed",'
    b'"date_envelope":{"basis":"first_origin_airport_local","end":"2026-10-05",'
    b'"inclusive":true,"start":"2026-10-05","timezone":"America/Los_Angeles"},'
    b'"destination_airport_fact_id":"ourairports:28118","filter_obligations":'
    b'[{"kind":"cabin_available_in","origin":"user_requirement","values":["business"]}],'
    b'"origin_airport_fact_id":"ourairports:3878","query_identity_version":'
    b'"logical-award-query-semantics-v1","requested_cabins":["business"],'
    b'"result_validation_obligations":[{"disposition":"not_verified",'
    b'"expected_destination_airport_fact_id":null,"expected_origin_airport_fact_id":null,'
    b'"kind":"minimum_award_seats","minimum_seats":2,'
    b'"responsible_stage":"provider_result_validation"}],"scope":"endpoint_market"}'
)


def _query() -> dict[str, object]:
    return {
        "query_id": _QUERY_ID,
        "origin_airport_fact_id": "ourairports:3878",
        "destination_airport_fact_id": "ourairports:28118",
        "scope": "endpoint_market",
        "date_envelope": {
            "start": "2026-10-05",
            "end": "2026-10-05",
            "inclusive": True,
            "basis": "first_origin_airport_local",
            "timezone": "America/Los_Angeles",
            "effective_window_precision": "exact",
            "field_provenance": {
                "field": "departure",
                "source": {"kind": "initial_snapshot", "field": "departure"},
                "amendment_id": None,
            },
        },
        "requested_cabins": ["business"],
        "award_mode": "award",
        "connection_semantics": "provider_returned_connections_allowed",
        "filter_obligations": [
            {
                "kind": "cabin_available_in",
                "values": ["business"],
                "origin": "user_requirement",
                "field_provenance": {
                    "field": "cabin",
                    "source": {"kind": "initial_snapshot", "field": "cabin"},
                    "amendment_id": None,
                },
            }
        ],
        "result_validation_obligations": [
            {
                "kind": "minimum_award_seats",
                "minimum_seats": 2,
                "expected_origin_airport_fact_id": None,
                "expected_destination_airport_fact_id": None,
                "field_provenance": {
                    "field": "travelers",
                    "source": {"kind": "initial_snapshot", "field": "travelers"},
                    "amendment_id": None,
                },
                "responsible_stage": "provider_result_validation",
                "disposition": "not_verified",
            }
        ],
    }


def _canonical_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def test_dict_and_typed_paths_match_independent_saved_query_identity() -> None:
    raw = _query()
    typed = LogicalAwardQuery.model_validate(raw)
    assert typed.query_id == _QUERY_ID
    assert _canonical_bytes(_query_identity_payload(raw)) == _CANONICAL_BYTES
    assert _canonical_bytes(_query_identity_payload(typed)) == _CANONICAL_BYTES
    assert _canonical_bytes(_logical_query_identity_payload(typed)) == _CANONICAL_BYTES
    assert "logical-award:" + hashlib.sha256(_CANONICAL_BYTES).hexdigest() == _QUERY_ID


def test_provenance_and_effective_precision_are_excluded() -> None:
    raw = _query()
    raw["date_envelope"]["effective_window_precision"] = "window"  # type: ignore[index]
    raw["date_envelope"]["field_provenance"] = None  # type: ignore[index]
    raw["filter_obligations"][0]["field_provenance"] = None  # type: ignore[index]
    raw["result_validation_obligations"][0]["field_provenance"] = None  # type: ignore[index]
    assert _canonical_bytes(_query_identity_payload(raw)) == _CANONICAL_BYTES


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("origin_airport_fact_id", "ourairports:999"),
        ("destination_airport_fact_id", "ourairports:999"),
        ("requested_cabins", ["first"]),
        ("award_mode", "cash"),
        ("connection_semantics", "direct_only"),
    ],
)
def test_semantic_changes_change_identity(field: str, replacement: object) -> None:
    raw = _query()
    raw[field] = replacement
    assert _canonical_bytes(_query_identity_payload(raw)) != _CANONICAL_BYTES


def test_missing_fields_and_malformed_obligations_retain_dict_errors() -> None:
    raw = _query()
    del raw["origin_airport_fact_id"]
    with pytest.raises(KeyError, match="origin_airport_fact_id"):
        _query_identity_payload(raw)
    raw = _query()
    del cast(dict[str, object], raw["date_envelope"])["timezone"]
    with pytest.raises(KeyError, match="timezone"):
        _query_identity_payload(raw)
    raw = _query()
    raw["filter_obligations"] = [7]
    with pytest.raises(AttributeError, match="model_dump"):
        _query_identity_payload(raw)


def test_error_order_and_malformed_model_dump_remain_unchanged() -> None:
    raw = _query()
    del cast(dict[str, object], raw["date_envelope"])["timezone"]
    del raw["requested_cabins"]
    with pytest.raises(KeyError, match="timezone"):
        _query_identity_payload(raw)

    class BadDump:
        def model_dump(self, **_kwargs: object) -> list[tuple[str, object]]:
            return [("kind", "cabin_available_in")]

    raw = _query()
    raw["filter_obligations"] = [BadDump()]
    with pytest.raises(TypeError):
        _query_identity_payload(raw)


def test_validator_rejects_forged_id_and_requires_typed_input() -> None:
    raw = _query()
    raw["destination_airport_fact_id"] = "ourairports:999"
    with pytest.raises(ValidationError, match="logical query ID"):
        LogicalAwardQuery.model_validate(raw)
    with pytest.raises(AttributeError, match="date_envelope"):
        _logical_query_identity_payload(deepcopy(raw))  # type: ignore[arg-type]


def test_typed_path_keeps_strict_cabin_value_access() -> None:
    typed = LogicalAwardQuery.model_validate(_query())
    malformed = typed.model_copy(update={"requested_cabins": ("business",)})
    with pytest.raises(AttributeError, match="value"):
        _logical_query_identity_payload(malformed)
