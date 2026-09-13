# Workboard

## Now

- Search planning is implemented and fixture-qualified for its explicitly narrow local snapshot.
  `award-search-planning-eval` runs the ten-case deterministic offline gate; it does not make
  provider or network calls.
- The active next cut is operational knowledge-base expansion: establish an explicit initial
  coverage manifest, then add reviewed, versioned geography/alias, airport, factual relation,
  airport-group policy, and directed-topology records with source, freshness, and applicability
  receipts. This is deliberately narrower than a global airport or route database.
- Typed upstream constraints before hard filters can be claimed, provider adapter semantic
  acceptance, and provider execution remain separate follow-ons. See the completion map in
  `docs/handoffs/2026-09-12-search-planning-design.md`.
- Preserve the frozen ADR 0016/0017 upstream boundary. This stage has no provider calls, payload
  mapping, provider-result parsing, normalization, ranking, or recommendation generation.

Boundary: `docs/handoffs/2026-09-10-search-plan-design-stage.md`.
Implemented design and fixture gate:
`docs/handoffs/2026-09-12-search-planning-design.md`.

## Next

- Define the initial operational market and its knowledge coverage; expand the reviewed snapshot
  and its market-specific offline evidence before provider execution.
- Add the Seats.aero provider adapter only after that declared operational knowledge coverage is
  in place and its boundary is evidenced.

## Later

- Adaptive search planning.
- Additional providers.
- Provider-result normalization and validation.
- Ranking and explanation.
- Persistence and trace history.
- Web interface and deployment.
- Selective RAG for changing loyalty rules.

This is not intended to become a detailed, long-range backlog.
