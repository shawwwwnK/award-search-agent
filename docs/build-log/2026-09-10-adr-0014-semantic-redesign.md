# 2026-09-10 — ADR 0014 semantic clarification redesign

## Work attempted

- Added ADR 0014 and its acceptance-evaluation protocol.
- Replaced continuation raw-answer semantic recovery with a typed receiver contract and a
  deterministic symbolic-temporal compiler.
- Restored post-reduction LLM prompt composition and removed deterministic clarification-copy
  fallback from the active renderer.
- Added typed offline guardrail cases, static parser-boundary checks, and a paired Luna versus
  GPT-4o mini composer experiment harness.
- Added semantic-contract hardening for correction authorization, typed ranges/dependencies, and
  visible assumption disclosures.

## Evidence

- `pytest -q tests/unit` passed: 379 tests.
- Focused semantic/controller/guardrail tests and mypy checks passed during implementation.
- The architecture review identified live-qualification gaps in the initial experiment/gate design;
  those findings were used to strengthen the typed offline gate. No live OpenAI calls were made in
  this stage.
- A subsequent live-harness report exposed a receiver metadata linkage failure for the reasonable
  combined answer “leave early October and go for about a week.” The receiver contract was reduced
  so it supplies only grounded semantic targets and values; deterministic session policy now derives
  amendment operation and requirement linkage. A target authorization miss is an independently
  rejected model proposal, not a terminal user-request error, so an accepted sibling remains usable.
- Focused controller/interpreter/semantic tests passed: 21 tests.
- Full unit suite after the follow-up authorization fix passed: 380 tests.
- Repaired a live-evaluator telemetry contract regression found by two failed Luna/Luna runs:
  receiver and composer telemetry now aggregates attempted/captured/missing calls across a session,
  and the evaluator records stage and wall-clock latency separately. Initial/post-answer composer
  failures and telemetry-drain failures now produce explicit failed records, continue the matrix,
  and fail the live gate closed rather than masking instrumentation loss. No live calls were made
  while verifying this repair; the offline full unit suite passed: 386 tests.

## Current limitations

- The paired composer harness is development infrastructure only until a preregistered,
  owner-held locked input set and blinded human quality review are available.
- The durable composer-only retry path needs a final architecture review before any live
  qualification or model-selection conclusion.

## ADR 0015 design follow-up

- Architecture accepted ADR 0015 after trace review showed that several reasonable clarification
  answers were understood semantically but rejected solely at the receiver representation boundary.
  The new boundary is generic model-authored calendar-calculation proposals, not a growing
  deterministic list of phrase-specific temporal relations.
- The approved policy permits one shared bounded model-owned repair per answer across receiver
  schema, grounding, and calendar-calculation failures. Same-answer fact references form an
  acyclic dependency graph rather than relying on text order. A residual failure is recorded as
  visibly communicated, non-mutating pending/retryable state and must not leak a raw schema
  exception, silently choose an interpretation, or count as user no-progress.
- The clarification acceptance protocol now specifies v3 action/property oracles and separates
  semantic diagnosis from end-to-end behavioral success, hard safety, and operational repair/pending
  metrics. It requires explicit numerators/denominators and labels zero-denominator metrics not
  applicable, preventing a pilot from making a vacuous qualification claim. Historical v1/v2
  artifacts remain historical evidence; they do not qualify the ADR 0015 runtime.
- This entry records architecture and evaluation-design decisions only. No ADR 0015 implementation
  tests or live evaluation results are asserted here.

## ADR 0015 implementation checkpoint

- Implemented the generic proposal runtime, flat OpenAI-only response DTO, bounded repair/pending
  behavior, v3 behavioral evaluator, adapter/schema telemetry, and module-wide raw-text boundary
  audit. The isolated one-call provider schema smoke reached inference and returned a parsed
  response; the prior eight-case diagnostic that was rejected before inference remains
  non-semantic adapter evidence only.
- At the weekly-limit stop point, the uncommitted post-smoke hardening delta passed repository Ruff,
  `mypy src tests`, `pytest -q tests/unit` (427 tests), the semantic guardrail CLI, and
  `git diff --check`. No post-smoke v3 behavioral rerun was made.
- Handover: `docs/handoffs/2026-09-10-adr-0015-v3-live-rerun-handover.md`.

## OpenAI flat-wire preflight correction

- The first v3 development diagnostic (`f582925`, one trial, eight scenarios) was inspected after
  trace capture. Every receiver call was rejected by OpenAI before inference because the prior
  generated Structured Output schema contained `oneOf`. The diagnostic's repair calls repeated
  that same rejected schema. It is retained as adapter/preflight and telemetry evidence only, not
  as a semantic, behavioral, latency, or model-comparison result.
