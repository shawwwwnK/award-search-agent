# Ranking M2 saved solution-style results

These are offline local-development projections of the three unchanged
[M1 matching outputs](../m1/README.md), using the owner-approved
[M2 style policy](../../../docs/handoffs/2026-10-01-ranking-m2-styles-contract.md) and the
[dated USD/CAD snapshot](../../../data/ranking/m2/README.md). No travel-provider or model call
was made to generate them. Ranking Stage was owner-closed on 2026-10-02 for its declared M1
matching/validation and M2 solution-style boundaries; see the
[stage closeout](../../../docs/handoffs/2026-10-02-ranking-stage-closeout.md). This does not claim
observed-cost coverage or broader provider, bookability, or full-workflow qualification.

The [index](styled/index.json) binds every input/output SHA-256, policy and FX digests, comparison
pool, reference/threshold, style counts, cost-evidence states, and highlight IDs. Each result embeds
its complete `MatchedJourneySet`, including the request, plan, provider result, validation reasons,
source evidence, baseline cash observations, and coverage. All 992 original journeys remain:
427 admitted/conditional candidates are style-eligible; 565 rejected/research records are retained
outside style assignment. Admitted and conditional candidates share the same style rules and minima.

| Saved request | Retained | Eligible | Time-focused | Cost-focused | Premium-focused | Two-or-more-style highlights |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [Mixed access](styled/mixed_access.json) | 473 | 257 | 5 | 0 | 120 | 0 |
| [Exact business](styled/exact_business.json) | 396 | 106 | 34 | 0 | 106 | 34 |
| [Positioning permitted](styled/sfo_to_bkk_positioning.json) | 123 | 64 | 22 | 0 | 0 | 0 |

All three results retain partial provider coverage. These different requests are not pooled
against each other. Premium-economy add-ons and possible cost/highlight indexes are empty on
this corpus; their behavior is exercised by synthetic tests, not claimed as live evidence.
Counts are candidate records, including retained source/query duplicates, not counts of unique
flight schedules. No new deduplication or variant-pruning policy was introduced.

## Interpretation of the saved assignments

These are parent-agent engineering interpretations for owner review, not owner conclusions or
product-usefulness qualification.

- **Mixed access:** the 19h05 reference gives a 22h54 time threshold. Five admitted Aeroplan
  award-only itineraries via TPE qualify; the cash-access journeys do not. The 120 Turkish
  business variants qualify for premium style while preserving their conditional requirements.
  This separates time and cabin tradeoffs without declaring an overall winner.
- **Exact business:** the reference is 27h27 and the threshold is 32h56m24s. All 106 eligible
  variants qualify for premium style; the 34 shorter variants also qualify for time and highlights.
  Premium is intentionally categorical rather than selective when the request already requires
  business. Every eligible result is conditional; highlights do not turn them into admitted trips.
- **Positioning permitted:** the same 27h27 reference is set by a conditional cash-access
  journey. All five admitted SIN-egress variants and 17 conditional access variants fall within
  32h56m24s. The longest admitted egress variant takes 32h25, including an 8h55 SIN transfer.
  Its inclusion follows the approved 120% rule, not a claim that an eight-hour wait is ideal.
  Actual transfer times remain available to the later presentation layer.

### Why cost membership is undetermined, not zero-cost

Every eligible award observation has unknown per-traveler/party price scope. No saved request
therefore supplies a sufficiently complete per-traveler heuristic-cost reference. All 427 eligible
cost assessments are `undetermined`; no cost threshold, definite cost winner, or possible-cost
membership is manufactured. Source points, fees, and cash quotes remain in each attachment and
component breakdown, alongside their scope limitations. The approved USD 150 missing-tax estimate
does not resolve unknown scope for points or cash fares.

This is an observed provider-evidence limitation, not proof that costs are equal or that the
cost algorithm is unfinished. Synthetic end-to-end tests supply supported price scopes to verify
the complete/partial cost rules, estimates, exact 200% boundary, and provisional highlights.
Claiming useful observed-cost style assignment still needs adequately scoped provider evidence
or a separately approved, explicitly recorded price-scope assumption. No such assumption was
silently adopted and no provider normalization was changed in this session.

## Reproduce and verify

Generate into a new directory; the command never overwrites existing evidence:

```sh
PYTHONPATH=src .venv/bin/python scripts/ranking_style_corpus.py \
  --fx-snapshot data/ranking/m2/fx-2026-09-29.json \
  --output-dir /private/tmp/ranking-m2-new-corpus
```

Verify the saved outputs, hashes, independent raw-component timing oracle, and byte-identical replay:

```sh
PYTHONPATH=src .venv/bin/python scripts/ranking_style_corpus.py \
  --fx-snapshot data/ranking/m2/fx-2026-09-29.json \
  --output-dir evidence/ranking-stage/m2/styled --verify
```

For one source, use `PYTHONPATH=src .venv/bin/python -m award_agent.cli.ranking_styles --help`.
Exact rational cost receipts and UTC microseconds determine membership; Decimal values are
reproducible display projections. The later Output Stage may choose how many variants to explain,
but cannot change membership, splice offers, suppress unknowns, or rank pure-cash baselines as solutions.
