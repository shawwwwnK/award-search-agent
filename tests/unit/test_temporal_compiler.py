from datetime import date
from functools import cache
from pathlib import Path
from typing import ClassVar, cast

import pytest
import yaml

from award_agent.domain import (
    DecisionReference,
    Holiday,
    LocationKind,
    LocationRef,
    RawRequest,
    RelativeCalendarPeriodConstraint,
    RelativeWeekdayConstraint,
    RelativeWeekendConstraint,
    RequestContext,
    SearchMode,
    TemporalEdge,
    TemporalEvidenceClaim,
    TemporalTarget,
)
from award_agent.intent.model_views import (
    NonTemporalAmbiguity,
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
    TemporalSelectorInput,
    TemporalSelectorOutput,
)
from award_agent.intent.temporal_candidates import (
    AnchorUseMode,
    CandidateComposition,
    CandidateRelation,
    TemporalCandidate,
    TemporalCandidateCatalog,
    auto_select_candidates,
    build_temporal_candidates,
)
from award_agent.intent.temporal_compiler import (
    CompiledTemporalIntent,
    TemporalCandidateValidationError,
    compile_temporal_candidates,
    validate_candidate_catalog,
    validate_candidate_selection,
)
from award_agent.intent.temporal_lexing import TemporalScan, scan_temporal_request
from award_agent.intent.workflow import understand_request


class FakeHolidayProvider:
    values: ClassVar = {
        (Holiday.LABOR_DAY, 2026): date(2026, 9, 7),
        (Holiday.NEW_YEARS_DAY, 2026): date(2026, 1, 1),
        (Holiday.NEW_YEARS_DAY, 2027): date(2027, 1, 1),
        (Holiday.THANKSGIVING, 2026): date(2026, 11, 26),
        (Holiday.CHRISTMAS, 2026): date(2026, 12, 25),
    }

    def holiday_date(self, holiday: Holiday, year: int) -> date:
        return self.values[(holiday, year)]


def _request(text: str) -> RawRequest:
    return RawRequest(
        text=text, context=RequestContext(reference_date=date(2026, 8, 29), timezone="UTC")
    )


def _compile(text: str) -> tuple[TemporalScan, TemporalCandidateCatalog, CompiledTemporalIntent]:
    scan = scan_temporal_request(_request(text))
    catalog = build_temporal_candidates(scan)
    return (
        scan,
        catalog,
        compile_temporal_candidates(
            _request(text),
            catalog,
            auto_select_candidates(catalog),
            holiday_provider=FakeHolidayProvider(),
        ),
    )


def test_scanner_classifies_thursday_extension_as_alternate_departure_evidence() -> None:
    scan = scan_temporal_request(
        _request("Leave Labor Day weekend. We are flexible to leave Thursday as well.")
    )

    thursday = next(
        phrase
        for phrase in scan.coarse_extraction.temporal_phrases
        if phrase.raw_text == "Thursday as well"
    )
    assert thursday.claim_ids == [TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY]


@pytest.mark.parametrize(
    ("case_id", "text", "departure", "return_date", "duration"),
    [
        (
            "labor_day_thailand",
            (
                "My boyfriend and I want to go to Thailand from SF leaving on the weekend of "
                "Labor Day weekend and be back after about 10 days. Find award and cash flight "
                "options."
            ),
            (date(2026, 9, 4), date(2026, 9, 7)),
            (date(2026, 9, 13), date(2026, 9, 18)),
            (9, 11),
        ),
        (
            "labor_day_thursday_flexibility",
            (
                "My boyfriend and I want to go to Thailand from SF leaving on Labor Day weekend "
                "for about 10 days. We are flexible to leave on the Thursday as well."
            ),
            (date(2026, 9, 3), date(2026, 9, 7)),
            (date(2026, 9, 12), date(2026, 9, 18)),
            (9, 11),
        ),
        (
            "return_weekend_after_departure",
            (
                "My boyfriend and I want to go to Thailand from SF leaving on Labor Day weekend "
                "and come back the weekend afterwards."
            ),
            (date(2026, 9, 4), date(2026, 9, 7)),
            (date(2026, 9, 12), date(2026, 9, 13)),
            None,
        ),
        (
            "exact_dates_and_cabin",
            (
                "Find me two business class award seats from Seattle to Tokyo leaving October 5 "
                "and returning October 15."
            ),
            (date(2026, 10, 5), date(2026, 10, 5)),
            (date(2026, 10, 15), date(2026, 10, 15)),
            None,
        ),
        (
            "early_month_with_approximate_duration",
            "My boyfriend and I want to go to Thailand from SF for about 10 days in early May",
            (date(2027, 5, 1), date(2027, 5, 10)),
            (date(2027, 5, 10), date(2027, 5, 21)),
            (9, 11),
        ),
        (
            "unbounded_after_new_year",
            "My boyfriend and I want to go to Europe from LA for 1 or 2 weeks after new year",
            None,
            None,
            (7, 14),
        ),
    ],
)
def test_six_proven_cases_compile_through_existing_evaluator(
    case_id: str,
    text: str,
    departure: tuple[date, date] | None,
    return_date: tuple[date, date] | None,
    duration: tuple[int, int] | None,
) -> None:
    _scan, _catalog, compiled = _compile(text)
    if departure is None:
        assert compiled.departure_window is None
    else:
        assert compiled.departure_window is not None
        assert (compiled.departure_window.start, compiled.departure_window.end) == departure
    if return_date is None:
        assert compiled.return_window is None
    else:
        assert compiled.return_window is not None
        assert (compiled.return_window.start, compiled.return_window.end) == return_date
    if duration is None:
        assert compiled.proposal.interpreted_duration is None
    else:
        assert compiled.proposal.interpreted_duration is not None
        assert (
            compiled.proposal.interpreted_duration.minimum_days,
            compiled.proposal.interpreted_duration.maximum_days,
        ) == duration


