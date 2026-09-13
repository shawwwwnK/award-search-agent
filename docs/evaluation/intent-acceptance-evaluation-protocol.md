# Intent acceptance evaluation protocol

This protocol qualifies the LLM-owned initial-intent boundary in ADR 0017 while preserving the
one-way award policy in ADR 0016. It evaluates whether raw language is interpreted into grounded,
generic typed semantics and whether deterministic code safely turns those semantics into a ready,
clarification, or unsupported outcome. It does not require one exact model AST, operation spelling,
evidence segmentation, or customer-facing sentence.

## Evaluation boundary

The `InitialIntentInterpreter` is the only semantic reader of the raw initial request. It emits
typed facts, exact source evidence, and generic temporal operations. Deterministic code grounds the
evidence, validates the typed result, evaluates calendar operations, detects conflicts, applies the
one-way award policy, and produces `ParsedRequest` plus `ClarificationDecision`. Deterministic code
must not scan raw text for temporal phrases, reinterpret a quote, expand locations into airports,
call travel providers, or recover meaning from a rejected model result.

The provider adapter is a wire boundary, not another semantic evaluator. A flat provider schema is
permitted for structured-output compatibility, and its translation into the internal contract must
be structural. Provider schema rejection before inference is adapter/preflight evidence, not
evidence that the model misunderstood the request.

Offline tests use fake, already-typed receiver outputs to test evidence identity, generic operation
validation, graph topology, calendar arithmetic, conflict handling, one-way policy, clarification
coverage, repair/pending reduction, provenance, and immutable state. They must not assert that
deterministic code understands a raw phrase, typo, or paraphrase. A raw request may be retained for
exact quote/span integrity tests only.

## Outcomes and action/property oracles

Each fixture declares an observable outcome envelope. It may allow more than one safe result only
when the alternatives are explicitly listed. The oracle has no field for a receiver AST, candidate
ID, relation spelling, exact evidence segmentation, or generated prompt copy.

```yaml
acceptable_actions: [ready, clarification]
must_ground: [origin, destination, travelers, departure]
must_remain_blocked: []
state_envelope:
  statuses: [ready]
  relations: [ready_iff_no_blockers]
properties:
  departure_window: {year: 2026, month: 9, start_day: [4, 7], end_day: [4, 7]}
  travelers: [2]
  mode: [award]
forbidden_outcomes:
  - return_or_duration_in_active_state
  - city_expanded_to_airports
  - success_shaped_model_failure
guidance:
  required: false
```

The supported action set is:

- `ready`: required origin, destination, bounded outbound departure, and travelers are present;
- `clarification`: a deterministic blocker set preserves missing, ambiguous, conflicting, or
  user-resolvable information;
- `unsupported`: recognized return/trip-duration scope or cash-only intent receives explicit stable
  guidance and does not become a misleading ready request; and
- `pending_retryable`: a genuine preflight, authentication/configuration, network/transport, or
  provider operational failure remains visibly retryable and non-mutating. A model response that
  remains unusable after its permitted repair completes as clarification with salvaged facts and
  explicit blockers; it is never pending.

Fixtures should use `must_ground`, `must_remain_blocked`, bounded date envelopes, exact arithmetic
values, mode, traveler count, provenance requirements, and forbidden outcomes to express the
permitted result. Exact values are required where the product contract requires them, especially
deterministically computed dates and traveler count. A bounded envelope is appropriate for an
approved approximation or an intentionally flexible date interpretation.

For a clarification fixture, `must_remain_blocked` and `blocker_order` check the authoritative
requirements and deterministic ordering, not the wording of a later question. For an unsupported
fixture, the oracle requires the relevant grounded evidence, stable guidance category, and absence
of active return/duration or cash-only state. For a pending fixture, it requires unchanged state,
visible retryability, preserved valid independent facts, no user no-progress increment, and no raw
provider/model/validation detail in the user-facing status. An inference-reached
model/representation failure fixture must instead complete as `clarification` with salvaged facts
and explicit blockers. A reasonable-language or representation-noise fixture must reach `ready`,
`clarification`, or `unsupported` after internal normalization/repair.

