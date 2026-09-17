# 2026-09-17: Milestone 2A endpoint-airport selection

## Work recorded

Implemented the bounded model-proposed endpoint-airport selection seam after
Milestone 1 exact location resolution. The work preserves the frozen
intent/clarification and Milestone 0 fixture contracts. It does not add a
serving-relationship graph, route data, provider execution, RAG, persistence,
or cache.

## Implemented evidence boundary

- `ResolvedEntityContext` classifies the already canonical entity from retained
  catalog taxonomy; unclear geographic regions use an explicit broad-cap
  fallback rather than erroring or letting the model choose a category.
- The v1 cap policy retains defaults 2/4/4/8 and records exactly seven
  approved canonical `(entity_id, category)` cap exceptions: San Francisco
  (`geonames:5391959`, `city_metropolitan`) 3, New York City
  (`geonames:5128581`, `city_metropolitan`) 3, London
  (`geonames:2643743`, `city_metropolitan`) 5, Los Angeles
  (`geonames:5368361`, `city_metropolitan`) 5, United States
  (`geonames:6252001`, `country`) 10, China (`geonames:1814991`, `country`)
  6, and India (`geonames:1269750`, `country`) 6. These are empirical
  product-policy decisions based on pretrained geographic/aviation knowledge,
  not catalog-verified city-serving geography or an airport-membership list.
  City exceptions address metro-serving practicality; country exceptions
  address useful international-gateway coverage. Each override changes only
  a maximum count, never airport membership, a whitelist, or a requirement to
  fill the cap. No regional exceptions are included.
- The selector uses strict Responses structured output with `store=False`, an
  abstention outcome, and two versioned prompt arms for comparison. It performs
  no retry/refill.
- Candidate outcomes distinguish catalog identity, snapshot facility-admission,
  country membership, city-distance policy, city-serving model proposal,
  priority, and policy acceptance. The permissive 200 km city-distance check
  is explicitly not city-serving verification.
- Immutable selection records and replay receipts bind policy/catalog/model/
  prompt/schema identities. Existing Milestone 0 planning identity is not
  rewritten.
- A diagnostic live evaluator and CLI use opt-in model capture, ignored private
  trace sidecars, redacted public artifacts, usage/call reconciliation, and a
  disclosed human-scored development casebook.

## Approved cap policy and budget boundary

The approved exceptions are a policy change only; they do not yet establish
that larger caps improve coverage. Accepted origin and destination counts
multiply into endpoint pairs under the planner's maximum of 25: `5 x 5` is
25, `6 x 4` is 24, while a US maximum creates `10 x 4`=40, `10 x 5`=50, and
`10 x 6`=60 before deduplication. Those US maximum combinations exceed the
budget. Such an over-budget request remains a
visible `endpoint_pair_budget_exceeded` failure; the planner does not silently
truncate the selected sets. Actual counts may be below the maxima because an
override does not require filling its cap. Future human/holdout evaluation is
still required to determine whether these larger maxima improve useful
coverage within the budget.

## Approved cap-policy verification

Phase 2 integrated verification after adding the seven approved overrides:

```text
.venv/bin/pytest -q tests/unit/test_airport_selection_foundation.py
# 21 passed in 0.29s

.venv/bin/pytest -q tests/unit/test_airport_selector.py tests/unit/test_airport_selector_live_eval.py
# 10 passed in 0.65s

.venv/bin/ruff check tests/unit/test_airport_selection_foundation.py
# All checks passed!

.venv/bin/ruff format --check tests/unit/test_airport_selection_foundation.py
# 1 file already formatted

.venv/bin/pytest -q
# 440 passed, 99 skipped in 3.66s
```

These checks validate policy loading/application and guard the existing
selector and offline repository behavior. They are mechanical regression
evidence only; they do not evaluate whether the larger caps improve semantic
coverage.

## Evaluation alignment after approved exceptions

The active evaluator now uses the disclosed
`evals/airport_selector/development_cases_v3.yaml` casebook and the active
policy digest
`a3b493cc8c271e78217d99dcc89bcfa7eb8089bb7310a6f2489ae5d9cd915256`.
It retains ordinary/default and regional cases, and adds the complete approved
override set: San Francisco, New York City, London, and Los Angeles as
city/metro cases; United States at cap 10, China and India at cap 6 as
country/international-gateway cases. The casebook's IATA envelopes remain human-scored review aids,
not airport-membership or city-serving records. The city and country review
purposes are intentionally distinct.

`development_cases_v1.yaml` and
`baseline/2026-09-17-gpt-5.6-luna-original-simple-vs-refined-development-3-trials.json`
are byte-preserved historical pre-override evidence. They remain useful prompt
diagnostic history but do not measure the active seven overrides and make no
claim about their extra coverage. The byte-preserved v2 casebook/artifact is
also historical US=6 evidence: it does not measure or validate the current
US=10 policy. No v3 live rerun has been performed; the active v3 diagnostic is
pending.

