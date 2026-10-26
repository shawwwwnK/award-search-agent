# Results M2: Luna input and latency next-session handoff

Date: 2026-10-25.

Status: investigation complete; next cut recommended after independent milestone
advisor review. The owner requested this handoff for a new session. This document
does not claim implementation of the proposed changes, a new shared configuration,
milestone closeout, or authorization to reuse an exhausted live-call budget.

## Objective and milestone alignment

Keep **Luna** and improve Results authoring responsiveness while preserving useful,
source-supported explanations and the existing Results contract.

The broader Results stage, previously called Output, helps travelers understand the
highlighted flight choices, compare their tradeoffs and inspect the other options
found. Current Results M2 owns structured facts and one coherent LLM-authored answer:
Ranking-informed highlights, individual explanations woven into a connected argument,
relevant alternatives, embedded exact references, cash context and consolidated
limitations. The complete explorer remains independent of authoring.

This next cut is **existing writer-input ergonomics and bounded measurement**.
Recruiting evidence is a consequence of disciplined engineering, not a reason to
add architecture. Retain the accepted delivery sequence:

```text
Results M2 revision → Frontend M1 saved-results workspace
                    → Frontend M2 connected experience
                    → Results M3 integrated evaluation/closeout
```

The owner's numerical latency target remains unset. The earlier 30-second example
was not an accepted SLA. A target is needed before claiming threshold-based
responsiveness acceptance; it need not block reversible offline investigation.

## Read first

Apply repository instructions and their source-of-truth hierarchy. Prioritize newer
dated amendments over historical opening/closeout paragraphs.

1. [Current project state](../project-state.md), especially the October 25 latency,
   composition and cost entries.
2. [ADR 0029](../adr/0029-structured-results-and-local-workspace.md), including
   October 25 composition and latency dispositions; consult the
   [ADR workflow](../adr/README.md) before accepting consequential changes.
3. [Current structured Results/workspace plan](../plans/2026-10-23-2334-feat-results-workspace-plan.md),
   especially the Goal Capsule, U1–U3 and milestone allocation.
4. [Complete-answer composition contract](../plans/2026-10-25-results-m2-composition-correction.md)
   and [Results API/delivery documentation](../results-m2.md).
5. [Latency measurements and actual answers](../../evidence/results-stage/m2/structured/2026-10-25-latency/README.md)
   and [independent source/composition review](../../evidence/results-stage/m2/structured/2026-10-25-latency/review.md).
6. [Detailed reasoning takeaway](../results-m2-latency-investigation-takeaway.md),
   [investigation build log](../build-log/2026-10-25-results-m2-latency-experiments.md)
   and [deferred register](../../DEFERRED.md), particularly G06/G08.

The external workbook is `/Users/shawnkang/bots/workbook_formatted.md`. Consult only
relevant product/ownership/evaluation sections when needed; do not modify it.

## What the investigation established

Eight saved-input calls used `gpt-6-luna`, explicit medium/low reasoning, standard
processing, streaming for timing and no automatic retries. There were no correction,
token-count, travel-provider or FX calls in this diagnostic.

| Probe | Full response | Disposition |
| --- | ---: | --- |
| Original admitted, medium | 87.25 s | Source/reference failures |
| Original admitted, low | 16.52 s | Material arithmetic/choice errors despite clean checks |
| Original conditional, medium | 42.84 s | Document validation failure |
| Original conditional, low | 17.06 s | Misleading choice argument despite clean checks |
| Original incomplete, low | 13.11 s | Main narrative sound; reference selection requires correction |
| Factored admitted, medium | 55.95 s | Three mechanical failures |
| Factored conditional, medium | 43.22 s | Misleading choice argument despite clean checks |
| Factored admitted, low | 15.09 s | Material date/arrival errors and a check failure |

No probe passed both mechanical and source/composition review. Medium baselines also
failed: the data does not establish that low effort caused the quality defects.
These timings measure initial generations, not complete accepted answers or fresh
intent-to-search application runs.

Important observations:

- Medium admitted used 7,054 reasoning tokens versus 360 at low. Medium took 87 s
  despite 207,321 cached input tokens. This supports reasoning as a major contributor,
  without isolating queue, network or input-processing time.
- Factoring four exactly repeated journey fields reduced prompt bytes about 39%
  and actual input tokens about 31%. Inverse reconstruction restored the entire
  original requests, preserving 258/232 exact eligible aliases. It did not establish
  consistent latency improvement or successful model interpretation.
- The incomplete request was unchanged by journey factoring: it has no complete
  journeys and is dominated by component/lead evidence. Preserve its local lead
  identities; removing them risks earlier observed alias/prose mismatches.
