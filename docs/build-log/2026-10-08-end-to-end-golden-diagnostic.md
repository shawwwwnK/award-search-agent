# Intent-golden input-to-Results M2 diagnostic

Date: 2026-10-08. The owner requested more examples from the intent golden set,
live execution through Results M2, complete traces and latency/token/cost accounting.
The owner explicitly requested subagents to execute the cases. Selection as a future
full end-to-end golden set remains a later owner activity.

The session continued into October 9. The revised campaign retains its declared
October 8 reference date; its January/February 2027 travel dates remain future dates.

## Declared scope

Use six disclosed complete-request fixtures from
`evals/intent/one_way_award_behavior_cases_v1.yaml`: `ready_whole_month`,
`ready_early_month`, `ready_holiday_window`, `ready_relative_weekend`,
`typo_recognizable_date`, and `mixed_award_cash_eligible`.
The campaign manifest preserves original fixtures and records date/context adaptations
for already-past windows. Adapted cases are diagnostic derivatives, not unchanged
golden-oracle trials. No holdout or newly qualified end-to-end golden set is claimed.

Use existing stage APIs and pinned provider budgets (12 award requests and 3 cash requests
per case). Intent and planning use GPT-5.6 Luna; Results uses the latest October 8
run-specific declared GPT-6 Luna profile, including 32,768 output tokens, a 600-second
authoring timeout and at most one correction. These are campaign inputs, not adopted
model defaults. Raw model/provider evidence stays in locally ignored run directories;
the reviewer index links those local artifacts.

## Implementation and observed diagnostic faults

A standalone runner under `evidence/end-to-end/2026-10-08-golden-diagnostic/`
captures stage contracts, actual SDK request/response envelopes, provider tape/bodies,
Results artifacts and rendered Markdown. No application-runtime change is intended.
Independent execution agents own disjoint cases.

Early runs exposed two runner defects: a planning summary referenced `.status` instead
of `SearchPlanningResult.outcome`, and the clarification session had no prompt composer.
Preserve the affected attempts. SDK instrumentation initially wrapped nested methods
twice; accounting must reconcile unique API responses rather than add those entries.

The typo request exhausted the intent repair allowance and retained no bounded
departure. The mixed-mode request retained an unresolved traveler blocker despite the
explicit original "one". These are observed initial outcomes, distinct from runner
configuration defects. Diagnostic continuations may use the existing fixture's intended
November 27, 2026 date and explicit one traveler, with saved-turn provenance; they must
not replace or be counted as first-pass successes.

## Verification and measurements

The six revised base cases reached Results delivery and replayed exactly. All six
base outputs report zero complete journeys: five compact runs made no award-detail
calls, while the standard business-cabin run returned empty primary award searches.
Three revised initial requests required scripted clarification (MLK weekend, typo,
mixed-mode traveler count); the month windows and explicit business request were
ready with the declared dates. Clean Results outcomes do not erase these intent misses.
Two standard-policy January follow-ups completed on the same saved plans. January 8
produced 0 admitted, 232 conditional and 296 rejected variants; Results selected three
conditional journeys and delivered an annotated answer with five failed checks.
January 15 produced 26 admitted, 232 conditional and 360 rejected variants; Results
selected three intact origin-to-destination award journeys and delivered a clean answer.
All acquired provider sets remain partial. These are one-trial observations, not reliability
qualification. Final composed live-stage latency ranges from 170.976 to 344.618 seconds.

The early-2027 campaign recorded 37 generation calls, 4,071,469 input and 86,231 output
tokens, with estimated generation cost $0.9237738050. This includes retained compact,
invalid profile comparisons and corrected standard runs. Original diagnostics recorded
28 calls, 2,605,572 input and 42,573 output tokens, estimated $0.6203748600.
Combined estimated generation cost is $1.5441486650; exclusions below apply.

A runner profile-switch defect initially reused compact policy under a standard label.
Those two attempts are preserved and excluded from profile comparisons. The runner now
derives either profile from frozen current standard policy. Offline assertions verified
standard 12/3 versus compact 3/1 budgets, idempotence and unchanged request/compiled plan.

