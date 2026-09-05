from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from award_agent.domain import (
    AnchorReference,
    CoarseIntentExtraction,
    DurationModifier,
    Holiday,
    RawRequest,
    RelativeWeekendConstraint,
    RequestContext,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalRelationGraph,
    TemporalTarget,
    TemporalUnit,
)
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
    StructuredValidationErrorView,
    TemporalInterpretationInput,
    TemporalResolutionResult,
    TemporalSelectorInput,
    TemporalSelectorOutput,
)
from award_agent.intent.temporal_candidates import (
    AnchorUse,
    AnchorUseMode,
    CandidateRelation,
    TemporalCandidate,
    TemporalCandidateCatalog,
    build_temporal_candidates,
)
from award_agent.intent.temporal_compiler import (
    compile_temporal_candidates,
    validate_candidate_selection,
)
from award_agent.intent.temporal_lexing import TemporalScan, scan_temporal_request
from award_agent.intent.temporal_selector import (
    TemporalSelectionPlan,
    TemporalSelectorValidationError,
    build_temporal_selector_input,
    plan_temporal_selection,
    restore_selector_output,
    unresolved_selection,
)
from award_agent.intent.workflow import understand_request


def _request(
    text: str = "Leave October 5.",
    *,
    reference_date: date = date(2026, 8, 29),
    timezone: str = "UTC",
) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=reference_date, timezone=timezone),
    )


def _ambiguous_catalog(scan: TemporalScan) -> TemporalCandidateCatalog:
    anchor = next(item for item in scan.anchors if item.kind == "exact_date")
    clause = anchor.clause
    direct = AnchorUse(anchor.handle, AnchorUseMode.DIRECT_WINDOW)
    support = AnchorUse(anchor.handle, AnchorUseMode.UNRESOLVED_SUPPORT)
    return TemporalCandidateCatalog(
        scan=scan,
        candidates=(
            TemporalCandidate(
                handle="internal:first",
                exclusive_group="internal:ambiguous",
                covers=(clause.handle,),
                requires=(),
                produces=(f"slot:{anchor.target.value}",),
                priority=100,
                anchor_uses=(direct,),
                relation=CandidateRelation.EXACT_DATE,
                target=anchor.target,
                clause_handle=clause.handle,
            ),
            TemporalCandidate(
                handle="internal:second",
                exclusive_group="internal:ambiguous",
                covers=(clause.handle,),
                requires=(),
                produces=(f"slot:{anchor.target.value}",),
                priority=100,
                anchor_uses=(direct,),
                relation=CandidateRelation.EXACT_DATE,
                target=anchor.target,
                clause_handle=clause.handle,
            ),
            TemporalCandidate(
                handle="internal:unresolved",
                exclusive_group="internal:ambiguous",
                covers=(clause.handle,),
                requires=(),
                produces=(),
                priority=0,
                anchor_uses=(support,),
                relation=CandidateRelation.UNRESOLVED,
                target=anchor.target,
                clause_handle=clause.handle,
                reason="conservative unresolved alternative",
            ),
        ),
    )


def _selector_input() -> TemporalSelectorInput:
    scan = scan_temporal_request(_request())
    catalog = _ambiguous_catalog(scan)
    plan = plan_temporal_selection(catalog)
    assert plan.selector_groups == ("internal:ambiguous",)
    return build_temporal_selector_input(catalog, plan)


def test_selector_view_is_opaque_and_context_invariant() -> None:
    first_catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    second_catalog = _ambiguous_catalog(
        scan_temporal_request(
            _request(reference_date=date(2031, 1, 2), timezone="America/Los_Angeles")
        )
    )
    first = build_temporal_selector_input(first_catalog, plan_temporal_selection(first_catalog))
    second = build_temporal_selector_input(second_catalog, plan_temporal_selection(second_catalog))

    assert first.model_dump_json() == second.model_dump_json()
    dumped = first.model_dump_json()
    assert "internal:" not in dumped
    assert "slot:" not in dumped
    for forbidden in (
        "reference_date",
        "timezone",
        "source_start",
        "source_end",
        "constraint_id",
        "priority",
        "2026-",
    ):
        assert forbidden not in dumped
    assert first.candidate_groups[0].handle == "g0"
    assert [candidate.handle for candidate in first.candidate_groups[0].candidates] == [
        "c0",
        "c1",
        "c2",
    ]
    assert first.ordered_evidence[0].handle == "e0"
    assert first.local_anchors[0].handle == "a0"


