"""Reviewed JSON knowledge snapshots for search planning.

This is intentionally a local, versioned retrieval boundary.  It does not
consult provider markets, web services, or model output at runtime.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from collections.abc import Iterable
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Protocol, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from award_agent.domain import LocationKind
from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    CatalogSourceArtifactReceipt,
    FreshnessClass,
    KnowledgeReceipt,
    PlanningContractModel,
)


def normalize_location_alias(value: str) -> str:
    """Apply only NFKC, case folding, and whitespace normalization.

    Alias evidence is deliberately exact beyond those transformations.  In
    particular, this does not strip diacritics, transliterate, or perform a
    second semantic interpretation of a model-proposed location value.
    """

    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _canonical_aliases(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(normalize_location_alias(value) for value in values)
    if any(not value for value in normalized):
        raise ValueError("aliases must be nonempty after normalization")
    if len(normalized) != len(set(normalized)):
        raise ValueError("aliases must be unique after normalization")
    return tuple(sorted(normalized))


def _canonical_source_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = tuple(value.strip() for value in values)
    if any(not value for value in cleaned):
        raise ValueError("source IDs must be nonempty")
    if len(cleaned) != len(set(cleaned)):
        raise ValueError("source IDs must be unique")
    return tuple(sorted(cleaned))


class KnowledgeSource(PlanningContractModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    license_note: str = Field(min_length=1)
    verified_on: date
    version_or_capture_id: str = Field(min_length=1)
    verification_scope: str = Field(min_length=1)


class SnapshotMetadata(PlanningContractModel):
    snapshot_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    as_of: date
    verification_date: date
    coverage_statement: str = Field(min_length=1)

    @model_validator(mode="after")
    def verify_dates(self) -> SnapshotMetadata:
        if self.verification_date > self.as_of:
            raise ValueError("snapshot verification_date cannot be after as_of")
        return self


class GeoEntity(PlanningContractModel):
    entity_id: str = Field(min_length=1)
    kind: LocationKind
    label: str = Field(min_length=1)
    aliases: tuple[str, ...] = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)

    _canonicalize_aliases = field_validator("aliases")(_canonical_aliases)
    _canonicalize_source_ids = field_validator("source_ids")(_canonical_source_ids)


class Airport(PlanningContractModel):
    airport_id: str = Field(min_length=1)
    iata: str = Field(pattern=r"^[A-Z]{3}$")
    label: str = Field(min_length=1)
    country_entity_id: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    aliases: tuple[str, ...] = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)

    _canonicalize_aliases = field_validator("aliases")(_canonical_aliases)
    _canonicalize_source_ids = field_validator("source_ids")(_canonical_source_ids)

    @model_validator(mode="after")
    def validate_timezone(self) -> Airport:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown airport IANA timezone: {self.timezone}") from exc
        return self


class LocationAirportRelationKind(str, Enum):
    WITHIN_GEOGRAPHY = "within_geography"
    SERVES_CITY = "serves_city"


class LocationAirportRelation(PlanningContractModel):
    relation_id: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    airport_id: str = Field(min_length=1)
    kind: LocationAirportRelationKind
    source_ids: tuple[str, ...] = Field(min_length=1)

    _canonicalize_source_ids = field_validator("source_ids")(_canonical_source_ids)


class AirportSelectionPolicy(PlanningContractModel):
    policy_id: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    entity_kind: LocationKind
    airport_ids: tuple[str, ...] = Field(min_length=1)
    selection_reason: str = Field(min_length=1)
    cap: int = Field(ge=1, le=5)
    source_ids: tuple[str, ...] = Field(min_length=1)

    _canonicalize_source_ids = field_validator("source_ids")(_canonical_source_ids)

    @model_validator(mode="after")
    def validate_policy_cap(self) -> AirportSelectionPolicy:
        if len(self.airport_ids) > self.cap:
            raise ValueError("selection policy cannot name more airports than its cap")
        if len(self.airport_ids) != len(set(self.airport_ids)):
            raise ValueError("selection policy airport IDs must be unique")
        return self


class RouteEvidenceKind(str, Enum):
    """How a directed topology edge may be used by the planner.

    Synthetic edges exist solely in offline tests.  They are deliberately
    carried in the same contract so test fixtures cannot accidentally look
    like operational route evidence.
    """

    SYNTHETIC_TEST_FIXTURE = "synthetic_test_fixture"
    REVIEWED_TOPOLOGY = "reviewed_topology"


class RouteDateApplicability(str, Enum):
    """What the reviewed topology evidence says about operating-date coverage."""

    KNOWN_INCLUSIVE_INTERVAL = "known_inclusive_interval"
    UNKNOWN = "unknown"


class DirectedRouteEdge(PlanningContractModel):
    """Evidence of one physical directed airport-to-airport topology edge.

    This is not schedule, availability, ticketing, or connection evidence.
    The direction is material: the repository never infers its reverse.
    """

    edge_id: str = Field(min_length=1)
    origin_airport_id: str = Field(min_length=1)
    destination_airport_id: str = Field(min_length=1)
    evidence_kind: RouteEvidenceKind
    source_ids: tuple[str, ...] = Field(min_length=1)
    date_applicability: RouteDateApplicability = RouteDateApplicability.UNKNOWN
    applicable_start: date | None = None
    applicable_end: date | None = None

    _canonicalize_source_ids = field_validator("source_ids")(_canonical_source_ids)

    @model_validator(mode="after")
    def validate_distinct_airports(self) -> DirectedRouteEdge:
        if self.origin_airport_id == self.destination_airport_id:
            raise ValueError("directed route edge cannot be a self-loop")
        known_interval = self.date_applicability is RouteDateApplicability.KNOWN_INCLUSIVE_INTERVAL
        if known_interval != (
            self.applicable_start is not None and self.applicable_end is not None
        ):
            raise ValueError("route applicability must be a complete interval or explicit unknown")
        if (
            self.applicable_start is not None
            and self.applicable_end is not None
            and self.applicable_end < self.applicable_start
        ):
            raise ValueError("route applicability end precedes start")
        return self


class KnowledgeSnapshot(PlanningContractModel):
    metadata: SnapshotMetadata
    sources: tuple[KnowledgeSource, ...] = Field(min_length=1)
    entities: tuple[GeoEntity, ...] = Field(min_length=1)
    airports: tuple[Airport, ...] = Field(min_length=1)
    relations: tuple[LocationAirportRelation, ...] = ()
    selection_policies: tuple[AirportSelectionPolicy, ...] = ()
    route_edges: tuple[DirectedRouteEdge, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def canonicalize_record_order(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        copied = dict(value)
        record_keys = {
            "sources": "source_id",
            "entities": "entity_id",
            "airports": "airport_id",
            "relations": "relation_id",
            "selection_policies": "policy_id",
            "route_edges": "edge_id",
        }
        for key, id_key in record_keys.items():
            records = copied.get(key)
            if isinstance(records, (list, tuple)):
                copied[key] = sorted(records, key=lambda item: str(item.get(id_key, "")))
        return copied

    @model_validator(mode="after")
    def validate_references(self) -> KnowledgeSnapshot:
        _require_unique((source.source_id for source in self.sources), "source IDs")
        _require_unique((entity.entity_id for entity in self.entities), "entity IDs")
        _require_unique((airport.airport_id for airport in self.airports), "airport IDs")
        _require_unique((airport.iata for airport in self.airports), "airport IATA codes")
        _require_unique((relation.relation_id for relation in self.relations), "relation IDs")
        _require_unique(
            (policy.policy_id for policy in self.selection_policies), "selection policy IDs"
        )
        _require_unique((edge.edge_id for edge in self.route_edges), "route edge IDs")

        source_ids = {source.source_id for source in self.sources}
        entity_by_id = {entity.entity_id: entity for entity in self.entities}
        airport_ids = {airport.airport_id for airport in self.airports}
        for record_name, records in (
            ("entity", self.entities),
            ("airport", self.airports),
            ("relation", self.relations),
            ("selection policy", self.selection_policies),
            ("route edge", self.route_edges),
        ):
            for record in records:
                unknown_sources = set(record.source_ids) - source_ids
                if unknown_sources:
                    raise ValueError(
                        f"{record_name} cites unknown sources: {sorted(unknown_sources)}"
                    )
        for airport in self.airports:
            if airport.country_entity_id not in entity_by_id:
                raise ValueError(f"airport {airport.airport_id} cites unknown country entity")
            if entity_by_id[airport.country_entity_id].kind is not LocationKind.COUNTRY:
                raise ValueError(
                    f"airport {airport.airport_id} country link must cite a country entity"
                )
        future_sources = [
            source.source_id for source in self.sources if source.verified_on > self.metadata.as_of
        ]
        if future_sources:
            raise ValueError(
                f"source verification dates cannot be after snapshot as_of: {sorted(future_sources)}"
            )
        relation_pairs = {(relation.entity_id, relation.airport_id) for relation in self.relations}
        if len(relation_pairs) != len(self.relations):
            raise ValueError("entity-airport relation pairs must be unique")
        for relation in self.relations:
            if relation.entity_id not in entity_by_id or relation.airport_id not in airport_ids:
                raise ValueError(f"relation {relation.relation_id} has an unknown endpoint")
        for policy in self.selection_policies:
            entity = entity_by_id.get(policy.entity_id)
            if entity is None:
                raise ValueError(f"selection policy {policy.policy_id} cites unknown entity")
            if entity.kind is not policy.entity_kind:
                raise ValueError(f"selection policy {policy.policy_id} has an entity-kind mismatch")
            for airport_id in policy.airport_ids:
                if airport_id not in airport_ids:
                    raise ValueError(f"selection policy {policy.policy_id} cites unknown airport")
                if (policy.entity_id, airport_id) not in relation_pairs:
                    raise ValueError(
                        f"selection policy {policy.policy_id} needs a factual entity-airport relation"
                    )
        edge_pairs = {
            (edge.origin_airport_id, edge.destination_airport_id) for edge in self.route_edges
        }
        if len(edge_pairs) != len(self.route_edges):
            raise ValueError("directed route edge pairs must be unique")
        for edge in self.route_edges:
            if (
                edge.origin_airport_id not in airport_ids
                or edge.destination_airport_id not in airport_ids
            ):
                raise ValueError(f"route edge {edge.edge_id} has an unknown airport endpoint")
        return self


def _require_unique(values: Iterable[str], label: str) -> None:
    rendered: tuple[str, ...] = tuple(values)
    if len(rendered) != len(set(rendered)):
        raise ValueError(f"{label} must be unique")


class PlanningKnowledgeRepository(Protocol):
    """Structural, read-only retrieval seam consumed by planning.

    Both the small reviewed JSON snapshot and the operational SQLite catalog
    implement this surface.  It deliberately contains no provider, fuzzy,
    airport-service inference, or write operation.
    """

    @property
    def snapshot_id(self) -> str: ...

    @property
    def snapshot_as_of(self) -> date: ...

    @property
    def knowledge_receipt(self) -> KnowledgeReceipt | CatalogKnowledgeReceipt: ...

    def freshness_for_source_ids(
        self, source_ids: Iterable[str], *, max_source_evidence_age_days: int
    ) -> FreshnessClass: ...

    def resolve_entities(
        self, kind: LocationKind, normalized_alias: str
    ) -> tuple[GeoEntity, ...]: ...

    def resolve_airports_by_alias(self, normalized_alias: str) -> tuple[Airport, ...]: ...

    def alias_exists_for_other_kind(self, kind: LocationKind, normalized_alias: str) -> bool: ...

    def airport_metadata_missing_for_alias(self, normalized_alias: str) -> bool: ...

    def lookup_airport_iata(self, iata: str) -> Airport | None: ...

    def get_entity(self, entity_id: str) -> GeoEntity | None: ...

    def relations_for(self, entity_id: str) -> tuple[LocationAirportRelation, ...]: ...

    def relation_for(self, entity_id: str, airport_id: str) -> LocationAirportRelation | None: ...

    def policy_for(self, entity_id: str, kind: LocationKind) -> AirportSelectionPolicy | None: ...

    def airport(self, airport_id: str) -> Airport | None: ...

    def route_edge(
        self, origin_airport_id: str, destination_airport_id: str
    ) -> DirectedRouteEdge | None: ...

    def outgoing_route_edges(
        self, origin_airport_id: str, *, limit: int
    ) -> tuple[tuple[DirectedRouteEdge, ...], bool]: ...


class KnowledgeRepository:
    """Read-only deterministic retrieval over one validated snapshot."""

    def __init__(self, snapshot: KnowledgeSnapshot) -> None:
        self.snapshot = snapshot
        self._entities = {entity.entity_id: entity for entity in snapshot.entities}
        self._airports = {airport.airport_id: airport for airport in snapshot.airports}
        self._airports_by_iata = {airport.iata: airport for airport in snapshot.airports}
        self._relations = tuple(snapshot.relations)
        self._policies = tuple(snapshot.selection_policies)
        self._route_edges = tuple(snapshot.route_edges)
        self._route_edges_by_pair = {
            (edge.origin_airport_id, edge.destination_airport_id): edge
            for edge in snapshot.route_edges
        }
        outgoing: dict[str, list[DirectedRouteEdge]] = {}
        for edge in sorted(
            snapshot.route_edges,
            key=lambda edge: (edge.origin_airport_id, edge.destination_airport_id, edge.edge_id),
        ):
            outgoing.setdefault(edge.origin_airport_id, []).append(edge)
        self._outgoing_route_edges = {
            origin_airport_id: tuple(edges) for origin_airport_id, edges in outgoing.items()
        }

    @property
    def snapshot_id(self) -> str:
        return self.snapshot.metadata.snapshot_id

    @property
    def snapshot_as_of(self) -> date:
        return self.snapshot.metadata.as_of

    @property
    def knowledge_receipt(self) -> KnowledgeReceipt:
        return KnowledgeReceipt(
            snapshot_id=self.snapshot.metadata.snapshot_id,
            schema_version=self.snapshot.metadata.schema_version,
            snapshot_as_of=self.snapshot.metadata.as_of,
            content_sha256=knowledge_content_digest(self.snapshot),
            source_ids=tuple(sorted(source.source_id for source in self.snapshot.sources)),
        )

    def freshness_for_source_ids(
        self,
        source_ids: Iterable[str],
        *,
        max_source_evidence_age_days: int,
    ) -> FreshnessClass:
        """Aggregate freshness for the evidence used by one planning result.

        Freshness is evaluated against the snapshot's pinned ``as_of`` date,
        never the wall clock.  Callers must provide the source IDs that their
        result actually relies on; unrelated snapshot sources must not make a
        grounded endpoint stale.  An empty set is current because there is no
        evidence claim to invalidate (for example, an unresolved alias).
        """

        requested_ids = tuple(sorted(set(source_ids)))
        sources_by_id = {source.source_id: source for source in self.snapshot.sources}
        unknown_ids = set(requested_ids) - sources_by_id.keys()
        if unknown_ids:
            raise ValueError(f"freshness requested for unknown source IDs: {sorted(unknown_ids)}")

        as_of = self.snapshot.metadata.as_of
        return (
            FreshnessClass.STALE
            if any(
                (as_of - sources_by_id[source_id].verified_on).days > max_source_evidence_age_days
                for source_id in requested_ids
            )
            else FreshnessClass.CURRENT
        )

    def resolve_entities(self, kind: LocationKind, normalized_alias: str) -> tuple[GeoEntity, ...]:
        return tuple(
            entity
            for entity in self.snapshot.entities
            if entity.kind is kind
            and normalized_alias in {normalize_location_alias(alias) for alias in entity.aliases}
        )

    def resolve_airports_by_alias(self, normalized_alias: str) -> tuple[Airport, ...]:
        return tuple(
            airport
            for airport in self.snapshot.airports
            if normalized_alias
            in {normalize_location_alias(alias) for alias in (*airport.aliases, airport.iata)}
        )

    def alias_exists_for_other_kind(self, kind: LocationKind, normalized_alias: str) -> bool:
        if kind is LocationKind.AIRPORT:
            return any(
                normalized_alias in {normalize_location_alias(alias) for alias in entity.aliases}
                for entity in self.snapshot.entities
            )
        return bool(self.resolve_airports_by_alias(normalized_alias)) or any(
            entity.kind is not kind
            and normalized_alias in {normalize_location_alias(alias) for alias in entity.aliases}
            for entity in self.snapshot.entities
        )

    def airport_metadata_missing_for_alias(self, normalized_alias: str) -> bool:
        # Snapshot validation proves every airport has its required country
        # entity and timezone metadata before this read-only repository exists.
        return False

    def lookup_airport_iata(self, iata: str) -> Airport | None:
        return self._airports_by_iata.get(iata)

    def get_entity(self, entity_id: str) -> GeoEntity | None:
        return self._entities.get(entity_id)

    def relations_for(self, entity_id: str) -> tuple[LocationAirportRelation, ...]:
        return tuple(relation for relation in self._relations if relation.entity_id == entity_id)

    def relation_for(self, entity_id: str, airport_id: str) -> LocationAirportRelation | None:
        return next(
            (
                relation
                for relation in self._relations
                if relation.entity_id == entity_id and relation.airport_id == airport_id
            ),
            None,
        )

    def policy_for(self, entity_id: str, kind: LocationKind) -> AirportSelectionPolicy | None:
        return next(
            (
                policy
                for policy in self._policies
                if policy.entity_id == entity_id and policy.entity_kind is kind
            ),
            None,
        )

    def airport(self, airport_id: str) -> Airport | None:
        return self._airports.get(airport_id)

    def route_edge(
        self, origin_airport_id: str, destination_airport_id: str
    ) -> DirectedRouteEdge | None:
        """Return only the explicitly recorded direction; never infer reverse edges."""

        return self._route_edges_by_pair.get((origin_airport_id, destination_airport_id))

    def outgoing_route_edges(
        self, origin_airport_id: str, *, limit: int
    ) -> tuple[tuple[DirectedRouteEdge, ...], bool]:
        """Return at most ``limit`` directed edges and a deterministic overflow bit.

        The caller applies this per requested endpoint pair.  A route catalog
        may have many outgoing edges; this repository boundary prevents an
        optional exploration from becoming an unbounded scan.
        """

        if limit < 0:
            raise ValueError("outgoing route edge limit cannot be negative")
        edges = self._outgoing_route_edges.get(origin_airport_id, ())
        bounded = edges[: limit + 1]
        return bounded[:limit], len(bounded) > limit

    def intermediate_airport_ids(self, origin_airport_id: str) -> tuple[str, ...]:
        """Compatibility helper for callers that do not need retrieval receipts."""

        edges, _ = self.outgoing_route_edges(origin_airport_id, limit=len(self._route_edges))
        return tuple(edge.destination_airport_id for edge in edges)


class CatalogSourceRecord(PlanningContractModel):
    """Inspectable provenance for one source-record evidence identifier."""

    source_record_key: str
    artifact_name: str
    source_record_id: str
    compact_row_id: str
    source_schema_name: str | None = None
    source_headers: tuple[str, ...] = ()
    raw_values: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_lossless_payload(self) -> CatalogSourceRecord:
        if bool(self.source_headers) != bool(self.raw_values):
            raise ValueError("catalog source payload needs both headers and values")
        if self.source_headers and len(self.source_headers) != len(self.raw_values):
            raise ValueError("catalog source payload headers and values must align")
        return self


class CatalogLookupStatus(str, Enum):
    """Explicit exact-catalog inspection outcomes; never a fuzzy fallback."""

    RESOLVED = "resolved"
    NOT_FOUND = "not_found"
    KIND_MISMATCH = "kind_mismatch"
    TAXONOMY_MISMATCH = "taxonomy_mismatch"
    AMBIGUOUS = "ambiguous"
    MISSING_METADATA = "missing_metadata"


class CatalogLookupCandidate(PlanningContractModel):
    """A deterministic exact-match candidate with source-record evidence."""

    candidate_id: str
    kind: LocationKind
    label: str
    taxonomy_id: str | None = None
    evidence_source_ids: tuple[str, ...]

    @model_validator(mode="after")
    def canonical_evidence(self) -> CatalogLookupCandidate:
        if not self.evidence_source_ids or self.evidence_source_ids != tuple(
            sorted(set(self.evidence_source_ids))
        ):
            raise ValueError("catalog lookup evidence source IDs must be sorted and nonempty")
        return self


class CatalogLocationLookup(PlanningContractModel):
    """Typed result for a narrow exact location/taxonomy inspection query."""

    normalized_alias: str
    requested_kind: LocationKind
    requested_taxonomy_id: str | None = None
    status: CatalogLookupStatus
    candidates: tuple[CatalogLookupCandidate, ...] = ()

    @model_validator(mode="after")
    def validate_status_shape(self) -> CatalogLocationLookup:
        if self.status is CatalogLookupStatus.RESOLVED and len(self.candidates) != 1:
            raise ValueError("a resolved catalog lookup requires exactly one candidate")
        if self.status is CatalogLookupStatus.AMBIGUOUS and len(self.candidates) < 2:
            raise ValueError("an ambiguous catalog lookup requires multiple candidates")
        if self.status is CatalogLookupStatus.TAXONOMY_MISMATCH and not self.candidates:
            raise ValueError("a taxonomy mismatch requires supported candidates")
        if self.status is CatalogLookupStatus.KIND_MISMATCH and not self.candidates:
            raise ValueError("a kind mismatch requires supported candidates")
        return self


class CatalogKnowledgeRepository:
    """Read one selected validated catalog release through SQLite read-only mode.

    The release is validated before the connection is opened.  This class never
    selects a release, reads raw importer inputs, or creates group/route policy
    from catalog facts.  The catalog has no such policy records in 1B.
    """

    def __init__(self, release_path: Path) -> None:
        # Import lazily: the publication module imports alias normalization from
        # this module, so a module-level import would create a cycle.
        from award_agent.catalog.publication import (  # pylint: disable=import-outside-toplevel
            DATABASE_FILENAME,
            MANIFEST_FILENAME,
            validate_release,
        )

        self.release_path = Path(release_path)
        manifest = validate_release(self.release_path)
        self._manifest = manifest
        manifest_path = self.release_path / MANIFEST_FILENAME
        self._manifest_sha256 = _file_sha256(manifest_path)
        self._database_path = self.release_path / DATABASE_FILENAME
        self._connection = sqlite3.connect(
            f"file:{self._database_path}?mode=ro", uri=True, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        # Defend the query surface as well as the URI mode; this also protects
        # against future accidental mutating SQL in this repository.
        self._connection.execute("PRAGMA query_only = ON")
        self._has_source_schema = (
            self._connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'source_schema'"
            ).fetchone()
            is not None
        )
        source_date = date.fromisoformat(manifest["publication_context"]["source_date"])
        artifacts = tuple(
            CatalogSourceArtifactReceipt(
                artifact_name=name,
                bytes=receipt["bytes"],
                sha256=receipt["sha256"],
            )
            for name, receipt in sorted(manifest["source_bundle"]["output_receipts"].items())
        )
        self._knowledge_receipt = CatalogKnowledgeReceipt(
            release_id=manifest["release_id"],
            schema_version=manifest["catalog_schema_version"],
            source_date=source_date,
            logical_content_sha256=manifest["logical_content_sha256"],
            manifest_sha256=self._manifest_sha256,
            database_sha256=manifest["database"]["sha256"],
            source_bundle_manifest_sha256=manifest["source_bundle"]["manifest_sha256"],
            source_artifacts=artifacts,
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _source_record_model(row: sqlite3.Row) -> CatalogSourceRecord:
        data = dict(row)
        headers_json = data.pop("headers_json", None)
        values_json = data.pop("raw_values_json", None)
        data["source_headers"] = () if headers_json is None else tuple(json.loads(headers_json))
        data["raw_values"] = () if values_json is None else tuple(json.loads(values_json))
        return CatalogSourceRecord.model_validate(data)

    def _source_record_projection(self) -> str:
        fields = "s.source_record_key, s.artifact_name, s.source_record_id, s.compact_row_id"
        if self._has_source_schema:
            return f"{fields}, s.source_schema_name, s.raw_values_json, schema.headers_json"
        return (
            f"{fields}, NULL AS source_schema_name, NULL AS raw_values_json, NULL AS headers_json"
        )

    @property
    def snapshot_id(self) -> str:
        return self._knowledge_receipt.release_id

    @property
    def snapshot_as_of(self) -> date:
        return self._knowledge_receipt.source_date

    @property
    def knowledge_receipt(self) -> CatalogKnowledgeReceipt:
        return self._knowledge_receipt

    def freshness_for_source_ids(
        self,
        source_ids: Iterable[str],
        *,
        max_source_evidence_age_days: int,
    ) -> FreshnessClass:
        """Validate query evidence against the release's pinned source date.

        Publication has already accepted each retained source record into this
        release.  There is no per-record wall-clock freshness claim; unknown
        evidence is rejected rather than treated as current.
        """

        if max_source_evidence_age_days < 0:
            raise ValueError("maximum source evidence age cannot be negative")
        requested = tuple(sorted(set(source_ids)))
        unknown: list[str] = []
        # SQLite bounds host parameters, and a request should only validate its
        # own evidence.  Do not build an in-memory index over every catalog
        # source record merely to reject an unknown query-time ID.
        for start in range(0, len(requested), 500):
            batch = requested[start : start + 500]
            placeholders = ",".join("?" for _ in batch)
            known = {
                row[0]
                for row in self._connection.execute(
                    f"SELECT source_record_key FROM source_record "
                    f"WHERE source_record_key IN ({placeholders})",
                    batch,
                )
            }
            unknown.extend(source_id for source_id in batch if source_id not in known)
        if unknown:
            raise ValueError(f"freshness requested for unknown source IDs: {unknown}")
        return FreshnessClass.CURRENT

    def resolve_entities(self, kind: LocationKind, normalized_alias: str) -> tuple[GeoEntity, ...]:
        rows = self._connection.execute(
            """SELECT e.*, a.display_alias, a.source_record_key AS alias_source_record_key
               FROM entity AS e
               JOIN entity_alias_evidence AS a ON a.entity_id = e.entity_id
               WHERE e.entity_kind = ? AND a.normalized_alias = ?
               ORDER BY e.entity_id, a.alias_evidence_id""",
            (kind.value, normalized_alias),
        ).fetchall()
        return self._entities_from_alias_rows(rows)

    def resolve_airports_by_alias(self, normalized_alias: str) -> tuple[Airport, ...]:
        rows = self._connection.execute(
            """SELECT airport_id, '' AS alias_source_record_key
                 FROM airport WHERE iata_code = ?
               UNION ALL
               SELECT airport_id, source_record_key AS alias_source_record_key
                 FROM airport_alias WHERE normalized_alias = ?
               ORDER BY airport_id, alias_source_record_key""",
            (normalized_alias.upper(), normalized_alias),
        ).fetchall()
        grouped: dict[str, list[str]] = {}
        for row in rows:
            source = str(row["alias_source_record_key"])
            grouped.setdefault(str(row["airport_id"]), []).extend((source,) if source else ())
        return tuple(
            airport
            for airport_id, alias_sources in sorted(grouped.items())
            if (airport := self._airport_by_id(airport_id, tuple(alias_sources))) is not None
        )

    def alias_exists_for_other_kind(self, kind: LocationKind, normalized_alias: str) -> bool:
        if kind is LocationKind.AIRPORT:
            return (
                self._connection.execute(
                    "SELECT 1 FROM entity_alias_evidence WHERE normalized_alias = ? LIMIT 1",
                    (normalized_alias,),
                ).fetchone()
                is not None
            )
        return (
            self._connection.execute(
                """SELECT 1 FROM airport_alias WHERE normalized_alias = ? LIMIT 1""",
                (normalized_alias,),
            ).fetchone()
            is not None
            or self._connection.execute(
                """SELECT 1 FROM entity AS e JOIN entity_alias_evidence AS a
                   ON a.entity_id = e.entity_id
                   WHERE a.normalized_alias = ? AND e.entity_kind != ? LIMIT 1""",
                (normalized_alias, kind.value),
            ).fetchone()
            is not None
        )

    def airport_metadata_missing_for_alias(self, normalized_alias: str) -> bool:
        return (
            self._connection.execute(
                """SELECT 1 FROM airport AS airport
               WHERE (
                 airport.iata_code = ?
                 OR airport.airport_id IN (
                   SELECT airport_id FROM airport_alias WHERE normalized_alias = ?
                 )
               ) AND 1 != (
                 SELECT COUNT(*) FROM entity
                  WHERE entity.entity_kind = 'country'
                    AND entity.country_code = airport.iso_country
               ) LIMIT 1""",
                (normalized_alias.upper(), normalized_alias),
            ).fetchone()
            is not None
        )

    def lookup_airport_iata(self, iata: str) -> Airport | None:
        row = self._connection.execute(
            "SELECT airport_id FROM airport WHERE iata_code = ?", (iata,)
        ).fetchone()
        return None if row is None else self._airport_by_id(row["airport_id"])

    def get_entity(self, entity_id: str) -> GeoEntity | None:
        row = self._connection.execute(
            "SELECT * FROM entity WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        return None if row is None else self._entity_from_row(row, ())

    def taxonomy_for_entity(self, entity_id: str) -> str | None:
        row = self._connection.execute(
            "SELECT taxonomy_id FROM entity WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        return None if row is None else str(row["taxonomy_id"])

    def taxonomy_ids(self) -> tuple[str, ...]:
        return tuple(
            row[0]
            for row in self._connection.execute(
                "SELECT taxonomy_id FROM taxonomy ORDER BY taxonomy_id"
            )
        )

    def lookup_exact_location(
        self,
        kind: LocationKind,
        alias: str,
        *,
        taxonomy_id: str | None = None,
    ) -> CatalogLocationLookup:
        """Inspect one exact normalized alias with an optional named taxonomy.

        Taxonomy selection is only meaningful for regions.  This is an
        inspection/query surface, deliberately separate from the existing
        planner's semantic ``LocationRef`` contract, which has no taxonomy
        selector yet.
        """

        if taxonomy_id is not None and kind is not LocationKind.REGION:
            raise ValueError("a named taxonomy lookup requires region kind")
        normalized = normalize_location_alias(alias)
        entity_candidates = self._entity_alias_candidates(normalized)
        airport_candidates, airport_missing_metadata = self._airport_alias_candidates(normalized)
        all_candidates = tuple(
            sorted(
                (*entity_candidates, *airport_candidates),
                key=lambda candidate: (
                    candidate.kind.value,
                    candidate.taxonomy_id or "",
                    candidate.candidate_id,
                ),
            )
        )
        requested = tuple(candidate for candidate in all_candidates if candidate.kind is kind)
        if taxonomy_id is not None:
            taxonomy_exists = self._connection.execute(
                "SELECT 1 FROM taxonomy WHERE taxonomy_id = ?", (taxonomy_id,)
            ).fetchone()
            if taxonomy_exists is None:
                return CatalogLocationLookup(
                    normalized_alias=normalized,
                    requested_kind=kind,
                    requested_taxonomy_id=taxonomy_id,
                    status=CatalogLookupStatus.MISSING_METADATA,
                )
            scoped = tuple(
                candidate for candidate in requested if candidate.taxonomy_id == taxonomy_id
            )
            if scoped:
                return self._lookup_result(
                    normalized,
                    kind,
                    taxonomy_id,
                    scoped,
                    missing_metadata=False,
                )
            if requested:
                return CatalogLocationLookup(
                    normalized_alias=normalized,
                    requested_kind=kind,
                    requested_taxonomy_id=taxonomy_id,
                    status=CatalogLookupStatus.TAXONOMY_MISMATCH,
                    candidates=requested,
                )
            if all_candidates:
                return CatalogLocationLookup(
                    normalized_alias=normalized,
                    requested_kind=kind,
                    requested_taxonomy_id=taxonomy_id,
                    status=CatalogLookupStatus.KIND_MISMATCH,
                    candidates=all_candidates,
                )
            return CatalogLocationLookup(
                normalized_alias=normalized,
                requested_kind=kind,
                requested_taxonomy_id=taxonomy_id,
                status=CatalogLookupStatus.NOT_FOUND,
            )
        if requested:
            return self._lookup_result(
                normalized,
                kind,
                None,
                requested,
                missing_metadata=kind is LocationKind.AIRPORT and airport_missing_metadata,
            )
        if all_candidates:
            return CatalogLocationLookup(
                normalized_alias=normalized,
                requested_kind=kind,
                status=CatalogLookupStatus.KIND_MISMATCH,
                candidates=all_candidates,
            )
        return CatalogLocationLookup(
            normalized_alias=normalized,
            requested_kind=kind,
            status=CatalogLookupStatus.NOT_FOUND,
        )

    def source_record(self, source_record_key: str) -> CatalogSourceRecord | None:
        row = self._connection.execute(
            f"""SELECT {self._source_record_projection()}
                FROM source_record AS s
                {"LEFT JOIN source_schema AS schema ON schema.source_name = s.source_schema_name" if self._has_source_schema else ""}
                WHERE s.source_record_key = ?""",
            (source_record_key,),
        ).fetchone()
        return None if row is None else self._source_record_model(row)

    def source_records_for_entity(self, entity_id: str) -> tuple[CatalogSourceRecord, ...]:
        rows = self._connection.execute(
            f"""SELECT DISTINCT {self._source_record_projection()}
               FROM source_record AS s
               {"LEFT JOIN source_schema AS schema ON schema.source_name = s.source_schema_name" if self._has_source_schema else ""}
               WHERE s.source_record_key = (SELECT source_record_key FROM entity WHERE entity_id = ?)
                  OR s.source_record_key IN (
                    SELECT source_record_key FROM entity_alias_evidence WHERE entity_id = ?
                  )
               ORDER BY s.source_record_key""",
            (entity_id, entity_id),
        ).fetchall()
        return tuple(self._source_record_model(row) for row in rows)

    def source_records_for_airport(self, airport_id: str) -> tuple[CatalogSourceRecord, ...]:
        rows = self._connection.execute(
            f"""SELECT DISTINCT {self._source_record_projection()}
               FROM source_record AS s
               {"LEFT JOIN source_schema AS schema ON schema.source_name = s.source_schema_name" if self._has_source_schema else ""}
               WHERE s.source_record_key IN (
                 SELECT source_record_key FROM airport WHERE airport_id = ?
                 UNION SELECT source_record_key FROM airport_alias WHERE airport_id = ?
                 UNION SELECT candidate.source_record_key
                   FROM airport_reconciliation AS r
                   JOIN geonames_airport_candidate AS candidate ON candidate.candidate_id = r.candidate_id
                  WHERE r.airport_id = ?
                 UNION SELECT evidence.source_record_key
                   FROM airport_reconciliation AS r
                   JOIN geonames_iata_evidence AS evidence ON evidence.evidence_id = r.evidence_id
                  WHERE r.airport_id = ?
                 UNION SELECT country.source_record_key
                   FROM airport AS endpoint
                   JOIN entity AS country
                     ON country.entity_kind = 'country'
                    AND country.country_code = endpoint.iso_country
                  WHERE endpoint.airport_id = ?
               ) ORDER BY s.source_record_key""",
            (airport_id, airport_id, airport_id, airport_id, airport_id),
        ).fetchall()
        return tuple(self._source_record_model(row) for row in rows)

    # Deliberately empty: catalog facts must not be mistaken for reviewed
    # airport groups or topology evidence.
    def relations_for(self, entity_id: str) -> tuple[LocationAirportRelation, ...]:
        return ()

    def relation_for(self, entity_id: str, airport_id: str) -> LocationAirportRelation | None:
        return None

    def policy_for(self, entity_id: str, kind: LocationKind) -> AirportSelectionPolicy | None:
        return None

    def airport(self, airport_id: str) -> Airport | None:
        return self._airport_by_id(airport_id)

    def route_edge(
        self, origin_airport_id: str, destination_airport_id: str
    ) -> DirectedRouteEdge | None:
        return None

    def outgoing_route_edges(
        self, origin_airport_id: str, *, limit: int
    ) -> tuple[tuple[DirectedRouteEdge, ...], bool]:
        if limit < 0:
            raise ValueError("outgoing route edge limit cannot be negative")
        return (), False

    def _entities_from_alias_rows(self, rows: list[sqlite3.Row]) -> tuple[GeoEntity, ...]:
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(str(row["entity_id"]), []).append(row)
        return tuple(
            self._entity_from_row(group[0], tuple(row["alias_source_record_key"] for row in group))
            for _, group in sorted(grouped.items())
        )

    def _entity_alias_candidates(self, normalized_alias: str) -> tuple[CatalogLookupCandidate, ...]:
        rows = self._connection.execute(
            """SELECT entity.entity_id, entity.entity_kind, entity.label, entity.taxonomy_id,
                      entity.source_record_key, alias.source_record_key AS alias_source_record_key
               FROM entity
               JOIN entity_alias_evidence AS alias ON alias.entity_id = entity.entity_id
               WHERE alias.normalized_alias = ?
               ORDER BY entity.entity_kind, entity.taxonomy_id, entity.entity_id,
                        alias.alias_evidence_id""",
            (normalized_alias,),
        ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(str(row["entity_id"]), []).append(row)
        return tuple(
            CatalogLookupCandidate(
                candidate_id=entity_id,
                kind=LocationKind(group[0]["entity_kind"]),
                label=group[0]["label"],
                taxonomy_id=group[0]["taxonomy_id"],
                evidence_source_ids=tuple(
                    sorted(
                        {
                            group[0]["source_record_key"],
                            *(row["alias_source_record_key"] for row in group),
                        }
                    )
                ),
            )
            for entity_id, group in sorted(grouped.items())
        )

    def _airport_alias_candidates(
        self, normalized_alias: str
    ) -> tuple[tuple[CatalogLookupCandidate, ...], bool]:
        rows = self._connection.execute(
            """SELECT airport.airport_id, airport.name, airport.source_record_key,
                      1 = (
                        SELECT COUNT(*) FROM entity
                         WHERE entity.entity_kind = 'country'
                           AND entity.country_code = airport.iso_country
                      ) AS country_metadata_present,
                      '' AS alias_source_record_key
                 FROM airport WHERE airport.iata_code = ?
               UNION ALL
               SELECT airport.airport_id, airport.name, airport.source_record_key,
                      1 = (
                        SELECT COUNT(*) FROM entity
                         WHERE entity.entity_kind = 'country'
                           AND entity.country_code = airport.iso_country
                      ) AS country_metadata_present,
                      alias.source_record_key AS alias_source_record_key
                 FROM airport
                 JOIN airport_alias AS alias ON alias.airport_id = airport.airport_id
                WHERE alias.normalized_alias = ?
               ORDER BY airport_id, alias_source_record_key""",
            (normalized_alias.upper(), normalized_alias),
        ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(str(row["airport_id"]), []).append(row)
        candidates = tuple(
            CatalogLookupCandidate(
                candidate_id=airport_id,
                kind=LocationKind.AIRPORT,
                label=group[0]["name"],
                evidence_source_ids=tuple(
                    sorted(
                        {
                            group[0]["source_record_key"],
                            *(
                                row["alias_source_record_key"]
                                for row in group
                                if row["alias_source_record_key"]
                            ),
                        }
                    )
                ),
            )
            for airport_id, group in sorted(grouped.items())
        )
        missing_metadata = any(
            not bool(group[0]["country_metadata_present"]) for group in grouped.values()
        )
        return candidates, missing_metadata

    def _lookup_result(
        self,
        normalized_alias: str,
        kind: LocationKind,
        taxonomy_id: str | None,
        candidates: tuple[CatalogLookupCandidate, ...],
        *,
        missing_metadata: bool,
    ) -> CatalogLocationLookup:
        status = (
            CatalogLookupStatus.MISSING_METADATA
            if missing_metadata
            else (
                CatalogLookupStatus.RESOLVED
                if len(candidates) == 1
                else CatalogLookupStatus.AMBIGUOUS
            )
        )
        return CatalogLocationLookup(
            normalized_alias=normalized_alias,
            requested_kind=kind,
            requested_taxonomy_id=taxonomy_id,
            status=status,
            candidates=candidates,
        )

    def _entity_from_row(self, row: sqlite3.Row, alias_sources: tuple[str, ...]) -> GeoEntity:
        return GeoEntity(
            entity_id=row["entity_id"],
            kind=LocationKind(row["entity_kind"]),
            label=row["label"],
            aliases=(row["label"],),
            source_ids=tuple(sorted({row["source_record_key"], *alias_sources})),
        )

    def _airport_by_id(
        self, airport_id: str, alias_sources: tuple[str, ...] = ()
    ) -> Airport | None:
        row = self._connection.execute(
            """SELECT airport.*, candidate.source_record_key AS candidate_source_record_key,
                      evidence.source_record_key AS evidence_source_record_key
               FROM airport
               JOIN airport_reconciliation AS reconciliation
                 ON reconciliation.airport_id = airport.airport_id
               JOIN geonames_airport_candidate AS candidate
                 ON candidate.candidate_id = reconciliation.candidate_id
               JOIN geonames_iata_evidence AS evidence
                 ON evidence.evidence_id = reconciliation.evidence_id
               WHERE airport.airport_id = ?""",
            (airport_id,),
        ).fetchone()
        if row is None:
            return None
        country = self._connection.execute(
            """SELECT entity_id, source_record_key FROM entity
               WHERE entity_kind = 'country' AND country_code = ?
               ORDER BY entity_id""",
            (row["iso_country"],),
        ).fetchall()
        if len(country) != 1:
            return None
        return Airport(
            airport_id=row["airport_id"],
            iata=row["iata_code"],
            label=row["name"],
            country_entity_id=str(country[0]["entity_id"]),
            timezone=row["timezone"],
            aliases=(row["name"],),
            source_ids=tuple(
                sorted(
                    {
                        row["source_record_key"],
                        row["candidate_source_record_key"],
                        row["evidence_source_record_key"],
                        country[0]["source_record_key"],
                        *alias_sources,
                    }
                )
            ),
        )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_knowledge_snapshot(path: Path) -> KnowledgeSnapshot:
    """Load one local JSON snapshot and fail on malformed or dangling evidence."""

    with path.open(encoding="utf-8") as file:
        document = json.load(file)
    return KnowledgeSnapshot.model_validate(document)


def knowledge_content_digest(snapshot: KnowledgeSnapshot) -> str:
    """Return the canonical content fingerprint for identity and stale-plan checks."""

    rendered = json.dumps(
        snapshot.model_dump(mode="json", round_trip=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def default_snapshot_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "data"
        / "search_planning"
        / "v1"
        / "knowledge_snapshot.json"
    )


def load_default_knowledge_snapshot() -> KnowledgeSnapshot:
    return load_knowledge_snapshot(default_snapshot_path())
