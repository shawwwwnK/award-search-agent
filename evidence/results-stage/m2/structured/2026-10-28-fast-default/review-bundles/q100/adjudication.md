# q100 source-and-rubric adjudication

Rubric: `fast-default-M2-v1.2-calibrated`. Original `review.md` / `review.json` remain unchanged.

| H | U | M2 | C | Sparse-source exception |
| --- | --- | --- | --- | --- |
| pass | pass | pass | basic | No |

U pass is supported by the exact United verification lead, its stated schedule downside and accurate no-complete-journey explanation. H pass is supported by explicit separation of observed seats from unverified returned-traveler evidence, program lead identities rather than operator assertions, award-summary premium economy rather than every-leg cabin, accurate source quotes with unknown scope, and correct cash route/time/stop context. M2 pass is supported by coherent individually explained embedded leads, relevant separate cash context and a final shared-limits passage. C remains basic: conditional date/cabin interest exists but the answer does not develop a clear offsetting sacrifice beyond shared uncertainty and unrankable cross-program points.

## 1. C — supported_basic_depth_with_refined_ground

> If you prefer the carrier shown on the other January 1 economy lead, check Aeroplan as an alternative; its reported seat count is lower. The points totals are from different programs and should not be compared as equivalent costs.

Source: `evidence.json components[observation_id=0184149657a160229362310b296ec0257a3277c777b852c7b943f3dfb59ac53c]; components[observation_id=cc7d8d9eb93023cfdd2dc89a9db92fe94154a32100978836c3db10ed4c4a8044]`. Fields: `carriers; program.value; seats.value; cabin.value; departure_date`. Values: Aeroplan program/BR/2/economy/Jan 1; United program/CA, UA, ZH/9/economy/Jan 1.

A conditional carrier preference is permissible even when the traveler did not state it; that alone is not a rubric violation. But the delivered text and display label never identify BR, so “carrier shown” does not develop an actionable carrier choice in this supplied rendering. The paragraph otherwise supplies a lower seat count and a points-comparability limit. This remains basic. Do not infer that Aeroplan is the operating airline: the sentence never makes that identity claim.

## 2. C — supported_basic_depth

> For a different date and cabin, the January 12 Alaska lead reports premium economy. It may be worth checking if that date and cabin suit you, but its 140,000 Alaska miles are not directly comparable with points from the other programs, and the itinerary schedule remains unspecified.

Source: `evidence.json components[observation_id=42cf9bfb3736f994c20d673468c06a45363d8653a202b2ee733f0db7d2ec0f97]; components[observation_id=cc7d8d9eb93023cfdd2dc89a9db92fe94154a32100978836c3db10ed4c4a8044]`. Fields: `departure_date; cabin.value; points.value; money.quoted_usd; money.scope; legs`. Values: Alaska Jan 12/premium_economy/140000/USD 50.90; United Jan 1/economy/60500/USD 28.20; scopes unknown; no reported award legs.

This identifies a useful possible cabin/date gain but develops little about the corresponding sacrifice. Unspecified schedule is shared, and cross-program noncomparability is a limit on inference, not an established cost disadvantage. The subsequent tax numbers are individually stated without an authored comparison or decision consequence. Basic is supported for the whole answer; it is not insufficient, and no fixed number, cabin or globally strongest representative is required.

## Other factual checks

- “United is the most useful first lead” is scoped by “For January 1”, desired economy and larger reported seats, then paired with the displayed Aeroplan lead. It need not assert global best across January or all cabins. Missing stronger representatives does not falsify this local argument.
- “Seat support ... is not verified by a returned traveler count” accurately states the absent field; it does not claim the seats are unavailable or that a returned count is the only imaginable support mechanism.
- “Premium economy for the journey” is qualified immediately as not established on every leg and repeatedly framed as an incomplete lead. It does not assert a complete journey exists.
- The carrier-reference omission weakens communication but is not evidence that the answer calls the Aeroplan program an operating carrier. No additional material source contradiction was established.
- Unknown tax/fare scope and partial coverage are consolidated; cash is one-stop SFO/HKG/BKK, not an award recommendation or a per-person/party total.

## Unresolved disagreement

- The basic/decision-rich boundary is qualitative. A permissive reading could credit the conditional cabin/date choice more heavily, but its losses remain undeveloped; source abundance alone is not the reason for basic.
- “Carrier shown” would be more actionable if a separate UI card displayed BR. No such rendered carrier detail is present in the supplied answer/document, and this review does not assume unseen UI content. The omission does not establish false carrier identity.

## Verification

- Parsed both assigned documents, canonical evidence, references, comparison registries and original reviews; read both complete answer.md files under the fixed rubric.
- Confirmed embedded selections map to A2 (United), A1 (Aeroplan), A37 (Alaska), and C1 (cash); all document block text appears in answer.md.
- Confirmed zero complete journeys, 378 incomplete leads, five cash benchmarks and partial provider coverage in each bundle.
- Checked selected program/carrier/cabin/seat/traveler/money fields against source.view.components as well as projected components. Original award source legs are empty; projected unreported legs do not establish per-leg cabin.
- Decimal arithmetic: CAD 116.50 × frozen CAD/USD rate = USD 82.11164364251480124048491683; selected USD quotes differ by USD 22.70. These are quote arithmetic, not trip-cost differences.
- Offset-aware cash elapsed time is 2680 minutes = 44h40; SFO Jan 1 22:55 -08:00 to BKK Jan 4 10:35 +07:00, airport sequence SFO/HKG/BKK, stops=1.
- Inspected compact same-program economy observations to rule out a sparse-source exception; omission of these observations is not itself a failure.
- No live calls, runtime tests, external source reads, source edits or rubric edits. Original review files preserved.

No deeper escalation recommended. Parent integration should preserve the stated disagreement. This adjudication makes no model/default qualification claim.
