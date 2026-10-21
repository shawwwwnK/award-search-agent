# Independent compact-input Luna answer review

Date: 2026-10-20. Read-only review of /Users/shawnkang/bots/award-search/evidence/results-stage/m2/compact-input/2026-10-20-luna/{admitted,incomplete,conditional}/{answer.md,artifact.json,receipt.json}. I treated each artifact.json embedded projection.view as canonical fact authority. Earlier comparison: /Users/shawnkang/bots/award-search/evidence/end-to-end/presentation/iterations/006/{review.md,admitted/answer.md,conditional/answer.md,conditional/artifact.json,incomplete/answer.md}. This is answer review, not owner qualification.

## Recorded outcomes and usage

- Admitted: two Aeroplan economy SFO–HKG–BKK awards and a separate SFO–BKK cash comparison. One call, 199,377 input + 7,145 output tokens. Success, clean, delivered, initial selected; replay_equal true.
- Incomplete: zero complete journeys, two Alaska award summaries (economy and premium economy), separate SFO–BKK cash comparison. Two calls: 141,023 + 2,730 then 141,849 + 1,437 tokens. Success, clean, delivered, correction selected; replay_equal true.
- Conditional: two Turkish economy LAX–IST–BKK choices using the same award observation but different SFO–LAX cash feeders, separate SFO–BKK cash comparison. Two calls: 179,488 + 5,462 then 181,314 + 4,817 tokens. Success, annotated, delivered, correction selected; replay_equal true.
- Total receipt usage: five calls, 843,051 input and 21,591 output tokens, 864,642 total. Conditional final still has two failed shared_binding_key checks for coverage and provider_status. The renderer exposes these as “Please check” notices. Those are structural/checker defects, separate from factual correctness of the coverage text. Clean outcomes in the other cases are mechanical checks only.

## Factual and advice audit

No unsupported positive claim of present award availability, bookability, protected connection, per-leg cabin, or party-wide price was found in the delivered prose. All three preserve unknown quote scope, observation dates, partial provider coverage, and the separate cash benchmark.

Admitted: Option A departs SFO Jan 15, 2027 at 11:15 PM and arrives BKK Jan 17 at 9:50 AM; elapsed 19 h 35 m. Option B departs Jan 15 at 11:45 AM and arrives Jan 16 at 10:25 PM; elapsed 19 h 40 m. Both are Aeroplan economy at journey level, 65,000 points + CAD 107.40, with individual-flight cabin not reported. The answer correctly explains that B reaches Bangkok one calendar day earlier despite A's five-minute shorter elapsed time. Canonical flight numbers differ (UA877/TG603 versus UA869/TG607), so they are distinct underlying itineraries. Cash comparison is USD 456. The resource-budget search omissions described are supported by canonical coverage.

Incomplete: canonical projection has no complete alternative. Lead A is an Alaska summary, Jan 1, economy, 42,500 points + USD 50.90; Lead B is an Alaska summary, Jan 12, premium economy, 140,000 points + USD 50.90. Neither has flight times or leg cabin evidence. The answer correctly withholds a complete recommendation and treats Taipei only as a search hypothesis. Cash comparison is USD 958. The amounts match source, but “42,500” and “140,000” omit the points unit. The award program is also omitted; it was available canonically but is outside the mandatory incomplete-lead keys.

Conditional: both journeys use one Turkish LAX–IST–BKK economy award observation, Jan 8 at 6:30 PM award departure to Jan 10 at 8:50 AM arrival, 110,000 points, fees unreported. Option A adds a USD 59 feeder departing SFO Jan 8 at 1:50 PM, arriving LAX 3:24 PM, 186 minutes at LAX and 28 h overall. Option B adds a USD 139 feeder departing 2:05 PM, arriving 3:46 PM, 164 minutes at LAX and 27 h 45 m overall. The USD 80 feeder and 15-minute elapsed differences are source-consistent. The answer explicitly retains separate-ticket, positioning-approval, award-seat, fee, quote-scope, and all-in-price caveats. Cash comparison is USD 452. Its coverage note matches omitted searches; the visible checker notices remain.

## Presentation and choice quality

- Admitted's tradeoff is useful, but identical generic titles hide the earlier-calendar-arrival decision. Both options say “Highlighted for Shorter travel time”; that source style label is awkward on B when A is five minutes shorter. Price/cabin caveats repeat.
- Incomplete now gives a usable no-complete-itinerary answer where iteration 006 delivered none. Its opening appends a bare “0”; it prints “arrive Time not reported”; it omits points units and program names; the cash comparison repeats awkward disposition wording. These are visible utility defects despite clean mechanical checks.
- Conditional spends both options on the same award and same cabin, varying only feeder fare by USD 80 and whole-trip duration by 15 minutes. The canonical pool still contains the business-cabin candidate selected in iteration 006, so that stronger award/cabin tradeoff was available in the new projection. The repeated long paragraphs and visible “Please check” lines weaken the answer. “A few details need confirming” understates the number of open conditions, though the later caveat is explicit.

## Comparison limits, commands, escalation

Iteration 006's admitted selection had distinct points/fees/routing (65,000 + CAD 107.40 versus 92,144 + CAD 43.90); its conditional selection contrasted economy and business at 110,000 versus 275,000 points. The new admitted answer states the calendar-day difference more clearly, and the incomplete case delivers. The new conditional choice is less informative. These are observations, not causal attribution to compact input: model, guidance, and settings changed too. The five saved calls do not establish broad quality or model context fit.

Commands: rg --files to locate evidence; cat for new and iteration-006 answers/review; read-only jq queries for selected IDs, canonical alternatives and components, coverage, disclosure profiles, checker findings, receipt usage and states. No live model/provider calls, code changes, repository writes, or test suite runs. Remaining uncertainty: generalization beyond these cases and relative contribution of model versus source representation. No escalation needed for this evidence review. Recommend architect if choosing distinctness policy or revising the authoring/checker contract; those are conceptual design decisions.

