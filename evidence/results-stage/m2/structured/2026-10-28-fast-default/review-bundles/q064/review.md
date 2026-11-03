# q064 blind review

**Rubric:** fast-default-M2-v1.2-calibrated  
**H:** fail  
**U:** pass  
**M2:** fail  
**C:** decision-rich  
**Sparse-source exception:** false

The selected 1:50 p.m. departure is a defensible conditional choice: it arrives at 8:50 a.m. with 1,680 elapsed minutes, compared with 1,990 for the displayed 8:40 a.m. options. The 8:36 a.m. option arrives 4 hours 35 minutes earlier but takes 39 minutes longer than the recommendation. Separate bookings, unknown award taxes and seat count, and unknown quote scope are disclosed. These comparisons provide decision-rich local tradeoffs. The USD 605 cash reference is correctly presented as separate, one-stop, and of unknown scope.

## Hard factual findings

1. “The two results otherwise share the displayed schedule and award details; their positioning flights differ: Alaska on one, United on the other.” In `evidence.json`, journeys `018b54da…` and `3c65e686…` point to cash components `bd251472…` and `fcfe48f1…`. Both components' `carriers` field is `["Alaska"]`. Distinct observation IDs do not establish different carriers.
2. “The separately booked SFO–LAX positioning flight is on United, followed by a 2-hour-29-minute wait at LAX; the award itinerary connects at Istanbul for 7 hours.” For displayed journey `018b54da…`, component `bd251472…` reports `["Alaska"]` in `carriers`. The 149-minute LAX wait and 420-minute Istanbul connection are supported.
3. “The displayed advantage over the United-positioning result is the carrier choice for the positioning flight, not a timing difference.” The same two cash components both report Alaska; the two journeys do have the same departure, arrival, and 1,990-minute elapsed time. The claimed carrier advantage is unsupported.

**Composition finding:** The raw “Arrival:” and “Journey duration:” comparisons use the 8:40 a.m. journey and 8:36 a.m. alternative, then appear between comparisons centered on the selected 1:50 p.m. journey. Their numbers are correct for their exact endpoints, but the unexplained switch and fictitious carrier distinction break the recommendation's flow. The benchmark label “Direct SFO–Bangkok cash baseline” is ambiguous next to prose that correctly says one stop; I treat it as a clarity issue, not an independent H failure. No exhaustive-inventory claim or coverage quota was applied.
