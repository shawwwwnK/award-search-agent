# 2026-09-17 to 2026-09-19: Milestone 2B gateway-airport discovery

## Work recorded

The owner opened Milestone 2B on 2026-09-17 and approved its market-policy and
model-hypothesis direction in ADR 0020 on 2026-09-18. On 2026-09-19, the
approved narrow implementation and bounded prompt-v2 diagnostic were completed.
This is local development evidence, not a production release or a semantic
qualification decision.

## Owner decisions implemented

- The static `planning-market-v1` policy is a product overlay on catalog facts:
  exact airport override, guarded exception-region gap, country/territory
  assignment, then explicit unknown gap. Hawaii and IPC overrides, Alaska in
  the United States market, and the Australia/New Zealand/Pacific boundary are
  represented without changing physical catalog metadata.
- A known single-market union is the only policy skip. Empty/invalid inputs are
  input errors. An unknown endpoint market forces the one grouped model call
  with an inspectable mapping-gap receipt; it is never silently treated as a
  shared market.
- A model/policy market mismatch is preserved as a nonfatal advisory for a
  future 2C rather than rejecting an otherwise valid candidate.
- 2B candidates are unverified supplemental-search hypotheses. The work does
  not adopt M2A, compile a `SearchPlan`, call a travel provider, or make route,
  schedule, connection, award, availability, feasibility, or booking claims.

## Implementation and staged review

- Added `market_policy.py` and
  `data/search_planning/v2/planning-market-policy-v1.json` for versioned,
  catalog-bound market classification, gate decisions, override provenance,
  guarded-region drift gaps, and immutable record validation.
- Added `gateway_generator.py` for one OpenAI structured-output call with the
  repository model configuration, resolved airport/market/date context,
  response-schema identity, disabled storage, and no retry/refill. Prompt-v2
  explicitly prevents an access gateway from creating a self-pair.
- Added `gateway_discovery.py` for schema/domain separation; pool caps,
  catalog identity and retained-facility checks; correct-side applicability;
  duplicate/self-reference checks; dependency-aware scope pruning; advisory
  market comparisons; coverage limits; and deterministic replay of a stored
  proposal.
- Added offline unit coverage for policy/gate behavior, grouped proposals,
  relationship validation, dependency pruning, partial/empty/failure outcomes,
  advisory mismatches, tamper/replay behavior, and no-call policy skips.
- Staged implementation reviews produced and fixed policy replay invariant
  checks, exact exception-region drift handling, generator input/prompt
  invariants, delayed domain validation for partial structured proposals, and
  validator self-pair behavior. Final focused reviews reported the policy,
  generator, discovery/replay, and evaluator boundaries ready for the final
  diagnostic.

## Evaluation implementation and artifacts

- Added the disclosed eight-scenario development casebook
  `evals/gateway_discovery/development_cases_v1.yaml`, the offline/live
  evaluator and CLI, and
  `docs/evaluation/gateway-discovery-evaluation-protocol.md`.
- The historical prompt-v1 artifact,
  [`2026-09-19-gpt-5.6-luna-development-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-development-2-trials.json),
  is retained as a diagnostic that led to bounded self-pair and prompt-v2 fixes;
  it is not the final baseline.
- The final public artifact is
  [`2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json).
  Its private raw trace/record sidecars remain under the ignored
  `evals/gateway_discovery/traces-live/` path and are linked by case/trial ID.

## Verification

The final offline suite (`.venv/bin/pytest -q`) completed with **505 passed,
99 skipped**. `.venv/bin/ruff check .` and `git diff --check` completed
cleanly. Targeted mypy across the nine changed 2B implementation/evaluation/test
files completed cleanly. A full-repository mypy run reported **266 pre-existing
errors in 14 legacy files**; that result is recorded as baseline debt and is
not attributed to 2B.

The bounded live run used `gpt-5.6-luna`, two trials, the eight disclosed cases,
one call per generation-required case, no retries, and no refill calls. The
`.venv/bin/python -m award_agent.cli.gateway_discovery_live_eval` command
produced the final public artifact. The equivalent
`award-gateway-discovery-live-eval` console entry point is declared in
`pyproject.toml`; the existing virtual environment was not reinstalled during
this session. The prompt-v2 artifact identity is:

