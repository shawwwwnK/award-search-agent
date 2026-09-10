# 0015: Use generic model-authored calendar proposals for clarification answers

- Status: Accepted
- Date: 2026-09-10

## Context

ADR 0014 correctly moved raw-answer understanding to the clarification receiver, but its closed
temporal mini-language still made the receiver's surface representation an accidental availability
boundary. A reasonable answer such as “10 days”, “Wednesday afterwards”, or a minor spelling
variation could be understood by the model yet fail conversion because its symbolic token was not
one of the exact schema spellings. Adding a deterministic branch for each new wording or named
relation would recreate the phrase grammar that ADR 0014 retired.

The live evaluation exposed this distinction. A conversion failure is not evidence that the user
was unclear, and should not appear to the user as a `ValidationError`. Conversely, a model's
plausible interpretation is not automatically safe to apply: calendar arithmetic, boundedness,
authority, provenance, ambiguity preservation, and immutable state reduction remain system
invariants.

## Options

1. Extend the deterministic answer grammar and temporal AST for each newly observed phrase.
2. Accept model-calculated dates or arbitrary request patches without deterministic validation.
3. Have the model express a generic, typed calendar calculation proposal; deterministically
   validate and execute that proposal without inspecting answer language, with one model-owned
   repair opportunity for an invalid proposal.

Choose option 3.

## Decision

### The receiver authors generic calendar calculations, not phrase rules

The receiver remains the only raw-answer semantic reader. For each grounded temporal fact it
authors a target, answer-local evidence span, and one generic calculation proposal. The proposal
may express a literal calendar interval, a recurring interval, an offset interval, or a bounded
duration. It can refer only to the immutable request context or another same-answer fact by
opaque fact ID. Same-answer references form an acyclic dependency graph: facts may be supplied in
any order, but a missing reference or cycle is invalid. It does not expose a catalogue of English
constructions, template identities, or model-calculated resolved dates.

These are calculation forms, not linguistic meanings. The receiver decides how “the following
Wednesday”, “Wednesday afterwards”, a typo, or a paraphrase maps to one of them. Deterministic
code must not recognize, rewrite, normalize, or add special handling for any of those phrases.
Adding a phrase-named relation is not an acceptable future fix.

The calculation proposal is deliberately bounded and typed enough to let deterministic code:

- verify evidence identity and the acyclic fact/dependency graph;
- resolve symbolic components under the immutable request context and typed receipts in graph order;
- perform calendar arithmetic and reject impossible, empty, or unbounded outcomes;
- apply authorization, conflict policy, immutable reduction, provenance, and blocker recomputation.

The model does not set a concrete resolved calendar date authoritatively, select a requirement
link, override protected state, or choose the final amendment authority. Those remain state-policy
and invariant decisions. This is an invariant boundary, not a second language parser.

### One bounded, model-owned repair; no user-visible contract exception

If a receiver result fails wire/schema conversion, grounding, semantic validation, or calendar
compilation, the system may make exactly one repair call. This is one shared repair budget per
answer turn, not one attempt per fact or validation stage. That call receives the original
permitted receiver input, the rejected result, and structured validation errors. The receiver—not
deterministic code—must canonicalize or reconsider the proposal. The repair cannot add a new
raw-text parser, change the original message, or widen receiver authority.

If repair succeeds, the trace records that the accepted proposal required repair and reduction
continues normally. If it fails, the answer is retained with its evidence and rejection details in
a non-mutating, retryable **pending interpretation** outcome. The session must not throw a raw
model/schema exception, become `ready`, silently invent a replacement interpretation, or discard
valid independent siblings.

A pending interpretation is operationally distinct from a user no-progress answer. It does not
increment the consecutive no-progress counter merely because the model contract failed. A retry
of the same message is idempotent and bounded by the same one-repair limit; an ordinary subsequent
user answer proceeds from the unchanged effective request. The pending result must be visibly
communicated as a retryable clarification state with the unchanged prompt/context; it is never a
leaked `ValidationError`, a silent dead end, or a fabricated normal answer. Presentation may be
composed, but it cannot change the authoritative pending state outcome.

### Approximation is generic provenance, not phrase-specific policy

When the receiver intentionally supplies a bounded approximation, the materialized contribution
retains generic interpretation metadata: the grounded fact, calculation operation, resolved
envelope, and whether an assumption/disclosure is required. The visible disclosure describes the
chosen bounded interpretation without relying on a hand-written rule for the source phrase.
Exact proposals do not acquire a fictional assumption merely to satisfy instrumentation. The
evaluator tests the presence and applicability of this generic metadata, not a specific disclosure
sentence.

### Evaluation judges outcomes, not internal spellings

A correct semantic diagnosis and a successful workflow transition are related but separate
measurements. A model output that clearly understands “10 days” but cannot yet be represented is
a semantic diagnostic success and an end-to-end task failure; it must not be counted as a pass
until repair or implementation can safely apply it. A genuine alternative or endpoint ambiguity is
successful only when the workflow preserves it and asks the specific needed question.

The acceptance protocol now uses action/property oracles and records first-pass, repaired, and
pending outcomes separately. Exact AST identity, canonical token spelling, or customer-service
wording are not behavioral pass criteria.

## Supersession

This ADR supersedes ADR 0014 only for clarification-answer temporal representation and residual
receiver-contract failure handling. ADR 0014 remains authoritative for the receiver/composer
separation, evidence boundary, deterministic state policy, post-reduction composition, and the
frozen initial request-understanding boundary. It does not revive ADR 0011's deterministic
clarification grammar, endpoint cues, positional numbered-line parsing, or raw-text recovery.

ADR 0012's property-oriented behavioral intent remains in force, as refined by the v3 acceptance
protocol. Historical v1/v2 results remain evidence of their then-current implementations and are
not evidence that the ADR 0015 runtime is qualified.

## Consequences

- New natural language should normally require receiver prompt/schema improvement, not a
  deterministic phrase branch.
- Typed proposal validation still has a strict role, but failures are diagnosed as representation
  or system outcomes rather than blamed on a reasonable user answer.
- The receiver may need a repair call, increasing worst-case latency and cost; reports must make
  repair rate and repair latency visible rather than hiding them in aggregate success.
- The evaluator can distinguish unsafe acceptance, correct ambiguity handling, semantic
  understanding, representation gaps, and genuine user non-progress.

## Evaluation

Use [the clarification acceptance evaluation protocol](../evaluation/clarification-acceptance-evaluation-protocol.md).
The hard offline gate remains 100% for safety invariants and includes proof that no continuation
code semantically parses raw answer text. Live qualification uses disclosed cases, a locked
external holdout, and rotating post-freeze challenges. It reports outcome/action correctness and
properties by family, with repair attribution, rather than one terminal-exactness score.

## Revisit trigger

Revisit this decision if generic calculation proposals cannot truthfully express important,
repeated clarification outcomes; if repair latency/rate makes the flow unacceptable; if pending
outcomes recur for ordinary language; or if independent holdout review finds that the outcome
oracles accept unsafe or materially surprising behavior.
