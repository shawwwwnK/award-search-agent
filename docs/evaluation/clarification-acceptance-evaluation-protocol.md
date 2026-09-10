# Clarification acceptance evaluation protocol

This protocol qualifies the LLM-owned clarification boundary in ADRs 0014 and 0015. It is designed to
reward accepting, grounded conversational behavior without turning the implementation into a
fixture-matching exercise.

## Evaluation boundary

The answer receiver is evaluated for interpreting raw clarification language into grounded,
generic calendar proposals. It alone decides how language maps to a proposal. The deterministic
suite is evaluated for validating and executing the proposal, then reducing state; it must not
infer semantics from raw answer text. The composer is evaluated only for writing questions from
authoritative blockers and issue records. Composer copy cannot change safety or state.

For OpenAI only, a flat provider wire adapter sits before the receiver contract. It uses fixed
arrays by fact kind and flat anchor fields because the provider rejects `oneOf` schemas. Its
translation into the internal proposal model is structural: it validates typed fields and never
reads a quote or raw answer to recover meaning. The provider wire form is not an evaluation target;
v3 oracles must continue to judge only observable outcomes.

There are no language-understanding unit goldens. Unit and offline guardrail tests use fake,
already-typed receiver/composer outputs to test schema, evidence-span integrity, generic calendar
proposal evaluation, calendar arithmetic, conflict handling, reduction, provenance, revisions,
idempotency, and error behavior. They must not assert that a deterministic parser understands a
raw phrase, typo, or paraphrase. A raw answer may be retained for exact evidence-span integrity
checks, but deterministic code must not infer semantics from it.

## Corpus split and freeze

| Set | Visibility | Purpose | Handling |
| --- | --- | --- | --- |
| Disclosed development | Checked in and visible to implementers | Prompt/schema development, offline diagnostics, and known regressions | May be inspected and extended before freeze; never the sole release evidence |
| Locked external holdout | Stored and executed outside the implementation workspace by an independent evaluator | Unbiased qualification after the code and prompts are frozen | Agents receive only a version/hash and redacted aggregates; no raw answers, case IDs, or fixture paths |
| Rotating post-freeze challenge | Authored or sampled after the freeze by the evaluator, including adversarial and paraphrase variants | Detect leakage, prompt overfitting, and regressions against newly observed language | Remains hidden until scoring; any exposed case is promoted to a public regression and replaced |

Before holdout or challenge scoring, preregister the code/prompt/schema versions, model IDs,
adapter configuration, evaluator version, corpus hashes, trial count, metrics, and decision rules.
No implementation or prompt change may be made in response to a hidden case without a new freeze
and a new preregistration. Public reports contain hashes, family counts, aggregate metrics, and
failure counts only.

## V3 action/property oracle

Every behavioral fixture states an acceptable final behavior, not a prescribed internal AST or
question wording. A v3 oracle contains:

```yaml
expected_action: resolve | partial_resolve_and_ask | ask | stop | pending_retryable
must_resolve: [departure, return_or_duration]
must_remain_blocked: []
protected_fields: [origin, destination]
state_envelope:
  statuses: [ready]
  relations: [ready_iff_no_blockers]
properties:
  departure_window: {year: 2026, month: 10, start_day: [1, 10], end_day: [1, 10]}
  duration_days: [9, 11]
forbidden_outcomes:
  - unsafe_ambiguity_acceptance
  - protected_field_mutation
question_intent:
  required: false
  requirement_ids: []
  issue_kinds: []
disclosure: {required: true}
valid_siblings: [departure]
```

`state_envelope`, `properties`, and `values` describe observable permitted outcomes: statuses,
blocker/prompt relations, bounded date or duration envelopes, and exact values only where the
product actually requires them. `question_intent` checks requirement and issue linkage, not
generated wording. `disclosure` checks generic approximation provenance/disclosure only when an
approximation was accepted. The oracle has no field for receiver ASTs, proposal handles, or
customer-facing copy. A fixture may permit several safe outcomes only when they are all explicitly
declared.

The checked-in v3 file is a **pilot corpus** and validates the action/property-oracle machinery.
It is not a behavioral qualification corpus. Its actions are `resolve`,
`partial_resolve_and_ask`, `ask`, `stop`, and `pending_retryable`; the latter means a visibly
communicated, non-mutating retryable receiver/composer outcome, not an ordinary ask or user
no-progress answer.

