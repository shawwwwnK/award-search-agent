# 0011: Use iterative all-blockers clarification sessions

- Status: Accepted

## Context

The qualified request-understanding workflow returns a frozen initial `ParsedRequest` and a
legacy `ClarificationDecision`, but stops before accepting any answer. The initial decision asks
one prioritized field. It cannot represent evidence from later messages, safely merge an answer,
or continue when the answer resolves only some required constraints.

The project owner requires one clarification message to enumerate every current blocking
requirement. A user may answer any subset; after each answer, the workflow must recompute the
complete blocker set and either ask again, become ready for planning, or stop explicitly.

## Options

1. Concatenate each answer onto the original request and rerun the frozen initial parser.
2. Mutate the original `ParsedRequest` directly with answer-derived fields.
3. Add a versioned clarification-session boundary with immutable revisions, turn-level evidence,
   typed amendments, and deterministic state reduction.
4. Delegate the loop to LangChain or LangGraph.

## Decision

Choose option 3. The frozen initial API remains unchanged. The authoritative session state is the
frozen initial result plus an append-only answer/transition ledger. `EffectiveRequest` is the
deterministically materialized conversation-aware projection consumed by a later planner; it is
not a renamed or mutated initial `ParsedRequest`. New `ClarificationSession` state owns the
ledger, revision number, status, effective projection, and pending all-blockers prompt.

`collect_blocking_requirements()` deterministically gathers every active conflict and required
unknown (origin, destination, departure, return/duration, travelers). It does not treat every
`UnknownField` as blocking: cabin, search mode, repositioning, and other soft or unsupported
preferences remain nonblocking unless separately approved. A prompt has exact coverage of that
set and deterministic ordering: conflicts first, then the established required-field order. It is
one message, even when it lists several requirements.

One answer carries a session ID, expected revision, prompt ID, message ID, and raw text. A narrow
answer interpreter receives only the answer message identity/text and active typed requirements;
it does not receive the concrete reference date, timezone, effective request, or session ledger.
It may propose typed amendments linked to current requirement IDs and explicit, grounded
corrections to supported already-resolved fields (origin, destination, travelers, departure,
return/duration). The deterministic reducer independently validates amendments,
atomically applies valid independent subsets, records rejected/out-of-scope fragments, rebuilds
temporal state from active source-keyed contributions, and recomputes unknowns/conflicts and the
next complete blocker set. It never reruns initial parsing or silently changes unrelated
constraints.

The response may also carry a concise, customer-service-oriented `next_question` and the ordered
IDs of the requirements it believes remain. That prose is not policy: after deterministic
reduction, the controller uses it only when the IDs exactly equal the recomputed canonical blocker
set and no answer fragment was rejected. Otherwise it renders the deterministic friendly fallback.
The structured prompt requirements remain authoritative, no second model call is made, and the
model still receives no effective request, calendar context, or ledger.

The continuation owns a separate `MessageSpan` with message ID, offsets, and exact text; frozen
initial-message span contracts are not widened. A clarification-specific temporal normalizer
interprets answer spans under the original `RequestContext`: a bare duration is supported only
when return/duration is active, and a bare date is supported only when its endpoint is
unambiguous from the pending requirements or explicit answer cue. The continuation grammar also
supports `this weekend`, `this <weekday>`, and `on <weekday>`, resolving them deterministically
against that immutable context. A complete numbered answer line uses its one-based ordinal to
map to the correspondingly ordered typed prompt requirement; incidental numbers elsewhere in
prose do not establish endpoint ownership. Ambiguous multi-endpoint dates are re-asked. Cross-turn
anaphora is deferred. This leaves the frozen initial temporal scanner/compiler unchanged: in
particular, the frozen initial parser still does not recognize a bare `this weekend` in the raw
request. The relative-period support is continuation-only after a clarification session starts.

