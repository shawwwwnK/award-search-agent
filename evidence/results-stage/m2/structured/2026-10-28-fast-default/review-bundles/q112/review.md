# q112 blind review

- H: fail. Exact answer sentence: “It is earlier-departing than the award journeys but arrives after the recommended award.” Canonical `evidence.components[observation_id=f1fcd665fa6b8830a4b21650190a913c55a55fab792ed144b143d14c6b0b5cf2].legs[0].arrival.local_iso` is `2027-01-10T00:20:00+07:00`; `evidence.journeys[candidate_id=0286e918614a7b41ec9aa8f5d5ec9042bf1bd5234d22fba3e9d968b1511b0bee].arrival.local_iso` is `2027-01-10T04:15:00+07:00`. The cash baseline arrives 3h55 before the recommended award. Its own preceding sentence says 12:20 a.m., so the passage is internally inconsistent.
- U: pass. The exact Turkish business award is defensible for its earlier arrival among the shown awards and shorter elapsed time; the separate SFO–LAX booking and unknown award support/taxes are disclosed.
- M2: pass. The narrative connects the recommendation, alternatives, cash baseline, and consolidated limitations. The H error should be corrected before delivery.
- C: decision-rich. The economy award reports 165,000 fewer Turkish miles in exchange for an economy award label and later arrival/longer travel. The second business award is dominated at the same miles, but the economy comparison remains useful.

Source checks: `evidence.json` selected journey and component timestamps, stops, cabin, points, tax states, seats, and booking obligations; `comparison-registry.json` endpoint/duration differences; `document.json` references. No live calls. No unresolved source ambiguity for the H failure; correction is recommended.
