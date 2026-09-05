# 2026-09-04: Selector-contract v2 evaluation

## Objective evidence

- Investigation of the initial frozen study found that several oracle decisions depended on
  date-free local meaning absent from the selector projection: explicit endpoint cues, relation
  ordinals, and anchor/composition semantics.
- Implemented a versioned v2 public selector contract. It adds sentence-local explicit endpoint
  cues, safe relation kind/ordinal fields, lossless candidate summaries, and explicit prompt rules
  for anchor modes, composition, dependencies, ordering, and unsupported seasons. It preserves
  opaque handles and excludes resolved dates, request context, source offsets, canonical IDs,
  private reasons, and oracle outputs. The v1 fixture remains retained for comparison.
- The first v2 matrix artifact was invalid for semantic comparison: its sandboxed process could not
  reach the API, causing all model calls to fail before parsing. A one-call network-enabled trace
  confirmed the v2 Structured Output boundary parsed normally; that artifact is retained only as
  diagnostic evidence.
- The valid v2 one-trial probe and three-trial confirmation compared `gpt-4o-mini` and
  `gpt-5.6-luna` over twelve order-balanced scenarios. Luna achieved 36/36 semantic selections,
  complete parse/membership/compiler checks, all class and unsupported gates, and zero repairs.
  Mini achieved 16/36 semantic selections and two dependency compiler errors, so it remains below
  the gate.
- Relative to the v1 one-trial baseline, Luna improved from 8/12 (66.7%) to 36/36 (100%) in the
  v2 three-trial confirmation. Mini remained below the gate, from 6/12 (50.0%) to 16/36 (44.4%).
  The coupled payload and prompt intervention supports the v2 contract, but does not isolate a
  single causal field.

## Artifacts

- v1 baseline: `evals/selector/baseline/2026-09-04-gpt-4o-mini-vs-gpt-5.6-luna-1-trial.json`
- invalid sandbox diagnostic: `evals/selector/baseline/2026-09-04-gpt-4o-mini-vs-gpt-5.6-luna-v2-1-trial.json`
- valid v2 probe: `evals/selector/baseline/2026-09-04-gpt-4o-mini-vs-gpt-5.6-luna-v2-network-1-trial.json`
- v2 confirmation: `evals/selector/baseline/2026-09-04-gpt-4o-mini-vs-gpt-5.6-luna-v2-network-3-trials.json`
- matched GPT-4.1 comparison: `evals/selector/baseline/2026-09-04-gpt-4.1-mini-vs-gpt-4.1-v2-network-3-trials.json`
- matched GPT-5.4 Mini / GPT-5.6 Terra comparison:
  `evals/selector/baseline/2026-09-04-gpt-5.4-mini-vs-gpt-5.6-terra-v2-network-3-trials.json`

## Additional model comparison

- Ran the same v2 fixture for three trials with `gpt-4.1-mini` and `gpt-4.1`. Both parsed,
  restored, and compiled all 36 runs with zero repairs, but neither passed the semantic gate.
- `gpt-4.1-mini` selected 25/36 oracles (69.4%). It was 1.057 seconds and 739.5 tokens per
  request, but failed scope (1/6) and unsupported-to-unresolved (0/6).
- `gpt-4.1` selected 29/36 oracles (80.6%). It was 0.806 seconds and 739.5 tokens per request,
  but failed all composition cases (0/6) and one unsupported case (5/6).
- The same validated Luna run selected 36/36 with every class at 6/6; it averaged 1.781 seconds
  and 804.5 tokens per request. Luna remains the sole model qualified for the next E2E experiment.

## GPT-5.4 Mini and GPT-5.6 Terra comparison

- Ran the same frozen v2 fixture for three network-enabled trials (36 requests per model) with
  `gpt-5.4-mini` and `gpt-5.6-terra`. The artifact retains the v2 fixture SHA-256 and per-run
  metrics; both arms had complete parse, membership, compiler-completion, usage capture, and zero
  repairs.
- `gpt-5.4-mini` achieved 25/36 semantic selections (69.4%), averaging 1.042 seconds and 746
  tokens per request. It failed all composition cases (0/6), half the scope cases (3/6), and two
  unsupported-to-unresolved cases (4/6), so it failed the existing quality gate.
- `gpt-5.6-terra` achieved 36/36 semantic selections, every class at 6/6, and 6/6
  unsupported-to-unresolved selections. It averaged 1.663 seconds and 761.8 tokens per request,
  passing every existing quality-gate check. It is roughly 6.6% faster and uses roughly 5.3% fewer
  tokens per request than the earlier validated Luna run, but those measurements were taken in
  separate live runs and do not establish a tail-latency or cost decision.
- The current selection evidence therefore qualifies Terra alongside Luna for the next
  selector-enabled compiler E2E experiment. It does not enable the selector by default or choose
  between the two models.

## Deferred default-model decision

- Added `docs/experiments/selector-model-choice-protocol.md`. It requires an immutable
  configuration/pricing record, independent semantic holdout, metamorphic/adversarial safety
  suite, test-only selector-path integration corpus, and repeat-day operational/cost confirmation
  before a production-default decision. The existing 12-stem v2 fixture remains a development
  screen, not the final holdout.

## Project-owner selector-model decision

- The project owner selected `gpt-5.6-luna` for future selector-enabled experiments. The stated
  basis is its passed v2 gate and substantially lower published token prices than Terra; the
  selector remains disabled by default and this is not a final production-default decision.
- Terra is retained as a passing comparison result. `gpt-5.4-mini`, `gpt-4.1-mini`, `gpt-4.1`, and
  `gpt-4o-mini` remain unqualified because they failed the frozen v2 quality gate.

## Commands and verification

- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.frozen_selector_eval --mini-model
  gpt-5.4-mini --luna-model gpt-5.6-terra --trials 3 --output
  evals/selector/baseline/2026-09-04-gpt-5.4-mini-vs-gpt-5.6-terra-v2-network-3-trials.json`
  — live frozen study; the process exited nonzero because the `mini` arm correctly failed its
  quality gate, while the artifact is complete and valid.
- `jq -e` checked schema version, v2 fixture contract, scenario/trial counts, and 36 calls per
  model in the saved artifact.
- `git diff --check` — passed after documentation updates.

## Next evidence needed

- Run the selector-enabled compiler end-to-end matrix only with an explicitly configured passing
  model (`gpt-5.6-luna` or `gpt-5.6-terra`); do not enable a selector by default based on this
  frozen study alone.
- Keep `gpt-4o-mini`, `gpt-4.1-mini`, `gpt-4.1`, and `gpt-5.4-mini` out of selector experiments
  until their failed semantic classes have improved and they pass the current gate.

## Owner interpretation

<!-- Project owner: record product/architecture conclusion and the next cut line here. -->