def test_selector_publishes_only_pn_production_slots_and_explicit_operands() -> None:
    scan = scan_temporal_request(_request("Leave Labor Day weekend; Thursday also."))
    from award_agent.intent.temporal_candidates import build_temporal_candidates

    catalog = build_temporal_candidates(scan)
    # Make the extension genuinely ambiguous so it is included in the public selector view.
    extension = next(
        item
        for item in catalog.candidates
        if item.relation is CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY
    )
    alternate = TemporalCandidate(
        handle="internal:alternate-extension",
        exclusive_group=extension.exclusive_group,
        covers=extension.covers,
        requires=extension.requires,
        produces=extension.produces,
        priority=100,
        anchor_uses=extension.anchor_uses,
        relation=extension.relation,
        composition=extension.composition,
        composition_operand=extension.composition_operand,
        target=extension.target,
        clause_handle=extension.clause_handle,
    )
    catalog = TemporalCandidateCatalog(
        scan=scan,
        candidates=tuple(catalog.candidates) + (alternate,),
    )
    model_input = build_temporal_selector_input(catalog, plan_temporal_selection(catalog))
    candidates = [
        candidate for group in model_input.candidate_groups for candidate in group.candidates
    ]
    assert model_input.available_productions == ("p0",)
    assert all(
        slot.startswith("p") and slot[1:].isdigit()
        for candidate in candidates
        for slot in (*candidate.requires, *candidate.produces)
    )
    composed = next(candidate for candidate in candidates if candidate.composition is not None)
    assert composed.composition_operand in composed.requires
    assert composed.composition_operand == "p0"
    assert "slot:" not in model_input.model_dump_json()


def test_selector_plan_closes_dependents_when_upstream_can_be_unresolved() -> None:
    scan = scan_temporal_request(_request("Travel next month."))
    clause = next(item for item in scan.clauses if item.kind == "next_month")
    catalog = TemporalCandidateCatalog(
        scan=scan,
        candidates=(
            TemporalCandidate(
                handle="upstream-one",
                exclusive_group="upstream",
                    covers=(clause.handle,),
                requires=(),
                produces=("slot:departure",),
                priority=100,
                anchor_uses=(),
                    relation=CandidateRelation.RELATIVE_CALENDAR_PERIOD,
                    target=TemporalTarget.DEPARTURE,
                    clause_handle=clause.handle,
            ),
            TemporalCandidate(
                handle="upstream-two",
                exclusive_group="upstream",
                    covers=(clause.handle,),
                requires=(),
                produces=("slot:departure",),
                priority=100,
                anchor_uses=(),
                    relation=CandidateRelation.RELATIVE_CALENDAR_PERIOD,
                    target=TemporalTarget.DEPARTURE,
                    clause_handle=clause.handle,
            ),
            TemporalCandidate(
                handle="upstream-unresolved",
                exclusive_group="upstream",
                    covers=(clause.handle,),
                requires=(),
                produces=(),
                priority=0,
                anchor_uses=(),
                    relation=CandidateRelation.UNRESOLVED,
                    target=TemporalTarget.DEPARTURE,
                    clause_handle=clause.handle,
            ),
            TemporalCandidate(
                handle="dependent",
                exclusive_group="dependent",
                    covers=(clause.handle,),
                requires=("slot:departure",),
                produces=("slot:return",),
                priority=100,
                anchor_uses=(),
                    relation=CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE,
                    target=TemporalTarget.RETURN,
                    clause_handle=clause.handle,
            ),
            TemporalCandidate(
                handle="dependent-unresolved",
                exclusive_group="dependent",
                    covers=(clause.handle,),
                requires=(),
                produces=(),
                priority=0,
                anchor_uses=(),
                    relation=CandidateRelation.UNRESOLVED,
                    target=TemporalTarget.RETURN,
                    clause_handle=clause.handle,
            ),
        ),
    )
    plan = plan_temporal_selection(catalog)
    assert plan.auto_selected == ()
    assert plan.selector_groups == ("upstream", "dependent")
    assert unresolved_selection(catalog, plan) == ("upstream-unresolved", "dependent-unresolved")