def test_anchor_scope_distinguishes_direct_reference_and_unresolved_support() -> None:
    _scan, catalog, _compiled = _compile(
        "Leave Labor Day weekend; Thursday as well works. Or leave two weekends after Thanksgiving."
    )
    modes = {use.mode for candidate in catalog.candidates for use in candidate.anchor_uses}
    assert AnchorUseMode.DIRECT_WINDOW in modes
    assert AnchorUseMode.REFERENCE_ONLY in modes

    unsupported = build_temporal_candidates(
        scan_temporal_request(_request("Leave the first week of June."))
    )
    uses = [use for candidate in unsupported.candidates for use in candidate.anchor_uses]
    assert AnchorUseMode.UNRESOLVED_SUPPORT in {use.mode for use in uses}


def test_unsupported_first_week_uses_only_its_own_month_anchor() -> None:
    catalog = build_temporal_candidates(
        scan_temporal_request(_request("Leave the first week of June, not October."))
    )
    unresolved = next(
        candidate
        for candidate in catalog.candidates
        if candidate.relation.value == "unresolved"
        and candidate.reason == "unsupported temporal grammar"
    )
    assert [use.handle for use in unresolved.anchor_uses] == ["a0"]
    assert any(
        candidate.relation.value == "month_portion" and candidate.anchor_uses[0].handle == "a1"
        for candidate in catalog.candidates
    )


def test_unsupported_non_contiguous_weekends_remain_unresolved() -> None:
    _scan, catalog, compiled = _compile("Leave the first and third weekends of June.")
    assert compiled.departure_window is None
    assert compiled.proposal.unresolved
    assert not any(
        candidate.relation is CandidateRelation.MONTH_PORTION for candidate in catalog.candidates
    )
    unresolved = next(
        candidate
        for candidate in catalog.candidates
        if candidate.reason == "unsupported temporal grammar"
    )
    assert unresolved.anchor_uses[0].mode is AnchorUseMode.UNRESOLVED_SUPPORT


def test_bare_labor_day_is_not_silently_compiled_as_a_weekend() -> None:
    catalog = build_temporal_candidates(scan_temporal_request(_request("Leave on Labor Day.")))
    assert not any(
        candidate.relation.value == "holiday_weekend" for candidate in catalog.candidates
    )


def test_every_safe_group_has_an_explicit_unresolved_candidate() -> None:
    scan = scan_temporal_request(_request("Leave Labor Day weekend for 10 days."))
    catalog = build_temporal_candidates(scan)
    groups: dict[str, list[TemporalCandidate]] = {}
    for candidate in catalog.candidates:
        groups.setdefault(candidate.exclusive_group, []).append(candidate)
    assert all(
        any(candidate.relation.value == "unresolved" for candidate in choices)
        for choices in groups.values()
    )
    assert all(
        catalog.by_handle(handle).relation.value != "unresolved"
        for handle in auto_select_candidates(catalog)
    )


def test_all_ready_scanner_catalogs_pass_structural_catalog_validation() -> None:
    for case in _ready_corpus_cases().values():
        context = cast(dict[str, object], case["context"])
        reference_date = context["reference_date"]
        timezone = context["timezone"]
        text = case["input"]
        assert isinstance(reference_date, str)
        assert isinstance(timezone, str)
        assert isinstance(text, str)
        request = RawRequest(
            text=text,
            context=RequestContext(
                reference_date=date.fromisoformat(reference_date), timezone=timezone
            ),
        )
        validate_candidate_catalog(build_temporal_candidates(scan_temporal_request(request)))