## Exact safety properties

These are hard properties, not model-quality preferences. The offline gate must pass all of them,
and live qualification has zero tolerance for any violation:

- A deterministic module never assigns semantics by scanning, regex-matching, classifying, or
  repairing raw request text. Exact quote lookup is allowed only to validate model-provided
  evidence identity and occurrence.
- Every accepted fact has an exact source quote, valid occurrence, canonical evidence ID, and
  original-message identity. Ungrounded or ambiguous evidence cannot silently enter state.
- Final concrete dates and windows are computed by deterministic calendar code from validated
  operations and immutable context. Model-provided resolved dates are diagnostic only and cannot
  be trusted as authoritative.
- Temporal references form a validated acyclic graph. Unknowns, alternatives, and conflicts are
  preserved; invalid, impossible, empty, or unbounded calculations cannot become ready.
- A ready result contains origin, destination, traveler count, and a bounded non-empty outbound
  departure window. It contains no return window, trip duration, or return temporal contribution.
- Recognized return/trip-duration intent yields explicit separate-one-way guidance and no active
  return/duration state or blocker. Cash-only intent yields explicit unsupported/invalid behavior;
  mixed award-and-cash intent never claims cash-search coverage.
- Locations remain resolver candidates. No city-to-airport expansion or provider call occurs in
  the intent component.
- A grounded correction or semantic fact cannot mutate unrelated hard constraints. State reduction
  is atomic, provenance-preserving, immutable, replay-safe, and idempotent.
- A rejected model result receives at most one shared model-owned repair. If the inference-reached
  result remains unusable, it completes as `clarification`, non-mutating with respect to unrelated
  constraints, visibly represented by explicit blockers, and retaining valid independent siblings.
  Ordinary reasonable language—including typo/paraphrase and provider-wire representation/shape
  noise—must be internally repaired into a normal outcome; it is not pending. No pending result is
  `ready`, a fabricated clarification, a raw exception, or a user no-progress turn.
- A provider/schema preflight failure before inference is recorded as adapter/pending evidence,
  receives no futile retry of the identical schema, and does not spend the semantic-repair budget.
- There is one live initial workflow: no raw scanner, opaque selector, sequential resolver, hidden
  candidate fallback, or runtime strategy switch can alter the result.
- A user-language problem never leaks as a user-visible exception or pending result. Ambiguity,
  incompleteness, conflict, and genuine unboundedness become `clarification`; recognized
  out-of-scope intent becomes `unsupported`; typo/paraphrase and representation/shape variance in
  reasonable input are normalized/repaired internally. Inference-reached model-contract failures
  complete as clarification after repair; only genuine preflight, authentication/configuration,
  network/transport, or provider operational failure becomes `pending_retryable`.
- Private traces and public artifacts obey the existing redaction and privacy requirements.

Instrumentation, static inspection, and call-capture tests must make these properties observable;
terminal pass rates cannot hide a safety violation.

## Corpus and freeze

The corpus has three deliberately separate classes:

| Set | Visibility | Purpose | Handling |
| --- | --- | --- | --- |
| Disclosed development baseline | Checked in and visible | Prompt/schema development, deterministic regression tests, and initial metric estimates | May change before freeze; never the sole qualification evidence |
| Locked external holdout | Kept outside the implementation workspace by an independent evaluator | Unbiased qualification after code and prompts are frozen | Agents receive only a version/hash and redacted aggregates |
| Rotating post-freeze metamorphic challenge | Authored or sampled after freeze and hidden until scoring | Detect prompt overfitting and newly observed-language regressions | Exposed cases become public regressions and are replaced |