## Gates

### Safety and offline guardrails

This is a hard 100% gate and runs without live model or provider access. It covers:

- typed generic-proposal validation and deterministic calendar evaluation;
- exact answer-message identity and evidence-span bounds/integrity;
- acyclic same-answer dependency topology, opaque fact-reference integrity, and graph-order
  calculation without any raw-text ordering or phrase inference;
- authorized requirement/correction targets and no unrelated hard-constraint mutation;
- deterministic temporal compilation, calendar arithmetic, bounded/nonempty windows, and conflict
  preservation;
- atomic independent-subset reduction, immutable revisions, provenance, concurrency, replay and
  idempotency behavior;
- exact blocker coverage/order, ready-state policy, explicit unsupported and pending/retryable
  outcomes, and
  privacy/redaction;
- composer question-set schema, complete ordered blocker coverage, and issue linkage.

An invalid receiver result gets at most one model-owned repair attempt across wire/schema,
grounding, semantic, and calculation validation. A residual invalid proposal must be explicit,
non-success-shaped, non-mutating, visibly retryable/pending, and retain valid independent
siblings; it must not leak as a raw exception or consume a user no-progress turn. There is no
deterministic semantic recovery and no robotic question fallback. Instrumentation or review must
also verify that continuation deterministic code never calls a raw-answer parser or applies
phrase-specific typo/endpoint/numbered-line rules.

Provider rejection of the submitted structured-output schema is different: it is an
adapter/preflight pending outcome before model inference. It receives no semantic repair attempt
with the identical schema, does not consume user no-progress, and cannot be counted as an
interpreter understanding, behavioral, or model-quality failure. The hard gate requires a
provider-schema smoke that reaches inference before a live behavioral matrix is eligible to run.

### Behavioral and semantic-diagnostic acceptance

Run the receiver and composer over all three corpus classes using the v3 action/property oracles,
not literal answer strings. Include typo and casing variants, natural date and duration language,
multiple independent facts, grounded corrections, alternatives, conflicts, cancellations,
non-answers, unsupported revisions, and prompt-injection-like text.

Report the following distinct dimensions by semantic family and corpus split; do not collapse them
into terminal correctness:

- **Semantic diagnosis:** receiver understood the answer, correctly identified a genuine
  ambiguity/conflict, or correctly identified unsupported intent. This is expert/human-reviewed
  diagnostic evidence and does not by itself pass the workflow.
- **Behavioral task outcome:** action/property-oracle success, false-block rate, incorrect
  acceptance, valid-sibling retention, assumption disclosure, conflict preservation, turns to
  ready, and convergence.
- **Safety:** unauthorized mutation, ungrounded fact, fabricated assumption, success-shaped
  failure, protected-field change, and raw exception exposure. These are zero-tolerance failures.
- **Operational quality:** first-pass proposal validity, one-repair success/failure rate, pending
  rate, model calls, repair-attributed latency/tokens/cost, targeted-question rate,
  generic-repeat rate, and composer invalid-output rate.

Every artifact includes internal proposal-contract version, provider wire-adapter version,
canonical generated-schema hash, and provider stage counts (preflight rejected, inference reached,
structured result returned). This makes adapter defects auditable without exposing private answer
payloads or treating a pre-inference rejection as a model response.

Fuzzy windows are scored against an approved bounded envelope; question quality is scored for
clarity, specificity, non-leading wording, and naturalness. Human review is authoritative for
materially surprising assumptions and naturalness. An LLM judge may scale calibrated semantic or
copy review but never override a deterministic safety finding.

Every rate records an explicit numerator and denominator. A zero-denominator metric is reported
as **not applicable**, never `0%` or `100%`; it cannot support a pass claim. Qualification
requires an owner-approved nonzero eligible population for each metric used as a gate—for example,
reasonable answers for false-blocking, real alternatives/conflicts for incorrect acceptance,
accepted approximations for disclosure, repair-eligible failures for repair success, and questions
for targeted/generic-repeat rates. The report must show fixture-family coverage and mark a pilot
as diagnostic when it cannot exercise those denominators.

### Live qualification

