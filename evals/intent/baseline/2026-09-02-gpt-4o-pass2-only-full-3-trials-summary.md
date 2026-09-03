# Pass 2-only model experiment: full corpus

- Date: 2026-09-02
- Pass 1 model: `gpt-4o-mini`
- Pass 2 model: `gpt-4o`
- Evaluator contract: schema v3, unchanged
- Corpus: all 16 ready scenarios, three trials each (48 runs)
- Corpus SHA-256: `c27ff9fc3295cdb50668386940b9d576e2566818bc4c8d611863d9dbcae27319`
- Artifact: `2026-09-02-gpt-4o-pass2-only-full-3-trials.json`

## Result

| Measure | All-mini Pass 2 | `gpt-4o` Pass 2 | Delta |
| --- | ---: | ---: | ---: |
| Passed | 15/48 (31.3%) | 23/48 (47.9%) | +8 |
| Completed with failed checks | 20 | 17 | -3 |
| Explicit errors | 13 | 8 | -5 |
| First-attempt completion | 23/48 (47.9%) | 34/48 (70.8%) | +11 |
| Final completion | 34/48 (70.8%) | 40/48 (83.3%) | +6 |

These are independent stochastic three-trial samples under the same corpus, expectations, and
evaluator contract. The Pass 1 model remained `gpt-4o-mini` in both runs.

## Failure dimensions

Dimensions overlap and are not exclusive root causes.

| Stage / dimension | All-mini Pass 2 | `gpt-4o` Pass 2 | Delta |
| --- | ---: | ---: | ---: |
| Pass-one failures | 1 | 1 | 0 |
| Pass-two wire failures | 7 | 2 | -5 |
| Grounding failures | 1 | 0 | -1 |
| Semantic-validation failures | 14 | 13 | -1 |
| Dependency-stage terminal errors | 0 | 3 | +3 |
| Evidence-support failures | 3 | 0 | -3 |
| Deterministic-output failures | 12 | 7 | -5 |
| Clarification failures | 4 | 8 | +4 |

The stronger model substantially reduced invented-ID wire failures and evidence-support failures,
but did not eliminate dependency errors. Clarification failures increased and remain an evaluator-
visible weakness.

## Per-case observations

- 3/3 passes: `exact_dates_and_cabin`, `relative_date_expression`,
  `early_month_with_approximate_duration`, `whole_month_with_exact_duration`.
- 2/3 passes: `labor_day_thailand`, `missing_origin`, `missing_travel_period`,
  `multiple_destination_options`.
- 0/3 passes: `approximate_duration`, `conflicting_dates`, `labor_day_thursday_flexibility`,
  `repositioning_allowed`, `unbounded_after_new_year`.
- `return_weekend_after_departure` passed once, failed once, and errored once.

The unchanged failures indicate that a stronger Pass 2 model is not sufficient for literal duration
dependency selection, unbounded-boundary semantics, conflict expectations, or several clarification
policies.

## Repair, latency, and usage

| Measure | All-mini Pass 2 | `gpt-4o` Pass 2 |
| --- | ---: | ---: |
| Repair attempts / successes | 28 / 14 | 14 / 6 |
| Pass 1 repairs | 5/6 | 3/4 |
| Pass 2 repairs | 9/22 | 3/10 |
| Total latency | 285.463 s | 451.516 s |
| Mean / median latency | 5.947 / 5.713 s | 9.407 / 8.997 s |
| Total tokens | 474,532 | 409,878 |
| Captured calls | 123/123 | 109/109 |

The stronger model made fewer repair calls because more first attempts completed. Its latency was
approximately 58% higher overall. Cost was not calculated.

## Limitations and decision boundary

- The runner now supports split models only for evaluation; default single-model invocation is
  unchanged.
- Three trials per case do not establish statistical significance.
- `gpt-4o` is an available Responses API model according to the official OpenAI model catalog,
  but account-specific availability and pricing were not measured here.
- No production model switch is recommended by this artifact alone. The evidence supports a targeted
  cost/quality decision for Pass 2, or further contract simplification, after owner review.

## Owner placeholders

- Model-quality/cost interpretation: _Pending._
- Production model-selection decision: _Pending project owner._
- Final next cut line: _Pending project owner decision._
