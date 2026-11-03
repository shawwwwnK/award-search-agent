# Results M2 fast-profile handover — stopped at V30

Recorded 2026-10-29. **Start a new session from this document.** The owner's latest
instruction is to stop implementation and hand over the work, with the main
iteration cycles documented through V30. This closeout changes documentation
only. No V31, new live calls, runtime changes or default promotion follow from it.

## Current outcome and working tree

The campaign did not produce a qualified default or close the current Results M2
revision. The public API/CLI is provisionally wired to **`focused-v27`**; the latest
opt-in experiment is **`focused-v30`**. These are different states: latest does not
mean default, and default wiring does not mean quality acceptance. The Streamlit
harness retains its historical route. Frontend milestones and M3 remain separate.

The owner's committed starting point is
`b7bedf5b13daab0ec0d170ba0b519877698ae0ff`. The subsequent work is uncommitted,
including substantial untracked source, tests, data, evidence and documentation.
Preserve it all. No commit is requested by this handover. Begin with `git status`
and the current project state; do not reset to the checkpoint or discard failed
experiments. This is local development, with no external deployment.

## Owner decisions to carry forward

- Keep Luna and its natural wording. The proposed inline comparison-clause binding
  was rejected after the offline prototype. Ordinary numerical prose remains
  model-authored under the existing trust policy; no claim of exhaustive checking.
- Retain Ranking's time-focused, cost-focused and premium-cabin categories, including
  overlapping memberships and multi-style highlights. Results explains Ranking's
  recommendations; it does not introduce another ranking policy or overall score.
- Limit the full-origin-to-destination cash benchmark to **one brief comparison
  sentence**. For example, a source-supported SFO–BKK USD440 quote via Singapore
  can be mentioned with its actual uncertainty. Do not imply other connecting
  cities share that quote. Extended cash schedules and prominent answer cards
  distract from the award-first tool's value. Cash access/egress within an
  award-led journey still needs relevant cost and separate-ticket explanation.
- Keep a complete, useful traveler answer and the independent complete explorer.
  The latency goal is approximately 20 seconds, with a small overage acceptable;
  measure the complete checked workflow, including input counts and actual repair.
- Prototype questions C/D are withdrawn as superseded by the category direction.
  Do not ask them again, infer a new lead-ranking policy, or change old grades.

These accepted decisions are recorded in [ADR0029](../adr/0029-structured-results-and-local-workspace.md).
Their runtime implementation is pending. The owner's final instruction explicitly
stops implementation in this session.

## Main iteration cycles through V30

All timings below are saved Results workflow measurements, not an application SLA.
H means factual correctness, U useful next action, M2 complete traveler composition,
and C comparative depth. A mechanical pass does not establish a source-review pass.

