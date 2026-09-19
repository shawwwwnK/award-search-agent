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
