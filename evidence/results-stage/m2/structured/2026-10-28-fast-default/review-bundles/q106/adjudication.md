# Independent q106 comparative-depth adjudication

Rubric: `fast-default-M2-v1.2-calibrated`. Date: 2026-10-28. Original review preserved; this is a separate adjudication, not a rewritten blind review.

**Verdict: H pass, U pass, M2 pass, C decision-rich; no sparse-source exception. C-basic does not stand under the displayed-argument calibration consistently applied to q098.**

## Blind sequence

Read the campaign instructions and only q106 answer/document/references/evidence, then recorded the initial assessment at `/private/tmp/v27-depth-assessment.md`. That assessment already gave C decision-rich, before reading q106 reviews or q098. Subsequently inspected both original reviews, q098 answer, and its two relevant canonical award components. No run settings or timing consulted.

## Displayed argument and canonical proof

q106 opens: “I’d check the January 1 Alaska award lead first, if that date works for you”. It prices the other choice at “7,500 more points in the same program” and closes: “whether January 1 works for you ...; if not, check January 7 on the same terms.” The reader receives an actionable conditional date/points choice, not merely two unexplained date labels. Choosing the later displayed date gives up 7,500 reported Alaska points while retaining the same reported fees/seats; selecting January 1 saves those points but requires that earlier date to work. Neither date is inherently preferable or known to suit this owner.

`evidence.json` components[2], A3 (`0c1f9d6448293b124e2917fb659277096ae49aba446a59bfd57274af3d0ad07b`): departure_date 2027-01-01, program.value alaska, points.value 42500, money.quoted_usd 50.9, seats.value 8, cabin.value economy. Components[20], A21 (`eed8e1e813efe23f2a87656c39948def8fcc93291351341db16b44e9a7219608`): 2027-01-07, alaska, 50000, 50.9, 8, economy. Both money.scope unknown, returned_travelers absent, and leads[2]/[20] identify incomplete itinerary schedules. Source request specifies January 2027 without a day preference; journeys is empty and provider_status partial.

C1 / components[106] (`456ce00d08b184d171728f7e51cce2dd7feff2cc201cc031c778ec907b04b630`) supports the separate Cathay Pacific SFO-HKG-BKK baseline: stops.value 1, duration_minutes.value 2680, local departure January 1 22:55 -08, arrival January 4 10:35 +07, USD 640 unknown scope, returned_travelers.value 1. H/U/M2 pass for accurate limited evidence, useful verification next action, woven references and relevant cash/coverage context.

## Consistency with q098

q098 recommends January 2 if it works, relative to January 1: United 55000 vs 60500 miles and USD 24.50 vs 28.20 raw taxes (q098 components[4]/[1], A5/A2). Its review credits the earlier date as a “modest, conditional gain” despite no date preference. q106 expressly offers a later date as fallback. Calling that merely hypothetical while crediting q098's earlier date is inconsistent without adding a preference for earlier departure. Both answers quantify a same-program quote/date choice; q106 even explicitly links fallback to date suitability. The extra raw-tax delta in q098 is another cost difference, not an independent offsetting benefit for its more expensive option.

## Boundary and uncertainty

This is narrow decision richness, not strong or exhaustive advice. The phrase “main tradeoff” incorrectly emphasizes a shared limitation rhetorically, but does not make a false factual claim. Date labels alone need not create depth: here conditional selection, quantified same-program consequence, and explicit fallback supply the authored choice. No cabin, option-count, global-best or inventory-frontier requirement was applied. No new rubric or owner preference is proposed. The subjective boundary remains modest; the concrete consistency verdict is decision-rich under the existing calibration. No escalation recommended.

Verification: parsed canonical JSON; checked exact selected references, award differences, quote scopes, missing schedules/party evidence, cash stops/timing/duration and source request. No runtime/model/provider calls or application tests; this is evidence-only adjudication. Only separate adjudication files added; originals preserved.

Original-file preservation: SHA-256 values for q106/q098 answer, document, references, evidence and original review JSON/Markdown are recorded in adjudication.json and verified unchanged across adding this metadata. Hashes were captured at closeout, not before inspection; no original-file writes were performed.
