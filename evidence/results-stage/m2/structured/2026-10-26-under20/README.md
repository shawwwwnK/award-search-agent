# Luna Results below 20 seconds — final decision report

**Speed target met; strict quality gate not yet met.** All six frozen full
`focused-v3` runs completed in **6.72–8.46s** (median **7.63s**) on Luna.
Independent review passed usefulness for 6/6 and factual correctness for 5/6;
all six had basic comparative depth and clean protocol/mechanical outcomes.
The remaining error reports one award seat where the source reports two. Both
support the requested one traveler, but the factual failure is retained.

**Recommendation:** keep the two-step architecture, exact reference validation,
small source-resolved writing bundle and code-computed temporal comparisons.
Keep this as an explicitly selected fast candidate. Do not adopt it as a
factually qualified default until the prose/source binding gap is addressed and
a fresh cohort passes.

**Subsequent owner direction:** commit this checkpoint and inspect/iterate in
another session, intending to make the fast profile the default. The actual
switch and quality acceptance remain pending. See the
[continuation handoff](../../../../../docs/handoffs/2026-10-28-results-fast-profile-next-session.md).

The owner requests below20seconds while retaining Luna, with architects,
investigators and advisors reassessing quality, input and parsing. This campaign
implements an explicit Results API/CLI path and measures the actual runtime on
three saved upstream cases. It makes no travel-provider or FX-refresh calls.

## Final unchanged confirmation

| Saved case | Cohort 1 | Cohort 2 | Independent H/U | Depth |
|---|---:|---:|---|---|
| Admitted |7.75s|8.46s|Pass/pass; **fail/pass**|Basic|
| Conditional |8.32s|7.51s|Pass/pass twice|Basic|
| Incomplete |6.72s|6.92s|Pass/pass twice|Basic|

All 12 generation responses returned Fast tier on `gpt-6-luna`. Each run made
one `none`-effort selector call and one `low`-effort composer call, with two
input counts, zero SDK retries and no third correction. Each outer timer includes
saved-source parsing, preparation, both counts/calls, checks, resolution and
artifact construction. Persistence and independent offline replay occur after
the clock stops. These are actual runtime measurements, not prototype or
first-token times. All 30 frozen runtime/source hashes match the run snapshots.

The [final manifest](confirmation-focused-v3.json) declared all six run names
before execution. No failures were replaced. The combined gate is **5/6**, not a
pass inferred from the median. The [last admitted review](review-bundles/b032/review.md)
quotes the seat-count error and exact source. Scoped timing comparisons passed;
the canonical evidence retains the correct count of two. The resolved journey
card does not itself display that count, so it must not be claimed to repair the
narrative error.

Read the actual answers:

| Case | First answer/review | Repeat answer/review |
|---|---|---|
| Admitted |[Answer](runs/confirm-f3-1-admitted/answer-preview.md) · [Review](review-bundles/b027/review.md)|[Answer](runs/confirm-f3-2-admitted/answer-preview.md) · [Review](review-bundles/b032/review.md)|
| Conditional |[Answer](runs/confirm-f3-1-conditional/answer-preview.md) · [Review](review-bundles/b028/review.md)|[Answer](runs/confirm-f3-2-conditional/answer-preview.md) · [Review](review-bundles/b031/review.md)|
| Incomplete |[Answer](runs/confirm-f3-1-incomplete/answer-preview.md) · [Review](review-bundles/b029/review.md)|[Answer](runs/confirm-f3-2-incomplete/answer-preview.md) · [Review](review-bundles/b030/review.md)|

The previews mark embedded source cards; full resolved factual objects are in
each run's `resolved.json`. The current frontend was not changed or evaluated.

## Keep/cut decision

