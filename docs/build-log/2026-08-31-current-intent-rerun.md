# Current intent workflow rerun

- **Date:** 2026-08-31
- **Goal for this session:** Rerun the full ready intent corpus and identify which historical
  failures are solved by the current workflow and current golden policies.
- **Work attempted:** Ran all 16 ready scenarios for three live `gpt-4o-mini` trials and compared
  scenario-level outcomes with the original three-trial baseline.
- **Files changed:** Added
  `evals/intent/baseline/2026-08-31-gpt-4o-mini-current-3-trials.json`; updated
  `evals/intent/baseline/2026-08-31-gpt-4o-mini-3-trials-summary.md` and
  `docs/project-state.md`; added this build-log entry.
- **Commands and tests run:** `.venv/bin/python -m pytest -q` (65 passed);
  `.venv/bin/python -m award_agent.cli.intent_eval --model gpt-4o-mini --trials 3 --output
  evals/intent/baseline/2026-08-31-gpt-4o-mini-current-3-trials.json`.
- **Evaluation result:** 48 runs: 30 passed all automatic checks, 16 completed with failed checks,
  and 2 raised explicit grounding errors. The run-level pass rate was 62.5%, compared with 29.2%
  in the historical artifact.
- **Solved under current checks:** `labor_day_thailand`, `missing_origin`,
  `multiple_destination_options`, `adversarial_schema_instruction`, `unbounded_after_new_year`,
  `whole_month_with_exact_duration`, and `tentative_city_and_month` passed all three trials.
- **Stable passes:** `exact_dates_and_cabin`, `approximate_duration`, and
  `early_month_with_approximate_duration` remained three-for-three.
- **Remaining failures:** `labor_day_thursday_flexibility`,
  `return_weekend_after_departure`, `relative_date_expression`, `conflicting_dates`, and
  `repositioning_allowed` passed no trials. `missing_travel_period` regressed from three passes to
  zero because all runs proposed `Los Angeles International Airport` for `LAX`; one run also
  invented one traveler.
- **Trace observation:** The deterministic holiday policies eliminated the Labor Day Thailand and
  Christmas-window failures. The remaining clarification failures were downstream of invented
  return timing, discarded conflicts, or omitted Europe. The two errors continued to demonstrate
  explicit rejection of non-verbatim Thursday evidence rather than a success-shaped fallback.
- **Decision made:** [Project-owner interpretation pending.]
- **What Codex generated:** The live rerun artifact, scenario comparison, and this objective build
  log.
- **What the project owner changed or rejected:** [Project-owner input pending.]
- **Next cut line:** [Project-owner selection pending after review of remaining failures and the
  `LAX` candidate-policy mismatch.]

## Airport-code follow-up

The project owner subsequently selected deterministic preservation of explicit airport codes. The
`missing_travel_period` scenario passed all three focused live trials after that change. See
`2026-08-31-airport-code-preservation.md`; the five other unsolved scenarios remain the next review
set.
