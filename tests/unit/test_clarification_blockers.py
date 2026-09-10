"""Focused Step-2 blocker collection and prompt-rendering tests."""

from datetime import date

from award_agent.clarification import (
    build_clarification_prompt,
    collect_blocking_requirements,
    render_clarification_prompt,
)
from award_agent.clarification.projection import project_initial_request
from award_agent.domain import (
    BlockingRequirementKind,
    Conflict,
    EffectiveRequest,
    LocationKind,
    LocationRef,
    ParsedRequest,
    RequestContext,
    UnknownField,
    UnknownReason,
)

_CONTEXT = RequestContext(reference_date=date(2026, 9, 8), timezone="America/Los_Angeles")


def _effective(
    *,
    unknowns: tuple[UnknownField, ...] = (),
    conflicts: tuple[Conflict, ...] = (),
) -> EffectiveRequest:
    return EffectiveRequest(
        raw_text="A trip request.",
        context=_CONTEXT,
        unknowns=unknowns,
        conflicts=conflicts,
    )


def _unknown(field: str) -> UnknownField:
    return UnknownField(
        field=field,
        reason=UnknownReason.MISSING,
        detail=f"{field} is missing",
    )


def test_collects_all_blockers_in_stable_order_and_suppresses_duplicates() -> None:
    effective = _effective(
        unknowns=(
            _unknown("travelers"),
            _unknown("cabin"),
            _unknown("origin"),
            _unknown("origin"),
            _unknown("return_or_duration"),
            _unknown("departure"),
            _unknown("destination"),
            _unknown("search_modes"),
        ),
        conflicts=(
            Conflict(code="z_conflict", fields=["return"], detail="private detail"),
            Conflict(code="a_conflict", fields=["departure"], detail="private detail"),
            Conflict(code="a_conflict", fields=["departure"], detail="duplicate"),
        ),
    )

    requirements = collect_blocking_requirements(effective)

    assert [item.requirement_id for item in requirements] == [
        "conflict:a_conflict",
        "conflict:z_conflict",
        "origin",
        "destination",
        "departure",
        "return_or_duration",
        "travelers",
    ]
    assert [item.kind for item in requirements] == [
        BlockingRequirementKind.CONFLICT,
        BlockingRequirementKind.CONFLICT,
        BlockingRequirementKind.ORIGIN,
        BlockingRequirementKind.DESTINATION,
        BlockingRequirementKind.DEPARTURE,
        BlockingRequirementKind.RETURN_OR_DURATION,
        BlockingRequirementKind.TRAVELERS,
    ]


def test_nonblocking_unknowns_are_excluded() -> None:
    effective = _effective(
        unknowns=(_unknown("cabin"), _unknown("search_modes"), _unknown("repositioning_allowed")),
    )

    assert collect_blocking_requirements(effective) == ()
    assert build_clarification_prompt(effective, revision=0) is None


def test_ready_request_has_no_blockers_and_no_prompt() -> None:
    effective = _effective()

    assert collect_blocking_requirements(effective) == ()
    assert render_clarification_prompt((), revision=4) is None


def test_prompt_is_one_template_message_with_exact_requirement_coverage() -> None:
    effective = _effective(
        unknowns=(_unknown("travelers"), _unknown("origin"), _unknown("destination")),
        conflicts=(Conflict(code="date_conflict", fields=["departure"], detail="private detail"),),
    )

    prompt = build_clarification_prompt(effective, revision=3, prompt_id="prompt-3")

    assert prompt is not None
    assert prompt.prompt_id == "prompt-3"
    assert prompt.revision == 3
    assert tuple(item.requirement_id for item in prompt.requirements) == (
        "conflict:date_conflict",
        "origin",
        "destination",
        "travelers",
    )
    assert prompt.message.count("\n") == len(prompt.requirements)
    assert "private detail" not in prompt.message
    assert "A trip request" not in prompt.message
    assert prompt.message.startswith("I’d be happy to help plan this trip.")
    assert "Where will you be departing from?" in prompt.message
    assert "How many people will be traveling?" in prompt.message


def test_prompt_renderer_orders_an_iterable_even_when_input_is_not_canonical() -> None:
    effective = _effective(unknowns=(_unknown("travelers"), _unknown("origin")))
    requirements = collect_blocking_requirements(effective)

    prompt = render_clarification_prompt(tuple(reversed(requirements)), revision=0)

    assert prompt is not None
    assert tuple(item.requirement_id for item in prompt.requirements) == ("origin", "travelers")


def test_initial_projection_preserves_unknowns_and_conflicts_for_blocker_collection() -> None:
    parsed = ParsedRequest(
        raw_text="A trip request.",
        context=_CONTEXT,
        travelers=None,
        origins=[],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        departure_expression=None,
        return_expression=None,
        departure_window=None,
        return_window=None,
        duration=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=[_unknown("travelers"), _unknown("origin"), _unknown("departure")],
        conflicts=[Conflict(code="date_conflict", fields=["dates"], detail="private detail")],
    )

    effective = project_initial_request(parsed)

    assert tuple(item.requirement_id for item in collect_blocking_requirements(effective)) == (
        "conflict:date_conflict",
        "origin",
        "departure",
        "travelers",
    )
