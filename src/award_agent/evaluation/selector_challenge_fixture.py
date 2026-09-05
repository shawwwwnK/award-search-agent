"""Checked-in public structural challenge fixture for the temporal selector.

The challenge catalogs in :mod:`selector_challenge_cases` are deliberately private.  This
module is the only place that turns those catalogs into a checked-in fixture.  It keeps the
private request, candidate identities, compiler oracle, and review rationales in memory while
publishing only the date-free ``TemporalSelectorInput`` projection.

The fixture has two deterministic payload variants per private surface.  The ``canonical``
variant follows the normal projection order.  The ``permuted`` variant applies a bijection to
every public handle namespace and reverses evidence, anchor, group, and candidate order.  The
permuted form is therefore useful for detecting selectors that rely on position or incidental
IDs rather than the supplied semantics.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from award_agent.evaluation.frozen_selector_eval import (
    FrozenSelectorFixtureError,
    preflight_frozen_selector_cases,
)
from award_agent.evaluation.selector_challenge_cases import (
    ChallengeSurfaceVariant,
    SelectorChallengeSurface,
    challenge_surface_registry,
    challenge_surface_variants,
)
from award_agent.intent.model_views import (
    TemporalSelectorAnchor,
    TemporalSelectorAnchorUse,
    TemporalSelectorCandidate,
    TemporalSelectorEvidence,
    TemporalSelectorGroup,
    TemporalSelectorInput,
)
from award_agent.intent.temporal_selector import (
    build_temporal_selector_input,
    plan_temporal_selection,
)

DEFAULT_SELECTOR_CHALLENGE_FIXTURE = Path(
    "evals/selector/structural_challenge_cases_v1.yaml"
)
DEFAULT_CONTROL_FIXTURE = Path("evals/selector/frozen_cases_v2.yaml")
CHALLENGE_FIXTURE_VERSION = "v1"

_PUBLIC_NAMESPACES = ("c", "g", "e", "a", "p")
_PRIVATE_MARKERS = (
    "manual:",
    "private",
    "oracle",
    "rationale",
    "catalog",
    "request",
    "resolved_date",
    "reference_date",
    "timezone",
    "source_start",
    "source_end",
    "priority",
    "canonical_id",
)
_RESOLVED_DATE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")


class SelectorChallengeFixtureError(ValueError):
    """A checked-in challenge fixture is malformed, stale, duplicated, or unsafe."""


@dataclass(frozen=True)
class PreparedSelectorChallengeCase:
    """A private challenge surface paired with its public payload variant."""

    identifier: str
    topology: str
    subtype_id: str
    surface_id: str
    order_variant: Literal["canonical", "permuted"]
    control_only: bool
    surface: SelectorChallengeSurface
    model_input: TemporalSelectorInput


@dataclass(frozen=True)
class LoadedSelectorChallengeFixture:
    """Checked-in public rows plus immutable fixture/control identities."""

    contract_version: str
    fixture_version: str
    scenarios: tuple[dict[str, Any], ...]
    path: Path
    sha256: str
    control_path: Path
    control_sha256: str


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _public_projection(model_input: TemporalSelectorInput) -> dict[str, Any]:
    """Return exactly what may cross the model boundary."""

    return model_input.model_dump(mode="json")


def _private_surface_signature(surface: SelectorChallengeSurface) -> str:
    """Return a stable structural identity without compiler-local handles.

    Request wording is retained because distinct manually reviewed stems can share a topology
    while exercising different local evidence.  Private IDs, priorities, rationales, and dates
    are intentionally excluded from the signature's structural fields.
    """

    scan = surface.catalog.scan
    clause_index = {clause.handle: index for index, clause in enumerate(scan.clauses)}
    anchor_index = {anchor.handle: index for index, anchor in enumerate(scan.anchors)}
    slots: dict[str, int] = {}

    def slot_number(slot: str) -> int:
        if slot not in slots:
            slots[slot] = len(slots)
        return slots[slot]

    grouped: dict[str, list[Any]] = defaultdict(list)
    for candidate in surface.catalog.candidates:
        grouped[candidate.exclusive_group].append(candidate)
    groups: list[Any] = []
    for candidates in grouped.values():
        normalized: list[Any] = []
        for candidate in candidates:
            normalized.append(
                {
                    "relation": candidate.relation.value,
                    "target": candidate.target.value if candidate.target is not None else None,
                    "ordinal": candidate.ordinal,
                    "covers": tuple(clause_index[item] for item in candidate.covers),
                    "requires": tuple(slot_number(item) for item in candidate.requires),
                    "produces": tuple(slot_number(item) for item in candidate.produces),
                    "anchors": tuple(
                        (anchor_index[item.handle], item.mode.value)
                        for item in candidate.anchor_uses
                    ),
                    "composition": (
                        candidate.composition.value
                        if candidate.composition is not None
                        else None
                    ),
                    "operand": (
                        slot_number(candidate.composition_operand)
                        if candidate.composition_operand is not None
                        else None
                    ),
                }
            )
        groups.append(tuple(normalized))
    return _json(
        {
            "topology": surface.topology_id.value,
            "subtype_id": surface.subtype_id,
            "text": surface.request.text,
            "clauses": tuple((item.kind, item.text) for item in scan.clauses),
            "anchors": tuple(
                (item.kind, item.target.value if item.target is not None else None,
                 clause_index[item.clause.handle])
                for item in scan.anchors
            ),
            "groups": tuple(groups),
        }
    )


def canonical_topology_signature(surface: SelectorChallengeSurface) -> str:
    """Expose the canonical private structural signature used by fixture preflight."""

    return _private_surface_signature(surface)


def _check_private_registry(registry: Mapping[str, SelectorChallengeSurface]) -> None:
    if len(registry) != 14:
        raise SelectorChallengeFixtureError("challenge registry must contain exactly fourteen surfaces")
    counts: dict[str, int] = defaultdict(int)
    signatures: set[str] = set()
    for surface in registry.values():
        counts[surface.topology_id.value] += 1
        signature = canonical_topology_signature(surface)
        if signature in signatures:
            raise SelectorChallengeFixtureError(
                f"duplicate canonical challenge topology signature for {surface.surface_id!r}"
            )
        signatures.add(signature)
        if not surface.subtype_id:
            raise SelectorChallengeFixtureError(
                f"challenge surface {surface.surface_id!r} has no subtype_id"
            )
    expected = {topology.value: 2 for topology in type(next(iter(registry.values())).topology_id)}
    if counts != expected:
        raise SelectorChallengeFixtureError(
            f"challenge registry must have two surfaces per topology: {dict(counts)!r}"
        )


def _remap_input(model_input: TemporalSelectorInput) -> TemporalSelectorInput:
    """Apply the deterministic reversed-order bijection to one public selector input."""

    old_evidence = tuple(model_input.ordered_evidence)
    old_anchors = tuple(model_input.local_anchors)
    old_groups = tuple(model_input.candidate_groups)
    old_candidates = tuple(candidate for group in old_groups for candidate in group.candidates)
    old_slots = tuple(
        dict.fromkeys(
            (*model_input.available_productions,
             *(slot for candidate in old_candidates for slot in candidate.produces))
        )
    )
    remap_evidence = {item.handle: f"e{len(old_evidence) - index - 1}" for index, item in enumerate(old_evidence)}
    remap_anchors = {item.handle: f"a{len(old_anchors) - index - 1}" for index, item in enumerate(old_anchors)}
    remap_groups = {item.handle: f"g{len(old_groups) - index - 1}" for index, item in enumerate(old_groups)}
    remap_candidates = {item.handle: f"c{len(old_candidates) - index - 1}" for index, item in enumerate(old_candidates)}
    remap_slots = {item: f"p{len(old_slots) - index - 1}" for index, item in enumerate(old_slots)}

    evidence = tuple(
        TemporalSelectorEvidence(
            handle=remap_evidence[item.handle],
            text=item.text,
            endpoint_cue=item.endpoint_cue,
        )
        for item in reversed(old_evidence)
    )
    anchors = tuple(
        TemporalSelectorAnchor(
            handle=remap_anchors[item.handle],
            evidence=remap_evidence[item.evidence],
            kind=item.kind,
        )
        for item in reversed(old_anchors)
    )

    def candidate(item: TemporalSelectorCandidate) -> TemporalSelectorCandidate:
        summary = item.summary
        for namespace, mapping in (
            ("e", remap_evidence),
            ("a", remap_anchors),
            ("g", remap_groups),
            ("c", remap_candidates),
            ("p", remap_slots),
        ):
            def replace_handle(
                match: re.Match[str], *, mapping: Mapping[str, str] = mapping
            ) -> str:
                return mapping[match.group(0)]

            summary = re.sub(
                rf"\b{namespace}\d+\b",
                replace_handle,
                summary,
            )
        return TemporalSelectorCandidate(
            handle=remap_candidates[item.handle],
            summary=summary,
            interpretation_kind=item.interpretation_kind,
            relation_ordinal=item.relation_ordinal,
            target=item.target,
            covers=tuple(remap_evidence[value] for value in item.covers),
            requires=tuple(remap_slots[value] for value in item.requires),
            produces=tuple(remap_slots[value] for value in item.produces),
            anchor_uses=tuple(
                TemporalSelectorAnchorUse(anchor=remap_anchors[use.anchor], mode=use.mode)
                for use in item.anchor_uses
            ),
            composition=item.composition,
            composition_operand=(
                remap_slots[item.composition_operand]
                if item.composition_operand is not None
                else None
            ),
        )

    groups = tuple(
        TemporalSelectorGroup(
            handle=remap_groups[group.handle],
            candidates=tuple(candidate(item) for item in reversed(group.candidates)),
        )
        for group in reversed(old_groups)
    )
    remapped = TemporalSelectorInput(
        ordered_evidence=evidence,
        local_anchors=anchors,
        available_productions=tuple(
            remap_slots[item] for item in reversed(model_input.available_productions)
        ),
        candidate_groups=groups,
    )
    remapped._candidate_handles = {
        remap_candidates[public]: private
        for public, private in model_input._candidate_handles.items()
    }
    remapped._group_handles = {
        remap_groups[public]: private for public, private in model_input._group_handles.items()
    }
    remapped._evidence_handles = {
        remap_evidence[public]: private
        for public, private in model_input._evidence_handles.items()
    }
    remapped._anchor_handles = {
        remap_anchors[public]: private for public, private in model_input._anchor_handles.items()
    }
    remapped._production_slots = {
        remap_slots[public]: private for public, private in model_input._production_slots.items()
    }
    return remapped


def _variant_input(variant: ChallengeSurfaceVariant) -> TemporalSelectorInput:
    plan = plan_temporal_selection(variant.surface.catalog)
    if not plan.selector_groups:
        raise SelectorChallengeFixtureError(
            f"challenge surface {variant.surface.surface_id!r} has no selector groups"
        )
    canonical = build_temporal_selector_input(
        variant.surface.catalog,
        plan,
        contract_version="v2",
    )
    return canonical if variant.order_variant == "canonical" else _remap_input(canonical)


def _load_yaml(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        payload = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise SelectorChallengeFixtureError(f"cannot read challenge fixture: {path}") from exc
    if not isinstance(payload, dict):
        raise SelectorChallengeFixtureError("challenge fixture must be a mapping")
    return cast(dict[str, Any], payload), raw


def _control_projection_map(control_path: Path) -> tuple[dict[str, str], str]:
    try:
        controls = preflight_frozen_selector_cases(control_path)
    except (FrozenSelectorFixtureError, OSError, ValueError) as exc:
        raise SelectorChallengeFixtureError("v2 control fixture failed preflight") from exc
    return {
        _json(_public_projection(item.model_input)): item.fixture.identifier for item in controls
    }, hashlib.sha256(control_path.read_bytes()).hexdigest()


def _privacy_violations(value: Any, *, path: str = "root") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in _PRIVATE_MARKERS:
                violations.append(f"{path}.{key_text}")
            violations.extend(_privacy_violations(child, path=f"{path}.{key_text}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            violations.extend(_privacy_violations(child, path=f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.casefold()
        if any(marker in lowered for marker in _PRIVATE_MARKERS):
            violations.append(path)
        if _RESOLVED_DATE.search(value):
            violations.append(path)
    return violations


def privacy_violations(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Return paths containing private catalog fields or resolved calendar state."""

    violations = _privacy_violations(payload)
    public_inputs = [
        row.get("public_input")
        for row in payload.get("scenarios", [])
        if isinstance(row, Mapping)
    ]
    for index, public_input in enumerate(public_inputs):
        if isinstance(public_input, Mapping):
            serialized = _json(public_input)
            for namespace in _PUBLIC_NAMESPACES:
                if re.search(rf"manual:[^\"]+|{namespace}:[^\"]+", serialized):
                    violations.append(f"root.scenarios[{index}].public_input.private_handle")
    return tuple(sorted(set(violations)))


