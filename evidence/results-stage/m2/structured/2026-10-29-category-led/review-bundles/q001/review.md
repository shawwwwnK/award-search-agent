# q001 independent blind review

**Overall: fail.**

| Axis | Grade | Reason |
| --- | --- | --- |
| H | fail | The opening and first card label attribute the Aeroplan/UA/CX economy itinerary to Singapore Airlines. |
| U | pass | The earlier-arrival economy versus conditional business/separate-ticket choice is intelligible, despite the independently failing airline identity. |
| M2 | fail | Opening and per-card paragraphs repeat the same reasons; incomplete pricing and availability caveats recur instead of being consolidated. |
| C | pass | Earlier arrival versus business cabin and separate-ticket risk is a supported, meaningful distinction. |
| K | pass | Full source has 11 time members, 116 premium members and no cost members; the answer preserves time and premium and correctly declines a lowest-total claim. There is no time/premium overlap to explain here. |
| P | fail | Real cards are present and full-cash context is one exact sentence, but the premium card omits the known SFO–LAX component schedule and its airline; its flight list begins at LAX despite whole-journey SFO departure. |

## Findings

- **q001-H1 (material):** Singapore Airlines economy award. Neither the source program nor reported carriers support Singapore Airlines. The correct factual card body does not repair the false caption and opening. Source identities: `1a1d383744d4dc2716b363cbef5d2be0ddd32f2d1bd0180184af265065086f5c`, `28b5a832f590e31794a56935985a19ac2add1203a766c16aa9bb5edbcf8a1a82`.
- **q001-P1 (material):** Premium card Flights list contains only LAX–IST and IST–BKK. Unreported individual legs must not become invented flights, but the known component-level SFO–LAX route and timing should still appear as component facts. The card suppresses that distinction rather than displaying it. Source identities: `f21d646e6c2945ae684dca8be205471aab6e5e145d2be25ca50bc20b3db99e42`.
- **q001-M1 (material):** Repeated incomplete-price/availability limitations and duplicated introductory and per-card reasons. Shared limitations and reasons recur across several paragraphs; the answer does not meet the accepted consolidated-limits composition.
- **q001-audit (note):** omitted_reasons lists time and premium despite selecting both. These are explanations of represented categories, not valid omission reasons. I did not trust this audit text as evidence; actual selected source memberships support K pass.

Exact field citations and full-source scope are retained in `review.json`. No run summaries, timing, prompt/profile mapping or previous grades were consulted. No live calls; no escalation recommended.
