"""Additive contracts for ADR 0011 clarification sessions.

These contracts deliberately sit beside, rather than inside, the frozen initial
request-understanding contracts.  A session records an immutable-looking ledger
of projections and answer turns; deterministic reduction is introduced by the
continuation controller in a later implementation step.
"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from award_agent.domain.models import (
    CabinClass,
    Conflict,
    ContractModel,
    DateWindow,
    InterpretedDuration,
    LocationRef,
    RequestContext,
    RequestUnderstandingResult,
    SearchMode,
    UnknownField,
)


class SessionContractModel(ContractModel):
    """A continuation-only contract with isolated nested model state.

    Pydantic's ``frozen`` setting prevents field reassignment but does not make a
    mutable nested v1 contract immutable.  Session contracts therefore
    round-trip nested model inputs at construction and return copies for the
    fields that retain mutable nested data.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def isolate_nested_models(cls, data: object) -> object:
        return _round_trip_nested_models(data)

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)
        if name in super().__getattribute__("_copy_on_read_fields"):
            return deepcopy(value)
        return value


def _round_trip_nested_models(value: object) -> object:
    """Convert nested Pydantic inputs to plain data before validation.

    Passing a v1 ``BaseModel`` directly would otherwise preserve its nested
    object references inside this additive frozen boundary.
    """

    if isinstance(value, BaseModel):
        return _round_trip_nested_models(value.model_dump(mode="python", round_trip=True))
    if isinstance(value, dict):
        return {key: _round_trip_nested_models(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_round_trip_nested_models(item) for item in value)
    if isinstance(value, list):
        return [_round_trip_nested_models(item) for item in value]
    return value


class ClarificationSessionStatus(str, Enum):
    AWAITING_ANSWER = "awaiting_answer"
    READY = "ready"
    STOPPED = "stopped"


class ClarificationStopReason(str, Enum):
    CANCELLED = "cancelled"
    ANSWER_TURN_LIMIT = "answer_turn_limit"
    NO_PROGRESS_LIMIT = "no_progress_limit"
    UNSUPPORTED_REQUEST_REVISION = "unsupported_request_revision"


class ClarificationSessionLimits(SessionContractModel):
    """Deterministic limits approved for the first continuation implementation."""

    max_answer_turns: int = Field(default=6, ge=1)
    max_consecutive_no_progress: int = Field(default=2, ge=1)


class MessageSpan(SessionContractModel):
    """Verbatim answer evidence with answer-message-local offsets.

    This is intentionally distinct from ``ValidatedSourceSpan``: its offsets
    are meaningful only within the answer identified by ``message_id``.
    """

    message_id: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_order(self) -> MessageSpan:
        if self.end <= self.start:
            raise ValueError("message span end must be greater than start")
        return self


class EffectiveField(str, Enum):
    ORIGIN = "origin"
    DESTINATION = "destination"
    DEPARTURE = "departure"
    RETURN_OR_DURATION = "return_or_duration"
    TRAVELERS = "travelers"
    CABIN = "cabin"
    SEARCH_MODE = "search_mode"
    REPOSITIONING = "repositioning"
    HARD_CONSTRAINTS = "hard_constraints"


class InitialSnapshotSource(SessionContractModel):
    kind: Literal["initial_snapshot"] = "initial_snapshot"
    field: EffectiveField


class AnswerMessageSource(SessionContractModel):
    kind: Literal["answer_message"] = "answer_message"
    span: MessageSpan


EffectiveValueSource = Annotated[
    InitialSnapshotSource | AnswerMessageSource,
    Field(discriminator="kind"),
]


class FieldProvenance(SessionContractModel):
    """The authoritative source of one effective request field."""

    field: EffectiveField
    source: EffectiveValueSource
    amendment_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_amendment_link(self) -> FieldProvenance:
        if isinstance(self.source, InitialSnapshotSource) and self.amendment_id is not None:
            raise ValueError("initial-snapshot provenance cannot name an amendment")
        if isinstance(self.source, AnswerMessageSource) and self.amendment_id is None:
            raise ValueError("answer-message provenance requires an amendment ID")
        return self


class TemporalContributionKind(str, Enum):
    DEPARTURE_WINDOW = "departure_window"
    RETURN_WINDOW = "return_window"
    DURATION = "duration"


class TemporalContribution(SessionContractModel):
    """One active, source-keyed temporal fact used to rebuild effective timing."""

    contribution_id: str = Field(min_length=1)
    kind: TemporalContributionKind
    source: EffectiveValueSource
    # Frozen v1 DateWindow permits an empty raw_text, so the additive projection
    # must retain it rather than rejecting an otherwise valid initial snapshot.
    raw_text: str = ""
    amendment_id: str | None = Field(default=None, min_length=1)
    date_window: DateWindow | None = None
    interpreted_duration: InterpretedDuration | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"source", "date_window", "interpreted_duration"}
    )

    @model_validator(mode="after")
    def validate_value_shape(self) -> TemporalContribution:
        has_window = self.date_window is not None
        has_duration = self.interpreted_duration is not None
        if self.kind is TemporalContributionKind.DURATION:
            if not has_duration or has_window:
                raise ValueError("duration contributions require only an interpreted duration")
        elif not has_window or has_duration:
            raise ValueError("window contributions require only a date window")
        if isinstance(self.source, InitialSnapshotSource) and self.amendment_id is not None:
            raise ValueError("initial temporal contributions cannot name an amendment")
        if isinstance(self.source, AnswerMessageSource) and self.amendment_id is None:
            raise ValueError("answer temporal contributions require an amendment ID")
        return self


