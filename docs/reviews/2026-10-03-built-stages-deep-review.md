# Award search deep review

Date: 2026-10-03. Reviewed baseline: `8ef1d6a`. **Advisory recommendations, not new owner decisions or reopened stages.** [Read the concise overview](2026-10-03-built-stages-overview.md); both documents use the same sections.

The project has a credible AI engineering foundation. Its next challenge is proving that the assembled workflow helps a traveler make a better-informed decision with less work. Start lightweight opportunity discovery alongside Results, address demonstrated contract/evaluation gaps, and test the complete task before expanding the architecture. Completing the last processing stage, demonstrating useful local behavior, and operating a web app are separate achievements. This document incorporates a second, deeper review requested by the owner; the recommendations below supersede the first pass where they differ.

## Overall assessment

**Keep the architecture's core discipline; change what the next iteration measures.** Models interpret language and propose bounded airport/search hypotheses. Deterministic code owns calendar computation, state reduction, compilation, provider accounting, matching, and style membership. Unknowns survive instead of becoming plausible-looking answers. Captured executions can be replayed and checked. These are substantive strengths.

The current supported workflow is one-way and award-led. It can include at most one cash access or egress component; direct cash is a separate benchmark. Search Planning, Provider Stage, and Ranking are closed for their declared boundaries. Results is still design work. The latest owner direction is **LLM-authored structure and prose with code-filled factual placeholders**, superseding the earlier code-assembled answer. No Results output was generated or user-tested in this review. [Current state](../project-state.md), [latest Results direction](../handoffs/2026-10-03-results-stage-authored-template.md).

The evidence supports three different levels of claim:

| Claim | Current position | Next evidence needed |
| --- | --- | --- |
| The stages implement their declared contracts | Strong scoped engineering and owner-acceptance record; fresh checks reveal some handoff failures | Preserve contract/replay checks and disclose failing gates |
| The local workflow helps a traveler | Not established by stage closeouts | Completed Results, a continuous task, and a measured comparison with the current workaround |
| A deployed app serves external users reliably | Not implemented or claimed | Separately opened delivery scope, provider access, safe rendering/data handling, bounded execution, and observed operation |

The [existing core-completion definition](../../DEFERRED.md) already requires at least one predeclared owner-relevant task yielding a supported actionable option with less total effort, alongside honest empty/partial behavior. That is the right MVP test. One success establishes possibility, not broad reliability.

The largest evidence limitation is concentration: all three saved provider requests are SFO→BKK on October 5, 2026, with different party/cabin/positioning conditions. Their 992 retained candidate records include variants and duplicates; they are not 992 independent flights or tasks. Of these, 427 are admitted/conditional and style-eligible; all 427 have undetermined cost membership. These facts should guide the next experiments rather than diminish the legitimate stage achievements. [Provider corpus](../../evidence/provider-stage/saved-searches/README.md), [Ranking corpus](../../evidence/ranking-stage/m2/README.md).

The deeper pass changed the priority of several issues:

| New evidence | What it changes |
| --- | --- |
| A synthetic provider `premium` cabin is dropped on a `premium_economy` request; the retained token also misses downstream add-ons | Confirm and normalize the provider vocabulary before claiming this cabin path works |
| Seeded omissions of matching blockers and cost needs pass specific downstream checks | Evaluate the detection power of the graders and define imported-artifact authority; parsing/replay alone is not semantic certification |
| Current products already document flexible region/date discovery and program filtering | Test a narrower unmet comparison/positioning job; a conversational search box is not an established advantage |
| Official trip examples offer a possible interpretation for 17 direct-award quotes | Investigate a narrow, versioned cost projection before assuming every useful comparison needs more provider calls |
| Some acquired hub evidence cannot enter current M1 assembly | Compare execution priorities against supported user outcomes while preserving the complete planning graph |

The cabin result is reproduced behavior under synthetic input. The evaluator findings are deliberately seeded faults, not examples of the normal producer failing. Product differentiation and the price interpretation remain hypotheses requiring their own evidence. This distinction determines the proposed response to each finding.

## Traveler experience and product value

**Recommended first segment:** points-literate travelers researching an outbound award journey, willing to verify availability and redemption eligibility with the relevant program. This is a product hypothesis to test. The broader label “AI flight search” invites expectations of round trips, personal points access, all-in comparable prices, and booking that the current scope does not provide.

Recommended promise: “Turn a flexible one-way award trip idea into a small set of observed options and the checks needed to investigate them.” Explain the one-way boundary before input and give realistic examples. An unsupported return request should receive the approved separate-one-way guidance; it should not quietly become a different task. Point balances and transfer eligibility remain D06, to be pulled forward only if the demonstrated task cannot be useful without them.

### Earn a reason to use this alongside existing tools

