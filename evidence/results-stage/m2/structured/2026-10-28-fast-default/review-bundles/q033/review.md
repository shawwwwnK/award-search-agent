# q033 blind source and composition review

| Dimension | Judgment |
| --- | --- |
| H factual | Pass |
| U useful action | Pass |
| M2 composition | Pass |
| C comparative depth | Basic; no sparse source exception |

## Source check

- The recommended journey `0286e918...` in `evidence.json` has SFO departure `2027-01-08T08:36:00-08:00`, BKK arrival `2027-01-10T04:15:00+07:00`, 1,719 elapsed minutes, a 150-minute separate booking connection at LAX and a 140-minute award connection at IST (`journeys[].departure`, `.arrival`, `.elapsed_minutes`, `.connections`). Its cash access observation `c68429d4...` lists American, SFO–LAX, USD 59 with unknown quote scope (`components[].carriers`, `.money`). Its award observation `14b3bb85...` lists Turkish, business at itinerary level, 275,000 points, unknown seats and taxes, and absent per-leg cabins (`components[].program`, `.cabin`, `.points`, `.seats`, `.taxes_fees`, `.legs[].cabin`). The journey's `booking_obligation` is `separate_tickets_unverified`; its `internal.reason_details` leaves baggage, check-in, terminal, transit, and missed-connection protection unverified.
- The displayed alternative `018b54da...` departs SFO at 08:40 and arrives BKK at 08:50 on the stated dates. Its LAX and IST waits are 149 and 420 minutes. The Alaska access observation `bd251472...` lists USD 59 with unknown scope; its Turkish award observation `d34f0323...` lists business, 275,000 points, unknown seats/taxes, and absent per-leg cabins (`evidence.json` corresponding `journeys[]` and `components[]`). `comparison-registry.json` T01–T03 supports the four-minute later departure, 275-minute later arrival, and 271-minute longer elapsed time. The answer's comparison lines reproduce T02 and T03.
- The separate cash benchmark `f1fcd665...` is SFO–SEA–ICN–BKK, two stops, 1,635 minutes, departure 06:05 SFO, arrival 00:20 BKK, USD 452 with unknown price scope (`evidence.json components[]`). Its `returned_travelers.value` is one, matching `source.view.request.travelers`, but that query echo does not establish the fare's traveler or party price scope. `source.view.provider_status` is `partial`; `availability_guidance` warns that some results are not real time.

No material answer sentence contradicted these source fields. The recommendation is appropriately conditional on the unverified separate-ticket transfer, and the answer does not turn the listed business itinerary cabin into a claim about each leg. “Earlier-arriving” reads against the displayed alternative; the closing paragraph explicitly says the two cards are selected results, not the full eligible inventory.

## Comparative depth

The later card offers almost the same departure, the same listed business cabin and 275,000 Turkish points, and the same USD 59 access quote, but arrives 4 hours 35 minutes later after a longer Istanbul wait. It confirms the recommended card's timing advantage without showing a material gain of its own. The pool is not sparse: `references.json comparison_pools.P1` includes journey `178a2400...`, an economy-listed 110,000-point Turkish option departing at 08:51, arriving at 04:15, with a USD 59 access quote (`evidence.json journeys[]` corresponding `award_cabin`, `award_points`, `departure`, `arrival`, `money.cash_fare`). That could support a cabin/points tradeoff, subject to the unknown quote scopes and per-leg cabins. Its absence limits C to **basic**; it does not falsify the answer's local timing comparison or require a full inventory frontier.

## Uncertainty and verification

Observed quote amounts are not established party totals; award availability and seat count, taxes, per-leg cabin, protection, and positioning permission remain unresolved. No live calls were made. Inspection used Python JSON reads of the assigned `answer.md`, `document.json`, `evidence.json`, `references.json`, and `comparison-registry.json` plus the parent `reviewer-instructions.md`; selected journey/component records and pool summaries were checked. No escalation is recommended for this bounded source review; the parent can adjudicate the C depth threshold.
