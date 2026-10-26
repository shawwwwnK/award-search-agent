# Results M2 latency investigation: reasoning, recommendations and FDE evidence

Date: 2026-10-25. This explains the completed investigation and its proposed next
experiment. Runtime settings remain unchanged; no quality-preserving latency fix
has yet been demonstrated.

The recommendation came from connecting three findings: **Luna spends substantial
time reasoning, the input makes comparison unnecessarily laborious, and reducing
reasoning alone did not produce acceptable answers.**

That suggests changing how we present the decision to Luna, then testing whether it
can do the job with less reasoning. The evidence supports that experimental
direction; it does not yet demonstrate that the change solves the problem.

## 1. Start with the product requirement

The owner reported waiting more than a minute for recommendations and wanted to
keep Luna. The relevant outcome is **time until the traveler receives an acceptable
answer**.

Several measurements can look encouraging without meeting that requirement:

- An API connection opens quickly.
- The first fragment of JSON arrives.
- The model finishes an answer quickly.
- The document passes automated checks.

Each is useful evidence, but the final answer must also make correct comparisons
and explain meaningful choices.

For example, the incomplete case finished in 13 seconds and its narrative was
source-supported. However, its references violated the document contract. The real
runner would need a correction call, adding more waiting.

The experiments therefore measured **initial-generation latency**, separately from
accepted-answer latency. No corrections were run in this diagnostic. For FDE work,
the metric needs to represent the experience the customer actually cares about.

## 2. Locate the delay before choosing an optimization

The relevant workflow is:

```text
Prepare evidence
  + count input tokens
  + send request and wait for generation
  + validate and resolve references
  + correct the answer when necessary
  = time until delivery
```

The earlier 70–90-second measurements covered the generation request itself. They
excluded preparation, counting and subsequent checking.

The local preparation, workspace construction, checking and reference resolution
profiled in this investigation together took approximately **0.67–1.79 seconds**
per case. That excludes source parsing, full-run replay and token counting.

This narrowed the investigation. Optimizing those measured local operations could
save some time, but could not explain the minute-long generation measurement.
Token counting remains unmeasured and adds application latency, but it also cannot
explain time already measured inside the separate generation request.

The next step was to investigate the model request. See the
[local timing measurements](../evidence/results-stage/m2/structured/2026-10-25-latency/local-timing.json).

## 3. Test whether reasoning effort materially changes the wait

The current request leaves reasoning effort unspecified. Returned receipts show
Luna using medium effort.

Explicit medium and low effort were compared using the same saved inputs:

| Saved case | Medium effort | Low effort |
| --- | ---: | ---: |
| Admitted | 87.25 s | 16.52 s |
| Conditional | 42.84 s | 17.06 s |

The admitted case provides particularly useful evidence:

| Measurement | Medium | Low |
| --- | ---: | ---: |
| Input tokens | 207,324 | 207,324 |
| Cached input tokens | 207,321 | 0 |
| Reasoning output tokens | 7,054 | 360 |
| First visible text | 77.42 s | 7.16 s |
| Full response | 87.25 s | 16.52 s |

The medium request had almost its entire input cached and still took 87 seconds.
The low request had no cached input and finished in about 17 seconds.

**Interpretation:** reasoning work is a major contributor to latency in this
workload. Cache reuse alone does not remove expensive generation work. This uses
returned reasoning-token counts, not access to the model's private reasoning text.

These are individual samples, with different cache conditions and potentially
different server conditions. Server queueing, input processing and network time
were not separately measured. We cannot assign an exact percentage of the delay
to reasoning. Nevertheless, this was enough to make lower effort a serious
candidate. [Complete metrics](../evidence/results-stage/m2/structured/2026-10-25-latency/summary.json)

## 4. Evaluate the faster answers before accepting the speedup

The low-effort results had material problems. One answer described a noon departure
as three hours earlier than a 23:15 departure. Another mishandled arrival ordering
across dates.

A more revealing failure involved the choice argument, even though the quoted
numbers were correct. The conditional answer effectively presented this comparison:

| Discussed option | Arrival | Quoted Turkish miles |
| --- | --- | ---: |
| Economy | January 10, 08:50 | 110,000 |
| Business | January 10, 04:15 | 275,000 |

It explained the extra 165,000 miles as buying business class and an earlier
arrival. But the eligible evidence also contained:

| Omitted option | Arrival | Quoted Turkish miles |
| --- | --- | ---: |
| Economy on the same schedule as that business option | January 10, 04:15 | 110,000 |

That changes the decision. The traveler can conserve miles **and** arrive early.
The points premium buys the better reported cabin; earlier arrival does not
require paying it.

