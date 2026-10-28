# Luna latency experiment: keep/cut decision report

Date: October 25–26, 2026. Status: live campaign closed; owner decision pending.

**Recommendation: keep one composer; cut parallel analysis and hold off on a
faster default. We measured faster answers, but did not establish a repeatable
overall latency improvement that preserves the existing complete-answer quality target.**
The smaller V1 input at medium effort is the most promising speed candidate,
but its first passing three-case cohort failed on all three repeats. Richer V2
input at medium produced source-correct answers, with two disputed relevance
judgments. Its case-level latency was mixed: the incomplete case improved, while
the overall median stayed near original. It was not repeated.

## Measured results

These are **Results-only wall times from saved source parsing through checked
resolution**, including preparation, input counting, actual bounded correction
and, where applicable, the parallel workers. They exclude upstream intent,
planning, travel searches and final report/persistence work. First streamed text
is not a checked traveler display. No numerical SLA was supplied.

| Input and effort | Completed answers | Median wall time (range) | Complete-answer target met after review/adjudication |
| --- | ---: | ---: | ---: |
| Original, medium | 6 | **74.0s** (45.3–138.4) | **1/6** |
| V1, medium | 6, plus 1 timeout | **30.5s** (25.5–65.0) | **3/6** |
| V1, low | 3 | **19.6s** (18.9–29.0) | **0/3** |
| V2, low | 3 | **21.9s** (21.5–31.9) | **0/3** |
| V1, parallel low | 1, plus 2 worker failures | **42.5s** (one completed answer) | **0/3 runs** |
| V2, parallel low | 1 | **33.1s** (one completed answer) | **0/1** |
| V2, medium | 3 | **76.0s** (29.1–82.1) | **3/3 adjudicated; initial reviewer 1/3** |

“Target met” permits minor weaknesses and requires the existing source,
reference-role and complete-answer obligations. It is a configuration-review
criterion, **not a new application delivery gate**. Annotated recovery remains
unchanged. The V1 timeout is an additional failed run, excluded from numerical
latency summaries because exact elapsed time was lost, not because it was fast.
Worker failure times (15.2s and 10.5s) are not completed-answer latency.

Original/V1 medium each have two draws per saved case; other arms have one draw
per case or a stopped sentinel. Medians describe these small samples, not
population reliability, percentiles or a causal estimate under controlled cache
conditions. The original medium quality failures also prevent attributing every
quality defect to reduced reasoning effort.

V2 medium should not be dismissed as uniformly slower. The individual cases are:

| Case | Original medium draws | V1 medium draws | V2 medium, one draw |
| --- | ---: | ---: | ---: |
| Admitted | 67.8 / 138.4s | 65.0 / 37.0s | 76.0s |
| Conditional | 99.6 / 80.2s | 25.5 / 28.6s | 82.1s |
| Incomplete | 45.3 / 63.1s | 32.5 / 25.8s | 29.1s |

The V2 medium incomplete result is faster than both original draws; the other
cases overlap the original variation. Its overall mean is also lower, 62.4s
versus original 82.4s, while the median is 76.0s versus 74.0s. This is promising
case-specific evidence, not a repeated general improvement or an isolated input
effect under matched cache/server conditions.

## What to keep or cut

| Item | Recommendation | Reason |
| --- | --- | --- |
| Single composer and existing bounded recovery | **Keep** | Parallel workers did not provide a supported quality/latency advantage. |
| Parallel analysis topology | **Cut from the next implementation** | More calls, longer wall time and remaining composer errors; two V1 runs additionally failed worker references. |
| Low reasoning as a shared default | **Do not adopt** | Both single-composer input versions failed the complete-answer target on all three cases. |
| V1 factoring, local quotes and reference guide | **Retain as an experimental candidate, not a qualified default** | Fastest medium-effort results; first cohort passed but all three repeats failed. The bundle's components were not separately ablated. |
| V2 expanded identity/assessment copies | **Retain as a quality candidate with mixed latency; no general default yet** | Cited facts pass in all three medium answers; relevance is disputed on two. Incomplete is faster, overall mean falls, median stays near original, and only one cohort was run. |
| Prepared-first ordering | **No performance claim yet** | Offline prefix preservation is proven; an isolated order-only live control was not run and actual cache reuse was not consistent. |
| Exact preservation audits and full-path measurement | **Keep as development evidence/tools** | They distinguish saved facts, writer errors, correction cost and unavailable outcomes. |

