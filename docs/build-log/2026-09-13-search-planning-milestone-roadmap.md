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
