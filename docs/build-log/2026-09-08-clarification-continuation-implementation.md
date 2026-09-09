# 2026-09-08: Clarification-continuation implementation

## Objective evidence

- Added the additive `award_agent.clarification` boundary approved by ADR 0011;
  the frozen `RawRequest -> ParsedRequest -> ClarificationDecision` workflow was
  not changed.
- Added immutable, append-only session contracts with an initial snapshot,
  revision ledger, all-blockers prompts, answer-message spans, typed
  amendments, accepted/rejected outcomes, source-keyed temporal contributions,
  and provenance checks.
- Added deterministic all-blocker collection and one-message template rendering.
- Added a narrow answer-interpreter protocol and an answer-only temporal
  normalizer that uses the original request context.  It does not call the
  initial scanner/compiler.
- Added controller operations for starting a session and applying an answer,
  including optimistic concurrency, exact message-ID replay, cancellation,
  partial valid-amendment application, no-progress/turn limits, explicit
  unsupported-revision stopping, and recomputation of blockers.
- The requested cut line is preserved: no continuation golden-evaluation corpus
  or Streamlit application was generated.

## Verification

- `.venv/bin/pytest -q` — 290 passed.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/mypy src tests` — passed.
- `git diff --check` — passed.

## Review observations

- An independent Step-1 review found that Pydantic frozen models were only
  shallowly immutable.  The session boundary now round-trips nested models,
  returns defensive copies for mutable nested values, validates the initial
  projection, and verifies answer-derived provenance against retained typed
  amendments.
- The review did not identify a reason to alter ADR 0011's separate
  continuation-boundary architecture.  The implementation keeps this work out
  of `award_agent.intent`.

## Offline continuation qualification

- Added the separate synthetic/redacted corpus at
  `evals/clarification/cases_v1.yaml`, with 28 trajectories and 41 controller
  operations.  It does not alter the frozen `evals/intent` corpus.
- Added a strict preflight and deterministic public-controller evaluator plus
  the `award-clarification-continuation-eval` CLI.  Its artifacts retain only
  case labels, check results, stable error classes, and aggregate metrics.
- The trajectory set exercises all-at-once and subset completion; bare dates,
  durations, corrections and conflicts; invalid/unsupported sibling fragments;
  cancellation and limits; stale/wrong/replayed commands; duplicate field
  writes; and injected interpreter, grounding, temporal, and reducer failures.
- Controller review resulted in localized hardening: a correction may only
  revise an already-resolved supported field, competing same-field amendments
  are rejected, non-temporal values require literal span support, a pending
  prompt exactly covers current blockers, and `ready` requires none.  The
  no-progress fingerprint excludes provenance-only changes.
- Architecture review found that the answer-interpreter protocol unnecessarily
  exposed concrete request reference date/timezone.  The model-facing input now
  contains only answer identity/text and typed blockers; the retained original
  context remains controller/normalizer-only.  A schema regression test locks
  this boundary.

## Offline evaluator result

- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.clarification_continuation_eval --output /private/tmp/clarification-continuation-eval.json`
  completed 28 scenarios / 41 turns: 41 passed, 0 failed, exact gate passed.
  The eight reported errors are expected negative-path fixtures; their ledger
  non-mutation checks passed.  No model or provider calls were made.
- Post-evaluator checks: `.venv/bin/pytest -q` — 294 passed;
  `.venv/bin/ruff check .`, `.venv/bin/mypy src tests`, and `git diff --check`
  all passed.

## Offline-evaluator oracle hardening

- Replaced the circular accepted-amendment summary with independently declared
  per-turn acceptance oracles.  The evaluator now reports expected, actual,
  and matched accepted-amendment identities, targets, and requirement links;
  the scripted proposal is no longer used as the expected acceptance set.
- Each synthetic trajectory now also carries a checked-in SHA-256 oracle for
  its redacted complete final projection.  The evaluator fails the final turn
  if the semantic/provenance projection drifts, while retaining the projection
  itself in the local artifact for diagnosis.
- Focused qualification: the offline evaluator completed 28 scenarios / 41
  turns with 41 passed, 0 failed, 38 expected/actual/matched accepted
  amendments, and the exact gate passed.  Focused pytest and Ruff checks
  passed.  This remains offline deterministic evidence, not live-model
  qualification.
- Follow-up review hardening expanded every non-empty accepted-amendment oracle
  to exact normalized target-specific payloads (location kind/value, traveler
  count, or temporal text) and the correction flag.  Answer spans remain
  independently grounded to the processed message.  Prompt-coverage reporting
  now derives only from the independently recomputed ordered blocker set and
  prompt contents; unrelated outcome or projection failures cannot change that
  metric.