The proposed promise is a supported-scope description, not yet a differentiated product proposition. Official guides document region/date discovery in Seats.aero, PointsYeah Daydream, and Roame, and program/transfer guidance in established products. These are documented capabilities, not measured competitive quality or a feature-complete comparison. We did not test logged-in products or adopt marketing savings claims. [Seats getting started](https://docs.seats.aero/article/92-getting-started-with-seats-aero), [PointsYeah Daydream](https://www.pointsyeah.com/insider/product/daydream-explorer), [Roame SkyView](https://help.roame.travel/articles/950879-how-to-use-roame-skyview-copy), [point.me workflow](https://connect.point.me/help/how-does-point.me-work).

| Candidate job | Why the existing work might help | Cheapest useful challenge |
| --- | --- | --- |
| Decide whether one cash feeder makes an award worth investigating | Current M1 can combine intact awards with one access/egress flight and preserve total timing/checks | Compare two disclosed, manually prepared positioning briefs with the user's normal spreadsheet/tool process, including one unattractive transfer |
| Explain a shortlist to a travel companion | Results could carry the program, tradeoffs, conditions, and next action without repeated explanation | Give a second person the user's existing artifact and a prototype over identical evidence; observe reconstruction questions and mistaken assumptions |
| Turn changing preferences into an accurate search brief | Grounded semantics and immutable corrections could reduce repeated form work | Compare the supported clarification flow with a concise form; distinguish pre-ready corrections from unimplemented post-results refinement |

These are alternative experiments, not three new features or claims of uniqueness. Experts may prefer direct filters; novices may need eligibility/transfer help outside the current scope. Recruit around an actual costly task rather than points literacy alone. Keep separate denominators for naturally occurring requests, requests fitting the one-way boundary, and supported tasks that produce a useful next action. A high success rate after excluding most real trips can coexist with weak product relevance.

Start observing the owner's workaround and conducting a small discovery round now, while Results is built. A disclosed prototype can test demand and comprehension; only the completed system can establish automated task benefit. Record usable programs, return needs, and ticket tolerance in the study worksheet without pretending they are implemented filters. If personal eligibility is essential to the chosen job, use D06's existing trigger rather than hiding that logic in writer prose. Do not broaden the scope simply to imitate competitors.

### Make the next action obvious

Each selected journey should let the traveler answer five questions:

1. What complete route, local dates, schedule, and cabin evidence am I looking at?
2. Which **redemption program** would I use, and which airlines operate the flights?
3. What points, fees, and cash amounts were actually returned, and what quantity do they cover?
4. Which requirements, availability details, or separate-ticket arrangements remain unverified?
5. What should I check next, with whom, using which route/date/party?

For example, identifying an Aeroplan redemption on an operating airline and a separately purchased onward flight gives the user a reconstructible search. A points number and airline logo do not. Initially, a program name and precise search particulars can be sufficient; invented booking links, automated transfers, or a loyalty knowledge base are unnecessary. Seats.aero's own [program-access explanation](https://docs.seats.aero/article/41-why-can-t-i-book-this-flight-with-my-miles) and [phantom-availability guidance](https://docs.seats.aero/article/15-what-does-phantom-availability-mean) support direct verification before relying on an observation or transferring points.

### Make uncertainty understandable at the decision

“Admitted” is an internal policy result. It does not establish booking protection, known all-in price, or every leg's cabin. All five admitted mixed journeys in the saved positioning case retain separate-ticket obligations. Show the actual transfer interval and unverified arrangements next to that journey. Do not translate a passing two-hour rule into “safe connection.” British Airways recommends four hours for separate tickets at Heathrow and describes the traveler's missed-connection exposure; this is a counterexample to a universal two-hour assurance, **not a proposal to replace the policy globally with four hours**. [BA connection guidance](https://www.britishairways.com/content/information/airport-information/flight-connections).

All three saved provider results are partial. Explain the relevant unfinished scope without converting overlapping graph accounting into a misleading percentage of flights searched. Distinguish completed-empty work, omitted work, provider failure, and answer-generation failure. Keep provider observation/update time distinct from retrieval time; label historical replay as historical. “Best available,” “no awards exist,” and “checked today” require evidence that the current artifacts do not supply. [Coverage contract and examples](../../evidence/provider-stage/saved-searches/README.md).

The provider audit found row-update ages reaching roughly 186 hours at acquisition in the saved data. `UpdatedAt` is not established as the last inventory verification time, so this is a row-age observation, not a measured stale-seat rate. The runtime `stale` result status instead concerns request/plan authority; it must not be presented as an inventory-freshness check. Keep those meanings distinct until a source contract supports stronger freshness claims.

### Treat price scope as a value bottleneck

The cost algorithm is implemented, but none of the saved requests supports its complete cost reference. Requested party size does not establish whether a returned quote is per person or per party. The one-cent point valuation and USD 150 unknown-tax estimate cannot repair that missing meaning. Display source quotes with their limits; suppress unsupported cheapest/savings claims.

The likely next value investment after honest Results is a **bounded provider-semantics investigation**: can real supported responses establish points, fees, and cash quote scope? Require documented semantics and reviewed captures, or an explicitly approved typed assumption with a different claim. Do not silently guess scope to activate a Cost badge. If users find the schedule/cabin shortlist useful without complete pricing, this can remain a scoped limitation; if pricing prevents a concrete next action, G04 becomes the next product priority. [M2 evidence limits](../../evidence/ranking-stage/m2/README.md).

The deeper provider audit found a concrete starting point. Seats.aero's official Concepts example describes a passenger paying the trip's `MileageCost` and `TotalTaxes`, with taxes expressed in minor units. It also distinguishes aggregate Availability from individual trips. This is strong illustrative evidence, not a universal guarantee across every source/program. A narrow per-passenger interpretation could be adopted for reviewed supported trip fields, with a versioned capability and new derived outputs. Do not transfer a summary minimum or seat count onto an unrelated trip. [Seats Concepts](https://developers.seats.aero/reference/concepts-copy).

In the saved corpus, 17 eligible direct Aeroplan award records have numeric trip points, CAD fees, and no cash component. They are the smallest candidate for such a projection. The remaining 410 eligible records include cash; 405 use Turkish awards with unsupported taxes and the approved estimate. Unlocking arithmetic there would still not make their totals fully observed. Requested party size—even one traveler—and a `gfly` query echo do not establish quote cardinality. Its documented `price` field does not supply that guarantee. [Current saved results](../../evidence/ranking-stage/m2/README.md), [gfly specification](https://github.com/rnwolfe/gfly/blob/main/spec.md).

Proposed order: decide whether the trip documentation is sufficient for the narrow interpretation; audit the 17 captures; generate a separate versioned projection and verify exact currency/quantity arithmetic; label the result as heuristic value. If that evidence threshold is not met, obtain provider clarification. Investigate cash cardinality separately using a pinned source contract and controlled matched-itinerary evidence. No quote scope was changed and no new cost reference was produced during this review.

### Test usefulness without confusing it with fluent writing

Use two studies with different purposes. First, compare presentation variants over identical frozen evidence to test comprehension and selection. Then compare the completed workflow with the user's actual workaround to measure total effort. A replay-only display comparison cannot establish live search-time savings.

For the first formative round, five to eight target users is a proposed manageable sample, not a reliability denominator. Include spontaneous requests, an all-conditional result, an admitted separate-ticket option, incomplete cost, and empty/partial outcomes. Ask users to select a next action and explain their understanding before asking whether they like the answer. Record wrong beliefs and remaining verification work. Use realistic, non-leading tasks, consistent with the [GOV.UK moderated usability guidance](https://www.gov.uk/service-manual/user-research/using-moderated-usability-testing).

### A small study that can change the plan

Use one owner dry run followed, for example, by six likely users across two formative rounds. Each gets two matched comparison tasks and one short comprehension probe; rotate the other probes to keep sessions manageable. Six is a workload choice, not a statistically sufficient sample. Predeclare tasks, evidence snapshots, assistance rules, and success criteria.

| Experiment | What to observe | Proposed change or stop rule |
| --- | --- | --- |
| All-conditional next action | Can the person name the program and specific unresolved seat/party/permission checks without treating a highlight as confirmation? | Any critical mistaken assurance triggers a presentation fix and retest. Correct refusal is an honest negative outcome, but cannot supply the positive-value demonstration |
| Shortlist omissions | Record preferences first; after selection, reveal a reviewed, readable set of omitted distinct alternatives from the same pool | If two independent cases expose material preference-relevant omissions, revise brief/selection before increasing the five-option cap. A changed preference alone is not a selection defect |
| Condition salience | Compare valid authored layouts with the same facts/IDs; observe finding and understanding key conditions on a narrow viewport | Missing/unreachable conditions fail. Repeated unnoticed material conditions trigger a placement/label change and retest while preserving model authorship |
| Total effort | Compare matched, different tasks using familiar tools versus the completed workflow | Require correct next actions and a predeclared meaningful effort improvement; count failed and assisted tasks. No speed claim if the gain disappears when rechecking is counted |
| Expansion value | Compare direct and supplemental options with explicit equivalent acquisition budgets | If supplements add review work without a useful next action, propose a narrower execution experiment; do not count unqueried alternatives as empty |

For the timing comparison, counterbalance task/tool order and give equal practice on a third task. Having everyone solve the same task manually first would teach them the answer and bias the app comparison. Measure active minutes and wall time separately. Include clarification, retries, external checking, and recurring human preparation. Use an unaided timed segment followed by retrospective questions; concurrent think-aloud is useful for diagnosis but changes ordinary-use timing. A readable worksheet is a fairer control than raw JSON.

The exact-business corpus has 106 eligible records, all conditional, across only three distinct award-observation IDs. Those IDs are not independently established unique flights or meaningful choices. Test selection diversity and omission regret rather than counting displayed styles. The positioning case's 8h55 wait is a particularly useful desirability test: a correct Time label does not establish that a person wants that journey.

For accessibility, inspect rendered heading semantics, reading order, keyboard access, and key-condition findability; include users with relevant access needs where feasible. A visually clear Markdown source is not evidence of accessible rendered content. [W3C headings and labels guidance](https://www.w3.org/WAI/WCAG22/Understanding/headings-and-labels.html).

Attribute failures to the earliest evidenced boundary: interpretation/state, search coverage, missing provider facts, matching/style policy, selection, wording/layout, or research setup. Missing source facts are not writer failures; overlooking a buried condition is not automatically user error. After two focused study/revision rounds without a credible benefit, explicitly consider narrowing the job, prioritizing provider evidence, or finishing this as a bounded engineering portfolio project. This is a proposed investment stop rule, not a current decision.

## AI design and evaluation

**Describe the system as an explicitly orchestrated LLM-assisted workflow with bounded model decisions.** The current executor does not let a model autonomously select tools and replan after provider results. That is an appropriate choice. A Results submission tool would change how the authored document reaches validation; it would not make the system more autonomous or its prose more accurate. This distinction aligns with [Anthropic's workflow and agent guidance](https://www.anthropic.com/engineering/building-effective-agents).

### Preserve the strengths and address the semantic gap

Source grounding establishes where a proposal came from; deterministic arithmetic establishes what the proposed operation computes. Neither proves that the proposal captured what the traveler meant.

The September 20 active Intent-to-planning diagnostic recorded 13/19 behavioral passes, two pending outcomes, and seven compiled plans. The `ambiguous_departure` case incorrectly reached ready and produced a plan. Its downstream mechanical checks succeeded. That is evidence of a semantic failure in that recorded run, not proof of its present frequency. The individual `unbounded_departure_ready` guard checks for a missing departure window; an invented bounded window escapes that check, although the overall case correctly fails other checks. Add an oracle-based **false-ready** measure: how often an input labeled as requiring clarification reaches executable state. Reproduce the failure, inspect its proposal, and test fresh contrast families before claiming dependable conversation. This is G01, not authorization for a wholesale upstream rewrite. [Recorded diagnostic](../build-log/2026-09-20-intent-to-search-planning-evaluation.md), [evaluator](../../src/award_agent/cli/intent_eval.py).

Do not erase positive evidence while explaining this gap. The active one-way clarification diagnostic recorded 35/36 trials over 12 scenarios, with the one ambiguous-departure failure leaving state unchanged. The ten exact-request ready trials supported a narrow wire-repair result. Neither replaces broad initial-input or independent holdout evidence. Do not combine the older 8/57 pre-fix intent result with 10/10 on one different request to claim a measured accuracy improvement. [Clarification artifact](../../evals/clarification/baseline/2026-09-11-one-way-award-live-v2-3-trials.json), [intent redesign record](../build-log/2026-09-11-initial-intent-semantic-redesign.md).

### Evaluate the filled Results document

The authored-template design is sound for binding values to the selected journey. A correctly inserted quote can still sit under “cheapest,” beside “per person,” or beneath a heading that promises an easy protected connection. Required-slot presence cannot establish truthful implications or visible conditions.

Keep deterministic checks for identity, allowed placeholders, alternate references, count limits, required conditions, and intact facts. Evaluate the **fully rendered answer** for misleading prose, unsupported comparisons, omitted caveats, and implied certainty. Do not let the writer rewrite the filled document. Prefer one submission contract; choose structured output or a tool adapter by implementation simplicity, with no extra lookup loop unless the compact brief proves insufficient.

Extend the existing M3 proposal rather than build another eval platform. It already proposes 12 cases × 3 writer trials, plus 11 labeled calibration answers: 36 writer invocations and 47 judge evaluations if each completes once, or 83 application invocations before retries. This is a proposed workload, not measured cost. Use the three saved cases and synthetic contrasts for complete costs, contradictory variants, fees, cabins, incomplete-only results, failed coverage, and empty outcomes. Add fluent false headings beside correct factual slots. [Results implementation plan](../handoffs/2026-10-02-results-stage-implementation-plan.md).

Judge outputs should identify the exact problematic passage and supporting evidence. Validate the judge's references and count invalid judge output as evaluator failure. Human-review hard flags and a declared sample of apparently clean outputs. Freeze the rubric after calibration and use fresh labels for any judge-accuracy claim. Model separation alone does not guarantee independent errors. Randomize/blind comparative presentation where practical; judge research documents position and verbosity biases. [LLM judge research](https://arxiv.org/abs/2306.05685).

### Use distinct denominators

| Evaluation layer | Measure | Proposed acceptance evidence |
| --- | --- | --- |
| Deterministic contracts | Invalid references/state changes accepted per challenged case; replay equality | No accepted known-invalid case in the declared suite; current scoped checks pass |
| Input semantics | Correct terminal action per attempt; false ready per oracle-blocked attempt; preserved corrections | No unresolved critical false-ready or constraint-loss case in the declared acceptance set; publish its size and misses |
| Results semantics | Materially unsupported answers per completed answer; hidden conditions per applicable answer | Resolve material defects before accepting the affected output; count generation failures separately |
| Judge quality | Missed defects per defective labeled answer; false alarms per clean answer; evaluator errors | Fresh human labels and adjudication; no judge-only acceptance |
| Complete task | Useful supported next action per attempted task; turns, remaining checks, total effort | A positive predeclared task plus truthful failure outcomes, compared with the workaround |
| Operations | Total wall time, attempts, tokens, timeouts, cost per useful completion | Explicit finite budgets and tested exhaustion; report all failed attempts in total cost |

All zero-defect gates above are proposed sample acceptance rules, **not proof of zero population risk**. Repeated trials measure instability; they do not add independent task diversity. Split development and holdout by related request/itinerary families, not random rows. Once an example informs tuning, treat it as development evidence. Keep regression tests separate from capability experiments, following current [agent-evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

Use a small manifest over existing runners, with model/prompt/schema/policy/catalog identities and resource settings. Keep routine checks offline. Authorized, bounded live runs answer semantic or provider-drift questions; frozen replay isolates downstream changes. Scripted multi-turn cases should come before elaborate user simulators. Simulators can stress behavior but cannot substitute for real user research.

### Test whether the evaluation detects a wrong answer

The second review ran deliberately faulty outputs through existing validators and evaluator seams. The repository and saved baselines were unchanged. These probes test the strength of specific claims; they do not show that current normal execution produces the faults. [Runnable oracle probe](evidence/2026-10-03-built-stages/evaluation_oracles.py), [recorded outcomes](evidence/2026-10-03-built-stages/evaluation_oracles.json).

| Seeded fault | What accepted it | Interpretation and narrow response |
| --- | --- | --- |
| Remove `award_travelers_unknown` and `result_validation_minimum_award_seats` from one conditional M1 journey; set admitted and update counts; keep plan/provider identical | M1 parsing, M2 assignment, and the independent M2 corpus integrity helper | Status is consistent with supplied reasons, but required reasons are incomplete. Define M1 import authority and independently assert source-required blockers |
| Wrap M2 derivation in memory to empty assessment `validation_needs` | JSON round trip, independent corpus helper, and all three existing M2 corpus test-function calls; 64 nonempty lists become empty in the positioning case | Validation reuses the production derivation. Component `missing_parts` remains, so this is a summary-needs gap, not total evidence disappearance |
| Relabel a temporary one-case policy-skip planning corpus with all five coverage categories | Preflight and the public exact gate report 1/1 passed | Labels are not exercised coverage. The current tracked four-case count test would catch this exact shrinkage; the public evaluator needs observed family predicates |
| Verify an empty temporary Provider index | Returns success with zero runs/observations | Valid empty structure is not positive stage coverage; acceptance requires a declared applicable denominator |

Frozen expected-byte verification would detect the changed M1/M2 artifacts where it is used. The suite also has real independent timing arithmetic, premium checks, pairing expectations, and synthetic cost tests. Calling all tests circular would be wrong. The gap concerns **newly produced artifacts and claims not covered by independent assertions**.

Similarly, the standalone planning 4/4 corpus uses skip, empty, and generation-failure scenarios, all with zero supplemental strategies. Separate unit tests do exercise nonempty relationships. Add a small nonempty public compilation-to-provider dry/replay path with hand-enumerated expected dependencies; do not treat its absence as evidence that supplemental compilation is wholly untested.

A compact next acceptance set should pair each invalid example with a valid control, so rejecting everything cannot pass. Begin with the four probes above, a nonempty access/hub graph, known/unknown/insufficient seat contrasts, equivalent per-person/per-party costs, missing-versus-zero fees, and reordered candidates. For Results, add accurate facts beside false assurance, visible versus hidden required slots, and valid alternative wording. Record faults detected, faults missed, clean controls rejected, and harness errors separately.

For each acceptance claim, record the expected invariant, the oracle's source, dependence on production helpers, valid control, seeded fault, and reviewer. Content hashes establish integrity; independent labels establish specified meaning; user action establishes usefulness. Recent evaluator audits also show why valid alternatives and faulty outputs both need checking; external benchmark defect rates do not transfer to this project. [OpenAI's SWE-bench evaluation audit](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/).

## Engineering and operational readiness

**The implementation has strong audit boundaries; the integrated operating and handoff boundary needs work.** Preserve immutable inputs, explicit errors, complete accounting, and replay. There is no evidence here that replacing them with a framework would help.

### Correct the provider cabin boundary before extending its claim

The internal premium-economy value is `premium_economy`. Seats.aero documents `premium` in its Bulk Availability cabin vocabulary; the inspected Get Trips schema allows a string rather than an exhaustive enum. Offline fake-response tests show a trip with `Cabin=premium` is silently discarded for a `premium_economy` request. An unrestricted search retains `premium`, which M2 does not recognize for the premium-economy add-on. This establishes adapter behavior on the supplied token; it does not measure how often live Get Trips returns it or whether Cached Search accepts the outbound alias. [Seats schema](https://developers.seats.aero/reference/get-availability), [adapter](../../src/award_agent/providers/seats_aero.py), [style rules](../../src/award_agent/ranking/styles.py).

| Synthetic contrast | Result |
| --- | --- |
| Business request and returned `business` | One parsed observation |
| Premium-economy request and returned `premium` | Completed page, zero observations, no finding |
| Same request and returned `premium_economy` | One parsed observation |
| Full public M1/M2 path, changing only `premium` to `premium_economy` | Both admit three candidates; premium-economy add-ons change from zero to three |

Proposed correction: one provider-specific vocabulary map at the adapter boundary, raw token preserved, canonical token used for filtering and downstream facts. Test all four cabins through request parameters, summary `W` fields, inline trips, detail trips, exact filtering, and style membership. Settle live response/request semantics with reviewed documentation or a representative capture before claiming actual API compatibility. Version changed interpretation and regenerate derived artifacts explicitly. [Parser probe](evidence/2026-10-03-built-stages/cabin_contracts.py), [public M1/M2 contrast](evidence/2026-10-03-built-stages/premium_style_contrast.py).

The audit also found a narrower disclosure question: synthetic positive `MixedCabinPct` survives in raw fields but creates no normalized mixed-cabin finding. Current defaults ordinarily exclude lower-cabin portions, and m1-v2 intentionally permits unreported leg cabins. Do not silently introduce a rejection rule. Preserve positive mixed-cabin evidence in the Results brief, and decide its strict-cabin implications explicitly if that response occurs. No such saved live failure was demonstrated.

Several suspected failures were falsified: both adapters return unknown instants for DST folds/gaps; unsupported free-text constraints remain unknown requirements; targeted stale-authority, fanout, transfer-boundary, and adopted cabin-policy checks passed. A deeper review should retain these negative findings alongside defects.

### Spend the existing provider budget more effectively

Two saved runs, `mixed_access` and `exact_business`, each executed two identical physical SFO→LAX cash searches because the queries were activated by different award observations. Each run allowed three cash requests, including the direct benchmark. Query identity includes the activating award ID; physical route/date/party/cabin/currency can still be identical. This preserves provenance but duplicates acquisition. [Execution](../../src/award_agent/providers/execution.py), [saved runs](../../evidence/provider-stage/saved-searches/README.md).

Test coalescing identical physical requests **within a run**, retaining every activation/dependency link. Use a recording transport to prove fewer calls and unchanged attribution. Preserve old policy snapshots for exact replay. Historical tapes cannot establish what a newly freed call would have returned; incremental result value requires a later bounded live comparison. Do not introduce cross-run caching or assume two observations captured at different instants are interchangeable.

The executor also performs summary searches before detail retrieval, sharing request/time budgets. The two-detail ceiling is a maximum, not a reservation. A broad graph can exhaust the budget before obtaining timings needed for complete journeys. Compare the current policy with a versioned detail reservation/interleaving experiment at equal budgets. Count distinct complete useful journeys, not raw rows or completed graph units. This concerns Provider scheduling; it does not make M2C unfinished or authorize graph trimming.

There is a more specific allocation question. M1 assembles intact endpoint awards and origin/destination access journeys; it does not join scoped-hub components. Yet hub-only queries consumed these saved acquisition resources:

| Saved case | Hub-only logical queries / all | Actual hub-only award transports | Hub-only summaries | Scheduled hub detail jobs / executed transports |
| --- | ---: | ---: | ---: | ---: |
| Mixed access | 6 / 8 | 6 | 192 | 115 / 0 |
| Exact business | 2 / 4 | 2 | 37 | 37 / 0 |
| Positioning | 2 / 5 | 2 | 36 | 36 / 0 |

“Hub-only” excludes mandatory/shared queries. Scheduled detail jobs were not executed calls. No timed hub-only itineraries appeared, and current M1 cannot assemble these hub components into complete recommendations. They might still be useful research leads; this narrow corpus does not prove otherwise. Test a versioned provider allocation that prioritizes supported complete topologies, with a separately measured allowance for useful leads and explicit omissions. Preserve the full compiler graph. Opening general hub assembly merely to use already-generated queries would reverse the correct direction of product scoping. [Execution](../../src/award_agent/providers/execution.py), [supported matching topology](../../src/award_agent/ranking/matching.py), [saved inputs](../../evidence/ranking-stage/m2/README.md).

### Give composed work and semantic checks clear owners

The substantial intent-to-planning composition currently lives in live-evaluation modules; Provider and Ranking have separate artifact CLIs, and the experimental harness stops at clarification as required. The first continuous workflow should have a small shared application coordinator that calls existing stages and returns explicit needs-input, unsupported, pending, partial, and completed outcomes. CLI and evaluation should drive that same path; scoring and fixture substitution stay outside it. This is a local composition task, not a reason to introduce an orchestration framework or move provider logic into the harness. [Current composition](../../src/award_agent/evaluation/intent_to_search_planning_live.py), [other planning diagnostic](../../src/award_agent/evaluation/search_planning_live.py).

The seeded M1 reason omission also needs an explicit ownership decision. Current M2 promises additional source timing checks, not complete rederivation of every M1 decision. Nevertheless, the file CLI accepts a supplied M1 artifact without an independently supplied trusted producer digest. A consistent hash and unchanged-file check do not establish that every necessary source-derived reason exists.

Recommended narrow design: M1 owns a pure, versioned candidate requirement assessment used by its producer and by an explicit loaded-artifact verifier. Verify applicable requirement reasons against the embedded source, rejecting admission inconsistent with source-required unknown or failed requirements. Requirements alone cannot establish every journey status. Do not copy rules into M2 or enumerate the whole matcher again. Dispatch the original matching policy faithfully or explicitly reject unsupported policy versions. Publish the verifier's actual scope; checking requirements does not prove every matching property. Independent hand-labeled sufficient/insufficient/unknown controls remain necessary because shared-function rederivation cannot detect an error inside the shared function.

An alternative is a deliberately trusted-only handoff with an expected digest from the producing run manifest plus independent producer tests. That is smaller but gives weaker support for accepting independently supplied/regenerated files. The preferred review recommendation is the scoped M1-owned import verifier, before Results relies on imported status/conditions as authoritative. The probe does not show that current normal matching or the saved originals contain bad admissions. [M1 contract](../../src/award_agent/ranking/contracts.py), [M2 file CLI](../../src/award_agent/cli/ranking_styles.py).

### Bound the whole request

Inspected active model clients use `OpenAI()` defaults; the installed SDK exposes a 600-second timeout and two retries. One application call can therefore involve multiple HTTP attempts, and one semantic repair is not a deadline. Provider elapsed accounting also excludes some local processing and upstream/downstream stages. HTTPX's read timeout applies to waiting for a chunk, not the entire composed workflow. [Model adapter](../../src/award_agent/intent/openai_interpreter.py), [transport](../../src/award_agent/providers/transport.py), [HTTPX timeout documentation](https://www.python-httpx.org/advanced/timeouts/).

Before promising responsiveness, introduce an absolute request deadline with explicit model/provider attempts, remaining time, cancellation, and typed partial/pending/failure outcomes. Test slow responses, retries, exhaustion, malformed output, and a request revision changing while work is in progress. Measure total wall time rather than adding reported stage times. Choose the numerical budget from the intended user experience and observed costs; this review supplies no invented latency target. A local orchestrator is sufficient initially; durable workflow infrastructure is not a prerequisite.

The existing measurements illustrate why the denominator matters. The 19-case intent-to-planning diagnostic records a median of 8.361 seconds of per-case stage time. Its seven planning-eligible cases have a 19.484-second median and consume 45,329 tokens; one of those seven is the semantic failure. All 19 attempts consume 89,305 tokens across 35 calls. The three separate saved Provider runs report transport-duration sums of approximately 24.638, 25.002, and 25.211 seconds, mostly cash acquisition. These are historical, different workloads; they cannot be added to produce observed application latency, and none includes Results or proves a cost per useful traveler task. [Recorded diagnostic](../../evals/intent_to_search_planning/baseline/2026-09-20-gpt-5.6-luna-active-intent-corpus-1-trial.json), [workload projection](evidence/2026-10-03-built-stages/saved_workload.json).

For an economic comparison, use total spend over all attempts divided by supported useful completions, with model input/output usage, provider entitlements/limits, and human rechecking reported separately. Do not infer dollar costs from token totals without the actual model/rate contract. A cheap failed task and an expensive useful task should remain distinguishable; stage-call savings alone do not establish product value.

### Make one handoff reproducible

Fresh M2 and Provider corpus verification succeeded locally. A tracked-only export of the repository failed the current planning golden CLI because the local catalog manifest was absent; the same CLI passed 4/4 on the owner's machine. The exported run reused installed dependencies, so it is a specific missing-artifact finding, not a complete fresh-install test. The older missing-provider-document explanation is stale.

The pinned `gfly` environment is also incomplete: its `pyvenv.cfg` is missing and the executable reports the base interpreter prefix, causing the intended compatibility guard to reject it. This explains two current compatibility-test failures; it does not demonstrate that the parser fix regressed. No tracked dependency lock or CI workflow was found. [Compatibility script](../../scripts/gfly_compat.py), [planning evaluator](../../src/award_agent/cli/search_planning_eval.py).

Choose one declared demonstration path. Supply pinned dependencies, permitted artifacts or a small synthetic replay alternative, an expected output, and no hidden laptop paths. Have another person run it and record setup friction. A downstream replay demo need not depend on live `gfly` if its claim excludes acquisition. Fix the active declared gate; postpone broad historical-code cleanup until an import/entry-point map makes retirement safe.

### Treat external web use as a separate boundary

Current Results has no implemented web renderer. Define safe Markdown rendering before adding one: disable raw HTML, constrain generated links, escape provider/user-derived strings, and test hostile text as data. Do not treat model-authored Markdown as trusted application markup. Keep semantic injection tests separate from browser injection tests.

Required-slot validation should operate on visible parsed content: a condition inside a comment or link target is not displayed merely because its token exists. Test hostile HTML, remote image links, unsafe URL schemes, inserted labels that break Markdown syntax, and instructions to suppress conditions. Verify rejection or inert rendering and no unintended external fetch. Deterministic rendering checks belong here; a language-model judge cannot establish browser safety. [OWASP prompt-injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html).

Private model traces intentionally capture full inputs/outputs. For external participants, select what is stored, redact secrets and identifying content, separate public evidence from private payloads, and define deletion/retention. Typed facts do not sanitize every free-text field. Keep provider credentials server-side and bound per-user work if a shared service is opened. These are future boundary controls, not claims of a current breach or requirements for a local replay.

Reuse the existing stale-result checks through final application publication. Test run A being superseded by B, with A finishing last: only B may become the current answer. Cancellation must stop subsequent calls; concurrent users must not share mutable trace collectors or retrieve each other's results. Add simple account-wide admission and quotas before shared live access; per-run budgets cannot bound aggregate load. These controls need no distributed queue initially. For logging, synthetic canary secrets and identifying phrases should be absent from ordinary diagnostics/public exports, including exception paths. [Existing traces](../../src/award_agent/observability/llm_trace.py), [OWASP logging guidance](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html).

Provider permission is a concrete delivery dependency. Seats.aero's current documentation describes restricted personal Pro API use and approval requirements for production/commercial use. Its terms require visible attribution and a link where API data are searched/displayed, and restrict certain public displays beyond 60 days absent OAuth or an agreement. Confirm the intended access mode and applicable agreement before opening a service. This does not overturn the current local choice to avoid per-journey citations; provider attribution is a separate future UI requirement. [API usage guidance](https://docs.seats.aero/article/68-seatsaero-pro-api-access-limits-and-usage), [terms](https://seats.aero/terms), inspected October 3, 2026.

## Decisions to challenge

These are the consequential disagreements to investigate. **Retain approved policies until evidence and an explicit owner decision change them.**

| Existing choice | Critical challenge | Recommended disposition and discriminating experiment |
| --- | --- | --- |
| Two-hour separate-ticket filter | Passing chronology is weaker than practical connection assurance | Keep the scoped filter; prohibit assurance language. Test comprehension of actual waits and unverified arrangements before designing richer feasibility rules |
| Unified admitted/conditional style minima | A conditional fastest option can determine Time membership and overshadow a more actionable option | Preserve membership. Test whether Results selects and explains the useful slower admitted option alongside the unresolved faster one |
| Time ≤120% and cost ≤200% of reference; categorical Premium | Mathematically correct categories may be broad or uninformative; every eligible exact-business record is Premium | Compare choice quality with simple elapsed-time presentation. Tune only if users misunderstand or fail to decide, with owner policy revision |
| Fixed point valuation and unknown-tax estimate | Heuristic cost can be mistaken for payable cost or personal value | Keep assumptions explicit; resolve quote scope before testing observed cost utility. Do not add weighted scoring to compensate for missing evidence |
| Complete provider-neutral graph | More hypotheses can consume detail budget without producing more complete choices | Keep compiler completeness. Test coalescing and provider scheduling, then direct-only versus expanded execution at equal budgets under D02 |
| LLM-owned answer structure | Natural writing may bury conditions or invent implications around accurate slots | Respect the authored-template decision; evaluate filled answers and comprehension. If it fails, propose narrower editorial constraints with examples |
| Cleanup without a separate input cap | Small saved examples do not establish context fit or selection quality at high fanout | Measure actual cleaned tokens and retained-condition/selection quality. Fail explicitly if generation cannot proceed; no silent truncation or unapproved cap |
| Extensive nested audit artifacts | Easy replay can impose repeated validation cost and make the evidence hard to navigate | Keep checks at trust boundaries; profile before refactoring. Use compact model views and a concise current entry point |

The review recommends **no** multi-agent product runtime, RAG, general component assembly, round-trip expansion, more providers, or weighted overall score for the next cut. Those are possible responses to demonstrated unmet needs, not proof of sophistication. The same applies to an adaptive controller: D09 should require an equal-budget improvement over deterministic scheduling.

There are two useful tensions rather than one universal answer. Conservative unknown preservation protects the traveler but can produce an unusable shortlist; measure usefulness instead of weakening facts. Natural model writing can improve explanation but reduce consistency and salience; measure both instead of assuming either templates or prose always win.

### Compare a materially smaller interaction design

The current clarification interpreter receives the new answer, blockers, and eligible target names. It does not receive resolved values, the authored question, or full history. READY is terminal for that API. Explicit supported corrections can work while clarification is open; arbitrary “one day later” references or post-results edits are a different capability. Initial and follow-up turns also use different calendar operation vocabularies. These are inspected contract limits, not newly measured live failure rates. [Interpreter input](../../src/award_agent/clarification/interpreter.py), [controller](../../src/award_agent/clarification/controller.py), [clarification calendar](../../src/award_agent/clarification/calendar_plan.py).

Test three interfaces over the same downstream evidence: current clarification; a proposal-only receiver given a compact resolved-state snapshot; and natural-language prefill followed by explicit editable request fields. The worksheet alternative retains initial model interpretation and the approved LLM-authored Results, while potentially removing a second receiver/composer/repair path. It changes the accepted interaction policy and cannot be implemented as cleanup. Read access to current facts need not grant write authority; every alternative must preserve explicit corrections, immutable revisions, unsupported scope, and recomputation.

The counterargument is substantial: worksheets can shift date-resolution work onto users, and separate contracts encode intentional authority/repair differences. Keep the conversational design if it reduces total effort without increasing wrong states. Measure restarts, correction success, lost constraints, and task abandonment; prototype post-ready editing only as an explicitly new capability. Consolidate shared calendar primitives or retire historical executable paths only after a caller audit and evidence of change burden. Preserve original policy/digest dispatch and historical replay. There is no justification here for a wholesale rewrite.

## FDE portfolio evidence

**The strongest story is judgment under uncertain inputs and incomplete tools.** The missing evidence is closer to customer delivery: observed task value, a maintainable handoff, and the owner's ability to explain decisions independently of AI assistance.

Current official role examples emphasize customer discovery, scoping, implementation, evaluation, production delivery, and measurable workflow effects. They support this emphasis, but they are a small sample of changing role requirements, not a hiring prediction. [OpenAI FDE](<https://openai.com/careers/forward-deployed-engineer-(fde)-sf-san-francisco/>), [OpenAI Forward Deployed Software Engineer](https://openai.com/careers/forward-deployed-software-engineer-seattle-seattle/), [Anthropic FDE](https://job-boards.greenhouse.io/anthropic/jobs/5391016008).

### Package what is already distinctive

| Artifact | What it should prove | Acceptance check |
| --- | --- | --- |
| One-page case study and current README | User problem, supported scope, model/code boundaries, one outcome and one limitation | A peer can explain the project after two minutes without reading milestone history |
| One-command offline replay | Evidence-bound engineering and practical handoff | Another engineer runs the declared path with permitted artifacts and no credentials |
| Success and failure trace cards | Decisions are inspectable, failures are diagnosable | One mixed journey plus its unresolved conditions; one minimized parsing failure and exact regression evidence |
| Evaluation scorecard | Measurements are relevant and honest | Separate tasks, trials, candidate records, offline checks, live diagnostics, and human outcomes |
| Observed task comparison | The tool earns its place in a workflow | All attempts and remaining manual work recorded; a justified keep/change/drop decision |
| Three owner-written decision explanations | Personal understanding and leadership | Explain the tradeoff, rejected alternative, AI assistance, evidence, and what would change the decision |

The `gfly` empty-price case is particularly strong: an empty price vector could crash parsing; a narrowly pinned compatibility correction preserved all eight captured itineraries, including one with unknown price. Demonstrate it only after repairing the referenced local environment, or present the historical evidence explicitly as historical. The intent wire-contract failure is a second useful case: schema integration can look like poor model reasoning, and a narrow fix does not establish broad semantic quality. [Provider failure/fix record](../build-log/2026-09-23-gfly-investigation-and-live-gates.md), [intent record](../build-log/2026-09-11-initial-intent-semantic-redesign.md).

The current README obscures progress: the opening emphasizes the early request slice, another passage says ranking remains future work, and the corpus count still says two while there are three runs. Refreshing that entry point has higher portfolio value than adding another framework. Preserve history behind links rather than asking a reviewer to reconcile it. [README](../../README.md).

### Use a seven-minute demonstration

| Time | Content |
| --- | --- |
| 0:00–0:45 | The traveler job and supported one-way scope |
| 0:45–1:30 | Model/deterministic/provider boundaries and one clarification or correction |
| 1:30–3:00 | Labeled replay of one award-plus-egress option, with ticket separation and partial coverage |
| 3:00–4:00 | Why an attractive conditional option and an absent cost winner stay uncertain |
| 4:00–5:15 | A minimized failure, diagnosis, narrow fix, and regression proof |
| 5:15–6:15 | Evaluation results with denominators and one unresolved AI failure |
| 6:15–7:00 | Owner decisions, task-study learning when available, and the next justified change |

Until Results exists, show its contract as design, not a working answer. Afterward use a real rendered result. Do not stitch unrelated saved stage outputs into an implied single live execution. Keep a permitted offline path available instead of depending on fresh inventory or credentials during an interview.

Defensible draft wording, subject to the owner's confirmation of personal contribution:

> Designed and implemented, with AI coding assistance, a local one-way award-search workflow with bounded LLM decisions, deterministic validation, provider execution, and replayable evidence.

> Built and verified captured-search replay for three plan-linked provider runs, preserving partial coverage and unknown price scope through journey matching and solution styles.

Do not claim search-time reduction, fare savings, customer adoption, production reliability, or personal diagnostic work that has not been demonstrated. Prepare to explain why a model belongs in one boundary but not another, what invalidates a recommendation, how a failure is reproduced, and what would cause removal of an LLM call. Authentic contribution and transparent assistance are also consistent with [Anthropic's candidate guidance](https://www.anthropic.com/candidate-ai-guidance).

### Demonstrate prediction and diagnosis beyond the prepared demo

The next portfolio exercise should test whether the owner can predict a changed case and choose a falsifying experiment. Repository artifacts cannot establish personal understanding or historical authorship. These are proposed learning/interview prompts, not an assessment already performed.

| Scenario | Evidence of a strong answer |
| --- | --- |
| A semantically ambiguous request reaches a valid plan | Trace backward to the earliest unsupported interpretation; distinguish source grounding from correct meaning; specify a clarifying contrast before changing a prompt |
| A validator and its producer agree on a wrong result | Identify their shared dependency, retain real independent checks, and design a hand-labeled fault plus valid control |
| Premium cabin disappears, an airport is absent, or a date is misread | Choose adapter, catalog, semantic, policy, or oracle investigation from the actual evidence; do not prescribe a stronger model for every symptom |
| Stakeholder asks to divide an unknown cash quote by two | Distinguish query party, returned traveler evidence, quantity scope, inventory, and bookability; name the contract needed to justify arithmetic |
| Eight transport attempts must cover summaries, details, and duplicates | Explain a versioned allocation, full accounting, deadline/partial behavior, and why replay cannot invent responses from unqueried alternatives |
| A real user needs a return, one particular points program, and no separate ticket | Discover the actual job, expose scope fit, define a useful narrower task only with explicit agreement, and accept rejection as evidence |
| A ready request changes while acquisition is running | Predict current rejection, then propose a new revision protocol with atomic changes, preserved unsupported scope, and stale-result suppression |
| All Results slots exist beside misleading assurance or inside comments | Separate factual substitution, visible disclosure, semantic truth, and safe rendering; show what each grader can and cannot establish |

Use a 90-minute rehearsal: 10 minutes explaining boundaries from memory; 20 tracing one failure; 15 predicting a new contrast and oracle; 20 handling a changed requirement or budget; 15 on discovery/misleading output; 10 recording assistance and learning gaps. Use an unseen counterfactual chosen by a peer, with open-book inspection after the first prediction. Stop unsupported claims immediately. If core distinctions remain confused, teach those rather than adding more scenarios. A later new case can show learning; memorizing the same trace cannot.

Choose the investment objective explicitly. For **portfolio evidence**, finish a reproducible end-to-end example and an independently explainable failure; a small real-user integration may then add more evidence than another internal subsystem. For **personal utility**, continue when the owner voluntarily reuses the tool and saves net effort including maintenance. For an **external product**, require task-fit, fair incumbent comparison, repeat use when new real trips arise, and viable access/operating costs before expanding delivery. These are different continuation tests; a successful engineering project need not become a competitive consumer service.

## Prioritized iteration plan

This revised sequence brings opportunity discovery forward and places demonstrated contract gaps ahead of stronger claims. It is an advisory plan within existing gates, not implementation authorization. The owner should select the objective and experiment limits before execution.

| Priority and timing | Work | Acceptance evidence and stop rule | Existing scope |
| --- | --- | --- | --- |
| Start now, alongside Results | Observe recent real tasks; choose positioning, decision handoff, or another evidenced job; compare an honest prototype with the incumbent workflow | Repeated specific pain, supported task fit, correct next action; narrow/stop if the proposed job is absent. A prototype does not prove automated benefit | D14, core product hypothesis |
| Before premium-economy support claims | Confirm provider vocabulary, add canonical cabin mapping at the adapter, preserve raw values | Four-cabin contract matrix; premium survives filtering and reaches the expected add-on; real-response uncertainty resolved for the claimed endpoint | G04; narrow Provider correction |
| Before trusting imported matching decisions in Results | Define M1 artifact authority; prefer scoped versioned M1-owned requirement verification | Seeded missing blockers rejected; original valid controls accepted; exact historical policy dispatch; no claim of broader revalidation than implemented | G03/G05 |
| With Results M1/M2 | Finish compact input, LLM-authored templates, visible factual conditions, single substitution, explicit failure and attempt policy | Intact variants, maximum five complete alternatives, safe rendering, truthful partial/empty/failure behavior, measured cleaned input | Results core, G03/G06 |
| With Results M3 and existing eval maintenance | Add independent semantic oracles, exercised-family manifest, valid controls, and calibrated final-document judging | Demonstrated seeded faults detected; clean alternatives accepted; missing families reported as unexercised; writer/judge failures retained | Results core, G01/G03/G04/G05 |
| Before a dependable complete conversational claim | Reproduce false readiness, address approved narrow fixes, expose current editing limits; compose stages through one shared local coordinator | Current contrast/trajectory evidence, immutable revision lineage, one continuous request-to-answer path and fault path; no evaluator-only application logic | G01/G03/G06 |
| At the first useful pilot | Make the declared offline path reproducible; run the complete-task comparison | Another person runs it; a predeclared supported task saves total effort including checking; all failures/assistance recorded | G05/G07, D14, core completion |
| Select one next bottleneck | Narrow Aeroplan cost projection, cash-scope evidence, coalesced requests/detail scheduling, or topology-focused execution | Source/assumption meaning versioned; independent arithmetic or equal-budget task comparison; stop changes with no useful gain | G04, D02/D06/D16 |
| Only for an evidenced delivery need | Open the smallest useful private/public app mode | Provider access/display terms, deadlines/cancellation, ownership, safe output/logging, quotas, and observed operation | D11, G05–G07 |

The first four rows can be scoped in parallel; they do not demand a large pre-Results rewrite. A narrowly disclosed replay demo can use reviewed frozen inputs while broader conversation remains unqualified. If cost evidence or acquisition prevents the first useful task, pull that bounded investigation forward. Preserve stage closures and old immutable artifacts; revisions require new policy/adapter identities and explicit evidence.

Use one experimental backlog, not an instruction to implement every suggestion. The shared coordinator and declared import contract reduce ambiguity at necessary integration boundaries. Worksheet/contextual clarification, shared calendar primitives, historical-code retirement, and different provider allocation remain alternatives to test. Neither RAG nor autonomous control is a prerequisite.

For each chosen change, write a short acceptance packet: triggering example; present behavior; proposed behavior; affected contract/policy; one negative and one valid control; exact commands/artifacts; measurement and stop rule. Prefer an independently expected outcome over another self-generated baseline. Where no implementation change is justified, a documented keep decision is a valid result.

The remaining owner choices are the primary investment objective, target job, interpretation of narrow price evidence, imported-artifact trust policy, Results failure/deadline settings, and study/delivery scope. This review recommends directions; it does not record those choices as adopted.

## Evidence and limits

Twelve specialist agent reviews across two rounds informed this synthesis. The first covered product, production AI/eval, FDE hiring, critical engineering, reliability/security, and UX. The second added cross-stage correctness, evaluator adversarial testing, provider semantics, competitive product strategy, a smaller architecture counterproposal, and an FDE interview/ownership audit. A worker packaged and independently reran the supplied offline probes. These were simulated professional roles, not employer/customer interviews. The parent integrated findings and adjudicated their scope; agent agreement is not independent human qualification.

Review scope included current repository policy/state, relevant workbook sections, ADRs, latest Results proposals, actual provider/ranking artifacts, active code and tests, packaging, and development history. The workbook was read only. External sources were searched and opened on October 3, 2026; recommendations derived from them are labeled as this review's application-specific judgments. Source pages can change.

Fresh verification is recorded in the [session build log](../build-log/2026-10-03-built-stages-review.md). No runtime implementation, provider acquisition, live model evaluation, user study, deployment, or stage qualification was performed. Local replay tests establish reproducibility on this environment; they do not establish current inventory or clean-install success.

| Fresh check | Result |
| --- | --- |
| First-round full offline pytest suite | 604 passed, 2 failed, 99 skipped; both failures are in the incomplete local `gfly` environment; unchanged runtime source was not broadly retested in round two |
| Provider and Ranking M2 corpus verifiers | All three provider runs and all three ranking cases passed |
| Current planning golden CLI | 4/4 locally; tracked-only export failed for missing catalog manifest |
| Ruff | One unused test binding |
| Mypy | 308 errors in 22 files; these are typing findings, not 308 demonstrated runtime failures |
| Second-round targeted matching checks | 5 passed, 21 deselected; covers selected stale/fanout/transfer/cabin controls |
| Second-round counterexample scripts | Three scripts reproduced the cabin behavior and four seeded evaluator blind spots; packaged reruns matched recorded outputs exactly |
| Review documentation | Matching sections, local links, and whitespace checks; independent integration review distinguishes actual behavior, seeded faults, and proposals |

These pre-existing failures were recorded, not fixed in a review session. The [evidence manifest](evidence/2026-10-03-built-stages/manifest.json) preserves commands, input/output hashes, synthetic/seeded provenance, and limits. The probes require the declared local dependencies/artifacts; packaging them does not resolve clean-install portability. The build log distinguishes first-round suite results, new targeted checks, and direct calls to test bodies under mutation. No aggregate pass rate combines these different experiments.

Known evidence limits remain explicit: three closely related saved requests; no observed complete cost reference; no implemented Results output; no user-benefit measurement; no external handoff success; historical semantic diagnostics without a fresh broad live rerun. The most useful next artifact is a completed, measured traveler task, not another architecture diagram.
