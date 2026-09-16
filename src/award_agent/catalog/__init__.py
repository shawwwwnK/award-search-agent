"""Offline Milestone 1A catalog publication contracts.

This package deliberately publishes facts only.  It is not a planner repository
and does not select a release or expose airport-serving relationships.
"""

from award_agent.catalog.publication import (
    CatalogPublicationError,
    PublicationContext,
    PublicationResult,
    inspect_release,
    publish_catalog,
    validate_release,
)

__all__ = [
    "CatalogPublicationError",
    "PublicationContext",
    "PublicationResult",
    "inspect_release",
    "publish_catalog",
    "validate_release",
]
