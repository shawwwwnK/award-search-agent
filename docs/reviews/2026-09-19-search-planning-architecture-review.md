# Search planning and whole-project architecture review

Date: 2026-09-19

Status: Advisory review for the owner before Milestone 2C implementation. Recommendations below are not approved architecture decisions.

Scope: Project purpose, completed-stage evidence, search planning, proposed 2C, and later workflow design.

Second review added 2026-09-19: [engineering evidence for FDE recruiting](#11-engineering-evidence-for-fde-recruiting). The root [deferred-work register](../../DEFERRED.md) tracks what stays parked and which claims have prerequisites.

Fresh-context Astra challenge, also 2026-09-19: recommendations below were revised in place. Main changes: narrow the first provider slice, bring user feedback forward, distinguish historical defects from current evidence gaps, and make engineering gates proportional to the claims. See the [challenge record](../build-log/2026-09-19-astra-adversarial-review.md).

## Main judgment

The project has a sound division of authority: models interpret language and propose useful search hypotheses; deterministic software controls state, facts, dates, budgets, and execution. Keep that foundation.

The investment is currently uneven. There is substantial evidence that the system can preserve and inspect its boundaries, but little evidence that its expanded searches improve a traveler's shortlist. The next architectural priority should be completing that feedback loop. More schemas, airport coverage, or model-generated strategies do not by themselves establish product value.

I recommend completing a narrow 2C, then testing one provider-backed scenario with validated baseline options and separately labeled supplemental research leads. Do not require automatic assembly of independently ticketed components for that first slice. The roadmap already makes RAG and coverage evidence-driven; my sequencing change is to gather provider and owner feedback earlier. Revisit intent and clarification when that feedback exposes missing decisions, and qualify current supported behavior before claiming a dependable conversational product.

## 1. What the whole project should prove

The owner's workbook identifies two related goals:

- Product: get from a vague trip idea to a credible shortlist in minutes instead of manually coordinating tools and spreadsheets.
- Portfolio: demonstrate AI workflow design, source grounding, tools, evaluation, reliability, and engineering judgment through working evidence.

The current one-way award-only scope intentionally narrows the workbook's older round-trip and cash ambitions. That refinement is sensible. It does not eliminate the need to reach actual results. A mature planning subsystem alone cannot establish either shortlist usefulness or successful inventory-tool orchestration.

My proposed working product target is: **given a supported one-way award request, produce a small, source-linked set of relevant observed options, identify what remains unverified, and show the search coverage achieved within a stated budget.** Empty or partial results can be honest successes in system behavior; inventing enough options to fill a five-item list cannot.

Useful outcome measures should include time to the first relevant option, hard-constraint violations, useful options found per unit of search work, duplicate work, unresolved verification obligations, and how much manual work remains. A planning-only milestone can prepare these measurements but cannot claim them.

The workbook's 50–80 hour flagship target also argues for a completion boundary. It is an original planning target, not a measurement of time already spent. I would not make worldwide airport coverage, document retrieval, multiple inventory providers, or perfect conversational interpretation prerequisites for the first useful workflow.

Sources: [workbook](/Users/shawnkang/bots/workbook_formatted.md:58), [active project state](../project-state.md), [one-way scope](../adr/0016-one-way-award-request-boundary.md).

## 2. What the completed stages establish

| Stage | What is established | What remains unproved |
| --- | --- | --- |
| Intent and clarification | Typed model interpretation, deterministic calendar/state handling, provenance, repairs, explicit scope limits | Broad current conversational qualification; known historical diagnostic failures remain relevant |
| Milestone 0 | A deterministic planning boundary and ten-case seed-fixture gate | Operational search utility and broad geographic coverage |
| Milestone 1 | A reviewed, versioned local geographic/airport catalog with deterministic retrieval | Airport suitability, connectivity, schedules, or inventory |
| Milestone 2A | A bounded endpoint-selection model seam and diagnostic evidence | Human semantic qualification, holdout evidence, and adoption |
| Milestone 2B | A bounded gateway-proposal seam, policy/validation/replay, and owner-accepted closure | Verified connectivity or evidence that the proposals improve observed search results |

This is substantial engineering progress. The distinction between stage closure, structural validity, semantic qualification, and product usefulness should remain visible. It should also become easier to understand: a reader should not need to reconstruct months of superseded decisions to identify the current runtime.

The current architecture document mixes an ADR-0017 description with a retired selector diagram and superseded clarification behavior. The evidence ledger still contains unfilled claims despite many supporting artifacts elsewhere. These are documentation maintenance gaps, not evidence that the implementation is absent. Update them when recording the chosen 2C direction; do not turn this review into a broad historical rewrite.

Sources: [project state](../project-state.md), [architecture](../architecture.md), [evidence ledger](../evidence-ledger.md), [2B closeout](../handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md).

### What the 2B evidence says about work and stability

The independent read-only audit of the final prompt-v6/casebook-v3 artifact found:

| Measurement | Observed value |
| --- | --- |
| Case-trials / model SDK invocations / policy skips | 46 / 42 / 4 |
| Accepted candidates / accepted relationships | 82 / 400 |
| Origin-access candidates / relationships | 22 / 83 |
| Destination-access candidates / relationships | 18 / 50 |
| Hub candidates / relationships | 42 / 267 |
| Relationships per case-trial | Median 3; p90 24; maximum 65 |
| Model tokens | 118,878 input + 67,671 output = 186,549 |
| Mean tokens per generated call | Approximately 4,442 |
| Recorded latency for generated case-trials | Median 15.932 s; p90 22.671 s; maximum 26.485 s |

Latency is the artifact's recorded case-trial latency, filtered to trials with generation; it is not isolated inference time. Invocation counts do not establish transport-attempt counts (§11). No dollar-cost estimate is available because the artifact has no versioned price card. Policy skips are excluded from generation-latency statistics.

The highest-fanout records were:

| Case / trial | Candidates | Required endpoint pairs | Supplemental relationships |
| --- | ---: | ---: | ---: |
| Major US gateways → India / 2 | 4 | 25 | 65 |
| Los Angeles metro → Australia/New Zealand / 1 | 4 | 20 | 55 |
| New York metro → Japan / 1 | 3 | 12 | 36 |
| Major US gateways → India / 1 | 1 | 25 | 25 |

Candidate/scoping summaries differed across the two trials in 18 of 23 scenarios; relationship metrics differed in 19. Los Angeles/Australia–New Zealand changed from 55 relationships to 2. This establishes proposal variability, not that either trial is semantically wrong. A deterministic compiler must operate on a pinned proposal record; it cannot make repeated model calls deterministic.

The investigator also modeled a provisional compilation rule: preserve each endpoint pair, produce the scoped access/hub award probes, deduplicate identical component pairs for the common fixture window, and keep positioning dependencies separately. That hypothetical compiler would produce 55 award items for India trial 2 (25 required + 30 supplemental) and 43 for the Los Angeles trial (20 + 23). Both exceed the existing 40-item ceiling. These counts are an analytical model, not output from an implemented 2C; different final date/filter semantics can change deduplication.

All 43 accepted hub scopes in the final live artifact referenced original endpoints. None used an access-gateway reference inside a hub scope. Therefore the final diagnostic does not exercise access → hub → access compilation. The corpus's three-day window also does not stress a 31-day planning limit. Use synthetic valid records and long-window cases to test those boundaries.

Source: [final public v6 artifact](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json), with immutable record sidecars inspected locally for aggregate relationship/query analysis. No raw private traces are reproduced here.

## 3. The right goal for search planning

A plan should allocate limited search effort toward useful evidence. It should answer:

1. Which requested endpoint combinations must be searched?
2. Which extra searches could reveal a meaningfully different option?
3. What assumptions or positioning dependencies would that option introduce?
4. What work is included, omitted, or deferred, and why?
5. What must downstream code verify before presenting a result as satisfying the request?

This changes the quality question from “Are these plausible airports?” to “Does this extra search add enough useful information to justify its cost?” The latter cannot yet be measured directly; 2C should make it measurable.

Keep four distinct objects:

| Object | Meaning | Example |
| --- | --- | --- |
| Strategy hypothesis | A reason to search, with conditions and unresolved obligations | Search from an alternate departure gateway if positioning is acceptable |
| Logical award query | Complete search semantics independent of its reasons | One origin/destination pair, departure envelope, cabin/filter semantics |
| Provider request | An adapter's actual call, batch, or pagination step | One Cached Search request containing airport lists |
| Observed travel option | Provider evidence that is normalized and checked | Returned itinerary details with seat, cabin, timestamp, and price evidence |

Several strategies may use the same query. One provider request may cover multiple queries, and one query may require multiple pages. Neither a strategy nor a pair of queries establishes a connected or bookable itinerary.

An O → D endpoint-market query also does not mean nonstop. Cached Search exposes a separate direct-flight filter. Its documented airport lists, pagination, and optional trip details reinforce the distinction between logical coverage and transport work. These are documentation-backed capabilities, not newly verified live response semantics. [Official Cached Search reference](https://developers.seats.aero/reference/cached-search).

This matters to the value proposition: baseline searches can already discover connecting itineraries. A supplemental O → H plus H → D strategy investigates separately observed components, potentially involving separate tickets; it is not simply discovering ordinary connections that baseline search cannot see. Its eventual value must be measured against those baseline connecting results. Independently observed prices and availability must not be presented as a through-ticket quote.

## 4. How well we are using LLMs

The current role assignment is mostly right:

- Language interpretation belongs with a model, with grounded proposals and deterministic acceptance.
- Geographic identity and metadata belong in the catalog.
- Endpoint suitability and gateway selection can use model priors, provided the output remains a hypothesis.
- Calendar arithmetic, deduplication, budget enforcement, and request construction belong in code.

The major limitation is that endpoint and gateway proposals mostly use model knowledge before observing inventory. They are informed guesses about useful searches. Catalog validation can establish that an airport exists in the retained data; it cannot establish that searching it will help this traveler.

I would not add a model call inside 2C. Its immediate task is faithful compilation of supplied decisions. A model deciding which duplicate query IDs to retain or adding another explanation of its own candidates is unlikely to address the current evidence gap.

Later, the strongest agentic opportunity is deciding the next bounded action after results arrive: inspect an option in more detail, activate an alternate gateway, request one missing preference, or stop. Start with a deterministic policy and compare a model controller against it. Give the controller a small action vocabulary and a fixed remaining budget. A plausible explanation for another search should not be enough to permit unbounded searching.

There is no need to add product-level multi-agent orchestration to demonstrate this capability. The present implementation is best described as an LLM-assisted workflow; a result-responsive controller could add meaningful agent behavior later. This distinction is consistent with the workflow/agent distinction in [Anthropic's architecture discussion](https://www.anthropic.com/engineering/building-effective-agents), but the recommendation here follows this project's evidence and scope.

## 5. Proposed Milestone 2C

### Objective and boundary

Compile a frozen ready request, selected endpoint airports, and a bound 2B record into mandatory endpoint coverage plus bounded, deduplicated supplemental award-search hypotheses, preserving every dependency, evidence limitation, and omission.

No provider calls, conversation interpretation, new geographic facts, inventory claims, or ranking of returned itineraries belong inside this compiler. It should make zero model calls and produce the same output for the same validated inputs and policies.

### Inputs

- Immutable `EffectiveRequest` and source revision/digest.
- Endpoint selections with catalog provenance and their actual review/adoption status.
- A validated or replayed 2B record bound to the same endpoint selection and catalog identities.
- An explicit compilation policy, budgets, and the reviewed provider capability description.

Bind the resulting plan identity to the actual selector records, selector cap/distance policies, gateway result digest, catalog, market policy, and compiler policy. A request digest alone cannot distinguish different model-selected airports or gateway proposals for the same request. The current airport-selection replay receipt sits outside `SearchPlan.identity`; integration needs to close that provenance gap.

Do not trust only the accepted subset of a stored 2B proposal. Use the existing replay mechanism and its binding checks. A mismatched or corrupt record is a typed evidence problem. An ordinary optional-generation failure should still allow the valid mandatory plan, with the failure disclosed.

### Output shape

Prefer a small extension of the existing plan over an elaborate new orchestration framework:

- Mandatory endpoint probes.
- Supplemental strategy hypotheses referencing the exact accepted 2B relationships that enabled them.
- A shared collection of unique logical queries.
- Many-to-many links from strategies to queries.
- Positioning and later result-validation obligations.
- Coverage and budget receipts identifying included, shared, omitted, and unsupported work.

Use a versioned evolution of `SearchPlan`, since the current contract has dense one-to-one endpoint/probe and physical-route invariants. Retain them for their original meaning rather than loosening them incidentally. Although logical query semantics can be provider-neutral, the current artifact binds a Seats.aero capability record. Describe that accurately as a capability-bound plan over provider-neutral strategy/query semantics.

Include minimal phase and eligibility metadata: mandatory initial work versus supplemental work, and any unresolved positioning/separate-ticket permission. Do not build a general execution graph or invent a definition of “enough results” in 2C. The executor will own activation and stopping. Nonempty baseline results alone should not necessarily suppress every supplement: an expensive or unsuitable baseline option can leave substantial search value.

The existing `ExplicitPathHypothesis` requires directed physical route evidence. Do not populate it with model-proposed gateways or weaken its meaning to make the integration convenient. Use a distinct supplemental hypothesis contract. [ADR 0020](../adr/0020-market-aware-model-proposed-gateway-candidates.md) already requires this separation.

### Strategy semantics

Use named, finite strategy types. For an original O → D request:

| Accepted relationship | Supplemental search idea | Unresolved obligation |
| --- | --- | --- |
| Origin-access gateway G | G → D | How the traveler gets from O to G within the trip constraints |
| Destination-access gateway A | O → A | How the traveler gets from A to D |
| Hub H with an accepted scope | Origin-side endpoint → H and H → destination-side endpoint | Whether observed components can form an acceptable journey |

The table is a proposed compilation vocabulary, not permission to form a new global Cartesian product. Compile only applicability relationships that the input record actually supports. If a scope relies on access gateways, retain those dependencies. If the necessary relationship is absent, the compiler must not infer it from airport popularity or geography.

The current 2B contract does not directly express a standalone origin-access G → destination-access A relationship. Access endpoints can occur inside an explicit hub scope, enabling G → H and H → A. Keep standalone G → A outside the first 2C vocabulary. A future versioned compiler composition rule could derive that hypothesis from compatible source relationships with both provenance links; changing 2B would not necessarily be required. This is a scope restriction, not a claim that composition is impossible.

Access positioning remains an obligation rather than an invented flight or automatic cash search. For a country destination, distinguish an airport already selected as a legitimate destination alternative from an additional gateway requiring onward travel. Do not accidentally add positioning to every country-level endpoint.

For hubs, initially treat the two searches as a linked exploration bundle. Atomic bundle admission is easy to reason about; shared queries may make its incremental cost smaller. A later executor may deliberately search one component first, but a partial result must not appear as a completed journey. Do not silently require nonstop components merely because an intermediate airport was proposed.

My revised recommendation is explicit endpoint-market query semantics, preserving each provider-returned itinerary boundary, **without automatic cross-query journey assembly in the first provider slice**. Hub components appear only as research leads, never completed options or summed through-ticket quotes. This avoids both an implicit nonstop restriction and an immediate general itinerary assembler. If a useful component case later justifies assembly, choose direct-only versus connecting components explicitly and test full topology, chronology, continuity, seats, and independent-ticket implications. `repositioning_allowed` alone does not authorize separate tickets.

### Dates and constraints

Keep the user's actual departure window immutable. Any wider gateway/component envelope is a search approximation with a recorded derivation, not permission for the traveler to depart outside their window. Later validation must reconstruct the actual journey and check the original constraint.

The current first-origin-local and later-component −1/+2 day convention is an approved exploratory convention. 2C needs explicit date cases for access-first travel and date-line/timezone changes; it must not present that envelope as proof of feasible connections. If it cannot represent a strategy faithfully under the declared convention, return a visible limitation.

The proposed mapping is: mandatory O → D and destination-access O → A use the original departure window; origin-access G → D uses the later-component envelope because positioning precedes it; a hub's first query uses the original window only when its origin is an original departure airport, and otherwise uses the later envelope; its second query uses the later envelope. Each query's date basis/timezone follows the explicit compiler rule and relevant airport metadata, not the timezone in the 2B generation context. This mapping is a proposal for 2C, not existing gateway-compilation behavior.

Keep free-text hard constraints as unresolved obligations until the upstream contract supports typed, item-grounded requirements. Do not make 2C a second intent parser. A deferred requirement must also prevent downstream code from casually labeling a result as satisfying every requirement.

### Budgeting and deduplication

Use separate limits for mandatory endpoint pairs, optional relationships/strategies, unique logical queries, and date-expanded work. Record actual provider calls and pagination later in execution; a compiler cannot accurately promise those totals from query count alone.

Bound compiled relationships, unique queries, and date-expanded output. Existing wire limits already make inputs finite: 20 entries per pool, 40 scopes, and 40 references per side. Required replay currently materializes per-scope relationship products before compilation; a compiler cap alone cannot bound that earlier work. Test a saturated valid record and report replay versus compilation cost separately. Add pre-replay admission only if measured resource use warrants it; do not claim lazy end-to-end processing or reopen 2B under an assumed unbounded-input threat.

Deduplicate complete query semantics before charging shared work. Preserve all strategy provenance links when two strategies share a query. Do not merge merely because airport pairs match: dates, filters, cabin semantics, and search purpose may affect result interpretation. Conversely, a provenance-only difference should not force duplicate transport work.

A deterministic allocation policy should prioritize required coverage, then spread optional budget across endpoint pairs using explicit strategy priorities and stable tie breaks. Alphabetic ordering is a serialization rule, not evidence of travel usefulness. Model ordering or self-reported confidence should not silently become an optimization score.

Respect the current mandatory-coverage promise. If selected endpoints alone exceed the admitted budget, retain the existing explicit failure; do not silently trim them. The active US cap of 10 and region cap of 8 can permit 80 pairs, above the planner's 25-pair/40-item limits. This is a ceiling calculation, not observed traffic. ADR 0019 deliberately permits selection to end in budget failure. It is a product tradeoff to measure, not a newly discovered correctness bug or a mandatory admission redesign before 2C.

There is also an authority distinction: airports explicitly requested by the user differ from exploratory airport suggestions for a country or region. My recommendation is to keep 2C's all-selected-pairs promise and, when adopting 2A, add visible request-level budget admission before freezing the final selected set. It can choose among exploratory suggestions under a declared policy; it cannot silently trim explicit user alternatives. For the first 2C pilot, use declared sets that fit the mandatory budget and return the existing typed failure outside it. This avoids giving 2C a hidden second endpoint selector while exposing the later product decision.

When a valid 2B hypothesis is omitted for budget, label it omitted, not rejected or semantically invalid. Market-mismatch advisories and mapping gaps should survive compilation without creating a new hidden semantic rejection rule.

### A policy I would change deliberately

The current v1 planner records `repositioning_allowed` but ignores it even when false. This follows the existing approved design. A synthetic offline probe during this review returned identical search work for false, unspecified, and true: three endpoint probes, one optional physical-path hypothesis, and five award items.

My recommendation is to resolve the meaning before 2C implementation: an explicit refusal should suppress strategies that require repositioning; unknown should remain unknown. Ordinary protected connections and independent positioning are different concepts, so a blanket “no intermediate airports” rule would be wrong. If product policy still permits speculative research despite refusal, its results must be labeled incompatible alternatives and must not displace compliant work. This is a proposed policy revision, not a bug fix or an already approved decision.

For an unspecified value, the plan can retain a conditional hypothesis but must not claim the user accepted positioning. Separate the permission needed to present a strategy as suitable from permission to perform cheap bounded exploratory research under a declared policy. The first 2C need not add another clarification loop to answer that distinction.

### Outcomes and legacy topology

The current planner attempts legacy route-backed expansion and can mark missing topology as reduced coverage. That is inappropriate as an automatic requirement for the new hypothesis mechanism. The proposed 2C policy should disable implicit legacy topology expansion by default; genuinely route-backed strategies can remain a separate explicitly enabled evidence source.

Use typed outcome accounting:

- Policy skip or successful empty optional discovery: valid mandatory-only plan with its discovery receipt.
- Rejected-all optional proposal: mandatory-only plan with explicit rejected-proposal/coverage disclosure; rejection is not proof that no useful alternatives exist.
- Valid optional operational failure: mandatory plan with reduced supplemental coverage.
- Budget omission of accepted work: reduced declared supplemental coverage with omission receipts.
- Record, catalog, endpoint, or replay binding corruption: evidence failure; do not consume the corrupt record as a successful optional result.

These are separate from nonblocking request obligations. In particular, absent legacy route data must not turn every valid 2B skip or empty outcome into a failed search-planning result.

### Completion gate

2C should close when offline evidence demonstrates:

1. Mandatory endpoint coverage is complete for every admitted request.
2. Every accepted optional relationship is accounted for as compiled/shared, omitted for budget, or unsupported by an explicit compiler rule.
3. Queries are unique under the declared semantic key; all strategy dependencies remain traceable.
4. Budget caps hold after deduplication and date expansion.
5. Record mismatch, optional failure, empty results, mapping gaps, and market advisories have truthful outcomes.
6. Dates, constraints, provenance, and source state are preserved; no hypothesis becomes a route or availability claim.
7. Current 2B records can be replayed through the compiler, including high-fanout cases, with an inspectable work report.
8. A declared pilot can progress from supported input geography to the complete plan using reviewed selections or explicitly diagnostic supplied records.

That closes a planning capability for its declared input coverage. It does not adopt 2A or qualify arbitrary natural-language-to-itinerary behavior. Do not reopen 2A implicitly by claiming broad Milestone 2 completion.

## 6. Rethinking intent and clarification later

Yes, there is a worthwhile redesign question. Do it after provider/result work reveals the missing decisions, rather than waiting for every possible milestone or restarting upstream now.

Keep the successful principles: model-owned language interpretation, deterministic calendar execution, immutable state transitions, preserved uncertainty, and explicit unsupported scope. Reconsider the amount of representation machinery and the split between initial and continuation semantics.

Specific experiments worth comparing against the current implementation:

- One shared semantic proposal language for initial requests and subsequent amendments, with different allowed targets and identical deterministic enforcement.
- A minimal authoritative projection of accepted state and relevant previous questions so the model can resolve references without receiving authority to overwrite those values.
- Typed constraints that influence real searches and validation: permitted departure alternatives, separate-ticket tolerance, cabin requirements, stops, and program restrictions, introduced only for supported product behavior.
- Deterministic well-written blocker presentation versus a dedicated model composer, comparing user comprehension, turns, latency, and failure rate. This would revise the current composer policy and needs its own decision.
- Consistent user-facing handling of exhausted interpretation repair. Initial intent currently salvages facts into clarification; continuation uses a non-mutating pending outcome. Evaluate the difference explicitly.

Exact quotations prove where an interpretation came from, not that it is correct. The ADR-0015 diagnostic's three unsafe cases were `bare_return_endpoint`; its sibling-loss example also included duration. ADR 0016 subsequently excluded return/duration state and intentionally stops unsupported-scope turns without accepting their siblings. Those historical cases motivate regression design, but do not demonstrate an unsafe ambiguous-departure defect in the current runtime. Broad current behavioral qualification remains an evidence gap; no new live holdout was run in this review.

Keep 2C tests isolated with frozen requests. Before advertising a reliable multi-turn product, rerun a current, non-vacuous behavioral holdout that includes ambiguity, corrections, contextual references, and partial valid answers. The goal should be fewer user turns and fewer wrong assumptions at acceptable latency, not simply fewer parser exceptions.

The context concern is concrete. The current clarification receiver sees the answer, ordered blocker types, and correction-eligible field names; it does not receive accepted values or structured choices from the previous prompt. Its calendar algebra supports the request date and same-answer prior facts, but not a bound current-departure anchor. Answers such as “make it a week later” or “yes, that option” therefore lack the context needed for faithful interpretation. This is a contract limitation inferred from the active projections, not a new live behavioral test.

Longer term, revisit trip-shaped input too. One-way award search is a useful execution primitive; requiring a traveler to manually split every ordinary return-trip request is a product compromise. After the first useful one-way slice, a parent trip workflow could accept a return trip and create two linked one-way requests while preserving each search's exact constraints. Cash remains a separate provider/capability decision. Neither change belongs in 2C or modifies ADR 0016 in this review.

A future `ClarificationInterpretationContext` could provide revision/prompt/digest bindings, relevant accepted typed values, and allowlisted opaque choice/anchor IDs. The model would select a target or anchor and propose an answer-grounded operation. Code would resolve it and authorize any mutation. Context would guide interpretation; it would not count as newly asserted user evidence. The initial intent receiver's symbolic calendar design does not create the same need to reveal a concrete reference date, so avoid a blanket “send more context everywhere” change.

Relevant implementation: [clarification input](../../src/award_agent/clarification/interpreter.py), [controller projection](../../src/award_agent/clarification/controller.py), [calendar anchor contract](../../src/award_agent/clarification/calendar_plan.py).

Sources: [ADR 0015 closeout](../handoffs/2026-09-10-adr-0015-stage-closeout.md), [ADR 0017](../adr/0017-llm-owned-initial-intent-semantics.md), [upstream constraint follow-on](../handoffs/2026-09-12-search-planning-design.md).

## 7. Database, retrieval, and eventual agent workflow

SQLite is a sensible current choice for geographic identity and structured retrieval. A vector database would not fix an airport-selection quality problem. Keep canonical facts, product selection policy, model hypotheses, and provider observations conceptually separate, even if later stored in one database.

Once provider execution is in scope, the most valuable storage addition is likely a query/result/validation ledger. It should link request revision, strategy, logical query, actual attempts, provider timestamps, normalized observations, validation decisions, and shortlist inclusion. This turns stage-specific traces into an end-to-end explanation of why an option was recommended or missed. Persistence is currently a non-goal; this is a later proposal, not work performed here.

Cache different things for different reasons. A version-bound endpoint or gateway proposal can be reused as a proposal; an inventory result has different freshness requirements. Never let a cached “no result” become a permanent route fact. Never promote past search success into authoritative catalog truth without a separate evidence policy.

The roadmap's M3 is a human-reviewed knowledge-authoring experiment, not runtime RAG. A separate later runtime use could retrieve changing loyalty conditions missing from a real option. For either, compare structured data or lexical retrieval before embeddings. Retrieved text should support a dated claim, not become executable policy merely because a model read it.

The future execution loop can start small:

```text
compile mandatory coverage and bounded optional hypotheses
  -> search required endpoint markets
  -> normalize and validate observations
  -> inspect promising results / activate selected optional work / ask / stop
  -> report observed options and remaining uncertainty
```

The first implementation can use deterministic actions and stopping rules. Later compare a bounded model controller using the same allowed actions and budgets. It may adapt search order or choose additional evidence to request; it may not relax a hard constraint, manufacture inventory, or silently authorize positioning.

Do not make the first useful result wait for every optional hypothesis. Once endpoints are selected, baseline execution and optional discovery could later overlap, with immutable plan extensions or separate work batches. The roughly sixteen-second median recorded 2B generation-trial latency makes this worth measuring after integration. It is an execution scheduling opportunity, not a reason to introduce asynchronous orchestration into 2C now.

This also provides a better basis for clarification. A missing preference need not always block the first search. After evidence arrives, ask the question whose answer would materially change the next search or shortlist—for example whether a separate positioning trip is acceptable. Mandatory safety/scope requirements still block as declared. Evidence-driven questions should be compared with the current all-blockers interaction rather than introduced as an unmeasured universal rule.

Eventually, points access becomes part of relevance. A technically valid award may be useless to a traveler who cannot access its program. Add the smallest supported transfer/program eligibility check when real shortlisted options require it. Avoid claiming cross-program value from raw mileage numbers or assuming that a user can transfer points; preserve program, taxes, and eligibility as separate facts. This is a later product requirement, not a reason to expand 2C into financial or loyalty research.

Batching and concurrency belong primarily in the provider adapter. If an airport-list request expands a sparse logical pair set into extra cross-product pairs, those extra searches need deliberate accounting; batching is not automatically semantics-preserving. Pagination, partial responses, and trip-detail work need their own execution ceilings and coverage reporting.

## 8. Experiments that would change the design

| Question | Small comparison | Decision it informs |
| --- | --- | --- |
| Do gateways help? | Mandatory queries alone versus mandatory plus 2B-derived supplements on the same bounded saved/live evidence window | Whether optional planning earns its work |
| Are model proposals better than a simple baseline? | 2B versus a small reviewed gateway policy with equal query budget | Whether model reasoning adds useful coverage |
| Does an adaptive controller help? | Fixed optional order versus bounded model choice over the same evidence and budget | Whether agentic execution is worth extra latency/cost |
| Do higher airport caps help? | Smaller and larger endpoint selections with comparable total work budgets | 2A cap/adoption decisions |
| Does a separate composer help users? | Current composer versus structured blocker copy | Whether the extra call improves task completion |
| Is RAG useful here? | Structured-only versus targeted retrieval on specific rule-dependent explanations | Whether to open the RAG authoring milestone |

Separate two measures: the first pilot can assess useful observations per unit of work; actual gateway journey lift requires validated complete options. Two promising hub components are not a shortlist addition. Use the same maximum budget, not forced equal consumption. Label fixtures as replay evidence and control live timing/caching where practical; changing inventory prevents an automatic fair counterfactual. Keep development examples separate from holdouts.

Set an end-to-end call and latency budget, not only per-component caps. If a fair provider-backed comparison shows no useful lift from runtime 2B, remove it from the default path or restrict it to the cases where it helps. Keeping an unsuccessful model feature merely to demonstrate more LLM use would weaken the portfolio story.

The same-market skip also deserves a later false-negative audit. It is an intentional cost policy, not proof that supplemental searches have zero value within a market. Preserve the current approved 2B mechanism during 2C; evaluate a possible policy revision using results rather than reopening the prompt because a hypothetical example sounds plausible.

## 9. Recommended sequence

1. Choose one reviewed O/D pair, bounded dates, cabin, travelers, and the exact output claim. Walk through a labeled mock/replay output with the owner before full 2C qualification. Existing provider access is evidenced; the missing questions are trip-detail/error semantics and required artifact acquisition. A targeted provider-contract experiment needs separately opened scope; no provider calls belong inside 2C.
2. Implement and qualify deterministic 2C on frozen inputs, within existing endpoint budgets, with explicit positioning/date obligations.
3. Run a small provider pilot: baseline plus one access alternative and one supplied hub record. Validate provider-returned options; show unsupported positioning and hub components only as research leads. No automatic cross-query assembly.
4. Walk the owner through that output immediately; later observe a consented user. Measure usefulness, remaining manual work, and integration failures before broadening the slice.
5. Address demonstrated upstream/constraint gaps and compare supplemental evidence against baseline. Claim completed-journey lift only after the relevant assembly is supported and validated.
6. Add component assembly, adaptive control, retrieval, or broader coverage only where observed gaps justify them.

The roadmap already gives M3 a comparative decision gate and makes M4 evidence-driven. The proposed change is earlier provider/user feedback, ahead of those knowledge-base experiments—not adding conditionality absent from the original plan. The owner has not yet adopted this sequencing change or opened provider implementation.

### Choices made in this review

The independent architecture reviews did not agree on every detail. The parent recommendation resolves three consequential alternatives as follows:

| Alternative | Parent recommendation and reason |
| --- | --- |
| Allow 2C to trim model-selected endpoint pairs | Preserve all-selected-pairs coverage and existing typed overflow. Use admitted pilot sets; consider upstream budget admission only when broad selection utility is evaluated. |
| Restrict hub-side queries to nonstop components | Keep query semantics explicit, but defer cross-query assembly. Return hub evidence as research leads; decide assembly restrictions from a useful concrete case. |
| Encode a complete result-dependent execution policy in 2C | Record phase and permission conditions now; leave sufficiency, activation, and stopping to the future executor. They depend on a result contract that has not yet been implemented. |

These choices keep the initial implementation bounded while making the unresolved downstream obligations explicit. They are recommendations for owner review, not consensus presented as fact.

## 10. Review evidence and limits

This review used four independent subagents: a deep architecture review, a compiler architecture review, upstream investigation, and quantitative 2B evidence investigation. The parent integrated the recommendations and inspected product intent, current documentation, code, provider references, and selected behavior directly.

Parent verification performed:

- `.venv/bin/python -m award_agent.cli.search_planning_eval`: **10/10 passed**.
- `.venv/bin/pytest -q tests/unit/test_search_planning_endpoint.py tests/unit/test_search_planning_paths.py tests/unit/test_search_planning_grounding.py tests/unit/test_search_planning_evaluation.py tests/unit/test_gateway_discovery.py tests/unit/test_gateway_generator.py`: **134 passed**.
- A read-only Python probe reused the synthetic path fixture and changed only `repositioning_allowed` across false, null, and true. All three returned the same three mandatory probes, one path, and five award items. This demonstrates existing policy behavior only, not real connectivity.
- Read current official Cached Search/Get Trips documentation. No authenticated inventory call or paid model evaluation was run by the product.

The upstream investigator additionally ran `.venv/bin/pytest -q tests/unit/test_intent_semantic.py tests/unit/test_clarification_controller.py tests/unit/test_clarification_openai_interpreter.py tests/unit/test_one_way_award_live_eval.py tests/unit/test_one_way_award_clarification_eval.py`: **46 passed**. The quantitative investigator used read-only Python aggregation of the public evaluation records and immutable record sidecars; this was an analysis of existing evidence, not a new model evaluation.

The compiler architect ran `.venv/bin/pytest -q tests/unit/test_search_planning_endpoint.py tests/unit/test_search_planning_paths.py tests/unit/test_selector_workflow_integration.py tests/unit/test_gateway_discovery.py tests/unit/test_gateway_generator.py tests/unit/test_market_policy.py`: **111 passed**. This overlaps the parent's focused suite and is not an additional independent 111-case denominator. All 15 local Markdown links in this document were checked for existing targets. Whitespace checks were applied to both new files, including their untracked contents.

No implementation, catalog, prompt, fixture, workbook, or approved runtime policy was changed by the initial review. The saved review and its build-log entry are advisory artifacts. Tests establish existing deterministic behavior; they do not establish travel usefulness, human semantic qualification, or provider execution correctness.

## 11. Engineering evidence for FDE recruiting

Added after a second inspection on 2026-09-19. This section evaluates engineering proof, not just future features. Three investigators reviewed engineering tooling and the accumulated deferrals; the parent performed the portability and transport-retry experiments and made the recommendations below.

### The engineering claim to optimize for

The strongest eventual claim is: **I took an ambiguous user workflow, integrated imperfect external systems, measured its behavior, made failures diagnosable, and handed over something another engineer could run and change.** A repository with sophisticated internal contracts proves only part of that statement.

This emphasis is consistent with the current official [OpenAI FDE role description](https://openai.com/careers/forward-deployed-engineer-%28fde%29-seattle-seattle/), which emphasizes end-to-end delivery, measurable workflow impact, scope/speed/quality tradeoffs, and reusable tools and handoffs. It is a useful reference, not a universal hiring rubric or a prediction of recruiting outcomes.

The workbook says the owner already has credible full-stack, data-pipeline, and engineering-ownership experience. Therefore this project should spend its scarce time proving the additional AI-system judgment: where model behavior breaks, how tools and evidence contain those failures, and whether the resulting workflow helps someone. Adding infrastructure keywords without a demonstrated requirement has low evidentiary value.

### What already constitutes strong engineering evidence

- **Data integration with explicit loss accounting.** The catalog publication pipeline preserves source identity and full retained payloads, quarantines conflicting evidence, validates digests/foreign keys, and publishes atomically. The lossless replacement's build log records 1,810,402 retained raw records and 3,244 retained OurAirports rows with zero full-payload mismatches. This is documented local data-engineering evidence, not a new benchmark or production traffic claim. [Catalog closeout](../build-log/2026-09-15-m1a-catalog-publication.md#retention-correction-and-milestone-1b-closeout-2026-09-16).
- **A reasoned response to a real data-performance problem.** The same log records an unindexed raw-evidence lookup, the addition of a matching source-record index, and deferral of another index until after bulk loading. That is a stronger backend story than merely saying “used SQLite.” There is no recorded comparative timing here; do not invent a speedup.
- **Untrusted model output has an enforceable boundary.** Typed proposals, grounded spans, immutable state, candidate caps, replay bindings, and adversarial tests demonstrate that a model cannot simply publish its own facts or rewrite accepted state.
- **Failures are documented honestly.** The archive retains failed semantic diagnostics, the v5 relationship-multiplication finding, and the distinction between offline correctness and human qualification. That can support a credible engineering learning story if the owner can explain the decision and limitations.
- **Observability captures actual contracts.** Model traces include adapter/schema identities and exact opt-in local I/O; public artifacts are separated from private traces. This supports diagnosis without pretending raw model rationale is a proof of correctness. [Trace implementation](../../src/award_agent/observability/llm_trace.py).

These strengths should be demonstrated with one representative failure and its evidence, rather than buried under every historical experiment. The [evidence ledger](../evidence-ledger.md) is still a placeholder; a small current-claims index would expose real strengths already earned.

### Finding A: local reproducibility has not yet become a handoff contract

The parent exported tracked `HEAD` into a temporary directory with `git archive`, then ran the planner golden CLI using the already-installed virtual environment and the exported `src` directory. It failed at capability-source verification:

```text
ValueError: capability source 'seats-aero-cached-search-local-2026-09-08'
does not name a local regular file
```

The capability record points to `.provider-docs/seats-aero/cached-search.md`, which is intentionally ignored. The local ten-case gate passes because those bytes exist here; the tracked export lacks them. This establishes a portability failure in that qualification command, not that every planner entry point is unusable. It did not test fresh dependency installation, wheel installation, or full catalog import.

The hash check is doing its job. Removing it would make the demonstration easier while weakening the evidence. Instead, define how a reviewer acquires the exact required artifacts. A small redistribution-permitted snapshot, a content-addressed artifact bundle, or a checked bootstrap step with exact digests can work. Fetching whatever a mutable URL returns today cannot reproduce an old pinned snapshot. Keep large raw sources optional for the small demo, and distinguish seed-fixture mode from the full reviewed catalog.

There is no tracked dependency lock or CI workflow. `pyproject.toml` has version ranges, and the schema receipt uses SDK conversion behavior. That combination makes dependency identity relevant to replay: even unchanged application source does not guarantee identical wire schemas under another allowed dependency version. Add a tested application/development environment lock and an environment fingerprint to reproducible evaluation runs; this does not require rigidly pinning every library consumer through package metadata.

**Proof to build:** a fresh checkout, plus any documented permission-checked artifact bootstrap, reproduces a small offline scenario without private credentials, ad hoc source copies, or private traces. The run itself is offline. CI can later run the same command; a second engineer should eventually perform the handoff without undocumented instructions or path edits.

### Finding B: semantic bounds do not compose into operational bounds

The default initial-intent, clarification, composer, endpoint-selector, and gateway adapters construct `OpenAI()` when no client is injected. None of those constructors declares its own retry or timeout policy. The installed SDK in this review was version `1.109.1`.

An offline `httpx.MockTransport` returned synthetic 429 responses. One `responses.create` invocation produced **three HTTP attempts** before `RateLimitError`. The default client reported `max_retries=2` and `Timeout(connect=5.0, read=600, write=600, pool=600)`. No network or real model was used. These observations describe this installed SDK and default client path, not every injected client or actual calls in the earlier live diagnostics.

The existing “one proposal call” rule remains a legitimate semantic bound. It is not a promise of one HTTP attempt or a short user wait. Likewise, a bounded semantic repair, several provider pages, and parallel branches can each obey local rules while the total workflow exceeds its budget. A per-operation read timeout is also not an end-to-end deadline.

**Proof to build:** for the first live integration, explicitly configure finite retries/timeouts, cap pages, and expose exhausted/partial outcomes. Before promising a bounded end-to-end workflow, carry a request deadline and remaining work budget across repairs, transport attempts, and branches; test cancellation and partial success. This is incremental hardening, not a demand for a general execution controller before a limited pilot. No distributed job framework is needed.

For read-only searches, avoid promising literal exactly-once remote execution: after a transport timeout the service may already have processed the request. Track logical queries and attempts, make local result ingestion idempotent, and explain the remaining remote uncertainty. That distinction is better evidence of engineering judgment than adding an unsupported “idempotency” checkbox.

### Finding C: quality gates need a coherent active target

The engineering investigator ran the documented tools:

| Command | Observed result in this inspection |
| --- | --- |
| `.venv/bin/ruff check .` | Passed |
| `.venv/bin/mypy src tests` | Failed: 266 errors in 14 files |
| `.venv/bin/mypy src` (parent follow-up) | Failed: 49 errors in 6 files; 96 source files checked |
| `.venv/bin/ruff format --check .` | Failed on existing formatting drift; no new exact file count claimed |
| Full `.venv/bin/pytest -q` | Two runs were started by the investigator, but no terminal result was recovered; no pass count claimed |

The errors are not only historical tests: the source-only run also fails in three legacy temporal modules and three evaluation modules. An AST scan found no static imports of those temporal modules within `src`, but this is not proof against dynamic loading or a reason to dismiss active evaluation errors. A pytest skip does not remove files from mypy. Formatting is not a declared stage gate; the documented type-check command does fail. Neither finding by itself proves a runtime defect.

The parent later checked process status and found no remaining pytest process. That does not recover the runs' exit codes. The 507-pass/99-skip full-suite result in the 2B build log remains prior recorded evidence, not a verified result of this second inspection.

**Proof to build:** declare one active verification target and make it green. Preserve retired experiments in an explicitly historical lane or tagged artifact rather than allowing them to obscure the active package's health. Do not hide active errors under blanket exclusions. Freeze one formatter convention when it is useful, without turning this review into an unrelated repository-wide formatting change. A smaller trustworthy gate is more useful than a larger ambiguous test count.

### Six engineering demonstrations worth building

| Demonstration | What a reviewer should be able to observe | Why it is stronger than another feature |
| --- | --- | --- |
| **1. Handoff from a clean checkout** | One documented offline command succeeds with pinned dependencies/artifacts; seed and real-data modes are clearly labeled | Proves the work is transferable beyond the original laptop |
| **2. A provider breaks mid-request** | A synthetic timeout, 429, truncated page, malformed field, or stale observation produces bounded recovery and a truthful partial/failed outcome | Proves integration ownership under imperfect external systems |
| **3. Explain one inclusion and one exclusion** | Request revision → selection → gateway hypothesis → query → attempt → observation → validation → output, with source/version links | Proves the system can diagnose its own decisions, including negative decisions |
| **4. Replay a bug without paying for new inference** | Pin the model proposal and provider fixture, rerun deterministic stages, change one stage, compare the resulting behavior | Separates model variability from application regressions and makes fixes reviewable |
| **5. Remove a feature that does not help** | Compare mandatory-only and supplemental search under matched budgets; keep, narrow, or remove supplements based on useful result lift | Proves evaluation changes architecture instead of decorating it |
| **6. Handle one small requirement change** | A new supported provider field or filter has a bounded change surface and focused regression evidence | Proves maintainability and adaptation without requiring a speculative plugin framework |

These are options, not six new completion gates. Select one first: the narrow provider pilot, with one retry-exhaustion fixture and one preserved-partial-result fixture. Existing replay seams and typed interfaces provide the foundation; a per-run evidence bundle can show lineage without a permanent event database.

For the provider simulator, use synthetic or permitted sanitized payloads. Include distinctions with real product consequences: unknown seat count versus zero seats, unavailable versus not searched, no result versus failed query, and stale data versus fresh absence. A happy-path response serializer alone will not prove those semantics.

For test design, prefer properties that survive implementation changes: mandatory coverage is preserved under optional failure; increasing a budget does not silently discard the baseline; equivalent ordering does not change semantics; stale revisions cannot execute; unverified evidence never becomes a verified claim; duplicate delivery cannot duplicate a final option. Add a few adversarial cross-stage trajectories. More tests that only mirror Pydantic field definitions would add little evidence.

### The FDE-specific gap: delivery to another person

The portfolio has strong self-directed development evidence, not customer adoption evidence. Bring an owner walkthrough into the first narrow provider pilot, then observe a few consented users when an appropriately safe artifact is shareable; do not wait for every stage to finish. Record their intended task, needed help, remaining work, and what changed because of feedback. A small candid usability record is useful; it is not enterprise ROI evidence.

The same principle applies to technical handoff. Ask another engineer to run a supported scenario and diagnose an injected failure using only the repository. Capture missing setup steps, confusing state, and unexplained errors. Fix those specific failures. This tests the ability to leave a maintainable system with someone else, which an architecture diagram by itself cannot establish. No outreach is authorized or performed by this recommendation.

Because implementation is AI-assisted, the owner's strongest interview evidence is a decision they can defend: what was rejected, what data changed their view, which invariant matters, and what would break if it were removed. Select one catalog reconciliation issue and one model/provider failure for that explanation. Build logs should continue to distinguish generated implementation from owner-made decisions rather than inventing authorship.

### What to improve now, and what should remain parked

**During 2C and the first integration:** preserve replay/provenance, explicit attempt limits, and focused cross-stage failure tests. Check artifact acquisition early. Observe the owner using the first output. A limited local preview does not require a whole-repository cleanup, CI, or a permanent database; a clean-checkout handoff claim does require a reproducible command and truthful passing gate.

**After the pilot exposes real gaps:** expand the value comparison, handoff exercise, and focused upstream simplification. Automatic component assembly needs its own usefulness and validation case. Broad coverage, extra providers, RAG, permanent persistence, and adaptive control remain conditional. Public deployment is optional and must not be implied by a local demonstration.

**Do not add for optics:** microservices, multi-agent product orchestration, a vector database, Kubernetes, or a second provider merely to lengthen the technology list. An engineer who can explain why a simple design meets measured requirements has a stronger story than one who cannot justify the system's complexity.

The parent judgment is that **evidence portability and bounded failure handling are now higher-value engineering investments than further prompt refinement**. The repository already has enough architectural depth to support a strong story. It needs an integrated result, a reproducible demonstration, and proof that someone else can operate and understand it.

### Second-inspection artifacts and limits

- Added [DEFERRED.md](../../DEFERRED.md), with stable IDs, sources, revisit triggers, evidence required for closure, and separate pre-claim gates. No parked feature is approved merely by appearing there.
- Added maintenance/discovery pointers in root instructions, README, project state, and workboard. Historical architecture prose was not broadly rewritten, and runtime code was not changed.
- Recorded commands, experiments, and remaining failures in the [engineering-review build log](../build-log/2026-09-19-fde-engineering-review.md).
- The temporary tracked export was `/private/tmp/award-search-fde-review.kmgdKr`, created from `HEAD`; it contained no ignored provider reference, raw catalog, or private trace copies. The existing virtual environment was reused, so this was not a clean dependency-install benchmark.
- The transport probe used a placeholder key, injected in-process HTTP transport, and synthetic responses. It establishes installed default retry behavior, not a measured production outage.
