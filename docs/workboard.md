# Workboard

## Now

- Search planning is implemented and fixture-qualified for its explicitly narrow local snapshot.
  `award-search-planning-eval` runs the ten-case deterministic offline gate; it does not make
  provider or network calls.
- Milestone 1 is complete. Milestone 2A endpoint-airport selection is implemented and has completed
  its active-policy diagnostic, but remains diagnostic-only pending independent human semantic
  review, holdout evidence, and an adoption decision.
- **Milestone 2B: gateway-airport discovery** is implemented. ADR 0020's approved global
  planning-market policy, one-call grouped generator, relationship-aware validator, and immutable
  replay record are offline-verified. The prompt-v5/casebook-v2 and first prompt-v5/casebook-v3
  diagnostics are historical evidence; the final prompt-v6/casebook-v3 run is mechanically complete
  for the current 23-scenario development set.
  Access alternatives may serve already-strong endpoints only for specific incremental value, and
  its independent 2/2/5 pool caps carry no intermediate-market diversity quota.
  Independent human semantic review and the owner's next-cut decision remain open.
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

- Review the completed prompt-v6/casebook-v3 2B development evaluation against the documented
  usefulness, scope, omission, weak-extra, access-role, uncertainty, and variation rubric; do not
  infer quality from valid IATA codes or mechanical completion. The v2 and v5/v3 diagnostics remain
  historical evidence only.
- Make an owner decision on the next cut after that review. 2C remains unimplemented: it would
  preserve mandatory endpoint coverage, budget compiled relationships/search items rather than raw
  candidate count, record budget omissions without relabeling candidates invalid, and compile bounded
  supplemental searches from accepted unverified hypotheses and their issues/advisories.

## Later

- Milestone 2C direct-plus-supplemental search-strategy compilation.
- Adaptive search planning.
- Additional providers.
- Provider-result normalization and validation.
- Ranking and explanation.
- Persistence and trace history.
- Web interface and deployment.
- Selective RAG for changing loyalty rules.

This is not intended to become a detailed, long-range backlog.
