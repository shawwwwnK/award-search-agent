# Focused `gpt-4o-mini` Pass 2 contract evaluation

- Date: 2026-09-02
- Model: `gpt-4o-mini`
- Evaluator contract: schema v3, unchanged
- Trials: 3 across 8 unchanged ready scenarios (24 runs)
- Production corpus SHA-256: `c27ff9fc3295cdb50668386940b9d576e2566818bc4c8d611863d9dbcae27319`
- Temporary focused corpus SHA-256: `0425d690b42488e46e2d23c4fd3d901fef24491ec3b3eed3867b6456d44cc996`
- Artifact: `2026-09-02-gpt-4o-mini-pass2-contract-focused-3-trials-2.json`

The temporary corpus copied the production entries for relative weekend, relative weekday, no
origin, approximate week duration, unbounded `after New Year`, whole-month exact duration, and two
month/flexibility cases. Case bodies and expectations were not changed.

An earlier candidate artifact, `2026-09-02-gpt-4o-mini-pass2-contract-focused-3-trials.json`, is
retained but was rejected by the focused guard because `return_weekend_after_departure` passed 0/3.
Evidence-level relation permissions were then added and this second, non-overwriting run was used
for the gate.

## Same-case comparison

| Measure | Immediate pre-Pass 2 subset | Pass 2 candidate | Delta |
| --- | ---: | ---: | ---: |
| Passed / failed / error | 3 / 3 / 18 | 9 / 7 / 8 | +6 / +4 / -10 |
| First-attempt completion | 4/24 | 10/24 | +6 |
| Final completion | 6/24 | 16/24 | +10 |
| Recorded repairs / successes | 20 / 2 | 16 / 8 | -4 / +6 |
| Total latency | 128.065 s | 141.726 s | +13.661 s |
| Captured calls | 68 | 63 | -5 |
| Input / output tokens | 244,177 / 9,942 | 236,467 / 9,291 | -7,710 / -651 |

The immediate comparator is the same eight-case subset of
`2026-09-02-gpt-4o-mini-prompt-schema-full-3-trials.json`. Both use the same schema-v3 evaluator,
but they are independent stochastic samples rather than paired deterministic outputs.

Terminal outcomes moved from 6 completed, 10 dependency, 7 conformance, and 1 wire failure to 16
completed, 1 dependency, 6 conformance, and 1 pass-one anchor failure. The focused gate therefore
justified the full run. The legitimate departure-to-return dependency remained expressible:
`return_weekend_after_departure` passed 2/3 focused trials.

## Case observations

- `whole_month_with_exact_duration` improved from three dependency errors to 3/3 passes. The
  canonical named-month relation is now stated by the catalog instead of inferred by the model.
- `missing_origin` passed 3/3.
- `relative_date_expression` completed and passed once, but two trials still attached weekend
  evidence to the wrong target.
- `approximate_duration` remained 0/3 because the model invented anchor identifiers during repair.
- `unbounded_after_new_year` completed twice but did not pass; one trial still ended in dependency
  failure.
- `tentative_city_and_month` remained 0/3 on deterministic output expectations.

## Repair and instrumentation

All 16 recorded repair attempts reconcile with captured model-call counts; 8 repairs succeeded.
The runner recorded 63/63 calls and complete token usage. Cost was not calculated.

## Owner placeholders

- Product-owner interpretation: _Pending._
- Final next cut-line decision: _Pending project owner decision._