- generated at `2026-09-19T07:36:30.793189+00:00`;
- model `gpt-5.6-luna`, adapter `openai_gateway_generator_v1`, prompt
  `gateway-generator-prompt-v2`;
- response schema SHA-256
  `173a1d66ef5091a0f44837583579fc1616b406f440ce15976b430bae53a5a680`;
- casebook SHA-256
  `9f4a1593ae7d06d132faaf5e5d3895f56823136f97a66d4bbde45292edb6789b`;
- market-policy `planning-market-v1`, SHA-256
  `4e2d9436659b4123f340b2619a4620f843a53ae198469fe9cde5e312e965285a`.

It has 16 completed case-trials and 14 expected, constructed, attempted, and
reconciled calls: 9 successful nonempty outcomes, 3 successful empty outcomes,
2 partial-acceptance outcomes, and 2 policy skips. It retains 39 accepted
candidates and 36 accepted scopes; two `PNH` candidate proposals were rejected
as absent from the pinned catalog, with five dependent scopes rejected. There
were 48,561 captured total tokens, zero generation failures, zero market
mismatch advisories, and no estimated cost because no versioned official price
card was captured. Artifact-integrity and final review checks passed.

## Remaining gate

The run is mechanically complete only. The owner has not human-qualified model
quality. Human review must still apply the documented usefulness, scope,
important-omission, weak-extra, access-role, uncertainty, rejected/advisory,
and variation rubric. That review, and the owner's next-cut decision, remain
open. Milestone 2C is not implemented; if opened, it must preserve mandatory
endpoint coverage and consolidate accepted unverified hypotheses together with
their mapping gaps and advisory evidence without converting them into
connectivity facts.

## 2026-09-19 revision: complementary access alternatives and prompt-v5 / casebook-v2

The owner approved a narrow 2B revision after human review identified a
semantic-coverage gap in the West Coast to Paris diagnostic. The change does
not claim a route, connection, schedule, award, or feasibility fact.

- Access gateways may be materially complementary departure or arrival
  alternatives even for already-strong original endpoints. They require
  specific incremental value relative to the opposite market and selected
  alternatives; size, proximity, shared market, or geographic diversity alone
  is insufficient.
- Pool ceilings are independent: 0–2 origin access, 0–2 destination access,
  and 0–5 hubs, for at most nine candidates. They are maxima rather than
  targets; access candidates do not reduce the hub ceiling. There is no
  intermediate-hub market-diversity quota.
- 2C remains unimplemented. If opened, it must preserve mandatory original
  endpoint coverage, budget compiled relationships/search items rather than
  raw candidate count, and record budget omissions without calling an accepted
  2B candidate invalid.

The v2 disclosed casebook changes the Southeast Asia scenario to SAI and KTI
only. The v1 casebook and its SHA-256
`9f4a1593ae7d06d132faaf5e5d3895f56823136f97a66d4bbde45292edb6789b` remain
historical evidence. Prompt-v3 and prompt-v4 public artifacts are diagnostic
iterations: v3 exposed saturation (58 accepted candidates, including 34 hubs);
v4 reduced burden but regressed IPC circuitousness and endpoint assessment.
Prompt v5 addresses both with marginal-distinctness, circuitousness, and
endpoint-assessment rules. The response schema and adapter remain unchanged.

Final offline verification completed with **507 passed, 99 skipped**;
`.venv/bin/ruff check .` and `git diff --check` were clean; targeted mypy for
the six changed 2B files was clean.

