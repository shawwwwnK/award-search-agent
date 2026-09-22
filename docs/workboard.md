# Workboard

## Now

- The original snapshot-backed `SearchPlan` gate is historical. Current search planning is the
  provider-neutral `CompiledSearchPlan` boundary described below; its offline verification makes no
  provider or network calls.
- Milestone 1 is complete. Milestone 2A endpoint-airport selection is implemented and has completed
  its active-policy diagnostic, but remains diagnostic-only pending independent human semantic
  review, holdout evidence, and an adoption decision.
- **Milestone 2B: gateway-airport discovery** is implemented and owner-closed as of 2026-09-19.
  ADR 0020's approved global
  planning-market policy, one-call grouped generator, relationship-aware validator, and immutable
  replay record are offline-verified. The prompt-v5/casebook-v2 and first prompt-v5/casebook-v3
  diagnostics are historical evidence; the final prompt-v6/casebook-v3 run is mechanically complete
  for the current 23-scenario development set.
  Access alternatives may serve already-strong endpoints only for specific incremental value, and
  its independent 2/2/5 pool caps carry no intermediate-market diversity quota.
  The owner accepted the implemented boundary and evidence record for closure; independent human
  semantic qualification is not claimed.
- **Milestone 2C: deterministic search-strategy compilation** is implemented in place with no V1
  compatibility path. Its active provider-neutral contract compiles mandatory and every replay-valid
  representable supplemental pair-level logical query, with semantic deduplication, provenance,
  obligations, dispositions, and replay bindings. The only compiler limit is the all-or-nothing
  100-pair structural guard. It makes no model or provider call. See the
  [implementation record](build-log/2026-09-19-m2c-implementation.md) and
  [provider-neutral revision](build-log/2026-09-20-m2c-provider-neutral-revision.md).
- Typed upstream constraints before hard filters can be claimed, provider adapter semantic
  acceptance, and provider execution remain separate follow-ons. See the completion map in
  `docs/handoffs/2026-09-12-search-planning-design.md`.
- Preserve the frozen ADR 0016/0017 upstream boundary. Milestone 2C has no provider calls, payload
  mapping, provider-result parsing, normalization, ranking, or recommendation generation.
- **The next provider/result stage: award-first observations and cash positioning** has an
  owner-approved goal and no implementation yet. It executes M2C output rather than adding another
  planning milestone. ADR 0022 keeps pure-cash endpoint observations outside the ranked award list,
  while permitting a validated cash access or egress component inside an award-led recommendation.
  The active runtime remains unchanged until this stage is implemented and accepted.

Historical Milestone 0 boundary and fixture gate:
`docs/handoffs/2026-09-10-search-plan-design-stage.md` and
`docs/handoffs/2026-09-12-search-planning-design.md`.
Current Milestone 0–4 roadmap:
`docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md`.

## Next

- Implement the separately approved provider/result plan only after reviewing its award and cash
  capability contracts, execution budgets, replay fixtures, normalized observation contract,
  direct-cash non-ranking boundary, and bounded mixed-candidate validation. Start offline; authorize
  the bounded live task separately.
- Review the model-only 2C diagnostic as development evidence. It does not adopt M2A, reopen 2B, or
  establish independent human semantic qualification.

## Later

Use the root [DEFERRED.md](../DEFERRED.md) for the maintained register. It separates
core provider/result/output work from optional post-core enhancements and records
the evidence needed to revisit each entry. Do not maintain a second competing
deferred list here.
