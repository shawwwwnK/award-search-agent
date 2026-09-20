# Future stage goals: from plausible searches to useful decisions

Date: 2026-09-19. Status: **advisory proposal requested by the owner; no stage is opened or policy adopted.**

Revised after an owner-requested fresh-context Astra challenge and substantive back-and-forth.
The [debate record](../build-log/2026-09-19-future-stage-astra-challenge.md) identifies accepted
challenges, qualified disagreements, and the resulting changes.

Read this when scoping 2C or any subsequent stage. The [active roadmap](../handoffs/2026-09-13-search-planning-milestone-roadmap.md) remains authoritative for approved sequencing. [DEFERRED.md](../../DEFERRED.md) remains the single register of parked work and claim prerequisites. The [earlier architecture review](2026-09-19-search-planning-architecture-review.md) supplies detailed compiler and engineering findings; this document proposes the goals and decision gates those implementations should serve.

## 1. The central change I recommend

**Organize the next stages around reducing the traveler's remaining decision work, with an explicit budget for acquiring and checking evidence.** Compiling more searches, integrating an API, retrieving documents, and ranking results are means to that end. Each stage should prove that it resolves a particular uncertainty, and have a legitimate outcome in which we simplify or abandon its proposed mechanism.

The current investment has produced strong control over how a model's proposals enter software. It has not yet established an advantage over the owner's existing search tools and manual workflow. My revised recommendation is a **time-boxed task comparison followed by a narrow provider/result/output slice**, ahead of full supplemental 2C automation, M3 RAG, and broad M4 expansion. Reviewed, manually translated search bundles can test supplemental value before we automate their compilation. A useful baseline may justify finishing a smaller product; prior investment in 2B does not obligate us to automate every proposal it can express.

This is a stronger sequencing alternative than simply building the pilot alongside 2C. The current roadmap still requires full 2C's declared scope. Postponing or narrowing it requires an owner decision; the review does not silently change that commitment.

Proposed first complete product promise:

> For a declared subset of one-way award requests, produce a small set of source-linked observed options, explain which requirements the evidence supports, and show the remaining checks and search coverage within a bounded effort budget.

This deliberately leaves room for an honest empty or partial outcome. It does not promise booking, comprehensive availability, or personal redeemability without supporting evidence. The workbook's broader round-trip/cash example is superseded for the active scope by [ADR 0016](../adr/0016-one-way-award-request-boundary.md); its underlying goal—less manual coordination and a credible shortlist—still guides this proposal.

**Truthful output is necessary but does not establish product value.** Joint completion should require at least one predeclared, owner-relevant task yielding an evidence-supported option the owner selects for a concrete next check, with less total owner effort than the existing workaround. Count query formulation, comparison and remaining verification. An unresolved must-have cannot be waived to manufacture that positive example. Correct empty/partial handling is additional required behavior, never a substitute for this capability demonstration. Report every pilot task; one success proves neither reliability nor broad improvement.

## 2. What our own history teaches us

| Implemented evidence | Engineering lesson | Consequence for future stages |
| --- | --- | --- |
| Initial intent moved from scanner/candidate selection to grounded model semantics plus deterministic generic calendar operations | Determinism is most useful for enforcing meaning after interpretation; enumerating language patterns can become the wrong abstraction | Keep models where interpretation is needed. Do not make the planner or adapter a second parser of free-text requirements. |
| The historical 57-run intent diagnostic largely failed at the structured proposal boundary; the subsequent wire correction and narrow 10/10 gate did not establish broad qualification | A schema/adapter defect can look like weak reasoning; a successful narrow repair does not prove general behavior | Diagnose interpretation, wire translation, deterministic acceptance, and user outcome separately. Do not respond to every integration failure with prompt tuning. |
| M1 established catalog identity and retained source evidence; M2A still requires semantic qualification/adoption | An airport's existence is much easier to prove than its suitability for a request | Carry suitability and adoption status forward. Do not let downstream execution silently qualify upstream choices. |
| M2B v5/v3 produced 731 accepted relationships; v6/v3 produced 400, despite small candidate pools | Fanout crosses stage boundaries; a local cap is not an end-to-end budget | Budget queries, attempts, details, verification, and human review—not just proposed airports. |
| M2B closure accepts the mechanism and diagnostic record, without human semantic qualification or verified connectivity | Stage closure, structural correctness, semantic quality, and product value are different claims | Give every next stage its own evidence claim and denominator; never inherit a stronger claim from a predecessor's closure. |
| Existing planner caps include 25 endpoint pairs and 40 search items; 2A's active US country cap is 10 | Independently reasonable component policies can be incompatible when composed | Test the supported input envelope across stages before increasing selection breadth. |

