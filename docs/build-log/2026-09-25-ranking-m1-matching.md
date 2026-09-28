# 2026-09-25: Ranking M1 deterministic matching

## Objective

Implement the owner's first Ranking Stage milestone: assemble intact provider-returned award
itineraries with at most one plan-authorized cash access or egress component, validate the
whole journey and separate-ticket connection, preserve uncertain evidence, and account for
every in-scope pairing. M2 heuristic ordering and the LLM Output Stage remain separate.

## Implementation record

The new `award_agent.ranking` boundary consumes a frozen `CompiledSearchPlan`, its
`EffectiveRequest`, and an attached `ProviderResultSet`. It reuses Provider Stage attachment
validation before pairing. Cash eligibility follows the physical cash query's positioning
dependency through its support alternative and award query use. The cash query's activating
award observation remains provenance; it is not the sole eligible award for a supported
dependency. Direct cash observations remain benchmarks outside journey construction.

Each scoped award/cash cross product receives a candidate disposition and reasons: admitted
for modeled checks that pass, conditional when required evidence is unresolved, rejected for
affirmative violations, and research lead when route or timing detail is insufficient. The
contract embeds the complete plan, request, provider result, provenance, coverage, and field
unknowns for later ranking/output work. It retains distinct observed cash variants, with
option grouping available by award and support identity. A versioned 100,000-pair structural
guard fails explicitly before returning a partial candidate set; it is not a top-N ranking.

The offline `award-ranking-match` command reads a saved provider bundle/result and writes a new
deterministic `MatchedJourneySet` JSON artifact. It makes no model or provider call.

## Review checkpoints

1. Architecture review specified exact graph joins, UTC and local-date rules, conditional versus
   research-lead handling, preservation of unknown fields, and full pairing accounting.
2. Independent contract/engine review found and returned missing cash-structure, chronology,
   output-integrity, and price-scope defects to implementation. The final targeted review
   reproduced and then verified fixes for forged strategy, activation, and logical-query
   references. It found no remaining blocker in its reported findings. Cash egress admission is
   exercised synthetically; saved live evidence covers access only.

## Final verification

The three Ranking M1 test modules passed (32 tests). They include exact 119m59s/120m/121m
self-transfer boundaries, same/next/two-days-later local dates, DST/date-line conversion,
provider-leg continuity, known cabin/seat failures, unknown cash structure and price scope,
stale/mismatched attachment, output tampering, fanout, and offline CLI behavior. The combined
provider-plus-M1 regression gate passed (98 tests). Scoped Ruff and `git diff --check` passed.

The two [saved M1 outputs](../../evidence/ranking-stage/m1/README.md) were generated offline:

| Source | Direct award | Mixed conditional | Mixed rejected | Mixed pairs |
| --- | ---: | ---: | ---: | ---: |
| `mixed_access` | 17 admitted | 240 | 216 | 456 |
| `exact_business` | 0 | 106 | 290 | 396 |

All 852 in-scope mixed pairs are retained and accounted for. Direct cash is separate. The
conditionals have modeled schedule continuity but unresolved returned traveler/cabin or
positioning permission evidence. The admitted direct awards pass modeled M1 checks but do not
carry a booking or complete-price claim. The October 4 exact-business awards paired with
October 5 cash flights are rejected for reversed chronology, not silently dropped. These
measurements reflect two partial provider executions and do not imply complete market coverage.
Both saved M1 JSON outputs were regenerated independently by the offline CLI and compared
byte-for-byte with their saved files. Local links in changed active documents and a direct scan
for the configured Seats.aero secret in the two M1 artifacts passed.

An optional repository-wide `.venv/bin/pytest -q` run reached 416 passing tests before it was
interrupted after 192 seconds while working through a slow search-planning catalog test. It
reported no failure before interruption. The 98-test scoped gate above is the completion test
for the affected boundaries.

## Owner interpretation and next cut

The owner authorized M1 implementation and requested agent review after major checkpoints.
No M2 scoring weights or Output Stage opening were decided in this session.
<!-- Preserve any further owner conclusion or next-cut decision here. -->