The final artifact for that revision is
[`2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v2-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v2-2-trials.json).
It uses prompt `gateway-generator-prompt-v5`, the unchanged response-schema
SHA-256 `173a1d66ef5091a0f44837583579fc1616b406f440ce15976b430bae53a5a680`,
the unchanged `planning-market-v1` policy, and casebook-v2 SHA-256
`65c455a9ca51f44ab98bd30800902271aab3077e578b2356b2bd1074e42a4b1d`.

The bounded final run has 16 records and 14 expected, constructed, attempted,
and reconciled calls: 11 nonempty outcomes, 3 empty outcomes, and 2 policy
skips; zero partial, rejected-all, or generation-failure outcomes. It accepted
35 candidates (7 origin access, 12 destination access, and 16 hubs) across 19
scopes; observed maxima were 2/2/3 within 2/2/5. The review records 65
accepted declared relationships, 36,772 input plus 19,745 output tokens
(56,517 total), zero rejected candidates, zero mismatch advisories, and
endpoint assessments for all 40 original endpoints. Cost is unestimated.
Final artifact-integrity and AI semantic review passed for owner human review;
this is not human semantic qualification.

## 2026-09-19 casebook-v3 expansion pre-live note (historical)

- Added the disclosed `development_cases_v3.yaml` without changing v1/v2
  fixtures or their historical artifacts. It preserves v2's eight scenarios
  and adds 15 catalog-pinned market-boundary and grouped-endpoint scenarios,
  including ITO→NRT and CDG→ATH.
- Updated the strict evaluator fixture contract to v3. The complete book has
  23 scenarios, two policy skips, and 21 generation cases: the two-trial
  bound is 42 calls, with no retry, refill, or same-model judging.
- Offline preflight and live results are recorded separately after their runs;
  this entry does not claim a v3 live evaluation result.

## 2026-09-19 casebook-v3 prompt-v6 closeout diagnostic

The casebook-v3 fixture SHA-256 is
`ba3b2e0efd73a2774da6af2950ff4addaf5e7763f754b49042dd56acec3b2f06`. It has
23 scenarios, two policy skips, and 21 generation cases, for 42 calls across
two trials with no retries or refill calls.

The first prompt-v5/v3 diagnostic completed mechanically but exposed
relationship multiplication: 46 records and 42 calls produced 125 accepted
candidates, 76 scopes, and 731 accepted relationships across 184,604 tokens.
Prompt-v6 added relationship-level uncertainty/scope reconciliation and
same-scope candidate consolidation. The response schema and adapter are
unchanged, as are the catalog, market policy, and deterministic validator.

The final public artifact is
[`2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json).
It records 46 case-trials and 42/42 expected, constructed, attempted, and
reconciled calls: 37 nonempty, 4 empty, 4 policy skips, and 1 partial; 82
accepted candidates (22 origin access, 18 destination access, and 42 hubs),
43 scopes, 400 accepted relationships, and 186,549 total tokens. One PNH
catalog-absence rejection and three model/policy market-mismatch advisories
were retained; there were zero errors or generation failures. Artifact/privacy
audit passed.

Before the v6 live run, the offline suite was **507 passed, 99 skipped**;
focused 2B checks (44 tests), Ruff, targeted mypy, and `git diff --check`
passed. A repository-wide Ruff format check is not a gate and reported 47
pre-existing unrelated files; no full-repository formatting claim is made.

Independent AI semantic review passed for owner human review, not human
qualification. It found a 45.3% relationship reduction and 34.4% candidate
reduction versus prompt-v5/v3, with no important omission observed. Residual
notes include 65 relationships for India, 55 for Los Angeles/Australia-New
Zealand, 36 for New York/Japan, one IPC→PPT circuitous regression, trial
variation, and a private control-character hygiene note. No prompt-v7 or
deterministic semantic-rejection change is currently recommended; 2C
relationship/search-work budgeting remains mandatory. M2A remains unadopted,
2C remains unimplemented.

## Owner close decision (2026-09-19)

The owner explicitly closed Milestone 2B and deferred consideration of Milestone 2C. Closure accepts
the implemented ADR 0020 boundary and the prompt-v6/casebook-v3 evidence record. It does not claim
independent human semantic qualification, verified connectivity, adoption of the diagnostic-only M2A
selector, or authorization to begin 2C. The durable learning and handoff record is
`docs/handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md`.
