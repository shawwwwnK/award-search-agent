# Ranking M2 factual solution-export implementation

Date: 2026-10-04. Status: **implemented, offline verified and independently reviewed for the declared export boundary**.

## Owner direction

The owner approved moving reusable Results M1 factual preparation into Ranking M2, requested
documentation updates and implementation with subagents/reviews, and clarified: “Basically finish
the ranking stage with this roped in”. Results Stage M2 remains the next step; no Results runtime
was implemented. The owner had already settled that verified same-project upstream input is trusted.

## Implementation

Added `ranking/projection_contracts.py` and `project_solutions.py`, exposing
`project_solutions(RankedJourneySet) -> SolutionProjection(view, receipt)` from the ranking package.
The pure exporter shares observation, reason, cost-component, cost and style-decision records.
It preserves all candidate identities, source quote scopes, conditions, elapsed/transfer facts,
booking obligations, comparisons, planning notes and provider coverage/findings. Source receipts
retain technical provenance and original local-time strings. Existing matching/style calculation
and ranked contracts were not changed.

Added the immutable-output `award-ranking-solutions` CLI, entry point, corpus generation/replay
script and three focused test modules. Saved all three exports and their hash/measurement index in
`evidence/ranking-stage/m2/solutions/`. Updated AGENTS, project state, deferred dispositions,
Ranking contract/closeout and Results design/plans to reflect the new boundary.

## Orchestration and review

An architect defined/reviewed the contract and performed independent read-only implementation
review. An investigator pinned literal source oracles. An implementer owned the production
projection; a separate implementer owned preservation tests. A worker implemented/tested the CLI
and then corpus integration tests. The parent integrated documentation, corpus tooling and evidence.

Initial development exposed Decimal hashing and receipt-set comparison failures, corrected before
the final gate. Independent review identified and verified fixes for omitted planned route/date
context, logical-versus-physical batch scope, missing discovery/provider/transport limitations,
reported flight numbers, receipt associations, corpus newline hashes and pre-publication mutation
checks. Measured repetition prompted normalized cost-component factoring and moving technical
candidate links to receipts. Final review reported no remaining Critical/Important findings.
See the [review record](../reviews/2026-10-04-ranking-m2-solution-export-review.md).
A separate final read-only documentation pass confirmed local links, saved hashes/byte counts and
stage scope. It found two stale Results milestone statements; the parent corrected them and the
reviewer confirmed the inconsistency was resolved. No remaining documentation issue was reported.

## Verification actually run

```sh
.venv/bin/python -m pytest -q tests/unit/test_ranking_solution_projection.py tests/unit/test_ranking_solutions_cli.py tests/unit/test_ranking_solution_corpus.py
# 28 passed in 21.49s

.venv/bin/python -m pytest -q tests/unit/test_ranking_m1.py tests/unit/test_ranking_m2.py tests/unit/test_ranking_m2_corpus.py tests/unit/test_ranking_m2_cli.py tests/unit/test_ranking_m2_script.py
# 62 passed in 94.85s

.venv/bin/ruff check src/award_agent/ranking/projection_contracts.py src/award_agent/ranking/project_solutions.py src/award_agent/ranking/__init__.py src/award_agent/cli/ranking_solutions.py scripts/ranking_solution_corpus.py tests/unit/test_ranking_solution_projection.py tests/unit/test_ranking_solutions_cli.py tests/unit/test_ranking_solution_corpus.py
# All checks passed

.venv/bin/mypy --follow-imports=silent src/award_agent/ranking/projection_contracts.py src/award_agent/ranking/project_solutions.py src/award_agent/cli/ranking_solutions.py
# Success: no issues found in 3 source files

.venv/bin/python scripts/ranking_solution_corpus.py --output-dir evidence/ranking-stage/m2/solutions
.venv/bin/python scripts/ranking_solution_corpus.py --output-dir evidence/ranking-stage/m2/solutions --verify
# All three generated and verified with matching bytes, hashes, round-trip and index
```

`git diff --check` was also run. Independent reviewer separately ran 28 tests and mutation/round-trip
probes. No live model/provider evaluation, broad whole-repo typecheck or fresh-install qualification
is claimed. Pre-existing evaluation-audit changes were preserved. No commit or push was requested
during this implementation session; the subsequent owner-directed commit/closeout is recorded in
[the transition log](2026-10-04-ranking-close-results-m2-open.md).

## Evidence and remaining limits

All 992 candidates and 427 eligible complete alternatives are accounted for (257/106/64 by case).
The tests preserve the literal Aeroplan USD 196/29h50 versus USD 290/27h30 variants, conditional
fastest journey, local/UTC schedules, unknown costs, zero/missing fees, positive synthetic cabin and
flight-number evidence, provider failures and overlapping coverage distinctions.

Compact view sizes are 2,011,912 / 1,302,037 / 654,408 bytes; full artifacts with receipts are
3,911,674 / 2,502,403 / 1,267,942 bytes. No tokens or authoring-context fit were measured. Full
excluded records remain; no silent cap is used. Host timezone data is unpinned, so cross-host
regeneration equality is unqualified. All saved cost references remain absent and coverage partial.

The declared Ranking implementation now includes matching, styles and this factual export. The
next cut is Results M2 authoring preparation/implementation, followed by M3 evaluation. Existing
owner-qualified boundaries retain their original scope; this log records engineering evidence,
not invented owner semantic acceptance or broader bookability/provider/task-benefit conclusions.
