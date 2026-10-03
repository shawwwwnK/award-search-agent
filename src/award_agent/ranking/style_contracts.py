"""Immutable contracts for deterministic Ranking M2 solution styles."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import ClassVar, Literal

from pydantic import Field, model_validator

from award_agent.providers.contracts import RawField, Sha256, content_digest
from award_agent.search_planning.contracts import PlanningContractModel

from .contracts import MatchedJourneySet


def _nonnegative(value: Decimal) -> Decimal:
    if not value.is_finite() or value < 0:
        raise ValueError("style numeric values must be finite and nonnegative")
    return value


class RankingStylePolicy(PlanningContractModel):
    version: str = "ranking-m2-v1"
    time_factor: Decimal = Decimal("1.2")
    cost_factor: Decimal = Decimal(2)
    points_per_usd: Decimal = Decimal(100)
    unknown_tax_usd: Decimal = Decimal(150)

    @model_validator(mode="after")
    def valid_policy(self) -> RankingStylePolicy:
        if any(not value.is_finite() or value <= 0 for value in (
            self.time_factor, self.cost_factor, self.points_per_usd,
        )) or not self.unknown_tax_usd.is_finite() or self.unknown_tax_usd < 0:
            raise ValueError("ranking style policy requires finite positive factors")
        return self


class CurrencyConversionSnapshot(PlanningContractModel):
    snapshot_id: str = Field(min_length=1)
    as_of: date
    source: str = Field(min_length=1)
    source_digest: Sha256
    rates_to_usd: dict[str, Decimal]
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"rates_to_usd"})

    @model_validator(mode="after")
    def valid_rates(self) -> CurrencyConversionSnapshot:
        if self.rates_to_usd.get("USD") != Decimal(1):
            raise ValueError("USD conversion rate must equal exactly one")
        if any(len(currency) != 3 or not currency.isascii() or not currency.isupper()
               or not currency.isalpha() or not rate.is_finite() or rate <= 0
               for currency, rate in self.rates_to_usd.items()):
            raise ValueError("conversion rates require uppercase currencies and positive finite values")
        return self


class CostComponent(PlanningContractModel):
    kind: Literal["points", "award_taxes", "cash_fare"]
    state: Literal["observed", "estimated", "unavailable"]
    observation_id: str
    raw_amount: RawField
    raw_currency: RawField | None = None
    unit: str
    scope: Literal["per_traveler", "party", "unknown"]
    per_traveler_usd: Decimal | None = None
    exact_numerator: int | None = None
    exact_denominator: int | None = Field(default=None, gt=0)
    reason: str | None = None
    conversion_snapshot_id: str | None = None

    @model_validator(mode="after")
    def coherent_value(self) -> CostComponent:
        if (self.state == "unavailable") != (self.per_traveler_usd is None) or (
            (self.per_traveler_usd is None) != (self.exact_numerator is None)
            or (self.per_traveler_usd is None) != (self.exact_denominator is None)
        ):
            raise ValueError("cost component state disagrees with normalized value")
        if self.per_traveler_usd is not None:
            _nonnegative(self.per_traveler_usd)
        if self.exact_numerator is not None and self.exact_numerator < 0:
            raise ValueError("exact normalized cost must be nonnegative")
        if self.state == "unavailable" and not self.reason:
            raise ValueError("unavailable component requires a reason")
        return self


class JourneyCost(PlanningContractModel):
    components: tuple[CostComponent, ...]
    known_subtotal_usd: Decimal | None = None
    complete_usd: Decimal | None = None
    exact_subtotal_numerator: int | None = None
    exact_subtotal_denominator: int | None = Field(default=None, gt=0)
    missing_parts: tuple[str, ...]
    completeness: Literal["complete", "partial", "unavailable"]

    @model_validator(mode="after")
    def coherent_total(self) -> JourneyCost:
        if self.known_subtotal_usd is not None:
            _nonnegative(self.known_subtotal_usd)
        if self.complete_usd is not None:
            _nonnegative(self.complete_usd)
        if ((self.known_subtotal_usd is None) != (self.exact_subtotal_numerator is None)
            or (self.known_subtotal_usd is None) != (self.exact_subtotal_denominator is None)
        ):
            raise ValueError("cost subtotal requires an exact ratio receipt")
        if self.exact_subtotal_numerator is not None and self.exact_subtotal_numerator < 0:
            raise ValueError("exact subtotal must be nonnegative")
        if self.complete_usd is not None and self.complete_usd != self.known_subtotal_usd:
            raise ValueError("complete cost must equal its known subtotal")
        if (self.completeness == "complete") != (self.complete_usd is not None):
            raise ValueError("complete cost requires all normalized components")
        return self


class JourneyFeatures(PlanningContractModel):
    candidate_id: Sha256
    option_family_id: Sha256
    award_observation_id: str
    cash_observation_id: str | None
    topology: str
    status: Literal["admitted", "conditional", "rejected", "research_lead"]
    elapsed_minutes: Decimal | None
    elapsed_microseconds: int | None = Field(default=None, gt=0)
    transfer_minutes: int | None
    booking_obligation: str
    award_cabin: RawField
    premium_economy_addon: bool
    cost: JourneyCost

    @model_validator(mode="after")
    def coherent_elapsed(self) -> JourneyFeatures:
        if (self.elapsed_minutes is None) != (self.elapsed_microseconds is None):
            raise ValueError("elapsed display requires exact UTC microseconds")
        return self


class StyleAssessment(PlanningContractModel):
    candidate_id: Sha256
    style: Literal["time", "cost", "premium"]
    state: Literal["member", "possible", "not_member", "undetermined"]
    feature_numeric: Decimal | None = None
    feature_label: str | None = None
    reference_value: Decimal | None = None
    threshold: Decimal | None = None
    exact_threshold_numerator: int | None = None
    exact_threshold_denominator: int | None = Field(default=None, gt=0)
    exact_threshold_unit: Literal["microseconds", "usd"] | None = None
    reasons: tuple[str, ...] = ()
    validation_needs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def coherent_threshold(self) -> StyleAssessment:
        present = self.threshold is not None
        if any((value is not None) != present for value in (
            self.exact_threshold_numerator, self.exact_threshold_denominator,
            self.exact_threshold_unit,
        )):
            raise ValueError("display threshold requires exact ratio and unit")
        return self


class StyleIndexes(PlanningContractModel):
    time: tuple[Sha256, ...] = ()
    cost: tuple[Sha256, ...] = ()
    premium: tuple[Sha256, ...] = ()
    possible_cost: tuple[Sha256, ...] = ()
    premium_economy_addons: tuple[Sha256, ...] = ()
    definite_highlights: tuple[Sha256, ...] = ()
    possible_highlights: tuple[Sha256, ...] = ()
    other_alternatives: tuple[Sha256, ...] = ()
    excluded: tuple[Sha256, ...] = ()


class RankedJourneySet(PlanningContractModel):
    contract_version: Literal["ranked-journey-set-v1"] = "ranked-journey-set-v1"
    policy: RankingStylePolicy
    policy_digest: Sha256
    fx_snapshot: CurrencyConversionSnapshot
    fx_snapshot_digest: Sha256
    matched: MatchedJourneySet
    matched_digest: Sha256
    comparison_pool_ids: tuple[Sha256, ...]
    time_reference_minutes: Decimal | None
    time_reference_microseconds: int | None = Field(default=None, gt=0)
    cost_reference_usd: Decimal | None
    cost_reference_numerator: int | None = None
    cost_reference_denominator: int | None = Field(default=None, gt=0)
    features: tuple[JourneyFeatures, ...]
    assessments: tuple[StyleAssessment, ...]
    indexes: StyleIndexes
    derived_digest: Sha256

    @model_validator(mode="after")
    def verify_derivation(self) -> RankedJourneySet:
        if self.policy_digest != content_digest(self.policy) or (
            self.fx_snapshot_digest != content_digest(self.fx_snapshot)
            or self.matched_digest != content_digest(self.matched)
        ):
            raise ValueError("ranking source binding digest differs from attachment")
        from .styles import _derive_style_data

        expected = _derive_style_data(self.matched, self.policy, self.fx_snapshot)
        actual = {key: getattr(self, key) for key in expected}
        from .styles import _derived_digest

        if _derived_digest(actual) != self.derived_digest or actual != expected:
            raise ValueError("ranking derived features or indexes differ from source evidence")
        return self