- Architecture approved an OpenAI-only flat wire envelope with fixed arrays per fact kind and flat
  nullable anchor fields. Structural wire conversion restores the unchanged generic internal
  calendar-proposal model and does not inspect raw answer text.
- A provider schema rejection is now a preflight pending outcome: it is visibly retryable and
  non-mutating, does not consume the receiver repair budget, and must not be counted as model
  understanding failure. Future live artifacts/traces bind the proposal-contract version,
  wire-adapter version, and canonical generated-schema hash.

## V3 public development diagnostic after flat-wire hardening

- An independent architecture review approved exactly one disclosed, one-trial v3 diagnostic at
  `a86bb59`; it did not approve qualification. Before that run, repository Ruff, `mypy src tests`,
  `pytest -q tests/unit` (427 tests), the semantic-guardrail CLI, and `git diff --check` passed.
- The Luna/Luna development run used the eight-scenario public v3 pilot corpus and wrote its
  redacted artifact to
  `evals/clarification/baseline/2026-09-10-gpt-5.6-luna-v3-development-diagnostic-1-trial-a86bb59.json`.
  Its private all-call sidecars remain ignored under
  `evals/clarification/traces-v3-diagnostic-a86bb59/`.
- The final flat interpreter schema reached structured inference: `preflight_rejected=0`,
  `inference_reached=21`, and `structured_result_returned=21`. All 21 model calls were captured
  and reconciled; the artifact reports zero model, system, and evaluator errors. It binds proposal
  contract `clarification-calendar-plan-v1`, interpreter adapter
  `openai_clarification_interpreter_flat_v3`, and schema hash
  `a37093bc5b1120add021f8e1fba75c2f15119dce57ae067603033c617c89924d`.
- This was diagnostic evidence, not qualification: the current artifact's exact safety gate failed
  for 2 of 8 records. Trace review confirmed one genuine unsafe ambiguity acceptance/protected-field
  change in `bare_return_endpoint`: the receiver proposed a return fact without preserving the
  ambiguity, and deterministic reduction and composition mechanically followed that authorized
  proposal. `fuzzy_month_disclosed` instead safely re-asked after the receiver proposed only an
  unresolved fact; its recorded undisclosed-approximation safety failure is an evaluator false
  positive because no approximation was accepted. The run also recorded a receiver-repair-to-pending
  outcome that failed independent-sibling retention after the repair repeated duplicate targets.
  The conflict scenario reached the required conflict-specific prompt; its only failure is the
  evaluator's `partial_resolve_and_ask` classification versus the fixture's `ask` action. No
  automatic rerun was made.
- Qualification remains blocked by these safety findings and by the pre-existing protocol
  requirements: a preregistered locked holdout, rotating post-freeze challenge, owner-approved
  thresholds, repeated trials/confidence intervals, and human review of question naturalness.

## V3 public development matrix (three trials)

- Ran the same disclosed eight-scenario v3 pilot corpus for three Luna/Luna trials. The redacted
  aggregate artifact is
  `evals/clarification/baseline/2026-09-10-gpt-5.6-luna-v3-development-diagnostic-3-trials-a86bb59.json`;
  its 24 private sidecars remain ignored under
  `evals/clarification/traces-v3-diagnostic-3trial-a86bb59/`.
- Provider and observability execution was complete: `preflight_rejected=0`,
  `inference_reached=63`, `structured_result_returned=63`, and all 63 calls were captured and
  reconciled with zero reported model, system, or evaluator errors. The command exited nonzero
  only because its safety/behavior gate failed; it was not retried.
- The current evaluator reports 6 safety-failing records, false blocking in 3/9 eligible turns,
  incorrect acceptance in 3/12, missing disclosure in 3/6, valid-sibling retention in 3/9, and
  0/5 completed repair workflows (all five became receiver-pending). The failure distribution is
  stable for `bare_return_endpoint`, `fuzzy_month_disclosed`, and
  `return_before_departure_conflict` (three trials each); the public artifact also records all
  three `explicit_date_alternatives` trials and two `valid_siblings_with_ambiguous_departure`
  trials as behavioral failures.
- This matrix is disclosed development evidence only. It increases confidence that the flat wire
  schema and trace capture work, but it does not override the one-trial trace audit: the
  approximation-disclosure and conflict action classifications need evaluator review before they
  are interpreted as product-safety defects. No qualification claim is made.

## Project-owner decisions

- _Placeholder: record any model-selection or latency decision after reviewed experimental
  evidence exists._