| Cycle | Design tested | Evidence and disposition |
| --- | --- | --- |
| V3 checkpoint | Two Luna calls: NONE selector over full inventory, LOW composer over selected exact facts; no correction. | Six frozen runs 6.72–8.46s, median7.63; usefulness6/6, facts5/6, all C-basic. Fast baseline, insufficient quality. |
| V4–V7 | Restore bounded correction and fuller answer structure; improve source roles, selected facts and quote handling. | Faster samples around10–17s, higher-effort cases21–28s. Unsupported scope/comparisons remain; no adoption. |
| V8–V10 | Unconditional full-answer editorial revision. | V8 23.39/23.94/17.20s; repairs some errors but adds latency. V10 still assigns a40-minute elapsed difference to a730-minute arrival difference at23.83s. |
| V11–V16 | Optional exact temporal comparison cards, stronger identity and selection-purpose guidance, effort changes. | Promising scouts fail fresh cohorts: V11 H3/6, V13 H4/6, V16 H5/6 with one M2 failure and one C-basic. Correct cards coexist with wrong surrounding prose. Selector purpose text can itself hallucinate. |
| V17–V22 | Atomic editorial patches; remove selector-purpose prose downstream; add exact pair dossiers, canonical party evidence and a bounded authoring pool. | More source structure does not guarantee correct narrative binding. V19 has two clear factual passes and one disputed party statement; incomplete remains basic. V21 39.22/27.52/17.76s fails. V22 initial and edited answers all pass source/composition/depth review, but final31.06/20.96/26.93s is too slow. |
| V23 | Retain V22's exact first two requests; replace unconditional editor with one LOW full-document correction only on actual recoverable mechanical findings. | Strongest full cohort: six fresh runs7.62–17.68s, median11.22; H/U/M2 6/6, C-rich5/6. q095 is basic, so combined gate fails. Controlled conditional correction18.73s passes review. |
| V24–V27 | Incomplete-only lossless named records and effort allocation changes, ending with MED selector/MED author for incomplete; complete remains V23. | Scouts improve some comparisons, with preserved review/adjudication disagreements. V27 fresh six:10.21–22.14s, median11.58; H3/6, U/M2 6/6, C-rich5/6. Errors include false earliest arrival, mixed points/fee endpoints and reversed cash arrival. Controlled repair26.23s passes quality but misses latency. |
| V28 | At most two non-benchmark references plus one benchmark; complete NONE/MED, incomplete MED/LOW. | Admitted17.90s passes richly; conditional NONE selector loops until API-incomplete at44.78s; incomplete10.62s is basic. Explicit failure preserved, no salvage/retry. |
| V29 | Complete LOW/MED; incomplete MED/LOW with lossless program-grouped378 leads across13 programs. | Scouts18.80/13.16/11.05s, H/U/M2 all pass, C-rich2/3. Grouping preserves exact records but cannot guarantee sound cross-program comparisons. |
| V30 | Complete branch identical to V29; incomplete selector explicitly distinguishes program units and requires a supported offsetting benefit. | Admitted16.383s, conditional12.294s, incomplete11.059s; all clean two-call H/U/M2 passes. Only admitted q119 is C-rich. q120 has generic later-arrival preference without offset; q121 discusses one lead despite378 records. Scout gate fails. No frozen confirmation or V30 repair diagnostic. |

The V27 first confirmation attempt also suffered a post-save harness `NameError`.
Its artifact/error and q107 review remain preserved; the failed attempt was not
replaced in place. The fixed cohort used a new manifest. Do not silently omit it.
V23's strong cohort does not establish reliability: later complete-path errors
occurred without a new complete-path design.

The [campaign README](../../evidence/results-stage/m2/structured/2026-10-28-fast-default/README.md)
contains the per-profile matrix and links to original blind reviews and separate
adjudications. The [chronological build log](../build-log/2026-10-28-results-fast-default.md)
records each accepted experiment, implementation, call budget and observed failure.

## Why correction disappeared, and what came back

V3 removed the correction call for a minimal fast two-pass path. Subsequent cycles
restored correction and also tested unconditional editorial passes. The late path
keeps **one conditional correction**, triggered by actual recoverable mechanical
findings, not every answer. Clean drafts finish after selector and author. There
is no fourth generation or SDK retry. Correction receives frozen selected facts
and recomputed findings; fewer mechanical failures wins, with correction winning
ties. Explicit failure evidence survives unsuccessful recovery.

This guardrail cannot catch every wrong model-written comparison. A source-review
failure can occur in a mechanically clean two-call answer and never trigger repair.
The measured controlled repairs are V23 18.73s and V27 26.23s; V30 repair latency
is unmeasured. Unconditional editors often added latency without a quality gain.

## Why the Ranking categories disappeared from the answer

The categories were not deleted upstream. They survived as data but stopped being
an authoring requirement. `interactive_packet.py` retains per-journey style states
and global Ranking indexes. `focused_packet.py` restricts the writer's pool to
selected journeys. `focused_records.py` keeps selected style facts but omits global
`ranking_hints`. Selector and writer briefs favor a generic defensible choice and
alternatives without requiring the category landscape to survive selection.
The writer cannot recover a premium option that selection omitted.

Saved q108/q119 full source contains11 time members,116 premium members and0 cost
members; these are journey variants, not116 distinct flight discoveries. q119 shows
two time-member economy options plus cash, omitting premium. The existing C review
did not flag that category omission. The offline prototype held those historical
selected pools fixed, so it also could not restore the missing category.

