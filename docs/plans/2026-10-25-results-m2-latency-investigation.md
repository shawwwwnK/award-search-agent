# Results M2 latency gap and proposed investigation

Date: 2026-10-25. Status: owner-reported responsiveness gap; investigation proposals
recorded, not implemented. The current instruction authorizes documentation and a
commit only. No new paid campaign, runtime change or frontend implementation follows.

## Owner finding and measured scope

After reviewing the Luna retry timing, the owner asked whether it measured sending
the API request through receiving the response, then said: “This is way too long.”
The measured delay is unacceptable to the owner for the intended interactive Results
step. A numerical latency target and an execution budget for corrective experiments
have not been supplied. A cheaper or composition-pass answer does not establish
acceptable responsiveness.

The timer in [the structured writer](../../src/award_agent/results/adapter.py) starts
before client/request construction and stops after the complete response returns,
its raw JSON is serialized and usage is extracted. It approximates client request-to-
full-response duration, including network/server time and small local SDK overhead.
It excludes the subsequent authored-document validation, token-count calls, workspace
resolution/checks and upstream request/search stages. It is not time to first token
or end-to-end application latency. Neither first-token nor first-usable-result timing
was instrumented. A complete answer may contain several journey recommendations;
this is not time per flight result.

[Luna retry receipts and metadata](../../evidence/results-stage/m2/structured/2026-10-25-cost-experiments/metadata.json)
record four generations across three completed answers:

| Saved case | Generations | Summed generation time |
| --- | ---: | ---: |
| Admitted | 1 | 90.71 s |
| Conditional | 1 | 72.75 s |
| Incomplete | 2, including bounded correction | 69.77 s |

The per-generation average is **58.31 seconds**. The mean summed generation time
per completed answer is **77.74 seconds**, excluding unmeasured count/local overhead.
The total 233.23 seconds is a sum across concurrent cases, not session wall time.
Fresh end-to-end execution would add upstream time that these saved-input runs do
not measure. The prior Sol cohort's 28.37-second mean is also per generation, not a
complete application timing or an owner-accepted latency target.

## Hypotheses, not diagnosed causes

Each Luna request used 171,065–207,324 input tokens and returned medium reasoning.
Reasoning accounted for 10,846 of 14,677 output tokens across the retry. Large input
and reasoning work are plausible investigation targets. The receipts do not separate
input processing, queueing, reasoning, output decoding or network contributions;
no dominant cause or expected speedup has been measured.

## Proposed next investigation

1. Measure generation request start/full response, token counting, local preparation/
   validation and full application completion separately. If evaluating streaming,
   distinguish first token from the first usable, correctly bound result. Incremental
   output alone does not establish a faster completed answer.
2. Test a smaller writer-facing representation. Preserve the full canonical evidence,
   every eligible journey as an exact selectable option, meaningful comparison scope,
   incomplete/cash distinctions and the independent complete explorer. Do not silently
   trim options or change Ranking to achieve a smaller prompt. Code-resolved card
   facts, unknowns and material limitations retain their settled ownership.
3. Test a lower reasoning budget against the unchanged composition and source-fidelity
   criteria. Capture exact request settings and returned usage. No reasoning setting
   or model default changes in this documentation session.
4. Compare cost, complete-answer latency and actual narrative quality on the same
   saved sources. Include bounded corrections in answer-level latency. Do not count
   mechanically clean output as semantic success or hide slower failed attempts.

These are candidate experiments, not an approved implementation recipe or a new
runtime orchestration framework. Preserve the passing Sol baseline and all Luna/Terra
outcomes, including the source-review disagreement and prior Luna variance. Numeric
prose remains model-authored under the current owner decision. A future implementation
or paid campaign needs its explicit scope/settings/bounds; no unused earlier campaign
budget is reused by this note.

## Milestones and evidence limits

This records an unresolved Results M2 interactive-readiness issue. Composition/cost
reviews do not close latency acceptance. Frontend M1/M2, owner presentation acceptance
and Results M3 remain separately scoped; no milestone sequence is silently changed.
The owner has not selected a numeric response-time threshold, a default model, a
streaming design or a specific input-reduction method.