## Owner interpretation

<!-- Project owner: record whether the offline continuation implementation is
ready to proceed to the separate golden trajectory corpus, and define the next
cut line. -->

## Live clarification qualification and trace policy

- Added the separate synthetic live corpus at `evals/clarification/live_cases_v1.yaml`, a
  least-authority `gpt-5.6-luna` answer interpreter, a redacted live evaluator, and the local
  Streamlit validation harness. The adapter receives only answer identity/text and active typed
  requirements, uses Responses structured output with `store=False`, and leaves calendar context
  and effective state deterministic-only.
- Every live-evaluator invocation now captures all model calls by default into private,
  gitignored `evals/clarification/traces/run-*` sidecars. Public artifacts retain only redacted
  aggregate telemetry and trace-run metadata. A regression test prevents usage aggregation from
  clearing pending trace records.
- The first traced attempt exposed trace-buffer clearing and evaluator-accounting defects. Those
  were corrected before the final run; the final artifact below is the qualification evidence.
- Final live run:
  `PYTHONPATH=src .venv/bin/python -m award_agent.cli.clarification_live_eval --model gpt-5.6-luna --trials 3 --output evals/clarification/baseline/2026-09-09-gpt-5.6-luna-3-trials-final.json`
  completed 36/36 correct terminal outcomes, 45/45 exact remaining-blocker sets, zero
  unauthorized mutations, zero system errors, and 36/36 convergence within the turn budget.
  Its 42 successful Luna calls used 42,939 input tokens and 6,515 output tokens over 96.394
  aggregate seconds. The live gate passed.
- Post-change verification: `.venv/bin/pytest -q` — 304 passed; `.venv/bin/ruff check src tests
  apps`, `.venv/bin/mypy src tests`, and `git diff --check` passed.

## GPT-4o mini comparison

- The matching traced three-trial `gpt-4o-mini` run at
  `evals/clarification/baseline/2026-09-09-gpt-4o-mini-3-trials-final.json` did **not** qualify:
  27/36 correct terminal outcomes and 31/45 exact remaining-blocker sets. It had zero
  unauthorized mutations, but nine explicit system-validation failures.
- All 37 GPT-4o mini API calls completed successfully. Private all-call trace inspection found
  the failures were semantic contract violations: multi-field answers linked one typed amendment
  to incompatible requirement IDs (for example, both origin and destination), which the
  deterministic interpreter validator correctly rejected. This is evaluation evidence, not an
  API, storage, or trace-capture failure.

## Local Streamlit harness completion (2026-09-09)

- Completed `apps/clarification_harness.py` as an ephemeral ADR 0011 validation surface. It
  validates pasted frozen `RequestUnderstandingResult` JSON before calling
  `start_clarification()`, and renders the deterministic next prompt plus its exact typed blocker
  records, revision status, terminal reason, and a collapsible session JSON view.
- The only answer transition path constructs `ClarificationAnswerCommand` from the current session
  ID, revision, prompt ID, and a deterministic session-scoped local message ID. It creates the
  explicitly selected `OpenAIClarificationAnswerInterpreter` and calls
  `apply_clarification_answer()` only inside an explicit Streamlit form-submit branch. Ordinary
  reruns cannot invoke the model or modify the session.
- Start-input validation, controller failures, and interpreter failures are retained in
  `st.session_state` and leave the previously stored session unchanged. The UI owns no workflow
  reduction or persistence. The existing adapter remains the sole model boundary and uses
  Responses storage disabled.
- Added structural harness tests for deterministic message IDs and the lazy Streamlit import, so
  Streamlit remains an optional dependency.

## Harness verification (2026-09-09)

- `.venv/bin/pytest -q tests/unit/test_clarification_harness.py tests/unit/test_clarification_controller.py tests/unit/test_clarification_openai_interpreter.py tests/unit/test_clarification_session_contracts.py` — 19 passed.
- `.venv/bin/python -m py_compile apps/clarification_harness.py` — passed.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/mypy src tests` — passed.
- `git diff --check` — passed.

## Model decision

- The project owner selected `gpt-5.6-luna` as the clarification-stage LLM model. The live
  continuation adapter is configured explicitly with Luna; GPT-4o mini is retained as failed
  comparison evidence and is not a runtime fallback. The decision affects only the narrow
  answer-interpreter adapter and leaves all deterministic continuation ownership unchanged.