class EffectiveRequest(SessionContractModel):
    """Conversation-aware, deterministically materialized request projection.

    It is a value object.  ``ClarificationSession`` revisions are the source of
    truth; no caller should mutate this object or treat it as a ``ParsedRequest``.
    """

    # ParsedRequest historically accepts an empty raw_text.  The session layer
    # is additive and must not reject a valid frozen snapshot.
    raw_text: str = ""
    context: RequestContext
    travelers: int | None = Field(default=None, ge=1)
    origins: tuple[LocationRef, ...] = ()
    destinations: tuple[LocationRef, ...] = ()
    departure_window: DateWindow | None = None
    return_window: DateWindow | None = None
    interpreted_duration: InterpretedDuration | None = None
    cabins: tuple[CabinClass, ...] = ()
    search_modes: tuple[SearchMode, ...] = ()
    repositioning_allowed: bool | None = None
    hard_constraints: tuple[str, ...] = ()
    unknowns: tuple[UnknownField, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    field_provenance: tuple[FieldProvenance, ...] = ()
    temporal_contributions: tuple[TemporalContribution, ...] = ()
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "context",
            "origins",
            "destinations",
            "departure_window",
            "return_window",
            "interpreted_duration",
            "unknowns",
            "conflicts",
            "field_provenance",
            "temporal_contributions",
        }
    )

    @model_validator(mode="after")
    def validate_unique_keys(self) -> EffectiveRequest:
        fields = [item.field for item in self.field_provenance]
        if len(fields) != len(set(fields)):
            raise ValueError("effective request field provenance must be unique per field")
        contribution_ids = [item.contribution_id for item in self.temporal_contributions]
        if len(contribution_ids) != len(set(contribution_ids)):
            raise ValueError("effective request temporal contribution IDs must be unique")
        return self


class BlockingRequirementKind(str, Enum):
    CONFLICT = "conflict"
    ORIGIN = "origin"
    DESTINATION = "destination"
    DEPARTURE = "departure"
    RETURN_OR_DURATION = "return_or_duration"
    TRAVELERS = "travelers"


