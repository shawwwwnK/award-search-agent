# Full `gpt-4o-mini` Pass 2 contract evaluation

- Date: 2026-09-02
- Model: `gpt-4o-mini`
- Evaluator contract: schema v3, unchanged
- Corpus: all 16 ready scenarios, three trials each (48 runs)
- Corpus SHA-256: `c27ff9fc3295cdb50668386940b9d576e2566818bc4c8d611863d9dbcae27319`
- Artifact: `2026-09-02-gpt-4o-mini-pass2-contract-full-3-trials.json`

## Result

| Measure | Immediate pre-Pass 2 artifact | Pass 2 candidate | Delta |
| --- | ---: | ---: | ---: |
| Passed all blocking checks | 11 | 15 | +4 |
| Completed with failed checks | 19 | 20 | +1 |
| Explicit errors | 18 | 13 | -5 |
| First-attempt completion | 17/48 (35.4%) | 23/48 (47.9%) | +6 |
| Final completion | 30/48 (62.5%) | 34/48 (70.8%) | +4 |

The comparator is `2026-09-02-gpt-4o-mini-prompt-schema-full-3-trials.json`. Both artifacts use the
same production corpus and schema-v3 evaluator. The samples are directly comparable by contract,
but remain independent stochastic three-trial samples.

## Failures by stage or dimension

Dimensions overlap and must not be summed as exclusive root causes.

| Stage / dimension | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Pass-one failures | 0 | 1 | +1 |
| Pass-two wire failures | 1 | 7 | +6 |
| Grounding failures | 0 | 1 | +1 |
| Semantic-validation failures | 26 | 14 | -12 |
| Dependency-stage explicit errors | 10 | 0 | -10 |
| Evidence-support failures | 0 | 3 | +3 |
| Deterministic-output failures | 11 | 12 | +1 |
| Clarification failures | 4 | 4 | 0 |

Exclusive terminal stages changed from 30 completed, 10 dependency, 7 conformance, and 1 wire
record to 34 completed, 7 wire, 6 conformance, and 1 pass-one grounding record. The stricter wire
counts are not hidden successes: they explicitly reject invented catalog identifiers and one
evidence/relation mismatch. Final wire codes were `unknown_evidence_id` (3), `unknown_anchor_id`
(3), and `incompatible_evidence_relation` (1).

## Repair accounting

The candidate records 28 repair attempts and 14 stage-level successes. Pass one attempted 6 and
succeeded 5; Pass 2 attempted 22 and succeeded 9. Repair attempts independently inferred from the
captured per-run model calls equal the 28 recorded attempts, and all 123 model calls have usage
records. No inferred-versus-recorded repair discrepancy remains.

Eleven runs completed after at least one successful repair; only three passed all blocking checks
and eight completed with deterministic mismatches. A structurally successful repair therefore
still does not imply semantic correctness.

## Latency and usage

| Measure | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Total latency | 246.320 s | 285.463 s | +39.143 s |
| Mean / median latency | 5.132 / 5.118 s | 5.947 / 5.713 s | +0.815 / +0.595 s |
| p95 / range | 7.388 / 2.352--10.243 s | 10.414 / 3.264--11.361 s | +3.026 s p95 |
| Captured model calls | 127/127 | 123/123 | -4 |
| Input tokens | 450,127 | 457,040 | +6,913 |
| Output tokens | 18,119 | 17,492 | -627 |
| Total tokens | 468,246 | 474,532 | +6,286 |
| Cost | Not calculated | Not calculated | -- |

## Improvements

- Dependency-stage terminal failures fell from 10 to 0. Reference catalog entries now state their
  permitted target and relation kinds, and dependency errors identify the exact consuming relation.
- `whole_month_with_exact_duration` improved from 0/3 completion to 3/3 passes. Canonical named
  months now carry their required direct `month_portion` relation kind.
- `return_weekend_after_departure` improved from 2/3 passes with one error to 3/3 passes; legitimate
  cross-field dependencies remain supported.
- `multiple_destination_options` improved from 2/3 to 3/3 passes.
- Semantic-validation failure dimensions fell from 26 to 14, while first-attempt and final
  completion both increased.

## Regressions and unchanged failures

- Pass-two wire failures rose from 1 to 7. Six were invented evidence or anchor IDs that remained
  wrong after the bounded repair; one was a newly localized evidence/relation permission failure.
- Evidence-support failures rose from 0 to 3 among completed outputs; catalog permission checks do
  not guarantee that the selected evidence fully supports the resulting deterministic window.
- `missing_travel_period` regressed from three completed outputs to three wire errors because the
  model invented unresolved evidence IDs despite receiving an empty temporal catalog. This is a
  prompt-following and repair limit, not a reason to accept unsupported relations.
- `labor_day_thailand` regressed from three completed failures to one completed failure and two
  errors; weekend evidence/target selection remained unstable.
- `exact_dates_and_cabin` moved from 3/3 to 2/3 passes.
- `relative_date_expression` and `approximate_duration` remained 0/3. The former repeatedly chose
  evidence for the wrong target; the latter invented month-anchor names during repair.
- Unbounded `after New Year` remained 0/3, although two trials now completed instead of all three
  ending in dependency errors.
- Deterministic-output failures remained essentially flat (11 to 12), and clarification failures
  remained 4. The intervention improved contract completion more than end-to-end semantics.

## Contract and instrumentation audit

- The strict Pass 2 output schema has no `oneOf`, `anyOf`, or nullable types. Existing supported
  Pass 1 union/null shapes were unchanged.
- Payload tests confirm that Pass 1, Pass 2, and both repair calls expose no reference date,
  timezone, resolved dates, provider output, golden expectations, or inferred calendar values.
- The production corpus and expectations, deterministic date arithmetic, calendar policy,
  validation strength, repair bound, model, and evaluator semantics were unchanged.
- Repair accounting now reconciles against captured calls. Packet bodies and calculated cost are
  still not persisted by the runner.

## Assumptions and unresolved limitations

- Three trials per case estimate reliability but do not establish statistical significance.
- Catalog permissions make invalid choices visible; they cannot force `gpt-4o-mini` to copy IDs or
  associate valid evidence with the correct target.
- `first week of June` still exposes the pre-existing unresolved-anchor consumption gap. No new
  conformance exception or season/calendar policy was added.
- The `missing_travel_period` traveler expectation and the deterministic extra conflict produced
  for `conflicting_dates` remain evaluator/contract questions separate from this Pass 2 change.

## Owner placeholders

- Product-owner interpretation: _Pending._
- Architectural/model cut-line decision: _Pending project owner decision._
- Final next cut line: _Pending project owner decision._
