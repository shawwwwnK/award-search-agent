# q021 blind Results M2 review

- **H:** pass
- **U:** pass
- **M2:** pass
- **C:** decision-rich; no sparse-source exception

The answer's three embedded journey references resolve to Turkish cash-access-plus-award journeys in `evidence.json`. Their reported journey-level business or economy cabins, points quotes, LAX separate-booking waits (150, 149, and 644 minutes), Istanbul award connections, arrival times, and unknown award seat and traveler support are supported. The rendered arrival card is also correct: the selected business lead arrives in Bangkok at **2027-01-10 04:15 +07:00**, 4 hours 35 minutes before the other shown business journey's **08:50 +07:00**. The quoted USD 59 SFO-LAX access legs have unknown price scope, and award taxes are unavailable.

The separate SFO-BKK cash benchmark observation `f1fcd665fa6b8830a4b21650190a913c55a55fab792ed144b143d14c6b0b5cf2` quotes USD 452, reports two stops, and arrives at **2027-01-10 00:20 +07:00**. Its scope is unknown despite one returned traveler. The answer correctly treats it as context.

The lead is a useful investigation target with a reason and downside. The answer is connected prose and gives real choices: earlier business arrival with a short LAX wait, later business arrival if that time suits the traveler, or economy at a lower point quote with a long separate-ticket wait. It consolidates booking, seat, traveler, tax, scope, coverage, and freshness limits.

**Source limitation:** All three journeys are conditional, including unresolved positioning permission in `internal.reason_codes`. The answer flags their separate cash bookings and unconfirmed protection but does not explicitly name the permission state. Because it asks the traveler to investigate rather than treating the journeys as booked or fully cleared, I did not count this omission as an H failure. The lead's earlier-arrival claim is expressly limited to the shown options.
