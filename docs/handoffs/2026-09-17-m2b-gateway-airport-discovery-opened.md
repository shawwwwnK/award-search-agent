# Milestone 2B: Gateway-airport discovery implementation and review handoff

- Status: Implemented; prompt-v6/casebook-v3 diagnostic complete, owner/human semantic review open
- Opened: 2026-09-17; implementation/evaluation, prompt-v5/casebook-v2, casebook-v3, and prompt-v6 update: 2026-09-19
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

The pools are independently bounded at 0–2 origin access gateways, 0–2
destination access gateways, and 0–5 intermediate hubs (nine candidates at
most). These are maxima, not targets; an access candidate does not lower the
hub cap. An access candidate may be a materially complementary alternative
even for an already-strong endpoint, but then requires specific incremental
value relative to the opposite market and selected alternatives. Size,
proximity, shared market, or geographic diversity alone is insufficient.
There is no intermediate-hub market-diversity quota.

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
  items remain Milestone 2C responsibilities. If opened, 2C must preserve those
  mandatory probes, budget compiled relationships/search items rather than raw
  candidate count, and record budget omissions without recasting accepted
  candidates as invalid.

## Evidence and remaining gate

The opening transition and the narrow implementation are complete. The result
is a small versioned market policy, a single-call structured generator, a
relationship-aware validator that retains safe subsets, and an immutable replay
record. The completed prompt-v5/casebook-v2 development artifact is historical evidence:
[`2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v2-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v2-2-trials.json);
prompt-v1 through prompt-v4 artifacts remain diagnostic iterations and the v1
casebook remains historical evidence. The current disclosed casebook is v3:
it preserves v2's eight scenarios and adds 15 catalog-pinned scenarios, for
23 total cases, two same-market skips, and 21 generation cases. Its two-trial
live bound is 42 calls with no retry or refill. No v3 live result is claimed
as qualification: the prompt-v6/casebook-v3 live diagnostic is complete, while
owner and human semantic qualification remain open.
Its protocol is [`gateway-discovery-evaluation-protocol.md`](../evaluation/gateway-discovery-evaluation-protocol.md).

This is not an adoption or semantic-qualification decision. Human review must
still assess usefulness, scope, omissions, weak extras, access-role fit,
uncertainty, and variation. Milestone 2C remains unimplemented and would be
responsible for preserving mandatory endpoint coverage, budgeting compiled
relationships/search items rather than raw candidate count, recording budget
omissions without relabeling candidates invalid, and consolidating accepted
unverified hypotheses and their mapping gaps/advisories into bounded
supplemental search work.

## Prompt-v6 / casebook-v3 final diagnostic

The casebook-v3 SHA-256 is
`ba3b2e0efd73a2774da6af2950ff4addaf5e7763f754b49042dd56acec3b2f06`; it has
23 scenarios, two same-market skips, and 21 generation cases. The first
prompt-v5/v3 diagnostic is historical: 46 records and 42 calls produced 125
accepted candidates, 76 scopes, and 731 accepted relationships across 184,604
tokens, exposing relationship multiplication.

Prompt-v6 added relationship-level uncertainty/scope reconciliation and
same-scope candidate consolidation. The schema, adapter, catalog, policy, and
deterministic validator remain unchanged. The final public artifact is
[`2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json).
It records 46 records and 42/42 calls across two trials: 37 nonempty, 4
empty, 4 policy skips, and 1 partial; 82 accepted candidates (22 origin
access, 18 destination access, and 42 hubs), 43 scopes, 400 accepted
relationships, and 186,549 tokens. One PNH catalog-absence rejection and
three market-mismatch advisories were retained; there were zero errors or
generation failures. Artifact/privacy audit and independent AI semantic review passed for
owner human review, not human qualification. Review found a 45.3% reduction
in relationships and 34.4% reduction in candidates versus prompt-v5/v3, with
no important omission observed. Residual notes are high relationship counts
in the India and Los Angeles/Australia-New Zealand cases, New York/Japan
volume, one IPC→PPT circuitous regression, trial variation, and a private
control-character hygiene note. No prompt-v7 or deterministic semantic
rejection change is currently recommended; 2C budgeting remains mandatory.
