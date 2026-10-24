# Results M2 structured-answer diagnostic — October 24

The owner authorized U1–U3 implementation, live evaluation and iteration. This
record uses the three saved October 20 projections; no travel-provider search or
saved-run FX refresh occurred. See [campaign scope/settings](campaign.json),
[implementation log](../../../../../docs/build-log/2026-10-24-results-m2-structured-implementation.md),
[code review](code-review.md) and [independent answer review](answer-review.md).

## Final inspected cohort

All three final cases use the same explicit [evaluated configuration](evaluated-config.json).
This is a tested development configuration, not an adopted default or broad model
context-fit claim. Each artifact retains the full source, eligible explorer,
prepared input, attempts, checks, raw writer receipts and resolved answer.

| Case | Source-eligible journeys | Final artifact | Resolved structured answer |
| --- | ---: | --- | --- |
| Admitted | 258 | [round 3 artifact](round-3/admitted/artifact.json) | [resolved facts/narrative](round-3/admitted/resolved.json) |
| Conditional | 232 | [round 3 artifact](round-3/conditional/artifact.json) | [resolved facts/narrative](round-3/conditional/resolved.json) |
| Incomplete | 0 | [round 3 artifact](round-3/incomplete/artifact.json) | [resolved facts/narrative](round-3/incomplete/resolved.json) |

The final selected artifacts have no failed checks. Cabin declarations in admitted
and conditional are **unchecked**, not deterministically supported, because their
propositions use prose instead of catalog identifiers. Independent source review
supports those statements; the distinction remains visible in findings.

The earlier material failures were corrected: missing business alternatives,
false absence of complete conditional journeys, wrong feeder airport association,
and an incompatible-date partial-route suggestion. The reviewer recommends retaining
two wording limitations without another generation: admitted calls an 11h30m
departure difference “slightly earlier,” and incomplete's “direct-route” cash
wording can be confused with nonstop even though its resolved route connects.
Owner presentation acceptance remains open; there is no claim of exhaustive prose
truth, traveler benefit, rendered frontend quality or Results M3 qualification.

## Calls, iteration and preservation

Nine saved runs across three rounds used **14 generations and 14 input-count
requests**, recording **2,308,185 writer input tokens and 36,919 output tokens**.
These are usage measurements, not billing estimates. The campaign cap was
18/18; every run allowed at most one correction and no automatic SDK retries.
The call ledger reserves each attempted request before invocation; exact requests,
counts, writer receipts and source archives remain under each case directory.

Round one exposed material semantic failures despite mechanical cleanliness.
Round two corrected those but exposed airport and lead-applicability problems.
Round three targeted those problems and then reran admitted under the final
shared guidance. Every earlier artifact/configuration remains unchanged.

Source-known lead dates required a factual-schema refinement: workspace/resolved
v2 carries component departure dates, while v1 retains its exact original shape.
Outer artifact V6/document v2/prepared v5 remain unchanged. Current replay supports
both nested versions. The new [replay audit](structured-replay.json) and
[verification summary](verification-summary.json) record exact accounting and
cross-process checks: **27 fresh-process replays passed** across all nine
artifacts at seeds 11/23/37. The [legacy matrix](legacy-replay/baseline.json) and
[after result](legacy-replay/after.json) preserve the same 15 passing checks and
three pre-existing V4 preparation mismatches across seeds 11/23/37; legacy artifact
bytes and strict response-schema digests are unchanged. No saved V3 artifact was
found in that inventory; generated tests cover its runtime version.

The live FX adapter smoke test recorded a sandbox tunnel 403 and an outside-sandbox
HTTP 403. See [first outage receipt](fx-adapter-smoke/acquisition.json) and
[outside-sandbox receipt](fx-adapter-smoke-escalated/acquisition.json). Both produced
explicit USD-only fallback; positive FX behavior is verified with supplied/fake
rates, not a successful live acquisition. Saved cases retain their original rates.

## Reproduction and later gates

The full repository suite finished with **926 passed, 99 skipped and two known
gfly environment failures**; it is not green. See the
[captured final output](full-suite-final-output.txt) and
[environment diagnosis](gfly-environment.txt). Scoped types (21 files), Ruff and
the changed Results/regression gates passed.

Offline preparation makes no model/count/provider/FX request:

```bash
.venv/bin/python scripts/run_structured_results_eval.py --case conditional --round 3
.venv/bin/python -m award_agent.cli.results replay --artifact evidence/results-stage/m2/structured/2026-10-24-luna/round-3/conditional/artifact.json --output /private/tmp/conditional-resolved.json
```

Replay output paths must be new. Running the evaluator with `--live` is a new paid
invocation and cannot overwrite a saved case directory. The existing campaign is
complete; its artifacts are evidence rather than instructions to spend its remaining
budget. [Acceptance preparation](acceptance-preparation.md) records expected facts
and criteria for later M3 opening. Frontend M1/M2 and owner rendered review retain
their accepted milestone boundaries.
