# 2026-09-08: Clarification-continuation implementation

## 2026-09-10: Single-call receiver and ordered date-pair repair

### Objective evidence

- The project owner rejected the separate post-reduction prompt-composer model
  call because of sequential latency. ADR 0013 records the resulting runtime
  decision.
- The controller now makes no composer call. The initial prompt is
  deterministic; after an answer, receiver-returned question items are used
  only when their ordered IDs exactly equal the deterministically recomputed
  remaining blockers. Any mismatch falls back to issue-specific deterministic
  copy without another model request.
- The answer receiver schema now returns those optional follow-up items in its
  original interpretation response.
- The continuation temporal normalizer accepts exactly two concrete dates
  joined by `and` or `then` as departure then return/duration when both date
  blockers are active and the receiver targets the narrow facts accordingly.
  Alternatives, extra facts, cross-sentence input, and swapped targets remain
  rejected. If the receiver conservatively rejects that exact closed grammar,
  the controller deterministically recovers its two answer-grounded typed
  amendments instead.
- The local Streamlit harness no longer exposes or constructs a prompt
  composer. A submitted clarification answer constructs only the answer
  interpreter.

### Verification

- `.venv/bin/pytest -q` — 412 passed.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/mypy src tests` — passed.
- `git diff --check` — passed.

### Live evaluation

- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.clarification_live_eval --model gpt-5.6-luna --trials 3 --output evals/clarification/baseline/2026-09-10-gpt-5.6-luna-3-trials-single-call-worker.json`
  exited successfully. The redacted artifact records 48/48 terminal-correct
  sessions, 60/60 exact blocker checks, 60/60 prompt-coverage checks, zero
  system errors, and a passed live gate.
- The private trace audit contains 57 `clarification_answer_interpretation`
  calls across 48 sidecars. Three cancellation turns required no model call;
  zero prompt-composer calls occurred.

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

## Two-stage local harness refinement (2026-09-09)

- Added a raw-request form to the local harness. Its explicit submit event composes only public
  frozen initial-workflow APIs (`RawRequest`, `RequestContext`, `OpenAIIntentExtractor`,
  `NagerHolidayProvider`, and `understand_request`) with `start_clarification()`. The existing
  pasted-frozen-JSON path remains available for replay.
- The three model selections (initial extraction, temporal selector, and clarification answer)
  are explicit. The app performs no model work during ordinary reruns. The initial path can use
  the existing Nager calendar boundary when a request names a U.S. federal holiday, but it adds no
  travel search or inventory provider call.
- Answer forms no longer clear before a successful transition. Errors are both retained in
  `st.session_state` and rendered in the same rerun, so model/controller failures leave the prior
  revision visible with the submitted answer intact.
- The harness now loads the local ignored `.env` through the existing `python-dotenv` dependency,
  matching the CLI convention. Credentials remain outside source, UI/session state, rendered JSON,
  and logs.

## Model decision

- The project owner selected `gpt-5.6-luna` as the clarification-stage LLM model. The live
  continuation adapter is configured explicitly with Luna; GPT-4o mini is retained as failed
  comparison evidence and is not a runtime fallback. The decision affects only the narrow
  answer-interpreter adapter and leaves all deterministic continuation ownership unchanged.

## Clarification UX and month-answer repair (2026-09-09)

- Reproduced the reported repeat locally: the continuation temporal normalizer recognized only an
  exact date or day/week duration, so a named-month answer left the departure blocker unresolved.
  The frozen initial parser already supports a whole named month; the additive continuation
  normalizer now mirrors its next-occurrence rule. Hedged wording such as `Maybe in October?` is
  accepted as an October whole-month departure range when endpoint ownership is unambiguous.
- Replaced the deterministic fallback copy with a warmer customer-service prompt that explicitly
  accepts a month, date, or range for departure.
- Extended the existing answer-interpreter structured response with an optional `next_question`
  plus ordered remaining blocker IDs. The controller uses that one-call model copy only after
  deterministic reduction when those IDs exactly equal the canonical remaining blockers and no
  answer fragment was rejected; otherwise it uses the fallback. The model still receives only the
  answer and active typed requirements, and typed blocker coverage remains authoritative.
