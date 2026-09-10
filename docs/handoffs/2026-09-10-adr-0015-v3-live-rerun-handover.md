# ADR 0015 v3 live-rerun handover

## Stop point

Stop here per project-owner instruction: do **not** make further live OpenAI calls until the weekly
limit resets. The next live operation is a one-trial, disclosed v3 diagnostic rerun; it has not
been executed after the flat-schema and preflight repairs described below.

## Completed work

Two committed checkpoints establish the redesign:

- `f582925 feat: evaluate clarification by safe user outcomes`
  - ADR 0015 generic model-authored calendar operations;
  - outcome/property-oriented v3 evaluator and disclosed development corpus;
  - model-owned one-repair/pending policy; and
  - retained the first redacted v3 diagnostic artifact.
- `8c5fbea fix: flatten clarification response schema`
  - replaced the OpenAI response DTO's unsupported nested `oneOf` unions with an OpenAI-only flat
    schema; private v3 traces are now ignored; the historical redacted artifact remains tracked.

The isolated provider schema smoke on `8c5fbea` succeeded. It made exactly one interpreter call,
reached inference, and returned a parsed structured result. It used adapter
`openai_clarification_interpreter_flat_v3`, schema hash
`4cd5b44d809643fd9dcbe5af27dc848f9bbd703057d4825abb1e540932fd4b4e`, request ID
`resp_0321faa615aa005f016aa33be42a3887d08d0f5d2f6a594f6b`, and took 2.434 seconds. The local
private smoke trace is `/private/tmp/flat-schema-smoke-8c5fbea.json`; do not commit it.

The current **uncommitted** delta completes post-smoke hardening:

- Flat DTO anchor/inclusion fields use provider-safe literals; incomplete literal endpoints,
  incompatible operation targets, and duplicate fact IDs are rejected structurally.
- A provider schema rejection now produces typed receiver unavailability, a non-mutating visible
  pending outcome, and `preflight_rejected` telemetry; it does not throw to the user or spend a
  futile repair call.
- V3 artifacts now include proposal-contract version and provider-stage counts. Repair/first-pass/
  pending metrics are separated.
- The raw-text audit covers the whole OpenAI adapter. It permits only exact quote-span grounding,
  configuration trimming, and provider-error classification; it rejects semantic text parsing in
  helper functions too.

## Evidence at this stop point

No live calls were made after the smoke.

```text
PYTHONPATH=src .venv/bin/ruff check .                                  # passed
PYTHONPATH=src .venv/bin/mypy src tests                                # passed, 104 files
PYTHONPATH=src .venv/bin/pytest -q tests/unit                          # passed, 427 tests
PYTHONPATH=src .venv/bin/python -m award_agent.evaluation.clarification_semantic_guardrails
                                                                         # passed
git diff --check                                                        # passed
```

The last pre-flat-schema v3 diagnostic is intentionally **not** semantic evidence: every scenario
failed before inference because the provider rejected the old `oneOf` response schema. Its redacted
artifact is tracked at:

`evals/clarification/baseline/2026-09-10-gpt-5.6-luna-v3-development-diagnostic-1-trial-f582925.json`

Its private sidecars are local/ignored under `evals/clarification/traces-v3-diagnostic-f582925/`.

## Required next steps

1. Review and commit the current uncommitted flat-wire hardening delta. Confirm `git diff --check`,
   full unit tests, full mypy, repository Ruff, and the semantic guardrail again after any merge.
2. Have architecture independently approve the revised preflight/pending behavior and v3 telemetry
   fields. The earlier architecture review authorized the smoke but required these fixes before a
   behavioral rerun.
3. Run exactly one disclosed/public v3 diagnostic trial, not qualification:

   ```sh
   PYTHONPATH=src .venv/bin/python -m award_agent.cli.clarification_behavior_live_eval \
     --interpreter-model gpt-5.6-luna \
     --composer-model gpt-5.6-luna \
     --trials 1 \
     --fixtures evals/clarification/live_cases_v3_development.yaml \
     --trace-dir evals/clarification/traces-v3-diagnostic-<commit> \
     --output evals/clarification/baseline/<date>-gpt-5.6-luna-v3-development-diagnostic-1-trial-<commit>.json
   ```

4. Inspect every failed private trace by user-visible action and failure owner. Do not judge a run by
   proposal/AST spelling. The artifact must report adapter/schema hashes, proposal-contract version,
   provider stages, first-pass/repair/pending counts, denominator eligibility, and safety outcomes.
5. Do not call a run qualification. Qualification remains blocked on a preregistered locked holdout,
   rotating post-freeze challenge, owner-approved thresholds, repeated trials/confidence intervals,
   and human review of question naturalness.

## Non-negotiable boundaries

- The LLM is the sole reader of answer language. No deterministic phrase aliases, typo tables,
  endpoint heuristics, or raw-text semantic parsing may be added.
- Deterministic code may only structurally validate typed proposals, perform calendar arithmetic,
  enforce authorization/bounds/conflicts, and reduce immutable state.
- A reasonable answer may be semantically understood but still be a system failure if it cannot
  reach a safe user-visible result. A bounded successful model repair counts as task success; a
  clear answer re-asked after exhausted repair is a safe false block, not success.
- Provider schema rejection is adapter preflight: non-mutating pending, no repair retry, and not a
  receiver-semantic failure.
- Never commit private trace sidecars. `.gitignore` now covers `evals/clarification/traces-v3-*/`.

## Relevant documents

- `docs/adr/0015-generic-model-authored-clarification-calendar-proposals.md`
- `docs/evaluation/clarification-acceptance-evaluation-protocol.md`
- `docs/project-state.md`
- `docs/build-log/2026-09-10-adr-0014-semantic-redesign.md`
