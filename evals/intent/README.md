# Intent Evals

These scenarios will become an executable golden set.

Exact checks should be used for schema and deterministic behavior. Invariants should be used where multiple valid semantic representations exist.

Temporal evidence is evaluated per typed claim rather than as an exact set of preferred phrases.
Executable fixtures use `evidence_expectations` with exact allowed envelopes, required-all
fragments, required-any groups, and optional preferred spans. Fixture strings compile to Python
start-inclusive/end-exclusive offsets before scoring; missing or ambiguous fixture strings fail
loading. Candidate evidence remains subject to strict exact-substring grounding, must fit one
common envelope for its linked claim, and must cover the claim's required fragments. Preferred span
agreement is recorded only as a prompt-quality diagnostic and does not determine case success.

Location `raw_text` is verbatim evidence. Location `value` is a model-proposed normalized name
candidate until a deterministic location resolver exists; it is not a stable identifier or an
authoritative display name. Instead of one exact `value`, a golden may use `accepted_values` to
enumerate semantically equivalent candidate strings. The scorer performs exact membership only and
never fuzzy matching.

Live-model evals and offline deterministic tests must be separable. Baseline results should be saved under `evals/intent/baseline/`.

Temporal evaluation is split by responsibility. `temporal_relations` expectations partially match
typed semantic invariants such as kind, target, reference, direction, ordinal, weekday, and unit;
they intentionally ignore equivalent evidence-span segmentation and unlisted trace fields. Final
`departure_window`, `return_window`, duration, conflict, and clarification checks score the
deterministic evaluator and end-to-end workflow separately. Calendar arithmetic belongs in offline
unit tests rather than live-model scoring.

Failing cases should be preserved and investigated rather than deleted. Evaluation should drive architecture changes rather than merely produce a score.

## Live baseline runner

Run only scenarios marked `status: ready` and save the full structured output:

```bash
python -m award_agent.cli.intent_eval \
  --model gpt-4o-mini \
  --trials 3 \
  --output evals/intent/baseline/YYYY-MM-DD-gpt-4o-mini-3-trials.json
```

The runner scores explicit structured expectations and keeps individual failures and errors from
aborting the corpus. Free-text invariants are retained in the artifact for human review but are not
included in the automatic pass rate. The OpenAI adapter records response usage when the SDK
provides it, but the runner does not calculate cost.

For failure triage, the runner writes private per-case model-call sidecars by default under
`evals/intent/traces/`:

```bash
python -m award_agent.cli.intent_eval \
  --model gpt-4o-mini \
  --trials 3 \
  --output evals/intent/baseline/YYYY-MM-DD-gpt-4o-mini-3-trials.json
```

Every non-passing case gets a sidecar containing the exact model instructions, serialized input,
structured-output schema, parsed output, SDK response JSON when available, and exception details for
each initial and repair call. The baseline JSON references each sidecar and records the trace
directory. Use `--trace-dir PATH` to override the location, `--trace-all-calls` to capture passing
cases too, or `--no-trace` to disable sidecars for a privacy-sensitive run. These traces may contain
private travel requests and evidence quotes; keep the directory access-controlled and do not commit
it unless that disclosure is intentional.

Use `--strategy one_pass` for the deliberately naive experiment arm. It sends only the raw request
and context to one model call and asks directly for `RequestUnderstandingResult`; it does not run
the production workflow's extraction, enrichment, temporal validation, conflict, or clarification
stages. The golden expected values are used only by the scorer after generation and are never sent
to the model.

`--strategy compiler_select_v1` is the opt-in end-to-end compiler arm. It constructs the strict
non-temporal Pass 1 boundary and never constructs a live Pass 2 resolver. Supply
`--selector-model MODEL_ID` only to enable the optional date-free selector for genuinely ambiguous
compiler groups; it is independently configured from `--pass-one-model`. `--pass-two-model` is
rejected for this strategy, as are selector model flags for `two_pass` or per-stage flags for
`one_pass`. Schema-v5 artifacts retain the existing run totals and add per-run and aggregate
`stage_telemetry` for Pass 1, selector, Pass 2, and one-pass: enabled/configured/model, attempts,
latency, and SDK usage. `--no-trace` prevents sidecar writes but still retains this payload-free
telemetry. Selector failures use the public `temporal_candidate_selector` stage and stable codes;
they are not reported as legacy Pass-2 wire failures.

## Frozen selector study

The date-free temporal-candidate selector has a separate frozen study. It does not run Pass 1,
the legacy Pass 2 resolver, the request-understanding workflow, or a live holiday provider. Its
checked-in inputs live in `evals/selector/frozen_cases.yaml`; the private manual catalog registry
is rebuilt before each run and must reproduce every public projection exactly. The fixture pairs
reverse candidate order and cover target, reference, composition, anchor scope, dependency
closure, and unsupported-to-unresolved choices.

Run all control/model arms with explicit IDs (the runner does not assign a model ID to either
label):

```bash
python -m award_agent.cli.frozen_selector_eval \
  --mini-model YOUR_MINI_MODEL_ID \
  --luna-model YOUR_LUNA_MODEL_ID \
  --trials 1 \
  --output evals/selector/baseline/YYYY-MM-DD-selector-study.json
```

The `none` control sends no selector request and chooses the conservative unresolved candidate.
Artifacts report parse, membership, validation/compiler completion, semantic and per-class
accuracy, unsupported-to-unresolved accuracy, zero repairs, latency, independently counted
selector call attempts, and SDK usage availability. Exception text is not retained in the public
artifact; failures use public stage/code classifications so private candidate and production-slot
identifiers cannot leak.

Each artifact also evaluates Mini and Luna independently against the handoff gate: 100% parse,
membership, and compiler completion; at least 95% semantic accuracy; at least 90% target,
reference, composition, and scope accuracy; 100% unsupported-to-unresolved accuracy; and zero
repairs. The `none` control is comparison-only and is not gate-eligible. The CLI exits nonzero
when either model arm fails that quality gate. Public fixture projections contain no resolved
date, request context, source offsets, canonical IDs, or private restoration handles; result
records retain public candidate handles only.
