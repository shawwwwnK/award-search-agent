# q019 blind Results M2 review

**H: fail. U: pass. M2: fail. C: insufficient.** Sparse-source exception: no.

The lead HKG journey is a defensible exact first check for earlier arrival, with a real 70-minute award connection downside. Yet the answer repeatedly reverses the comparisons that should guide the choice. Canonical `evidence.json` gives:

| Displayed option | SFO departure | BKK arrival | Elapsed | Reported seats | Quote |
| --- | --- | --- | ---: | ---: | --- |
| Earlier HKG `cc11925bdbf1b454bd01da92f122569d8f1caab2a21cc915493675159f29111a` | Jan 15 11:45 | Jan 16 22:25 | 1180 min | 9 | 65,000 Aeroplan points + CAD 107.40 |
| TPE `46ff88141207d0e57a27197f6ea281b2f5c2206a27151cbe79bc6f1764c48fd3` | Jan 15 12:00 | Jan 17 01:25 | 1345 min | 1 | 65,000 Aeroplan points + CAD 116.50 |
| Later HKG `28b5a832f590e31794a56935985a19ac2add1203a766c16aa9bb5edbcf8a1a82` | Jan 15 23:15 | Jan 17 10:35 | 1220 min | 2 | 65,000 Aeroplan points + CAD 107.40 |

All listed award quote scopes are unknown; fees above convert `money.award_taxes.raw_amount.value` from minor CAD units. The cash baseline `063df2b37ecbf5a3ef75c229f78f56edf82bbf4b69f36675ee52725a744064dd` is USD 440 with unknown scope, one stop via SIN, and arrives January 17 at **08:25**.

## Hard factual failures

1. “For an earlier Bangkok arrival, investigate the HKG-routing award that arrives first among these shown options; choose the later-arriving HKG alternative only if its shorter elapsed journey and larger reported seat count matter more.” The later HKG is **40 minutes longer** (`journeys[].elapsed_minutes`: 1220 versus 1180) and reports **2 versus 9 seats** (`components[award_observation_id].seats.value`).
2. “The tradeoff is a 70-minute HKG award connection and just 1 reported seat.” The earlier HKG component reports **9 seats**; the 70-minute `connections[0].wait_minutes` is correct.
3. “Consider this Aeroplan economy award via TPE if its earlier departure and 9 reported seats are more useful than the HKG option.” The TPE component reports **1 seat**. It departs **15 minutes after** the immediately preceding HKG journey (12:00 versus 11:45). If “the HKG option” meant the later 23:15 HKG instead, the departure comparison is true, but that HKG still reports two seats, not nine.
4. “This Aeroplan economy award via HKG is the shortest elapsed option shown, 2 hours 5 minutes shorter than the TPE alternative, and reports 2 seats.” The later HKG is 1220 minutes, but earlier HKG is **1180**. The 2-hour-5-minute advantage over TPE (1345) and two-seat count are correct.
5. “The cash search returned USD 440 for a one-stop Singapore Airlines itinerary via SIN, arriving before the shown awards.” The cash component's `legs[0].arrival.local_iso` is January 17 at **08:25**: it arrives **after** earlier HKG (January 16 at 22:25) and TPE (January 17 at 01:25), before only later HKG (January 17 at 10:35). The route, stop count, carrier, and quote are correct.

The other stated intervals are individually correct: earlier HKG takes 40 minutes less than later HKG; TPE arrives three hours after earlier HKG; later HKG takes two hours five minutes less than TPE. The award cabin is stated at journey level, with no unsupported leg-cabin assertion. The final limitations correctly describe unknown quote scope, assembled results, one-traveler request, and single-award rather than separate-ticket connections.

**M2 fails** because the opening action advice and the later comparisons contradict each other. **C is insufficient**: seat counts, elapsed order, and cash arrival are central to the choice, and the answer gets each wrong in at least one place. The lead itself still supports U. Current bookability and all-in prices remain unresolved.

No live calls were made; no escalation is recommended for the review judgment.