@pytest.mark.parametrize("text", ["Leave the first week of June.", "Leave next spring."])
def test_unsupported_grammar_remains_unresolved(text: str) -> None:
    _scan, catalog, compiled = _compile(text)
    assert compiled.departure_window is None
    assert compiled.proposal.unresolved
    assert not any(candidate.relation.value == "month_portion" for candidate in catalog.candidates)


def test_scanner_ignores_malformed_pass_one_shape_by_accepting_only_raw_request() -> None:
    request = _request("Leave Labor Day weekend.")
    scan = scan_temporal_request(request)
    assert [anchor.holiday for anchor in scan.anchors] == [Holiday.LABOR_DAY]
    assert "pass_one" not in scan_temporal_request.__annotations__


def test_unbounded_departure_keeps_literal_duration_known() -> None:
    _scan, _catalog, compiled = _compile("Leave after New Year for 10 days.")
    assert compiled.departure_window is None
    assert len(compiled.literal_duration) == 1
    assert compiled.proposal.interpreted_duration is not None


def test_scanner_does_not_compile_a_point_offset_as_trip_duration() -> None:
    scan = scan_temporal_request(_request("Leave in 10 days."))
    catalog = build_temporal_candidates(scan)

    assert scan.durations == ()
    assert not any(candidate.relation is CandidateRelation.DURATION for candidate in catalog.candidates)


def test_compiler_topologically_orders_reversed_selector_output_and_uses_departure_end() -> None:
    text = "Leave Labor Day weekend and return the weekend afterwards."
    scan = scan_temporal_request(_request(text))
    catalog = build_temporal_candidates(scan)
    selected = tuple(reversed(auto_select_candidates(catalog)))
    compiled = compile_temporal_candidates(
        _request(text), catalog, selected, holiday_provider=FakeHolidayProvider()
    )
    relation = next(
        item for item in compiled.graph.constraints if isinstance(item, RelativeWeekendConstraint)
    )
    assert isinstance(relation.reference, DecisionReference)
    assert relation.reference.constraint_id == "d0"
    assert relation.reference.edge is TemporalEdge.END


def test_selection_rejects_unknown_duplicate_and_uncovered_groups() -> None:
    scan = scan_temporal_request(
        _request("Leave Labor Day weekend and return the weekend afterwards.")
    )
    catalog = build_temporal_candidates(scan)
    selected = auto_select_candidates(catalog)
    with pytest.raises(TemporalCandidateValidationError, match="unknown"):
        validate_candidate_selection(catalog, (*selected, "not-a-candidate"))
    with pytest.raises(TemporalCandidateValidationError, match="duplicates"):
        validate_candidate_selection(catalog, (*selected, selected[0]))
    with pytest.raises(TemporalCandidateValidationError, match="coverage"):
        validate_candidate_selection(catalog, selected[:-1])


def _manual_catalog(*candidates: TemporalCandidate) -> TemporalCandidateCatalog:
    return TemporalCandidateCatalog(scan_temporal_request(_request("Travel.")), candidates)