class BlockingRequirement(SessionContractModel):
    """A closed-policy blocker identified without embedding user-provided text."""

    requirement_id: str = Field(min_length=1)
    kind: BlockingRequirementKind
    field: EffectiveField | None = None
    conflict_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_kind_shape(self) -> BlockingRequirement:
        if self.kind is BlockingRequirementKind.CONFLICT:
            if self.conflict_code is None or self.field is not None:
                raise ValueError("conflict requirements require conflict_code and no field")
            return self
        expected_fields = {
            BlockingRequirementKind.ORIGIN: EffectiveField.ORIGIN,
            BlockingRequirementKind.DESTINATION: EffectiveField.DESTINATION,
            BlockingRequirementKind.DEPARTURE: EffectiveField.DEPARTURE,
            BlockingRequirementKind.RETURN_OR_DURATION: EffectiveField.RETURN_OR_DURATION,
            BlockingRequirementKind.TRAVELERS: EffectiveField.TRAVELERS,
        }
        if self.field is not expected_fields[self.kind] or self.conflict_code is not None:
            raise ValueError("field requirements must use their matching effective field")
        return self


class ClarificationPrompt(SessionContractModel):
    prompt_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    requirements: tuple[BlockingRequirement, ...] = ()
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_requirements(self) -> ClarificationPrompt:
        requirement_ids = [item.requirement_id for item in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("clarification prompt requirement IDs must be unique")
        return self


class ClarificationAnswerCommand(SessionContractModel):
    """Optimistically-concurrent user answer input for a clarification session."""

    session_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    prompt_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class AnswerTurn(SessionContractModel):
    turn_number: int = Field(ge=1)
    expected_revision: int = Field(ge=0)
    prompt_id: str = Field(min_length=1)
    message: MessageSpan


class AmendmentTarget(str, Enum):
    ORIGIN = "origin"
    DESTINATION = "destination"
    TRAVELERS = "travelers"
    DEPARTURE = "departure"
    RETURN_OR_DURATION = "return_or_duration"
    CONFLICTING_DATES = "conflicting_dates"


class TypedAmendmentBase(SessionContractModel):
    """Common grounding and scope controls for every answer-derived amendment."""

    amendment_id: str = Field(min_length=1)
    target: AmendmentTarget
    requirement_ids: tuple[str, ...] = ()
    span: MessageSpan
    is_correction: bool = False

    @model_validator(mode="after")
    def validate_scope(self) -> TypedAmendmentBase:
        if not self.requirement_ids and not self.is_correction:
            raise ValueError("amendments require a requirement link unless they are corrections")
        return self


class LocationAmendment(TypedAmendmentBase):
    target: Literal[AmendmentTarget.ORIGIN, AmendmentTarget.DESTINATION]
    locations: tuple[LocationRef, ...] = Field(min_length=1)


class TravelersAmendment(TypedAmendmentBase):
    target: Literal[AmendmentTarget.TRAVELERS]
    travelers: int = Field(ge=1)


class TemporalAmendment(TypedAmendmentBase):
    """Typed temporal input awaiting clarification-specific normalization.

    Step 4 supplies the normalizer that turns this grounded text into one or
    more ``TemporalContribution`` values.  The frozen initial compiler is not
    an input to this contract.
    """

    target: Literal[
        AmendmentTarget.DEPARTURE,
        AmendmentTarget.RETURN_OR_DURATION,
        AmendmentTarget.CONFLICTING_DATES,
    ]
    temporal_text: str = Field(min_length=1)


TypedAmendment = Annotated[
    LocationAmendment | TravelersAmendment | TemporalAmendment,
    Field(discriminator="target"),
]


class RejectedFragmentReason(str, Enum):
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"
    NOT_GROUNDED = "not_grounded"
    OUT_OF_SCOPE = "out_of_scope"
    UNSUPPORTED_REQUEST_REVISION = "unsupported_request_revision"


class RejectedFragment(SessionContractModel):
    span: MessageSpan
    reason: RejectedFragmentReason
    detail: str = Field(min_length=1)


class ResolutionOutcome(SessionContractModel):
    """Outcome records the accepted typed values, not merely their identifiers."""

    accepted_amendments: tuple[TypedAmendment, ...] = ()
    rejected_fragments: tuple[RejectedFragment, ...] = ()
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"accepted_amendments"})

    @model_validator(mode="after")
    def validate_unique_acceptances(self) -> ResolutionOutcome:
        accepted_ids = self.accepted_amendment_ids
        if len(accepted_ids) != len(set(accepted_ids)):
            raise ValueError("accepted amendment IDs must be unique")
        return self

    @property
    def accepted_amendment_ids(self) -> tuple[str, ...]:
        """Compatibility convenience derived from the retained typed records."""

        return tuple(item.amendment_id for item in self.accepted_amendments)