Every number in the selected-pair comparison can be correct while the
recommendation still misleads the traveler. Reviewing only the selected options
would miss the failure; review must consider the relevant eligible alternatives.

Independent review found this problem in both original low and factored medium
outputs. Medium baselines also had other failures. We cannot conclude that lowering
effort caused all the quality problems. We can conclude that **low effort has not
yet earned adoption**.

All eight probes failed either mechanical or semantic acceptance. Three outputs
had clean mechanical checks while retaining material narrative or choice errors.
[Independent source and composition review](../evidence/results-stage/m2/structured/2026-10-25-latency/review.md)

## 5. Inspect what Luna is being asked to work through

The original inputs contained roughly 171,000–207,000 tokens. Size made them worth
investigating, but the more actionable finding was their repetition.

In the admitted case, 142 journey fact groups contained only:

- Two distinct reasons values.
- Two distinct cost structures.
- Four distinct assessments.
- Two distinct positioning-reason values.

Large structures were repeated across groups. The reversible factoring experiment
stored each distinct value once, then referenced it from the relevant group.
Every exact journey remained selectable.

Preservation was checked mechanically: reconstructing the original request from
the factored representation produced the original request exactly. This established
that the information had been preserved.

Actual API input tokens fell:

- Admitted: **207,324 → 142,367**, a 31.33% reduction.
- Conditional: **189,806 → 130,864**, a 31.05% reduction.

All 258 admitted and 232 conditional exact journey aliases survived. The incomplete
case had no journeys, so this factoring method left it unchanged. Its component and
lead evidence requires a separate approach.

This is a useful engineering result independently of answer quality: substantial
input was removed without removing source information. But preservation is only
one requirement. Luna still has to interpret the representation correctly.
[Exact preservation audit](../evidence/results-stage/m2/structured/2026-10-25-latency/audit.json)

## 6. Discover why compression alone is insufficient

Factoring produced mixed latency results:

| Case and effort | Original | Factored |
| --- | ---: | ---: |
| Admitted, medium | 87.25 s | 55.95 s |
| Conditional, medium | 42.84 s | 43.22 s |
| Admitted, low | 16.52 s | 15.09 s |

A 31% input-token reduction did not produce a consistent proportional speedup.
None of the factored outputs passed both mechanical and semantic acceptance.
Changed reasoning-token counts, cache conditions and sampling variance prevent
isolating input-processing savings from these single draws.

That changed the recommendation. **Exact compression reduces duplication. A clearer
comparison view could also reduce the reasoning the model must perform.** The
second benefit remains a hypothesis to test.

A compact representation can still require considerable work:

1. Find a candidate.
2. Follow references to its component facts.
3. Recover its schedule and price scope.
4. Compare it with another candidate.
5. Search for a third candidate that invalidates the apparent tradeoff.
6. Calculate date and time differences.
7. Turn the result into a coherent explanation.

Simply shortening the input does not necessarily simplify those operations.
Additional indirection can make some relationships harder to see. This is an
inference about a possible mechanism, not a measured explanation of the model's
internal process.

That is why the recommendation addresses the organization of the evidence as well
as its size.

## 7. What the recommended input change is intended to accomplish

The proposed writer view would put the facts needed for comparison close to each
exact selectable option:

- Departure and arrival, including full dates.
- Whole-journey duration.
- Cabin and program.
- Points and cash amounts with their scopes.
- Separate-ticket arrangements.
- Material unknowns.
- Relationships to meaningful variants.

For the conditional failure, a comparison aid could explicitly expose:

> These economy and business variants have the same departure, arrival and duration.
> Their quoted Turkish miles differ by 165,000.

Luna would still decide whether those variants matter, which to highlight, and how
to explain them. Ranking and eligibility would remain unchanged. Schedule
relationships must not imply broader equivalence in price, cabin or booking facts.

Similarly, code could supply exact time differences:

> January 16 at 22:25 is 11 hours 25 minutes before January 17 at 09:50.

That could reduce the arithmetic Luna needs to reconstruct while composing prose.

The proposed division of work follows the observed failures:

| Observed difficulty | Proposed assistance |
| --- | --- |
| Repeated evidence consumes context | Factor identical structures |
| Relevant alternatives are overlooked | Expose meaningful variant relationships |
| Date differences are wrong | Supply calculated differences |
| Facts are associated with the wrong reference | Keep essential identity facts beside the reference |

These are experimental aids. Their value still needs measurement. The full eligible
inventory, exact references, unknowns, canonical evidence and independent explorer
must remain intact. This recommendation does not adopt a stronger inline-factual-
binding requirement or change model ownership of narrative composition.

