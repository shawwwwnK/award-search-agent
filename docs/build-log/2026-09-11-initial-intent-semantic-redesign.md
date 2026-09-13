# 2026-09-11: Initial-intent semantic redesign

## Implemented boundary

Implemented ADR 0017's replacement for the live initial intent workflow:

- One semantic model receiver reads the complete request; the active path does not import or call
  the temporal scanner, candidate builder, or opaque selector.
- The receiver emits quoted semantic facts and reusable calendar operations. Deterministic code
  validates source grounding, computes calendar dates, detects conflicts, and applies ADR 0016
  one-way and cash policy.
- Recognized return/duration scope and cash-only intent are grounded independently and remain
  explicit unsupported outcomes even when an unrelated outbound fact is malformed. Mixed intent
  remains award-eligible.
- Blank input completes as missing-field clarification. Normal user language never leaks a raw
  exception or pending result: typos, recognizable paraphrases, and provider-wire
  representation/shape noise must be internally normalized/repaired into `ready`, `clarification`,
  or `unsupported`. If an inference-reached model result remains unusable after repair, it
  completes as clarification with salvaged facts and explicit blockers. Only genuine preflight,
  authentication/configuration, network/transport, or provider operational failures become a
  non-session `pending_retryable` outcome.
- The OpenAI repair payload includes the rejected proposal and typed validation issues. Provider
  traces bind the adapter version and the exact SDK strict response-schema hash.
- Active CLI, local harness, combined evaluator, corpus, and telemetry use one receiver and have
  no `--selector-model` option. Historical selector tests are explicitly marked historical.

## Verification

- `.venv/bin/pytest -q` — 251 passed, 99 historical skips.
- `.venv/bin/ruff check .` — passed.
- Focused semantic/evaluator suite — 28 passed.
- Clarification boundary smoke — 2/2 passed.
- Strict provider-schema smoke — passed; SHA-256
  `b84d14a5471fd43b7955aba413989215a86552f3a6d8325fc2ed48e444a9fc92`.
- `git diff --check` — passed.

## Live diagnostic

Command:

```text
PYTHONPATH=src .venv/bin/python -m award_agent.cli.intent_eval --model gpt-5.6-luna --trials 3 --output evals/intent/baseline/2026-09-11-intent-behavior-v1-gpt-5.6-luna-3-trials-redesign.json
```

The 19-scenario corpus ran for three trials: 57 runs, 8 passed, 49 behavioral failures, and zero
workflow errors. Forty-six runs reached `pending_retryable` because the model's structured
proposals failed post-inference Pydantic validation. Under the revised contract, these
inference-reached shape failures are not acceptable pending outcomes: after the one repair they
must complete as clarification with salvaged facts and explicit blockers. All 57 private trace
sidecars and calls reconciled; public-artifact redaction inspection passed. This is diagnostic
evidence, not a behavioral-qualification result.

## Remaining evidence

The live diagnostic indicates that the receiver's closed structured proposal contract/prompt needs
investigation before a qualification attempt. The high post-inference pending count is a
release-blocking contract violation, not an acceptable user outcome, where structured-proposal
shape defects followed otherwise reasonable requests; the required disposition is completed
clarification with salvaged facts after repair. No owner conclusion or next-cut decision is recorded
here.

## Local Streamlit harness alignment

- Updated the local harness presentation for the active initial-intent boundary: it identifies
  ADR 0017 semantic interpretation while retaining ADR 0016 one-way award guidance, exposes one
  initial semantic-intent model rather than selector configuration, and labels imported initial
  results as ADR 0017 output.
- A typed initial `pending_retryable` result remains sessionless as required for genuine operational
  failures only. The harness preserves the original request and date context locally, displays only
  a stable stage/code status, and offers a user-triggered retry. Raw provider, model, and validation
  detail remains private and no clarification session is created. Representation/shape noise is
  expected to be repaired and, if still unusable, completed as clarification with salvaged facts;
  it is not a valid pending reason.
- Follow-on harness checks cover pending context retention, generic presentation, and retry
  affordance: `PYTHONPATH=src .venv/bin/pytest -q tests/unit/test_clarification_harness.py` — 12
  passed. Ruff checks for the harness/test files and `git diff --check` also passed. Full-suite and
  live verification remain to be recorded after parent integration.

## Reasonable-input reliability gate

The provider contract was revised to fixed wire-v2 arrays with structural conversion and a
one-repair semantic boundary. A yearless literal month/day is an explicitly supported semantic
form: the receiver emits `start_year: 0`, and deterministic code selects the next occurrence from
the immutable request context. An initial response that marks such a date unresolved receives the
same bounded model-owned semantic reconsideration; genuine ambiguity and unbounded timing remain
clarification.

Commands and results:

- `.venv/bin/python -m pytest` — 273 passed, 99 historical skips.
- `.venv/bin/ruff check .` — passed.
- `git diff --check` — passed.
- Ten live trials of `Find two business award seats from SFO to BKK on October 5.` with reference
  date `2026-08-30`, timezone `America/Los_Angeles`, and `gpt-5.6-luna` — 10/10 ready. Each result
  had SFO → BKK, two travelers, business award, and an exact `2026-10-05` departure; there were no
  repairs, pending outcomes, errors, blockers, unsupported parts, or active return/duration state.
  Private artifact: `/private/tmp/award-search-exact-gate-10.json`.

This is a narrow exact-request reliability gate, not a replacement for a refreshed broad live
behavioral matrix.
