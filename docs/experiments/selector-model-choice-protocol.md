# Historical selector-model choice protocol

## Status and scope

This is an archived selector-screen test plan. ADR 0010 subsequently selected the selector-only
request-understanding architecture and retired sequential temporal resolution. It remains a
reference for future selector-model comparisons, but it does not change the frozen Luna model
decision, the current runtime, or reintroduce a fallback path.

The checked-in v2 fixture at `evals/selector/frozen_cases_v2.yaml` is a useful regression and
development screen, but it has twelve semantic stems paired into two order variants and repeated
three times.  It is not an independent holdout and cannot by itself establish generalization or a
production model default.

## Pre-registration and reproducibility

Before a candidate-comparison run:

1. Freeze the public fixture path and SHA-256, selector instruction text, JSON schema, SDK
   version, exact model ID (prefer a dated snapshot where one is available), request date, and
   API-pricing snapshot.
2. Pre-register the candidate models, primary/secondary metrics, quality gates, sample sizes,
   concurrency, retry policy, and the decision rule.  Do not alter the holdout after observing a
   candidate's outputs.
3. Retain redacted artifacts with per-run status, model, latency, usage, and gate results.  Scan
   artifacts and traces for resolved dates, request context, source offsets, private catalogs,
   or credentials before publishing them.

## Decision sequence

The sequence below records the historical model-choice protocol. It is not an outstanding release
checklist for the frozen intent implementation; any future run must be explicitly authorized and
must preserve the current selector-only boundary.

### 1. Development screen (archived frozen v2 fixture)

Run every candidate on the fixed v2 fixture with three trials and both opaque-handle order
variants.  Report parse, membership, compiler completion, semantic accuracy, each class,
unsupported-to-unresolved accuracy, repair attempts, latency, and token usage.

The existing handoff gate remains the minimum screen:

| Check | Minimum |
| --- | ---: |
| Parse, membership, compiler completion | 100% |
| Overall semantic accuracy | 95% |
| Target, reference, composition, scope | 90% each |
| Unsupported-to-unresolved | 100% |
| Repair attempts | 0 |

Passing this screen only qualifies a model for the next evaluation stage.  A failure excludes it
from selector-enabled E2E experiments unless a separately documented contract change is made.

### 2. Independent semantic holdout

Create and freeze manually reviewed, previously unseen ambiguity stems: start with 30 independent
stems for each of target, reference, composition, scope, dependency closure, and unsupported
selection (180 stems).  Generate two opaque-handle/order variants per stem (360 requests per
model), then run three temporally separated repetitions (1,080 calls per model).

Report results both by independent stem and by request.  A model must meet the pre-registered
gate in every semantic stratum, preserve 100% unsupported-to-unresolved behavior, and have no
compiler-safety failures.  Treat repeated calls as stability evidence, not as independent semantic
examples; report Wilson confidence intervals using independent stems.

If the full holdout is too costly for early pruning, use a distinct 10-stems-per-class development
set first, then leave the 180-stem holdout untouched for finalists.

### 3. Metamorphic and adversarial safety suite

For every holdout stem, test deterministic transformations with the same oracle:

- permuted opaque candidate/group/evidence/anchor/production-slot handles and candidate order;
- irrelevant date-free prose, reordered evidence/groups/anchors, and repeated anchors;
- endpoint-cue conflicts and absent endpoint cues;
- two to four supported alternatives plus an unresolved option;
- dependency chains, invalid closures, and cycles.

Separate a parse or restoration rejection from a dangerous but schema-valid semantic selection.
Any private-data leak, invalid membership, unsafe compiler completion, or selection of an
unsupported interpretation is a release blocker rather than an accuracy trade-off.

### 4. Selector-path integration evaluation (historical protocol)

The 16-case ready corpus was used as a compiler-route rollback-isolation test: while its grammar
yielded no genuine ambiguity, it had to make zero selector and Pass-2 calls. The historical
Pass-2 reference is retained only to explain those earlier artifacts; it is not a current runtime
stage.

Add a test-only, manually constructed ambiguity integration corpus that exercises:

`projection -> selector -> restoration -> deterministic compiler -> workflow result`.

Evaluate every finalist through that corpus with static non-temporal extraction and a fake holiday
provider.  Introducing a genuine ambiguity into the production grammar would be a product change,
not an evaluation-only action, and requires an architecture checkpoint before it is attempted.

### 5. Operational and cost confirmation

For finalists, run the selected selector-path corpus at the intended concurrency and measure
p50/p95/p99/max latency, 429/5xx/error rate, parse/membership/compiler failure rate, input/output
tokens, and calculated cost using the dated pricing snapshot.  Repeat on a separate day before
choosing a default.

At the time this protocol was written, rollback criteria were any safety failure, gate miss,
materially regressed tail latency/cost outside the pre-registered budget, or trace/privacy failure.
The former `two_pass` rollback language is superseded by ADR 0010; two-pass is retired and is not
a current fallback path.

## Historical evidence boundary

The validated v2 frozen study qualified `gpt-5.6-luna` and `gpt-5.6-terra` only for a
selector-enabled compiler E2E experiment. The project owner selected `gpt-5.6-luna` for those
experiments on 2026-09-04, based on its passed screen and lower published token pricing.
`gpt-4o-mini`, `gpt-4.1-mini`, `gpt-4.1`, and `gpt-5.4-mini` did not pass the current screen.
Luna subsequently passed the test-only selector-to-workflow integration gate across the same
known frozen-v2 stems. These are historical comparison results, not the current intent
qualification record.

## Project-owner decision record

The project owner concluded on 2026-09-06 that request understanding is complete and frozen. The
selector-only Luna path is the sole live path, and sequential two-pass resolution is retired. The
final qualification record is
`evals/intent/baseline/2026-09-06-gpt-5.6-luna-selector-only-prompt-repair-3-trials.json`:
47/48 passed (97.92%) over three trials, with zero errors and one documented clarification miss.
Its all-call traces remain private/local under `evals/intent/traces/`. No further intent changes
are authorized without an explicit owner decision to reopen the slice.