| Component | Recommendation | Evidence/tradeoff |
|---|---|---|
| Typed selection over the entire inventory, then focused writing |**Keep**|All choices remain available to Luna; writing input contains only exact model-selected records. Six full runs below 8.5s.|
| Explicit source roles and schema-enforced total ≤8 references |**Keep**|Stops unknown/wrong-role/over-budget output without silent repair or pruning.|
| Code-computed selected-journey time comparisons |**Keep**|Fixed the demonstrated duration inversion; final timing comparisons pass review. Does not verify all prose.|
| One full-context low-effort composer; longer descriptive IDs as the sole fix |**Cut as the preferred route**|Repeated route, program, date and identity errors despite fast answers.|
| Full-answer `none` reasoning or parallel analyst/composer topology |**Cut as the next bet**|Prior probes failed quality; parallel work added latency without demonstrated benefit.|
| Automatic qualification/default adoption |**Hold**|One factual failure remains; all six explanations are basic, sometimes awkward or thin.|

This is a quality tradeoff, not proof that all original presentation goals were
preserved. The prospective H/U/C rubric is narrower than an exhaustive rich
comparison requirement. It does not retroactively qualify the older campaigns,
M2 owner presentation acceptance or M3. Further prompt/alias tweaks alone have
not demonstrated reliable prose-to-source binding.

Use the explicit candidate with a Luna config:

```bash
.venv/bin/python -m award_agent.cli.results author --interactive --packet-profile focused-v3 --projection projection.json --config config.json --output artifact.json --live
```

The fixed profile owns selector/composer effort and Fast service; it rejects
effort/tier overrides. Ordinary replay makes no calls. Legacy routes remain.

## What changed

- A writer-specific decision packet retains every eligible journey, incomplete
  lead and benchmark, with decision facts/unknowns and exact source joins. Full
  canonical evidence and the eligible explorer remain local and complete.
- The compact typed wire derives highlights, alternatives, one cash benchmark
  and leads into the existing structured document and source-resolved cards.
  Selection, answer organization and explanations remain Luna's responsibility.
- The interactive return path constructs the bound artifact once. Independent
  offline replay checks source, request, raw model output, document and resolved
  answer bindings; it is no longer an immediate second reconstruction on return.
- Processing tier and reasoning effort are explicit. Fast requests still use
  `gpt-6-luna`; actual returned tiers and raw usage are recorded. Old Results
  routes/defaults and prior replay compatibility boundaries are preserved.
  This does not undo the earlier source-version-only replay disposition for
  superseded October24 V6 preparations.

These are separate from changes to Ranking, eligibility, provider execution or
frontend integration. The new wire omits optional declared-claim annotations;
ordinary numerical prose remains outside exhaustive mechanical verification.

## Target and quality standard

Each frozen confirmation must deliver a mechanically clean, independently
truthful and useful answer in **less than20seconds**, including saved-source
parsing, preparation, counted input, all actual authoring/correction, checks,
resolution and artifact construction. Disk persistence and independent offline
replay occur afterward. First text or a sub20 median is insufficient. This is
Results-only timing, not the whole intent-to-search-to-answer application.

The prospective `under20-HUC-v1` rubric in [campaign.json](campaign.json) treats
material truth/scope/identity (H) and useful supported choice/reason/downside,
cash context and limitations (U) as hard requirements. Comparative depth (C) is
graded separately as insufficient/basic/decision-rich. No cabin/style quota or
exhaustive frontier is required. An omission is a hard factual failure when it
invalidates the answer's actual central argument. This does not retrospectively
regrade the earlier campaign or establish owner acceptance of thinner answers.

Reviewers inspect anonymized answer/document/source bundles without settings,
timings or a desired winner. Mechanical cleanliness does not establish H/U.

## Preserved iterations

