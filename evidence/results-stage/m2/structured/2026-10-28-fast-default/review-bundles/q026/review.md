# q026 blind Results review

Rubric: `fast-default-M2-v1.1-scope`. **H fail; U pass; M2 pass; C decision-rich.** Sparse-source exception: no.

## Material finding

> “It arrives before the awards, but is not a like-for-like valuation or an all-in award comparison; confirm what the quote covers.”

The selected cash baseline, observation `063df2b37ecbf5a3ef75c229f78f56edf82bbf4b69f36675ee52725a744064dd`, arrives at `2027-01-17T08:25:00+07:00` (`evidence.json` `source.view.components[].arrival.local_iso`). The displayed Hong Kong alternative `cc11925…` arrives at `2027-01-16T22:25:00+07:00`, and the Taipei alternative `46ff881…` at `2027-01-17T01:25:00+07:00` (`evidence.json` `journeys[].arrival.local_iso`). The cash flight arrives **10 hours and 7 hours after** those awards, respectively. It arrives before only the late Hong Kong award `eba1b080…` at `2027-01-17T09:50:00+07:00`. The plural claim reverses the ordering for two displayed choices.

## Other checks and judgments

- The three document-selected journey IDs match their embedded references. All are admitted direct awards. The corresponding award observations report Aeroplan economy, 65,000 points with unknown point scope, 9/9/1 observed seats, and CAD 107.40/CAD 107.40/CAD 116.50 fees with unknown quote scope. The source amounts are minor CAD units. None of those claims treats observed seats as guaranteed availability.
- The Hong Kong connection is 70 minutes on both options; Taipei is 270 minutes. Offset-aware arrival and elapsed comparisons in the answer agree with `evidence.json` and the cited comparison-registry facts: earlier Hong Kong arrives 11h25 earlier while taking 5 minutes longer; Taipei arrives 8h25 earlier than the late lead while taking 2h50 longer.
- The cash observation reports USD 440, one stop via SIN, Singapore Airlines, and unknown quote scope. It is correctly framed as a separate baseline apart from the arrival error.
- U passes because the late departure lead is exact and defensible, with a short-connection and later-arrival downside. M2 passes independently because the narrative weaves the references, alternatives, cash context, and consolidated caveats. C is decision-rich because timing, route, seats, fees, and connection tradeoffs are explained.
- Uncertainty: the introduction’s “earlier arrival still” for Taipei is ambiguous if read against the immediately preceding earlier Hong Kong option. The detailed Taipei paragraph explicitly compares against the late lead, so I did not count an additional H failure. The source does not establish current bookability or total/per-traveler award pricing.

Inspection was limited to the assigned bundle and reviewer instructions. I used compact Python JSON field inspection and checked `answer.md` against `document.json`, `evidence.json`, `references.json`, and `comparison-registry.json`. Escalation is not needed to identify the factual error; the wording ambiguity may be adjudicated with the parent review.
