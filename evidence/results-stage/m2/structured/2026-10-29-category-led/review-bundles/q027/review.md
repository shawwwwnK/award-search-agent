# q027 source review

**Overall: PASS.** H, U, M2, C, K and P pass for the supplied source/answer boundary.

The model wording was reviewed independently of correct cards. It describes no complete eligible award journey, conditional program/date checks, date-only schedules and unknown quote scopes. These match source rather than claiming a confirmed itinerary, traveler balances/preferences, or economic superiority across different point currencies. Under Q3, the conditional program/date explanations are useful next-check reasons without requiring a numerical comparison or fixed number of leads.

Exact selected evidence:

- United `a8dad3774d9e11df4c6a4a282520a7b66bca6c5736c576e527b48257efdfe6ae`: SFO–BKK, January 9, 2027, economy, 55,000 United points, USD 16.20 taxes quote, 9 reported seats, unknown price scope.
- Aeroplan `5486487c6671aff4179cb6601eb4a9b802d49305e58a788b192fe30f8f974bc4`: SFO–BKK, January 19, 2027, economy, 65,000 Aeroplan points, CAD 82.90 taxes quote, 9 reported seats, unknown price scope.
- Cash `29289b6c9db95327ccdcc1ca2eda4a84c3cdf070c64a81ab5ab8465981720f1d`: `kind=cash_itinerary`, SFO–BKK, `cash_amount.value=686`, `cash_currency.value=USD`, `price_scope=unknown`.

Award field citations are `evidence.json components[observation_id=…]` fields `origin`, `destination`, `departure_date`, `program.value`, `cabin.value`, `points.value`, `taxes_fees.value`, `taxes_fees_unit=minor`, `tax_currency.value`, `seats.value`, and `price_scope`. Both leads have `missing_information=[itinerary_schedule_incomplete]`; component schedule instants and durations are absent. The source request permits January 1–31 and states no cabin preference. “Route-matching” is supported as endpoint match, with incomplete schedules made explicit. The answer does not assert verified intermediate routing.

Shared schedule/scope limits are explained once, with compact factual card indicators retained. Current availability/price verification appears once. The source-typed “Cash comparison:” prefix and the authored words “Cash search results” visibly identify one brief bound sentence in both Markdown and HTML. There is no cash card and no duplicated cash paragraph. The cash observation is dated January 1; the answer does not use it for a same-date savings calculation or claim a guaranteed fare throughout January. Two actual HTML lead-card articles match the resolved source components exactly.

Null `style_audit` entries agree with empty source alternatives, assessments, comparison pools and style indexes, supporting K. Free choices A26/A60/A131/A164/A288 normalize to five optional pool leads; C2 normalizes to the cash reference. The delivered document uses A26/A60. No quota or material omission requires displaying the others. Other dates/programs/cabins and partial-route summaries were examined beyond selection; the answer claims neither exhaustive coverage nor a best/cheapest itinerary.

Verification covered all 383 components, 378 award-summary leads and five cash observations, all endpoint/program/cabin/date/point/tax/scope groups, request, gaps and empty Ranking landscape. All source identities and 14 common factual fields match evidence; complete award/lead and cash reference populations remain intact. Every selected resolved component equals its evidence component. Explorer preservation is verified at the supplied data boundary; interactive UI was not supplied or tested.

Blindness disclosure: I previously reviewed q006/q009/q012/q015/q018/q024 on the same source and remember their answers/outcomes. This is not a fresh source-blind assessment. I read only the latest rubric and q027's seven assigned artifacts in this task, reusing previously read AGENTS.md. Current profile/model settings, prompts, generation timing, token metrics, checker verdicts, other current grades, campaign summaries/index and docs/reviews remained unread. No runtime code inspected; HTML content/markup checked without browser rendering.

Files written: `q027/review.json` and `q027/review.md`. JSON/six axes, audit normalization, two cards and a single visibly labeled cash sentence validated. No live calls, product/runtime edits, outside-source research or delegation. No population, provider-fresh, latency or bookability claim follows from this saved-answer pass. No escalation recommended.
