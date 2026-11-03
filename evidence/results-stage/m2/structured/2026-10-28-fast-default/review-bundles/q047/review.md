# Blind review: q047

Rubric: `fast-default-M2-v1.2-calibrated`

| Dimension | Judgment |
| --- | --- |
| H | Pass, with the quote-scope wording caveat below |
| U | Pass |
| M2 | Pass |
| C | Decision-rich |
| Sparse-source exception | No |

The displayed recommendation is a supported local tradeoff. `references.json` maps J12 to the Vancouver journey `b8d4f8e3…` and J13 to the Taipei journey `3f06b08a…`; both are in comparison pool P1. `comparison-registry.json` T02 gives J12 a 620-minute earlier arrival, and T03 gives it a 90-minute shorter elapsed time. In `evidence.json`, `journeys[candidate_id=b8d4f8e3…].award_points.value` is 92,144 and `journeys[candidate_id=3f06b08a…].award_points.value` is 65,000, both Aeroplan. The answer explicitly limits “earlier” to the other award shown, so it does not claim global earliest arrival. The alternative's lower quoted points are a meaningful offset to its later arrival and longer elapsed time; no strongest-representative or option quota is needed for this comparison.

I checked both journey records and their award observations for endpoints, offset-aware dates and times, award cabin versus absent leg cabins, carriers, one-stop routes, connection waits (375 and 495 minutes), observed seats (9 and 1), points, and CAD tax quotes. The selected cash observation `063df2b3…` supports the separate USD 440 reference, SFO–SIN–BKK route, one stop, Singapore Airlines, Jan 15 9:40 a.m. departure, Jan 17 8:25 a.m. arrival, and 1,905-minute duration, longer than both awards. Its `money.scope` is `unknown`, as the answer says. `source.view.provider_status` is `partial`, and `availability_guidance` says some results are not real-time. I found no contradicted hard fact in the rendered prose or display references.

The opening gives a choice, reason, and downside; the reference passages explain each option, provide an alternative and cash context, and end with consolidated limitations. The inserted comparison blocks repeat long journey labels and read mechanically, but they are correct and do not break the overall recommendation.

**Uncertainty for adjudication:** “It requires 92,144 Aeroplan points” is stronger wording than “quotes” or “shows.” The canonical `journeys[candidate_id=b8d4f8e3…].money.points_scope` is `unknown`, as is J13's. I read the sentence as the displayed raw points quote for a request with one traveler, not as a verified all-in or per-traveler price; the answer separately disclaims tax and cash quote scope and urges price confirmation. A stricter reading of “requires” as a guaranteed payable total would make this an H scope concern. No such total or cross-program value claim is explicit here.

Verification: read only this bundle and the assigned rubric; inspected compact canonical records and reference mappings; independently computed the 620-minute arrival difference and checked 1,490/1,580/1,905-minute durations. No live calls. No escalation recommended; the wording caveat can be adjudicated within the fixed rubric.