- Measured local workspace/preparation/check/resolution took about 0.67–1.79 s per
  case, excluding parsing/full replay/counting. Live counting remains unmeasured.
- First stream events arrived in roughly one second, but medium visible text took
  34–77 s. First JSON text is not a usable checked flight display.
- Existing feedback-first serialization shares only 13 input bytes between the saved
  incomplete initial and correction requests. Preparation-first ordering would share
  597,318 bytes offline. Actual new cache reuse/speedup has not been tested.

Representative quality failures to carry forward:

1. **Omitted alternative changes the argument:** the writer frames 275,000-mile
   business as buying earlier arrival compared with 110,000-mile economy, while
   another eligible 110,000-mile economy option has the same early schedule.
   Correct selected-pair arithmetic does not make the overall comparison sound.
2. **Date/time errors:** January 16 at 22:25 versus January 17 at 09:50 is 11 h 25 m,
   not 1 h 25 m; noon versus 23:15 differs by 11 h 15 m.
3. **Reference-role errors:** positioning components incorrectly emitted as direct
   benchmarks or incomplete leads; additional benchmark references not matching the
   current selection contract; unsupported declared-claim scope or literal placement.

Estimated generation cost was $0.14050, excluding native Codex work. Prior focused
verification passed 27 tests. These are dated prior results, not fresh verification
for whatever the next session changes.

## Advisor disposition and constraints

An independent architect reviewed the proposed work against the current milestone,
ADR, contracts, workbook and evidence. It supports this narrow direction with the
following restrictions. This records advisory recommendations and existing policy;
it does not invent a new owner-approved architecture.

- Improve the **existing prepared writer input**. Do not introduce another canonical
  factual projection, comparison engine, scoring system, reranking or upstream verifier.
- Preserve all exact eligible options, source associations, unknowns, complete
  canonical evidence and the independent explorer. Do not trim choices to fit context.
- Matching schedules may expose useful relationships, but do not establish identical
  physical flights or interchangeable cabin/price/booking facts.
- The LLM retains recommendation selection, words, structure, order and comparative
  explanation. Ranking highlights remain a starting point. No fixed skeleton,
  recommendation count, cabin quota or style quota is introduced.
- Supported arithmetic already fits code ownership. Any new aid must be small,
  source-bound and justified by an observed error. **Do not build exhaustive pairwise
  matrices.** Do not force supplied facts into prose or add an inline-value binding
  contract/exhaustive semantic verifier; numerical prose remains model-authored.
- Clarify existing reference/claim rules rather than changing eligibility or relaxing
  the output contract to accommodate mistakes. Cash benchmarks remain outside award
  recommendations; incomplete leads do not become complete journeys.
- Preserve current recovery: one initial generation and at most one correction for
  recoverable failed checks, retain the better recoverable draft, correction wins
  ties, and preserve annotated remaining findings. No recoverable document is an
  explicit generation failure. Independent experimental review is not a runtime judge.
- **Configuration-adoption criteria are not new blocking delivery rules.** Report
  diagnostic outputs meeting review criteria alongside failed and annotated outcomes;
  do not imply the application withholds every imperfect answer until a judge passes it.
- Keep one composer for the primary next cut. The owner subsequently requested
  recording the parallel-analysis alternative below; it remains a separate proposed
  experiment, not adopted runtime orchestration. No provider search, FX refresh,
  request mutation, persistent cache infrastructure or broader workflow redesign.
- Streaming/rendered first-usable content belongs to later frontend work. This
  diagnostic does not qualify M3, owner presentation acceptance or traveler benefit.

## Recommended next cut

### A. Prototype offline in the existing input path

1. Establish the unchanged source/option/reference inventories for the three saved
   admitted/conditional/incomplete cases.
2. Improve locality of exact schedules, dates, duration, cabin, program, points,
   scoped money, booking facts and unknowns beside their selectable references.
   Reuse existing resolved/compact facts; avoid creating a second authority.
3. Factor exact repetition where useful. Preserve or explicitly account for every
   member and source value; retain lead identities that address previous failures.
4. Make source-supported same-schedule economy/business relationships easy to see
   without choosing a winner or equating unrelated facts.
5. Clarify journey/benchmark/lead selection and declared-claim rules within the
   existing output contract.
6. Add a limited calculated comparison aid **only if** putting the existing facts
   together leaves a specific demonstrated problem. Use exact references, sufficient
   date/time evidence and explicit unknowns. Do not perform naive local-clock
   subtraction across time zones or discard calendar dates.

Deliverable: one reviewable candidate representation, preservation evidence and
targeted date/reference controls. A simpler change that addresses the failure is
preferable to implementing every suggested aid.

### B. Measure the full Results authoring path

