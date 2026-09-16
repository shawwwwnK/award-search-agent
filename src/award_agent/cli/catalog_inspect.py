"""Inspection-only CLI for one explicitly selected catalog release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from award_agent.domain import LocationKind
from award_agent.search_planning.knowledge import (
    CatalogKnowledgeRepository,
    normalize_location_alias,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect a validated local catalog release")
    parser.add_argument(
        "release", type=Path, help="explicit release directory containing manifest.json"
    )
    query = parser.add_mutually_exclusive_group()
    query.add_argument(
        "--alias", help="exact alias to inspect (normalization is documented in receipt)"
    )
    query.add_argument("--entity", help="canonical entity ID")
    query.add_argument("--airport", help="airport IATA code or canonical airport ID")
    query.add_argument("--source-record", help="catalog source_record_key")
    parser.add_argument(
        "--taxonomy",
        help="named region taxonomy; requires --alias and performs a scoped exact lookup",
    )
    return parser


def _models(values: object) -> object:
    if isinstance(values, tuple):
        return [_models(item) for item in values]
    if hasattr(values, "model_dump"):
        return values.model_dump(mode="json")
    return values


def inspect_catalog(
    release: Path,
    *,
    alias: str | None = None,
    entity: str | None = None,
    airport: str | None = None,
    taxonomy: str | None = None,
    source_record: str | None = None,
) -> dict[str, Any]:
    """Return read-only catalog inspection data; it never invokes planning."""

    with CatalogKnowledgeRepository(release) as repository:
        receipt = repository.knowledge_receipt.model_dump(mode="json")
        if taxonomy is not None:
            if alias is None:
                raise ValueError("--taxonomy requires --alias")
            return {
                "knowledge_receipt": receipt,
                "lookup": _models(
                    repository.lookup_exact_location(
                        LocationKind.REGION,
                        alias,
                        taxonomy_id=taxonomy,
                    )
                ),
            }
        if alias is not None:
            normalized = normalize_location_alias(alias)
            return {
                "knowledge_receipt": receipt,
                "normalized_alias": normalized,
                "lookups": {
                    kind.value: _models(repository.lookup_exact_location(kind, alias))
                    for kind in (LocationKind.COUNTRY, LocationKind.CITY, LocationKind.REGION)
                },
                "airport_lookup": _models(
                    repository.lookup_exact_location(LocationKind.AIRPORT, alias)
                ),
            }
        if entity is not None:
            record = repository.get_entity(entity)
            return {
                "knowledge_receipt": receipt,
                "entity": _models(record),
                "taxonomy": None if record is None else repository.taxonomy_for_entity(entity),
                "source_records": _models(repository.source_records_for_entity(entity)),
            }
        if airport is not None:
            airport_record = (
                repository.lookup_airport_iata(airport.upper())
                if len(airport) == 3 and airport.isascii() and airport.isalpha()
                else repository.airport(airport)
            )
            return {
                "knowledge_receipt": receipt,
                "airport": _models(airport_record),
                "source_records": _models(
                    ()
                    if airport_record is None
                    else repository.source_records_for_airport(airport_record.airport_id)
                ),
            }
        if source_record is not None:
            return {
                "knowledge_receipt": receipt,
                "source_record": _models(repository.source_record(source_record)),
            }
        return {"knowledge_receipt": receipt, "taxonomy_ids": list(repository.taxonomy_ids())}


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    if args.taxonomy is not None and args.alias is None:
        parser.error("--taxonomy requires --alias")
    print(
        json.dumps(
            inspect_catalog(
                args.release,
                alias=args.alias,
                entity=args.entity,
                airport=args.airport,
                taxonomy=args.taxonomy,
                source_record=args.source_record,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
