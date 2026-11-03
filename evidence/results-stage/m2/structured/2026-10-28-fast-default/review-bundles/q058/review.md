# q058 blind Results M2 review

Rubric: `fast-default-M2-v1.2-calibrated`. Verdict: **H pass; U pass; M2 pass; C decision-rich**. Sparse-source exception: **false**.

## Source checks

| Answer claim | Canonical source and field | Check |
| --- | --- | --- |
| No complete award itinerary; three selected leads are date-only with no schedule | `document.json.selection.journey_ids = []`; `evidence.json.journeys = []`; `evidence.json.leads[reference_id = A12/A8/A5 observation IDs].missing_information = ["itinerary_schedule_incomplete"]`; the corresponding `components[].legs[0]` have null arrival/departure instants and `reported = false` | Supported. This does not assert that the whole market lacks bookable awards. |
| Request and award dates | `evidence.json.source.view.request`: one traveler, SFO to BKK, outbound window 2027-01-01 through 2027-01-31; selected `components[].departure_date` are January 4, 3, and 2, respectively | Supported. The answer calls 8/9 **reported seats**, not requested travelers or guaranteed seats. |
| Alaska lead A12 | `references.json.awards.A12 = 298e9fc3fa28627cc1ab28d956ab4682deece903365a89805c922c0c9eb502af`; matching `evidence.json.components[]`: `program.value = alaska`, `cabin.value = economy`, `points.value = 42500`, `seats.value = 8`, `money.quoted_usd = 50.9`, `money.raw_amount.value = 5090`, `money.unit = minor`, `money.scope = unknown` | Supported. Among the three **selected** leads, its mileage is lowest and its reported USD tax quote highest. |
| United lead A8 | `references.json.awards.A8 = a7af2ffba298ae7fd372cdc19bbb1276d9a59968de8683e2666d0259af2e0a1b`; matching component: January 3, `program.value = united`, `cabin.value = economy`, `points.value = 60500`, `seats.value = 9`, `money.quoted_usd = 19`, `money.raw_amount.value = 1900`, `money.unit = minor`, `money.scope = unknown` | Supported. Its quoted fees are lowest of the selected trio. |
| United lead A5 and same-program comparison | `references.json.awards.A5 = f3fbd99e899fb14814669bb76116f1982f7423dd264f4a41a8d1a3479027014e`; matching component: January 2, `program.value = united`, `cabin.value = economy`, `points.value = 55000`, `seats.value = 9`, `money.quoted_usd = 24.5`, `money.raw_amount.value = 2450`, `money.unit = minor`, `money.scope = unknown` | Supported: 60,500 - 55,000 = 5,500 miles and 24.50 - 19.00 = USD 5.50 in **reported quotes**. Unknown price scope prevents an all-in or per-person cost conclusion, which the answer explicitly withholds. |
| Separate cash baseline C1 | `references.json.cash.C1 = 456ce00d08b184d171728f7e51cce2dd7feff2cc201cc031c778ec907b04b630`; matching component: `kind = cash_itinerary`, `airport_sequence = [SFO,HKG,BKK]`, `stops.value = 1`, `carriers = [Cathay Pacific]`, `legs[0].departure.local_iso = 2027-01-01T22:55:00-08:00`, `legs[0].arrival.local_iso = 2027-01-04T10:35:00+07:00`, `duration_minutes.value = 2680`, `money.quoted_usd = 640`, `money.scope = unknown` | Supported. Offset-aware subtraction of the two UTC instants gives 2,680 minutes = 44 hours 40 minutes. It is identified as cash context, not an award recommendation or cheapest fare. |
| Partial search and availability limits | `evidence.json.source.view.provider_status = partial`; `coverage_groups`: SFO-BKK detail query `status = omitted`, `reason = resource_budget_exhausted`; TPE connection logical query `status = partial`, `reason = pagination_budget_exhausted`; `availability_guidance` calls for booking-site confirmation | Supported. The answer does not infer the full inventory from the selected leads. |

## Judgment

H passes: no material source contradiction found in the selected identities, roles, cabin, dates, prices, unit conversion, quote scopes, seats, cash stop and time facts, or comparison directions. No award transfer or protection claim is made; award schedules and connections are explicitly unknown.

U passes: the answer truthfully says no complete award journey is available in these results and tells the traveler to check schedules, routing, availability, and exact quotes with the programs.

M2 passes: the narrative explains the incomplete-result decision, embeds each lead's reference beside an individual explanation, uses the same-program comparison, supplies separate cash context, and closes with consolidated limitations.

C is decision-rich for the available date-only evidence: Alaska offers the fewest reported miles but the highest reported fee and a different program; January 3 United trades more miles for lower reported fees than January 2 United. Each displayed lead has an authored gain and loss, and the answer refuses to pick a better trip without schedule or quote-scope detail. This is local comparative depth, not full-inventory coverage.

Uncertainty: Award quote scope and missing schedules prevent a firm total-cost or itinerary-quality ranking. The bundle has many other leads, but the answer's comparative superlatives are expressly limited to the three selected leads. No adjudication or architectural escalation is recommended.
