"""Versioned planning-market policy and deterministic 2B generation gate.

Markets are product policy used only to decide whether optional gateway
generation may be skipped.  They are neither route evidence nor a claim that
an airport has a particular service pattern.  A missing mapping is preserved
as a receipt and requires (rather than prevents) the later grouped model call.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import ClassVar, Protocol

from pydantic import Field, model_validator

from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    PlanningContractModel,
    SelectedAirport,
)
from award_agent.search_planning.knowledge import AirportSelectionMetadata


class _AirportIdentity(Protocol):
    @property
    def iata(self) -> str: ...


class PlanningMarketCatalogRepository(Protocol):
    """The intentionally narrow catalog surface used by the market policy."""

    @property
    def knowledge_receipt(self) -> CatalogKnowledgeReceipt: ...

    def airport(self, airport_id: str) -> _AirportIdentity | None: ...

    def airport_selection_metadata(self, airport_id: str) -> AirportSelectionMetadata | None: ...


class PlanningMarket(PlanningContractModel):
    market_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    definition: str = Field(min_length=1)


class AirportMarketOverride(PlanningContractModel):
    """An exact catalog airport exception, never a geographic rewrite."""

    airport_id: str = Field(min_length=1)
    expected_iata: str = Field(pattern=r"^[A-Z]{3}$")
    expected_country_code: str = Field(pattern=r"^[A-Z]{2}$")
    expected_iso_region: str = Field(min_length=1)
    market_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")


class PlanningMarketPolicy(PlanningContractModel):
    """A catalog-authored, forward-compatible market classification overlay."""

    policy_version: str = Field(min_length=1)
    # Authoring identity is a replay/audit receipt. A later catalog can remain
    # compatible if every exact override still resolves to its expected facts.
    catalog_release_id: str = Field(min_length=1)
    catalog_logical_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    markets: tuple[PlanningMarket, ...] = Field(min_length=1)
    country_assignments: dict[str, str] = Field(min_length=1)
    explicit_unknown_country_codes: tuple[str, ...] = ()
    airport_overrides: tuple[AirportMarketOverride, ...] = ()
    # Drift guards are not range overrides: a new airport in one of these
    # regions is deliberately unknown until the exact override list is reviewed.
    override_coverage_regions: dict[str, str] = Field(default_factory=dict)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "markets",
            "country_assignments",
            "explicit_unknown_country_codes",
            "airport_overrides",
            "override_coverage_regions",
        }
    )

    @model_validator(mode="before")
    @classmethod
    def canonicalize_policy_collections(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        copied = dict(value)
        if isinstance(copied.get("markets"), (list, tuple)):
            copied["markets"] = sorted(
                copied["markets"],
                key=lambda item: item["market_id"] if isinstance(item, dict) else item.market_id,
            )
        if isinstance(copied.get("airport_overrides"), (list, tuple)):
            copied["airport_overrides"] = sorted(
                copied["airport_overrides"],
                key=lambda item: item["airport_id"] if isinstance(item, dict) else item.airport_id,
            )
        if isinstance(copied.get("explicit_unknown_country_codes"), (list, tuple)):
            copied["explicit_unknown_country_codes"] = sorted(copied["explicit_unknown_country_codes"])
        return copied

    @model_validator(mode="after")
    def validate_policy(self) -> PlanningMarketPolicy:
        market_ids = tuple(item.market_id for item in self.markets)
        if market_ids != tuple(sorted(set(market_ids))):
            raise ValueError("planning markets must have sorted, unique IDs")
        valid_markets = set(market_ids)
        for country_code, market_id in self.country_assignments.items():
            if len(country_code) != 2 or not country_code.isupper():
                raise ValueError("country assignment codes must be uppercase two-letter codes")
            if market_id not in valid_markets:
                raise ValueError("country assignment names an unknown market")
        unknown_codes = self.explicit_unknown_country_codes
        if unknown_codes != tuple(sorted(set(unknown_codes))) or any(
            len(code) != 2 or not code.isupper() for code in unknown_codes
        ):
            raise ValueError("explicit unknown country codes must be sorted unique two-letter codes")
        if set(unknown_codes) & set(self.country_assignments):
            raise ValueError("a country code cannot be both assigned and explicitly unknown")
        override_ids = tuple(item.airport_id for item in self.airport_overrides)
        if override_ids != tuple(sorted(set(override_ids))):
            raise ValueError("airport market overrides must have sorted, unique airport IDs")
        for override in self.airport_overrides:
            if override.market_id not in valid_markets:
                raise ValueError("airport override names an unknown market")
        for region, market_id in self.override_coverage_regions.items():
            if not region or market_id not in valid_markets:
                raise ValueError("override coverage region must name a known market")
        for override in self.airport_overrides:
            guarded_market = self.override_coverage_regions.get(override.expected_iso_region)
            if guarded_market is not None and override.market_id != guarded_market:
                raise ValueError(
                    "airport override in a guarded region must use that region's declared market"
                )
        return self


class MarketAssignmentSource(str, Enum):
    AIRPORT_OVERRIDE = "airport_override"
    COUNTRY_ASSIGNMENT = "country_assignment"
    EXPLICIT_UNKNOWN_COUNTRY = "explicit_unknown_country"
    UNMAPPED_COUNTRY = "unmapped_country"
    OVERRIDE_COVERAGE_DRIFT = "override_coverage_drift"


class AirportMarketAssignment(PlanningContractModel):
    role: str = Field(pattern=r"^(origin|destination)$")
    endpoint: SelectedAirport
    catalog_country_code: str = Field(pattern=r"^[A-Z]{2}$")
    catalog_iso_region: str = Field(min_length=1)
    market_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$")
    source: MarketAssignmentSource
    mapping_gap: bool
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"endpoint"})

    @model_validator(mode="after")
    def validate_mapping_shape(self) -> AirportMarketAssignment:
        known_sources = {
            MarketAssignmentSource.AIRPORT_OVERRIDE,
            MarketAssignmentSource.COUNTRY_ASSIGNMENT,
        }
        gap_sources = {
            MarketAssignmentSource.EXPLICIT_UNKNOWN_COUNTRY,
            MarketAssignmentSource.UNMAPPED_COUNTRY,
            MarketAssignmentSource.OVERRIDE_COVERAGE_DRIFT,
        }
        if self.source in known_sources and (self.mapping_gap or self.market_id is None):
            raise ValueError("known-market assignment source requires a market ID without a gap")
        if self.source in gap_sources and (not self.mapping_gap or self.market_id is not None):
            raise ValueError("mapping-gap assignment source cannot name a market")
        return self


class MarketPolicyCatalogCompatibility(PlanningContractModel):
    """Runtime catalog receipt plus whether it is the policy's authoring release."""

    authoring_release_id: str = Field(min_length=1)
    authoring_logical_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_catalog_receipt: CatalogKnowledgeReceipt
    authoring_identity_matches_runtime: bool
    override_metadata_validated: bool = True
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"runtime_catalog_receipt"})