Offline verification after this alignment:

```text
.venv/bin/pytest -q tests/unit/test_airport_selection_foundation.py tests/unit/test_airport_selector_live_eval.py tests/unit/test_airport_selector.py
# 35 passed in 0.56s

.venv/bin/ruff check src/award_agent/evaluation/airport_selector_live.py tests/unit/test_airport_selector_live_eval.py tests/unit/test_airport_selection_foundation.py
.venv/bin/ruff format --check src/award_agent/evaluation/airport_selector_live.py tests/unit/test_airport_selector_live_eval.py tests/unit/test_airport_selection_foundation.py
.venv/bin/mypy src/award_agent/evaluation/airport_selector_live.py tests/unit/test_airport_selector_live_eval.py tests/unit/test_airport_selection_foundation.py
# all passed

.venv/bin/pytest -q
# 444 passed, 99 skipped in 3.49s

git diff --check
# passed
```

## Verification

Implementation-time focused checks (run after integration):

```text
.venv/bin/pytest -q tests/unit/test_airport_selector.py tests/unit/test_airport_selector_live_eval.py
.venv/bin/ruff check src/award_agent/search_planning src/award_agent/evaluation/airport_selector_live.py src/award_agent/cli/airport_selector_live_eval.py tests/unit/test_airport_selector.py tests/unit/test_airport_selector_live_eval.py
.venv/bin/ruff format --check src/award_agent/search_planning src/award_agent/evaluation/airport_selector_live.py src/award_agent/cli/airport_selector_live_eval.py tests/unit/test_airport_selector.py tests/unit/test_airport_selector_live_eval.py
.venv/bin/mypy src/award_agent/search_planning/airport_selection_policy.py src/award_agent/search_planning/airport_selector.py src/award_agent/search_planning/distance_consistency.py src/award_agent/search_planning/knowledge.py src/award_agent/search_planning/planner.py src/award_agent/evaluation/airport_selector_live.py src/award_agent/cli/airport_selector_live_eval.py tests/unit/test_airport_selection_foundation.py tests/unit/test_airport_selector.py tests/unit/test_airport_selector_live_eval.py
.venv/bin/pytest -q
git diff --check
```

The evaluator's tests use fake selector responses and a tiny generated catalog;
they make no network/model call.

Final integrated verification: `432 passed, 99 skipped`; targeted Ruff,
formatter, and mypy checks passed; `git diff --check` passed. Repository-wide
mypy continues to report its unrelated legacy clarification/temporal baseline,
so it is not presented as a new M2A failure or as a clean whole-repository
type-check result.

## Historical pre-override live diagnostic evidence

The user authorized a bounded live diagnostic after the selector and evaluator
reviews. The completed artifact below used `development_cases_v1.yaml` before
the seven overrides were approved, so it is historical diagnostic evidence and
not active-policy evidence:

`evals/airport_selector/baseline/2026-09-17-gpt-5.6-luna-original-simple-vs-refined-development-3-trials.json`

Command:

```text
.venv/bin/python -m award_agent.cli.airport_selector_live_eval --model gpt-5.6-luna --trials 3 --output evals/airport_selector/baseline/2026-09-17-gpt-5.6-luna-original-simple-vs-refined-development-3-trials.json
```

Objective run evidence:

- 12 disclosed canonical-entity cases, two prompt arms, and three trials:
  72 attempted live calls.
- 72 completed records, zero provider/model errors, 72 captured-usage records,
  and 72 reconciled private trace sidecars.
- The selected catalog was `m1a-3cb7981519612945`; the cap-policy digest was
  `55b003987436d02dbed0d9898dbf334375a38ed87fa7b8da5476b3cb3f682571`; the
  city-distance-policy digest was
  `1ac4c7c443453db2354e95d852c8c493ce0e0897873c1a4f6fd70bf3350e75c3`.
- The mean recorded call latency was 4.985 seconds. Cost is intentionally not
  estimated because the run did not carry a versioned official price card.
- One original-simple North America trial returned the permitted
  `insufficient_knowledge` outcome. The other 71 proposals produced 280
  catalog-verified, facility-admitted exploratory endpoints; no candidate was
  rejected during this corpus run.
- The refined arm accepted 156 endpoints versus 124 for original-simple. Its
  validated proposals met the casebook's must-consider envelope in all 36
  runs, but had nine selections outside the disclosed acceptable envelope,
  compared with two for original-simple. Neither arm selected a listed
  unacceptable airport. These are review observations, not automatic semantic
  pass/fail scores.

The ignored raw-call sidecars are under `evals/airport_selector/traces-live/`.
They retain model-facing input and raw provider responses; the public artifact
retains only validated decision evidence.

## Historical v2 active-policy live diagnostic evidence (US=6)

After the independent exception-policy and v2-evaluator reviews, the then-
approved seven-override policy, with US=6, was evaluated with:

