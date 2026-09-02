# `gpt-4o-mini` intent relation evaluation — post-fix, three trials

- Date: 2026-09-01
- Corpus: 16 scenarios marked `status: ready`
- Runs: 48
- Passed all blocking checks: 8 (16.7%)
- Completed with failed checks: 7
- Explicit errors: 33
- Total latency: 320.547 seconds
- Usage and cost: unavailable from the current adapter

## Failure taxonomy

The 40 non-passing runs fall into four mutually exclusive outcome buckets.

| Failure type | Runs | Share of all runs | Share of non-passing runs |
| --- | ---: | ---: | ---: |
| Flat wire output could not convert to a typed relation | 19 | 39.6% | 47.5% |
| Explicit anchor or graph validation error | 14 | 29.2% | 35.0% |
| Strict source-grounding failure | 3 | 6.3% | 7.5% |
| Completed output with incorrect temporal semantics | 4 | 8.3% | 10.0% |

### Flat wire to typed relation conversion

Nineteen runs ended in `DateResolutionError` after the API had accepted the flat Structured Outputs
schema. The artifact records the generic message `OpenAI returned an invalid temporal reference`,
so it does not retain the exact conversion cause for each run. A separate diagnostic replay exposed
`relative_weekday constraint requires direction`, proving this bucket also contains missing
kind-specific fields and is not limited to malformed reference objects.

This is currently the largest failure class. The flat nullable schema satisfies the API's supported
JSON Schema subset, but it does not reliably make `gpt-4o-mini` populate every field required by the
selected internal relation variant.

### Explicit semantic and graph validation

Fourteen runs ended in `TemporalResolutionValidationError`:

- 12 rejected anchors whose grounded quote did not support the proposed anchor kind, including
  month anchors backed by `next month`, `next spring`, `two weekends after`, `about 10 days`, or
  `the weekend afterwards`; exact-date anchors backed by `Thursday` or `about 10 days`; and a Labor
  Day anchor backed only by `the weekend afterwards`.
- 2 rejected cyclic request-field dependencies at departure.

These failures are explicit rejections of unsupported semantics rather than success-shaped date
outputs.

### Strict grounding

Three completed records failed exact occurrence grounding:

- Two `exact_dates_and_cabin` trials used occurrence index 1 for `October 15`, which appears once.
- One `tentative_city_and_month` trial used occurrence index 1 for `Maybe sometime in January`,
  which appears once.

### Completed but semantically incorrect

Four runs reached deterministic evaluation but failed expected temporal outputs:

- `missing_origin`: exact `for a week` became an approximate 6–8 day duration.
- `early_month_with_approximate_duration`: `early May` became the whole month, widening both the
  departure and derived return windows.
- `multiple_destination_options`: `about a week` became exactly six days.
- `whole_month_with_exact_duration`: exact `for 2 weeks` became 13–15 days.

The deterministic evaluator applied the typed portions and quantities it received. These observed
failures occurred in semantic relation selection, before deterministic calendar arithmetic.

## Scenario outcomes

| Scenario | Passed | Failed checks | Errors |
| --- | ---: | ---: | ---: |
| `labor_day_thailand` | 0 | 0 | 3 |
| `labor_day_thursday_flexibility` | 0 | 0 | 3 |
| `return_weekend_after_departure` | 0 | 0 | 3 |
| `exact_dates_and_cabin` | 0 | 2 | 1 |
| `missing_origin` | 1 | 1 | 1 |
| `missing_travel_period` | 3 | 0 | 0 |
| `relative_date_expression` | 0 | 0 | 3 |
| `approximate_duration` | 0 | 0 | 3 |
| `conflicting_dates` | 0 | 0 | 3 |
| `multiple_destination_options` | 2 | 1 | 0 |
| `repositioning_allowed` | 0 | 0 | 3 |
| `adversarial_schema_instruction` | 0 | 0 | 3 |
| `early_month_with_approximate_duration` | 1 | 1 | 1 |
| `unbounded_after_new_year` | 0 | 0 | 3 |
| `whole_month_with_exact_duration` | 1 | 1 | 1 |
| `tentative_city_and_month` | 0 | 1 | 2 |

## Comparison with the August 30-era runs

The original baseline immediately following the August 30 implementation recorded 14 passes, 31
failed outputs, and 3 errors. The later current-workflow rerun recorded 30 passes, 16 failed outputs,
and 2 errors. Those artifacts were written after midnight on August 31.

The pass rates are not directly comparable accuracy measurements because the current evaluator adds
typed relation conversion, graph validation, and claim-level evidence checks. The comparison does
show that the latest workflow's dominant reliability problem is now the model-to-typed-relation
boundary, not silent deterministic calendar arithmetic.

Product-owner interpretation and the next implementation cut remain pending.