class MarketGateIssueCode(str, Enum):
    EMPTY_ORIGIN_ENDPOINTS = "empty_origin_endpoints"
    EMPTY_DESTINATION_ENDPOINTS = "empty_destination_endpoints"
    DUPLICATE_ENDPOINT = "duplicate_endpoint"
    ENDPOINT_NOT_IN_CATALOG = "endpoint_not_in_catalog"
    ENDPOINT_IDENTITY_MISMATCH = "endpoint_identity_mismatch"
    MAPPING_GAP = "mapping_gap"


class MarketGateIssue(PlanningContractModel):
    code: MarketGateIssueCode
    message: str = Field(min_length=1)
    role: str | None = Field(default=None, pattern=r"^(origin|destination)$")
    airport_id: str | None = None
    airport_iata: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class MarketGenerationGateStatus(str, Enum):
    INPUT_ERROR = "input_error"
    SKIP_SINGLE_MARKET = "skip_single_market"
    GENERATION_REQUIRED = "generation_required"


class MarketGenerationGate(PlanningContractModel):
    """Deterministic pre-generator decision; it never makes a model call."""

    origin_endpoints: tuple[SelectedAirport, ...]
    destination_endpoints: tuple[SelectedAirport, ...]
    assignments: tuple[AirportMarketAssignment, ...] = ()
    compatibility: MarketPolicyCatalogCompatibility
    status: MarketGenerationGateStatus
    known_market_ids: tuple[str, ...] = ()
    issues: tuple[MarketGateIssue, ...] = ()
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"origin_endpoints", "destination_endpoints", "assignments", "compatibility", "issues"}
    )

    @model_validator(mode="after")
    def validate_gate(self) -> MarketGenerationGate:
        input_errors = {
            MarketGateIssueCode.EMPTY_ORIGIN_ENDPOINTS,
            MarketGateIssueCode.EMPTY_DESTINATION_ENDPOINTS,
            MarketGateIssueCode.DUPLICATE_ENDPOINT,
            MarketGateIssueCode.ENDPOINT_NOT_IN_CATALOG,
            MarketGateIssueCode.ENDPOINT_IDENTITY_MISMATCH,
        }
        has_input_error = any(item.code in input_errors for item in self.issues)
        if (self.status is MarketGenerationGateStatus.INPUT_ERROR) != has_input_error:
            raise ValueError("input-error gate status must match input validation issues")

        endpoints_by_role = {
            "origin": self.origin_endpoints,
            "destination": self.destination_endpoints,
        }
        assignment_keys: set[tuple[str, str]] = set()
        for assignment in self.assignments:
            endpoint_key = (assignment.role, assignment.endpoint.airport_id)
            if endpoint_key in assignment_keys:
                raise ValueError("an endpoint can have at most one market assignment per side")
            assignment_keys.add(endpoint_key)
            if assignment.endpoint not in endpoints_by_role[assignment.role]:
                raise ValueError(
                    "assignment endpoint must completely match an input endpoint on its side"
                )

        derived_market_ids = tuple(
            sorted({assignment.market_id for assignment in self.assignments if assignment.market_id})
        )
        if self.known_market_ids != derived_market_ids:
            raise ValueError("known market IDs must be derived from assignments")

        gap_assignment_keys = tuple(
            (assignment.role, assignment.endpoint.airport_id, assignment.endpoint.airport_iata)
            for assignment in self.assignments
            if assignment.mapping_gap
        )
        gap_issue_keys = tuple(
            (issue.role, issue.airport_id, issue.airport_iata)
            for issue in self.issues
            if issue.code is MarketGateIssueCode.MAPPING_GAP
        )
        if gap_issue_keys != gap_assignment_keys:
            raise ValueError("mapping-gap issues must exactly record gap assignments in assignment order")

        endpoint_issue_codes = {
            MarketGateIssueCode.DUPLICATE_ENDPOINT,
            MarketGateIssueCode.ENDPOINT_NOT_IN_CATALOG,
            MarketGateIssueCode.ENDPOINT_IDENTITY_MISMATCH,
            MarketGateIssueCode.MAPPING_GAP,
        }
        input_endpoint_keys = {
            (role, endpoint.airport_id, endpoint.airport_iata)
            for role, endpoints in endpoints_by_role.items()
            for endpoint in endpoints
        }
        for issue in self.issues:
            if issue.code in endpoint_issue_codes and (
                issue.role,
                issue.airport_id,
                issue.airport_iata,
            ) not in input_endpoint_keys:
                raise ValueError("airport-referencing issue must name an actual input endpoint")

        invalid_endpoint_keys = {
            (issue.role, issue.airport_id, issue.airport_iata)
            for issue in self.issues
            if issue.code
            in {
                MarketGateIssueCode.ENDPOINT_NOT_IN_CATALOG,
                MarketGateIssueCode.ENDPOINT_IDENTITY_MISMATCH,
            }
        }
        if invalid_endpoint_keys & {
            (assignment.role, assignment.endpoint.airport_id, assignment.endpoint.airport_iata)
            for assignment in self.assignments
        }:
            raise ValueError("an invalid endpoint cannot retain a market assignment")

        self._validate_empty_and_duplicate_issue_shapes(endpoints_by_role)

        if self.status is MarketGenerationGateStatus.INPUT_ERROR:
            return self

        if not self.origin_endpoints or not self.destination_endpoints:
            raise ValueError("non-input-error gate requires nonempty endpoint sets")
        expected_assignments = tuple(
            (role, endpoint)
            for role, endpoints in (
                ("origin", self.origin_endpoints),
                ("destination", self.destination_endpoints),
            )
            for endpoint in endpoints
        )
        actual_assignments = tuple(
            (assignment.role, assignment.endpoint)
            for assignment in self.assignments
        )
        if actual_assignments != expected_assignments:
            raise ValueError("assignments must cover valid endpoint inputs once, in role/input order")
        if len(gap_issue_keys) != len(self.issues):
            raise ValueError("non-input-error issues must exactly record mapping gaps in assignment order")
        should_skip = not gap_assignment_keys and len(derived_market_ids) == 1
        if (self.status is MarketGenerationGateStatus.SKIP_SINGLE_MARKET) != should_skip:
            raise ValueError("same-market skip requires exactly one fully known market")
        return self

    def _validate_empty_and_duplicate_issue_shapes(
        self, endpoints_by_role: dict[str, tuple[SelectedAirport, ...]]
    ) -> None:
        for role, endpoints in endpoints_by_role.items():
            empty_issues = tuple(
                issue
                for issue in self.issues
                if issue.code
                is (
                    MarketGateIssueCode.EMPTY_ORIGIN_ENDPOINTS
                    if role == "origin"
                    else MarketGateIssueCode.EMPTY_DESTINATION_ENDPOINTS
                )
            )
            if bool(empty_issues) != (not endpoints) or any(
                issue.role != role or issue.airport_id is not None or issue.airport_iata is not None
                for issue in empty_issues
            ):
                raise ValueError("empty-endpoint issue shape must agree with input endpoint sets")

            seen_ids: set[str] = set()
            expected_duplicate_keys: list[tuple[str, str, str]] = []
            for endpoint in endpoints:
                if endpoint.airport_id in seen_ids:
                    expected_duplicate_keys.append((role, endpoint.airport_id, endpoint.airport_iata))
                seen_ids.add(endpoint.airport_id)
            duplicate_issue_keys = tuple(
                (issue.role, issue.airport_id, issue.airport_iata)
                for issue in self.issues
                if issue.code is MarketGateIssueCode.DUPLICATE_ENDPOINT and issue.role == role
            )
            if duplicate_issue_keys != tuple(expected_duplicate_keys):
                raise ValueError("duplicate-endpoint issues must agree with same-side input duplicates")