If the current complete-answer goal stays unchanged, **none of these results
supports selecting a new faster shared default now**. If the owner is willing to
trade comparative coverage for speed, V2 low illustrates a roughly 22-second
answer with correct cited facts on two cases, but narrower or misleading choice
coverage; the incomplete case still had a cross-program comparison error. That
is an explicit quality tradeoff to decide, not a demonstrated equivalent answer.
No case-routing policy is inferred from three saved requests.

## Why the faster answers did not clear the quality bar

V1 medium's first three answers had no unresolved material defect after review
and adjudication. The same configuration's repeat cohort then:

- Reversed a one-hour arrival comparison in the admitted case.
- Applied a $59 positioning quote to a selected conditional journey whose exact
  quote was $139, while missing a relevant later-departure variant.
- Said Alaska and United lead taxes used different currencies when both were USD.

See the repeat reviews for [admitted](source-review-r2-admitted-candidate.md),
[conditional](source-review-r2-conditional-candidate.md) and
[incomplete](source-review-r2-incomplete-candidate.md).

V2 low reduced some identity mistakes, but factual correctness and whole-answer
quality diverged. Its admitted answer's dates/programs/arithmetic were correct,
yet three economy schedules displaced the materially different business and
separate-ticket discussion. Its conditional answer still omitted a same-arrival,
same-quote economy variant with a later SFO departure and shorter transfer buffer.
Its business comparison also lacks an exact supporting business reference card.
The incomplete answer ranked nominal points across different program currencies
despite an explicit instruction against doing so.

These are source-backed review findings over saved development cases. Mechanical
checks do not verify numerical prose or the whole choice argument; clean checks
therefore did not establish factual or composition quality.

## Why parallelism did not help

Matched admitted low-effort examples:

| Version | One composer | Worker wall phase | Final composition with workers | Total parallel wall | Estimated generation cost, single → parallel |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 19.6s | 23.2s | 16.6s | 42.5s | $0.0255 → $0.0766 |
| V2 | 21.9s | 14.7s | 15.2s | 33.1s | $0.0316 → $0.0937 |

The final composer did not become cheap enough to offset the analysis phase.
In V1, the choice worker correctly identified the two Aeroplan quotes and dates,
but the composer contradicted it. V2 parallel still said two flights left late at
night when one departed 11:45 a.m. and the other 11:15 p.m. The extra analysis did not
ensure correct synthesis. V1 conditional/incomplete workers emitted ranges such
as `J1–J232` instead of exact aliases, causing explicit failure before composition.
V2 clarified the worker protocol without silently expanding ranges or retrying.

These are stopped feasibility probes, not proof that every possible parallel
design fails. They provide no reason to add runtime orchestration now.

## Input size, preservation and cache

V1 factors four repeated fields, joins exact award/cash quotes near each member,
and adds a full-inventory same-schedule index plus a clearer reference guide.
V2 adds exact per-member dates/cabin/carrier/booking identity and unmodified
traveler/seat assessment records, plus a targeted comparison brief. Neither
version selects a winner, alters Ranking or trims eligible choices.

| Case | Original input tokens | V1 | V2 |
| --- | ---: | ---: | ---: |
| Admitted | 207,324 | 198,629 | 247,402 |
| Conditional | 189,806 | 180,600 | 224,631 |
| Incomplete | 171,065 | 171,471 | 171,886 |

V1's approximately 13% prompt-byte reduction yielded only about 4–5% token
reduction in the complete cases. V2 increased prompt bytes about 10% and input
tokens about 19% over original. Input size alone did not predict completion time.

Inverse reconstruction restores original requests exactly. All 258 journey aliases
in the admitted case and 232 in the conditional case, source joins, unknowns and
lead identities survive; the incomplete case keeps all 378 lead identities. Matching schedules
are not treated as identical physical flights. See the
[V1 audit](candidate-audit.json) and [V2 audit](candidate-v2-audit.json).

