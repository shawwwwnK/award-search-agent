# 2026-09-10: Search-plan stage scoped

## Owner-directed scope change

The project owner narrowed the next stage to `EffectiveRequest -> SearchPlan`. The plan represents
expected future Seats.aero search items only. Provider calls, provider adapters, result
normalization, ranking, and recommendations are deferred to later stages.

The owner identified two design problems that must be addressed before implementation:

- retrieval-backed resolution from city, region, country, or airport candidates to stable airport
  sets; and
- grounded connection discovery that can add separately searched legs, such as SFO to an eligible
  intermediate airport and that airport to BKK.

The owner will review an external high-level design before implementation. No code, evaluation, or
provider call was performed in this documentation session.

## Documentation changed

- `docs/project-state.md`
- `docs/architecture.md`
- `docs/workboard.md`
- `docs/handoffs/2026-09-10-search-plan-design-stage.md`
- `docs/provider-feasibility/2026-09-08-initial-provider-intake.md`
- `README.md`

## Preserved boundaries

ADR 0015 remains closed. The frozen initial workflow and clarification-session semantics remain
unchanged. The new stage does not authorize raw-text parsing, provider integration, or a model
that invents airport/connection facts without grounded retrieval evidence.
