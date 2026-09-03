# Pass 2-only model experiment: focused corpus

- Date: 2026-09-02
- Pass 1 model: `gpt-4o-mini`
- Pass 2 model: `gpt-4o`
- Evaluator contract: schema v3, unchanged
- Trials: 3 across 8 unchanged focused scenarios (24 runs)
- Artifact: `2026-09-02-gpt-4o-pass2-only-focused-3-trials.json`

The evaluator split is optional and evaluation-only. Production behavior remains one configured
model for both passes unless a caller explicitly supplies separate evaluators.

## Comparison

| Measure | All-mini Pass 2 contract | `gpt-4o` Pass 2 | Delta |
| --- | ---: | ---: | ---: |
| Passed / failed / error | 9 / 7 / 8 | 13 / 5 / 6 | +4 / -2 / -2 |
| First-attempt completion | 10/24 | 11/24 | +1 |
| Final completion | 16/24 | 18/24 | +2 |
| Repair attempts / successes | 16 / 8 | 14 / 8 | -2 / 0 |
| Total latency | 141.726 s | 235.299 s | +93.573 s |
| Total tokens | 245,758 | 237,095 | -8,663 |
| Captured calls | 63 | 62 | -1 |

Both runs use the same focused corpus and expectations. They are independent stochastic samples,
not paired outputs.

## Case movement

- `relative_date_expression`: error 2/pass 1 → pass 3/3. The stronger Pass 2 model consistently
  associated evidence with the correct target.
- `return_weekend_after_departure`: pass 2/error 1 → pass 3/3 in this focused sample.
- `whole_month_with_exact_duration`: pass 3/3 in both candidates.
- `missing_origin`: pass 3/3 in both candidates.
- `approximate_duration`: error 3/3 in both; dependency and unconsumed-claim failures remain.
- `unbounded_after_new_year`: error 3/3 in both; the stronger model still selected an invalid
  reference relation or unresolved dependency.
- `labor_day_thursday_flexibility`: failed 2/error 1 → failed 3; completion improved but the
  deterministic expectation still failed.
- `tentative_city_and_month`: failed 3 → failed 2/pass 1.

## Interpretation

This is evidence that Pass 2 model capacity, not only schema wording, contributes to evidence-target
association and dependency selection. It does not establish that `gpt-4o` should replace `gpt-4o-mini`:
the sample is small, latency increased 66%, and three high-frequency failure families were unchanged.

## Owner placeholders

- Model-quality/cost interpretation: _Pending._
- Production model-selection decision: _Pending project owner._
- Next experiment cut line: _Pending project owner decision._
