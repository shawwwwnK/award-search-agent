"""Offline checks for deterministic 2A selector context and policy foundations."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from award_agent.domain import LocationKind
from award_agent.search_planning import (
    AirportSelectionCapOverride,
    AirportSelectionCapPolicy,
    AirportSelectionCapSource,
    AirportSelectionCategory,
    AirportSelectionMetadata,
    CityAirportDistanceConsistency,
    CityAirportDistanceStatus,
    GeoEntity,
    GeoEntitySelectionMetadata,
    airport_selection_cap_policy_digest,
    assess_city_airport_distance,
    classify_resolved_entity,
    load_default_airport_selection_cap_policy,
)


def _entity(
    kind: LocationKind,
    *,
    entity_id: str = "geonames:example",
) -> GeoEntity:
    return GeoEntity(
        entity_id=entity_id,
        kind=kind,
        label="Example",
        aliases=("Example",),
        source_ids=("source:example",),
    )


def _metadata(
    *,
    entity_id: str = "geonames:example",
    taxonomy_id: str = "geonames:populated_place",
    latitude: float | None = 37.6213,
    longitude: float | None = -122.379,
) -> GeoEntitySelectionMetadata:
    return GeoEntitySelectionMetadata(
        entity_id=entity_id,
        taxonomy_id=taxonomy_id,
        country_code="US",
        latitude=latitude,
        longitude=longitude,
    )


def _airport(*, latitude: float = 37.6213, longitude: float = -122.379) -> AirportSelectionMetadata:
    return AirportSelectionMetadata(
        airport_id="airport:SFO",
        country_code="US",
        iso_region="US-CA",
        airport_type="large_airport",
        latitude=latitude,
        longitude=longitude,
    )


@pytest.mark.parametrize(
    ("entity", "metadata", "category", "basis"),
    [
        (
            _entity(LocationKind.CITY),
            _metadata(taxonomy_id="geonames:populated_place"),
            AirportSelectionCategory.CITY_METROPOLITAN,
            "entity_kind",
        ),
        (
            _entity(LocationKind.COUNTRY),
            _metadata(taxonomy_id="geonames:country"),
            AirportSelectionCategory.COUNTRY,
            "entity_kind",
        ),
        (
            _entity(LocationKind.REGION),
            _metadata(taxonomy_id="geonames:admin1"),
            AirportSelectionCategory.SUB_COUNTRY_REGION,
            "catalog_taxonomy",
        ),
        (
            _entity(LocationKind.REGION),
            _metadata(taxonomy_id="geonames:admin2"),
            AirportSelectionCategory.SUB_COUNTRY_REGION,
            "catalog_taxonomy",
        ),
        (
            _entity(LocationKind.REGION),
            _metadata(taxonomy_id="geonames:continent"),
            AirportSelectionCategory.INTERNATIONAL_REGION,
            "catalog_taxonomy",
        ),
        (
            _entity(LocationKind.REGION),
            _metadata(taxonomy_id="geonames:geographic_region"),
            AirportSelectionCategory.REGION_UNSPECIFIED,
            "broad_fallback",
        ),
    ],
)
def test_catalog_entity_classification_is_deterministic_and_records_its_basis(
    entity: GeoEntity,
    metadata: GeoEntitySelectionMetadata,
    category: AirportSelectionCategory,
    basis: str,
) -> None:
    context = classify_resolved_entity(entity, metadata)

    assert context.category is category
    assert context.category_basis.value == basis
    assert context.entity_id == entity.entity_id
    assert context.latitude == metadata.latitude


def test_unspecified_region_is_not_an_error_and_uses_the_broad_cap() -> None:
    context = classify_resolved_entity(
        _entity(LocationKind.REGION),
        _metadata(taxonomy_id="geonames:geographic_region"),
    )
    policy = load_default_airport_selection_cap_policy()

    applicable = policy.applicable_cap_for(context)

    assert applicable.cap == 8
    assert applicable.category is AirportSelectionCategory.REGION_UNSPECIFIED
    assert applicable.source is AirportSelectionCapSource.DEFAULT
    assert applicable.override_entity_id is None


def test_default_category_caps_and_canonical_entity_override_are_separate() -> None:
    city = classify_resolved_entity(
        _entity(LocationKind.CITY, entity_id="geonames:2643743"),
        _metadata(entity_id="geonames:2643743"),
    )
    another_city = classify_resolved_entity(
        _entity(LocationKind.CITY, entity_id="geonames:other"),
        _metadata(entity_id="geonames:other"),
    )
    policy = AirportSelectionCapPolicy(
        policy_version="test-v1",
        overrides=(
            AirportSelectionCapOverride(
                entity_id="geonames:2643743",
                category=AirportSelectionCategory.CITY_METROPOLITAN,
                cap=5,
            ),
        ),
    )

    override = policy.applicable_cap_for(city)
    default = policy.applicable_cap_for(another_city)

    assert override.cap == 5
    assert override.source is AirportSelectionCapSource.CANONICAL_ENTITY_OVERRIDE
    assert default.cap == 2
    assert default.source is AirportSelectionCapSource.DEFAULT


@pytest.mark.parametrize(
    ("entity_id", "kind", "category", "cap"),
    [
        (
            "geonames:1269750",
            LocationKind.COUNTRY,
            AirportSelectionCategory.COUNTRY,
            6,
        ),
        (
            "geonames:1814991",
            LocationKind.COUNTRY,
            AirportSelectionCategory.COUNTRY,
            6,
        ),
        (
            "geonames:2643743",
            LocationKind.CITY,
            AirportSelectionCategory.CITY_METROPOLITAN,
            5,
        ),
        (
            "geonames:5128581",
            LocationKind.CITY,
            AirportSelectionCategory.CITY_METROPOLITAN,
            3,
        ),
        (
            "geonames:5368361",
            LocationKind.CITY,
            AirportSelectionCategory.CITY_METROPOLITAN,
            5,
        ),
        (
            "geonames:5391959",
            LocationKind.CITY,
            AirportSelectionCategory.CITY_METROPOLITAN,
            3,
        ),
        (
            "geonames:6252001",
            LocationKind.COUNTRY,
            AirportSelectionCategory.COUNTRY,
            10,
        ),
    ],
)
def test_default_policy_applies_approved_canonical_entity_cap_exceptions(
    entity_id: str,
    kind: LocationKind,
    category: AirportSelectionCategory,
    cap: int,
) -> None:
    context = classify_resolved_entity(
        _entity(kind, entity_id=entity_id), _metadata(entity_id=entity_id)
    )

    applicable = load_default_airport_selection_cap_policy().applicable_cap_for(context)

    assert applicable.category is category
    assert applicable.cap == cap
    assert applicable.source is AirportSelectionCapSource.CANONICAL_ENTITY_OVERRIDE
    assert applicable.override_entity_id == entity_id


def test_default_policy_has_exactly_the_approved_override_set() -> None:
    policy = load_default_airport_selection_cap_policy()

    assert {
        (override.entity_id, override.category.value, override.cap) for override in policy.overrides
    } == {
        ("geonames:5391959", "city_metropolitan", 3),
        ("geonames:5128581", "city_metropolitan", 3),
        ("geonames:2643743", "city_metropolitan", 5),
        ("geonames:5368361", "city_metropolitan", 5),
        ("geonames:6252001", "country", 10),
        ("geonames:1814991", "country", 6),
        ("geonames:1269750", "country", 6),
    }


def test_default_policy_digest_is_pinned_for_selection_record_replay() -> None:
    assert airport_selection_cap_policy_digest(load_default_airport_selection_cap_policy()) == (
        "a3b493cc8c271e78217d99dcc89bcfa7eb8089bb7310a6f2489ae5d9cd915256"
    )


def test_default_policy_leaves_an_ordinary_city_at_the_category_default() -> None:
    context = classify_resolved_entity(
        _entity(LocationKind.CITY, entity_id="geonames:ordinary-city"),
        _metadata(entity_id="geonames:ordinary-city"),
    )
    policy = load_default_airport_selection_cap_policy()

    applicable = policy.applicable_cap_for(context)

    assert policy.city_metropolitan_default_cap == 2
    assert applicable.cap == 2
    assert applicable.source is AirportSelectionCapSource.DEFAULT
    assert applicable.override_entity_id is None


@pytest.mark.parametrize(
    "overrides",
    [
        (
            AirportSelectionCapOverride(
                entity_id="geonames:1",
                category=AirportSelectionCategory.COUNTRY,
                cap=5,
            ),
            AirportSelectionCapOverride(
                entity_id="geonames:1",
                category=AirportSelectionCategory.COUNTRY,
                cap=6,
            ),
        ),
        (
            AirportSelectionCapOverride(
                entity_id="geonames:1",
                category=AirportSelectionCategory.COUNTRY,
                cap=4,
            ),
        ),
    ],
)
def test_cap_override_cannot_be_duplicate_or_nonexpanding(
    overrides: tuple[AirportSelectionCapOverride, ...],
) -> None:
    with pytest.raises(ValidationError):
        AirportSelectionCapPolicy(policy_version="test-v1", overrides=overrides)


def test_cap_policy_digest_is_stable_when_independent_overrides_are_reordered() -> None:
    first = AirportSelectionCapOverride(
        entity_id="geonames:1", category=AirportSelectionCategory.COUNTRY, cap=5
    )
    second = AirportSelectionCapOverride(
        entity_id="geonames:2", category=AirportSelectionCategory.COUNTRY, cap=6
    )

    forward = AirportSelectionCapPolicy(policy_version="test-v1", overrides=(first, second))
    reversed_order = AirportSelectionCapPolicy(policy_version="test-v1", overrides=(second, first))

    assert airport_selection_cap_policy_digest(forward) == airport_selection_cap_policy_digest(
        reversed_order
    )


def test_city_distance_is_a_permissive_consistency_signal_not_service_evidence() -> None:
    context = classify_resolved_entity(_entity(LocationKind.CITY), _metadata())
    assessment = assess_city_airport_distance(
        context,
        _airport(),
        CityAirportDistanceConsistency(policy_version="city-distance-v1"),
    )

    assert assessment.status is CityAirportDistanceStatus.WITHIN_POLICY_DISTANCE
    assert assessment.distance_km is not None and assessment.distance_km < 30
    assert assessment.threshold_km == 200


def test_city_distance_records_outside_missing_and_noncity_states() -> None:
    city = classify_resolved_entity(_entity(LocationKind.CITY), _metadata())
    policy = CityAirportDistanceConsistency(policy_version="city-distance-v1")

    outside = assess_city_airport_distance(
        city, _airport(latitude=51.47, longitude=-0.4543), policy
    )
    unavailable = assess_city_airport_distance(
        classify_resolved_entity(_entity(LocationKind.CITY)), _airport(), policy
    )
    noncity = assess_city_airport_distance(
        classify_resolved_entity(_entity(LocationKind.COUNTRY), _metadata()), _airport(), policy
    )

    assert outside.status is CityAirportDistanceStatus.OUTSIDE_POLICY_DISTANCE
    assert outside.distance_km is not None and outside.distance_km > 200
    assert unavailable.status is CityAirportDistanceStatus.UNAVAILABLE
    assert noncity.status is CityAirportDistanceStatus.NOT_APPLICABLE