Measure preparation, input counting, generation, checking/resolution, actual bounded
correction and Results completion. Separate request-to-full-response, first visible
text and any future first usable rendered result. Do not label Results-only timing
as full intent/planning/provider application latency.

Test stable preparation before changing feedback/prior draft as a separate control.
Measure actual cache receipts rather than inferring savings from prefix bytes.
Retain existing context protection and exact request/count association.

Deliverable: attributable timing and request settings without another orchestration
framework. The runtime currently has no explicit reasoning-effort setting in its
structured request; the probe supplies it directly. If configuration is integrated,
make that change explicit and account for request/replay consequences.

### C. Run a small declared Luna diagnostic when invoked

First compare original and revised inputs at fixed medium effort. Then compare the
revised representation at medium/low if warranted. Repeat/interleave matched draws,
hold unrelated instructions/settings constant, and record cache conditions.

Use the same saved sources and existing composition criteria. Review the full
eligible landscape where it changes the argument, exact date arithmetic, reference
roles, cash/price scope and consolidated limitations. Mechanical cleanliness alone
is insufficient. Include actual bounded corrections, all failed attempts, usage and
cost in the report. Keep quality-passing completion times separate from other outcomes.

Declare a finite generation/count/correction envelope before any new calls. The
previous probe's eight-call cap is exhausted. This handoff is not unused budget or
an automatic paid-campaign invocation; follow the new session's explicit instruction.
Do not expand this into a general M3 judge-calibration campaign.

### D. Decide and preserve the milestone boundary

Retain, revise or reject the candidate based on the measured tradeoff. Obtain the
owner's responsiveness disposition before claiming the latency issue resolved.
If no numerical target is supplied, report actual values and relative results without
claiming an SLA pass. Do not infer owner presentation acceptance or close M2/M3.

## Optional follow-on: parallel Luna analysis, then one composer

### Owner request and status

After the advisor-reviewed handoff, the owner asked whether parallel subagents
handling different components followed by a main composer could reduce latency,
then requested adding that option here. This records the alternative for the next
session. It does not authorize immediate implementation, new paid calls, a default
topology change or a general multi-agent framework. The improved-input single-
composer baseline remains the first comparison point.

**Hypothesis:** narrow parallel analysis lets the final Luna composer reason less
while preserving the complete choice argument. This has not been tested.

### Candidate decomposition

Use Luna throughout. Compare the single-composer baseline with two independent,
bounded analysis calls, followed by one final composer:

| Role | Responsibility |
| --- | --- |
| Choice-analysis worker | Examine meaningful eligible alternatives, shared schedules and actual differences. Search across cabin options so the early-arriving economy counterexample remains discoverable. |
| Evidence-limitations worker | Identify applicable price-scope, cabin, traveler, separate-ticket and dated-availability limitations, associated with exact references. |
| Final composer, after workers | Use source-bound facts and worker findings to select and explain options in one connected answer, with exact embedded references, cash context and consolidated limitations. |

Workers should return concise findings tied to exact existing references, rather
than separately polished answer sections. They do not select an exclusive shortlist,
change eligibility/Ranking, or become a new source of truth. The composer retains
the accepted editorial and selection ownership. Preserve complete eligible access,
canonical evidence, unknowns and the independent explorer. Do not treat worker
summaries as evidence that every omitted alternative was checked or remove exact
source facts merely to make composition faster.

Avoid one writer per option initially. Individually correct option explanations
can miss the cross-option relationship that changes the choice; stitching their
prose together also adds reconciliation work and risks disconnected mini-answers.

### Timing model and risks

```text
Parallel workers start together
  → wait for the slowest worker
  → final composition
  → validation and existing bounded correction, if applicable
  → Results completion
```

Total latency includes preparation/counting, the slowest analysis call, the final
composition call and handoff/check/correction overhead. The final composition is
a sequential dependency. It must become sufficiently cheaper to offset the added
analysis phase; parallel worker execution alone does not establish a speedup.

Specific risks to test:

- The composer repeats the workers' full analysis, adding calls without removing work.
- A worker omits a decisive alternative, and the composer trusts its summary.
- Reference/date/price errors propagate through the handoff.
- Overlapping evidence across workers increases total tokens and cost.
- A slow or failed worker delays synthesis or introduces a new failure path.

If prototyped, define finite worker/final-call counts, timeouts and explicit failure
outcomes before calls. Do not add silent retries, recursive delegation or a fallback
that labels missing worker analysis as successful. Preserve existing final-document
recovery/annotated delivery; distinguish any new worker failure from that policy.
Do not automatically apply the final writer's correction allowance to each worker.

### Discriminating comparison

1. Establish the improved-input, one-Luna-composer baseline from the primary cut.
2. Compare it with two parallel Luna analysis workers plus one Luna composer using
   the same saved sources, option access, output contract and review criteria.
