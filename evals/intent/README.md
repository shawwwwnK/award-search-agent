# Intent Evals

`one_way_award_behavior_cases_v1.yaml` is the disclosed development baseline for the active
ADR 0017 one-receiver initial-intent boundary. Its 19 action/property scenarios cover bounded
outbound forms, a recognizable typo, each required blocker, unbounded/ambiguous departure,
return/duration scope, cash-only/mixed eligibility, and the home-airport false-positive guard.
It scores observable actions, deterministic dates, mode/scope policy, grounding, and forbidden
outcomes—not an LLM proposal shape or a selector decision. The earlier v1/v2, round-trip, and
selector-era corpora and artifacts remain historical evidence only.

The runner refuses a corpus unless it has the `intent_behavior_v1` contract, exact
root/scenario/context/oracle shape, unique IDs and coverage families, and the full 19-scenario
behavioral denominator. Each public artifact records the exact fixture SHA-256 and scenario count.

Exact assertions are retained for deterministic dates, traveler count, and scope safety. The
action/property envelopes intentionally do not assert a receiver AST, operation spelling, evidence
segmentation, or generated prompt wording. Departure evidence is checked against the immutable
request spans; location values remain resolver candidates and are never airport-expanded.

Live-model evals and offline deterministic tests must be separable. Baseline results should be saved under `evals/intent/baseline/`.

Calendar arithmetic, graph validation, repair limits, and provenance are deterministic offline
tests. The live baseline measures the configured receiver's final action/property outcome without
turning ordinary user-language ambiguity or a recognizable typo into an error pass.

Failing cases should be preserved and investigated rather than deleted. Evaluation should drive architecture changes rather than merely produce a score.

## Live baseline runner

Run only scenarios marked `status: ready` and save the full structured output:

```bash
python -m award_agent.cli.intent_eval \
  --model gpt-5.6-luna \
  --trials 3 \
  --output evals/intent/baseline/YYYY-MM-DD-intent-behavior-v1-3-trials.json
```

The runner scores action/property oracles and keeps individual failures and errors from aborting
the corpus. The OpenAI adapter records response usage when the SDK provides it, but the runner does
not calculate cost.

For failure triage, the runner writes private per-case model-call sidecars for every trial by default under
`evals/intent/traces/`:

```bash
python -m award_agent.cli.intent_eval \
  --model gpt-5.6-luna \
  --trials 3 \
  --output evals/intent/baseline/YYYY-MM-DD-intent-behavior-v1-3-trials.json
```

Every case gets a sidecar containing the exact model instructions, serialized input,
structured-output schema, parsed output, SDK response JSON when available, and exception details for
the semantic receiver and its optional repair call. The baseline JSON references each sidecar and
records the trace directory. The public baseline is redacted: it contains only scenario/trial
outcomes, action/check names, public failure classifications, metrics, and private-sidecar
references—not raw requests, model output, assertion values, or error text. Use `--trace-dir PATH`
to override the location or `--no-trace` to disable
sidecars for a privacy-sensitive run. These traces may contain
private travel requests and evidence quotes; keep the directory access-controlled and do not commit
it unless that disclosure is intentional.

The active runner has one semantic receiver. `--model` configures that receiver; there is no
selector-model, scanner, strategy flag, or hidden candidate fallback. Schema-v9 artifacts identify
`architecture: one_llm_semantic_receiver` and report payload-free `semantic_receiver` telemetry.
`--no-trace` prevents sidecar writes while retaining telemetry. A model/adapter failure must not
pass an ordinary-language action/property case; a future typed pending result is only eligible when
the fixture explicitly permits it.

Selector-only results and earlier round-trip artifacts are historical evidence. They do not qualify
the current one-receiver boundary. The next live record must use the behavioral v1 corpus and
record its fixture hash; do not compare pass rates across contracts.

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
