# 2026-09-20: Active Intent corpus through clarification and search planning

## Authorization and scope

The owner requested an end-to-end diagnostic using the active Intent-stage evaluation set through
request understanding, clarification-state projection, and search planning, with traces and result
analysis but no behavior changes. The owner also requested that connector or infrastructure defects
be fixed without changing semantic behavior.

The active denominator is the 19-case `intent_behavior_v1` corpus. Historical round-trip,
selector-era, and older one-way corpora were not mixed into this result. The connector supplies no
invented clarification answers: every completed Intent result is passed to `start_clarification`,
and only a genuinely ready session may cross the frozen `EffectiveRequest` boundary into planning.
Awaiting-answer and unsupported sessions stop upstream. The planning path uses the current local
catalog, M2A endpoint selector where independent catalog grounding permits it, closed M2B gateway
discovery, and the deterministic M2C compiler. It constructs no travel-provider client.

## Evaluation connector

The session added a bounded evaluation-only connector and CLI:

- `src/award_agent/evaluation/intent_to_search_planning_live.py`;
- `src/award_agent/cli/intent_to_search_planning_live_eval.py`;
- `tests/unit/test_intent_to_search_planning_live_eval.py`; and
- the `award-intent-to-search-planning-live-eval` project entry point.

The connector pins `gpt-5.6-luna`, one trial, the exact 19-case corpus and its SHA-256
`52a98b9ca316b9a2744c21072d6d0d603bcf4265f45328b6358ef2f1a238607a`, and the current catalog,
policy, and capability identities. Public output is redacted. Raw requests, model calls, full typed
records, exception text, and source bundles are stored only under the ignored private trace root
`evals/intent_to_search_planning/traces-live/`.

The first live attempt exposed an evaluation-connector defect: exact-date requests were projected
into `GatewayOutboundDateContext` with hard-coded `window` precision. M2C correctly rejected the
replayed evidence because it differed from the effective request. The connector now copies
`request.departure_window.precision.value`; a focused regression test covers the exact-date path.
The initial public diagnostic is preserved with a `-pre-fix` suffix and is not the result analyzed
below. No runtime prompt, policy, corpus, semantic contract, or workflow behavior changed.

## Commands and verification

The worker and implementer recorded these scoped checks:

```text
.venv/bin/pytest -q tests/unit/test_intent_to_search_planning_live_eval.py
5 passed

.venv/bin/pytest -q tests/unit/test_intent_eval_runner.py \
  tests/unit/test_search_planning_live_eval.py \
  tests/unit/test_intent_to_search_planning_live_eval.py
20 passed

.venv/bin/ruff check <new evaluator, CLI, and focused test>
passed

.venv/bin/mypy <new evaluator, CLI, and focused test>
passed

git diff --check
passed
```

The real-catalog preflight completed before the live run. The final public artifact is:

`evals/intent_to_search_planning/baseline/2026-09-20-gpt-5.6-luna-active-intent-corpus-1-trial.json`

Its private run directory is ignored and local:

`evals/intent_to_search_planning/traces-live/run-2026-09-20T192003.510303-0000-45b3f0e4/`

The public redaction scan found no raw request, scenario payload, exception text, model output,
instructions, effective request, or private trace path. The private run contains 19 typed record
sidecars and seven M2C source bundles.

## Mechanical results

The final one-trial run recorded:

- 19/19 corpus cases and 19/19 trace reconciliations;
- 35 attempted model calls and 35 private call traces;
- 74,533 input tokens, 14,772 output tokens, and 89,305 total tokens;
- 201.546 seconds of cumulative per-case stage latency (not wall-clock latency), with 8.361-second
  median and 26.008-second maximum;
- 13/19 Intent behavioral passes;
- 17 behavioral terminal outcomes and two `pending_retryable` infrastructure outcomes;
- seven ready sessions compiled into plans, six awaiting-answer sessions, four correctly stopped
  unsupported sessions, and two pending Intent outcomes; and
- zero travel-provider calls.

All seven planned cases used direct IATA endpoints, so they required no M2A selection record. All
seven M2B results were `success_nonempty`. M2C produced 36 logical queries in total (three to eight
per plan), complete mandatory coverage, equal same-record disk replay, and a `current` executable
handoff for every plan.

## Behavioral findings

Thirteen cases satisfied the active Intent oracle. The four unsupported cases—explicit return,
duration, relative return, and cash-only—stopped before planning as required. Missing origin,
departure, and travelers remained awaiting clarification. Mixed award-and-cash and the home-airport
wording both reached ready and planned without claiming cash coverage or interpreting “home” as a
return cue.

Six cases did not satisfy the Intent oracle:

| Case | Observed result | Interpretation |
| --- | --- | --- |
| `ready_holiday_window` | clarification; departure remained unresolved | Behavioral miss: the expected Labor Day window did not reach ready. |
| `typo_recognizable_date` | clarification; departure remained unresolved | Behavioral miss: the recognizable holiday/date typo was not recovered. |
| `missing_destination` | clarification with unexpected blocker/traveler mismatch | The action was safe, but the blocker/property envelope was wrong. |
| `ambiguous_departure` | ready, then a valid plan | Safety-relevant behavioral miss: broad “next spring” should have remained blocked. Downstream mechanical success does not make the upstream interpretation correct. |
| `ready_relative_weekend` | `pending_retryable` after bounded adapter work | Operational/model-adapter outcome; no success-shaped fallback and no planning. |
| `unbounded_departure` | `pending_retryable` after bounded adapter work | Operational/model-adapter outcome; no success-shaped fallback and no planning. |

This single development trial is evidence of the remaining broad upstream behavioral gap, not a
qualification result. In particular, the unsafe `ambiguous_departure` ready result should be
treated more seriously than an ordinary recall miss because it authorized downstream work from an
expected blocker. The two pending results keep `mechanically_completed=false`; they are not
connector failures and were not hidden or automatically reclassified.

## Claim boundary and disposition

This run demonstrates a traceable local handoff from the active Intent corpus through clarification
state and, where eligible, current planning. It does not supply user clarification answers, adopt
M2A, reopen M2B, qualify model semantics, call a travel provider, observe availability, validate an
itinerary, rank recommendations, or establish product/provider qualification. No behavior change
or owner decision follows from the diagnostic. The existing upstream behavioral-evidence gate
remains open.
