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
    UNSUPPORTED_REQUEST_SCOPE = "unsupported_request_scope"


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


class TemporalTemplateProvenance(SessionContractModel):
    """Auditable origin for a continuation-only approved temporal template.

    The template registry is intentionally separate from the frozen initial
    intent compiler.  The answer span remains on ``source``; this record says
    precisely which versioned, date-free template was selected and which
    answer-local candidates it depended on.
    """

    template_id: str = Field(min_length=1)
    registry_version: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    dependency_candidate_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_dependencies(self) -> TemporalTemplateProvenance:
        if self.candidate_id in self.dependency_candidate_ids:
            raise ValueError("template provenance cannot depend on itself")
        if len(self.dependency_candidate_ids) != len(set(self.dependency_candidate_ids)):
            raise ValueError("template provenance dependency candidate IDs must be unique")
        return self


class AssumptionDisclosure(SessionContractModel):
    """A concise user-visible statement of an accepted approximation.

    This records disclosure, rather than authorizing an interpretation. The
    corresponding policy and symbolic interpretation remain explicit in
    ``TemporalAnswerInterpretationProvenance`` so a reducer cannot smuggle an
    arbitrary calendar value into an otherwise helpful clarification answer.
    """

    disclosure_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class TemporalAnswerInterpretationProvenance(SessionContractModel):
    """Policy-versioned provenance for a continuation-only interpretation.

    The initial intent temporal contracts deliberately do not use this model.
    ``candidate_ids`` identify the answer-local candidates that the approved
    policy used; their date evaluation is still a deterministic reducer task.
    """

    policy_version: str = Field(min_length=1)
    interpretation_id: str = Field(min_length=1)
    candidate_ids: tuple[str, ...] = Field(min_length=1)
    assumption_disclosure: AssumptionDisclosure | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"assumption_disclosure"})

    @model_validator(mode="after")
    def validate_candidate_ids(self) -> TemporalAnswerInterpretationProvenance:
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("temporal interpretation candidate IDs must be unique")
        return self


class TemporalContribution(SessionContractModel):
    """One active, source-keyed temporal fact used to rebuild effective timing."""

    contribution_id: str = Field(min_length=1)
    kind: TemporalContributionKind
    source: EffectiveValueSource
    # Frozen v1 DateWindow permits an empty raw_text, so the additive projection
    # must retain it rather than rejecting an otherwise valid initial snapshot.
    raw_text: str = ""
    amendment_id: str | None = Field(default=None, min_length=1)
    date_window: DateWindow
    template_provenance: TemporalTemplateProvenance | None = None
    interpretation_provenance: TemporalAnswerInterpretationProvenance | None = None
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "source",
            "date_window",
            "template_provenance",
            "interpretation_provenance",
        }
    )

    @model_validator(mode="after")
    def validate_value_shape(self) -> TemporalContribution:
        if isinstance(self.source, InitialSnapshotSource) and self.amendment_id is not None:
            raise ValueError("initial temporal contributions cannot name an amendment")
        if isinstance(self.source, AnswerMessageSource) and self.amendment_id is None:
            raise ValueError("answer temporal contributions require an amendment ID")
        if self.interpretation_provenance is not None and not isinstance(
            self.source, AnswerMessageSource
        ):
            raise ValueError("temporal interpretation provenance requires an answer-message source")
        if self.template_provenance is not None and self.interpretation_provenance is not None:
            raise ValueError(
                "temporal template and interpretation provenance are mutually exclusive"
            )
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
        disclosure_ids = [
            item.interpretation_provenance.assumption_disclosure.disclosure_id
            for item in self.temporal_contributions
            if item.interpretation_provenance is not None
            and item.interpretation_provenance.assumption_disclosure is not None
        ]
        if len(disclosure_ids) != len(set(disclosure_ids)):
            raise ValueError("effective request active assumption disclosure IDs must be unique")
        return self


class BlockingRequirementKind(str, Enum):
    CONFLICT = "conflict"
    ORIGIN = "origin"
    DESTINATION = "destination"
    DEPARTURE = "departure"
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
            BlockingRequirementKind.TRAVELERS: EffectiveField.TRAVELERS,
        }
        if self.field is not expected_fields[self.kind] or self.conflict_code is not None:
            raise ValueError("field requirements must use their matching effective field")
        return self


class ClarificationIssueKind(str, Enum):
    """The post-reduction reason an otherwise active blocker remains."""

    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    CONFLICT = "conflict"


class ClarificationIssue(SessionContractModel):
    """Authoritative, answer-local context for one active requirement.

    Requirement linkage is validated by ``ClarificationPrompt`` because only a
    prompt knows the active blocker set. ``reason_code`` is intentionally
    stable and machine-readable while ``reason`` is a safe human-facing
    explanation for a composer or deterministic fallback.
    """

    issue_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    kind: ClarificationIssueKind
    reason: str = Field(min_length=1)
    span: MessageSpan | None = None
    reason_code: str = Field(min_length=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"span"})


