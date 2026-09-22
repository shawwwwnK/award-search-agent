# 2026-09-21 — M2A adoption, planning-boundary qualification, and M0 retirement

## Owner decisions recorded

The owner adopted Milestone 2A as the official endpoint-airport source for exactly resolved
geographic entities. Explicit IATA and uniquely resolved named airports remain direct catalog
singletons. The owner also stated that they monitored the builds and reviewed the results, and
qualified each completed search-planning milestone—M1, M2A, M2B, and M2C—for its declared boundary.

M0 is retired rather than an active completed milestone. Its executable JSON/group compatibility
surface is removed. Historical evidence remains preserved. Separately retained Seats.aero research
is relocated under provider-capability ownership, not retained as an M0 planner input.

## Claim boundary

- M2A selections retain model-proposed provenance and do not become catalog facts.
- M2B candidates remain unverified search hypotheses, not route or connectivity facts.
- M2C remains provider-neutral deterministic planning only.
- These owner qualifications do not claim independent external or holdout corroboration, provider
  execution or availability, validated itineraries, product behavior, or recommendations.
- Independent review, holdout evidence, and useful-coverage measurement may inform later policy
  revision; they are not prerequisites to the owner's completed qualification decision.

## Implementation and verification

The implementation made M2A replay the sole geographic endpoint source, retained direct singleton
grounding for explicit IATA and uniquely resolved named airports, removed the alternate reviewed
mapping path, and bound M2A plans as `owner_qualified_model_proposed` while preserving each airport
projection as `model_proposed`. The compiler and planning-policy identities advanced to v3, and the
active offline casebook was repinned without rewriting prior live artifacts.

The retired executable surface includes the M0 JSON snapshot/repository, reviewed group selection,
group caps, route/path exploration, legacy award-search item, payment/manual-cash contracts, V1
corpus, and its dedicated grounding tests. The retained Seats.aero capability record moved from
`data/search_planning/v1/` to `data/provider_capabilities/`; its content remains provider research,
not planning input.

Verification recorded during the implementation and integration review:

```text
focused M2A/direct/catalog checks: 4 passed
active evaluation/golden suite after capability relocation: 7 passed
broader scoped planning suite: 35 passed
focused contracts/compiler/endpoint suite after final dead-contract cleanup: 18 passed
tests/unit/test_intent_to_search_planning_live_eval.py: 5 passed
Ruff: passed
targeted mypy for search-planning and the active evaluator: passed
exact-reference audit for retired M0 symbols and paths: clean
git diff --check: passed
```

A broad `tests/unit` run reached 340 passed and zero failures in 6 minutes 15 seconds before it was
manually stopped during repeated large-catalog publication hashing/copying. That partial run is not
reported as a complete whole-suite pass. Repository-wide mypy still reports 49 pre-existing
clarification-stage errors outside this change; the scoped 16-file type check passed.

### Files changed

- endpoint selection, catalog access, compilation contracts, planning policy, evaluator pins, and
  their focused tests;
- current-state documentation, ADR 0023, milestone handoffs, and deferred-work dispositions;
- deleted M0 JSON/corpus/test artifacts; and
- relocated provider capability research.

## Follow-up

With the owner marking search planning complete, the next separately authorized work remains the
award-first provider/result stage. Its goal is approved under ADR 0022, but its implementation and
qualification are not supplied by this session.
