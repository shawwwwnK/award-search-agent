# Results M2 latency next-cut experiment — 2026-10-25

## Invocation and checkpoint

The owner approved the updated latency handoff and requested experiments, iteration,
live runs, subagent orchestration and a final keep/cut decision report. The stated
goal is shorter latency without sacrificing too much quality. No numerical latency
target or tolerance for material misinformation was supplied.

The subsequent instruction required committing pending work before execution.
Checkpoint commits: `d9c225a` (curated prior end-to-end diagnostic) and `b4a8084`
(prior latency investigation/evidence and updated handoff). The working tree was
clean immediately afterward. Fresh pre-checkpoint evidence: 27 focused Results
tests passed in 97.70s; prior latency integrity verifier and Ruff passed; staged
whitespace checks passed. No new live call or experiment file preceded checkpoint.

## Declared experiment

The new [campaign](../../evidence/results-stage/m2/structured/2026-10-25-latency-next-cut/campaign.json)
caps all initial, correction and worker attempts at 60 generations and 60 counts,
reserved before invocation. Luna, zero SDK retries, 240s per-call timeout. Saved
three-case comparison only; no travel provider/FX calls. Original-medium versus
candidate-medium, then candidate-low versus two parallel low-effort analysts plus
one low-effort composer. Two matched repetitions planned; stage/stop based on
observed evidence. Version any input iteration and preserve all failed results.

Subagents: architect strategy, investigator harness trace and prior-checkpoint
inspection, separate implementers for candidate input and measurement harness.
Independent code and source/composition review will follow. Applied the
verification-before-completion and requesting-code-review skills.

## ADR disposition

The owner invokes an isolated feasibility experiment, including the handoff's
parallel-analysis alternative. No runtime topology, eligibility, trust, Ranking,
delivery or recovery decision is adopted. ADR 0029 will record experiment scope
and final disposition; runtime adoption remains a subsequent explicit decision.

## Results and verification

Execution continues into October 26 local time. First admitted original/candidate
medium draws completed in 67.76/65.02s, both mechanically clean; independent review
found a material omitted economy comparison in original and only a minor internal
alias presentation defect in candidate. These are initial draws, not adoption.

The first conditional candidate draw failed with `httpx.ReadTimeout` during SSE
iteration. Its count/generation reservations and exact request/snapshot remain.
The diagnostic caught SDK APIError but not the stream's raw httpx exception;
therefore exact wall/first-text timing and final usage were not captured. A clearly
labeled failure note records this gap; do not fabricate a 240s measured duration or
zero cost. The harness will catch/record transport failures and receive a fake
stream-timeout control before further calls. A manual replacement, if run, has a
new identity and consumes the original finite envelope. No automatic retry.

This was an execution checkpoint. Final results and disposition are below; no
owner conclusion or accepted latency fix is inferred.

## Evidence-driven V2 iteration (October 26)

At 21 generation/count reservations, V1 medium revised input has three final
answers with no material defect after adjudication (minor weaknesses remain).
Original medium admitted/conditional omit decision-changing economy alternatives.
V1 low single-composer has material errors in all three cases: date/reference
identity, overstated schedule sacrifice, and cross-program mileage ranking.
Parallel low admitted also misidentifies airline/program despite correct worker
findings; conditional/incomplete fail exact worker alias validation before a final
composer because a worker uses range strings. All evidence remains immutable.

The incomplete V1 medium reviewer considered an explicitly wrong-origin/date lead
a material relevance failure; an architect adjudicated pass with minor relevance
weakness because the answer explicitly denies a usable connection, consistently
with earlier review policy. Both reviews are preserved. The adjudicator records
incidental timing metadata exposure and does not claim complete timing blindness.

The architect recommends one narrow V2: exact per-reference identity/carriers and
unmodified traveler/seat reason records beside quotes; a brief for same-arrival
variants, source-supported connection-buffer arguments and program distinctions.
No pairwise matrix, scoring, new authority or semantic binding. V2 costs about 10%
more prompt bytes than original; it tests locality/quality, not compression.
Workers V2 require exact individual aliases and may use existing P1 only for the
whole eligible pool; no range repair/retry. V1 modules/protocol remain available.

The campaign records the revised schedule before new calls, preserving the 60/60
cap: reverse-order second medium cohort, matched V2 low/topology cohort, then a
repeat of the more promising configuration if the remaining bound permits its
full recovery path. Failed V1 low protocols are not repeated or pooled with V2.

## Final execution and decision evidence