| Candidate | Evidence | Disposition |
|---|---|---|
| Indexed packet, low/Fast | Admitted7.98s prototype | Wrong referenced alternative facts; reject |
| Indexed packet, none/standard | Admitted10.09s prototype | Identity/time/fee errors; reject |
| Indexed packet, medium/Fast | Actual-runtime scouts14.83/16.50/15.10s; one API failure retained | First scouts passed H/U; insufficient repetition |
| Indexed packet, medium/Fast frozen confirmation | Six delivered;9.64–21.42s | Two latency misses and one separate H/U failure; failed cohort preserved |
| Joined packet v2, low/Fast |13.00/8.33/5.74s | Admitted H/U pass; conditional factual failure; incomplete invalid-role/unavailable |
| Joined packet v2, medium/Fast | Incomplete15.88s; conditional38.57s | Both H/U pass; conditional misses speed target |
| Readable identities and source-role grammar, v3 |10.45/9.98/8.59s; all mechanically clean | Admitted calls connecting flights direct; conditional falsely claims equal arrival; incomplete H/U pass. Reject as final profile |
| Domain wording and arrival-bound identities, v4 |11.43/12.25/6.96s; all mechanically clean | Conditional H/U pass; admitted route/departure error, incomplete program-name error. Frozen confirmation not launched |
| Focused-v1, V8 typed selection then composition | Admitted10.08s H/U pass; two selectors return9refs and stop | Structural total-budget correction required |
| Focused-v2, schema total≤8 |10.06/9.13/6.70s; all delivered clean | Conditional/incomplete H/U pass; admitted reverses duration comparisons |
| Focused-v3, code-supplied temporal comparisons | One composition-only diagnostic H/U pass, then six full runs6.72–8.46s | All six useful; five factual passes, one wrong seat count. Speed pass, strict joint gate fail |

Prototype times are not actual runtime confirmations. No failed run is replaced
inside a frozen cohort. The original [confirmation manifest](confirmation.json)
and [review index](review-index.json) remain intact.

V8 targets the repeated full-context association failure structurally. The first
Luna call sees all choices and returns only exact references. Code resolves up to
eight model-selected references into a small fact bundle for a second Luna call.
The composer retains final selection and editorial discretion among those choices;
comparisons must be scoped to what it can see. Both calls/counts/local work count
toward the same strict runtime target. These two calls consume the full per-run
generation budget, so there is no third correction call. Canonical explorer
coverage remains complete. This differs from the earlier unsuccessful heavy
analyst/composer experiments: the first response contains typed identities only
and the writing call receives a small source-resolved bundle.

## Evidence and limits

The [declared campaign](campaign.json) permits48generation and48input-count
invocations, zero SDK retries, and at most two authoring attempts per run. The
shared atomic [call ledger](calls/) accounts for every invocation, including
unavailable outcomes. No usage means unknown cost, not free execution. Runtime
snapshots preserve code/config/source for each draw; source reviews and metrics
report all outcomes. **46generation reservations and47count reservations** were
used, below48/48. One count reservation was externally interrupted by sandbox
network policy; its [interruption receipt](runs/focused2-a/interruption-receipt.json)
records no response, generation or latency claim. The reservation remains charged
to the limit. One earlier generation (`scout-d`) has unknown usage/cost.
Historical first-cohort snapshots omitted the CLI file;
its declared code hash therefore cannot be independently verified from those
archives. New snapshots include it; no historical proof is fabricated.

Recorded generation-cost estimate for the final six answers is **USD 0.02423265**
in total (USD 0.00162738–0.01277170 per answer). Reused-case prompt caching heavily
affects this range; it is not a fresh-request cost forecast. Rates use observed
input/cache-write/cache-read/output usage and Fast's 2× multiplier. The campaign's
known generation subtotal is USD 0.502989985 plus the unpriced earlier error;
count-endpoint/native Codex costs and actual invoices are outside this estimate.
See [metrics](metrics.json) and the official
[Luna model](https://developers.openai.com/api/docs/models/gpt-6-luna) and
[Fast processing](https://developers.openai.com/api/docs/guides/fast-mode) documentation.

Verification: **221 Results tests passed**, including the new focused, comparison,
stream failure and replay-boundary cases. Ruff and mypy pass for changed source.
Every delivered run has independent offline reconstruction receipts; final code
and settings match the frozen manifest. The whole repository suite was not rerun.

Only three reused development cases are covered. No holdout reliability,
population percentile/SLA, current provider availability, owner presentation
acceptance or M3 qualification follows from this experiment. Fast has premium
pricing; it does not itself guarantee a deadline.

See [session log](../../../../../docs/build-log/2026-10-26-results-under20.md)
and [ADR0029](../../../../../docs/adr/0029-structured-results-and-local-workspace.md).
