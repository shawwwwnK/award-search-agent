# Luna fast Results M2 campaign

For new-session navigation, read the [V3–V30 cycle summary and October29 owner
direction](../../../../../docs/handoffs/2026-10-29-results-m2-fast-profile-handover.md).
The owner stopped implementation. Luna wording and Ranking categories are retained;
inline binding is rejected and full-cash context becomes one brief sentence.
These accepted changes are pending runtime implementation; old grades stay intact.

## Final status (2026-10-28; stopped at V30)

Live iteration stopped at V30 as requested. No V30 frozen confirmation or actual
correction diagnostic was run because its three-scout quality gate failed. No more
paid calls are authorized in this campaign. The latest experiment is opt-in
`focused-v30`; the public API/CLI default remains provisionally `focused-v27`.
No candidate qualified as the default, and this work does not close Results M2.
The entire work-in-progress was [reviewed](../../../../../docs/reviews/2026-10-28-results-v30-change-review.md)
against checkpoint `b7bedf5`; all code remains uncommitted.

V30 retains V29's incomplete-only lossless view of 378 leads grouped by 13 programs.
It selects at most two non-benchmark references (journeys or leads) plus one
benchmark (three total): complete cases
use LOW selection and MEDIUM authoring with `roles-v28/complete-v26`; incomplete
cases use MEDIUM selection and LOW authoring with `roles-v30/complete-v28`.
Correction remains one LOW full-document call only after actual recoverable
mechanical failures. The source pool is not filtered or ranked by code.

The three fresh scouts took 16.383, 12.294, and 11.059 seconds for admitted,
conditional, and incomplete cases respectively; each was a clean two-call run.
q119 passed H/U/M2 with rich depth. q120 passed H/U/M2 but was basic: a generic
later-arrival preference had no offsetting gain. Positioning permission was not
explicitly restated; the source reviewer recorded uncertainty, not a proven factual
contradiction. q121 passed H/U/M2 but was also basic: it discussed one United lead
without comparing it to another lead despite 378 available source records. See
[q119](review-bundles/q119/review.md), [q120](review-bundles/q120/review.md), and
[q121](review-bundles/q121/review.md). The combined gate failed, so no
confirmation or recovery call followed.

V29 scouts passed H/U/M2 in all three cases, with rich depth in two of three;
times were 18.80, 13.16, and 11.05 seconds. V28's NONE-selector output loop failed at
44.78 seconds, with all source reviews preserved. Earlier V27 confirmation had
H 3/6 and its controlled correction took 26.23 seconds; V23 remains the strongest
full confirmation cohort, with H/U/M2 6/6, C-rich 5/6, and 7.62–17.68 second
latency (median 11.22), but its gate failed on q095's basic depth. Its separate
conditional correction diagnostic passed review in 18.73 seconds. No experiment
qualified for default promotion.

The ledger records 254 generation and 254 input-count reservations under a
278/278 cap; 24 slots remain unused. There were no provider or FX calls and no
SDK retries. [Strict verification](verification-v30-final.json) exited 1 with seven flags.
A [read-only audit](verification-v30-audit.json) classifies them as four verifier
bugs: wrong fault identity, valid one-pass failure handling, incomplete-only
guidance required for complete cases, and a valid empty pair list rejected. All109
summarized artifacts reached replay and matched. The extra persistence-failed run
is separately preserved and replayed in q107. The strict gate remains red; no
verifier or runtime fix followed the stop. The owner-set cap was V30 followed
by a whole-change review; no V31 is authorized.

The engineering gate requires every frozen answer to pass H (facts), U (useful
next action), M2 (complete traveler composition), and C (decision-rich comparison
or a genuinely sparse-source exception), with latency ordinarily below 20 seconds
and a small overage allowed. These three saved cases do not establish population
reliability, an application SLA, owner presentation acceptance, frontend
integration, or M3 qualification. Luna remains the model. The active config is
[fast-default.json](../../../../../data/results/fast-default.json); the dated
campaign record is the [build log](../../../../../docs/build-log/2026-10-28-results-fast-default.md).

## Live evidence by candidate

Reviews below retain their original judgments. `H`, `U`, and `M2` are factual
correctness, useful next action, and complete composition; `C` is comparative
depth. Where a separate adjudication differs, both readings remain available.
Each run preserves exact requests, receipts, raw responses, source archive,
configuration, summary, and replayable artifact under `runs/`. The aborted V27
persistence attempt retains its artifact and explicit error instead of a summary.