class PlanningMarketPolicyCompatibilityError(ValueError):
    """A policy's exact override no longer describes the catalog it is applied to."""


def planning_market_policy_digest(policy: PlanningMarketPolicy) -> str:
    rendered = json.dumps(
        policy.model_dump(mode="json", round_trip=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def default_planning_market_policy_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "data"
        / "search_planning"
        / "v2"
        / "planning-market-policy-v1.json"
    )


def load_planning_market_policy(path: Path) -> PlanningMarketPolicy:
    with path.open(encoding="utf-8") as file:
        return PlanningMarketPolicy.model_validate(json.load(file))


def load_default_planning_market_policy() -> PlanningMarketPolicy:
    return load_planning_market_policy(default_planning_market_policy_path())


def validate_planning_market_policy_for_catalog(
    policy: PlanningMarketPolicy, repository: PlanningMarketCatalogRepository
) -> MarketPolicyCatalogCompatibility:
    """Validate exact exceptions without rejecting a later, otherwise usable catalog.

    A new unmapped country is a normal runtime mapping gap.  Conversely, an
    existing named override changing identity/country/region is a policy incompatibility
    because silently applying a geographic exception to a different airport
    would be unsafe.
    """

    receipt = repository.knowledge_receipt
    if not isinstance(receipt, CatalogKnowledgeReceipt):
        raise PlanningMarketPolicyCompatibilityError("planning-market policy requires a catalog receipt")
    for override in policy.airport_overrides:
        airport = repository.airport(override.airport_id)
        metadata = repository.airport_selection_metadata(override.airport_id)
        if (
            airport is None
            or metadata is None
            or airport.iata != override.expected_iata
            or metadata.country_code != override.expected_country_code
            or metadata.iso_region != override.expected_iso_region
        ):
            raise PlanningMarketPolicyCompatibilityError(
                f"planning-market override {override.airport_id} does not match runtime catalog"
            )
    return MarketPolicyCatalogCompatibility(
        authoring_release_id=policy.catalog_release_id,
        authoring_logical_content_sha256=policy.catalog_logical_content_sha256,
        runtime_catalog_receipt=receipt,
        authoring_identity_matches_runtime=(
            receipt.release_id == policy.catalog_release_id
            and receipt.logical_content_sha256 == policy.catalog_logical_content_sha256
        ),
    )


def classify_and_gate_airport_markets(
    *,
    origin_endpoints: tuple[SelectedAirport, ...],
    destination_endpoints: tuple[SelectedAirport, ...],
    policy: PlanningMarketPolicy,
    repository: PlanningMarketCatalogRepository,
) -> MarketGenerationGate:
    """Classify exact retained endpoints and make the one-market skip decision.

    Unknown markets are intentionally not conflated with a same-market result:
    they are emitted as mapping-gap receipts and leave the grouped generator
    eligible to apply its own general knowledge.
    """

    compatibility = validate_planning_market_policy_for_catalog(policy, repository)
    issues: list[MarketGateIssue] = []
    if not origin_endpoints:
        issues.append(MarketGateIssue(code=MarketGateIssueCode.EMPTY_ORIGIN_ENDPOINTS, message="origin endpoint set is empty", role="origin"))
    if not destination_endpoints:
        issues.append(MarketGateIssue(code=MarketGateIssueCode.EMPTY_DESTINATION_ENDPOINTS, message="destination endpoint set is empty", role="destination"))

    assignments: list[AirportMarketAssignment] = []
    seen: set[tuple[str, str]] = set()
    for role, endpoints in (("origin", origin_endpoints), ("destination", destination_endpoints)):
        for endpoint in endpoints:
            key = (role, endpoint.airport_id)
            if key in seen:
                issues.append(MarketGateIssue(code=MarketGateIssueCode.DUPLICATE_ENDPOINT, message="endpoint is duplicated on one side", role=role, airport_id=endpoint.airport_id, airport_iata=endpoint.airport_iata))
                continue
            seen.add(key)
            airport = repository.airport(endpoint.airport_id)
            metadata = repository.airport_selection_metadata(endpoint.airport_id)
            if airport is None or metadata is None:
                issues.append(MarketGateIssue(code=MarketGateIssueCode.ENDPOINT_NOT_IN_CATALOG, message="endpoint is not a retained catalog airport", role=role, airport_id=endpoint.airport_id, airport_iata=endpoint.airport_iata))
                continue
            if airport.iata != endpoint.airport_iata:
                issues.append(MarketGateIssue(code=MarketGateIssueCode.ENDPOINT_IDENTITY_MISMATCH, message="endpoint airport ID and IATA do not match catalog identity", role=role, airport_id=endpoint.airport_id, airport_iata=endpoint.airport_iata))
                continue
            assignment = _classify_endpoint(role, endpoint, metadata.country_code, metadata.iso_region, policy)
            assignments.append(assignment)
            if assignment.mapping_gap:
                issues.append(MarketGateIssue(code=MarketGateIssueCode.MAPPING_GAP, message=f"no approved planning market for {endpoint.airport_iata}", role=role, airport_id=endpoint.airport_id, airport_iata=endpoint.airport_iata))

    known_market_ids = tuple(sorted({item.market_id for item in assignments if item.market_id is not None}))
    input_error_codes = {
        MarketGateIssueCode.EMPTY_ORIGIN_ENDPOINTS,
        MarketGateIssueCode.EMPTY_DESTINATION_ENDPOINTS,
        MarketGateIssueCode.DUPLICATE_ENDPOINT,
        MarketGateIssueCode.ENDPOINT_NOT_IN_CATALOG,
        MarketGateIssueCode.ENDPOINT_IDENTITY_MISMATCH,
    }
    if any(item.code in input_error_codes for item in issues):
        status = MarketGenerationGateStatus.INPUT_ERROR
    elif not any(item.mapping_gap for item in assignments) and len(known_market_ids) == 1:
        status = MarketGenerationGateStatus.SKIP_SINGLE_MARKET
    else:
        status = MarketGenerationGateStatus.GENERATION_REQUIRED
    return MarketGenerationGate(
        origin_endpoints=origin_endpoints,
        destination_endpoints=destination_endpoints,
        assignments=tuple(assignments),
        compatibility=compatibility,
        status=status,
        known_market_ids=known_market_ids,
        issues=tuple(issues),
    )


def _classify_endpoint(
    role: str,
    endpoint: SelectedAirport,
    country_code: str,
    iso_region: str,
    policy: PlanningMarketPolicy,
) -> AirportMarketAssignment:
    override = next((item for item in policy.airport_overrides if item.airport_id == endpoint.airport_id), None)
    if override is not None:
        # Exact airport identity wins. Guard regions never assign markets; they
        # only stop a newly added airport from silently falling back to country.
        return AirportMarketAssignment(role=role, endpoint=endpoint, catalog_country_code=country_code, catalog_iso_region=iso_region, market_id=override.market_id, source=MarketAssignmentSource.AIRPORT_OVERRIDE, mapping_gap=False)
    if iso_region in policy.override_coverage_regions:
        return AirportMarketAssignment(role=role, endpoint=endpoint, catalog_country_code=country_code, catalog_iso_region=iso_region, source=MarketAssignmentSource.OVERRIDE_COVERAGE_DRIFT, mapping_gap=True)
    market_id = policy.country_assignments.get(country_code)
    if market_id is not None:
        return AirportMarketAssignment(role=role, endpoint=endpoint, catalog_country_code=country_code, catalog_iso_region=iso_region, market_id=market_id, source=MarketAssignmentSource.COUNTRY_ASSIGNMENT, mapping_gap=False)
    source = (MarketAssignmentSource.EXPLICIT_UNKNOWN_COUNTRY if country_code in policy.explicit_unknown_country_codes else MarketAssignmentSource.UNMAPPED_COUNTRY)
    return AirportMarketAssignment(role=role, endpoint=endpoint, catalog_country_code=country_code, catalog_iso_region=iso_region, source=source, mapping_gap=True)