Sources: [current state](../project-state.md), [ADR 0017](../adr/0017-llm-owned-initial-intent-semantics.md), [2B closeout](../handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md), [planning policy](../../src/award_agent/search_planning/policy.py). These are existing observations, not new evaluations conducted for this proposal.

The deeper lesson is **to match evidence strength to the consequence of an action**. A weak but plausible gateway hypothesis may justify a cheap exploratory query. It cannot justify silently expanding the user's trip or presenting a completed itinerary. Requiring route-level certainty before every query wastes useful hypotheses; accepting query-level plausibility as recommendation evidence misleads the traveler. The architecture should support both exploration and strict claims by keeping those thresholds separate.

## 3. Proposed stage map

The letters below identify proposed work packages, not newly approved milestone numbers. Provider, validation, and output are separate responsibilities but should be exercised together in one small vertical slice.

| Existing or implied stage | Revised goal | Evidence that would close the proposed stage |
| --- | --- | --- |
| **M2C: strategy compilation** | Automate search strategies whose value justifies their work, with truthful coverage and replay | First establish value with reviewed bundles; if opened, qualify deterministic compilation and faithful scopes under the owner-selected coverage contract |
| **P: provider integration/execution** | Establish exactly what one provider can observe, and acquire those observations under finite limits | Accepted semantics plus success, empty, partial, stale, malformed and exhausted-attempt behavior |
| **V: normalization and validation** | Decide which statements each observation supports for this request | Evidence-linked requirement checks; uncertain and incomplete observations remain distinct from satisfying options |
| **U: shortlist and explanation** | Help the user make a concrete next decision with less total effort than the current workaround | Predeclared task rubric, positive actionable-option demonstration, transparent tradeoffs and measured remaining checks; empty/partial behavior is additional evidence |
| **M3: reviewed knowledge/RAG** | Resolve a demonstrated knowledge gap that changes a decision or reduces authoring effort | Source-supported improvement over a small structured/lexical baseline; a valid decision to omit RAG |
| **M4: coverage expansion** | Increase useful task coverage at an acceptable maintenance and search cost | A named demand/failure cohort improves after a bounded addition, with regression and provenance evidence |
| **A: optional adaptive control** | Choose the next useful observation, clarification, or stopping action better than fixed ordering | Matched-budget improvement over a deterministic controller with no authority or constraint violations |
| **H: handoff/delivery** | Make the declared workflow usable and diagnosable by another person | Reproducible supported run and one diagnosable failure; deployment only if a delivery need warrants it |

Proposed order: **declare a few owner tasks and benchmark the current workaround → narrow P/V/U slice → test frozen reviewed supplemental bundles → finish the small product or automate the strategy family that earns its cost.** H's setup and evidence needs should be checked during the pilot. M3, M4 and A remain possible responses to observed gaps, not a mandatory completion ladder. A mock walkthrough can help design U but cannot establish real task value.

## 4. Sharpening each stage

### M2C — make search effort intelligible and affordable

The compiler's goal should be more precise than “expand the gateways.” It should explain why each unique query exists, what it costs in the declared planning units, and which useful hypothesis cannot be investigated within the budget. Keep it deterministic and model-free. Under the proposed sequence, implement supplemental strategy families only after reviewed query bundles show useful incremental value; that tests the strategy without prematurely building the full compiler.

Preserve the distinction between a strategy, a logical query, a provider request, and an observed option. Two strategies can share one query; an adapter may batch queries or paginate a request. A smaller API-call count does not establish less logical work or complete result coverage.

**Treat the baseline coverage guarantee as a product decision.** For illustration, ten selected origins and three destinations imply 30 mandatory endpoint pairs, above the current 25-pair limit. This is arithmetic, not an observed failing evaluation case. Supplemental pruning cannot fix it. The current compiler correctly returns an over-budget outcome under its all-selected-pairs contract; preserve that behavior until a replacement is approved. But rejecting a broadly flexible request because of an internal cap is not my recommended long-term product goal.

At next-cut design, use a bounded provider-capability check to choose between exhaustive selected-pair coverage and a versioned progressive-search contract. The latter would expose admitted, attempted and omitted pairs, selection rationale, and completeness explicitly. Distinguish airports the user specified from alternatives proposed by the system; neither may be quietly rewritten, but they need not have identical scheduling priority. Audit which flexible choices get starved. Canonical ordering makes an allocation reproducible, not useful. Logical-pair caps and provider transport costs also need separate justification. No partial plan may impersonate the existing exhaustive contract.

