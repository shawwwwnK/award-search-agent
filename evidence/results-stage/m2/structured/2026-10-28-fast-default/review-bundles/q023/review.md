# q023 blind Results M2 review

- **H:** pass
- **U:** pass
- **M2:** pass
- **C:** decision-rich; no sparse-source exception

Both visible award references resolve to admitted Aeroplan economy SFO-HKG-BKK journeys. The earlier-arriving journey `cc11925bdbf1b454bd01da92f122569d8f1caab2a21cc915493675159f29111a` leaves SFO on January 15 at 11:45 −08:00 and reaches BKK on January 16 at 22:25 +07:00. The later-arriving journey `eba1b0800784ea3ca14afa1a89a4c140e5004a8b1e3b83831ef7e155c17f1669` leaves at 23:15 −08:00 and reaches BKK on January 17 at 09:50 +07:00. Both report 9 seats, a 70-minute HKG award connection, 65,000 Aeroplan points, and CAD 107.40 observed taxes with unknown scope. Neither reports individual leg cabins.

The rendered T08 comparison card has the correct SFO-BKK endpoints and local timestamps. The canonical UTC arrivals differ by **685 minutes (11 hours 25 minutes)**, with the first journey earlier. Their elapsed times are **1180 and 1175 minutes**, so the later-arriving journey is 5 minutes shorter.

The separate cash observation `ccc7379a32c4f818d72f0236429fc74bcd63fc2dd4af1ee5cd150f8db6b1bc4e` is a United/ANA SFO-LAX-NRT-BKK itinerary with two stops, **1379 minutes (22h 59m)** duration, and an observed **USD 456** quote of unknown scope. One returned traveler does not establish a per-person fare. The answer uses it only as context.

The lead recommendation is exact and supported for the stated arrival preference among the shown choices. The alternative explains the later departure and near-equal duration, while the ending consolidates quote, cabin, booking, coverage, and freshness limits.

**Source-selection limitation:** `document.json` lists only the earlier journey in `selection.journey_ids`, although its reference blocks and the visible answer include the later journey. The later journey exists in the canonical evidence and is admitted. I found no resulting visible factual error; the selection/reference mismatch may merit a separate document-contract check.
