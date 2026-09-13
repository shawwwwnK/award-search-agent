# 2026-09-13: Operational knowledge-base expansion opened

## Work recorded

The owner selected operational knowledge-base expansion as the next active cut, before provider
execution. This entry changes project sequencing only; it does not alter the implemented
fixture-qualified `EffectiveRequest -> SearchPlan` boundary or add knowledge records.

## Active scope

- Declare an initial operational coverage rather than imply global geographic coverage.
- Expand the checked-in seed into reviewed, versioned records for geographic entities and narrow
  aliases, airport identity and timezones, factual location-to-airport relations, airport-selection
  preferences, and directed physical topology.
- Retain source, verification, freshness, and date-applicability receipts with each factual record.
- Add a coverage manifest and market-specific offline evidence. Requests outside declared coverage
  must remain visibly unsupported or reduced-coverage outcomes.

## Preserved boundaries

- The existing seed and ten-case planner golden gate remain fixture-qualified only; they do not
  demonstrate operational airport, route, schedule, inventory, or provider coverage.
- No provider adapter, provider payload, live provider call, response parsing, normalization,
  ranking, or cash-search automation is in this cut.
- Free-text upstream hard constraints remain preserved deferred obligations. Typed, value-validated
  upstream constraints are a separate follow-on before requirements may be claimed as provider
  filters.
- The work does not require a global airport or route database before a bounded initial coverage can
  be called operational.

## Documentation updated

- `AGENTS.md`
- `README.md`
- `docs/architecture.md`
- `docs/project-state.md`
- `docs/workboard.md`
- `docs/handoffs/2026-09-12-search-planning-design.md`

## Verification

- Documentation-only change; no production code, fixtures, or provider access changed.
- `git diff --check` is required before closing this documentation update.
