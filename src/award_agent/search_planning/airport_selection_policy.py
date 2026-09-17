"""Versioned category caps for model-proposed endpoint-airport selection.

This policy is a product decision, not geographic evidence. In particular, an
override only changes the number of candidates a selector may propose; it does
not name airport membership or imply an airport serves an entity.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path

from pydantic import Field, model_validator

from award_agent.domain import LocationKind
from award_agent.search_planning.contracts import PlanningContractModel, ResolvedLocation
from award_agent.search_planning.knowledge import (
    GeoEntity,
    GeoEntitySelectionMetadata,
    PlanningKnowledgeRepository,
)


class AirportSelectionCategory(str, Enum):
    """Deterministic selection-cap categories, distinct from ``LocationKind``."""

    CITY_METROPOLITAN = "city_metropolitan"
    SUB_COUNTRY_REGION = "sub_country_region"
    COUNTRY = "country"
    INTERNATIONAL_REGION = "international_region"
    REGION_UNSPECIFIED = "region_unspecified"


class SelectionCategoryBasis(str, Enum):
    """Why an entity received its selection-cap category."""

    ENTITY_KIND = "entity_kind"
    CATALOG_TAXONOMY = "catalog_taxonomy"
    BROAD_FALLBACK = "broad_fallback"


class ResolvedEntityContext(PlanningContractModel):
    """Read-only post-resolution projection used by a selector.

    It intentionally leaves ``LocationRef`` and the clarification boundary
    untouched. The category is computed from the already resolved catalog
    entity, so a model cannot choose a broader category to obtain a larger cap.
    """

    entity_id: str = Field(min_length=1)
    entity_kind: LocationKind
    label: str = Field(min_length=1)
    taxonomy_id: str | None = None
    feature_code: str | None = None
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    evidence_source_ids: tuple[str, ...] = Field(min_length=1)
    category: AirportSelectionCategory
    category_basis: SelectionCategoryBasis

    @model_validator(mode="after")
    def validate_context(self) -> ResolvedEntityContext:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("resolved-entity coordinates must be present together")
        if self.entity_kind is LocationKind.CITY:
            expected = AirportSelectionCategory.CITY_METROPOLITAN
        elif self.entity_kind is LocationKind.COUNTRY:
            expected = AirportSelectionCategory.COUNTRY
        elif self.entity_kind is LocationKind.REGION:
            expected = None
        else:
            raise ValueError("resolved entity context cannot represent an airport")
        if expected is not None and self.category is not expected:
            raise ValueError("entity kind and airport-selection category disagree")
        return self


def classify_resolved_entity(
    entity: GeoEntity, metadata: GeoEntitySelectionMetadata | None = None
) -> ResolvedEntityContext:
    """Classify a canonical entity without reinterpreting request text.

    A generic geographic region intentionally falls back to the broad cap. The
    fallback is an explicit recordable outcome rather than an error or an
    unsupported claim that the region is international.
    """

    if metadata is not None and metadata.entity_id != entity.entity_id:
        raise ValueError("selector metadata must name the resolved entity")
    if entity.kind is LocationKind.CITY:
        category = AirportSelectionCategory.CITY_METROPOLITAN
        basis = SelectionCategoryBasis.ENTITY_KIND
    elif entity.kind is LocationKind.COUNTRY:
        category = AirportSelectionCategory.COUNTRY
        basis = SelectionCategoryBasis.ENTITY_KIND
    elif entity.kind is LocationKind.REGION:
        if metadata is not None and metadata.taxonomy_id in {"geonames:admin1", "geonames:admin2"}:
            category = AirportSelectionCategory.SUB_COUNTRY_REGION
            basis = SelectionCategoryBasis.CATALOG_TAXONOMY
        elif metadata is not None and metadata.taxonomy_id == "geonames:continent":
            category = AirportSelectionCategory.INTERNATIONAL_REGION
            basis = SelectionCategoryBasis.CATALOG_TAXONOMY
        else:
            category = AirportSelectionCategory.REGION_UNSPECIFIED
            basis = SelectionCategoryBasis.BROAD_FALLBACK
    else:
        raise ValueError("airport selection context requires a geographic entity")
    return ResolvedEntityContext(
        entity_id=entity.entity_id,
        entity_kind=entity.kind,
        label=entity.label,
        taxonomy_id=None if metadata is None else metadata.taxonomy_id,
        feature_code=None if metadata is None else metadata.feature_code,
        country_code=None if metadata is None else metadata.country_code,
        latitude=None if metadata is None else metadata.latitude,
        longitude=None if metadata is None else metadata.longitude,
        evidence_source_ids=entity.source_ids,
        category=category,
        category_basis=basis,
    )


def context_for_resolved_location(
    resolution: ResolvedLocation, repository: PlanningKnowledgeRepository
) -> ResolvedEntityContext:
    """Project only an already-resolved geographic location into selector context."""

    if resolution.resolved_entity_id is None:
        raise ValueError("selector context requires a resolved geographic entity")
    entity = repository.get_entity(resolution.resolved_entity_id)
    if entity is None:  # Defensive: the repository validated the resolution.
        raise ValueError("resolved entity is absent from the catalog")
    context = classify_resolved_entity(
        entity, repository.entity_selection_metadata(entity.entity_id)
    )
    return context.model_copy(
        update={
            "evidence_source_ids": tuple(
                sorted(set(context.evidence_source_ids) | set(resolution.evidence_source_ids))
            )
        }
    )


class AirportSelectionCapOverride(PlanningContractModel):
    """One canonical-entity cap exception; never a text-match or membership rule."""

    entity_id: str = Field(min_length=1)
    category: AirportSelectionCategory
    cap: int = Field(ge=1, le=20)


class AirportSelectionCapSource(str, Enum):
    DEFAULT = "default"
    CANONICAL_ENTITY_OVERRIDE = "canonical_entity_override"


class ApplicableAirportSelectionCap(PlanningContractModel):
    cap: int = Field(ge=1, le=20)
    category: AirportSelectionCategory
    source: AirportSelectionCapSource
    policy_version: str = Field(min_length=1)
    override_entity_id: str | None = None

    @model_validator(mode="after")
    def validate_override_shape(self) -> ApplicableAirportSelectionCap:
        if (self.source is AirportSelectionCapSource.CANONICAL_ENTITY_OVERRIDE) != (
            self.override_entity_id is not None
        ):
            raise ValueError("cap override source and entity identity must agree")
        return self


class AirportSelectionCapPolicy(PlanningContractModel):
    """Versioned cap-only policy for a model-proposed selection.

    ``region_unspecified`` deliberately uses the broad eight-airport fallback:
    inability to refine catalog taxonomy is not an error and does not give the
    model authority to choose a category.
    """

    policy_version: str = Field(min_length=1)
    city_metropolitan_default_cap: int = Field(default=2, ge=1, le=20)
    sub_country_region_default_cap: int = Field(default=4, ge=1, le=20)
    country_default_cap: int = Field(default=4, ge=1, le=20)
    international_region_default_cap: int = Field(default=8, ge=1, le=20)
    region_unspecified_default_cap: int = Field(default=8, ge=1, le=20)
    overrides: tuple[AirportSelectionCapOverride, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def canonicalize_override_order(cls, value: object) -> object:
        if not isinstance(value, dict) or not isinstance(value.get("overrides"), (list, tuple)):
            return value
        copied = dict(value)
        copied["overrides"] = sorted(
            copied["overrides"],
            key=lambda item: (
                (
                    str(item.get("entity_id", ""))
                    if isinstance(item, dict)
                    else item.entity_id
                    if isinstance(item, AirportSelectionCapOverride)
                    else ""
                ),
                (
                    str(item.get("category", ""))
                    if isinstance(item, dict)
                    else item.category.value
                    if isinstance(item, AirportSelectionCapOverride)
                    else ""
                ),
            ),
        )
        return copied

    @model_validator(mode="after")
    def validate_overrides(self) -> AirportSelectionCapPolicy:
        keys = tuple((override.entity_id, override.category) for override in self.overrides)
        if len(keys) != len(set(keys)):
            raise ValueError(
                "airport-selection cap overrides must be unique by entity and category"
            )
        for override in self.overrides:
            if override.cap <= self.default_cap_for(override.category):
                raise ValueError(
                    "airport-selection cap overrides must be larger than their default"
                )
        return self

    def default_cap_for(self, category: AirportSelectionCategory) -> int:
        return {
            AirportSelectionCategory.CITY_METROPOLITAN: self.city_metropolitan_default_cap,
            AirportSelectionCategory.SUB_COUNTRY_REGION: self.sub_country_region_default_cap,
            AirportSelectionCategory.COUNTRY: self.country_default_cap,
            AirportSelectionCategory.INTERNATIONAL_REGION: self.international_region_default_cap,
            AirportSelectionCategory.REGION_UNSPECIFIED: self.region_unspecified_default_cap,
        }[category]

    def applicable_cap_for(self, context: ResolvedEntityContext) -> ApplicableAirportSelectionCap:
        override = next(
            (
                candidate
                for candidate in self.overrides
                if candidate.entity_id == context.entity_id
                and candidate.category is context.category
            ),
            None,
        )
        if override is not None:
            return ApplicableAirportSelectionCap(
                cap=override.cap,
                category=context.category,
                source=AirportSelectionCapSource.CANONICAL_ENTITY_OVERRIDE,
                policy_version=self.policy_version,
                override_entity_id=override.entity_id,
            )
        return ApplicableAirportSelectionCap(
            cap=self.default_cap_for(context.category),
            category=context.category,
            source=AirportSelectionCapSource.DEFAULT,
            policy_version=self.policy_version,
        )


def airport_selection_cap_policy_digest(policy: AirportSelectionCapPolicy) -> str:
    """Stable policy identity for a future immutable selection record."""

    rendered = json.dumps(
        policy.model_dump(mode="json", round_trip=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def default_airport_selection_cap_policy_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "data"
        / "search_planning"
        / "v2"
        / "airport-selection-cap-policy-v1.json"
    )


def load_airport_selection_cap_policy(path: Path) -> AirportSelectionCapPolicy:
    with path.open(encoding="utf-8") as file:
        return AirportSelectionCapPolicy.model_validate(json.load(file))


def load_default_airport_selection_cap_policy() -> AirportSelectionCapPolicy:
    return load_airport_selection_cap_policy(default_airport_selection_cap_policy_path())
