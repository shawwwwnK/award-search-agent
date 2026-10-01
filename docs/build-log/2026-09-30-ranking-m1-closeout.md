# 2026-09-30: Ranking M1 owner closeout

## Owner decision

After reviewing whether `sfo_to_bkk_positioning` satisfied the M1 closeout criteria, the owner
explicitly instructed “Close M1.” The declared matching/validation boundary is owner-qualified
and closed, retaining the current award-only cabin interpretation for separate cash positioning.
No M2 weights, broader topology, expanded acquisition dates, or Output Stage opening were approved.

## Objective evidence and changes

- Read the project state, deferred register, Ranking Stage design and closeout criteria,
  September 25/27 build logs, saved matching README, relevant workbook sections, and M1 tests.
- Ran `.venv/bin/pytest -q tests/unit/test_ranking_m1.py tests/unit/test_ranking_m1_corpus.py
  tests/unit/test_ranking_m1_cli.py`: **35 passed in 6.32 seconds**.
- Called `award_agent.cli.ranking_match.main` from `.venv/bin/python` using each saved run's
  bundle/result and temporary outputs; byte comparisons passed for `mixed_access`,
  `exact_business`, and `sfo_to_bkk_positioning`. No live provider or model calls were made.
- Reproduced distributions: 17/240/216/0 for `mixed_access`, 0/106/290/0 for
  `exact_business`, and 5/59/58/1 for `sfo_to_bkk_positioning`
  (admitted/conditional/rejected/research lead). All 975 mixed pairs remain accounted for.
- Added the M1 closeout handoff and updated `AGENTS.md`, `docs/project-state.md`, the Ranking
  Stage design record, `DEFERRED.md` (including D15 and dated disposition), and the saved
  matching README. Runtime, tests, and saved JSON evidence are unchanged.
- `git diff --check` and local-link checks for both new closeout documents passed.

## Limits

Acceptance is for the declared M1 boundary. Conditional access options, incomplete prices,
partial provider coverage, and unverified bookability remain explicit. Broader provider
reliability and full-workflow usefulness are unclaimed. M2 and Output Stage remain later work;
D15's wider topology and D18 remain parked.
