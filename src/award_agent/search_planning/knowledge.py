"""Reviewed JSON knowledge snapshots for search planning.

This is intentionally a local, versioned retrieval boundary.  It does not
consult provider markets, web services, or model output at runtime.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable
from datetime import date
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from award_agent.domain import LocationKind
from award_agent.search_planning.contracts import FreshnessClass, PlanningContractModel


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
