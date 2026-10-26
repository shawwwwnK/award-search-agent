# Independent answer review — Luna latency probes

Date: 2026-10-25. Reviewer: independent architect agent. The review reads each
complete narrative and its exact references against the original saved source
artifacts under `../2026-10-25-cost-experiments/luna-retest/round-1/`, using the
[composition contract](../../../../../docs/plans/2026-10-25-results-m2-composition-correction.md).
Latency was not used to decide quality. Verdicts apply to individual saved outputs,
not model-wide capability or repeatability. No live calls or product edits were made.

| Probe | Source/composition verdict | Mechanical finding disposition |
| --- | --- | --- |
| admitted-low | Fail: wrong comparisons and omitted material alternative | Clean checks do not detect these narrative errors |
| conditional-low | Fail: misleading decision landscape | Clean checks do not detect the omitted same-schedule economy alternative |
| incomplete-low | Narrative/source pass with minor wording caveat | Fail: three unselected benchmark references; needs correction in the real runner |
| admitted-medium | Fail: wrong Vancouver schedule comparisons | Invalid positioning-component benchmark and invisible declared claim |
| admitted-factored-low | Fail: arrival arithmetic/order errors | Invisible declared cabin claim |
| admitted-factored-medium | Main narrative quantities reconcile; contract failure prevents passing | Wrong comparison scope, unselected second benchmark, invalid positioning lead |
| conditional-factored-medium | Fail: misleading decision landscape despite correct selected-pair arithmetic | Clean checks do not detect omitted same-schedule economy alternative |
| conditional-medium | Undeliverable; raw narrative also omits decision-changing economy schedules | Four narrative blocks illegally carry references; Pydantic rejection reproduced |

## admitted-low

Material source errors:

- The Taipei paragraph says noon is three hours earlier than the quickest journey.
  Exact `46ff88141207…` departs January 15 at 12:00; `eba1b0800784…` departs 23:15.
  The difference is **11 hours 15 minutes**.
- The Vancouver paragraph says 17:15 is five hours twenty minutes earlier than that
  Hong Kong flight. It is **six hours** earlier than 23:15.
- Both opening and Vancouver reference claim that Vancouver's January 17 06:30
  arrival is earliest among the highlights. Highlighted Taipei arrives at **01:25
  that same day**, five hours five minutes before Vancouver.
- The quickest-option explanation refers to a later Hong Kong alternative "below"
  that never appears, and calls its departure both later and the same. That dangling
  comparison has no exact supporting reference in this answer.

Material composition gap: three economy routes dominate the answer while no
business/separate-ticket alternative is acknowledged. The original eligible pool
contains 116 business journeys; for example `3b51cb0563e1…` has a Turkish business
award, 275,000 quoted points, a January 17 04:15 arrival, and separate positioning
bookings. Its different cabin and booking arrangement are decision-changing under
the existing composition brief. This finding does not impose a cabin quota or
require recommending business; a supported explanation with an exact alternative
reference would satisfy it.

Verified correct: 19h35 quickest duration, Taipei 22h25 and 8h25 earlier arrival
than 09:50, Vancouver 22h15 and 3h20 earlier arrival, 92,144 versus 65,000 Aeroplan
quoted points, and cash 440 USD / 31h45 / January 17 08:25. The cash scope and
dated-availability caveats are appropriately consolidated. Those correct details
do not resolve the material errors above.

## conditional-low

The two exact selected journeys support their individual numbers: business
`eb95a4e1a79f…` and economy `66a9bef6a376…` depart January 8 at 06:18; they arrive
January 10 at 04:15 and 08:50 respectively. Their difference is 4h35 and quoted
Turkish points differ by 165,000 (275,000 minus 110,000).

The **choice argument is materially misleading**, however. It says preserving
points "gives up that earlier arrival" and frames the key decision as business
early versus economy late. Eligible economy `32cdb0ba4af8…` uses the same 06:18
departure and 04:15 arrival as the selected business option, at 110,000 Turkish
points, with the same 1,857-minute complete duration and separate-ticket boundary.
This exact alternative removes the supposed timing sacrifice. A traveler should
be told that the cabin upgrade, rather than early arrival itself, costs the extra
points. The selected slower economy has no explanation that justifies omitting
this alternative.

