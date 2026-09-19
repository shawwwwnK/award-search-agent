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
