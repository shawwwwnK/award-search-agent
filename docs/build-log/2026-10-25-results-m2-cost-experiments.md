# Results M2 lower-cost candidate experiment

Date: 2026-10-25. Baseline commit: `b40b9fa`. Owner asks to retry Luna and try Terra
because the passing Sol configuration is too expensive for the intended use.

## Scope and operating envelope

No runtime, contract, Ranking or frontend change. Keep the passing Sol evidence and
original Luna failures unchanged. Test current committed source/input/brief with
model-only changes: GPT-6 Luna and GPT-5.6 Terra, medium reasoning as returned by
the API, default service tier. Same explicit numerical settings as the passing Sol
cohort. Each new candidate gets its own immutable campaign/ledger; admitted first,
independent review, then conditional/incomplete only for a passing sentinel. Maximum
six generations/six input counts per candidate, one cohort, two attempts per run.
No automatic retries, travel-provider calls, FX acquisition or global model adoption.

Official pricing was searched/fetched before choosing the candidate: Terra has the
same Standard input rate as GPT-6.1 Sol (USD2/M input,USD2.50/M 30m writes), a higher
output rate (USD12/M versusUSD10/M), and a higher cache-read rate. Terra is therefore
not assumed to be a cheaper intermediate model. Actual receipt-based cost estimates
must determine its value. User's requested named model is tested, not substituted.
Sources: https://developers.openai.com/api/docs/pricing and each model page.

## Sentinel review

Luna admitted: independent composition and source review pass for this sample.
Two meaningful economy schedule choices, integrated cash context, an exact referenced
business alternative and consolidated applicable limitations form a connected answer.
Every numerical comparison was independently recomputed (13h35m/1h25m/12h10m cash
contrast,11h30m departure/11h25m arrival/five-minute duration award contrast). All258
eligible IDs survive once in the explorer. The rest of the same-config cohort runs
next. No prompt or Sol-derived exemplar was added: this is a stochastic retest, not
a demonstrated correction or a stable-quality claim.

Terra admitted: inspected explicit source quantities and IDs reconcile, but the full
composition target does not pass. Limitations are scattered rather than consolidated,
and the dismissed business alternative lacks an exact journey reference. “Having
the evening” overstates a22:25 landing. Stop after sentinel rather than spend on a
full candidate cohort with no observed price advantage. These are two independent
native architect/investigator reviews, not a calibrated evaluation system.

## Complete-cohort results and review disagreement

Luna completed three cases with four generations/four counts, retaining one mechanical
correction for incomplete. Composition review passes for all three. Source quantities
reconcile, but the source reviewer rejects conditional's “quicker” wording because
selected economy/business tie. Architect adjudication considers this a minor ambiguity:
same departure/arrival and no faster business schedule are repeated immediately.
Parent retains the original source verdict, adjudication and unchanged output together;
no extra generation for wording polish. The admitted and incomplete source review pass.
This is not an unqualified unanimous factual pass or demonstrated repeatability.

Luna actual739,968 input/14,677 output tokens, of which10,846 reasoning. Estimated
costUSD0.09933602 versus reused Sol cohortUSD1.9009922 (94.77% less). Summed generation
latency233.23s versus113.47s; count latency is not recorded and this is not wall time.
Terra sentinel207,324 input/1,464 output, estimatedUSD0.5358765 versusSol admitted
USD0.5361585, so no useful cost reduction; it was faster17.22s in this one draw.

Total new experiment: five generations/five counts,947,292 input/16,141 output and
estimatedUSD0.63521252. Pricing includes default30-minute cache writes and excludes
unknown count-endpoint fees, native Codex billing and account-specific adjustments.
No price or latency ranking is generalized from these single saved-case draws.

## Verification and documentation

Shared evidence audit commands with candidate roots passed Luna9 andTerra3 fresh-
process archived-source replays at seeds11/23/37. Exact snapshots, raw responses,
reference binding, source/eligible/group identities, request/count/writer receipts,
usage and call reservations reconcile. Luna all three configs/snapshots match final
current source; both admitted sentinels differ from Sol only in model. Original
Sol/October24/compact evidence and runtime source are unchanged.

`summarize.py` recomputes costs and per-attempt metadata from raw receipts using
Decimal arithmetic; mypy/Ruff pass. A missing type annotation was fixed during
verification. Four previews preserve model prose unchanged with card insertion markers.
No runtime tests/full suite were rerun, because runtime code and schemas are unchanged;
previous test counts remain historical, not fresh claims for this experiment.
See [experiment evidence](../../evidence/results-stage/m2/structured/2026-10-25-cost-experiments/README.md).

## ADR / deferred / owner disposition

No ADR change is required: this is an explicitly authorized same-contract model
comparison, with no workflow, source trust, evaluation acceptance rule or default
model adopted. The current ADR index links the experiment without changing the
decision. G08 still excludes exhaustive narrative truth; the disagreement and prior
Luna variance remain visible. No feature is newly deferred or reopened. Owner
presentation acceptance, frontend milestones and M3 retain their separate scope.


## Independent accounting closeout

A native worker independently recomputed every attempt's cost using Decimal and
raw SDK cache/read/write/output token fields. All per-attempt and aggregate amounts,
count receipts and reservation ledgers match. No material accounting or reporting
finding was identified. Final local checks: summary-script mypy/Ruff passed; relative
file links passed (296 links across10 documents); credential scan found no key paths;
`git diff --check` passed. Runtime, tests and previous Sol/Luna evidence are unchanged
from baseline b40b9fa. Only this cost experiment's evidence/docs enter its commit;
the pre-existing October8 untracked owner work is excluded.
