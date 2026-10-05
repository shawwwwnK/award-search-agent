# ADR 0024: Deterministic award-led journey matching

- Status: Accepted; Ranking M1 owner-qualified and closed for its declared boundary
- Decision dates: 2026-09-25 opening; 2026-09-27 evidence-policy revision; 2026-09-30 closeout
- Recorded: 2026-10-04 (backfill of existing decisions; no new runtime policy)

## Context

Provider Stage returns observations, not assembled journeys. The owner's workflow requires
mechanically joining award itineraries to relevant cash positioning flights, checking timing and
requirements, and preserving useful alternatives for later explanation. ADR 0022 opens the intact
award and at-most-one-cash-component topology but leaves assembly to Ranking.

Sources: [design opening](../handoffs/2026-09-25-ranking-stage-design.md),
[September 27 decisions and evidence](../build-log/2026-09-27-ranking-m1-live-evidence-run.md),
and [M1 acceptance](../handoffs/2026-09-30-ranking-m1-closeout.md).

## Options

The recorded design chooses deterministic matching before model explanation over leaving
combination and feasibility judgments to the later Output/Results model. It also chooses intact
provider-returned awards with one cash access or egress component over general component assembly.
The September 27 evidence-policy choice was to retain the Seats.aero adapter and accept confirmed
journey-level cabin evidence for unreported legs, rather than requiring new per-leg adapter evidence
before admission. These are recorded alternatives, not a claim of a separate comparative experiment.

## Decision

Ranking consumes frozen request, plan and provider artifacts and produces a typed, replayable
`MatchedJourneySet`. Enumerate every compatible award/cash pairing within an authorized planning
dependency. Keep distinct observed variants and their provenance; group alternatives by award
family without substituting one variant's facts for another's.

Validate airport continuity, aware chronology, original outbound departure, supported requirements,
and separate-ticket obligations deterministically. The transfer must be at least two elapsed hours
and on the same or following local date at the transfer airport. This is the selected policy buffer,
not an airline minimum-connection-time or bookability guarantee.

Retain admitted, conditional, rejected and research outcomes with reasons. Missing requirement
evidence remains unresolved; missing price scope does not discard a useful schedule match or
manufacture a complete price. Direct cash remains a separate benchmark. Requested cabin applies
to the award component; cash cabin evidence remains visible.

Under matching policy m1-v2, confirmed matching award journey-level cabin is sufficient when leg
cabins are unreported. Unreported legs remain visible as nonblocking reasons; a reported
out-of-request leg cabin rejects. The owner also approved the gfly provider-returned `adults` echo
as returned-traveler evidence, recorded in the versioned cash capability; query-requested values
alone do not establish returned adequacy.

## Consequences

Results explains already classified journeys and cannot promote research or rejected observations
into validated recommendations. Conditional status and booking checks remain explicit. General
assembly, cash on both ends and expanded acquisition dates remain parked under D15/D18. This
refines ADR 0022's later matching boundary without reopening upstream request or planning policy.

## Evaluation

The closeout records 35 M1 tests and three byte-exact saved-output replays on September 30.
The September 27 provider capture supplies five admitted mixed egress journeys; the evidence covers
the declared matching boundary, not provider reliability, bookability or broader coverage.
Tests cover transfer/date boundaries, DST/date-line behavior, unknown requirements/prices,
variant accounting, provenance and direct-cash exclusion. See the linked closeout for evidence.
These are historical results, not tests rerun by this backfill.

## Revisit trigger

Revisit when the owner changes cabin/traveler evidence interpretation, transfer policy or topology,
or task evidence exposes unsafe admission or important excluded journeys. Require a versioned
policy, boundary tests and preserved source evidence for any change.