Consult the [Ranking styles contract](2026-10-01-ranking-m2-styles-contract.md):
time is within120% of the shortest whole journey; cost within200% of the lowest
sufficiently complete heuristic cost; premium means business/first award component,
with premium economy separate. Preserve possible/undetermined cost states and
multi-style highlights. The fixed point heuristic is an owner preference, not a
market valuation. Cash-only benchmarks and incomplete research leads are not style
members. No complete journey means truthful supported leads, not invented styles.
The later two-option ceiling is an engineering experiment, not Ranking policy;
it must not silently erase meaningful available category perspectives. A fixed
one-per-category rule is also not an accepted replacement.

## Proposed next session work — not implemented

When the owner resumes implementation, focus on **Ranking category → selection →
explanation**. Reconcile the authoring contract and acceptance examples first.
Preserve enough global category availability and membership information through
selection and composition to explain useful representatives and overlaps without
inventing Ranking decisions or duplicating cards. Apply the single-sentence cash
rule with exact source identity; existing benchmark-reference/coverage checks may
need a versioned adjustment so they do not force a full cash card back into prose.

Retain factual review as a hard gate. Add explicit category-faithfulness evidence;
do not substitute a new lead-ranking policy or universal decorative tradeoff
requirement, and do not retroactively regrade the old campaign. First correct the
four known verifier assumptions below with positive/negative controls. Then freeze
one controlled hypothesis and a prospective bounded campaign, with genuinely new
source cases and cache-aware complete latency measurement, including natural repair
costs. The old three-case repeated campaign and unused budget are not a reason to
resume a profile ladder automatically. No V31 is authorized by this handover.

## Evidence limits, review debt and verification

The closed ledger contains254 generation and254 input-count reservations under
an engineering cap278/278, leaving24 unused. There were no travel-provider calls,
FX calls or SDK retries. Three saved source archetypes were reused repeatedly;
call count is not task diversity. Warm/cold cache differences confound comparisons.

[Strict verification](../../evidence/results-stage/m2/structured/2026-10-28-fast-default/verification-v30-final.json)
exited1 with seven flags. A [read-only audit](../../evidence/results-stage/m2/structured/2026-10-28-fast-default/verification-v30-audit.json)
classifies them as four verifier assumption bugs: wrong injected-fault identity;
valid one-pass API-incomplete handling rejected; incomplete-only V30 instructions
required on the unchanged complete branch; and a valid empty comparison-pair list
rejected when only one lead plus benchmark was selected. These are not fixed.
All109 summarized artifacts reached exact replay and matched; the additional
aborted post-save V27 artifact was replayed separately. Strict gate remains red.

The [whole-change review](../reviews/2026-10-28-results-v30-change-review.md) found
no hard standards breach, two maintainability concerns (repeated profile switches
and duplicated measurement/error scaffolding), and four substantive gaps: factual
acceptance, comparative depth, correction latency and verifier contract mismatch.
No full-repository pass is claimed. Earlier Results434 tests passed before V24;
later profiles had scoped tests, final source/CLI mypy43-file and Ruff checks.
Two earlier full-suite gfly environment failures remain recorded; provider code
was not changed. Do not convert these checks into a current all-green claim.

The [offline prototype log](../build-log/2026-10-28-results-offline-comparison-prototype.md)
and [owner-direction log](../build-log/2026-10-29-results-ranking-led-direction.md)
record the advisor proposal, critique and rejection. Hand-authored paired answers
and synthetic clause controls prove no model quality or latency improvement.
Read these entry points before opening large source archives. Preserve exact
requests, responses, source/config archives, failure receipts and original grades.

## Implementation map and boundaries

`results/default.py` owns public default dispatch and shared-client lifetime;
`focused.py` dispatches profiles and replay. `focused_comparison_runtime.py` owns
the late conditional-correction path; `focused_patch_runtime.py` holds historical
atomic-editor paths. Packet/record/selection modules own source projection;
`focused_comparison_wire.py` owns authoring guidance. `comparison_registry.py`,
pair dossiers and traveler evidence supply facts without proving surrounding prose.
The campaign-local harness and verifier are separate from product runtime.

Do not reopen upstream request, planning, provider or Ranking policy. No new travel
searches, live FX, frontend implementation, M3 qualification or commits are implied.
[Project state](../project-state.md), [Results contract](../results-m2.md),
[ADR index](../adr/README.md), and [deferred register](../../DEFERRED.md) retain
those boundaries. The October8 closeout remains historical to its declared scope;
this later revision still needs acceptance and must not be declared closed here.
