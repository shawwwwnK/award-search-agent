# Iteration 005 review

Status: agent review finds the admitted and conditional answers substantially
more usable than the baseline, but still needs presentation refinement; owner
review pending. The incomplete case was held for a rendered-slot vocabulary
revision. This iteration contains two live Results-only cases.

The admitted answer presents a direct economy award reaching Bangkok on January
16 against a conditional business-cabin award with a separate Los Angeles cash
flight reaching Bangkok on January 17. It states the later-day tradeoff, separate
ticket conditions, observed prices, local schedules, cabin limits and a distinct
cash comparison. The corrected document is clean with no notices. It repeats
the quote-scope sentence per option and again in a shared note, includes a
redundant “cash fare is available” line after the cash comparison, and devotes
too much space to generic search limits.

The conditional answer compares economy and business-cabin awards on the same
separate-ticket route. It visibly retains baggage, transit, connection,
traveler-count, price and cabin uncertainty. It too is clean with no final
notices. It repeats the same shared quote-scope sentence twice, duplicates
whole-trip/component timing, and renders missing award fees as “points plus
Amount not reported,” which reads poorly. The separate-ticket requirements
paragraph is long and partly repetitive.

Both cases used the same frozen v4 source, explicit `gpt-6.1-sol` configuration,
and saved Ranking exports. Each made two live authoring calls (initial plus
correction). Both corrected drafts pass mechanical checks and exact replay.
The source/code hashes were unchanged during each call; exact writer usage and
per-attempt findings are in their `receipt.json` files. The Results package and
dependency versions are archived for historical replay. These cases do not
qualify the incomplete-answer path or the other early-2027 final cases.

Next iteration should supply the writer with the exact rendered vocabulary for
small finite slots, stop it from writing “plus Amount not reported,” and prevent
duplicate shared quote and benchmark-status sentences. It should then run the
admitted, conditional and incomplete cohort on one frozen source.
