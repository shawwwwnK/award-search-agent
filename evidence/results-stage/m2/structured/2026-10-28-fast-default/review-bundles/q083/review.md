# Blind review: q083

- Rubric: `fast-default-M2-v1.2-calibrated`
- H: **fail**
- U: **pass**
- M2: **pass**
- C: **decision-rich**; sparse-source exception: **no**

## Hard factual finding

> “Compared with the recommended choice, it leaves 3 hours 11 minutes later and arrives 4 hours 35 minutes later; its elapsed time is 84 minutes shorter.”

`evidence.json` journey `010ec2caa13dc729a813d55f4e5761340e533c25779d178524fe0bd6af2e6669` has `elapsed_minutes = 1803`; recommended journey `0286e918614a7b41ec9aa8f5d5ec9042bf1bd5234d22fba3e9d968b1511b0bee` has `elapsed_minutes = 1719`. The economy journey is **84 minutes longer**. The immediately following comparison block states the correct direction, so the answer contradicts itself as well as the source.

## Other judgments

The selected business journey is a defensible exact recommendation for a traveler who values its 04:15 Bangkok arrival and reported business award cabin. It names the 275,000-point quote and meaningful downsides: award seats and taxes unknown, a separate SFO–LAX cash ticket, and unverified ticket protection. The displayed economy journey gives up cabin and earlier arrival for 165,000 fewer reported points and a later SFO departure. The second economy journey provides a still later local schedule; the later business journey has the same reported points quote but a later arrival and longer elapsed time. These are supported **local** gains and losses; the answer expressly limits the displayed options to selected examples. The false 84-minute statement does not erase the other supported comparisons, but it materially reduces factual reliability.

The answer uses narrative around embedded journey references, offers a separate one-stop EVA Air cash baseline with unknown quote scope, and consolidates booking limits. This supports M2 composition. The comparison blocks are verbose, though their source values are consistent with the canonical journeys. No exhaustive-frontier or strongest-representative requirement was applied.

Source checks: selected journey records and their `departure`, `arrival`, `elapsed_minutes`, `award_program`, `award_cabin`, `award_points`, `money`, `connections`, and `legs`; the four selected cash component records; `source.view.request.travelers`; and cash benchmark observation `5436f6892bc314630a4d33086ede20fd08197aa93b8dfbbf21f0fa8bbeaf07ed` (`stops = 1`, `airport_sequence = [SFO, TPE, BKK]`, USD 605 with unknown scope). No live calls were made.

Uncertainty: no material source ambiguity remains for the failed duration claim. Escalation is not needed for the source judgment; the parent can adjudicate the separate H/M2/C dimensions.