3. Record each call's model, effort, evidence/input, cache receipt, time and usage.
   Measure actual full Results wall time, including preparation, counting, the
   slowest worker, synthesis, checking and any correction. Do not sum concurrent
   worker durations and call that user latency.
4. Compare quality-passing completion times alongside all failed/annotated outcomes,
   total cost and correction frequency. Review cross-option reasoning and whole-
   answer composition independently; clean worker outputs do not establish a sound
   final recommendation.
5. Keep topology and input changes distinguishable. Any later combined effort/input
   tuning needs separate labeling so its effects are not attributed to parallelism.

Declare a separate finite campaign under the next session's instruction before
paid execution. Reuse no exhausted budget. This is a topology feasibility probe,
not an M3 calibration campaign or general model qualification. Any accepted runtime
multi-agent topology would require revisiting the current non-goal and one-composer
decision through the ADR workflow before adoption; recording the hypothesis does
not change those decisions.

Proceed only if the experiment can materially resolve the latency/quality question.
A slower or costlier result without a justified quality benefit is useful rejection
evidence, not a reason to expand orchestration. The simpler successful configuration
remains a valid outcome.

## Implementation and evidence map

Relevant seams to inspect before editing:

- `src/award_agent/results/structured.py`: prepared input, instructions, request,
  checks, resolution and replay.
- `src/award_agent/results/authoring.py`: existing compact representation/factoring.
- `src/award_agent/results/presentation.py`: resolved source facts and workspace.
- `src/award_agent/results/adapter.py`: generation/count adapters and timing.
- `src/award_agent/results/runner.py`: shared bounded attempt/recovery behavior.
- `src/award_agent/results/contracts.py` and `structured_contracts.py`: configuration
  and saved request/document/artifact shapes.
- `scripts/run_structured_results_eval.py`: bounded saved-case runner; inspect before
  extending rather than adding a parallel evaluation framework.

The isolated diagnostic is under
`evidence/results-stage/m2/structured/2026-10-25-latency/`:

- `factor.py` and `audit.json`: offline exact factoring and inverse preservation.
- `verify.py` and `summary.json`: offline request/source integrity and output rechecks.
- `probe.py` and `campaign.json`: exhausted live diagnostic, **not** a runtime implementation.
- Per-probe folders: immutable request, response, timing, findings and available previews.
- `prefix-audit.json`, `local-timing.json`, `source-manifest.json`: supporting measurements.

Original saved sources are under
`evidence/results-stage/m2/structured/2026-10-25-cost-experiments/luna-retest/round-1/`.
Preserve earlier passing Luna/Sol cohorts and all failed evidence. The new probe
documents are not canonical Results artifacts and do not establish historical replay.

## Verification and session closeout

Choose tests appropriate to actual changes; useful existing starting points are:

```bash
.venv/bin/python -m pytest -q tests/unit/test_results_structured.py tests/unit/test_structured_results_eval.py tests/unit/test_results_structured_cli.py
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-latency/verify.py
git diff --check
```

Run relevant preservation, runner/configuration, formatting/type and replay checks
for any affected seams. A saved document replay must not regenerate through Luna.
Keep original evidence unchanged. The owner permits intentional development
compatibility breaks with explicit receipts and coverage claims; avoid compatibility
machinery solely to conceal a preparation change. Historical V1–V5 behavior remains
outside this cut unless the new instruction changes that scope.

Before implementation, inspect `git status`: this workspace contains uncommitted
latency documentation/evidence and separate end-to-end diagnostic artifacts from
earlier work. Preserve unrelated changes and do not attribute or sweep them into a
commit without scope review. This handoff makes no commit/push request.

Update the relevant build log, project state and deferred dispositions with actual
work/results. Follow the ADR workflow: routine input ergonomics need no new policy
decision; accepted ownership, eligibility, delivery, trust or evaluation-boundary
changes require an explicit ADR disposition and conflict review. Report new failures
and claim limits. The previous full suite had two recorded gfly environment failures;
do not represent that historical run as fresh evidence or silently assume the same
failures after new changes.

## Suggested new-session instruction

> Read this handoff and the current source-of-truth documents. Start with the
> narrow offline writer-input improvement, preserve all eligible choices and
> existing model/Ranking/recovery ownership, and verify the candidate representation.
> Keep Luna. Treat the handoff's proposed aids as hypotheses, not a requirement to
> build every mechanism. Declare any new live diagnostic's scope and finite bounds
> under the new session's instructions before making calls. Report measured quality,
> complete Results timing and remaining uncertainty without claiming frontend or
> M3 completion. The optional parallel-analysis topology is a separate follow-on
> experiment after the improved-input single-composer baseline, not a requirement
> to introduce runtime multi-agent orchestration.