For supplements, preserve accepted 2B applicability rather than inventing a new Cartesian product. Deduplicate on complete query semantics, retain every supporting strategy link, and carry access/hub dependencies. A budget omission is a compiler choice, not retrospective invalidation of the candidate. Keep route-backed `ExplicitPathHypothesis` separate from model-proposed hypotheses, as [ADR 0020](../adr/0020-market-aware-model-proposed-gateway-candidates.md) requires.

Separate authority to research from willingness to take the proposed trip. My recommended initial policy is: false excludes strategies requiring positioning, while preserving any shared query needed by another eligible strategy; unknown can permit bounded read-only research within an already authorized cost budget, but cannot establish shortlist suitability. True positioning does not imply separate-ticket tolerance, acceptable extra travel time, overnight tolerance, or feasibility. An evidence-driven preference question may be useful; unknown preference alone need not create another tool-approval barrier. This proposes a replacement for the fixture policy, whose receipt says it does not consume `repositioning_allowed`; it requires an explicit design decision before integration.

**Completion evidence if opened:** frozen requests/selection records, zero model/provider calls, stable output under incidental reordering, preserved admitted baseline under optional failure, explicit cap conflicts, shared queries, and dependency cases for every claimed strategy family. The currently approved contract still requires every selected pair. A progressive replacement would require its own completeness and omission tests. Test long date windows as well as the short diagnostic fixtures. Keep future activation metadata minimal; do not build an executor inside the compiler.

### P — buy observations whose meaning we understand

An HTTP 200 is insufficient as this stage's success criterion. The earlier [provider spike](../provider-feasibility/2026-09-08-initial-provider-intake.md) already demonstrated narrow authenticated access, but discarded the full response after preserving a sanitized summary. It is not a complete normalization fixture or semantic acceptance test.

Begin with one supported provider operation, explicit airports, a bounded date window, and a narrow declared result claim. Verify date boundaries, cabin semantics, program-specific fields, pagination, missing versus zero seats, and detail availability before relying on them. Record provider observation time separately from retrieval time: fetching a cached record now does not make its underlying observation fresh.

Maintain a simple coverage record: planned, attempted, completed-empty, completed-with-results, partial, failed, and omitted. Here “completed” means the admitted provider query/page scope was exhausted—not that all awards in the market were searched. Missing inventory may reflect provider coverage, cache age, filters, or a truncated response. The system can establish “nothing matching was returned in this searched scope”; it generally cannot establish “no award exists.”

Enforce explicit attempt, page, detail-fetch and deadline limits. Preserve completed observations if another branch fails. Recheck request revision before execution and before attaching results to the current request. Local ingestion should tolerate duplicate delivery; a timeout does not prove the remote service never processed the call.

**Component acceptance:** offline replay fixtures for meaningful outcomes and one bounded real integration record. Include a page failure after earlier results, unknown seat evidence, and a stale record. A baseline result should flow all the way into U during this stage, avoiding a large adapter developed without a consumer. These checks establish integration behavior, not whole-product completion; the joint positive-task condition still applies.

### V — turn observations into bounded claims

This stage is more than field normalization. It owns the transition from “a provider returned this” to “this supports a particular travel claim.” Make requirement checks explicit: satisfied, violated, unknown, or not applicable, with the evidence behind each. A prose caveat cannot compensate for labeling an unchecked hard requirement satisfied.

Keep separate dimensions for provider freshness, requested-seat evidence, cabin evidence, chronology, endpoint fit, and unresolved travel dependencies. Do not collapse them into an invented confidence percentage. A fresh one-seat record cannot support a two-traveler option; unknown seats must not become either zero seats or sufficient seats. Free-text hard requirements remain unresolved until the separately scoped typed contract can represent and enforce them.