For bounded answer-only relative expressions outside that legacy normalizer, the answer model
selects from one global, date-free catalog of opaque operator affordances and grounds only
answer-local spans plus a weekday slot where required. The catalog is constant across sessions:
it receives no calendar dates, request state, fixture identifiers, candidates, or internal
template IDs. Deterministic continuation code validates complete classification and slot grounding,
maps each span to an ordered blocker or local endpoint cue, enforces the same-answer-only
departure dependency for `following`/`afterwards` weekdays, and performs all date arithmetic.
Unsupported relative spans remain explicit rejected provenance. This replaces answer-text regex
candidate harvesting; it does not add cross-turn anaphora or alter the frozen initial boundary.

When a model returns only a narrow temporal fact span, deterministic cue recovery is limited to
that same answer message and the fact's same physical sentence or answer line. It may use a nearby
departure or return cue only when the local segment contains one supported fact, or exactly two
supported facts joined by one explicit `and` or `then`, and the resulting endpoint must agree with
the typed amendment target. A disjunction or alternative (`or`/`either`), facts in separate
sentences or lines, multiple facts without one coordinator, a distant cue, or a swapped target is
ambiguous or invalid and is re-asked. Accepted recovery preserves the original narrow span as
provenance; it does not widen the source evidence or infer ownership from unrelated answer text.

Session status is `awaiting_answer`, `ready`, or `stopped`. A session becomes ready only with no
current blockers and no unresolved explicit attempted request revision. New hard constraints and
unsupported field changes remain explicit and stop the session with
`unsupported_request_revision`; a supported explicit correction is applied normally. It stops on
explicit decline/cancel or deterministic limits: initially six total answer turns or two
consecutive no-progress turns. Revisions use optimistic concurrency and message-ID idempotency;
system failures leave the prior revision unchanged. Exact message-ID replay is resolved before
revision freshness; reuse of an ID with different text is an explicit error.

Do not adopt LangChain or LangGraph in this stage. Explicit Python/Pydantic contracts and narrow
model protocols match the bounded, local state machine better and preserve deterministic ownership.
A framework may be reconsidered only for durable cross-process recovery, concurrent branches, or
multiple approval nodes.

For the initial live clarification-answer interpreter, use `gpt-5.6-luna`. The qualified
three-trial synthetic continuation evaluation met every initial live gate. `gpt-4o-mini` is not
the clarification-stage model: its matching evaluation produced incompatible blocker links that
the deterministic boundary correctly rejected. This is a model-selection decision for the narrow
interpreter adapter, not a change to deterministic validation or to the frozen initial workflow.

An optional Streamlit development dependency may provide a local validation harness. It owns only
ephemeral UI state and calls an application/controller API; it has no workflow logic, persistence,
authentication, deployment, provider calls, or automatic rerun-triggered model calls.

## Consequences

- The initial request-understanding implementation and ready corpus remain frozen and comparable.
- Later answer evidence has truthful turn identity and exact source spans.
- Users can resolve several blockers in one response without forcing a rigid question-by-question
  conversation.
- Explicit corrections to supported planning fields are accepted with provenance and complete
  recomputation. Arbitrary new constraints and unsupported field revisions remain deferred.
- Streamlit is permitted solely for local experimentation; production UI remains out of scope.
- LangChain/LangGraph dependency and orchestration complexity are avoided.

## Evaluation

Use a separate continuation corpus with complete trajectories and answer groupings. Offline gates
must be 100% for schema, prompt blocker coverage/order, grounding, temporal arithmetic, atomicity,
revision/idempotency, redaction, accepted-amendment correctness, final effective-request
correctness, and unintended-mutation checks.

For initial live qualification, run at least twelve complete trajectories across three trials
(at least 36 sessions). Require at least 95% correct terminal outcomes (at least 35 of 36), at
least 95% exact remaining-blocker sets after each processed answer, zero unauthorized field
mutations, and zero success-shaped system failures. Report convergence within the configured turn
budget, requirement-resolution precision/recall, prompt coverage, calls, latency, tokens, errors,
and stop reasons.

Every live-evaluation run captures all raw model calls in private, gitignored trace sidecars by
default. Public artifacts retain only redacted aggregate evidence and trace-run metadata. This is
required to make failures diagnosable without publishing user-answer payloads.

## Revisit trigger

Revisit the session shape or framework choice only if local state can no longer meet required
durable recovery, concurrent workflow, multi-approval, or observability needs, or if the
trajectory corpus identifies an inadequately representable answer pattern.
