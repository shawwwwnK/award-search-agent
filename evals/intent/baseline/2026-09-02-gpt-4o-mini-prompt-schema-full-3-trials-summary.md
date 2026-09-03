# Full `gpt-4o-mini` prompt/schema evaluation

- Date: 2026-09-02
- Model: `gpt-4o-mini`
- Evaluator contract: schema v3, unchanged
- Corpus: all 16 ready scenarios, three trials each (48 runs)
- Corpus SHA-256: `c27ff9fc3295cdb50668386940b9d576e2566818bc4c8d611863d9dbcae27319`
- Artifact: `2026-09-02-gpt-4o-mini-prompt-schema-full-3-trials.json`

## Result

| Measure | Prior schema-v3 artifact | Prompt/schema candidate | Delta |
| --- | ---: | ---: | ---: |
| Passed all blocking checks | 4 | 11 | +7 |
| Completed with failed checks | 18 | 19 | +1 |
| Explicit errors | 25 | 18 | -7 |
| First-attempt completion | 15/48 (31.2%) | 17/48 (35.4%) | +2 |
| Final completion | 22/48 (45.8%) | 30/48 (62.5%) | +8 |

The artifacts use the same production corpus and schema-v3 evaluator, so these counts are directly
comparable. They are independent stochastic three-trial samples, not paired deterministic outputs.

## Failures by stage or dimension

Dimensions overlap and must not be summed as exclusive root causes.

| Stage / dimension | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Pass-one failures | 3 | 0 | -3 |
| Pass-two wire failures | 5 | 1 | -4 |
| Grounding failures | 1 | 0 | -1 |
| Semantic-validation failures | 31 | 26 | -5 |
| Dependency-stage explicit errors | 6 | 10 | +4 |
| Evidence-support failures | 4 | 0 | -4 |
| Deterministic-output failures | 6 | 11 | +5 |
| Clarification failures | 5 | 4 | -1 |

Exact terminal-stage counts changed from 22 completed, 12 pass-two conformance, 6 dependency, 5
wire conversion, 2 pass-one anchor validation, and 1 grounding record to 30 completed, 7
pass-two conformance, 10 dependency, 1 wire conversion, and no pass-one or grounding terminal
records.

## Repair accounting

The new artifact records 31 repairs and 13 successes: pass one attempted 3 and succeeded 3; pass
two attempted 28 and succeeded 10. Captured call counts exactly reconcile: 96 base calls plus 31
repair calls equals 127 captured calls.

The prior artifact's recorded 34 attempts and 8 successes undercounted five successful pass-one
repairs. Five later pass-two failures each captured four calls (base pass one, pass-one repair, base
pass two, pass-two repair) but recorded only one repair. Corrected prior accounting is therefore 39
attempts and 13 successes: pass one 10/7 and pass two 29/6. This correction does not change the
prior output or pass/fail counts.

## Latency and usage

| Measure | Before | After |
| --- | ---: | ---: |
| Total latency | 321.280 s | 246.320 s |
| Mean / median latency | 6.693 / 5.954 s | 5.132 / 5.118 s |
| p95 / range | 12.582 / 3.242--32.728 s | 7.388 / 2.352--10.243 s |
| Captured model calls | 132/132 | 127/127 |
| Input tokens | 306,602 | 450,127 |
| Output tokens | 23,281 | 18,119 |
| Total tokens | 329,883 | 468,246 |
| Cost | Not calculated | Not calculated |

Latency decreased despite a 46.8% increase in input tokens. The larger input is attributable to
field/model descriptions embedded in the generated schemas. No cost inference is made.

## Improvements

- Pass one produced no final validation or grounding failures.
- Wire namespace errors fell from five to one; no `unknown_evidence_id` errors remained.
- Exact dates passed all three trials, up from one.
- `return_weekend_after_departure` passed two trials, up from zero.
- `missing_travel_period` emitted empty relation collections in all completed outputs and passed one
  trial, up from zero completion.
- `next month` produced the symbolic `context:request_date` whole-calendar-period relation in all
  three completed outputs; no explicit inferred month anchor was accepted.
- `next spring` produced unresolved departure relations in all three completed outputs rather than
  an unspecified target.
- Literal-duration check failures fell from ten to one among completed outputs.
- Evidence-support failures fell from four to zero.

## Regressions and unchanged failures

- Dependency-stage errors rose from 6 to 10, dominated by eight `unresolved_dependency` errors.
  `whole_month_with_exact_duration` regressed from three completed outputs to three errors, and
  unbounded `after New Year` ended in three errors.
- Deterministic-output mismatches rose from 6 to 11. Completed records more often exposed upstream
  semantic differences as window or conflict mismatches instead of ending earlier in wire or
  conformance failure.
- `first week of June` remained 0/3 because the current unresolved wire cannot consume the required
  literal month-anchor claim without also producing a bounded relation.
- Relative weekday handling remained 0/3. Two cyclic dependencies and one incompatible evidence
  claim survived repair.
- Non-temporal traveler and destination extraction caused repeated failures in `next month` and
  `next spring` even when temporal semantics improved.
- Repairs frequently became schema-valid but semantically wrong: 18 of 28 pass-two repairs still
  failed, often as unresolved dependencies or deterministic mismatches.

## Contract and instrumentation audit

- Strict pass-two output contains no `oneOf`, `anyOf`, or nullable fields. Pass one uses only the
  API-supported anchor-reference `anyOf` and nullable scalar shapes already exercised by the live
  Structured Outputs calls; it contains no `oneOf` or unsupported union shape.
- Pass-one, pass-two, and both repair DTOs remain structurally date-free at their prohibited
  boundaries. Static serialized-payload tests cover reference date, timezone, resolved anchors,
  provider detail, expected answers, and inferred calendar values.
- The prior repair-accounting defect is verified above. The new artifact has no call-count
  discrepancy, but the runner still does not persist packet bodies or calculate cost.

## Assumptions and unresolved limitations

- The production corpus, golden expectations, deterministic validators, calendar policy,
  evaluator semantics, and model were unchanged.
- A three-trial sample estimates reliability but does not establish statistical significance.
- Prompt/schema guidance alone did not solve dependency selection, unsupported month-portion
  representation, or unrelated non-temporal extraction reliability.
- A separate architectural follow-up should decide whether unresolved relations may explicitly
  consume an anchor claim. No conformance rule was added here.

## Owner placeholders

- Product-owner interpretation: _Pending._
- Final next cut-line decision: _Pending owner decision._