**Preserve provider-returned itinerary boundaries in the first slice.** An O→D search can include connections: the official Cached Search interface exposes a separate direct-flight filter and optional trip details. Consequently, adding O→H and H→D queries is not simply recovering ordinary connections omitted by the baseline. Their results may be independent components needing a new journey contract. [Official Cached Search reference](https://developers.seats.aero/reference/cached-search).

The date trap deserves its own test. A G→D award departing Friday does not prove that a traveler who can leave O only on Friday can reach G in time. Likewise, two individually valid hub components can fail chronology or require an unacceptable overnight. The existing exploratory date envelope is a search convention, not a connection validator. Access and hub results remain labeled research leads until their full obligations are discharged; no automatic cross-query assembly in the first pilot.

**Completion evidence:** a claim matrix with traceable checks, rejected and unknown cases, timezone/date-boundary examples, mixed-cabin cases, and incomplete component cases. Closing V for intact provider itineraries does not close [D15](../../DEFERRED.md)'s component-assembly scope.

### U — reduce decision work before optimizing a ranking formula

Start with a readable comparison and an explicit next step. The owner should be able to tell why an option appears, which tradeoff it makes, what is unknown, and what remains to check. Do not force a fixed number of options or blend incomplete research leads into a ranked list of satisfying itineraries.

Use deterministic feasibility filtering and transparent comparisons first. Dominance can remove an option only on comparable known dimensions; unknown fees or different loyalty currencies prevent casual “cheapest” claims. A Pareto shortlist or a few user-selected sort orders can be more truthful than a universal weighted score. Personal ranking needs actual preferences and program access; mileage amounts alone do not establish personal value.

The pilot needs enough user context to judge usefulness even if a points wallet remains deferred. Before seeing results, record supported must-haves, unknowns that would disqualify an option, usable programs or explicit willingness to investigate another program, acceptable remaining checking effort, and the concrete decision to enable. The owner can supply this task context manually; this does not require a new parser or automated points profile. If the promise becomes “you can redeem this,” minimal eligibility and transfer evidence become prerequisites. Merely calling an unusable option an observation does not make it useful. [D06/G03/G04](../../DEFERRED.md) capture the scope boundaries.

Generate explanations from checked records, not by asking a model to re-evaluate raw provider prose. Templates may suffice initially. If an LLM improves readability, require every factual assertion to be supported by those records and forbid promotion of research leads into completed options. External descriptions and retrieved documents are data, not authority to alter the request or call new tools.

**Completion evidence:** compare the owner's current provider/manual workflow and the pilot on the same predeclared task rubric. Record total effort, time to a first relevant option, remaining checks, rejection reasons, and the concrete next action. Selecting a supported option for a named final check is evidence; “looks plausible” and generic advice to check the airline are not. Utility judgment remains partly subjective—make it inspectable. Include no-result and partial-result tasks, and every failure in the report. Predeclare what improvement would justify continuation without inventing a statistical threshold from a tiny pilot.

### M3 — make knowledge answer a demonstrated decision gap

The existing roadmap already limits M3 to human-reviewed strategy authoring and requires a useful comparison. Keep that discipline, but change its timing and sharpen the question: **which decisions are failing because necessary source knowledge is absent?**

Do not use document retrieval to decorate a gateway idea with a citation. Source relevance is not support for the exact claim, and a historical trip report does not establish current service or inventory. A useful first authoring task could be extracting a strategy's applicability, exceptions, date and source passage for human review—if pilot failures demonstrate that these conditions are missing.

Separate that authoring experiment from runtime loyalty-rule retrieval. They have different users, freshness needs, and acceptance criteria. A runtime rule should state its scope, effective/retrieved dates, source, exceptions and unresolved conflicts; code still performs the arithmetic. Current inventory remains provider evidence.

**Completion evidence:** start with a small structured fact/decision table, then lexical retrieval, then hybrid retrieval only if retrieval failures justify it. Measure supported decisions, missed conditions, conflicting-source handling, review time, cost and latency. If ten reviewed records solve the gap, stop there. “No RAG needed for this workflow” is a successful architectural conclusion, not an incomplete stage. This refines [D07](../../DEFERRED.md), without opening it.

### M4 — grow useful task coverage, not catalog size

Move gap recording into the first pilot; keep broad expansion conditional. Distinguish identity, endpoint suitability, provider inventory coverage, unsupported requirements, missing rule knowledge, and evidence freshness. Adding geographic entities will not fix a provider blind spot. Another provider will not fix a misunderstood date.

Prioritize a gap by the requests it blocks, the consequence of the failure, how likely an addition is to help, and its ongoing review/search cost. Do not turn this into a falsely precise score before data exists. A severe correctness problem can outrank a frequent convenience gap.

For each addition, name the failed task it should unlock, compare before/after behavior, and inspect the extra fanout it creates. Expanding country airport sets can increase “coverage” while decreasing useful results per budget. Sometimes the right expansion is a better selection policy, a clearer supported boundary, or removal of weak alternatives.

**Completion evidence:** one declared cohort improves, new evidence is reviewable, omissions remain explicit, and regressions/cost are measured. A global route database is not a universal prerequisite: the older planning notes' route-first language has been superseded for gateway proposals by ADR 0020. Acquire route evidence only for a claim or filtering task that actually requires it.

### A — earn autonomy through better next actions

The strongest later agentic opportunity is selecting what to learn next after results arrive. Start with a deterministic controller; compare a model only when fixed ordering leaves a measured gap. Give it a finite vocabulary such as inspect details, activate an eligible supplement, ask a supported clarification, or stop. Code enforces permissions, current request identity, remaining budget, and allowable transitions.

A useful action should either reveal a relevant option or resolve uncertainty that changes a decision. Repeatedly searching because no satisfying answer appeared is not progress. Reserve some effort for checking promising observations; a controller that spends everything discovering candidates may finish with nothing supportable.

A consequential experiment is **delaying optional gateway generation until baseline observations suggest it is useful**. M2B currently mandates one grouped call whenever its valid input passes the generation gate. Delaying whether/when that stage is invoked could reduce planning latency without changing its internal semantics, but changes the surrounding workflow and needs an explicit policy decision. An empty baseline is only one activation signal; unsuitable or weak baseline options may justify exploration too. Do not implement lazy invocation silently in 2C.

**Completion evidence:** equal-budget comparison to fixed ordering, bounded stopping, revision-safe clarification, and useful evidence gained per action. No gain means retain the deterministic controller. This applies agent design where feedback matters, without product-level multi-agent orchestration. [D09](../../DEFERRED.md) remains conditional.

### H — make the workflow transferable

A local demonstration can be valuable. A claim that another engineer can reproduce it needs exact dependencies/artifacts, one documented supported command, declared replay/live modes, and a usable failure trace. The prior architecture review found a missing ignored provider-reference dependency in an exported checkout; that is a specific handoff gap, not justification for a platform rewrite.

Test a second person's ability to run a supported scenario and diagnose an injected failure. Add persistence when recovery/history across runs is needed; add deployment when someone needs hosted access. Neither is a prerequisite for learning from a local owner walkthrough. Preserve privacy-safe evidence and distinguish historical evaluations from the active verification target. See [G05–G07, D10–D14](../../DEFERRED.md).

There is a strategic tension to resolve: workbook §3 selected a 50–80-hour portfolio flagship with a shareable/deployed demonstration, while current repository decisions make deployment and persistence non-goals. The newer scope governs implementation. The historical hours are not a remaining budget, and the workbook does not authorize deployment now. When opening the next cut, choose a finite new timebox and a delivery target: reproducible local/replay handoff or separately approved hosted use. My recommendation is to finish the smaller shareable evidence package first, rather than let “conditional later stages” become an indefinite research program.

## 5. Experiments that could overturn the proposed design

**Start with the external baseline.** Select a small fixed set of owner-relevant one-way tasks: an ordinary expected success, flexible airport/date choices, and empty/poor-result recovery. These are design contrasts, not a statistically representative sample. Measure the owner's current workflow, including translating vague intent, using existing search tools, copying results and comparing them. Then evaluate the narrow pilot under the same task rubric. A system that wins only against its own artificially weak baseline may add no product value.

Use two distinct comparisons. The whole-task comparison includes actual request-formulation effort; manually supplied frozen requests cannot earn a claim of conversational assistance. A separate frozen-request comparison can isolate provider/result handling and remain useful while G01/G02 are open. Count any manual setup rather than attributing it to unimplemented automation.

**Then compare search strategies:** baseline endpoint queries; baseline plus access alternatives; baseline plus hub-component research. Freeze reviewed query bundles and their rationale before inspecting outcomes. They may be transparently translated from supplied 2B records or labeled human-authored; count human authoring and verification time. This evaluates strategy value, not generator quality or faithful 2C compilation. First fix endpoint selections so that supplements are isolated; evaluate larger/model-selected endpoint sets separately under M2A's adoption requirements.

Use the same maximum resource envelope, comparable retrieval timing, fixed query semantics, and a predefined usefulness rubric. A baseline need not waste its remaining budget merely to match spend; report actual work and the quality/cost tradeoff. Keep completed-option yield separate from useful-lead yield and from human verification effort. A hub component hit is not itinerary lift.

Record task order and observation timestamps. Repeating a task can make the second workflow faster because the owner already learned the answer; changing inventory can favor either arm. Counterbalance where practical or compare matched replay evidence, and report this small pilot as directional rather than a causal speedup estimate. For a downstream-only comparison, give both workflows the same prepared request and context; never start the pilot clock after human preparation while charging that work only to the manual baseline.

**Beware of unobserved counterfactuals.** Replaying only the queries chosen by one strategy cannot tell us what a different strategy would have found. Never mark an unqueried alternative empty. A bounded reference experiment can acquire the union of compared query sets and replay policies over it, with evaluation acquisition cost recorded separately from simulated policy cost. Live comparisons still need repeated, time-matched samples because inventory changes. Neither approach establishes exhaustive recall over all awards.

**Audit omissions as well as accepted output.** A system can look precise by suppressing everything difficult. Use reviewer-authored contrasts for same-market skips, country endpoints, rejected records and budget exclusions. Such cases can reveal whether a gate suppresses useful work; they do not authorize reopening 2B before an owner decision. Evaluate semantic variability by useful outcome differences, not by requiring identical model-selected airports across trials.

Predeclare decisions the results can cause: retain supplements, narrow their eligible scenarios, change caps, postpone component assembly, or remove a mechanism. Treat small pilot findings as directional. No numerical utility threshold, sample-size guarantee, or current gain is claimed here.

**Make the stop rule consequential.** If the baseline reduces owner effort on the declared tasks, finish its replay/demo and propose closing the smaller product cut; supplements need not be mandatory under the revised roadmap. If a bundle yields a distinct useful option or a lead with a named remaining obligation and worthwhile next action, propose automation of that specific strategy family. Useful lead discovery does not establish that automatic journey assembly is worth implementing; D15 needs its own value and validation case. If a bundle adds only records/caveats or transfers equal work downstream, park it. If the baseline shows no value, allow at most one explicitly time-boxed iteration on the observed bottleneck, then stop, pivot, or retain the result as an engineering demonstration. Do not automatically escalate into RAG, catalog growth or an adaptive controller. These are proposed decisions for the owner, not automatic implementation authority.

## 6. General agent-engineering principles applied here

These external sources inform the method; the stage recommendations above are project-specific judgments, not claims that a vendor prescribes this architecture.

| Primary source | Principle | Application to this project |
| --- | --- | --- |
| [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Distinguish fixed workflows from feedback-driven agents; increase complexity when it improves outcomes | Keep 2C deterministic. Test adaptive action selection only after observable results exist. |
| [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Inspect outcomes and traces, combine code/model/human grading, and separate capability from regression evaluation | Use code for invariants, humans for travel usefulness, calibrated model review for assistance; do not turn diagnostic casebooks into holdouts. |
| [Anthropic: Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) | Tools need meaningful, task-relevant interfaces and realistic evaluation | A future controller should receive compact coverage, observation and unresolved-check records, rather than undifferentiated provider payloads. |

One additional project inference follows: **uncertainty should be discharged only by evidence competent to resolve it.** Catalog lookup resolves identity; a provider observation can support inventory claims within its scope; a user answer resolves preference or permission; a grounded rule resolves eligibility conditions. Another model's agreement cannot substitute for any of those. Implement this initially with typed obligations and per-run receipts, not a new general-purpose evidence platform.

## 7. Decisions to make when opening the next cut

My recommended initial answers are:

1. **First output:** observed intact itineraries with supported requirements, plus separately labeled research leads; no automatic component assembly.
2. **Sequence:** approve a time-boxed comparison against the current workaround, then a narrow provider/result/output pilot and reviewed supplemental-bundle experiment. Full supplemental 2C automation becomes contingent in the proposed roadmap, rather than an assumed prerequisite.
3. **Baseline over budget:** preserve current compiler behavior until a versioned decision; consider explicit progressive coverage at next-cut design instead of treating all-pairs-or-fail as a permanent product goal.
4. **Positioning:** false excludes dependent strategies, not independently useful shared queries; unknown need not block authorized bounded research, but cannot establish suitability; true does not settle separate-ticket or feasibility questions.
5. **Value test:** compare supplements against baseline observations, count useful leads separately, and permit removal of a feature that does not justify its cost.
6. **Completion boundary:** demonstrate a supported positive option with reduced owner effort, plus correct failure/empty behavior and a finite delivery target. Choose whether to finish that smaller product or invest further. Broad conversational claims still require G01; M2A default adoption still requires G02.

The user requested analysis and a discoverable document, not implementation. These answers remain recommendations. No provider calls, new model diagnostics, catalog changes, stage reopening, or runtime policy changes were performed for this review. The workbook was read, not edited.