Run the frozen adapters through the locked holdout and rotating challenge after the offline gate
passes. Capture private, gitignored traces for every receiver and composer call; public artifacts
must be redacted aggregates. A live failure can never yield `ready`: model errors, invalid output,
grounding failures, and composition failures remain explicit and are counted. A receiver contract
failure is first offered one shared repair; a residual failure is recorded as `pending_retryable`,
with visible retry communication, rather than as a user-visible raw exception or an ordinary
no-progress answer.

The live safety gate is zero unauthorized mutations, raw exception exposures, and success-shaped
system/model failures, with exact blocker and prompt coverage for every successfully processed
turn. Terminal outcomes and behavioral quality use preregistered thresholds and confidence
intervals; if a threshold has not yet been owner-approved, report it diagnostically rather than
silently promoting it to a release gate. A passing development run is never sufficient for
qualification.

## Anti-overfit procedure

Development fixtures may be used to improve prompts, schemas, and proposal execution. They are
not qualification evidence on their own. Before a live qualification run, freeze and record the
receiver/composer prompts, model IDs, schema/proposal version, repair policy, evaluator version,
corpus hashes, action/property oracle version, trial count, and scoring rules. Keep the locked
holdout out of the workspace; report only hashes, family aggregates, and redacted failure counts.

The independent evaluator also generates rotating post-freeze metamorphic challenges: typo,
punctuation, ordering, wording, and equivalent-reference variants, plus paired accept/ask boundary
cases. When a hidden case becomes visible during debugging, promote it to disclosed regression
coverage and replace it in the holdout/challenge pool. Do not tune against a hidden result without
a new freeze and preregistration. The evaluator must retain first-pass, repair, and pending traces
privately so a score cannot hide representation failures behind an aggregate pass rate.

## Superseded v3 preflight diagnostic

The one-trial v3 development diagnostic recorded at
`evals/clarification/baseline/2026-09-10-gpt-5.6-luna-v3-development-diagnostic-1-trial-f582925.json`
had all eight scenarios rejected by the provider's prior `oneOf` schema before inference. Its
automatic pending/retry attempts repeated the same rejected schema and therefore add no semantic
or behavioral evidence. Retain it only as adapter-failure and trace-capture evidence; do not use
its false blocks, pending counts, latency, or terminal outcomes in a receiver baseline or model
comparison. The flat OpenAI wire-adapter schema supersedes that diagnostic for future live runs.

## Preregistered composer experiment: Luna versus GPT-4o-mini

### Hypothesis and arms

The composer can use `gpt-4o-mini` instead of `gpt-5.6-luna` if it is materially faster or cheaper
without materially worse valid coverage, issue-specificity, or naturalness. The receiver remains
on `gpt-5.6-luna`; this is a composer-only experiment.

Before seeing results, freeze the model IDs, system/user prompts, output schema, adapter settings,
retry policy, temperature/sampling settings, trace policy, evaluator version, and the exact issue
bundles to be scored. Use identical authoritative issue inputs for both arms, randomize arm order,
and run at least three independent trials per bundle. The scored population must be fixed before
the run, balanced across missing, ambiguous, unsupported, and conflict issues, and include the
locked holdout and post-freeze challenge through the independent evaluator. Do not select cases,
retries, or examples after observing an arm's output.

### Metrics and decision rule

Measure, per arm and paired by issue bundle:

- valid structured-output rate and complete ordered blocker coverage;
- issue linkage correctness and invalid-output/error rate;
- human-calibrated clarity, specificity, non-leading quality, and naturalness;
- generic-repeat rate;
- p50/p95 end-to-end composer latency, model calls, tokens, and cost.

Any state mutation or safety violation is disqualifying; the composer has no state authority, so an
invalid output must remain an explicit retryable composition error. Select GPT-4o-mini only if all
of the following are true under the preregistered paired analysis:

1. It has zero safety violations and no worse than a five-percentage-point loss in valid complete
   coverage or issue linkage versus Luna.
2. Its human quality score is no more than 0.2 points lower on the calibrated five-point scale,
   with the confidence interval reported.
3. It improves p95 latency or token cost by at least 20% with the same input population.

If any condition fails, retain Luna as the composer and record the failed dimension. If the result
is inconclusive, make no model switch; repeat only after an owner-approved new preregistration.
The decision report must include model/prompt/schema hashes, split hashes, sample counts, trial
counts, paired confidence intervals, raw call/error/latency/token aggregates, and the final switch
or no-switch decision.
