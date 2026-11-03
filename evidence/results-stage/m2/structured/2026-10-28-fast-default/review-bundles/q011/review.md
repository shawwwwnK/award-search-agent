# q011 blind Results M2 review

**H: fail. U: pass. M2: pass. C: basic.** Sparse-source exception: no.

The lead is defensible for a one-traveler SFO–BKK request on January 15: among the admitted complete journeys, it arrives earliest (January 16 at 22:25 Bangkok time), with nine observed award seats. The answer gives its earlier SFO departure as a downside, includes references in the traveler narrative, keeps the USD 456 two-stop cash quote as a separate baseline, and consolidates price-scope and availability limits. Its Aeroplan economy claim is at journey level; the individual leg cabins are unreported and are not asserted by the answer.

## Hard factual failures

1. “For an Aeroplan award, the Hong Kong routing departing earlier is the strongest schedule fit among these shown choices: it has the shortest elapsed time and gets you to Bangkok the evening of January 16.” `evidence.json` → `journeys[candidate_id=cc11925bdbf1b454bd01da92f122569d8f1caab2a21cc915493675159f29111a].elapsed_minutes` is **1180**; `journeys[candidate_id=eba1b0800784ea3ca14afa1a89a4c140e5004a8b1e3b83831ef7e155c17f1669].elapsed_minutes` is **1175**. The lead has the earlier arrival, but is five minutes longer.
2. “Its elapsed time is 5 minutes shorter than the later-departing Hong Kong alternative, and it arrives 11 hours 25 minutes before that option.” The same `elapsed_minutes` fields reverse the stated duration direction. The `arrival.instant` fields, **2027-01-16T15:25:00Z** and **2027-01-17T02:50:00Z**, support the 11-hour-25-minute arrival advantage.
3. “Consider it if the later departure matters more than arriving earlier; it takes 5 minutes longer.” The later HKG journey's `elapsed_minutes` is **1175**, versus **1180** for the lead; it takes five minutes less.

## Comparative depth and uncertainty

The shown TPE journey is a weak third choice. Its `arrival.local_iso` is January 17 at 01:25, `elapsed_minutes` is 1345, and its award observation has one reported seat. Another eligible TPE journey, `c559213003ec943dd700f59c7813a457b52988433ba469978634ffb2a6a72954`, also departs SFO at noon but arrives January 16 at 23:40, takes 1240 minutes, and reports two seats; both return 65,000 Aeroplan points and 11,650 CAD minor units in fees. This does not impose a frontier quota, but limits the stated option's decision value. Unknown quote scope prevents an all-in or cross-program value conclusion. Reported seats and the cash baseline are observations, not current booking guarantees.

No live calls were made. Review was limited to this bundle's answer, document, evidence, and references. No escalation is needed for the review judgment.