| Candidate | Live cases and complete Results seconds | Independent review and disposition |
| --- | --- | --- |
| V4 | Admitted 10.255 | q001 failed H/U; M2 passed, C basic. Cash amount was presented as per-traveler without known quote scope. Not adopted. |
| V5 | Admitted 11.763; conditional 12.979; incomplete 9.449 | q002 and q004 passed H/U/M2, C basic. q003 failed H/M2 by asserting a business advantage over cash without cabin evidence. Not adopted. |
| V6 | Admitted 21.727; conditional 27.672 | q005 failed H through an unsupported comparator; q006 passed H/U/M2. Both had decision-rich C. The conditional miss and quality error disqualified it. |
| V7 | Admitted 13.649; conditional 16.312; incomplete 13.809 | q007 failed H/U; q008 and q009 passed H/U/M2. C ranged from basic to decision-rich. Not adopted. |
| V8 | Admitted 23.390; conditional 23.937; incomplete 17.196 | Three-call editorial revision. Delivered answers q010/q012/q014 passed; initial drafts q011/q015 had factual errors; q013 passed. The unconditional third call was slow. Not adopted. |
| V9 | Admitted 12.632 | q016 delivered answer passed H/U but failed M2 by relying on an unshown Taiwan comparator; q017 initial draft failed H/U/M2. Not adopted. |
| V10 | Admitted 23.831 | q018 delivered answer failed H: it assigned a 40-minute elapsed difference to an arrival claim whose delta was 730 minutes; q019 initial draft had multiple factual errors. Not adopted. |
| V11 scouts | Admitted 17.085; conditional 19.196; incomplete 15.844 | Original q020 failed H/C-basic; q021/q022 passed H/U/M2 with decision-rich C. Parent adjudicated q020 H as disputed, with a decision-rich central comparison and wording limits. |
| V11 frozen cohort | Admitted 14.237/17.397; conditional 16.991/20.810; incomplete 11.350/12.624 | All six were mechanically clean and passed U/M2. Original independent review passed H in only 3/6; q026/q028/q029 found material errors (cash-arrival scope, global lead dates, and seats 2 vs 9). Five had decision-rich C. **The combined gate failed; V11 was not adopted.** |
| V12 scouts | Admitted 14.041; conditional 11.613; incomplete 7.375 | q023/q024 passed H/U/M2 with decision-rich C. q025 failed H: `USD 60,500 points`. The effort-only low composer was rejected. |
| V11 recovery diagnostic | Admitted 24.486, three actual calls | A controlled fault triggered a real correction and a clean delivered artifact. This is a recovery-path timing example, not a natural correction rate or quality-confirmation answer. |
| V13 scouts | Admitted 20.789; conditional 15.569; incomplete 12.489 | Original q032 failed H/C-basic; q033/q034 passed H/U/M2 with C-basic. Parent adjudicated q032 H as disputed and its central comparison C as decision-rich; q034's displayed comparison is decision-rich, while q033 remains a basic comparison. The separate [adjudication](../../../../../docs/reviews/2026-10-28-results-v13-adjudication.md) preserves the originals and explains the scope. **These scouts do not qualify V13.** |
| V13 frozen confirmation | Admitted 16.837 (q035), 18.223 (q036); conditional 11.358 (q037), 18.449 (q038); incomplete 23.631 (q039), 13.137 (q040). Median 17.530 seconds. | Six independent reviews: q035 failed H (wrong elapsed-time comparison), U/M2 passed, C-rich; q036/q037 passed H/U/M2, C-basic; q038 failed H (departure order reversed), U/M2 passed, C-basic; q039 passed H/U/M2, C-rich with scope ambiguity noted; q040 passed H/U/M2, C-basic. **Gate failed: 2/6 H failures, despite latency median below 20 seconds. All six remain in the denominator.** See [q035](review-bundles/q035/review.md), [q036](review-bundles/q036/review.md), [q037](review-bundles/q037/review.md), [q038](review-bundles/q038/review.md), [q039](review-bundles/q039/review.md), and [q040](review-bundles/q040/review.md). |
| V14 scouts | Admitted 27.331; conditional 28.109; incomplete 17.609 | All three runs used two calls and were mechanically clean. q041/q042 passed H/U/M2 with C-rich; q043 passed H/U/M2 with C-basic. Selector times were 14.304/12.281/5.976 seconds; composer times were 8.952/12.634/9.226 seconds. Selector cached-token count was zero in all cases. **Latency gate failed; no confirmation cohort or default adoption.** Reviews: [q041](review-bundles/q041/review.md), [q042](review-bundles/q042/review.md), [q043](review-bundles/q043/review.md). |
| V15 scouts | Admitted 19.691; conditional 17.597; incomplete 12.703 | All three runs used two calls and were mechanically clean. Both passes in each run reported zero cached input tokens. q044/q046 passed H/U/M2 with C-rich; q045 passed H/U/M2 with C-basic. q045's plan call J115 selected `economy` while its canonical journey was business at 275k points; the composer correctly rejected that mismatched cabin, retained the facts, but produced a weak alternative. **No V15 confirmation or qualified default.** This was a combined effort-and-incomplete-guidance arm, so the effects cannot be isolated. Reviews: [q044](review-bundles/q044/review.md), [q045](review-bundles/q045/review.md), [q046](review-bundles/q046/review.md). |
| V16 scouts | Admitted 17.591; conditional 19.723; incomplete 13.989 | All three used two calls, were mechanically clean, and both calls in each run reported zero cached input tokens. q047/q048/q049 passed H/U/M2 with C-rich; minor wording caveats remain in the reviews. These scout results do not override the failed confirmation. See [q047](review-bundles/q047/review.md), [q048](review-bundles/q048/review.md), and [q049](review-bundles/q049/review.md). |
| V16 frozen confirmation | Admitted 17.08967399969697 (q050), 19.1094991248101 (q053); conditional 22.113502041902393 (q051), 21.61941258329898 (q054); incomplete 13.468674708623439 (q052), 13.957580666989088 (q055). Median 18.099586562253535 seconds. | Six normal completions, all two-call and mechanically clean. q050/q051/q052/q054 passed H/U/M2 with C-rich. q053 failed H and M2: it called one journey earliest among three despite J7 arriving 9h10 earlier; later text acknowledges the earlier arrival. q055 passed H/U/M2 with C-basic. Totals: H 5/6, U 6/6, M2 5/6, C-rich 5/6. **Gate failed** on q053 and q055's basic comparative depth. Original reviews remain preserved: [q050](review-bundles/q050/review.md), [q051](review-bundles/q051/review.md), [q052](review-bundles/q052/review.md), [q053](review-bundles/q053/review.md), [q054](review-bundles/q054/review.md), [q055](review-bundles/q055/review.md). |
| V18 frozen confirmation | Admitted 23.7674 (q063), 20.5955 (q066); conditional 18.3727 (q064), 19.1855 (q067); incomplete 17.1634 (q065), 14.1389 (q068). Median 18.7791 seconds. | All six used three actual generations/counts and selected the mechanically clean editorial patch. q063/q064 failed H and M2. q065/q066/q067 passed all axes. q068's original H-fail review and separate H-pass adjudication are both preserved; adjudication confidence is moderate. Final adjudicated H is 4/6 versus 3/6 under original reviews; U and M2 are 6/6 and C-rich is 4/6. The frozen cohort **failed** the combined gate. |
| V19 scouts | Admitted `scout-v19-admitted` 21.5028s; conditional `scout-v19-conditional` 18.8859s; incomplete `scout-v19-incomplete` 10.4261s. | All three were clean three-call Luna low/Fast runs. Final q069 passes H/U/M2 with rich C; conditional q071 party wording has a preserved disputed H-fail adjudication; incomplete q073 passes H/U/M2 but is basic. Paired draft reviews q070/q072/q074 are complete. No confirmation or qualification. |
| V20 scouts | Admitted 20.20s; conditional 20.90s; incomplete 16.99s. | q075 retains an ambiguous opening comparison, q077 is factually correct but basic, and q079 reverses the opening United points direction. All pass U/M2; the candidate fails the combined gate. Original paired reviews q075–q080 remain. |
| V21 scouts | Admitted39.2169s; conditional27.5173s; incomplete17.7582s. | NONE selector, LOW draft and MEDIUM atomic editor; all three-call mechanically clean. Source/depth gate did not pass and two cases exceeded latency. No confirmation/default qualification. |
| V22 scouts | Admitted 31.064s; conditional 20.963s; incomplete 26.931s. | All six initial drafts q088/q090/q092 and paired source answers passed H/U/M2 and decision-rich C, but final workflow latency failed. These initial drafts became V23 source evidence only after exact request/delivery identity proof. |
| V23 frozen confirmation | Admitted 11.347/12.818s; conditional 11.098/17.679s; incomplete 9.672/7.622s. Median 11.222s. | Six fresh answers all passed H/U/M2; five were decision-rich, q095 basic. Gate failed. The controlled conditional correction diagnostic completed in 18.731s and passed H/U/M2/C. See q093–q098 and `recovery-v23-conditional`. |
| V24 incomplete scouts | 10.081s and 10.987s. | q099 original review flagged H/M2/C; separate adjudication preserves H non-pass for ambiguous party linkage, finds M2 pass and C-rich on the supported premium/date/raw-quote comparison. q100 passes H/U/M2 but is C-basic. Fixed two-scout gate failed. |
| V25 incomplete scouts | 14.222s and 11.398s. | q101/q102 pass H/U/M2 but are C-basic with no sparse-source exception. No confirmation cohort or default promotion. |
| V26 incomplete scouts | 12.50s and 12.33s. | q103/q104 pass H/U/M2 but are C-basic. No confirmation or qualification. |
| V27 selector scouts | 19.36s and 18.03s. | q105 passes H/U/M2 and is C-rich. q106 passes H/U/M2; original review says C-basic, while separate fresh blind architect review says C-rich, consistent with q098. Preserve both. |
| V27 first frozen attempt | Two calls; post-save `NameError`, with no normal completion timing. | q107 source review passes H/U/M2 and is C-rich, but the cohort was aborted after harness failure. See [q107 review](review-bundles/q107/review.md). Original artifact, error and manifest remain saved. |
| V27 frozen cohort after harness fix | Admitted 11.48/10.21s; conditional 11.67/10.38s; incomplete 22.14/14.64s. Median 11.57576s. | All six are mechanically clean two-call completions and pass U/M2. H passes 3/6: q108 reverses global earliest vs a Taipei option 550 minutes earlier; q110 mixes points/fee comparison endpoints; q112 reverses the cash arrival comparison. q109 and q113 pass all axes; q111 passes H/U/M2 but is borderline basic. C-rich 5/6. **Gate failed.** See [q108](review-bundles/q108/review.md), [q109](review-bundles/q109/review.md), [q110](review-bundles/q110/review.md), [q111](review-bundles/q111/review.md), [q112](review-bundles/q112/review.md), and [q113](review-bundles/q113/review.md). |
| V27 correction diagnostic | 26.23448s; three actual calls. | Actual alias finding triggered one LOW full-wire correction; final artifact clean. Separate blind review passes H/U/M2/C-rich. Controlled recovery path only; latency misses target by more than a small overage. |
| V28 scouts | Admitted17.90s; conditional44.78s API-incomplete; incomplete10.62s. | Admitted q114 passes H/U/M2 with rich C. Conditional NONE-selector output loop ends at max_output_tokens8192; explicit failure, no salvage/retry. Incomplete q115 passes H/U/M2 but is basic. All artifacts preserved; no qualification. |
| V29 scouts | 18.80s, 13.16s, 11.05s (admitted, conditional, incomplete). | All passed H/U/M2; C-rich in 2/3. Scout evidence only; no frozen confirmation or qualification. |
| V30 scouts | 16.382831540890038s (admitted), 12.294490541797131s (conditional), 11.05886720912531s (incomplete). | All clean two-call runs. q119 passes H/U/M2, C-rich. q120 passes H/U/M2, C-basic; generic later-arrival preference has no offset. Positioning-permission uncertainty is not a source contradiction. q121 passes H/U/M2, C-basic; it discusses one United lead without an actual lead comparison despite the nonsparse 378-record inventory. Scout gate failed; no confirmation or correction diagnostic followed. |