The disclosed baseline must exercise exact dates and ranges, month and holiday anchors, supported
relative outbound expressions, typos and unfamiliar recognizable paraphrases, repeated evidence,
missing fields, ambiguity, conflicts, alternatives, invalid/unbounded timing, return dates,
durations, cash-only requests, mixed award-and-cash requests, and malformed model results. Include
all required fields and each independent blocker in multiple combinations.

Metamorphic pairs preserve the underlying request meaning while changing spelling, casing,
punctuation, word order, harmless filler, or equivalent calendar phrasing. Additional paired cases
move an input across an accept/clarify or supported/unsupported boundary. The expected result is
expressed as an action/property envelope; a model may choose a different valid generic operation
representation. Metamorphic changes must not grant new hard constraints or make an unsupported
return/duration target active.

Before holdout or challenge scoring, preregister the receiver and adapter versions, prompts,
generated schema hash, model ID/settings, repair policy, evaluator version, corpus hashes, trial
count, metrics, confidence method, and decision rules. No hidden case may be used to tune the
implementation without a new freeze and preregistration.

## Metrics

Every metric reports numerator, denominator, split, semantic family, and trial count. A zero
denominator is `not applicable`, never `0%` or `100%`, and cannot support a qualification claim.

### Semantic diagnosis

Semantic diagnosis is expert-reviewed evidence about what the receiver understood, separate from
whether deterministic code could safely execute it. Report by family and corpus split:

- grounded identification of origin, destination, travelers, cabin, mode, and outbound timing;
- recognition of return/trip-duration and cash-only scope;
- interpretation of typos and understandable paraphrases into an allowed generic operation;
- ambiguity, conflict, alternative, and unsupported-intent recognition;
- evidence sufficiency and source-occurrence selection; and
- representation/contract failures after a semantically reasonable interpretation (these consume
  the repair allowance and then complete as clarification with salvaged facts, not pending).

This dimension may use calibrated human review (with an LLM judge only as a disclosed aid). A
semantic diagnosis success does not count as an end-to-end behavioral pass if the result was not
safely representable or executable.

### Behavioral action/property outcomes

Score the final workflow against the fixture oracle, not literal output shape or wording. Report:

- action/property-oracle success and failure by family;
- false-block rate for reasonable, supported requests;
- unsafe or incorrect acceptance rate for ambiguity, conflict, unsupported, and unbounded cases;
- exact deterministic date/window and traveler-value correctness;
- required-field and blocker coverage, ordering, and valid-independent-fact retention;
- return/duration non-mutation and cash-only/mixed-mode policy correctness;
- approved approximation-envelope and disclosure correctness where applicable; and
- turns/calls to ready or clarification convergence when continuation is in scope.

Behavioral failures are distinct from operational pending outcomes. A pending result caused by a
provider outage is not a false block, while an ordinary understandable request—or a recoverable
representation/shape defect—that reaches pending is a behavioral/operational regression and must
be visible as such. A model-contract defect that completes as clarification is scored against its
clarification and salvage oracle, not as an operational pending.

### Safety

Report each safety numerator and denominator separately, with zero tolerance for any violation:

- unauthorized or unrelated hard-constraint mutation;
- ungrounded facts or invalid evidence occurrence;
- unsafe acceptance of ambiguity, conflict, unbounded timing, return/duration, or cash-only intent;
- fabricated or model-authoritative dates;
- return/duration state mutation or cash-coverage claim;
- city-to-airport expansion or travel-provider call;
- success-shaped model/provider failure or raw exception exposure;
- repair-budget violation, lost valid siblings, or user no-progress mutation on pending; and
- privacy/redaction leakage.

Safety findings are disqualifying even if the aggregate behavioral score is high. Deterministic
tests and trace review, not a probabilistic judge, are authoritative for these properties.

### Operational and repair quality

Report first-pass structured-output validity, evidence/operation validation failures, one-repair
attempt rate, repair success/failure rate, residual pending rate, provider preflight rejection,
inference-reached rate, runtime/model error rate, model calls, repair-attributed p50/p95 latency,
tokens/cost, and trace reconciliation. Also report pending rate by semantic family so ordinary
language failures are not hidden inside an all-request average.