- Added unit coverage for hedged-month normalization, year rollover, multi-endpoint ambiguity, the
  reported LA-to-Tokyo nine-day trajectory, model-copy acceptance, deterministic fallback, and
  inactive follow-up blocker IDs. Updated ADR 0011, the implementation handoff, and project state
  to record the presentation-copy boundary.

## Clarification UX verification (2026-09-09)

- `.venv/bin/pytest -q` — 313 passed.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/mypy src tests` — passed.
- `git diff --check` — passed.
- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.clarification_continuation_eval --output /private/tmp/clarification-continuation-followup-ux-eval.json`
  — 28 scenarios / 41 turns passed; exact gate and 41/41 prompt-coverage checks passed. The
  evaluator's eight errors are expected negative-path fixtures.

## Relative temporal answer repair (2026-09-09)

- The continuation-only temporal normalizer now accepts `this weekend`, `this <weekday>`, and
  `on <weekday>`, resolving the next applicable weekend or weekday against the immutable original
  request context. The frozen initial parser is unchanged and still does not recognize a bare
  `this weekend` in an initial raw request.
- Complete numbered answer lines now map one-based to the ordered typed prompt requirements. This
  lets a response with separate numbered departure and return lines resolve both endpoints while
  avoiding endpoint inference from incidental numbers in prose. The mapping remains deterministic
  and answer-local; typed blocker coverage is still authoritative.
- Added continuation regression trajectories for numbered weekend/Monday and cued Friday/Monday
  answers, plus deterministic coverage for relative-date arithmetic and the frozen-boundary
  distinction. No raw user or private model trace content is included in the corpus or this log.

## Relative temporal offline verification (2026-09-09)

- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.clarification_continuation_eval --output /private/tmp/clarification-continuation-relative-temporal-eval.json`
  completed 30 scenarios / 43 turns: 43 passed, 0 failed, exact gate passed, and 43/43
  prompt-coverage checks passed. The evaluator's expected negative-path errors retained their
  non-mutation checks. This run used deterministic local interpreters and made no model or
  provider calls; the subsequent online qualification is recorded below.
- `git diff --check` — passed.

## Prior post-repair live Luna verification (before relative-temporal repair) (2026-09-09)

- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.clarification_live_eval --model gpt-5.6-luna --trials 3 --output evals/clarification/baseline/2026-09-09-gpt-5.6-luna-3-trials-live-escalated.json`
  completed after the sandboxed network attempt returned `APIConnectionError` before any call;
  the escalated retry completed successfully.
- The redacted artifact reports 36/36 correct terminal outcomes, 45/45 exact remaining-blocker
  sets and prompt-coverage checks, zero unauthorized mutations, zero system errors, and 36/36
  sessions within the turn budget. It made 42 successful Luna calls (49,659 input and 7,351 output
  tokens; 119.772 aggregate seconds). Requirement-resolution precision was 1.0 and recall was
  0.9048 (57/63 matched).
- Private all-call traces remain in the gitignored run-specific sidecar directory
  `evals/clarification/traces/run-2026-09-09T182213.909134-0000-5a62934f`: 36 sidecars, 42 calls,
  no call errors, and parsed output present for every call. No raw answer or model payload is
  included in this build log.

## Relative temporal cue-recovery live qualification (2026-09-09)

- An intermediate live artifact,
  `evals/clarification/baseline/2026-09-09-gpt-5.6-luna-3-trials-relative-cue-repair.json`,
  recorded 45/48 terminal outcomes, while all 57/57 processed-turn checks and exact blocker and
  prompt checks passed with zero errors and zero unauthorized mutations. Its three terminal misses
  were the expected nonterminal first turn of `ambiguous_disjunctive_relative_dates`: the
  alternative answer was correctly left `awaiting_answer` for an explicit follow-up. That
  intermediate gate treated the expected nonterminal trajectory as a terminal failure; this was
  evaluation-trajectory accounting, not an implementation failure.
