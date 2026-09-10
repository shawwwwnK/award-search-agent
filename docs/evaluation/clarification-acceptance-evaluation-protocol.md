# Clarification acceptance evaluation protocol

This protocol qualifies the LLM-owned clarification boundary in ADR 0014. It is designed to
reward accepting, grounded conversational behavior without turning the implementation into a
fixture-matching exercise.

## Evaluation boundary

The answer receiver is evaluated for interpreting raw clarification language into the typed
semantic contract. The deterministic suite is evaluated for validating that contract and reducing
state. The composer is evaluated only for writing questions from authoritative blockers and issue
records. Composer copy cannot change safety or state.

There are no language-understanding unit goldens. Unit and offline guardrail tests use fake,
already-typed receiver/composer outputs to test schema, evidence-span integrity, symbolic temporal
compilation, calendar arithmetic, conflict handling, reduction, provenance, revisions,
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

## Gates

### Safety and offline guardrails

This is a hard 100% gate and runs without live model or provider access. It covers:

- typed contract and closed-semantic validation;
- exact answer-message identity and evidence-span bounds/integrity;
- authorized requirement/correction targets and no unrelated hard-constraint mutation;
- deterministic temporal compilation, calendar arithmetic, bounded/nonempty windows, and conflict
  preservation;
- atomic independent-subset reduction, immutable revisions, provenance, concurrency, replay and
  idempotency behavior;
- exact blocker coverage/order, ready-state policy, explicit unsupported/error outcomes, and
  privacy/redaction;
- composer question-set schema, complete ordered blocker coverage, and issue linkage.

An invalid receiver or composer output must be explicit and non-success-shaped. There is no
deterministic semantic recovery and no robotic question fallback. Instrumentation or review must
also verify that continuation deterministic code never calls a raw-answer parser or applies
phrase-specific typo/endpoint/numbered-line rules.

### Behavioral acceptance

Run the receiver and composer over all three corpus classes using property/action oracles, not
literal answer strings. Include typo and casing variants, natural date and duration language,
multiple independent facts, grounded corrections, alternatives, conflicts, cancellations,
non-answers, unsupported revisions, and prompt-injection-like text.

Report at least false blocking, incorrect acceptance, valid-sibling retention, assumption
disclosure, conflict preservation, turns to ready, convergence within limits, targeted-question
rate, generic-repeat rate, composer invalid-output rate, and paraphrase/metamorphic consistency.
Fuzzy windows are scored against an approved bounded envelope; question quality is scored for
clarity, specificity, non-leading wording, and naturalness. Human review is authoritative for
materially surprising assumptions and naturalness. Behavioral metrics are reported by semantic
family and split; they are not collapsed into terminal correctness.

### Live qualification

Run the frozen adapters through the locked holdout and rotating challenge after the offline gate
passes. Capture private, gitignored traces for every receiver and composer call; public artifacts
must be redacted aggregates. A live failure can never yield `ready`: model errors, invalid output,
grounding failures, and composition failures remain explicit and are counted.

The live safety gate is zero unauthorized mutations and zero success-shaped system/model failures,
with exact blocker and prompt coverage for every successfully processed turn. Terminal outcomes
and behavioral quality use preregistered thresholds and confidence intervals; if a threshold has
not yet been owner-approved, report it diagnostically rather than silently promoting it to a
release gate. A passing development run is never sufficient for qualification.

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
