# Holiday-window policy

- **Date:** 2026-08-31
- **Goal for this session:** Classify the baseline holiday-window discrepancy and encode the golden
  behavior in the second-pass policy.
- **User outcome shipped:** The temporal resolver prompt now defines inclusive holiday windows. A
  Monday Labor Day weekend runs Friday through Monday, retaining late-Friday departure options;
  “over Christmas” runs from Christmas Eve through the day after Christmas.
- **Commands and tests run:** `.venv/bin/pytest -q tests/unit/test_openai_extractor.py
  tests/unit/test_eval_cases.py` (10 passed); `.venv/bin/pytest -q` (56 passed);
  `.venv/bin/ruff check src tests` (passed); `.venv/bin/mypy src tests` (passed); focused live
  `gpt-4o-mini` holiday evaluation (four scenarios, three trials, 12 scored runs).
- **Evaluation result:** Offline prompt-contract and corpus-validation tests passed. The focused
  live run did not verify the behavior: 4/12 complete cases passed, 7 failed, and 1 errored. The
  isolated Labor Day pass-2 case was stable at 3/3. The isolated Christmas-weekend case was 0/3,
  the end-to-end “over Christmas” case was 1/3, and the end-to-end Labor Day case was 0/3 on all
  checks (although one trial had the correct holiday boundary and failed only origin normalization).
- **Most instructive failure:** All three isolated “Christmas weekend” runs returned December
  24–26 instead of the focused golden case's December 24–27. The model did not reliably preserve
  the prompt's distinction between “Christmas weekend” and “over Christmas.”
- **Failure classification:** Underspecified second-pass interpretation policy.
- **Trace observation:** The isolated Labor Day second pass consistently returned September 4–7.
  Across completed end-to-end runs, exact holiday-boundary checks passed in two of five trials:
  Labor Day was once correct and once started September 3; “over Christmas” was once correct and
  twice ended December 25. One Labor Day trial failed earlier because pass 1 emitted ungrounded
  anchor evidence `10 days after`.
- **Decision made:** The project owner explicitly selected the golden windows as correct behavior.
- **What Codex generated:** Prompt policy, an offline prompt-contract regression test, ADR wording,
  baseline classification, and this build-log entry.
- **What the project owner changed or rejected:** The owner selected the golden behavior and stated
  that Friday must be included to support late departure searches.
- **Next cut line:** The clarified prompt alone is insufficient. Decide whether to enforce the
  exact golden holiday-window arithmetic deterministically or further revise the model policy,
  then re-run this same focused evaluation.

## Deterministic-policy follow-up

- **Work attempted:** Move recognized holiday-window arithmetic out of the model pass, retain model
  semantic evidence, and rerun the same focused live evaluation.
- **Files changed:** `src/award_agent/intent/temporal.py`,
  `src/award_agent/intent/workflow.py`, `src/award_agent/intent/openai_extractor.py`,
  `tests/unit/test_temporal.py`, `tests/unit/test_openai_extractor.py`,
  `evals/intent/cases.yaml`, `docs/adr/0003-two-pass-temporal-resolution.md`, and
  `docs/project-state.md`.
- **Commands and tests run:** `.venv/bin/pytest -q` (64 passed); `.venv/bin/ruff check src tests`
  (passed); `.venv/bin/mypy src tests` (passed); focused live `gpt-4o-mini` holiday evaluation
  (four scenarios, three trials, 12 scored runs).
- **Evaluation result:** 12/12 live runs passed with no failures or errors, improving from 4/12 in
  the prompt-only run. Labor Day weekend resolved to September 4–7 in every applicable trial,
  “over Christmas” to December 24–26, and “Christmas weekend” to December 24–27.
- **Trace observation:** Deterministic resolution corrected narrower or wider model proposals before
  duration-based return arithmetic. The retained assumption records the authoritative inclusive
  window in the parsed trace.
- **What Codex generated:** Deterministic holiday-policy resolution, explicit preceding-weekday
  flexibility expansion, regression tests, golden-layer reclassification, documentation, and a
  focused post-change live artifact.
- **What the project owner changed or rejected:** The owner selected deterministic enforcement and
  requested that the focused test be adjusted to reflect that responsibility boundary.
- **Next cut line:** Preserve the focused artifact as evidence; expand deterministic holiday-policy
  coverage only when another named convention is explicitly accepted as product behavior.