class PromptCompositionSource(str, Enum):
    """Whether customer-facing copy was accepted from the composer or fallback."""

    MODEL = "model"
    FALLBACK = "fallback"


class ScopeNotice(SessionContractModel):
    """A deterministic, user-visible disclosure about this one-way release."""

    code: Literal["one_way.return_or_duration"] = "one_way.return_or_duration"
    message: Literal[
        "This release supports one-way award searches. Please submit your return journey as a separate one-way request."
    ] = "This release supports one-way award searches. Please submit your return journey as a separate one-way request."
    span: MessageSpan
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"span"})


class ClarificationPrompt(SessionContractModel):
    prompt_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    requirements: tuple[BlockingRequirement, ...] = ()
    message: str = Field(min_length=1)
    issues: tuple[ClarificationIssue, ...] = ()
    composition_source: PromptCompositionSource = PromptCompositionSource.FALLBACK
    fallback_code: str | None = Field(default=None, min_length=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"issues"})

    @model_validator(mode="after")
    def validate_unique_requirements(self) -> ClarificationPrompt:
        requirement_ids = [item.requirement_id for item in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("clarification prompt requirement IDs must be unique")
        issue_ids = [item.issue_id for item in self.issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("clarification prompt issue IDs must be unique")
        issue_requirement_ids = [item.requirement_id for item in self.issues]
        if self.issues and set(issue_requirement_ids) != set(requirement_ids):
            raise ValueError("clarification prompt issues must exactly link active requirements")
        requirements_by_id = {item.requirement_id: item for item in self.requirements}
        for issue in self.issues:
            requirement = requirements_by_id[issue.requirement_id]
            if requirement.kind is BlockingRequirementKind.CONFLICT:
                if issue.kind is not ClarificationIssueKind.CONFLICT:
                    raise ValueError("conflict requirements require conflict clarification issues")
            elif issue.kind not in {
                ClarificationIssueKind.MISSING,
                ClarificationIssueKind.AMBIGUOUS,
                ClarificationIssueKind.UNSUPPORTED,
            }:
                raise ValueError("field requirements cannot use conflict clarification issues")
        if (
            self.composition_source is PromptCompositionSource.MODEL
            and self.fallback_code is not None
        ):
            raise ValueError("model-composed prompts cannot carry a fallback code")
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
    requirement_ids: tuple[str, ...] = ()
    reason_code: str | None = Field(default=None, min_length=1)
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset({"span"})

    @model_validator(mode="after")
    def validate_requirement_links(self) -> RejectedFragment:
        if len(self.requirement_ids) != len(set(self.requirement_ids)):
            raise ValueError("rejected fragment requirement IDs must be unique")
        return self


class ResolutionOutcome(SessionContractModel):
    """Outcome records the accepted typed values, not merely their identifiers."""

    accepted_amendments: tuple[TypedAmendment, ...] = ()
    rejected_fragments: tuple[RejectedFragment, ...] = ()
    scope_notices: tuple[ScopeNotice, ...] = ()
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {"accepted_amendments", "scope_notices"}
    )

    @model_validator(mode="after")
    def validate_unique_acceptances(self) -> ResolutionOutcome:
        accepted_ids = self.accepted_amendment_ids
        if len(accepted_ids) != len(set(accepted_ids)):
            raise ValueError("accepted amendment IDs must be unique")
        notice_spans = [
            (item.code, item.span.message_id, item.span.start, item.span.end)
            for item in self.scope_notices
        ]
        if len(notice_spans) != len(set(notice_spans)):
            raise ValueError("scope notices must be unique per answer span")
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
    terminal_message: str | None = Field(default=None, min_length=1)
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
            if (
                self.prompt is None
                or self.stop_reason is not None
                or self.terminal_message is not None
            ):
                raise ValueError("awaiting-answer revisions require a prompt and no stop reason")
            if not self.prompt.requirements:
                raise ValueError("awaiting-answer revisions require active blocking requirements")
        elif self.status is ClarificationSessionStatus.READY:
            if (
                self.prompt is not None
                or self.stop_reason is not None
                or self.terminal_message is not None
            ):
                raise ValueError("ready revisions cannot have a prompt or stop reason")
        elif self.prompt is not None or self.stop_reason is None:
            raise ValueError("stopped revisions require a stop reason and no prompt")
        elif (
            self.stop_reason is ClarificationStopReason.UNSUPPORTED_REQUEST_SCOPE
            and self.terminal_message is None
        ):
            raise ValueError("unsupported-scope stops require a user-visible terminal message")
        if self.answer_turn is not None and self.outcome is not None:
            _validate_outcome_grounding(answer_turn=self.answer_turn, outcome=self.outcome)
        if self.prompt is not None:
            if self.revision == 0:
                if any(issue.span is not None for issue in self.prompt.issues):
                    raise ValueError("initial prompt issues cannot cite answer spans")
            elif self.answer_turn is None:
                if any(issue.span is not None for issue in self.prompt.issues):
                    raise ValueError("prompt issue spans require the revision answer turn")
            else:
                for issue in self.prompt.issues:
                    if issue.span is not None:
                        _validate_answer_local_span(
                            span=issue.span,
                            answer_message=self.answer_turn.message,
                            label="prompt issue",
                        )
        return self


class PendingPromptTransition(SessionContractModel):
    """A validated, durable semantic transition awaiting presentation only.

    The receiver and reducer have already run.  Retrying this object may call
    only the prompt composer, never reinterpret the user's answer.
    """

    session_id: str = Field(min_length=1)
    base_revision: int = Field(ge=0)
    revision: int = Field(ge=1)
    answer_turn: AnswerTurn
    effective_request: EffectiveRequest
    outcome: ResolutionOutcome
    requirements: tuple[BlockingRequirement, ...] = Field(min_length=1)
    issues: tuple[ClarificationIssue, ...] = Field(min_length=1)
    composition_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    _copy_on_read_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "answer_turn",
            "effective_request",
            "outcome",
            "requirements",
            "issues",
        }
    )

    @model_validator(mode="after")
    def validate_shape(self) -> PendingPromptTransition:
        if self.revision != self.base_revision + 1:
            raise ValueError("pending prompt revision must immediately follow its base revision")
        if self.answer_turn.expected_revision != self.base_revision:
            raise ValueError("pending prompt answer turn must target the base revision")
        requirement_ids = tuple(item.requirement_id for item in self.requirements)
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("pending prompt requirements must be unique")
        if {item.requirement_id for item in self.issues} != set(requirement_ids):
            raise ValueError("pending prompt issues must cover its requirements")
        return self