def test_selector_includes_anchor_evidence_and_uses_raw_text_source_order() -> None:
    scan = scan_temporal_request(_request("Leave October 5 after New Year."))
    exact_date = next(anchor for anchor in scan.anchors if anchor.kind == "exact_date")
    new_year = next(
        anchor for anchor in scan.anchors if anchor.kind == "holiday" and anchor.holiday is not None
    )
    direct = AnchorUse(new_year.handle, AnchorUseMode.REFERENCE_ONLY)
    unresolved_support = AnchorUse(new_year.handle, AnchorUseMode.UNRESOLVED_SUPPORT)
    catalog = TemporalCandidateCatalog(
        scan=scan,
        candidates=(
            TemporalCandidate(
                handle="internal:first",
                exclusive_group="internal:ambiguous",
                # This deliberately excludes New Year's clause: it is only a reference anchor.
                covers=(exact_date.clause.handle,),
                requires=(),
                produces=("departure",),
                priority=100,
                anchor_uses=(direct,),
                relation=CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR,
                target=TemporalTarget.DEPARTURE,
                clause_handle=exact_date.clause.handle,
            ),
            TemporalCandidate(
                handle="internal:second",
                exclusive_group="internal:ambiguous",
                covers=(exact_date.clause.handle,),
                requires=(),
                produces=("departure",),
                priority=100,
                anchor_uses=(direct,),
                relation=CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR,
                target=TemporalTarget.DEPARTURE,
                clause_handle=exact_date.clause.handle,
            ),
            TemporalCandidate(
                handle="internal:unresolved",
                exclusive_group="internal:ambiguous",
                covers=(exact_date.clause.handle,),
                requires=(),
                produces=(),
                priority=0,
                anchor_uses=(unresolved_support,),
                relation=CandidateRelation.UNRESOLVED,
                target=TemporalTarget.DEPARTURE,
                clause_handle=exact_date.clause.handle,
                reason="conservative unresolved alternative",
            ),
        ),
    )

    model_input = build_temporal_selector_input(catalog, plan_temporal_selection(catalog))

    # Lexing harvests holidays before exact dates, so this assertion protects the public view
    # from inheriting that implementation order when the lexical order is the reverse.
    assert [(entry.handle, entry.text) for entry in model_input.ordered_evidence] == [
        ("e0", "October 5"),
        ("e1", "New Year"),
    ]
    assert [
        (anchor.handle, anchor.evidence, anchor.kind) for anchor in model_input.local_anchors
    ] == [("a0", "e1", "holiday")]
    assert model_input.candidate_groups[0].candidates[0].covers == ("e0",)


def test_selector_v2_uses_only_explicit_local_endpoint_tokens_for_cues() -> None:
    departure_catalog = _ambiguous_catalog(scan_temporal_request(_request("Leave October 5.")))
    returned_catalog = _ambiguous_catalog(
        scan_temporal_request(_request("Return October 5."))
    )
    unmarked_catalog = _ambiguous_catalog(scan_temporal_request(_request("October 5.")))

    departure = build_temporal_selector_input(
        departure_catalog, plan_temporal_selection(departure_catalog)
    )
    returned = build_temporal_selector_input(returned_catalog, plan_temporal_selection(returned_catalog))
    unmarked = build_temporal_selector_input(unmarked_catalog, plan_temporal_selection(unmarked_catalog))

    assert departure.ordered_evidence[0].endpoint_cue == "departure"
    assert returned.ordered_evidence[0].endpoint_cue == "return"
    assert unmarked.ordered_evidence[0].endpoint_cue == "unspecified"
    assert "reference_date" not in departure.model_dump_json()


