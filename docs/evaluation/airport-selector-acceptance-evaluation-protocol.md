# Airport-selector evaluation protocol

## Purpose and boundary

This protocol evaluates the M2A model-proposed endpoint-airport selector. It
does not evaluate request parsing, airport-service facts, routes, schedules,
award availability, provider execution, or a worldwide airport graph. The
model proposes an endpoint set only after deterministic resolution has fixed a
canonical entity and category. Deterministic code validates bounded response
shape and only catalog-supported metadata.

The first live run is a diagnostic, not a standalone qualification claim. The owner separately
adopted and qualified the selector boundary on 2026-09-21 through ADR 0023; that decision does not
retroactively turn this individual run into independent corroboration.

## Corpus and splits

`evals/airport_selector/development_cases_v3.yaml` is the active disclosed
development casebook. It covers ordinary/default cities and countries;
San Francisco, New York City, London, and Los Angeles at their approved
city/metro caps; United States at its approved cap of 10, China and India at
their approved caps of 6; sub-country regions; continents; and an
unclassified geographic region using the broad fallback. Each case expresses
must-consider alternatives, acceptable alternatives, unacceptable choices, and
a review focus. The city/metro cases review practical metro-serving usefulness;
the country cases review international-gateway coverage. Neither is an
airport-membership list or a catalog assertion of a serving relationship.

The active cap-policy digest is
`a3b493cc8c271e78217d99dcc89bcfa7eb8089bb7310a6f2489ae5d9cd915256`.
`development_cases_v1.yaml` and its associated 2026-09-17 live artifact are
preserved historical pre-override evidence. `development_cases_v2.yaml` and
its active-cap-overrides v2 artifact are preserved historical US=6 evidence:
they do not measure or validate the active US=10 policy. The completed v3
artifact is the active-policy diagnostic evidence; neither historical artifact
may support a US=10 coverage claim.

Synthetic offline tests cover response shapes, fewer-than-cap acceptance,
exactly-at-cap acceptance, over-cap rejection, duplicates, invalid/absent
identities, country contradiction, missing metadata, and the city-distance
policy. Those cases are not semantic evidence about a live model.

For independent qualification and future policy review, an evaluator should prepare an external
holdout (suggested eight cases) and retain it outside this workspace. It should
contain different entities in the same families, ambiguous/weak-metadata
contexts, and plausible-but-inappropriate valid IATA choices. Do not invent a
secret casebook here; record only its later version/hash and aggregate results.

## Preregistered diagnostic run

Run both prompt arms with the same model/configuration and schema:

- `original_simple`: the initial compact instruction, represented as strict
  structured output only for wire compatibility;
- `refined`: the narrow scope/cap/abstention instruction.

Use three trials per case by default. The runner may be limited for a smoke
test, but any limited run must state its selected cases, arms, and trial count.
There are no model retries or rejected-candidate refill calls. Record model ID,
adapter version, prompt version, response-schema hash, casebook hash, catalog
receipt, cap/distance-policy digest, selection outcomes, usage, latency, and
trace reconciliation. No cost estimate is made without a versioned official
price card captured with the run.

Private traces are written under ignored `evals/airport_selector/traces-live/`.
They contain raw model-facing input, raw provider responses, and provider-error
detail. The public artifact contains no user utterance, full prompt, raw
provider response, or provider-error message; validated proposal and selection
IATA codes may appear as reviewable evidence. Trace reconciliation requires
each attempted selector call to have a sidecar trace and captured usage;
failures are reported, not hidden.

## Human scoring

For each run and aggregate by family/prompt arm, report separately:

- response/schema errors and invalid identities caught by validation;
- duplicate and over-cap behavior;
- accepted identity-valid airports that are nevertheless inappropriate;
- must-consider omissions;
- weak extras and their estimated search-budget cost, including the explicit
  `10 x 4`/`10 x 5`/`10 x 6` US maximum pair counts of 40/50/60 before
  deduplication and the visible 25-pair planner budget;
- city distance-policy flags without calling them serving verification;
- country contradiction and unavailable regional-membership evidence;
- fewer-than-cap choices and abstentions;
- semantic acceptability and variation across repeated trials; and
- latency, tokens, cost (if a later versioned price card is supplied), and
  trace reconciliation.

The same model must not judge its own suggestions. Human review assesses useful
coverage and city-serving appropriateness; a result with provider availability
does not retroactively validate an incorrect geographic endpoint.

## Independent corroboration and policy-revision gate

ADR 0023 records the owner's adoption and qualification of M2A for its declared boundary after
monitoring and reviewing the completed work. No independent external qualification is claimed.
Before claiming independent corroboration—or retaining the policy unchanged in the face of material
downstream cost—the evidence gate requires: all offline structural checks; no unresolved trace or
privacy failure; documented human review on the active development corpus; a preregistered
independent holdout; comparison of category defaults against the approved exception caps; and
evidence that extra airports improve useful coverage more than they increase planner work. Any
unsafe catalog contradiction, repeated inappropriate endpoint, systematic important omission, or
budget pressure is a reason to revise, restrict, or replace the policy rather than add unreviewed
hardcoded airports. The selector remains model-proposed and never becomes catalog fact merely by
owner qualification.
