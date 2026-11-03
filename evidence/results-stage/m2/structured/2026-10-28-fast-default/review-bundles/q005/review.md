# q005 blind source and composition review

| Dimension | Judgment | Reason |
| --- | --- | --- |
| H: material facts | Fail | The unqualified TPE arrival comparison is misleading. |
| U: useful next action | Pass | Investigate the identified earlier-arriving HKG award first; the answer gives a reason, downside, alternative, and verification step. |
| M2 composition | Pass | Individual explanations surround journey references, with a relevant alternative, separate cash context, and consolidated limitations. |
| C: comparative depth | Decision-rich | The late-departure alternative states its 11h30 departure gain and 11h25 arrival cost at equal reported points, fees, and seats. |

## H finding

Exact answer sentence: “This economy award via HKG is reported with 9 seats and arrives 3 hours before the TPE option, with the same reported 65,000 Aeroplan points and CAD fee amount.”

Canonical counterexample: `evidence.json` journey `cc11925bdbf1b454bd01da92f122569d8f1caab2a21cc915493675159f29111a` has `arrival.local_iso = 2027-01-16T22:25:00+07:00`; the earliest admitted TPE journey, `c559213003ec943dd700f59c7813a457b52988433ba469978634ffb2a6a72954`, has `arrival.local_iso = 2027-01-16T23:40:00+07:00`. The gap is **75 minutes**, not 3 hours. The answer identifies no TPE journey, so “the TPE option” cannot be mapped unambiguously.

Residual uncertainty: two other admitted TPE journeys arrive at `2027-01-17T01:25:00+07:00`, which *is* three hours after the selected HKG journey. The claim could have intended either of those, but neither is referenced. This is an ambiguous and materially misleading comparison, not evidence that every TPE comparison is false.

## Other checks

- The selected HKG award and later HKG alternative each show 9 observed seats, 65,000 Aeroplan points, 10,740 CAD minor units of fees with unknown price scope, and journey-level economy cabin. Their leg cabins are absent. Their local departures differ by 11h30 and their local arrivals by 11h25.
- The cash reference is a separate SFO–LAX–NRT–BKK United/ANA itinerary with two stops and a $456 USD quote of unknown scope. Its returned traveler count is one; that does not establish quote scope.
- The request specifies one traveler; provider status is partial. The named awards are single-award journeys, so the answer does not invent an unprotected transfer.

Checks: read `AGENTS.md`, the campaign reviewer instructions, and only q005's `answer.md`, `document.json`, `evidence.json`, and `references.json`; used Python read-only projections of q005 canonical journeys/components and offset-aware arrival arithmetic. No live calls or product changes. Escalation is not needed for this review; the answer's TPE comparator needs clarification or correction before an H pass.