## 8. Why streaming and caching are secondary recommendations

Streaming exposed an important distinction: the first event arrived in roughly one
second, but medium first visible text took 34–77 seconds.

For admitted medium, only about ten seconds separated first text from the completed
response. Most of the wait had already happened. Streaming could make later output
feel more responsive, but would not by itself eliminate that initial wait. A fragment
of structured JSON is also not yet a checked recommendation or usable flight display.

Caching revealed a separate opportunity on corrections. Current serialization puts
feedback before the large stable evidence view. When feedback changes, initial and
correction inputs diverge after only 13 bytes.

An offline reordering probe showed that putting stable evidence first would preserve
approximately 597,000 bytes of shared input prefix. This provides a concrete reason
to test better cache reuse on corrections. The resulting cache hit and latency
improvement have **not** been measured. This targets corrections and retained-
evidence follow-ups, rather than a first cold request.
[Prefix experiment](../evidence/results-stage/m2/structured/2026-10-25-latency/prefix-audit.json)

## 9. Cross-cutting learning and FDE recruiting evidence

The central engineering insight is that latency, representation and recommendation
quality interact. Lower effort changes generation time; compact input changes what
the model must read; comparison organization may change the work required to reach
a useful answer. Each needs its own evidence.

The strongest recruiting evidence is the chain from a product complaint to a bounded
engineering decision:

- The owner established the constraint: keep Luna.
- The investigation defined the relevant outcome and separated generation from delivery.
- Measurement narrowed the investigation to the model request.
- Two plausible levers were tested: reasoning effort and input representation.
- Information preservation was proved rather than silently trimming options.
- Actual recommendations were reviewed against the full source evidence.
- Attractive timings were rejected when the outputs failed acceptance.
- Specific failure patterns informed the next proposed experiment.

The same-schedule economy example is particularly useful interview material. It
demonstrates that checking selected facts is insufficient when an omitted alternative
changes the recommendation.

A defensible recruiting description today would be:

> Investigated minute-long recommendation latency under a fixed Luna model
> constraint. Eight bounded probes showed substantially faster generations at low
> reasoning and approximately 31% input-token savings through lossless factoring.
> Source-backed review found that the faster outputs still failed factual,
> comparison or document requirements. Those failures motivated a proposed
> comparison-oriented input representation and a follow-up evaluation measuring
> accepted-answer latency.

That statement claims the investigation and measured results accurately. A claim
that latency was solved would require further evidence. Any personal account of
what the owner learned or decided should reflect the owner's own interpretation;
this document supplies evidence and proposed takeaways.

## 10. Open questions and implications for the next experiment

The unresolved question is now sharper: **Can clearer comparison evidence let Luna
produce correct, useful answers with less reasoning and fewer corrections?**

The next experiment should hold the saved sources and acceptance criteria fixed,
compare the revised representation at medium and low effort, repeat the samples,
record cache conditions, and include correction time. It should explicitly test
same-schedule economy alternatives, cross-midnight arithmetic and exact reference
roles. Those cases discriminate between a shorter answer and a useful answer.

Remaining uncertainty includes the owner's numerical latency target, repeatability
across cases, token-count overhead, safe first-usable-result delivery, and the
quality effect of the proposed representation. No runtime adoption, owner
presentation acceptance, frontend milestone completion or Results M3 qualification
follows from this diagnostic.

## Evidence and verification

The investigation used eight saved-input generations, zero count calls and no new
travel-provider searches or FX refreshes. Estimated generation cost was $0.14050,
excluding native Codex work. The focused suite passed 27 tests. Offline factoring
restored the original requests exactly; saved findings and resolved outputs were
rechecked for seven parsed documents, and the eighth document's validation failure
was reproduced. These checks do not establish arbitrary narrative correctness.

- [Experiment report and actual outputs](../evidence/results-stage/m2/structured/2026-10-25-latency/README.md)
- [Independent source/composition review](../evidence/results-stage/m2/structured/2026-10-25-latency/review.md)
- [Request metrics, usage and cost](../evidence/results-stage/m2/structured/2026-10-25-latency/summary.json)
- [Development evidence and ADR disposition](build-log/2026-10-25-results-m2-latency-experiments.md)
- [Current architectural decision](adr/0029-structured-results-and-local-workspace.md)

Official reference material consulted during the investigation:

- [Reasoning effort](https://developers.openai.com/api/docs/guides/reasoning)
- [Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization)
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)

These references explain mechanisms; the local experiments supply the workload-
specific evidence and its limits.