def test_selector_v2_publishes_safe_semantics_and_relation_ordinals() -> None:
    from award_agent.evaluation.frozen_selector_cases import frozen_selector_case_registry

    reference = frozen_selector_case_registry()["reference-forward"]
    model_input = build_temporal_selector_input(
        reference.catalog, plan_temporal_selection(reference.catalog)
    )
    relative = model_input.candidate_groups[0].candidates[0]

    assert relative.interpretation_kind == "weekend_after_anchor"
    assert relative.relation_ordinal == 2
    assert "2nd weekend" in relative.summary
    assert "manual:" not in model_input.model_dump_json()


@pytest.mark.parametrize(
    ("text", "minimum", "maximum", "unit", "modifier", "summary"),
    [
        (
            "Travel for about 10 days.",
            10,
            10,
            TemporalUnit.DAY,
            DurationModifier.APPROXIMATE,
            (
                "Interpret e0 as a trip duration stated as approximate 10 days "
                "(minimum 10, maximum 10; unit day)."
            ),
        ),
        (
            "Travel for about nine days.",
            9,
            9,
            TemporalUnit.DAY,
            DurationModifier.APPROXIMATE,
            (
                "Interpret e0 as a trip duration stated as approximate 9 days "
                "(minimum 9, maximum 9; unit day)."
            ),
        ),
        (
            "Travel for two weeks.",
            2,
            2,
            TemporalUnit.WEEK,
            DurationModifier.EXACT,
            (
                "Interpret e0 as a trip duration stated as exact 2 weeks "
                "(minimum 2, maximum 2; unit week)."
            ),
        ),
        (
            "Travel for 1 or 2 weeks.",
            1,
            2,
            TemporalUnit.WEEK,
            DurationModifier.ALTERNATIVE,
            (
                "Interpret e0 as a trip duration stated as alternative 1 to 2 weeks "
                "(minimum 1, maximum 2; unit week)."
            ),
        ),
        (
            "Travel for about a week.",
            1,
            1,
            TemporalUnit.WEEK,
            DurationModifier.APPROXIMATE,
            (
                "Interpret e0 as a trip duration stated as approximate 1 week "
                "(minimum 1, maximum 1; unit week)."
            ),
        ),
    ],
)
def test_selector_duration_projection_preserves_literal_and_restores_compilable_choice(
    text: str,
    minimum: int,
    maximum: int,
    unit: TemporalUnit,
    modifier: DurationModifier,
    summary: str,
) -> None:
    request = _request(text)
    catalog = build_temporal_candidates(scan_temporal_request(request))
    plan = plan_temporal_selection(catalog, policy="supported_or_unresolved")
    model_input = build_temporal_selector_input(catalog, plan)

    assert len(model_input.candidate_groups) == 1
    duration_candidate = model_input.candidate_groups[0].candidates[0]
    assert duration_candidate.interpretation_kind == "trip_duration"
    assert duration_candidate.summary == summary
    assert duration_candidate.relation_ordinal is None
    serialized = model_input.model_dump_json()
    for forbidden in ("reference_date", "timezone", "2026-", "slot:"):
        assert forbidden not in serialized

    restored = restore_selector_output(
        model_input,
        TemporalSelectorOutput(selected_candidates=[duration_candidate.handle]),
    )
    compiled = compile_temporal_candidates(request, catalog, restored)
    duration = next(
        constraint for constraint in compiled.graph.constraints if constraint.kind == "duration"
    )
    assert duration.stated_minimum_quantity == minimum
    assert duration.stated_maximum_quantity == maximum
    assert duration.unit is unit
    assert duration.modifier is modifier


@pytest.mark.parametrize(
    "selected",
    [
        ["missing"],
        ["c0", "c0"],
        ["c0", "c1"],
        [],
    ],
)
def test_selector_output_membership_and_group_coverage_are_validated(selected: list[str]) -> None:
    with pytest.raises(TemporalSelectorValidationError):
        restore_selector_output(
            _selector_input(), TemporalSelectorOutput(selected_candidates=selected)
        )


def test_selector_output_restores_only_private_candidate_handles() -> None:
    restored = restore_selector_output(
        _selector_input(), TemporalSelectorOutput(selected_candidates=["c1"])
    )
    assert restored == ("internal:second",)


