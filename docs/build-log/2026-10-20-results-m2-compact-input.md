# Results M2 compact writer input — 2026-10-20

## Objective

Implement the owner-authorized compact model-facing Results input, preserve all
eligible choices and canonical evidence, group equivalent reported facts while
retaining member identity, and complete the bounded Luna diagnostic described in
the [plan](../plans/2026-10-20-2238-perf-compact-results-input-plan.md).

## Scope and policy

The [2026-10-20 ADR 0026 amendment](../adr/0026-model-authored-results-with-bound-facts.md#2026-10-20-amendment--compact-model-facing-input)
records the accepted representation policy. The full canonical projection remains
local; every admitted and conditional option remains individually selectable;
rejected rows are represented by source-backed summaries; and conservative groups
retain each member's short reference, retrieval timestamp and source binding. The
bounded live diagnostic is limited to three saved cases, at most three initial
generations plus three corrections, at most six associated count requests, no
provider calls and no automatic reruns. It is diagnostic evidence, not qualification.

## Objective development evidence

- The compact authoring view is implemented in `src/award_agent/results/authoring.py`
and integrated into the Results contracts, request measurement, generation, artifact
binding and replay paths. New runs use `results-artifact-v5` / `results-prepared-v4`;
historical versions retain their original semantics.
- The frozen source snapshot is
  [source-snapshot.json](../../evidence/results-stage/m2/compact-input/2026-10-20-luna/source-snapshot.json)
  with a matching [zip archive](../../evidence/results-stage/m2/compact-input/2026-10-20-luna/results-source-snapshot.zip).
  The evidence bundle also includes the independent [field disposition](../../evidence/results-stage/m2/compact-input/2026-10-20-luna/field-disposition.md)
  and offline probes; these are separate from the source-code archive.
- The independent preservation probe compared canonical sources and receipts to V5
  preparation for all three saved cases: 258/258 and 232/232 eligible aliases survived;
  all 360 and 296 rejected rows were summarized; all incomplete leads and benchmarks
  were retained. It checked member facts and timestamps, comparison scope, costs and
  dispositions, with no failed checks. Negative controls confirmed differing source
  hashes split groups, missing local times remain distinct, USD 135 and USD 176 flights
  with the same schedule stay separate, and no 64-hex IDs appear in writer inputs.
  See [preservation.json](../../evidence/results-stage/m2/compact-input/2026-10-20-luna/offline/preservation.json)
  and [negative-controls.json](../../evidence/results-stage/m2/compact-input/2026-10-20-luna/offline/negative-controls.json).
- Complete initial request JSON byte counts changed as follows:

  | Saved case | Previous | Compact | Reduction |
  | --- | ---: | ---: | ---: |
  | Admitted | 2,421,717 | 868,610 | 64.13% |
  | Conditional | 2,144,234 | 784,268 | 63.42% |
  | Incomplete | 846,934 | 574,989 | 32.11% |

  Representative correction JSON fell from 2,427,975 to 873,514 bytes (64.02%),
  2,154,629 to 791,001 bytes (63.29%), and 846,934 to 574,989 bytes (32.11%),
  respectively. The accounting includes full token-bearing JSON with instructions
  and response schema. These are bytes, not measured compact-request token counts.
  Component breakdown and hashes are in
  [offline-measurement.json](../../evidence/results-stage/m2/compact-input/2026-10-20-luna/offline-measurement.json).
- Pre-change baseline: **121 Results tests passed in 46.19 seconds**; mypy passed for
  five files (parent-observed). Post-change Results suite: **143 passed in 61.91 seconds**
  (implementer-observed); harness integration: **11 passed**. Parent-observed Ruff for
  changed paths and mypy for eleven files passed. Independent code review ran **26
  focused tests, all passed in 13.91 seconds**, and found no runtime defect. These
  results establish the recorded scoped checks, not a completed repository-wide test run.
- The repository-wide run before the narrow post-live fix used `PYTHONPATH=src:. .venv/bin/pytest -q` and
  completed with **878 passed, 99 skipped, and two failed** in 528.38 seconds. The
  failures are the two known gfly environment compatibility tests documented in the
  [October 7 Results implementation log](2026-10-07-results-m2-implementation.md#verification):
  the local pinned interpreter/dependency environment is incomplete. An initial plain
  `pytest -q` attempt failed during collection because the repository root was absent
  from the import path; the explicit `PYTHONPATH` run is the completed result. Do not
  claim the repository-wide suite passed.
- A later focused Results-plus-evaluation run completed with **148 passed in 61.19
  seconds** before the narrow post-live replay fix. After that fix, the post-fix
  Results suite passed **146 tests in 70.08 seconds**. Parent-observed
  Ruff on changed paths and mypy on eleven files passed. The final combined
  Results/evaluation/harness command
  `.venv/bin/pytest tests/unit/test_results*.py tests/unit/test_compact_results_eval.py tests/unit/test_harness_pipeline.py tests/unit/test_harness_workflow_ui.py -q`
  passed **162 tests in 172.36 seconds**. Final mypy on eleven files and scoped Ruff
  over changed source/scripts/new tests passed. The broad repository suite above ran
  before the narrow post-live core change; do not describe it as a post-fix full-suite
  pass.
- The bounded live diagnostic completed across all three cases with **five generation
  calls and five count calls**, all using `gpt-6-luna`; total writer usage was **843,051
  input and 21,591 output tokens**. There were no provider calls or automatic reruns.
  See the run's [README](../../evidence/results-stage/m2/compact-input/2026-10-20-luna/README.md)
  and authoritative [summary](../../evidence/results-stage/m2/compact-input/2026-10-20-luna/summary.json)
  for per-case receipts and comparisons. Iteration 006 comparisons use the Sol baseline
  and are not controlled; the same-projection Luna comparison is also from an earlier
  prompt/source version. No dollar amount is asserted because current rates and an
  invoice were not verified.
- Independent answer review found no unsupported positive claim of present availability,
  protected connection, per-leg cabin or party-wide price. It did find visible utility
  issues: conditional output ends annotated with two shared-binding key findings and
  selects two economy feeder variants around one shared award while a business-cabin
  option remains in the canonical pool; incomplete output omits points units/program
  names and has awkward or malformed schedule text. The admitted answer usefully
  explains a calendar-arrival tradeoff. Review evidence is in the run README; this is
  diagnostic judgment, not qualification or causal attribution to compaction.
- The original cross-seed probe found the new V5 incomplete artifact failed at hash seed
  37 with a saved check-receipt mismatch. A narrow deterministic V5 traversal fix changed
  only `src/award_agent/results/core.py` after the live run. The post-fix report replays
  seven artifacts (new V5 admitted/conditional/incomplete and saved V1–V4) successfully
  at seeds 11, 23 and 37. The request-integrity report confirms all five live requests
  and artifact SHA values are unchanged and records zero paid calls. The exact post-live
  source is preserved in the replay-fix manifest/archive. Independent architect review
  confirmed tampered or reordered findings remain rejected. This resolves the new V5
  seed-37 defect. The older finding-order concern documented in the October 8 end-to-end
  diagnostic remains separate and is not claimed resolved for historical artifacts.
- This documentation reconciliation ran `git diff --check` over the tracked docs.
  It did not run tests or live calls.

## Remaining review and disposition

**Offline verification, bounded Luna diagnostic and V5 post-fix replay:** completed for
this record and linked above. No new baseline generation calls or paid reruns were made.
Input bytes, actual writer tokens, model comparisons, mechanical outcomes, answer-review
findings and historical replay limits are kept separate in the evidence.

**Evidence limits:** distinguish the byte reductions above from actual compact-run
model token counts. Do not call the bounded diagnostic M2 or M3 qualification and do
not infer owner acceptance. The full repository suite's two gfly environment failures
predate the narrow post-live code fix; no full-suite rerun after that fix is claimed.
Presentation acceptance and owner interpretation remain pending.

## Commit scope

The current-branch change includes the pre-existing uncommitted V4 Results
presentation prerequisite and its frozen presentation evidence, which the new V5
compatibility checks and saved-source evaluation depend on. Their original data
and live receipts are preserved. The new compact implementation, tests, plan,
documentation and diagnostic evidence are included. Unrelated pre-existing
golden-diagnostic campaign files remain outside this commit.

The owner subsequently requested committing and pushing the implementation and
proper documentation. The implementation/evidence commit is `693517b`. A follow-up
documentation check corrected the ADR index's relative link to the compact-input
evidence. This link-only correction changes no policy and needs no new ADR; the
existing ADR 0026 amendment remains the decision record. Local link resolution and
`git diff --check` were checked before the follow-up commit; no additional live
calls or code tests were needed for this documentation-only change.

## ADR disposition and owner interpretation

ADR 0026 was amended for the accepted compact writer-input policy; the index and
affected contracts/state were updated. This log records no additional product
decision. **Owner interpretation and next cut line:** pending owner review.