def _expected_rows(
    registry: Mapping[str, SelectorChallengeSurface],
    control_projections: Mapping[str, str],
) -> tuple[PreparedSelectorChallengeCase, ...]:
    prepared: list[PreparedSelectorChallengeCase] = []
    for surface in registry.values():
        for variant in challenge_surface_variants(surface):
            model_input = _variant_input(variant)
            public = _public_projection(model_input)
            identifier = f"{surface.surface_id}-{variant.order_variant}"
            prepared.append(
                PreparedSelectorChallengeCase(
                    identifier=identifier,
                    topology=surface.topology_id.value,
                    subtype_id=surface.subtype_id,
                    surface_id=surface.surface_id,
                    order_variant=cast(Literal["canonical", "permuted"], variant.order_variant),
                    control_only=_json(public) in control_projections,
                    surface=surface,
                    model_input=model_input,
                )
            )
    return tuple(prepared)


def _validate_loaded(
    loaded: LoadedSelectorChallengeFixture,
    registry: Mapping[str, SelectorChallengeSurface],
) -> tuple[PreparedSelectorChallengeCase, ...]:
    if loaded.contract_version != "v2" or loaded.fixture_version != CHALLENGE_FIXTURE_VERSION:
        raise SelectorChallengeFixtureError("challenge fixture contract/version is unsupported")
    control_projections, control_sha = _control_projection_map(loaded.control_path)
    if control_sha != loaded.control_sha256:
        raise SelectorChallengeFixtureError("v2 control fixture SHA-256 drifted")
    prepared = _expected_rows(registry, control_projections)
    expected_by_id = {item.identifier: item for item in prepared}
    if len(loaded.scenarios) != 28:
        raise SelectorChallengeFixtureError("challenge fixture must contain exactly 28 scenarios")
    seen: set[str] = set()
    for row in loaded.scenarios:
        expected_keys = {
            "id", "topology", "subtype_id", "surface_id", "order_variant", "control_only",
            "public_input",
        }
        if set(row) != expected_keys:
            raise SelectorChallengeFixtureError("challenge scenario has an unexpected schema")
        identifier = row.get("id")
        if not isinstance(identifier, str) or identifier in seen or identifier not in expected_by_id:
            raise SelectorChallengeFixtureError("challenge scenario IDs must be unique and known")
        expected = expected_by_id[identifier]
        if (
            row.get("topology") != expected.topology
            or row.get("subtype_id") != expected.subtype_id
            or row.get("surface_id") != expected.surface_id
            or row.get("order_variant") != expected.order_variant
            or row.get("control_only") != expected.control_only
            or row.get("public_input") != _public_projection(expected.model_input)
        ):
            raise SelectorChallengeFixtureError(
                f"challenge scenario {identifier!r} does not match its private projection"
            )
        seen.add(identifier)
    if seen != set(expected_by_id):
        raise SelectorChallengeFixtureError("challenge fixture registry/scenario mismatch")
    if violations := privacy_violations({"scenarios": list(loaded.scenarios)}):
        raise SelectorChallengeFixtureError(f"challenge fixture privacy violation: {violations[0]}")
    return tuple(expected_by_id[item.identifier] for item in prepared)