def test_selector_output_contract_allows_only_candidate_handles() -> None:
    with pytest.raises(ValueError, match="Extra inputs"):
        TemporalSelectorOutput.model_validate(
            {"selected_candidates": ["c0"], "relation": "exact_date"}
        )


def test_no_selector_uses_unresolved_for_genuinely_ambiguous_group() -> None:
    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    plan = plan_temporal_selection(catalog)
    assert plan.auto_selected == ()
    assert unresolved_selection(catalog, plan) == ("internal:unresolved",)


def test_selector_preflight_rejects_an_invalid_unselected_distractor() -> None:
    """A bad manual alternative must fail before it can become public model input."""

    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    invalid = replace(
        catalog.candidates[1],
        anchor_uses=(AnchorUse("missing-anchor", AnchorUseMode.DIRECT_WINDOW),),
    )
    invalid_catalog = TemporalCandidateCatalog(
        scan=catalog.scan,
        candidates=(catalog.candidates[0], invalid, catalog.candidates[2]),
    )

    with pytest.raises(TemporalSelectorValidationError, match="incompatible anchor binding"):
        plan_temporal_selection(invalid_catalog)


def test_selector_preflight_rejects_an_open_dependency_before_projection() -> None:
    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    clause = catalog.scan.clauses[0]
    open_dependent = TemporalCandidate(
        handle="internal:open-dependent",
        exclusive_group="internal:dependent",
        covers=(clause.handle,),
        requires=("slot:missing",),
        produces=("slot:return",),
        priority=100,
        anchor_uses=(),
        relation=CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE,
        target=TemporalTarget.RETURN,
        clause_handle=clause.handle,
    )
    unresolved = TemporalCandidate(
        handle="internal:dependent-unresolved",
        exclusive_group="internal:dependent",
        covers=(clause.handle,),
        requires=(),
        produces=(),
        priority=0,
        anchor_uses=(),
        relation=CandidateRelation.UNRESOLVED,
        target=TemporalTarget.RETURN,
        clause_handle=clause.handle,
    )
    invalid_catalog = TemporalCandidateCatalog(
        scan=catalog.scan,
        candidates=(*catalog.candidates, open_dependent, unresolved),
    )

    with pytest.raises(TemporalSelectorValidationError, match="without a possible producer"):
        plan_temporal_selection(invalid_catalog)


def test_selector_preflight_keeps_the_conservative_all_unresolved_selection_compilable() -> None:
    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    plan = plan_temporal_selection(catalog)

    selected = unresolved_selection(catalog, plan)
    assert [candidate.handle for candidate in validate_candidate_selection(catalog, selected)] == list(
        selected
    )


def test_selector_preflight_allows_a_same_target_availability_dependency() -> None:
    from award_agent.evaluation.frozen_selector_cases import frozen_selector_case_registry

    case = frozen_selector_case_registry()["composition-forward"]
    plan = plan_temporal_selection(case.catalog)
    dependent = next(
        candidate
        for candidate in case.catalog.candidates
        if candidate.handle == "manual:composition:weekend-after"
    )

    assert dependent.requires == ("slot:base-departure",)
    assert plan.selector_groups == ("manual:composition",)
    assert [candidate.handle for candidate in validate_candidate_selection(
        case.catalog,
        ("manual:composition:base", dependent.handle),
    )] == ["manual:composition:base", dependent.handle]


def test_generic_availability_dependency_does_not_become_a_canonical_reference() -> None:
    from award_agent.evaluation.frozen_selector_cases import frozen_selector_case_registry

    class LaborDayProvider:
        def holiday_date(self, holiday: Holiday, year: int) -> date:
            assert holiday is Holiday.LABOR_DAY
            assert year == 2026
            return date(2026, 9, 7)

    case = frozen_selector_case_registry()["composition-forward"]
    compiled = compile_temporal_candidates(
        case.request,
        case.catalog,
        ("manual:composition:base", "manual:composition:weekend-after"),
        holiday_provider=LaborDayProvider(),
    )
    relation = next(
        item for item in compiled.graph.constraints if isinstance(item, RelativeWeekendConstraint)
    )

    assert isinstance(relation.reference, AnchorReference)