class ClarificationSessionRevision(SessionContractModel):
    """One immutable ledger entry after a deterministic session transition."""

    revision: int = Field(ge=0)
    effective_request: EffectiveRequest
    answer_turn: AnswerTurn | None = None
    outcome: ResolutionOutcome | None = None
    prompt: ClarificationPrompt | None = None
    status: ClarificationSessionStatus
    stop_reason: ClarificationStopReason | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"effective_request", "answer_turn", "outcome", "prompt"}
    )

    @model_validator(mode="after")
    def validate_transition_shape(self) -> ClarificationSessionRevision:
        if (self.answer_turn is None) != (self.outcome is None):
            raise ValueError("answer turns and resolution outcomes must be recorded together")
        if self.prompt is not None and self.prompt.revision != self.revision:
            raise ValueError("a revision prompt must carry the same revision number")
        if self.status is ClarificationSessionStatus.AWAITING_ANSWER:
            if self.prompt is None or self.stop_reason is not None:
                raise ValueError("awaiting-answer revisions require a prompt and no stop reason")
        elif self.status is ClarificationSessionStatus.READY:
            if self.prompt is not None or self.stop_reason is not None:
                raise ValueError("ready revisions cannot have a prompt or stop reason")
        elif self.prompt is not None or self.stop_reason is None:
            raise ValueError("stopped revisions require a stop reason and no prompt")
        if self.answer_turn is not None and self.outcome is not None:
            _validate_outcome_grounding(answer_turn=self.answer_turn, outcome=self.outcome)
        return self


def _validate_outcome_grounding(
    *,
    answer_turn: AnswerTurn,
    outcome: ResolutionOutcome,
) -> None:
    """Ensure this revision's accepted amendments belong to its answer message."""

    for amendment in outcome.accepted_amendments:
        if amendment.span.message_id != answer_turn.message.message_id:
            raise ValueError("accepted amendments must be grounded in the recorded answer message")


def _validate_effective_provenance(
    effective_request: EffectiveRequest,
    amendments_by_id: dict[str, TypedAmendment],
) -> None:
    """Link every answer-derived effective value to the ledger so far."""

    def validate_source(source: EffectiveValueSource, amendment_id: str | None) -> None:
        if isinstance(source, InitialSnapshotSource):
            return
        if amendment_id not in amendments_by_id:
            raise ValueError("answer-derived provenance must link to an accepted amendment")
        amendment = amendments_by_id[amendment_id]
        if source.span != amendment.span:
            raise ValueError("answer-derived provenance span must match its accepted amendment")

    for provenance in effective_request.field_provenance:
        validate_source(provenance.source, provenance.amendment_id)
    for contribution in effective_request.temporal_contributions:
        validate_source(contribution.source, contribution.amendment_id)