- The fresh rerun used:
  `PYTHONPATH=src .venv/bin/python -m award_agent.cli.clarification_live_eval --model gpt-5.6-luna --trials 3 --output evals/clarification/baseline/2026-09-09-gpt-5.6-luna-3-trials-relative-cue-recovery.json`.
  The redacted artifact reports 48/48 correct terminal outcomes, 60/60 exact remaining-blocker
  checks, 60/60 prompt-coverage checks, 0 system errors, 0 unauthorized mutations, and 48/48
  sessions converging within the turn budget. Requirement resolution was 81/87 matched (precision
  1.0, recall 0.9310). It made 57 successful API calls: 76,554 input tokens and 10,124 output
  tokens (86,678 total), with 209.453 aggregate latency seconds.
- Private all-call traces are in the gitignored run-specific sidecar directory
  `evals/clarification/traces/run-2026-09-09T191202.413442-0000-ec3b0a54`: 48 sidecars, 57
  captured calls, no missing calls, and no call errors. No raw answer or model payload is included
  in this build log.
- Target trajectory outcomes were correct in all three trials: `numbered_relative_weekend_and_monday`
  reached `ready` in one turn with departure `2026-09-12..2026-09-13` and return `2026-09-14`;
  `cued_relative_friday_and_monday` reached `ready` in one turn with departure `2026-09-11` and
  return `2026-09-14`; `polite_cued_relative_friday_and_monday` reached the same result in one
  turn; and `ambiguous_disjunctive_relative_dates` correctly remained awaiting an answer after
  the alternative first response, then reached `ready` after the explicit two-endpoint follow-up
  in two turns with departure `2026-09-11` and return `2026-09-14`.

## Global clarification-relative selector qualification (2026-09-10)

- Replaced the unapproved answer-text regex candidate registry with a global static, date-free
  selector catalog. The answer model grounds local spans to opaque affordances and supplies a
  weekday slot where required; deterministic code validates complete selection/unresolved
  provenance, requirement ownership, same-answer dependency edges, and calendar arithmetic.
  No calendar dates, session state, evaluator keys, candidates, or internal template IDs cross the
  model boundary. Cross-turn anaphora remains unsupported.
- Restored the blind departure phrase and added mandatory 3/3 gates for it and the two core
  numbered relative trajectories, so an aggregate threshold cannot mask a targeted miss. The
  live artifact records per-target/template metrics and private all-call traces separately from
  its redacted public summary.
- Independent architecture review approved the global-selector structure, affordance
  disambiguation, and target gate before the final run.