`evals/airport_selector/baseline/2026-09-17-gpt-5.6-luna-original-simple-vs-refined-active-cap-overrides-v2-3-trials.json`

Command:

```text
.venv/bin/python -m award_agent.cli.airport_selector_live_eval --model gpt-5.6-luna --trials 3 --output evals/airport_selector/baseline/2026-09-17-gpt-5.6-luna-original-simple-vs-refined-active-cap-overrides-v2-3-trials.json
```

Objective run evidence:

- 14 disclosed v2 cases, two prompt arms, and three trials: 84 attempted
  calls; all 84 completed with zero errors, captured usage, and reconciled
  private trace sidecars.
- The catalog snapshot was `m1a-3cb7981519612945`; the then-active cap-policy
  digest was `35d470c8871e0c61be152729734ef140d70ba9eebc8d4ff12b46c3737acbb45e`.
- All 84 runs met their must-consider envelope and none selected a listed
  unacceptable airport. The refined arm accepted 216 endpoints (5.14 per
  record) and original-simple 180 (4.29 per record). Refined had 13 selections
  outside the disclosed acceptable envelopes, compared with three for
  original-simple.
- City overrides consistently returned their configured cap: San Francisco
  and New York City three; London and Los Angeles five. Refined filled all
  three six-airport country caps; original-simple returned five for each.
- Mean recorded latency was 8.360 seconds. Cost remains intentionally
  unestimated because this run has no versioned official price card.

These mechanical and envelope observations do not establish city-serving facts,
prove that every extra endpoint is useful, or qualify either prompt arm for
adoption. In particular, they do not validate the later US=10 policy. They are
historical input to the pending independent human semantic review.

## US-focused cap revision (US=10)

The owner raised only the canonical United States country override from 6 to
10 for a US-focused product policy. China and India remain at 6 and the four
city/metro exceptions are unchanged. The active evaluator contract is now
`development_cases_v3.yaml`; it is a byte-derived v2 successor whose only
case-level change is the US scenario's cap-10 identity/review semantics.

The v1 and v2 casebooks and both associated public artifacts are SHA-256
pinned in offline tests. They remain historical evidence. In particular, the
v2 84-call artifact measured US=6 and cannot validate the active US=10 cap.

The corresponding v3 diagnostic artifact is:

`evals/airport_selector/baseline/2026-09-17-gpt-5.6-luna-original-simple-vs-refined-us-cap-10-v3-3-trials.json`

It ran 14 cases, two prompt arms, and three trials: 84 completed calls with
zero errors and 84 reconciled traces. All runs met their must-consider envelope
and none selected a listed unacceptable airport. Refined selected 228 endpoints
(5.43 per record) with 11 outside-envelope selections; original-simple selected
178 (4.24 per record) with one outside-envelope selection. For US=10, refined
returned 10 endpoints in all three trials, while original-simple returned five
in all three. The refined US selections included IAH in two trials, outside the
disclosed acceptable envelope. Mean recorded latency was 3.691 seconds; cost
remains unestimated without a versioned official price card.

These are diagnostic envelope observations, not proof that the ten-airport US
maximum is semantically preferable or schedulable inside the 25-pair budget.

Verification after this revision:

```text
.venv/bin/ruff check src/award_agent/evaluation/airport_selector_live.py tests/unit/test_airport_selection_foundation.py tests/unit/test_airport_selector.py tests/unit/test_airport_selector_live_eval.py
.venv/bin/ruff format --check src/award_agent/evaluation/airport_selector_live.py tests/unit/test_airport_selection_foundation.py tests/unit/test_airport_selector.py tests/unit/test_airport_selector_live_eval.py
.venv/bin/mypy src/award_agent/evaluation/airport_selector_live.py tests/unit/test_airport_selection_foundation.py tests/unit/test_airport_selector.py tests/unit/test_airport_selector_live_eval.py
# all passed

.venv/bin/pytest -q tests/unit/test_airport_selection_foundation.py tests/unit/test_airport_selector.py tests/unit/test_airport_selector_live_eval.py
# 38 passed in 0.52s

.venv/bin/pytest -q
# 447 passed, 99 skipped in 3.43s
```

The active policy SHA-256 is
`a3b493cc8c271e78217d99dcc89bcfa7eb8089bb7310a6f2489ae5d9cd915256`.

## Owner decision placeholders

- Historical pre-override live diagnostic: **completed; artifact recorded above**.
- Active v3 US=10 diagnostic: **completed; v3 artifact recorded above; v2 remains historical US=6 evidence only**.
- Human semantic review: **pending**.
- Whether a named cap exception is approved: **approved; exactly the seven
  exceptions listed above**.
- Whether the larger caps improve useful coverage: **pending future
  evaluation**.
- Whether holdout evidence admits selector adoption: **pending**.
- Next M2A cut after review: **pending**.