def test_selection_rejects_candidate_dependency_cycle() -> None:
    catalog = _manual_catalog(
        TemporalCandidate(
            handle="a",
            exclusive_group="ga",
            covers=(),
            requires=("return",),
            produces=("departure",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            target=TemporalTarget.DEPARTURE,
        ),
        TemporalCandidate(
            handle="b",
            exclusive_group="gb",
            covers=(),
            requires=("departure",),
            produces=("return",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            target=TemporalTarget.RETURN,
        ),
    )
    with pytest.raises(TemporalCandidateValidationError, match="dependency cycle"):
        validate_candidate_selection(catalog, ("a", "b"))


def test_selection_rejects_cross_target_composition() -> None:
    catalog = _manual_catalog(
        TemporalCandidate(
            handle="departure",
            exclusive_group="g-departure",
            covers=(),
            requires=(),
            produces=("departure",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            target=TemporalTarget.DEPARTURE,
        ),
        TemporalCandidate(
            handle="return-composition",
            exclusive_group="g-return",
            covers=(),
            requires=("departure",),
            produces=("return",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            composition=CandidateComposition.EXTEND_START,
            composition_operand="departure",
            target=TemporalTarget.RETURN,
        ),
    )
    with pytest.raises(TemporalCandidateValidationError, match="cross-target composition"):
        validate_candidate_selection(catalog, ("departure", "return-composition"))


def test_production_slots_bind_labor_day_to_thursday_even_when_text_order_is_reversed() -> None:
    text = "We can leave Thursday also, for Labor Day weekend."
    scan = scan_temporal_request(_request(text))
    catalog = build_temporal_candidates(scan)
    holiday = next(
        item for item in catalog.candidates if item.relation is CandidateRelation.HOLIDAY_WEEKEND
    )
    extension = next(
        item
        for item in catalog.candidates
        if item.relation is CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY
    )
    assert extension.requires == holiday.produces
    assert extension.composition_operand == holiday.produces[0]
    assert extension.produces != holiday.produces

    compiled = compile_temporal_candidates(
        _request(text),
        catalog,
        tuple(reversed(auto_select_candidates(catalog))),
        holiday_provider=FakeHolidayProvider(),
    )
    relations = [
        item for item in compiled.graph.constraints if isinstance(item, RelativeWeekdayConstraint)
    ]
    assert len(relations) == 1
    assert relations[0].combine_with == "d0"
    assert isinstance(relations[0].reference, DecisionReference)
    assert relations[0].reference.constraint_id == "d0"


def test_alternatives_share_one_production_slot_but_selected_producer_is_unique() -> None:
    catalog = _manual_catalog(
        TemporalCandidate(
            handle="first",
            exclusive_group="alternatives",
            covers=(),
            requires=(),
            produces=("slot:departure",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            target=TemporalTarget.DEPARTURE,
        ),
        TemporalCandidate(
            handle="second",
            exclusive_group="alternatives",
            covers=(),
            requires=(),
            produces=("slot:departure",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            target=TemporalTarget.DEPARTURE,
        ),
    )
    assert validate_candidate_selection(catalog, ("first",))[0].produces == ("slot:departure",)
    assert validate_candidate_selection(catalog, ("second",))[0].produces == ("slot:departure",)


def test_selection_rejects_multiple_selected_producers_for_one_slot() -> None:
    catalog = _manual_catalog(
        TemporalCandidate(
            handle="one",
            exclusive_group="one",
            covers=(),
            requires=(),
            produces=("slot:shared",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            target=TemporalTarget.DEPARTURE,
        ),
        TemporalCandidate(
            handle="two",
            exclusive_group="two",
            covers=(),
            requires=(),
            produces=("slot:shared",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            target=TemporalTarget.DEPARTURE,
        ),
    )
    with pytest.raises(TemporalCandidateValidationError, match="multiple selected producers"):
        validate_candidate_selection(catalog, ("one", "two"))


@pytest.mark.parametrize(
    "composition_operand,requires,error",
    [
        (None, ("slot:departure",), "explicit operand"),
        ("slot:other", ("slot:departure",), "operand is not required"),
        ("slot:missing", ("slot:missing",), "unproduced value"),
    ],
)
def test_selection_rejects_invalid_composition_operands(
    composition_operand: str | None, requires: tuple[str, ...], error: str
) -> None:
    catalog = _manual_catalog(
        TemporalCandidate(
            handle="departure",
            exclusive_group="departure",
            covers=(),
            requires=(),
            produces=("slot:departure",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            target=TemporalTarget.DEPARTURE,
        ),
        TemporalCandidate(
            handle="composition",
            exclusive_group="composition",
            covers=(),
            requires=requires,
            produces=("slot:extended",),
            priority=1,
            anchor_uses=(),
            relation=CandidateRelation.UNRESOLVED,
            composition=CandidateComposition.EXTEND_START,
            composition_operand=composition_operand,
            target=TemporalTarget.DEPARTURE,
        ),
    )
    with pytest.raises(TemporalCandidateValidationError, match=error):
        validate_candidate_selection(catalog, ("departure", "composition"))


def test_chained_slot_compositions_topologically_compile_from_reversed_selection() -> None:
    scan = scan_temporal_request(_request("Travel next month."))
    catalog = TemporalCandidateCatalog(
        scan=scan,
        candidates=(
            TemporalCandidate(
                handle="base",
                exclusive_group="base",
                covers=(),
                requires=(),
                produces=("slot:base",),
                priority=1,
                anchor_uses=(),
                relation=CandidateRelation.RELATIVE_CALENDAR_PERIOD,
                target=TemporalTarget.DEPARTURE,
                clause_handle="e0",
            ),
            TemporalCandidate(
                handle="first-extension",
                exclusive_group="first-extension",
                covers=(),
                requires=("slot:base",),
                produces=("slot:first",),
                priority=1,
                anchor_uses=(),
                relation=CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY,
                composition=CandidateComposition.EXTEND_START,
                composition_operand="slot:base",
                target=TemporalTarget.DEPARTURE,
                clause_handle="e0",
            ),
            TemporalCandidate(
                handle="second-extension",
                exclusive_group="second-extension",
                covers=(),
                requires=("slot:first",),
                produces=("slot:second",),
                priority=1,
                anchor_uses=(),
                relation=CandidateRelation.EXTEND_DEPARTURE_TO_THURSDAY,
                composition=CandidateComposition.EXTEND_START,
                composition_operand="slot:first",
                target=TemporalTarget.DEPARTURE,
                clause_handle="e0",
            ),
        ),
    )
    compiled = compile_temporal_candidates(
        _request("Travel next month."),
        catalog,
        ("second-extension", "first-extension", "base"),
    )
    assert [item.constraint_id for item in compiled.graph.constraints] == ["d0", "d1", "d2"]
    extensions = [
        item for item in compiled.graph.constraints if isinstance(item, RelativeWeekdayConstraint)
    ]
    assert [item.combine_with for item in extensions] == ["d0", "d1"]
    assert isinstance(compiled.graph.constraints[0], RelativeCalendarPeriodConstraint)


def test_repeated_holiday_candidates_bind_the_anchor_in_their_own_clause() -> None:
    catalog = build_temporal_candidates(
        scan_temporal_request(
            _request(
                "Travel after New Year, then after New Year again; "
                "leave Labor Day weekend, then Labor Day weekend again."
            )
        )
    )
    clauses = {clause.handle: clause for clause in catalog.scan.clauses}
    anchors = {anchor.handle: anchor for anchor in catalog.scan.anchors}
    candidates = [
        candidate
        for candidate in catalog.candidates
        if candidate.relation
        in {CandidateRelation.HOLIDAY_WEEKEND, CandidateRelation.UNBOUNDED_AFTER}
    ]
    assert len(candidates) == 4
    for candidate in candidates:
        assert candidate.clause_handle is not None
        clause = clauses[candidate.clause_handle]
        anchor = anchors[candidate.anchor_uses[0].handle]
        assert clause.start <= anchor.clause.start
        assert anchor.clause.end <= clause.end


class StaticNonTemporalExtractor:
    """Selector-only Pass-1 fixture."""

    def __init__(self, extraction: NonTemporalIntentExtraction) -> None:
        self.extraction = extraction

    def extract_non_temporal(
        self, _input: NonTemporalExtractionInput
    ) -> NonTemporalIntentExtraction:
        return self.extraction

class SupportedSelector:
    """Choose the compiler-authored supported candidate from every published group."""

    def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
        return TemporalSelectorOutput(
            selected_candidates=[group.candidates[0].handle for group in model_input.candidate_groups]
        )


def _non_temporal(*, origin: bool = True, destination: bool = True) -> NonTemporalIntentExtraction:
    return NonTemporalIntentExtraction(
        travelers=1,
        origins=(
            [LocationRef(kind=LocationKind.CITY, value="Origin", raw_text="Origin")]
            if origin
            else []
        ),
        destinations=(
            [LocationRef(kind=LocationKind.CITY, value="Destination", raw_text="Destination")]
            if destination
            else []
        ),
        search_modes=[SearchMode.AWARD],
    )


def test_compiler_route_preserves_city_level_locations_without_airport_ambiguity() -> None:
    text = "I can go from LA to SF using points."
    extraction = NonTemporalIntentExtraction(
        travelers=1,
        origins=[LocationRef(kind=LocationKind.CITY, value="Los Angeles", raw_text="LA")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="San Francisco", raw_text="SF")],
        search_modes=[SearchMode.AWARD],
    )

    result = understand_request(
        _request(text),
        StaticNonTemporalExtractor(extraction),
        SupportedSelector(),
        holiday_provider=FakeHolidayProvider(),
    )

    assert result.parsed_request.travelers == 1
    assert result.parsed_request.origins == extraction.origins
    assert result.parsed_request.destinations == extraction.destinations
    assert not result.parsed_request.unknowns or all(
        unknown.field not in {"origin", "destination"} for unknown in result.parsed_request.unknowns
    )
    assert result.clarification.field == "departure"


def test_compiler_route_preserves_blocking_geographic_identity_ambiguity() -> None:
    text = "I can go from Springfield to Tokyo using points."
    extraction = NonTemporalIntentExtraction(
        travelers=1,
        origins=[LocationRef(kind=LocationKind.CITY, value="Springfield", raw_text="Springfield")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        search_modes=[SearchMode.AWARD],
        ambiguities=[
            NonTemporalAmbiguity(
                field="origin",
                detail="Springfield has multiple plausible geographic identities.",
                raw_text="Springfield",
            )
        ],
    )

    result = understand_request(
        _request(text),
        StaticNonTemporalExtractor(extraction),
        SupportedSelector(),
        holiday_provider=FakeHolidayProvider(),
    )

    assert any(unknown.field == "origin" for unknown in result.parsed_request.unknowns)
    assert result.clarification.field == "origin"


def test_compiler_route_keeps_alternatives_and_tentative_nested_destination_nonblocking() -> None:
    text = "I can go from SF to Brazil, probably Sao Paulo, using points."
    extraction = NonTemporalIntentExtraction(
        travelers=1,
        origins=[LocationRef(kind=LocationKind.CITY, value="San Francisco", raw_text="SF")],
        destinations=[
            LocationRef(kind=LocationKind.COUNTRY, value="Brazil", raw_text="Brazil"),
            LocationRef(kind=LocationKind.CITY, value="São Paulo", raw_text="Sao Paulo"),
        ],
        search_modes=[SearchMode.AWARD],
        ambiguities=[
            NonTemporalAmbiguity(
                field="destination_preference",
                detail="São Paulo is tentative within Brazil.",
                raw_text="probably Sao Paulo",
            )
        ],
    )

    result = understand_request(
        _request(text),
        StaticNonTemporalExtractor(extraction),
        SupportedSelector(),
        holiday_provider=FakeHolidayProvider(),
    )

    assert result.parsed_request.destinations == extraction.destinations
    assert any(
        unknown.field == "destination_preference" for unknown in result.parsed_request.unknowns
    )
    assert result.clarification.field == "departure"


def test_compiler_route_keeps_explicit_destination_alternatives_without_ambiguity() -> None:
    text = "I can go from SF to Seoul or Taipei using points."
    extraction = NonTemporalIntentExtraction(
        travelers=1,
        origins=[LocationRef(kind=LocationKind.CITY, value="San Francisco", raw_text="SF")],
        destinations=[
            LocationRef(kind=LocationKind.CITY, value="Seoul", raw_text="Seoul"),
            LocationRef(kind=LocationKind.CITY, value="Taipei", raw_text="Taipei"),
        ],
        search_modes=[SearchMode.AWARD],
    )

    result = understand_request(
        _request(text),
        StaticNonTemporalExtractor(extraction),
        SupportedSelector(),
        holiday_provider=FakeHolidayProvider(),
    )

    assert result.parsed_request.destinations == extraction.destinations
    assert all(unknown.field != "destination" for unknown in result.parsed_request.unknowns)
    assert result.clarification.field == "departure"


@pytest.mark.parametrize(
    ("text", "travelers"),
    [
        ("I can go from SF to Tokyo using points.", 1),
        ("I can help book flights for my parents from SF to Tokyo using points.", None),
    ],
)
def test_compiler_route_preserves_first_person_traveler_contract(
    text: str, travelers: int | None
) -> None:
    extraction = NonTemporalIntentExtraction(
        travelers=travelers,
        origins=[LocationRef(kind=LocationKind.CITY, value="San Francisco", raw_text="SF")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        search_modes=[SearchMode.AWARD],
    )

    result = understand_request(
        _request(text),
        StaticNonTemporalExtractor(extraction),
        SupportedSelector(),
        holiday_provider=FakeHolidayProvider(),
    )

    assert result.parsed_request.travelers == travelers
    assert result.clarification.field == "departure"
    assert any(unknown.field == "travelers" for unknown in result.parsed_request.unknowns) is (
        travelers is None
    )


_READY_GRAPH_KINDS: dict[str, tuple[str, ...]] = {
    "labor_day_thailand": ("anchor_window", "duration"),
    "labor_day_thursday_flexibility": ("anchor_window", "duration", "relative_weekday"),
    "return_weekend_after_departure": ("anchor_window", "relative_weekend"),
    "exact_dates_and_cabin": ("anchor_window", "anchor_window"),
    "missing_origin": ("duration", "month_portion"),
    "missing_travel_period": (),
    "relative_date_expression": ("relative_weekend",),
    "approximate_duration": ("duration", "unresolved"),
    "conflicting_dates": ("anchor_window", "duration", "unbounded_boundary"),
    "multiple_destination_options": ("anchor_window", "duration"),
    "repositioning_allowed": ("unresolved",),
    "adversarial_schema_instruction": ("relative_calendar_period",),
    "early_month_with_approximate_duration": ("duration", "month_portion"),
    "unbounded_after_new_year": ("duration", "unbounded_boundary"),
    "whole_month_with_exact_duration": ("duration", "month_portion"),
    "tentative_city_and_month": ("month_portion",),
}


@cache
def _ready_corpus_cases() -> dict[str, dict[str, object]]:
    payload = yaml.safe_load(
        (Path(__file__).parents[2] / "evals" / "intent" / "cases.yaml").read_text()
    )
    scenarios = payload["scenarios"]
    return {scenario["id"]: scenario for scenario in scenarios if scenario.get("status") == "ready"}


@pytest.mark.parametrize(
    (
        "case_id, text, reference_date, expected_departure, expected_return, expected_clarification, "
        "oracle_handles, has_origin"
    ),
    [
        (
            "labor_day_thailand",
            "Leave Labor Day weekend for about 10 days.",
            date(2026, 8, 29),
            (date(2026, 9, 4), date(2026, 9, 7)),
            (date(2026, 9, 13), date(2026, 9, 18)),
            None,
            (
                "holiday_weekend:departure:weekend-of-labor-day-weekend",
                "duration:return:about-10-days",
            ),
            True,
        ),
        (
            "labor_day_thursday_flexibility",
            "Leave Labor Day weekend for about 10 days; Thursday as well.",
            date(2026, 8, 29),
            (date(2026, 9, 3), date(2026, 9, 7)),
            (date(2026, 9, 12), date(2026, 9, 18)),
            None,
            (
                "holiday_weekend:departure:labor-day-weekend",
                "extend_departure_to_thursday:departure:thursday-as-well",
                "duration:return:about-10-days",
            ),
            True,
        ),
        (
            "return_weekend_after_departure",
            "Leave Labor Day weekend and return the weekend afterwards.",
            date(2026, 8, 29),
            (date(2026, 9, 4), date(2026, 9, 7)),
            (date(2026, 9, 12), date(2026, 9, 13)),
            None,
            (
                "holiday_weekend:departure:labor-day-weekend",
                "return_weekend_after_departure:return:the-weekend-afterwards",
            ),
            True,
        ),
        (
            "exact_dates_and_cabin",
            "Leave October 5 and return October 15.",
            date(2026, 8, 30),
            (date(2026, 10, 5), date(2026, 10, 5)),
            (date(2026, 10, 15), date(2026, 10, 15)),
            None,
            ("exact_date:departure:october-5", "exact_date:return:october-15"),
            True,
        ),
        (
            "missing_origin",
            "Travel for a week in May.",
            date(2026, 1, 12),
            (date(2026, 5, 1), date(2026, 5, 31)),
            (date(2026, 5, 8), date(2026, 6, 7)),
            "origin",
            ("month_portion:departure:may", "duration:return:a-week"),
            False,
        ),
        (
            "missing_travel_period",
            "Find award flights from LAX to Sydney.",
            date(2026, 4, 18),
            None,
            None,
            "departure",
            (),
            True,
        ),
        (
            "relative_date_expression",
            "Leave two weekends after Thanksgiving.",
            date(2026, 11, 20),
            (date(2026, 12, 5), date(2026, 12, 6)),
            None,
            "return_or_duration",
            ("relative_weekend_after_anchor:departure:two-weekends-after-thanksgiving",),
            True,
        ),
        (
            "approximate_duration",
            "Leave around the first week of June and stay for about nine days.",
            date(2026, 2, 2),
            None,
            None,
            "departure",
            ("unresolved:departure:first-week-of-june", "duration:return:about-nine-days"),
            True,
        ),
        (
            "conflicting_dates",
            "Leave July 10, back before July 8, for a 10-day trip.",
            date(2026, 5, 1),
            (date(2026, 7, 10), date(2026, 7, 10)),
            None,
            "dates",
            (
                "unbounded_before:return:back-before-july-8",
                "exact_date:departure:july-10",
                "duration:return:10-day",
            ),
            True,
        ),
        (
            "multiple_destination_options",
            "Travel over Christmas for about a week.",
            date(2026, 9, 14),
            (date(2026, 12, 24), date(2026, 12, 26)),
            (date(2026, 12, 30), date(2027, 1, 3)),
            None,
            ("christmas_period:departure:over-christmas", "duration:return:about-a-week"),
            True,
        ),
        (
            "repositioning_allowed",
            "Travel next spring.",
            date(2026, 10, 3),
            None,
            None,
            "departure",
            ("unresolved:departure:next-spring",),
            True,
        ),
        (
            "adversarial_schema_instruction",
            "Travel next month.",
            date(2026, 8, 30),
            (date(2026, 9, 1), date(2026, 9, 30)),
            None,
            "return_or_duration",
            ("relative_calendar_period:departure:next-month",),
            True,
        ),
        (
            "early_month_with_approximate_duration",
            "Travel in early May for about 10 days.",
            date(2026, 8, 29),
            (date(2027, 5, 1), date(2027, 5, 10)),
            (date(2027, 5, 10), date(2027, 5, 21)),
            None,
            ("month_portion:departure:early-may", "duration:return:about-10-days"),
            True,
        ),
        (
            "unbounded_after_new_year",
            "Travel after New Year for 1 or 2 weeks.",
            date(2026, 8, 29),
            None,
            None,
            "departure",
            ("unbounded_after:departure:after-new-year", "duration:return:1-or-2-weeks"),
            True,
        ),
        (
            "whole_month_with_exact_duration",
            "Travel for 2 weeks in October.",
            date(2026, 8, 29),
            (date(2026, 10, 1), date(2026, 10, 31)),
            (date(2026, 10, 15), date(2026, 11, 14)),
            None,
            ("month_portion:departure:october", "duration:return:2-weeks"),
            True,
        ),
        (
            "tentative_city_and_month",
            "Maybe sometime in January.",
            date(2026, 8, 29),
            (date(2027, 1, 1), date(2027, 1, 31)),
            None,
            "return_or_duration",
            ("month_portion:departure:january",),
            True,
        ),
    ],
)
def test_ready_case_oracles_compile_and_flow_without_a_temporal_model(
    case_id: str,
    text: str,
    reference_date: date,
    expected_departure: tuple[date, date] | None,
    expected_return: tuple[date, date] | None,
    expected_clarification: str | None,
    oracle_handles: tuple[str, ...],
    has_origin: bool,
) -> None:
    corpus_case = _ready_corpus_cases()[case_id]
    corpus_context = cast(dict[str, object], corpus_case["context"])
    reference_value = corpus_context["reference_date"]
    timezone_value = corpus_context["timezone"]
    assert isinstance(reference_value, str)
    assert isinstance(timezone_value, str)
    assert reference_date == date.fromisoformat(reference_value)
    # The fixed corpus request, not a shortened paraphrase, is the scanner input
    # for this offline gate.  Non-temporal output remains hand-authored below.
    text_value = corpus_case["input"]
    assert isinstance(text_value, str)
    text = text_value
    request = RawRequest(
        text=text,
        context=RequestContext(reference_date=reference_date, timezone=timezone_value),
    )
    scan = scan_temporal_request(request)
    catalog = build_temporal_candidates(scan)
    selected = auto_select_candidates(catalog)
    assert sorted(selected) == sorted(oracle_handles), case_id
    assert all(
        not segment.startswith("e") or not segment[1:].isdigit()
        for handle in selected
        for segment in handle.split(":")
    ), case_id

    compiled = compile_temporal_candidates(
        request, catalog, selected, holiday_provider=FakeHolidayProvider()
    )
    assert sorted(constraint.kind for constraint in compiled.graph.constraints) == sorted(
        _READY_GRAPH_KINDS[case_id]
    ), case_id
    assert (
        None
        if compiled.departure_window is None
        else (compiled.departure_window.start, compiled.departure_window.end)
    ) == expected_departure, case_id
    assert (
        None
        if compiled.return_window is None
        else (compiled.return_window.start, compiled.return_window.end)
    ) == expected_return, case_id

    result = understand_request(
        request,
        StaticNonTemporalExtractor(_non_temporal(origin=has_origin)),
        SupportedSelector(),
        FakeHolidayProvider(),
    )
    assert result.clarification.field == expected_clarification, case_id
    assert (
        None
        if result.parsed_request.departure_window is None
        else (
            result.parsed_request.departure_window.start,
            result.parsed_request.departure_window.end,
        )
    ) == expected_departure, case_id
    assert (
        None
        if result.parsed_request.return_window is None
        else (result.parsed_request.return_window.start, result.parsed_request.return_window.end)
    ) == expected_return, case_id
    if case_id == "conflicting_dates":
        assert [conflict.code for conflict in result.parsed_request.conflicts] == [
            "return_before_departure"
        ]
        assert compiled.endpoint_bounds[0].boundary == date(2026, 7, 8)


@pytest.mark.parametrize(
    "text",
    [
        "Leave the first week of June for about nine days.",
        "Travel for 10 days.",
    ],
)
def test_day_duration_without_a_bounded_departure_remains_known(text: str) -> None:
    _scan, _catalog, compiled = _compile(text)
    assert compiled.departure_window is None
    assert compiled.return_window is None
    assert compiled.proposal.interpreted_duration is not None