def preflight_selector_challenge_fixture(
    fixture_path: Path = DEFAULT_SELECTOR_CHALLENGE_FIXTURE,
    *,
    control_path: Path = DEFAULT_CONTROL_FIXTURE,
) -> tuple[PreparedSelectorChallengeCase, ...]:
    """Load and verify the public challenge fixture against fresh private catalogs."""

    payload, raw = _load_yaml(fixture_path)
    if payload.get("contract_version") != "v2":
        raise SelectorChallengeFixtureError("challenge fixture must use selector contract v2")
    if payload.get("fixture_version") != CHALLENGE_FIXTURE_VERSION:
        raise SelectorChallengeFixtureError("challenge fixture has an unsupported fixture version")
    control = payload.get("control_fixture")
    if not isinstance(control, Mapping):
        raise SelectorChallengeFixtureError("challenge fixture must bind the v2 control fixture")
    if control.get("path") != str(control_path):
        raise SelectorChallengeFixtureError("challenge fixture control path drifted")
    control_sha = control.get("sha256")
    if not isinstance(control_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", control_sha):
        raise SelectorChallengeFixtureError("challenge fixture control SHA-256 is invalid")
    loaded = LoadedSelectorChallengeFixture(
        contract_version="v2",
        fixture_version=CHALLENGE_FIXTURE_VERSION,
        scenarios=tuple(payload.get("scenarios", ())),
        path=fixture_path,
        sha256=hashlib.sha256(raw).hexdigest(),
        control_path=control_path,
        control_sha256=control_sha,
    )
    registry = challenge_surface_registry()
    _check_private_registry(registry)
    return _validate_loaded(loaded, registry)


def load_selector_challenge_fixture(
    fixture_path: Path = DEFAULT_SELECTOR_CHALLENGE_FIXTURE,
    *,
    control_path: Path = DEFAULT_CONTROL_FIXTURE,
) -> LoadedSelectorChallengeFixture:
    """Return fixture identity metadata after full public/private preflight."""

    payload, raw = _load_yaml(fixture_path)
    preflight_selector_challenge_fixture(fixture_path, control_path=control_path)
    control = cast(Mapping[str, Any], payload["control_fixture"])
    return LoadedSelectorChallengeFixture(
        contract_version="v2",
        fixture_version=CHALLENGE_FIXTURE_VERSION,
        scenarios=tuple(cast(Sequence[dict[str, Any]], payload["scenarios"])),
        path=fixture_path,
        sha256=hashlib.sha256(raw).hexdigest(),
        control_path=control_path,
        control_sha256=str(control["sha256"]),
    )


def challenge_fixture_payload(
    *,
    control_path: Path = DEFAULT_CONTROL_FIXTURE,
) -> dict[str, Any]:
    """Build the exact checked-in YAML payload without exposing private catalog state."""

    registry = challenge_surface_registry()
    _check_private_registry(registry)
    controls, control_sha = _control_projection_map(control_path)
    prepared = _expected_rows(registry, controls)
    return {
        "contract_version": "v2",
        "fixture_version": CHALLENGE_FIXTURE_VERSION,
        "control_fixture": {"path": str(control_path), "sha256": control_sha},
        "scenarios": [
            {
                "id": item.identifier,
                "topology": item.topology,
                "subtype_id": item.subtype_id,
                "surface_id": item.surface_id,
                "order_variant": item.order_variant,
                "control_only": item.control_only,
                "public_input": _public_projection(item.model_input),
            }
            for item in prepared
        ],
    }


__all__ = [
    "CHALLENGE_FIXTURE_VERSION",
    "DEFAULT_CONTROL_FIXTURE",
    "DEFAULT_SELECTOR_CHALLENGE_FIXTURE",
    "LoadedSelectorChallengeFixture",
    "PreparedSelectorChallengeCase",
    "SelectorChallengeFixtureError",
    "canonical_topology_signature",
    "challenge_fixture_payload",
    "load_selector_challenge_fixture",
    "preflight_selector_challenge_fixture",
    "privacy_violations",
]