def _validate_outcome_grounding(
    *,
    answer_turn: AnswerTurn,
    outcome: ResolutionOutcome,
) -> None:
    """Ensure this revision's accepted amendments belong to its answer message."""

    for amendment in outcome.accepted_amendments:
        _validate_answer_local_span(
            span=amendment.span,
            answer_message=answer_turn.message,
            label="accepted amendment",
        )
    for fragment in outcome.rejected_fragments:
        _validate_answer_local_span(
            span=fragment.span,
            answer_message=answer_turn.message,
            label="rejected fragment",
        )
    for notice in outcome.scope_notices:
        _validate_answer_local_span(
            span=notice.span,
            answer_message=answer_turn.message,
            label="scope notice",
        )


def _validate_answer_local_span(
    *,
    span: MessageSpan,
    answer_message: MessageSpan,
    label: str,
) -> None:
    """Require evidence to be an exact substring of its recorded answer."""

    if span.message_id != answer_message.message_id:
        raise ValueError(f"{label} must be grounded in the recorded answer message")
    if span.start < answer_message.start or span.end > answer_message.end:
        raise ValueError(f"{label} span must lie within the recorded answer message")
    relative_start = span.start - answer_message.start
    relative_end = span.end - answer_message.start
    if answer_message.text[relative_start:relative_end] != span.text:
        raise ValueError(f"{label} span text must exactly match the recorded answer message")


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
        if self.initial_result.parsed_request is None:
            raise ValueError(
                "a pending request-understanding outcome cannot initialize a clarification session"
            )
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
                    raise ValueError(
                        "pending prompt requirements must exactly match active blockers"
                    )
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
            if (
                previous.prompt is None
                or revision.answer_turn.prompt_id != previous.prompt.prompt_id
            ):
                raise ValueError("answer turn prompt ID must match the prior pending prompt")
            active_requirement_ids = {item.requirement_id for item in previous.prompt.requirements}
            for fragment in revision.outcome.rejected_fragments:
                if not set(fragment.requirement_ids).issubset(active_requirement_ids):
                    raise ValueError(
                        "rejected fragment requirement links must be active in the prior prompt"
                    )
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
    "AssumptionDisclosure",
    "BlockingRequirement",
    "BlockingRequirementKind",
    "ClarificationAnswerCommand",
    "ClarificationIssue",
    "ClarificationIssueKind",
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
    "PromptCompositionSource",
    "RejectedFragment",
    "RejectedFragmentReason",
    "ResolutionOutcome",
    "ScopeNotice",
    "TemporalAmendment",
    "TemporalAnswerInterpretationProvenance",
    "TemporalContribution",
    "TemporalContributionKind",
    "TravelersAmendment",
    "TypedAmendment",
    "TypedAmendmentBase",
]