Cash 452 USD, departure 06:05 January 8, arrival 00:20 January 10, two stops,
and the January 8 Alaska 42,500-point incomplete lead all reconcile with source.
The limitations preserve unknown award traveler evidence, unknown price scope,
separate-ticket risk and dated availability. Minor wording: "airport transfer"
can imply changing airports; source describes a same-LAX separate-ticket
connection, so "connection and re-check-in" would be clearer.

## incomplete-low

The narrative correctly states that no complete award journey qualifies. Exact
Alaska lead `0c1f9d644829…` is SFO–BKK economy on January 1 at 42,500 quoted miles;
exact `ac6d57df9d47…` is TPE–BKK business on December 31. Its reference explicitly
calls out the wrong origin/date, and no complete connection is invented.

The benchmark set confirms 640 USD is the lowest returned quote, arriving January 4
at 10:35 after 44h40. Korean's 958 USD quote arrives January 2 at 23:05, **35h30
earlier**, consistent with "about a day and a half"; it is the earliest among the
five returned benchmarks. EVA's 686 USD / January 3 11:10 / 32h10 also reconcile.
Unknown scopes and dated availability stay explicit; these are comparisons of
reported quotes, not verified payable party totals.

Minor wording: "would require reaching Taipei first" could be more direct that
the December 31 lead cannot complete a January 1 SFO departure. The explicit
wrong-date reference and no-complete-journey framing prevent a material usable-
connection claim in this answer.

The document nevertheless sets `selection.benchmark_observation_id` to null while
emitting three benchmark reference blocks. All three have `unselected_reference`
findings. The current runtime would invoke bounded correction; one-call probe time
therefore does **not** measure a clean completed answer for this output.

## admitted-medium

Material arithmetic/source mismatch on selected Vancouver `a8f358f50458…`: source
departure is 17:15 and duration 1,335 minutes (**22h15**), but the narrative says
an 8h35 earlier departure and **24h50** total. Against the exact 23:15 / 19h35
Hong Kong baseline, correct differences are **6h earlier** and **2h40 longer**,
not 8h35 and 5h15. The 3h20 arrival improvement and 27,144-point increment do
reconcile.

The SFO–LAX positioning component `7d8b293e0b25…` is emitted as a benchmark despite
being outside the requested-route benchmark set; resolution marks it unavailable
and the checker flags `invalid_reference`. A declared business claim is also
absent from its reference block (`invisible_claim`). These require correction
under the current runtime.

Verified correct: earlier Hong Kong exact `cc11925bdbf1…` departs 11h30 before the
shortest choice and takes five minutes longer, arriving January 16 at 22:25;
economy `c37c0ca25094…` departs 06:18, arrives January 17 04:15 and takes30h57;
selected business `2a98925e026c…` arrives08:50 at275,000 points versus110,000.
The text covers materially different alternatives and consolidates limitations,
but medium reasoning does not prevent the material defects in this sample.

## admitted-factored-low

The comparison between January 16 22:25 and January 17 09:50 says **1h25** earlier;
the correct difference is **11h25**. It also says business arrival January 17
08:50 is later than both direct-award choices, although it is **one hour before**
the highlighted January 17 09:50 arrival. The dates and exact referenced members
are unchanged from the original source; factoring has not removed them.

This answer includes the distinct business/separate-booking alternative and
consolidated risk caveats. Its declared cabin claim is nevertheless absent verbatim
from its reference block, so mechanical correction would also be required.

## admitted-factored-medium

The principal narrative figures reconcile: both Hong Kong quotes are 65,000
Aeroplan points plus CAD107.40, the departure difference is11h30 and duration
difference five minutes; business is06:18 to January17 08:50, 35h32, 275,000
Turkish miles; its86USD feeder quote and unknown award taxes are source-supported.
Cash440USD arrives January17 morning while525USD arrives January16 at23:40.
Different programs' points are explicitly kept incomparable, and traveler/booking/
price/availability limitations are consolidated.

The document fails three existing contract checks:

- It declares shortest in the full eligible pool but supplies the wrong supported
  claim scope (`claim_scope_mismatch`).
- It emits a second cash benchmark beyond the single selected benchmark
  (`unselected_reference`).
- It emits SFO–LAX positioning component `7d8b293e0b25…` as an incomplete lead
  although it is not in the source's incomplete-lead set (`invalid_reference`);
  that display is unavailable.

