# 0016: One-way award request boundary

- Status: Accepted
- Date: 2026-09-11

## 2026-09-21 successor decision

[ADR 0022](0022-award-first-cash-observations.md) approves downstream direct-cash benchmarks and
bounded cash positioning in the next provider/result stage. It consumes M2C's existing endpoint
probes and positioning dependencies rather than reopening search-strategy compilation. Cash-only
user requests remain unsupported, and this ADR continues to govern active runtime behavior until
the successor decision is implemented and accepted.

## Context

The prior live request boundary required origin, destination, departure, return-or-duration, and
travelers before a request could become ready. That makes every search round-trip shaped even
though the next provider and search-planning work will first need a simpler outbound award-search
vertical slice. Cash-fare execution is separately constrained by limited provider access.

The project owner has paused search-plan design to recut the upstream workflow instead of carrying
round-trip and cash semantics as inactive fields. The initial parser and clarification session must
remain traceable and safe while this product scope narrows.

## Options

1. Retain round-trip and cash semantics in the live contracts, but ignore them in search planning.
2. Add a runtime choice between the current round-trip workflow and a one-way workflow.
3. Replace the live workflow with a one-way award-only boundary, retaining prior contracts and
   artifacts as historical evidence.

Choose option 3.

## Decision

### Active ready contract

The active ready contract requires only:

- origin;
- destination;
- a bounded outbound departure window; and
- traveler count.

Cabin and repositioning remain nonblocking. The active semantic target and effective state contain
outbound timing only: no return window, duration, return temporal contribution, or
`return_or_duration` blocker exists in the live path.

### Return and duration information

Return-date and trip-duration information are unsupported at both initial request understanding
and clarification-answer interpretation. Structured semantic detection must retain exact evidence
and return a visible, stable response directing the user to submit the return leg as a separate
one-way request. It must not compile a return value, mutate active session state, create a
clarification blocker, or silently accept only an outbound subset.

The model remains the raw-language reader. Deterministic code may classify the model/selector's
typed return or duration target and apply the fixed product response, but may not add phrase-based
raw-text detection or repair.

### Award and cash requests

Award is the sole executable search mode in this cut. A cash-only request is explicitly invalid.
A request that includes award and cash remains eligible for its award portion; no current result
may claim cash prices or cash-search coverage. Later stages decide how to present or compare the
unavailable cash portion.

### Migration and evidence

There is no runtime mode switch. The live request-understanding and continuation contracts are
replaced and versioned for this boundary. Existing round-trip/cash implementation, artifacts, and
scores remain historical evidence and must not be rewritten as qualification of the one-way path.

## Consequences

- The initial workflow, continuation controller, contracts, prompts, model schemas, tests, and
  corpora need coordinated changes.
- The generic clarification calendar proposal contract no longer needs active return/duration
  operations, while its no-raw-text-parsing, grounding, repair, provenance, and immutable-state
  invariants remain in force.
- The paused search-plan stage will consume an outbound-only `EffectiveRequest` when reopened.
- A request that asks for cash alone or return travel receives an explicit limitation rather than a
  misleading ready result.

## Evaluation

Offline evaluation must cover:

- ready one-way award requests with exact, range, month, holiday, and supported relative outbound
  timing;
- missing origin, destination, departure, and travelers;
- return dates and durations in initial requests and clarification answers, including evidence and
  non-mutation checks;
- cash-only invalid outcomes and mixed award-and-cash award eligibility;
- removal of the return/duration blocker and preservation of all outbound invariants.

Run a bounded live evaluation after offline checks. Record traces under the existing private-trace
discipline and report mechanical/schema/provider errors separately from behavioral outcomes.

## Revisit trigger

Revisit when a provider-execution stage needs round-trip pairing, when cash-search access becomes
adequate, or when one-way scope creates a recurring user-harmful limitation.
