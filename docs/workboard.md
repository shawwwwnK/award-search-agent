# Workboard

## Now

- Search planning is implemented and fixture-qualified for its explicitly narrow local snapshot.
  `award-search-planning-eval` runs the ten-case deterministic offline gate; it does not make
  provider or network calls.
- The active next cut is **Milestone 1: geographic and airport-data foundation**. Import and serve
  GeoNames and OurAirports data through the local snapshot/repository boundary; support named
  region-taxonomy resolution; and publish explicit catalog/group coverage. Airport-group curation
  expands iteratively. The operational catalog publication will use SQLite with a JSON manifest
  under ADR 0018. Directed topology is Milestone 2, not part of this first cut.
- Typed upstream constraints before hard filters can be claimed, provider adapter semantic
  acceptance, and provider execution remain separate follow-ons. See the completion map in
  `docs/handoffs/2026-09-12-search-planning-design.md`.
- Preserve the frozen ADR 0016/0017 upstream boundary. This stage has no provider calls, payload
  mapping, provider-result parsing, normalization, ranking, or recommendation generation.

Boundary: `docs/handoffs/2026-09-10-search-plan-design-stage.md`.
Implemented Milestone 0 design and fixture gate:
`docs/handoffs/2026-09-12-search-planning-design.md`.
Current Milestone 0–4 roadmap:
`docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md`.

## Next

- Complete Milestone 1 source import, deterministic lookup, source evidence, taxonomy, and
  coverage-manifest design before beginning connectivity.
- Revisit raw-source-artifact retention only after imported data is available for inspection.

## Later

- Adaptive search planning.
- Additional providers.
- Provider-result normalization and validation.
- Ranking and explanation.
- Persistence and trace history.
- Web interface and deployment.
- Selective RAG for changing loyalty rules.

This is not intended to become a detailed, long-range backlog.
