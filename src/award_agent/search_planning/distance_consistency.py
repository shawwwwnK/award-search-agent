"""Non-serving geographic distance consistency for model-proposed airports."""

from __future__ import annotations

from enum import Enum
from math import asin, cos, radians, sin, sqrt

from pydantic import Field

from award_agent.search_planning.airport_selection_policy import (
    AirportSelectionCategory,
    ResolvedEntityContext,
)
from award_agent.search_planning.contracts import PlanningContractModel
from award_agent.search_planning.knowledge import AirportSelectionMetadata


class CityAirportDistanceStatus(str, Enum):
    """Distance consistency is deliberately not city-serving verification."""

    WITHIN_POLICY_DISTANCE = "within_policy_distance"
    OUTSIDE_POLICY_DISTANCE = "outside_policy_distance"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class CityAirportDistanceConsistency(PlanningContractModel):
    """A permissive, versioned city-only consistency threshold."""

    policy_version: str = Field(min_length=1)
    maximum_distance_km: float = Field(default=200.0, gt=0, le=1000)


class CityAirportDistanceAssessment(PlanningContractModel):
    entity_id: str = Field(min_length=1)
    airport_id: str = Field(min_length=1)
    status: CityAirportDistanceStatus
    distance_km: float | None = Field(default=None, ge=0)
    threshold_km: float | None = Field(default=None, gt=0)
    policy_version: str = Field(min_length=1)


def great_circle_distance_km(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    """Return a deterministic haversine distance using the conventional 6371 km radius."""

    latitude_delta = radians(second_latitude - first_latitude)
    longitude_delta = radians(second_longitude - first_longitude)
    first_latitude_radians = radians(first_latitude)
    second_latitude_radians = radians(second_latitude)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(first_latitude_radians) * cos(second_latitude_radians) * sin(longitude_delta / 2) ** 2
    )
    return 2 * 6371.0 * asin(sqrt(min(1.0, max(0.0, haversine))))


def assess_city_airport_distance(
    context: ResolvedEntityContext,
    airport: AirportSelectionMetadata,
    policy: CityAirportDistanceConsistency,
) -> CityAirportDistanceAssessment:
    """Assess only city contexts; do not extrapolate center distance to regions.

    Callers decide whether an outside-distance outcome rejects a candidate. This
    helper purposefully does not make that product decision or claim that a
    within-distance airport serves the city.
    """

    if context.category is not AirportSelectionCategory.CITY_METROPOLITAN:
        return CityAirportDistanceAssessment(
            entity_id=context.entity_id,
            airport_id=airport.airport_id,
            status=CityAirportDistanceStatus.NOT_APPLICABLE,
            policy_version=policy.policy_version,
        )
    if context.latitude is None or context.longitude is None:
        return CityAirportDistanceAssessment(
            entity_id=context.entity_id,
            airport_id=airport.airport_id,
            status=CityAirportDistanceStatus.UNAVAILABLE,
            policy_version=policy.policy_version,
        )
    distance_km = great_circle_distance_km(
        context.latitude,
        context.longitude,
        airport.latitude,
        airport.longitude,
    )
    return CityAirportDistanceAssessment(
        entity_id=context.entity_id,
        airport_id=airport.airport_id,
        status=(
            CityAirportDistanceStatus.WITHIN_POLICY_DISTANCE
            if distance_km <= policy.maximum_distance_km
            else CityAirportDistanceStatus.OUTSIDE_POLICY_DISTANCE
        ),
        distance_km=distance_km,
        threshold_km=policy.maximum_distance_km,
        policy_version=policy.policy_version,
    )
