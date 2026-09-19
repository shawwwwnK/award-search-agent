# Milestone 2B: Gateway-airport discovery implementation and review handoff

- Status: Implemented; prompt-v2 diagnostic mechanically complete, human semantic review open
- Opened: 2026-09-17; implementation/evaluation update: 2026-09-19
- Boundary: Selected endpoint airport sets to a policy skip or bounded unverified candidates

## Purpose

Milestone 2B uses deterministic planning-market policy plus one grouped model
proposal to produce a small, explainable set of airports that may justify
supplemental award searches beyond the required departure-to-destination
endpoint market. It does not compile those searches; that is Milestone 2C.

The conceptual boundary is:

```text
selected departure airports + selected destination airports + versioned market policy
  -> single-known-market skip | one grouped proposal and bounded validation record
```

ADR 0020 now supersedes the opening mechanism question for this version. The
approved direction is a versioned global planning-market policy, one grouped
structured model proposal when generation is required, deterministic catalog
and relationship validation, and an immutable candidate-selection record.

## Preserved predecessor status

Milestone 1 is complete. Milestone 2A implemented a bounded model-proposed
endpoint selector and completed its active-policy v3 diagnostic, but the
selector remains diagnostic-only. Independent human semantic review,
preregistered holdout evidence, evidence that larger caps improve useful
coverage relative to planner work, and an adoption decision remain open.

Opening 2B does not satisfy that gate. Early interface and fixture work may
consume manually reviewed endpoint sets or supplied immutable selection
records, but it must not treat an M2A model proposal as a reviewed geographic
fact or claim operational endpoint coverage.

## Implemented cut

The completed 2B implementation:

1. Load and validate the approved global planning-market policy separately from
   physical catalog metadata, with explicit airport-override, country-mapping,
   and mapping-gap provenance.
2. Skip generation only when both endpoint sets are nonempty, every endpoint
   has a known market, and the union of all origin and destination markets has
   exactly one member. Equality of multi-market side sets is insufficient.
3. Make one grouped structured model call for every other valid input. An
   unknown endpoint market forces generation and is passed as explicit unknown
   context; it is not treated as evidence of shared or cross-market membership.
4. Validate airport identity, retained-facility eligibility, pool bounds,
   references, applicability, duplicates, self-reference, and dependency
   integrity deterministically while retaining safe valid subsets.
5. Preserve model/policy candidate-market disagreement as a nonfatal advisory
   observation for 2C consolidation, not a candidate rejection.
6. Record all input, catalog, policy, prompt/schema/model, proposal, validation,
   coverage, and non-claim identities needed for replay and inspection.

## Truthful outcomes and non-claims

- A missing market-policy assignment is an `unknown_mapping_gap` classification.
  It prevents a same-known-market skip but does not withhold grouped generation.
  It is neither a catalog-identity failure nor a claim about connectivity.
- Market classification and generation result are independent. A structured
  empty proposal, a partial/rejected proposal, and an operational or systemic
  failure remain distinguishable from a policy skip and from mapping coverage.
- A model-asserted candidate market is provenance. Deterministic policy
  classification is recorded separately; disagreement is handed to 2C and does
  not by itself reject a catalog-valid candidate or scope.
- A gateway candidate is a planning hypothesis for possible supplemental
  search. It is not evidence of a scheduled flight, feasible or protected
  connection, through-ticket, baggage handling, award availability, or
  bookability.
- Gateway discovery does not infer that the traveler accepts positioning, does
  not mutate `EffectiveRequest`, and does not reparse conversation text.
- 2B makes no award or cash provider call and does not map provider payloads,
  normalize results, rank recommendations, or write generated facts into the
  Milestone 1 catalog.
- Required endpoint-market probes and the compilation of supplemental search
  items remain Milestone 2C responsibilities.

## Evidence and remaining gate

The opening transition and the narrow implementation are complete. The result
is a small versioned market policy, a single-call structured generator, a
relationship-aware validator that retains safe subsets, and an immutable replay
record. The prompt-v2 development artifact is
[`2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json);
its protocol is [`gateway-discovery-evaluation-protocol.md`](../evaluation/gateway-discovery-evaluation-protocol.md).

This is not an adoption or semantic-qualification decision. Human review must
still assess usefulness, scope, omissions, weak extras, access-role fit,
uncertainty, and variation. Milestone 2C remains unimplemented and would be
responsible for preserving mandatory endpoint coverage while consolidating
accepted unverified hypotheses and their mapping gaps/advisories into bounded
supplemental search work.