def test_selector_preflight_rejects_an_unresolved_composition_operand() -> None:
    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    invalid = replace(catalog.candidates[2], composition_operand="slot:unexpected")
    invalid_catalog = TemporalCandidateCatalog(
        scan=catalog.scan,
        candidates=(*catalog.candidates[:2], invalid),
    )

    with pytest.raises(TemporalSelectorValidationError, match="cannot consume, produce, or compose"):
        plan_temporal_selection(invalid_catalog)


def test_selector_preflight_rejects_a_duration_on_a_non_duration_relation() -> None:
    request = _request("Leave October 5 for 10 days.")
    scan = scan_temporal_request(request)
    catalog = build_temporal_candidates(scan)
    exact = next(candidate for candidate in catalog.candidates if candidate.relation is CandidateRelation.EXACT_DATE)
    invalid_catalog = TemporalCandidateCatalog(
        scan=scan,
        candidates=tuple(
            replace(candidate, duration=scan.durations[0]) if candidate is exact else candidate
            for candidate in catalog.candidates
        ),
    )

    with pytest.raises(TemporalSelectorValidationError, match="non-duration candidate"):
        plan_temporal_selection(invalid_catalog)


@pytest.mark.parametrize(
    ("text", "relation"),
    [
        ("Leave two weekends after Thanksgiving.", CandidateRelation.RELATIVE_WEEKEND_AFTER_ANCHOR),
        ("Leave Labor Day weekend and return the weekend afterwards.", CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE),
    ],
)
def test_selector_preflight_rejects_non_positive_relation_ordinals(
    text: str, relation: CandidateRelation
) -> None:
    scan = scan_temporal_request(_request(text))
    catalog = build_temporal_candidates(scan)
    target = next(candidate for candidate in catalog.candidates if candidate.relation is relation)
    invalid_catalog = TemporalCandidateCatalog(
        scan=scan,
        candidates=tuple(
            replace(candidate, ordinal=0) if candidate is target else candidate
            for candidate in catalog.candidates
        ),
    )

    with pytest.raises(TemporalSelectorValidationError):
        plan_temporal_selection(invalid_catalog)


def test_selector_preflight_rejects_a_production_slot_shared_across_groups() -> None:
    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    duplicate_group_candidate = replace(
        catalog.candidates[0],
        handle="internal:other-supported",
        exclusive_group="internal:other",
    )
    duplicate_group_unresolved = replace(
        catalog.candidates[2],
        handle="internal:other-unresolved",
        exclusive_group="internal:other",
    )
    invalid_catalog = TemporalCandidateCatalog(
        scan=catalog.scan,
        candidates=(*catalog.candidates, duplicate_group_candidate, duplicate_group_unresolved),
    )

    with pytest.raises(TemporalSelectorValidationError, match="shared across exclusive groups"):
        plan_temporal_selection(invalid_catalog)


def test_selector_projection_preflight_cannot_be_bypassed_with_a_manual_plan() -> None:
    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    invalid = replace(catalog.candidates[0], requires=("slot:unexpected",))
    invalid_catalog = TemporalCandidateCatalog(
        scan=catalog.scan,
        candidates=(invalid, *catalog.candidates[1:]),
    )

    with pytest.raises(TemporalSelectorValidationError, match="without a possible producer"):
        build_temporal_selector_input(
            invalid_catalog,
            TemporalSelectionPlan(auto_selected=(), selector_groups=("internal:ambiguous",)),
        )


def test_selector_preflight_rejects_a_self_produced_availability_dependency() -> None:
    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    invalid = replace(catalog.candidates[0], requires=("slot:departure",))
    invalid_catalog = TemporalCandidateCatalog(
        scan=catalog.scan,
        candidates=(invalid, *catalog.candidates[1:]),
    )

    with pytest.raises(TemporalSelectorValidationError, match="own production slot"):
        plan_temporal_selection(invalid_catalog)