class ClarificationSession(SessionContractModel):
    """Authoritative additive state: initial snapshot plus append-only revisions."""

    session_id: str = Field(min_length=1)
    initial_result: RequestUnderstandingResult
    limits: ClarificationSessionLimits = Field(default_factory=ClarificationSessionLimits)
    revisions: tuple[ClarificationSessionRevision, ...] = Field(min_length=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"initial_result", "limits", "revisions"}
    )

    @model_validator(mode="after")
    def validate_revision_ledger(self) -> ClarificationSession:
        revision_numbers = [item.revision for item in self.revisions]
        expected = list(range(len(self.revisions)))
        if revision_numbers != expected:
            raise ValueError("session revisions must be contiguous and begin at zero")
        if self.revisions[0].answer_turn is not None:
            raise ValueError("initial session revision cannot contain an answer turn")
        # Local import avoids making the frozen initial workflow depend on the
        # continuation package at import time.
        from award_agent.clarification import project_initial_request
        from award_agent.clarification.blockers import collect_blocking_requirements

        expected_initial_projection = project_initial_request(self.initial_result.parsed_request)
        if self.revisions[0].effective_request != expected_initial_projection:
            raise ValueError(
                "initial session revision effective request must match the initial snapshot"
            )
        for revision in self.revisions:
            blockers = collect_blocking_requirements(revision.effective_request)
            if revision.status is ClarificationSessionStatus.AWAITING_ANSWER:
                assert revision.prompt is not None
                if revision.prompt.requirements != blockers:
                    raise ValueError("pending prompt requirements must exactly match active blockers")
            if revision.status is ClarificationSessionStatus.READY and blockers:
                raise ValueError("ready session revisions cannot retain blocking requirements")
        answer_message_ids: list[str] = []
        amendment_ids: list[str] = []
        amendments_by_id: dict[str, TypedAmendment] = {}
        _validate_effective_provenance(self.revisions[0].effective_request, amendments_by_id)
        for revision in self.revisions[1:]:
            previous = self.revisions[revision.revision - 1]
            if previous.status is not ClarificationSessionStatus.AWAITING_ANSWER:
                raise ValueError("only an awaiting-answer revision can accept a later answer")
            if revision.answer_turn is None or revision.outcome is None:
                raise ValueError("noninitial revisions require an answer turn and outcome")
            if revision.answer_turn.turn_number != revision.revision:
                raise ValueError("answer turn number must match its resulting revision")
            if revision.answer_turn.expected_revision != previous.revision:
                raise ValueError("answer turn expected revision must match the prior revision")
            if previous.prompt is None or revision.answer_turn.prompt_id != previous.prompt.prompt_id:
                raise ValueError("answer turn prompt ID must match the prior pending prompt")
            answer_message_ids.append(revision.answer_turn.message.message_id)
            for amendment in revision.outcome.accepted_amendments:
                amendments_by_id[amendment.amendment_id] = amendment
            amendment_ids.extend(revision.outcome.accepted_amendment_ids)
            _validate_effective_provenance(revision.effective_request, amendments_by_id)
        if len(answer_message_ids) != len(set(answer_message_ids)):
            raise ValueError("session answer message IDs must be unique")
        if len(amendment_ids) != len(set(amendment_ids)):
            raise ValueError("session accepted amendment IDs must be unique")
        return self

    @property
    def current_revision(self) -> ClarificationSessionRevision:
        return self.revisions[-1]

    @property
    def status(self) -> ClarificationSessionStatus:
        return self.current_revision.status

    @property
    def effective_request(self) -> EffectiveRequest:
        return self.current_revision.effective_request


__all__ = [
    "AmendmentTarget",
    "AnswerMessageSource",
    "AnswerTurn",
    "BlockingRequirement",
    "BlockingRequirementKind",
    "ClarificationAnswerCommand",
    "ClarificationPrompt",
    "ClarificationSession",
    "ClarificationSessionLimits",
    "ClarificationSessionRevision",
    "ClarificationSessionStatus",
    "ClarificationStopReason",
    "EffectiveField",
    "EffectiveRequest",
    "EffectiveValueSource",
    "FieldProvenance",
    "InitialSnapshotSource",
    "LocationAmendment",
    "MessageSpan",
    "RejectedFragment",
    "RejectedFragmentReason",
    "ResolutionOutcome",
    "TemporalAmendment",
    "TemporalContribution",
    "TemporalContributionKind",
    "TravelersAmendment",
    "TypedAmendment",
    "TypedAmendmentBase",
]