Older profile details, implementation decisions, the independent V27/V30 reviews and adjudications, and the chronology of preserved failures are recorded in the [campaign build log](../../../../../docs/build-log/2026-10-28-results-fast-default.md).
The run directories and review bundles remain the source artifacts for every
listed outcome. Historical V4–V22 profiles are not current defaults.

## Running and replaying

Run from the repository root with the project virtual environment. Without
`--live`, the runner uses its offline path and makes no model calls. A live run
requires a unique name and is limited by the campaign ledger. Frozen cohorts
must use the manifest recorded for each run.

```sh
PYTHONPATH=src .venv/bin/python evidence/results-stage/m2/structured/2026-10-28-fast-default/selftest.py
PYTHONPATH=src .venv/bin/python evidence/results-stage/m2/structured/2026-10-28-fast-default/review_bundle.py --run <run-name> --bundle <opaque-id>
PYTHONPATH=src .venv/bin/python evidence/results-stage/m2/structured/2026-10-28-fast-default/verify.py --verify
```

This campaign has stopped at V30; do not add `--live` calls. A recovery diagnostic, when present, is labeled and excluded from the natural-answer denominator. The verifier checks receipts, source snapshots, replay, mutation controls, and per-run/global call caps; its final strict archive run exited 1 as recorded above. For
all dated decisions, preserved original reviews, failures, and detailed test
results, see the [build log](../../../../../docs/build-log/2026-10-28-results-fast-default.md)
and the linked review bundles above. The Streamlit path, owner presentation
acceptance, frontend integration, and M3 remain separate.