- `.venv/bin/pytest -q` — 336 passed.
- `.venv/bin/ruff check src tests` — passed.
- `.venv/bin/mypy src` — passed.
- `git diff --check` — passed.
- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.clarification_continuation_eval --fixtures evals/clarification/cases_v1.yaml`
  — 32 scenarios / 46 turns passed; exact gate and template coverage passed.
- Final live qualification used `gpt-5.6-luna` for three trials and wrote
  `evals/clarification/baseline/2026-09-10-gpt-5.6-luna-3-trials-template-v2-final-qualified.json`.
  It reports 48/48 terminal-correct sessions, 60/60 exact remaining-blocker and prompt-coverage
  checks, zero unauthorized mutations, zero system errors, and all three protected targets at
  3/3. The private all-call traces are in
  `evals/clarification/traces/run-2026-09-10T072813.618144-0000-c072ae3d` (48 sidecars); no raw
  answer or model payload is included in this log.

## Owner-directed accepting-clarification refinement (2026-09-10)

- The project owner identified that the qualified strict continuation behavior can still block a
  cooperative user: a reasonable response such as “early next month for a week” may be rejected
  for narrow grammar mismatch and trigger a generic repeated prompt.
- The owner directed the next cut to make clarification more accepting than the frozen initial
  intent stage: accept grounded, bounded fuzzy interpretations with visible assumption provenance;
  reserve targeted questions for genuine alternatives, conflicts, and unresolved ownership.
- ADR 0012 records the superseding policy and separates deterministic safety conformance from
  open-ended behavioral evaluation. No implementation or qualification evidence is claimed by
  this entry.

## ADR 0012 behavioral v2 offline evaluation implementation (2026-09-10)

- Added the separate `cases_v2.yaml` behavioral corpus and scripted offline adapter. Its safety
  gate recomputes blockers from the reduced effective request and independently verifies the
  prompt's ordered requirement links; it does not derive safety from prompt copy.
- The development corpus covers accepting month portions and ordinary duration, open-surface
  paraphrases, material alternatives, non-answers, conflicts, corrections, and a mixed answer
  that retains resolved SFO/traveler/duration siblings while asking only about an ambiguous date.
  The v2 properties permit bounded fuzzy envelopes rather than a single fixed range.
- `PYTHONPATH=src .venv/bin/pytest -q tests/unit/test_clarification_behavior_eval.py tests/unit/test_clarification_controller.py tests/unit/test_clarification_temporal_approximations.py tests/unit/test_clarification_temporal_templates.py tests/unit/test_clarification_continuation_eval.py` — 62 passed.
- `PYTHONPATH=src .venv/bin/pytest -q tests/unit/test_clarification_continuation_eval.py tests/unit/test_clarification_live_eval.py tests/unit/test_clarification_behavior_eval.py` — 23 passed.
- `ruff` and focused `mypy` checks for the v2 evaluator/CLI passed. The offline CLI emitted an
  exact-safety pass with zero behavioral failures in the disclosed development corpus. This is a
  deterministic scripted diagnostic, not an online-model qualification or owner-set threshold.

## ADR 0012 behavioral v2 evaluator review corrections (2026-09-10)

- Remaining oracle-required blockers are now an exact safety failure for every answer class;
  incorrect acceptance remains separately reported as behavioral evidence. Status and semantic
  action contracts are independently checked, so a valid controller status cannot mask a wrong
  accepting, correction, or targeted-follow-up outcome.
- Fixture preflight now validates initial blocker names, numeric calendar envelopes, sibling links,
  pair roles, and the only executable forbidden outcome (`generic_repeat`). Reports explicitly
  identify answer class as their semantic-family distribution and slice dimension.
- Added deterministic sensitivity coverage for the remaining-blocker gate, status/action facets,
  disclosure/material-assumption metrics, generic versus targeted questions, paraphrase overlap,
  pair behavior, and strict fixture links.
- `PYTHONPATH=src .venv/bin/pytest -q` — 388 passed. `ruff check src tests`, `mypy src`, and
  `git diff --check` — passed.

## ADR 0012 final live behavioral qualification (2026-09-10)

- The first live pilot exposed a SOCKS transport dependency and then four conservative
  cross-registry temporal classifications that were incorrectly surfaced as system failures. The
  dependency was declared as `httpx[socks]`; the temporal boundary was hardened with union
  registry coverage, unresolved-only routing for conservative bounded date surfaces, and
  deterministic disjunction downgrade. The public pilot artifact remains diagnostic evidence;
  no safety claim is based on it.
- The final public three-trial Luna run used the accepting v2 corpus and wrote
  `evals/clarification/baseline/2026-09-10-gpt-5.6-luna-behavior-v2-final.json`. Its exact safety
  gate passed with 0 failures, 0 model/system/evaluator errors, and 129/129 captured/reconciled
  all-call private traces (51 interpreter, 78 composer). It reported 0/27 false blocks, 0/12
  incorrect acceptances, 24/24 required assumption disclosures, 0/24 materially incorrect
  assumptions, 18/18 valid siblings retained, and zero property-envelope failures.
- The public artifact's behavioral metrics are intentionally diagnostic rather than release
  thresholds. The accept/ask pairs and paraphrase checks passed. All three conflict trajectories
  remained safe and blocked, but their composer wording was generic rather than sufficiently
  issue-specific: 12/15 targeted follow-ups and generic-repeat rate 0.20. This is the observed
  next quality concern; no owner conclusion or corrective implementation is claimed here.
- Post-run verification: `PYTHONPATH=src .venv/bin/pytest -q` — 398 passed; `ruff check src tests`,
  `mypy src tests`, and `git diff --check` passed before final qualification. Raw model payloads
  remain only in the gitignored trace sidecars.
