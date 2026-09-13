# 2026-09-11: One-way award request-boundary recut

## Owner decision

The owner paused the `EffectiveRequest -> SearchPlan` design stage and reopened intent and
clarification work. The live workflow is being replaced with a one-way award-only boundary under
ADR 0016.

- Ready requires origin, destination, bounded outbound departure timing, and travelers.
- Return dates and trip durations must receive explicit guidance to submit the return leg as a
  separate one-way request; they cannot become active request/session state.
- Cash-only requests are invalid. Mixed award-and-cash requests retain award eligibility but do
  not imply cash-price support.
- Existing round-trip/cash artifacts remain historical; there is no runtime workflow switch.

## Implementation and verification

Implemented the replacement live boundary across the initial parser, selector/compiler projection,
clarification session, receiver wire contract, controller, evaluator, and active corpus.

- `ParsedRequest` and `EffectiveRequest` now expose outbound timing only. The active blocker set is
  origin, destination, departure, and travelers.
- Structured return/duration semantics terminate initial request understanding or a clarification
  session with exact-span, separate-one-way guidance. A clarification answer containing a return
  fact is non-mutating and makes no prompt-composer call.
- Cash-only input is terminally unsupported. Award is the default when unstated; mixed
  award-and-cash input remains eligible for its award portion.
- Endpoint-targeting regressions cover relative return forms, `fly home`, and false-positive
  `home airport`/`my home` departure wording.
- The active evaluation corpus and runners are versioned one-way artifacts; old baseline JSON is
  retained as historical evidence.

Commands and results:

- `.venv/bin/pytest -q` — 326 passed.
- `git diff --check` — passed.
- `.venv/bin/python -m award_agent.cli.one_way_award_clarification_eval` — passed.
- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.one_way_award_live_eval --model gpt-5.6-luna --trials 1 --output evals/clarification/baseline/2026-09-11-one-way-award-live-smoke.json` — exit 0.

The redacted live artifact records 2/2 passing development scenarios, five reconciled private
model calls, and zero preflight/runtime errors. Private raw traces are retained only under the
gitignored `evals/clarification/traces-one-way-live/`. This was a bounded mechanical smoke, not a
broad behavioral qualification.

## Architect-reviewed v2 live matrix

An architecture review found the v1 intent corpus and two-session clarification smoke insufficient
for a full ADR 0016 evaluation. The review prescribed immutable v2 fixtures with strict preflight,
fixture hashes, redacted public artifacts, and private all-call sidecars. The new fixtures contain
18 intent scenarios and 12 multi-turn clarification scenarios; v1 evidence remains historical.

Commands and results:

- `PYTHONPATH=src .venv/bin/pytest -q` — 334 passed.
- `.venv/bin/ruff check .` — passed.
- `git diff --check` — passed.
- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.intent_eval --model gpt-5.6-luna --selector-model gpt-5.6-luna --trials 3 --output evals/intent/baseline/2026-09-11-one-way-award-v2-gpt-5.6-luna-3-trials.json` — exit 1 for behavioral failures only: 52/54 passed, 2 failed, 0 errors. All 102 model calls were captured and reconciled; all 54 private run traces exist.
- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.one_way_award_live_eval --model gpt-5.6-luna --trials 3 --output evals/clarification/baseline/2026-09-11-one-way-award-live-v2-3-trials.json` — exit 0: 35/36 passed, 1 failed, 0 errors. The runner reported `mechanically_completed: true`; all 123 calls reconcile with the 36 private session traces.

The intent fixture SHA-256 is
`2997939d6ec84806238e8755a864f24469fb5cc70a0bc962debcd286e7a49517`; the clarification fixture
SHA-256 is `1ec5cd53c17aa28884eec93b255aac3be3a6819b9d32c05ebb0356632c5aea46`. Public-artifact
inspection found no request or answer text. The three behavioral misses are explicit follow-up
work: a cash-only traveler extraction variance, an unstated-award-mode variance in the home-airport
guard, and one ambiguous-departure clarification turn that became `pending` and invoked the
composer instead of retaining its blocker. This is a completed mechanical evaluation, not a claim
that the behavioral boundary is qualified.

## Local Streamlit harness alignment

- Audited the local validation harness against ADR 0016. Its active request/controller paths
  already used the replacement one-way workflow, but its UI exposed only an opaque terminal reason
  and hid `terminal_message` in session JSON. Return/duration separate-one-way guidance and
  cash-only guidance are now displayed prominently.
- Updated the harness labels and help text for the one-way award boundary. A durable
  composer-pending transition is now retained locally and retried through the composer-only retry
  boundary, without resubmitting the prior answer to the receiver.
- Added structural harness coverage for terminal guidance, ADR 0016 labels, and the composer-only
  retry path. Verification passed: `PYTHONPATH=src .venv/bin/pytest -q` (`337 passed`),
  `.venv/bin/ruff check .`, `git diff --check`, and a direct harness-module import.
