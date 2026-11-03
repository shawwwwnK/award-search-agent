# q099 blind answer review

Rubric: `fast-default-M2-v1.2-calibrated`

| H | U | M2 | C | Sparse-source exception |
| --- | --- | --- | --- | --- |
| Fail | Pass | Fail | Basic | No |

The source has no complete award journeys and partial provider coverage. A first lead to verify is a useful next action; the cash itinerary is correctly separate from the award leads. Dates, program point amounts, cash stop count, duration, and local clock times align with the selected canonical records.

## Findings

1. **H — traveler support:** “If you’re looking on January 1, check the United lead first: it reports 9 seats for one traveler, versus 2 on the Aeroplan lead, and a lower USD award-tax quote.” In `evidence.json`, United component `cc7d8d9e…` has `seats.value=9`, `returned_travelers.state=absent`, and `requested_travelers=1`. The seat observation does not establish support for the requested party; “for one traveler” implies that linkage.
2. **H — cabin by carrier:** “The result reports economy on CA, UA, and ZH, 60,500 United miles, 9 seats, and USD 28.20 in award taxes.” The same component has `cabin.value=economy` and `carriers=[CA, UA, ZH]`, but its only `legs[0]` is `reported=false` with absent carrier. The source does not establish economy cabin on each carrier.
3. **M2 — consolidated limits:** The cash-context passage closes with partial coverage, but quote scope and itinerary gaps are repeated across individual paragraphs. There is no consolidated statement covering schedule, party support, cabin by leg, quote scope, and partial coverage together. Canonical fields are `source.view.provider_status=partial`, the selected leads’ `missing_information=[itinerary_schedule_incomplete]`, and selected quotes’ `money.scope=unknown`.
4. **C — limited alternative gain:** The Aeroplan paragraph says it “offers a different reported carrier and program” but does not explain what the traveler gains against United’s higher reported seats and lower converted tax quote. The Alaska paragraph offers a useful premium-cabin/date/tax distinction. Overall depth remains basic. Relevant canonical fields are the Aeroplan and United components’ `carriers`, `program`, `seats`, `money.quoted_usd`, `cabin`, and `departure_date`.

The United/Aeroplan “lower USD award-tax quote” is directionally true under the frozen FX snapshot: Aeroplan’s CAD 116.50 is about USD 82.11 versus United’s USD 28.20. The answer does not state that conversion, so this is a clarity concern rather than another factual failure. No global optimum or fixed option count was assumed.