Preflight, authentication/configuration, transport/network, and provider errors are operational
evidence. They are not semantic diagnoses and may produce `pending_retryable`; a valid model result
that fails the typed contract consumes the repair allowance and then completes as clarification if
still unusable. A shape/representation defect on otherwise reasonable input is repair/salvage work,
not a user-visible pending outcome.

## Offline gate

Run the complete disclosed baseline with fake model outputs and fake holiday data before any live
run. The hard gate requires:

1. 100% of deterministic schema, evidence, graph, calendar, boundedness, conflict, provenance,
   state-reduction, one-way, mode, blocker, privacy, and idempotency invariants.
2. 100% enforcement of the single-repair rule, clarification salvage for inference-reached model
   contract failures, valid-sibling retention, provider-preflight distinction, no user-visible raw
   exception, and no pending result for reasonable language or recoverable representation/shape
   noise.
3. 100% proof that the live initial route does not construct or invoke a scanner, selector,
   sequential resolver, or fallback, and that deterministic code does not semantically parse raw
   request text.
4. Action/property-oracle machinery that exercises ready, clarification, unsupported, and
   pending-retryable outcomes with non-vacuous denominators for every proposed behavioral gate.

The baseline's semantic and behavioral rates are diagnostic until owner-approved thresholds are
preregistered. A clean offline safety run does not by itself qualify a model or prove natural
language coverage.

## Bounded live evaluation

After the offline gate and freeze, run the same configured receiver and adapter over the locked
holdout and rotating challenge for at least three independent trials, or the owner-approved trial
count. Capture private, gitignored all-call traces, including first-pass and repair calls, and
publish only redacted aggregate artifacts with fixture, prompt, schema, adapter, and evaluator
hashes.

The live hard gate is zero unauthorized mutations, ungrounded accepted facts, unsafe acceptance,
return/duration or cash-policy violations, provider/model failures represented as success, raw
exceptions, repair-budget violations, and trace mismatches. Every successfully processed request
must also have complete deterministic blocker/state coverage. User-language ambiguity or
incompleteness must be represented as clarification, and recognized unsupported intent as
unsupported; neither may be recoded as a system error. Reasonable language and recoverable
representation/shape variance must not be recoded as pending; inference-reached model-contract
failures must complete as clarification with salvage. Pending is limited to genuine preflight,
authentication/configuration, network/transport, or provider operational failures and must expose
only a generic retryable stage/code status.

Behavioral thresholds, confidence intervals, and any model comparison decision must be
preregistered. If thresholds have not been approved after the baseline, report the live matrix as
diagnostic rather than silently calling it qualification. A passing disclosed run is never enough
for release.

## Reporting and anti-overfit rules

The report must show corpus hashes, fixture-family counts, split/trial counts, model and schema
versions, action/property numerators and denominators, semantic-review sample sizes, safety
violations, operational error classes, repair/pending attribution, latency/tokens/cost, and trace
reconciliation. Public artifacts must not contain raw user travel data or private prompts/payloads.

When a hidden case is exposed during debugging, promote it to disclosed regression coverage and
replace it in the holdout or rotating pool. Do not alter a fixture oracle after observing output
unless the owner approves the semantic change and a new preregistration. Preserve failed traces
privately so representation failures, unsafe acceptance, and ordinary user clarification are not
collapsed into one terminal score.

## Qualification decision

Qualification requires the offline hard gate, the live zero-safety gate, reconciled traces, and
non-vacuous denominators for every owner-approved behavioral/operational gate. Behavioral quality
must meet its preregistered thresholds by semantic family and split; otherwise the result is
diagnostic and the implementation remains unqualified. Genuine preflight,
authentication/configuration, network/transport, or provider operational failures may be reported
as pending, but no such failure may produce a success-shaped ready result or expose raw detail.
Inference-reached model-contract failures must complete as clarification with salvaged facts and may
not be blamed on reasonable user language.