Prepared-first ordering preserves the large correction prefix offline. It did
not establish automatic cache savings: for example, the V1 incomplete correction
reported only 1,824 cached tokens out of 172,272 input tokens. Other repeated
requests did receive cache hits. No queue/prefill/network breakdown or separate
order-only causal effect is claimed. Count and response cache receipts are saved.

## Review disagreements and evidence limits

The final report retains every original review, including stricter judgments:

- V1 incomplete medium: initial material relevance failure; adjudicated minor
  because the wrong date/origin and lack of a usable connection were explicit.
  [Review](source-review-r1-incomplete-candidate.md),
  [adjudication](adjudication-r1-incomplete-candidate.md).
- V2 admitted low: initial minor weakness; adjudicated material composition
  failure because it omitted the entire distinct cabin/booking choice dimension.
  This does not require selecting business.
  [Review](source-review-v2-r1-admitted-low.md),
  [adjudication](adjudication-v2-r1-admitted-low.md).
- V2 medium admitted/incomplete: cited facts pass. The initial reviewer considered
  omitted better variants/lead relevance material; adjudication found the actual
  cabin argument supported and the invalid lead explicitly bounded. Thus the
  initial review is 1/3 passes and adjudicated classification 3/3, with minor
  relevance weaknesses. [Adjudication and source checks](adjudication-v2-r1-medium.md).

Reviews used original sources and complete eligible landscapes. Main source
review did not consult timing/usage. One earlier incomplete adjudication
incidentally exposed trailing attempt metadata; it does not claim full timing
blindness. These are independent native AI judgments, not owner presentation
acceptance, calibrated M3 judging, independent holdout evidence or traveler benefit.
The main keep/cut recommendation is unchanged under the stricter classifications:
the consistently fast low configurations have material defects; V1 medium's first
passing cohort failed on repetition; V2 medium's mixed timing and quality judgments
come from one cohort.

## Cost, failures and verification

The campaign reserved **40 generations and 40 input counts** against a 60/60 ceiling:
26 runs, 23 final answers, 8 worker generations, 8 correction generations, 2 explicit
worker failures and 1 transport timeout. There were 39 responses with API usage receipts:
7,625,093 input tokens and 104,098 output tokens (68,911 reasoning tokens included
in output). Estimated generation cost from those receipts is **$0.919395920** at
the recorded October 25 rates. The timed-out generation's cost is unknown and
additional; input-count billing and native Codex work are excluded. Not an invoice.

The timeout initially escaped the SSE iterator before the harness saved timing.
Its exact elapsed/usage remain unknown; 240s is a configured read timeout, not an
invented measurement. A separately named replacement is retained alongside the
failure. The instrumentation was fixed and tested with a timeout after partial
events; no automatic retries were introduced. The diagnostic also rejects
noncompleted/refusal responses before parsing, slightly stricter than the runtime
adapter; no captured final response had such a status.

Fresh verification: 27 focused Results tests passed in 102.50s; candidate inverse
and source-join audits, harness failure/budget/version controls, strict offline
request/receipt/source-snapshot/selected-resolution verification and Ruff passed.
All 26 runs are accounted for, including unavailable outcomes. The reporter's
strict failed-run accounting and original-version normalization bugs were fixed
before final verification. No runtime source, scripts or tests changed; the full
repository suite was not rerun. Prior evidence remains unchanged.

Read [metrics](metrics.json), [review classifications](reviews.json),
[campaign and stopping decisions](campaign.json), [code review](code-review.md),
or the [build log](../../../../../docs/build-log/2026-10-25-results-m2-latency-next-cut.md).
Saved requests, responses, selected answers, attempts and source archives are under
`runs/`. Diagnostic documents are noncanonical; their offline rechecks do not
claim historical artifact replay or a runtime version adoption.

No runtime model/effort default, authoring topology, Ranking policy, eligibility,
numerical-prose trust or recovery rule changed. Frontend work, owner acceptance
and M3 remain separate. Baseline checkpoint commits are `d9c225a` and `b4a8084`;
this experiment/report is left available for the owner's keep/cut decision.
