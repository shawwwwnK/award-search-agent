# Handoff: iterative clarification-continuation implementation plan

## Start here

The active milestone is the additive clarification-session boundary approved in
[ADR 0011](../adr/0011-iterative-clarification-sessions.md). This handoff is the executable plan
for implementation steps 1–6. Read it with:

- [`AGENTS.md`](../../AGENTS.md) for active scope and non-goals.
- [`docs/project-state.md`](../project-state.md) for current phase and frozen boundaries.
- [`docs/architecture.md`](../architecture.md) for ownership and state diagrams.
- [`ADR 0011`](../adr/0011-iterative-clarification-sessions.md) for accepted architecture.

The initial request-understanding boundary remains frozen:

`RawRequest -> ParsedRequest -> ClarificationDecision`

Do not change `ParsedRequest`, `RequestUnderstandingResult`, `understand_request()`, the selector,
the temporal scanner/compiler, clarification policy, or the ready corpus. The new session boundary
is additive. Do not add LangChain or LangGraph.

## User-visible behavior

The first frozen result remains an initial snapshot. If it needs clarification, the continuation
session asks **one message listing every current blocking requirement**. A user may answer any
subset. After each answer, the workflow applies valid amendments, recomputes the complete blocker
set, and either asks an updated all-blockers message, becomes `ready`, or becomes `stopped`.

An explicit, grounded correction to a supported already-resolved field is valid. For example,
when travelers are missing, “Two travelers, and actually make the departure October 6” must update
both travelers and departure, then recompute the effective temporal state. New unsupported
constraints or unsupported field revisions must remain explicit and cannot yield a misleading
`ready` result.

`ready` means ready for later planning, not directly ready to query Seats.aero; location-to-airport
resolution remains a later planning responsibility.

## Core invariants

- The authoritative state is the frozen initial result plus an append-only answer/transition ledger.
  `EffectiveRequest` is a deterministic projection, not separately mutable truth.
- Every prompt has exact coverage of a closed blocker policy: active conflicts plus required
  origin, destination, departure, return/duration, and traveler unknowns. Cabin, search-mode,
  repositioning, and other soft/unsupported unknowns are nonblocking.
- Every accepted value has exact answer-turn provenance. Use a new answer-only `MessageSpan`; do
  not widen frozen initial-message evidence types.
- One answer may contain independent typed amendments. User-level invalid fragments may be
  rejected while valid independent amendments commit in one revision. Infrastructure, model,
  grounding, compiler, or reducer failures abort the entire transition without a new revision.
- Initial context, especially reference date and timezone, remains authoritative across all turns.
- System failures are explicit and never success-shaped. Terminal states reject new answers.
- Exact message-ID replay returns its recorded transition before freshness checks. Reusing a
  message ID with different text is an error. A stale revision or wrong prompt ID fails before a
  model call.
- No provider, search-planning, persistence, authentication, deployment, or production UI work is
  part of steps 1–6.

## Step 1 — session contracts and projection foundation

Add Pydantic contracts for `ClarificationSession`, `EffectiveRequest`, revisions, session status,
limits, stop reasons, `ClarificationPrompt`, `BlockingRequirement`, answer commands, answer turns,
message spans, resolution outcomes, rejected fragments, and typed-amendment base shapes.

Implement pure projection/revision scaffolding. Existing v1 contracts and APIs must remain intact.

**Tests:** contract validation, prior-session non-mutation, revision basics, initial-contract
isolation.

**Exit:** no continuation code changes the initial request-understanding result.

## Step 2 — blocker collection and prompt rendering

Implement deterministic `collect_blocking_requirements(effective_request)` from the closed blocker
policy. Use stable semantic IDs without user text. Render exactly one template-based prompt with
conflicts first, then origin, destination, departure, return/duration, and travelers.

**Tests:** exact blocker coverage, stable order, duplicate suppression, ready-with-no-blockers,
and exclusion of nonblocking unknowns.

**Exit:** `prompt.requirements` exactly matches the active blocker set.

## Step 3 — answer interpreter and typed amendments

Add a narrow `ClarificationAnswerInterpreter` protocol. It can propose grounded typed amendments
for origin, destination, travelers, departure, return/duration, conflicting dates, and explicit
corrections to supported resolved fields. It must never produce generic dictionary patches.

The model-facing input is limited to the answer message ID/text and current typed blocker
requirements. The original `RequestContext`, effective request, ledger, limits, and all concrete
calendar values remain deterministic-only.
An answer may resolve multiple requirements. Record rejected fragments explicitly.

**Tests:** fake-interpreter multi-field and subset answers, mixed valid/invalid fragments, explicit
corrections, and no unrelated mutation.