Parent verification command:
`PYTHONPATH=src .venv/bin/python evidence/end-to-end/2026-10-08-golden-diagnostic/verify_and_report.py`
inspected **16 retained Results artifacts**. All embedded Results projections match saved
Ranking exports. One verification process replayed 15 exactly; a retained invalid
compact mixed-mode comparison failed receipt equality because incomplete-observation
findings iterate a Python set. An independent process replayed all 16; another reproduced
the failure and confirmed identical finding multisets with two findings in swapped order.
Full verification observed 16 passes in one process and 15 in the final process. Separate
`PYTHONHASHSEED` probes 0 and 3 failed, while 1 and 2 passed, with unchanged finding
multisets; `replay-order-probe.json` preserves this evidence.
This establishes a cross-process nondeterministic receipt-order defect, not a semantic
finding-content difference. Runtime code and saved receipts remain unchanged. All six
latest valid early-2027 outputs replayed exactly in final verification. No blanket exact
replay guarantee follows from these observations.

Ruff and Python compilation passed for the diagnostic utilities; `git diff --check`
passed. No runtime source changes or new behavioral tests were needed for these
standalone diagnostic runners. Earlier loader/composer/instrumentation defects and
their retained failed attempts remain in the session evidence.
Accounting was regenerated with `reconcile.py` and `summarize.py` for each campaign.
Final checks used `.venv/bin/ruff check evidence/end-to-end/2026-10-08-golden-diagnostic`,
`python -m py_compile` on all four runner/report utilities, the parent verifier above,
and cross-process hash-seed replay probes. `git check-ignore` confirmed both raw-run
directories remain locally ignored. Changes comprise the standalone evidence utilities,
manifests, reviewer reports and this log, plus project-state/deferred-register dispositions.
Model generation estimates use per-call published pricing pinned in `pricing-basis.json`.
Token-count endpoint billing, provider charges and failed calls without usage remain
unknown and excluded from any quoted generation estimate. Preserve separate live-stage
latency and offline replay/verification time.

## Owner date steering and revised batch

During the campaign the owner requested early-2027 travel dates, raising the risk that
past fixture dates/reference contexts could limit live acquisition. The revised batch uses
today's reference date (2026-10-08), explicit early-2027 temporal derivatives and preserved
source fixtures. Completed/in-flight original diagnostics remain separate; queued original
supplemental runs are replaced by this revised batch.

The revised batch declares the smaller diagnostic acquisition profile before execution,
on the same full compiled graph: 3 award requests/3 pages/300 rows and 1 cash
request/1 page/100 rows, one direct-cash sample and zero positioning samples. This
changes campaign acquisition coverage, not the application's defaults or planner graph.
The explicit business-cabin/home-airport case retains the standard provider profile
as a coverage contrast. The other five revised cases start with the compact profile.
Compact capacity can be spent before itinerary-detail calls; an empty Ranking/Results
answer under that profile does not establish the absence of live award availability.
Original standard-profile month runs had reached Results but produced no answer:
early-May measured 997,393 input tokens, and whole-May measured 1,445,873, both
exceeding the campaign input ceiling. Their failure artifacts are retained.

The relative-weekend original diagnostic additionally exposed the harness's unresolved
`New York` catalog ambiguity (two matching entities); it stopped before provider calls.
The revised batch uses a different existing complete business-cabin fixture instead;
the original failure is not repaired or erased. The original Seattle–Tokyo holiday
answer passed mechanical Results checks while faithfully reporting an incorrectly
resolved whole-September window. This is an upstream semantic finding, not a clean
end-to-end outcome. Original typo and relative-weekend/mixed continuations remain
explicitly scripted diagnostics rather than first-pass successes.

## ADR and deferred-work disposition

Read ADR 0028, the ADR index, current project state, the deferred register and relevant
workbook trace/evaluation sections. No new ADR is needed for this diagnostic: existing
stage ownership, eligibility, provider budgets, Results correction/check policy and
evaluation qualification boundaries remain unchanged. The concurrent October 8 owner
Results M2 closeout is recorded in current project state; these diagnostics add evidence
without changing that disposition. They do not open M3, select a new golden set or establish task benefit/provider
reliability. The owner has not supplied a final assessment or next cut.
