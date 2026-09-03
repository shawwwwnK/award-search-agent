# 2026-09-02: Pass 2 Contract v2 implementation

## Objective evidence

- Replaced Pass 2's model-facing canonical IDs and source offsets with request-local `e*`, `a*`,
  and `r*` handles; canonical mappings remain private deterministic state.
- Added a bounded decision wire, generated handle-enum Structured Output schemas, conservative
  plain-literal direct-anchor insertion (excluding relative-holiday wording), decision-output
  references, composition operators, and bounded
  unresolved reasons.
- Changed generated duration relations to reference the whole departure interval.
- Confirmed the representative Labor Day semantic graph resolves departure to 2026-09-03 through
  2026-09-07 and return to 2026-09-12 through 2026-09-18 in an offline fixture.
- Commands and test results are recorded in the implementation session handoff. No live model eval
  was run.
- Split coarse-extraction repair guidance from temporal-decision repair guidance; production Pass 2
  serialization now localizes or rejects nonlocal catalog handles, including repair payloads.
- Added deterministic transcript-local evidence coordinates for condensed-transcript conformance.
- Repaired Pass 2's local semantic context: the transcript now labels each ordered clause with its
  `e*` handle, Pass 1 is instructed to retain the endpoint cue in weekday alternatives, and each
  evidence entry supplies date-free `allowed_targets`. Conversion and conformance reject a decision
  whose target is not permitted by its selected evidence. The payload still omits claim labels,
  source offsets, canonical IDs, and all calendar context.
- Ran a network-enabled, full-corpus `gpt-4o-mini` two-pass regression after Contract v2:
  16 scenarios × 3 trials, 48 runs, output at
  `evals/intent/baseline/2026-09-02-gpt-4o-mini-pass2-contract-full-3-trials-worker-escalated.json`.
  The evaluator reported 3 passes, 6 completed failed checks, and 39 errors; first-attempt
  completion was 7/48 and final completion 9/48. It recorded 27 repairs with 2 successes,
  17 Pass 2 wire failures, 14 semantic-validation failures, and 3 deterministic-output
  failures. Total latency was 296.105 seconds; 126/126 calls supplied usage totaling 301,795
  tokens. Cost was not calculated.
- A sandboxed preliminary run could not reach the API and produced only `APIConnectionError`
  records; it is retained separately and excluded from the network-enabled result above.
- Independent artifact inspection confirmed all 16 scenario IDs had exactly three trials and
  identified 15 terminal `AssertionError` records without structured stage/code information.
  The artifact does not establish a model-selection comparison against pre-Contract-v2 runs.

## Owner interpretation

<!-- Project owner: record any product/architecture conclusion and next cut line here. -->