**Exit:** every amendment is field-typed, requirement-linked or a supported correction, and
grounded to an answer span.

## Step 4 — clarification-specific temporal normalization

Do not reuse isolated answer text through the frozen initial temporal scanner/compiler. Add a
clarification-specific temporal normalizer under the original `RequestContext`:

- Accept bare duration such as `10 days` only while return/duration is active.
- Accept a bare date only when endpoint ownership is unambiguous from active requirements or an
  explicit cue.
- Accept explicit correction cues such as “make departure October 6”.
- Re-ask ambiguous multi-endpoint answers.

Rebuild effective temporal state from active source-keyed contributions. Defer cross-turn anaphora,
such as “same dates, one week later.”

**Tests:** durations, endpoint ownership, corrections, conflict recomputation, original-context
preservation, and explicit model/grounding/compiler/holiday failures.

**Exit:** every accepted temporal fact is turn-grounded and deterministically evaluated without
changing the frozen scanner/compiler.

## Step 5 — controller and atomic transitions

Implement public operations equivalent to `start_clarification()` and
`apply_clarification_answer()`. A transition validates replay/freshness, interprets and validates
amendments, applies valid independent amendments atomically, recomputes the projection and blocker
set, then returns `awaiting_answer`, `ready`, or `stopped`.

Use six total answer turns and two consecutive no-progress turns. A no-progress fingerprint is the
effective-state fingerprint plus blocker IDs. Processed user answers create revisions; system
failures do not. A supported correction updates its field; a new unsupported constraint or
unsupported revision produces `stopped(unsupported_request_revision)`.

**Tests:** replay/idempotency, stale revision, wrong prompt, terminal states, partial application,
correction, no-progress, stop precedence, and no false `ready` after an attempted unsupported
revision.

**Exit:** transitions are atomic, traceable, and cannot falsely claim readiness.

## Step 6 — offline continuation corpus and evaluator

Create a separate continuation corpus. Do not modify the frozen initial ready corpus. Include full
trajectories for all-at-once/subset answers, date conflicts, temporal answers, corrections,
ambiguous/no-progress paths, cancellation, unsupported revisions, stale/replayed commands,
failures, privacy/redaction, and equivalent answers grouped across different turns.

Report exact blocker coverage/order, accepted-amendment correctness, final `EffectiveRequest`,
remaining blockers, terminal outcome, convergence, turns to ready, requirement precision/recall,
unintended mutations, calls, latency, tokens, errors, and stop reasons.

**Offline gate:** 100% for schema, blocker coverage/order, grounding, temporal arithmetic,
atomicity, idempotency, redaction, accepted-amendment correctness, final effective-request
correctness, and no unauthorized mutation.

**Future live gate:** at least 12 trajectories across 3 trials (36 sessions), at least 35 correct
terminal outcomes, at least 95% exact remaining-blocker sets after processed answers, zero
unauthorized mutations, and zero success-shaped system failures.

**Live trace requirement:** every live evaluator invocation must capture **all** model calls by
default. Write exact model-facing input, instructions, structured-output schema, response, and
failure data only to a run-specific private sidecar directory under a gitignored `traces/` path.
The checked-in/redacted evaluation artifact may identify that directory and report its case count,
but must never embed raw prompts, answer text, model payloads, responses, credentials, or other
private trace content. Do not add a default-off trace mode; an exceptional trace opt-out requires
an explicit future project-owner decision.

## Deferred after step 6

Only after offline implementation is stable: add the local, ephemeral Streamlit validation harness,
then run live continuation qualification. The fixed Seats.aero planner follows only after a
qualified `ClarificationSession(ready).effective_request` is available.

## Relevant current code

- [`domain models`](../../src/award_agent/domain/models.py) — frozen v1 contracts.
- [`initial workflow`](../../src/award_agent/intent/workflow.py) — initial snapshot assembly.
- [`clarification policy`](../../src/award_agent/intent/clarification.py) — legacy prioritized
  decision and required-field policy.
- [`temporal scanner`](../../src/award_agent/intent/temporal_lexing.py) and
  [`temporal compiler`](../../src/award_agent/intent/temporal_compiler.py) — frozen initial path;
  do not alter for isolated answers.
- [`intent tests`](../../tests/unit/) and [`intent corpus`](../../evals/intent/cases.yaml) — frozen
  initial evidence; continuation gets new tests and a separate corpus.

## Baseline and verification

Before continuation work began, `.venv/bin/pytest -q` passed with **263 tests**. Use the project
commands after each behavior change:

```sh
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy src tests
git diff --check
```

Record meaningful implementation and evaluation evidence in `docs/build-log/` without exposing
raw travel text, model payloads, or credentials.