def test_selector_preflight_rejects_a_cross_target_availability_dependency() -> None:
    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    clause = catalog.scan.clauses[0]
    dependent = replace(catalog.candidates[0], requires=("slot:return",))
    return_candidate = TemporalCandidate(
        handle="internal:return-supported",
        exclusive_group="internal:return",
        covers=(clause.handle,),
        requires=("slot:departure",),
        produces=("slot:return",),
        priority=100,
        anchor_uses=(),
        relation=CandidateRelation.RETURN_WEEKEND_AFTER_DEPARTURE,
        target=TemporalTarget.RETURN,
        clause_handle=clause.handle,
    )
    return_unresolved = TemporalCandidate(
        handle="internal:return-unresolved",
        exclusive_group="internal:return",
        covers=(clause.handle,),
        requires=(),
        produces=(),
        priority=0,
        anchor_uses=(),
        relation=CandidateRelation.UNRESOLVED,
        target=TemporalTarget.RETURN,
        clause_handle=clause.handle,
    )
    invalid_catalog = TemporalCandidateCatalog(
        scan=catalog.scan,
        candidates=(dependent, *catalog.candidates[1:], return_candidate, return_unresolved),
    )

    with pytest.raises(TemporalSelectorValidationError, match="incompatible production slot"):
        plan_temporal_selection(invalid_catalog)


def test_selector_preflight_rejects_a_cycle_between_availability_dependencies() -> None:
    catalog = _ambiguous_catalog(scan_temporal_request(_request()))
    first = replace(
        catalog.candidates[0],
        exclusive_group="internal:first-cycle",
        produces=("slot:first",),
        requires=("slot:second",),
    )
    second = replace(
        catalog.candidates[1],
        exclusive_group="internal:second-cycle",
        produces=("slot:second",),
        requires=("slot:first",),
    )
    first_unresolved = replace(
        catalog.candidates[2],
        handle="internal:first-cycle-unresolved",
        exclusive_group="internal:first-cycle",
    )
    second_unresolved = replace(
        catalog.candidates[2],
        handle="internal:second-cycle-unresolved",
        exclusive_group="internal:second-cycle",
    )
    invalid_catalog = TemporalCandidateCatalog(
        scan=catalog.scan,
        candidates=(first, first_unresolved, second, second_unresolved),
    )

    with pytest.raises(TemporalSelectorValidationError, match="cannot participate"):
        plan_temporal_selection(invalid_catalog)


class StaticExtractor:
    def __init__(self, extraction: CoarseIntentExtraction) -> None:
        self.extraction = extraction

    def extract(self, model_input: CoarseExtractionInput) -> CoarseIntentExtraction:
        return self.extraction

    def repair_extract(self, model_input: CoarseExtractionRepairInput) -> CoarseIntentExtraction:
        raise AssertionError("compiler path must not repair pass-one temporal output")

    def extract_non_temporal(
        self, _input: NonTemporalExtractionInput
    ) -> NonTemporalIntentExtraction:
        return NonTemporalIntentExtraction.model_validate(
            self.extraction.model_dump(exclude={"date_anchors", "temporal_phrases"})
        )


class ResolverMustNotRun:
    def resolve_dates(self, model_input: TemporalInterpretationInput) -> TemporalResolutionResult:
        raise AssertionError("compiler path must not call the temporal resolver")

    def repair_dates(
        self,
        model_input: TemporalInterpretationInput,
        rejected_output: TemporalRelationGraph,
        validation_errors: list[StructuredValidationErrorView],
    ) -> TemporalRelationGraph:
        raise AssertionError("compiler path must not call the temporal resolver")


class RecordingSelector:
    def __init__(self, selected: list[str] | None = None) -> None:
        self.selected = selected or ["c0"]
        self.calls: list[TemporalSelectorInput] = []

    def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
        self.calls.append(model_input)
        return TemporalSelectorOutput(selected_candidates=self.selected)


def test_auto_only_compiler_path_does_not_call_selector() -> None:
    selector = RecordingSelector()
    result = understand_request(
        _request("Leave October 5."),
        StaticExtractor(CoarseIntentExtraction()),
        ResolverMustNotRun(),
        temporal_strategy="compiler_select_v1",
        temporal_selector=selector,
    )

    assert selector.calls == []
    assert result.parsed_request.departure_window is not None


