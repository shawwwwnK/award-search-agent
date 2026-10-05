"""Deterministic award-led matching, solution styles and factual exports."""

from .contracts import (
    MatchAccounting,
    MatchedJourney,
    MatchedJourneySet,
    MatchReason,
    PairingReceipt,
)
from .matching import assemble_matched_journeys
from .project_solutions import project_solutions
from .projection_contracts import ProjectionReceipt, SolutionProjection, SolutionView
from .style_contracts import CurrencyConversionSnapshot, RankedJourneySet, RankingStylePolicy
from .styles import assign_journey_styles

__all__ = [
    "CurrencyConversionSnapshot",
    "MatchAccounting",
    "MatchReason",
    "MatchedJourney",
    "MatchedJourneySet",
    "PairingReceipt",
    "ProjectionReceipt",
    "RankedJourneySet",
    "RankingStylePolicy",
    "SolutionProjection",
    "SolutionView",
    "assemble_matched_journeys",
    "assign_journey_styles",
    "project_solutions",
]
