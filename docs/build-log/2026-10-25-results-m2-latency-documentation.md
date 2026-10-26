# Results M2 latency documentation

Date: 2026-10-25. Starting commit: `43a1aa2`.

## Owner request and scope

The owner confirmed that the observed metric was roughly API request to full
response, rejected the delay as too long, then requested documentation and a commit.
This session records that finding and the proposed investigation. No runtime code,
model setting, provider/search behavior or paid evaluation is changed or run.

## Evidence inspected

Read current project state and relevant ADR 0029/composition/cost records. Inspected
OpenAIStructuredResultsWriter.author in results/adapter.py: timer starts before client/
request construction, includes the full response and raw-response serialization/usage
extraction, then stops before authored-document parsing. Token counting, downstream
validation, upstream searches and first-token timing are outside this measurement.

Recomputed from the immutable cheaper-model metadata: Luna four generations across
three answers, 233.227873 seconds total generation time. Per generation mean 58.306968
seconds; per completed answer mean 77.742624 seconds. Admitted 90.710089 seconds,
conditional 72.752512 seconds, incomplete 69.765272 seconds across two generations.
Summed concurrent-case time is not session wall time. Requests contained 171,065–
207,324 input tokens; reasoning contributed 10,846 of 14,677 output tokens. Neither
large context nor reasoning is established as the dominant latency cause by these
measurements.

## Documentation changes

Added a latency investigation note with measurement boundaries, owner rejection,
proposed experiments and preservation requirements. Project state, API usage, the
composition plan and AGENTS link the unresolved latency gap. ADR 0029 and its index
record the evidence/acceptance clarification, not a new architecture decision.
G06 and the deferred-register history distinguish responsiveness from operational
attempt/deadline guarantees. No numeric target, default, optimization implementation,
new live budget or milestone-sequence change is inferred.

## Verification

Verified all 326 relative file links across nine changed/new Markdown documents
(file existence, not heading anchors). Recomputed the 58.31/77.74-second means and
90.71/72.75/69.77-second case totals from saved metadata; all match the note. Verified
no source, script, test or evidence modification. `git diff --check` passed. Runtime
tests are not rerun for this documentation-only change; historical test results are
not claimed fresh. Prior unrelated untracked October8 owner work is excluded from
this commit.