These facts are already embedded in the business journey's source-resolved display;
the separate illegal reference adds no valid display. The output cannot be accepted
as a clean completed answer merely because its primary narrative arithmetic improves
over the fresh uncompressed medium sample.

## conditional-factored-medium

All selected-pair arithmetic reconciles: economy `4a2ad78e800f…` departs14:05 and
arrives January10 08:50 in27h45; business `0286e918614a…` departs08:36 and arrives
04:15 in28h39. Differences are5h29 in departure,4h35 in arrival and54minutes in
duration. The Turkish quotes differ by165,000 points; LAX waits are164/150minutes
and cash feeder quotes139/59USD. The cash452USD benchmark, scope caveats and
separate-ticket/unknown-traveler disclosures reconcile.

The answer nonetheless frames the165,000-mile premium as buying the better cabin
**and earlier arrival**, omitting a decision-changing alternative. Exact economy
`6abf61dad6d5…` has the **same08:36 departure, January10 04:15 arrival,28h39
duration and59USD feeder** as its chosen business counterpart, at110,000 Turkish
miles. Thus a traveler can conserve miles and arrive early; paying extra is needed
for the better reported award cabin. The answer must either make that distinction
or acknowledge the exact early economy option. This is the same material landscape
failure as original conditional-low, despite its correctly quoted selected members.

## conditional-medium

Re-validating the raw response with `StructuredDocument.model_validate_json`
reproduces four errors: narrative blocks1–4 contain journey/benchmark references.
The response cannot be delivered through the existing document contract. No repair
or rewrite was performed for this review.

Its raw selected-member numbers are mostly coherent: J59 is06:18/04:15/30h57
business, J137 is14:05/08:50/27h45 business, J213 is14:05/15:05/34h economy.
Computed business departure/arrival differences are7h47/4h35, with3h12 less
duration; the selected economy arrives6h15 later than selected later business.
However, the source also contains110,000-point economy with the same14:05/08:50
schedule (`4a2ad78e800f…`) and the same06:18/04:15 schedule (`32cdb0ba4af8…`).
Conserving miles does not require the late15:05 arrival suggested by its framing.
This is an additional choice-quality problem beyond structural rejection.

## Review method and limits

Read full `answer-preview.md`, `document.json` and `resolved.json` as appropriate.
Python inspection mapped every displayed reference to the original source
`evidence.journeys` or `evidence.components` and asserted equality for resolved
source objects. Arithmetic and comparison counterexamples above were checked
against those original exact objects. The eligible landscape was searched for
same-schedule economy alternatives and materially different business choices.
Existing findings were inspected after narrative/source assessment; they are
reported separately, not treated as semantic verification.

No full application test or automated prose oracle was run. These are scoped
source-backed judgments over development cases, with owner presentation acceptance,
repeatability, frontend behavior and M3 qualification unclaimed.

## Independent mitigation assessment

All eight requested probes are reviewed. None supplies both a mechanically clean
document and a source/composition pass. The three mechanically clean outputs
(admitted-low, conditional-low, conditional-factored-medium) retain material
narrative or choice-landscape defects. Incomplete-low has a sound main narrative
but needs benchmark-selection correction. Do not equate one-call timings with
latency of an accepted final answer; actual correction timing is unmeasured here.

After fixing the quality verdicts above, the reviewer inspected timing receipts.
Lower effort is a credible latency lever in these samples, but the fresh original
medium outputs also fail, so this study does **not** establish that low effort
caused the errors or quantify a low-versus-medium reliability loss. Likewise,
factoring preserves source information but has not demonstrated quality
equivalence in model use. Matching token counts and inverse decoding establish
data preservation, not successful interpretation or recommendation quality.

Recommend retaining explicit low effort and exact factoring as experimental
candidates, with no default adoption from this cohort. Factoring is the safer
next input experiment because it preserves every source value and eligible member,
but should be measured at fixed effort with repeated randomized/interleaved cases,
cache receipts, complete answer/correction latency and source-backed quality review.
Avoid claiming a precise causal latency gain from single samples under variable
cache/server conditions. The most discriminating next quality criterion is whether
the author compares **cabin and schedule independently** and supports exact date
arithmetic; otherwise a shorter prompt can still yield a fast but misleading choice.

No architectural escalation is recommended. The remaining uncertainty requires
better controlled samples and targeted input ergonomics, rather than a stronger
review model or an assumed production readiness claim.