Live calls stopped at **40 generations / 40 input counts**, below the declared
60/60 cap. There are 26 run directories, 23 selected final answers, 8 worker
generations, 8 correction generations, two explicit worker failures before
composition and one transport timeout without a final response/usage receipt.
No further live call is invoked by this closeout or unused ceiling.

Original/V1 medium each completed two three-case cohorts. V1 low completed one
cohort; V2 low completed one cohort with the same complete-answer target. V1
parallel completed one answer and failed two workers; V2 parallel was stopped
after its admitted sentinel still misstated the schedule. V2 medium then ran on
all three cases without further prompt changes; no repeat is claimed for V2.

Completed-answer medians: original medium 73.96s; V1 medium 30.53s; V1 low 19.62s;
V2 low 21.86s; V1/V2 parallel admitted 42.49/33.06s; V2 medium 75.96s. Timings
include preparation, counting, shared checks/resolution, actual bounded correction
and worker critical path; exclude upstream pipeline and final persistence/report.
The unmeasured timeout remains visible and outside numerical latency summaries.

V1 medium first cohort passed bounded source/composition review after adjudication,
but all three repeats failed with factual or material choice errors. Both low
single-composer cohorts fail the complete-answer target; V2 improves cited facts
in particular draws but misses meaningful comparison coverage. Parallel outputs
retain errors despite correct worker findings and add time/cost. V2 medium cited
facts pass; its admitted/incomplete relevance failures were adjudicated minor,
with original stricter reviews preserved. Its median does not improve on original.
The report displays initial and adjudicated results, not unanimous qualification.
V2 medium improves the incomplete case and lowers the overall mean (62.4s versus
82.4s), with mixed admitted/conditional comparisons; it is not uniformly slower.
Its one cohort does not establish a repeated general speed improvement.

Known estimated generation cost: **USD 0.919395920**, covering 39 returned usage
receipts at recorded October 25 rates; one timed-out generation remains unpriced.
7,625,093 input / 104,098 output tokens, including 68,911 reasoning tokens in
output. Count billing/native Codex excluded; this is not an invoice. No travel
provider or FX calls occurred.

See [decision report](../../evidence/results-stage/m2/structured/2026-10-25-latency-next-cut/README.md),
[metrics](../../evidence/results-stage/m2/structured/2026-10-25-latency-next-cut/metrics.json)
and [review classifications](../../evidence/results-stage/m2/structured/2026-10-25-latency-next-cut/reviews.json).
Agent recommendation: retain one composer and the development measurement/preservation
tools; cut parallel analysis, do not adopt low reasoning as a shared default, keep
V1/V2 input representations as unqualified candidates. This is a recommendation
for the owner's keep/cut decision, not an owner conclusion.

## Final verification and files

New experiment files are under
`evidence/results-stage/m2/structured/2026-10-25-latency-next-cut/`: candidate v1/v2,
source/inverse audits, versioned isolated harness, fake controls, exact requests,
counts, raw responses/usage, attempts/findings/resolved previews, source ZIPs,
call ledger, offline reporter, source reviews, adjudications and decision report.
Updated project state, ADR 0029/index and deferred G06/G08 dispositions. No runtime
source, shared script or existing test changed; no new runtime configuration or
canonical artifact version is adopted. Earlier evidence remains unchanged.

Fresh commands:

```bash
.venv/bin/python -m pytest -q tests/unit/test_results_structured.py tests/unit/test_structured_results_eval.py tests/unit/test_results_structured_cli.py
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-latency-next-cut/verify_harness.py
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-latency-next-cut/verify_candidate.py
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-latency-next-cut/verify_candidate_v2.py
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-latency-next-cut/summarize.py --verify
.venv/bin/ruff check evidence/results-stage/m2/structured/2026-10-25-latency-next-cut
git diff --name-only b4a8084 -- src scripts tests
git diff --check
```

Focused tests: **27 passed in 102.50s**. Harness controls and candidate audits pass;
strict offline verification accounts for all 26 runs, exact measured requests and
responses, archived snapshots and saved resolutions, including unavailable outcomes.
The first final strict check exposed a reporter count that incorrectly treated
the accounted timeout as unfinished; fixed with a terminal-failure control. Also
normalized absent/null original input version labels before grouping medians.
No live result was overwritten or reclassified by those reporting fixes.
Ruff/diff and local report links are checked before final delivery. The full suite
was not rerun; no historical gfly environment failure is claimed as a fresh result.

ADR disposition: amended 0029 and index with authorized experiment scope/results,
not new trust, eligibility, Ranking, recovery or runtime topology policy. Deferred
G06/G08 remain open for their claim-specific prerequisites. Owner latency and
presentation acceptance, frontend milestones and M3 remain separate. Final owner
keep/cut decision: **not supplied**.