def test_supported_or_unresolved_forces_safe_groups_through_selector() -> None:
    catalog = build_temporal_candidates(scan_temporal_request(_request("Leave October 5.")))

    default_plan = plan_temporal_selection(catalog)
    experiment_plan = plan_temporal_selection(
        catalog, policy="supported_or_unresolved"
    )

    assert default_plan.selector_groups == ()
    assert len(default_plan.auto_selected) == 1
    assert experiment_plan.auto_selected == ()
    assert experiment_plan.selector_groups == (catalog.candidates[0].exclusive_group,)
    selector_input = build_temporal_selector_input(catalog, experiment_plan)
    serialized = selector_input.model_dump_json()
    assert len(selector_input.candidate_groups) == 1
    assert "slot:" not in serialized
    assert "reference_date" not in serialized
    assert "2026-" not in serialized


def test_supported_or_unresolved_forces_dependent_groups_with_their_upstream() -> None:
    catalog = build_temporal_candidates(
        scan_temporal_request(
            _request("Leave Labor Day weekend and return the weekend afterwards.")
        )
    )

    plan = plan_temporal_selection(catalog, policy="supported_or_unresolved")
    groups = {candidate.exclusive_group for candidate in catalog.candidates}

    assert plan.auto_selected == ()
    assert set(plan.selector_groups) == groups
    selector_input = build_temporal_selector_input(catalog, plan)
    assert selector_input.available_productions == ()
    dependent = next(
        candidate
        for group in selector_input.candidate_groups
        for candidate in group.candidates
        if candidate.interpretation_kind == "return_weekend_after_departure"
    )
    assert dependent.requires


def test_workflow_selector_view_uses_raw_text_not_malformed_pass_one_temporal_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from award_agent.intent import workflow

    monkeypatch.setattr(
        workflow,
        "build_temporal_candidates",
        lambda scan: _ambiguous_catalog(scan),
    )
    selector = RecordingSelector()
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="not in the raw request",
            )
        ]
    )
    result = understand_request(
        _request(),
        StaticExtractor(extraction),
        ResolverMustNotRun(),
        temporal_strategy="compiler_select_v1",
        temporal_selector=selector,
    )

    assert len(selector.calls) == 1
    serialized = selector.calls[0].model_dump_json()
    assert "October 5" in serialized
    assert "not in the raw request" not in serialized
    assert result.parsed_request.departure_window is not None


def test_workflow_without_selector_compiles_ambiguous_group_as_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from award_agent.intent import workflow

    monkeypatch.setattr(
        workflow,
        "build_temporal_candidates",
        lambda scan: _ambiguous_catalog(scan),
    )
    result = understand_request(
        _request(),
        StaticExtractor(CoarseIntentExtraction()),
        ResolverMustNotRun(),
        temporal_strategy="compiler_select_v1",
    )

    assert result.parsed_request.departure_window is None
    assert result.parsed_request.date_resolution is not None
    assert result.parsed_request.date_resolution.unresolved
    assert result.parsed_request.temporal_relations is not None
    assert [
        constraint.kind for constraint in result.parsed_request.temporal_relations.constraints
    ] == ["unresolved"]


def test_supported_or_unresolved_requires_selector_before_non_temporal_pass_one() -> None:
    class ExtractorMustNotRun:
        def __init__(self) -> None:
            self.calls = 0

        def extract_non_temporal(self, _input: NonTemporalExtractionInput) -> NonTemporalIntentExtraction:
            self.calls += 1
            raise AssertionError("supported_or_unresolved must fail before Pass 1")

    extractor = ExtractorMustNotRun()
    with pytest.raises(ValueError, match="requires a temporal_selector"):
        understand_request(
            _request("Leave October 5."),
            extractor,  # type: ignore[arg-type]
            ResolverMustNotRun(),
            temporal_strategy="compiler_select_v1",
            selector_policy="supported_or_unresolved",
        )

    assert extractor.calls == 0


def test_two_pass_rejects_the_experiment_only_selector_policy() -> None:
    with pytest.raises(ValueError, match="only supported by compiler_select_v1"):
        understand_request(
            _request(),
            StaticExtractor(CoarseIntentExtraction()),
            ResolverMustNotRun(),
            selector_policy="supported_or_unresolved",
        )
