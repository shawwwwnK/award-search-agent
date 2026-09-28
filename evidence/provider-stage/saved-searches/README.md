# Plan-linked saved provider searches

This is the current reusable Provider Stage search corpus. Every saved **result** here comes from
one frozen `CompiledSearchPlan` and one bounded live Provider Stage execution. Each run has its
search-planning input, provider bundle, acquisition tape, typed `ProviderResultSet`, and the exact
captured response bodies needed for offline replay. The [index](index.json) records identities,
counts, paths, and SHA-256 digests. The five [frozen planning inputs](trace-inputs/) remain for
source-plan inspection and offline tests; they are plans, not additional provider results.

| Run | Request and observed evidence | Limits |
| --- | --- | --- |
| [Mixed access](runs/mixed_access/result.json) | SFO→BKK, October 5, 2026, one traveler. 212 award summaries, 23 timed award itineraries, four direct cash observations, and 76 SFO→LAX cash-access observations. The plan's LAX→BKK access award and SFO→LAX dependency activated under the versioned two-detail-call priority policy. | Partial: 154 coverage units, 13 transport calls. Cash flights have unknown returned traveler/cabin and price scope; timed combinations still require Ranking M1 validation. |
| [Exact business](runs/exact_business/result.json) | SFO→BKK, October 5, 2026, two travelers, business class. 41 award summaries, six timed LAX→BKK award itineraries, six direct cash observations, and 66 SFO→LAX cash-access observations. | Partial: 55 coverage units, nine transport calls. Returned seats and cash traveler/price scope remain unknown where providers did not establish them. |

These runs prove that the existing search-planning graph can lead to both award and cash searches:
M2C supplies award queries, original endpoint probes, and positioning dependencies; Provider Stage
derives direct cash queries and activates same-day access cash after timed access-award evidence.
The graph itself remains provider-neutral and award-only. An omitted query is not an empty result.
No candidate journey, price total, booking availability, or recommendation has been validated here.

## Verify and replay

From the repository root, with the local catalog release available:

```sh
.venv/bin/python scripts/provider_plan_corpus.py verify \
  --corpus evidence/provider-stage/saved-searches \
  --catalog data/search_planning/catalogs/m1a-3cb7981519612945
```

The verifier checks source-plan and current-request identity, file hashes, evidence references,
result attachment, and byte-exact offline CLI replay of **each** run. It makes no provider calls.
To inspect or replay an individual run, use its `runs/<case>/bundle.json`, `tape.json`,
`result.json`, and `runtime/` with the `award_agent.cli.provider_results` replay mode. Exit code
1 is expected for these partial results; the output bytes must match the saved result.

Use `scripts/provider_plan_corpus.py add --help` to add another plan-linked run. The tool requires
the frozen planning input and rejects a provider bundle that differs from it. It also rejects a
result whose replay, attachment, evidence, or hashes do not match.

## Scope and provenance

Both live runs were captured on 2026-09-25 from current frozen planning inputs, with the reviewed
Seats.aero and pinned `gfly` adapters. The mixed run uses the original one-traveler mixed-intent
plan; the exact run uses the original two-traveler business plan. Their embedded provider policy
and capability snapshots are immutable replay inputs. The active development configuration lives
at `data/provider_capabilities/provider-stage-current.json` and may evolve independently.

The prior standalone contrast collection was retired at the owner's request because some pairs
were hand-picked outside an executed plan. Indispensable parser regression captures are retained
under `tests/fixtures/providers/`, clearly separate from the active saved-search results.
Historical build logs still describe the earlier campaign and its then-current evidence; those
measurements are not outcomes of these new runs.
