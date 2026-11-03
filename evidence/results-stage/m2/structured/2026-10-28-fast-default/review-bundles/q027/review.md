# q027 blind Results review

Rubric: `fast-default-M2-v1.1-scope`. **H pass; U pass; M2 pass; C decision-rich.** Sparse-source exception: no. No material source contradiction found.

## Checks and judgments

- `evidence.json` records the selected `0286e918…` as a **conditional** SFO–LAX cash-access award via IST to BKK. The American positioning observation reports USD 59 with unknown quote scope; the Turkish award reports 275,000 points, business as the award-level cabin, unknown fees, unknown seats and award traveler support. Its LAX join is 150 minutes and its IST connection 140 minutes. Each leg’s cabin is absent, so the answer’s caution about the business label is accurate.
- The displayed `018b54da…` alternative is also conditional. Its Alaska SFO–LAX cash observation reports USD 59 with unknown quote scope; the separate LAX join is 149 minutes, the IST connection 420 minutes, and award fees and traveler support remain unknown. The comparison registry and offset-aware journey timestamps confirm that it departs 4 minutes later, arrives 4h35 later, and takes 4h31 longer.
- The cash baseline observation `f1fcd665…` reports USD 452, SFO–BKK with two stops, Delta and Korean Air, and unknown quote scope. The answer does not fold this baseline into the award or claim an all-in value comparison.
- U passes because “investigate” is a defensible next action for the exact earlier-arriving lead, with the separate-ticket and traveler-support limitations stated. M2 passes because the narrative ties the lead, alternative, displayed comparisons, cash context, and consolidated caveats together. C is decision-rich: the answer quantifies arrival and elapsed differences, distinguishes the two IST waits and positioning carriers, and explains the cost and protection unknowns.

## Material uncertainty

All 232 explorer journeys are conditional; `evidence.json` `journeys[].internal.reason_codes` includes `award_travelers_unknown` and `positioning_permission_unknown` for both shown journeys. The answer discloses award traveler uncertainty and the need to check separate-ticket workability, but does not explicitly say the traveler has not agreed to positioning. It also does not explicitly state that the 275,000-point quote has unknown point scope. These omissions warrant attention, though neither sentence asserts a false per-traveler, all-in, or eligible-booking conclusion.

The alternative is a valid source journey and appears in a reference block and `answer.md`, while `document.json` `selection.journey_ids` contains only the lead. The blind bundle does not establish whether selection is meant to contain every displayed journey or only the selected recommendation. I did not turn that binding uncertainty into an H failure. The parent may adjudicate it against the rendering contract.

Inspection was limited to the assigned bundle and reviewer instructions. I used compact Python JSON field inspection and checked `answer.md` against `document.json`, `evidence.json`, `references.json`, and `comparison-registry.json`. Escalation is recommended only if selection/reference semantics need architectural interpretation; no deeper source investigation is needed for the factual verdict.
