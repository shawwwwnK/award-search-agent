# 2026-09-13: Search-planning milestone roadmap

## Work recorded

Recorded the owner-approved Milestone 0–4 roadmap for the search-planning
stage in `docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md`.

## Owner decisions recorded

- Milestone 0 is complete: the existing deterministic planner is
  fixture-qualified only.
- Milestone 1 is the active geographic and airport-data foundation. It must
  import GeoNames and OurAirports data and serve it deterministically through
  the existing local snapshot/repository boundary.
- Milestone 1 includes region resolution under named taxonomies.
- Airport-group curation beyond the existing examples proceeds iteratively
  after source data is available.
- Durable retention/storage of large raw source artifacts is on hold pending
  inspection of available data.
- Directed connectivity, reviewed strategy/RAG authoring, and evidence-driven
  coverage expansion are Milestones 2, 3, and 4 respectively.

## Files changed

- `AGENTS.md`
- `README.md`
- `docs/architecture.md`
- `docs/project-state.md`
- `docs/workboard.md`
- `docs/handoffs/2026-09-12-search-planning-design.md`
- `docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md`

## Verification

- Documentation-only update. No source data was downloaded, imported, or
  retained; no planner contracts, fixtures, dependencies, or provider behavior
  changed.
- `git diff --check` required before closing.

## Milestone 2 goal correction (2026-09-16)

The owner clarified that the operational planning need is not a route catalog
for its own sake. A required O -> D endpoint-market award search may omit a
useful split strategy, such as independently searching from a connection or
gateway airport after a separate positioning leg. Milestone 2 therefore owns
the ability to provide bounded, explainable candidate gateway airports and
supplemental award-search strategies while retaining O -> D probes.

The roadmap now treats directed topology and strict route-evidence rules as
possible supporting mechanisms to evaluate, rather than as an assumed
Milestone 2 deliverable. The later award-search/result stage remains
responsible for actual returned itinerary topology, award availability, and
itinerary validation.

No code, fixtures, source data, or provider behavior changed. The owner has
not selected a candidate-generation mechanism or initial operational coverage.

## Milestone 2 decomposition (2026-09-16)

The owner divided the operational planning expansion into three increments:

- **2A: endpoint airport grounding** — supported region/country/area/city or
  explicit-airport requests become bounded reviewed endpoint airport sets;
- **2B: gateway-airport discovery** — selected departure/destination airport
  sets receive bounded candidate connection/gateway airports; and
- **2C: search-strategy compilation** — required direct endpoint-market and
  optional supplemental award-search strategies are compiled from those sets.

The roadmap records objectives, components, and decision gates for each
increment. This is a documentation-only scope decomposition; no mechanism,
coverage set, source data, contracts, fixtures, or provider behavior was
selected or changed.

## Milestone 2B implementation update (2026-09-19)

Milestone 2B's approved versioned market policy, one-call grouped generator,
relationship-aware validator, immutable replay record, and eight-case
development evaluator are now implemented. The final prompt-v2 diagnostic is
mechanically complete and recorded in
[`2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json).

This update does not close the Milestone 2A adoption gate or implement Milestone
2C. The 2B diagnostic requires human semantic review before any qualification
or next-cut decision, and its candidates remain unverified hypotheses rather
than connectivity, availability, or booking facts.

## Milestone 2B revision update (2026-09-19)

The owner approved a narrow revision: access gateways may be materially
complementary alternatives even for already-strong endpoints when they have
specific incremental value. Size, proximity, shared market, or geographic
diversity alone is insufficient. The independent candidate maxima are 0–2
origin access, 0–2 destination access, and 0–5 hubs (nine total), with no
intermediate-hub market-diversity quota. 2C remains unimplemented; its future
budget applies to compiled relationships/search items, preserves mandatory
original coverage, and records budget omissions without relabeling candidates
invalid.

The disclosed v2 casebook now uses SAI and KTI only for the Southeast Asia
scenario. The v1 casebook hash
`9f4a1593ae7d06d132faaf5e5d3895f56823136f97a66d4bbde45292edb6789b` and its
artifacts are historical. Prompt-v3 exposed saturation (58 accepted candidates,
34 hubs); prompt-v4 reduced burden but regressed IPC circuitousness and
endpoint assessment. The final prompt-v5 rules address those issues without
changing the schema or adapter.

Offline evidence: **507 passed, 99 skipped**; Ruff and diff checks clean; and
targeted mypy for six changed 2B files clean. The final public artifact is
[`2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v2-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v2-2-trials.json),
with casebook-v2 SHA-256
`65c455a9ca51f44ab98bd30800902271aab3077e578b2356b2bd1074e42a4b1d` and
unchanged response-schema/policy identities. It has 16 records and 14
expected/constructed/attempted/reconciled calls: 11 nonempty, 3 empty, 2
skips, and zero partial/rejected/generation failures. It accepted 35 candidates
(7 origin access/12 destination access/16 hubs), 19 scopes, and 65 declared
relationships; observed maxima were 2/2/3 within 2/2/5. It recorded 36,772
input plus 19,745 output tokens (56,517 total), zero rejected candidates, zero
mismatch advisories, and endpoint assessments for all 40 originals. Cost is
unestimated. Final artifact-integrity and AI semantic review passed for owner
human review, not human qualification.

## Milestone 2B casebook-v3 prompt-v6 closeout (2026-09-19)

The v3 fixture SHA-256 is
`ba3b2e0efd73a2774da6af2950ff4addaf5e7763f754b49042dd56acec3b2f06`. The
23-case book has two policy skips and 21 generation cases, giving 42 calls
across two trials. The first prompt-v5/v3 diagnostic is historical evidence:
46 records and 42 calls yielded 125 accepted candidates, 76 scopes, and 731
accepted relationships across 184,604 tokens, exposing relationship
multiplication.

Prompt-v6 added relationship-level uncertainty/scope reconciliation and
same-scope candidate consolidation without changing the response schema,
adapter, catalog, policy, or deterministic validator. The final public artifact
is [`2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json).
It records 46 case-trials and 42/42 expected, constructed, attempted, and
reconciled calls: 37 nonempty, 4 empty, 4 policy skips, and 1 partial; 82
accepted candidates, 43 scopes, 400 accepted relationships, and 186,549
tokens. One PNH catalog-absence rejection and three market-mismatch advisories
were retained; there were zero errors or generation failures. Artifact/privacy
audit passed.

Offline verification before live evaluation recorded **507 passed, 99 skipped**;
focused 2B checks (44 tests), Ruff, targeted mypy, and `git diff --check`
passed. Repository-wide Ruff format is not a gate and reported 47 unrelated
pre-existing files; no full-repository formatting claim is made.

Independent AI semantic review passed for owner human review, not human
qualification. It measured 45.3% fewer relationships and 34.4% fewer
candidates versus prompt-v5/v3, with no important omission observed. Residual
notes include high relationship counts for India and Los Angeles/Australia-New
Zealand, New York/Japan volume, one IPC→PPT circuitous regression, trial
variation, and a private control-character hygiene note. No prompt-v7 or
deterministic semantic-rejection change is currently recommended; 2C
relationship/search-work budgeting remains mandatory. M2A remains unadopted,
2C remains unimplemented.

## Milestone 2B owner close decision (2026-09-19)

The owner explicitly closed Milestone 2B after the prompt-v6/casebook-v3 diagnostic, artifact audit,
and independent AI semantic review. The stage is closed with residual scope-volume, circuitousness,
trial-variation, and text-hygiene findings preserved; no independent human semantic qualification or
connectivity claim is made. Milestone 2C is deferred until explicitly opened. See
`docs/handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md`.
