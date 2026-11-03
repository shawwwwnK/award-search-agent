# Delivered answer source review

Rubric: `fast-default-M2-v1.2-calibrated`. Scope: the delivered controlled-recovery diagnostic answer only; excluded from the natural confirmation denominator.

| Dimension | Judgment |
| --- | --- |
| H — hard factual | Pass |
| U — useful next action | Pass |
| M2 composition | Pass |
| C — comparative depth | Decision-rich |

## Source checks

- `J18` (`010ec2ca…`), `J115` (`018b54da…`), and `J63` (`0286e918…`) are the three displayed conditional SFO–BKK journeys. The local departure and arrival times, elapsed durations (1,803, 1,990, and 1,719 minutes), LAX waits (301, 149, and 150 minutes), and IST award connections (60, 420, and 140 minutes) match `evidence.json > journeys`. The offset-aware differences are 187 minutes for the same-arrival comparison and 275 minutes earlier arrival / 271 minutes shorter elapsed time for the earlier business option. The rendered comparison facts agree with these endpoints.
- `evidence.json > components` confirms Turkish economy at 110,000 quoted points for `J18`, Turkish business at 275,000 for `J115` and `J63`, one IST stop in each award component, and American / Alaska / American SFO–LAX cash components quoted at USD 109 / 59 / 59. All cash quote scopes and award point scopes are unknown. The text compares reported quotes without claiming an all-in price or per-traveler amount.
- All three award components have an unknown reported seat count and award taxes; `source.view.request.travelers` is one, while the shared reason set marks traveler support and the minimum-award-seat obligation unknown. The selected joins are separate bookings, with positioning permission and ticket protection unverified. The answer states these limits and does not claim a cabin for each leg.
- The `C3` cash component (`5436f689…`) is an EVA Air SFO–BKK baseline with one stop, the stated local times, and a USD 605 source quote with unknown scope. It is presented as a separate cash benchmark. `source.view.provider_status` is `partial`, consistent with the closing coverage caveat.

## Judgment and limits

The answer gives an exact economy lead, its lower quoted points and later departure versus the same-arrival business option, and its economy cabin, longer LAX wait, higher positioning quote, and separate-ticket risks. The earlier-arrival business alternative adds a supported time-versus-points/cabin choice. References sit inside the explanation; cash context and limitations are consolidated. The same-arrival business journey offers little meaningful gain over the other business journey, but it remains a useful reference for the economy-versus-business comparison. No sparse-source exception applies.

No hard factual failure was identified. This source and composition review does not assess model performance, natural failure frequency, or reliability of correction. No escalation is recommended for this bounded review; a broader product judgment about whether to omit the weaker business comparison is outside this rubric.

Verification: inspected only the assigned `answer.md`, `document.json`, `evidence.json`, `references.json`, `comparison-registry.json`, and `scope.json`; checked selected records and arithmetic with read-only Python commands. No live calls or runtime edits.
