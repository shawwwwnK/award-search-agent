# Deferred work — finish the core workflow first

Last reviewed: 2026-10-04.

This is the living register of work we are deliberately not doing now. Revisit an entry when its trigger is met; that means decide whether to build, narrow, or drop it. It does not mean automatically implement everything here.

For this register, **core complete** means one declared one-way award workflow reaches real award
observations, validates them, adds a bounded direct-cash value anchor, and returns a
source-attributed award shortlist under a bounded search budget, with correct empty/partial behavior
as well. A validated award-led cash-positioning option may appear when the evidence supports it; a
pure-cash itinerary is not part of the ranked award list. The completion criterion requires at
least one predeclared owner-relevant task yielding a supported actionable award or award-led option
with less total owner effort than the current workaround; only producing cash anchors, caveats, or
empty/partial outcomes is insufficient. Report all pilot tasks, and do not treat one positive
example as reliability qualification. It does not require worldwide coverage, every possible
request, RAG, a cash-only product, or a public service. This owner-approved cut is recorded in
[ADR 0022](docs/adr/0022-award-first-cash-observations.md); its positive-task discipline was refined
by the [fresh Astra challenge](docs/build-log/2026-09-19-future-stage-astra-challenge.md).

Current focus: search planning is owner-complete as of 2026-09-21, Provider Stage is
owner-complete as of 2026-09-23 for its typed, replayable `ProviderResultSet` boundary, and
Ranking Stage M1/M2 is owner-closed as of 2026-10-02 for its declared matching/validation and
solution-style boundaries. The [Provider Stage closeout](docs/handoffs/2026-09-23-provider-stage-closeout.md)
and [Ranking Stage closeout](docs/handoffs/2026-10-02-ranking-stage-closeout.md) record their
accepted scopes and limits. Results Stage (previously Output Stage) is owner-opened for design on 2026-10-02; see the
[opening record](docs/handoffs/2026-10-02-results-stage-opening.md). ADR 0023 adopts and owner-qualifies M2A with the completed M1,
M2B, and M2C planning boundaries; independent corroboration remains future policy evidence.
This register does not reopen 2B or override active ADRs. The [project state](docs/project-state.md)
and [completed milestone record](docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md)
retain their authority.

**Quick cut:** Provider Stage returns a replayable `ProviderResultSet` with bounded award and
cash observations. The closed Ranking Stage assembles bounded award-led journeys and organizes
them into deterministic solution styles; Results Stage is now open for user-facing presentation/explanation design. Later, consider upstream
simplification, general component assembly, round trips, cash-only
product scope, points, RAG, wider coverage, persistence, adaptive control, and deployment. User
feedback is not postponed until everything is finished; the detailed entries below preserve the
conditions and evidence.

**Sequencing recommendation disposition:** the revised [future-stage review](docs/reviews/2026-09-19-future-stage-goals.md)
proposes comparing a narrow baseline pilot against the current workaround, then testing frozen
reviewed supplemental query bundles before deciding how much 2C to automate. The owner instead
authorized the full bounded compiler with all-selected-endpoint coverage. Progressive coverage was
not adopted. The proposed current-workflow comparison remains useful for the downstream pilot;
other sequencing recommendations and closed/deferred stage statuses remain unchanged.

## Keep on the path to the first complete workflow

These are remaining core work, not optional items to postpone until after completion:

- **2C compilation — completed 2026-09-19; provider-neutral revision 2026-09-20:** mandatory endpoint
  coverage, complete replay-valid representable supplemental hypotheses, deterministic semantic
  deduplication, replay identity, and explicit positioning and separate-ticket obligations are
  implemented. The 100-pair structural guard is all-or-nothing; provider execution budgets are
  downstream. This completion does not satisfy provider/result gates.
- **Provider Stage — completed 2026-09-23:** narrow Seats.aero and pinned `gfly` adapters,
  bounded execution, source-attributed observations, truthful partial/empty/error behavior,
  and replayable coverage receipts. This is not provider or recommendation qualification.
- **Ranking Stage M1 candidate validation — owner-complete 2026-09-30:** the accepted
  `MatchedJourneySet` boundary validates intact awards and one plan-backed cash access or
  egress component, preserves unknowns and all scoped pairings, and keeps direct cash separate.
  The five admitted `award_cash_egress` journeys in `sfo_to_bkk_positioning` supply the live
  positive case. Owner qualification applies to this boundary; broader provider reliability,
  bookability, and full-workflow usefulness remain unclaimed. See the
  [M1 closeout](docs/handoffs/2026-09-30-ranking-m1-closeout.md).
- **Ranking Stage M2 and Results Stage:** M2 solution-style policy was owner-approved on
  2026-10-01 and locally implemented with offline saved-corpus replay. The owner closed Ranking
  Stage on 2026-10-02 for its declared M1 matching/validation and M2 solution-style boundaries;
  the closeout does not establish broader provider, bookability, observed-cost, or full-workflow
  qualification. Results Stage is owner-opened for design on 2026-10-02 and may choose presentation breadth with a separate cash
  baseline; a supported empty result must not be padded with invented options. See the
  [Results v1 discussion draft](docs/handoffs/2026-10-02-results-stage-v1-design.md), which
  records the owner's high-level direction and reviewed engineering proposals. The
  [October 4 review](docs/reviews/2026-10-04-results-stage-design-review.md) aligns model-owned
  structure across M1/M2/M3 and makes source/visible-condition/call/evaluation gates explicit. See the
  [M2 policy and draft contract](docs/handoffs/2026-10-01-ranking-m2-styles-contract.md) and
  [stage closeout](docs/handoffs/2026-10-02-ranking-stage-closeout.md).
- **Early feedback:** an owner walkthrough can start with labeled mock/replay output before full 2C qualification, then repeat with real pilot evidence. Record usefulness and remaining work. External observation requires consent and safe evidence.

Sources: [planning completion map](docs/handoffs/2026-09-12-search-planning-design.md#9-what-remains-after-this-design), [2B closeout](docs/handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md), [architecture recommendations](docs/reviews/2026-09-19-search-planning-architecture-review.md#9-recommended-sequence). Earlier provider feedback is advisory. The existing roadmap already makes RAG and coverage evidence-driven.

## Gates that cannot be postponed past their associated claim

These can be outside the current stage without disappearing into an indefinite backlog.

| ID | Gate | Latest safe point to resolve | Required evidence / source |
| --- | --- | --- | --- |
| G01 | Current supported intent/clarification behavioral qualification | Before claiming dependable conversational input; 2C can use reviewed frozen requests | Current holdout covering ambiguity, corrections, and partial answers. The 2026-09-20 active-corpus end-to-end trial recorded 13/19 Intent passes, including an unsafe ambiguous-departure ready/plan result and two pending outcomes; it is diagnostic evidence, not qualification. ADR 0015's unsafe return cases are historical, not demonstrated current supported-path defects; ADR 0016 changed that scope. [Historical closeout](docs/handoffs/2026-09-10-adr-0015-stage-closeout.md), [current intent evidence](docs/build-log/2026-09-11-initial-intent-semantic-redesign.md), [end-to-end diagnostic](docs/build-log/2026-09-20-intent-to-search-planning-evaluation.md), [improvement-plan measurement and evidence limits](docs/reviews/2026-09-19-intent-clarification-improvement-plan.md#6-measure-the-whole-task-then-diagnose-the-boundary). The post-core redesign does not defer this claim gate. |
| G02 · completed 2026-09-21 | M2A owner qualification | Completed when the owner monitors and reviews the M2A build and results for its declared endpoint-selection boundary | The owner explicitly adopted and qualified M2A on 2026-09-21, alongside the completed M1, M2B, and M2C planning boundaries. Selection provenance remains model-proposed, not catalog fact. Independent external review, a preregistered holdout, and useful-coverage-versus-work comparison are unclaimed corroboration for future policy revision, not prerequisites to this completed owner qualification. [ADR 0023](docs/adr/0023-adopt-m2a-and-retire-m0-endpoint-selection.md), [M2A handoff](docs/handoffs/2026-09-17-m2a-llm-endpoint-airport-selection.md). |
| G03 | Typed requirements and actual constraint enforcement | Before claiming that a hard requirement filters searches or is satisfied by a recommendation | Typed value/provenance/correction contract and tested filter/validation mapping; otherwise visibly unresolved. The [second review](docs/reviews/2026-10-03-built-stages-deep-review.md#give-composed-work-and-semantic-checks-clear-owners) reproduces a seeded omission of required M1 reasons accepted downstream; define imported-artifact authority and test source-required conditions independently. This is an acceptance/oracle gap, not an observed normal-producer failure. [Planning completion map](docs/handoffs/2026-09-12-search-planning-design.md#9-what-remains-after-this-design). |
| G04 | Provider capability semantics, freshness, and result validation | Before presenting provider observations as satisfying the supported travel request or supporting observed-cost comparison claims | Accepted request/response contract, success and failure fixtures, actual supported evidence, no invented availability/bookability. Observed M2 cost comparison additionally needs supported traveler price scope, units/currencies, and a sufficiently complete reference; all three saved runs currently lack that reference. This does not block their declared schedule/cabin style assignments or turn tax estimates into source evidence. The [second review](docs/reviews/2026-10-03-built-stages-deep-review.md#correct-the-provider-cabin-boundary-before-extending-its-claim) reproduces a premium-token normalization gap and proposes its narrow contract matrix. Official trip documentation may support a separately versioned 17-record direct-Aeroplan cost projection; no quote scope or acceptance claim changed. [Provider intake](docs/provider-feasibility/2026-09-08-initial-provider-intake.md), [M2 evidence limits](evidence/ranking-stage/m2/README.md). |
| G05 | Reproducible reviewer verification and truthful quality gates | Before claiming a clean-checkout handoff or reproducible evaluation, not every local preview | Reproduce the declared command with exact permitted artifacts/dependencies and a passing scoped gate. The 2026-10-03 current planning golden passes 4/4 locally but a tracked-only export fails because its local catalog manifest is absent; this supersedes the historical missing-provider-document mechanism. Broad mypy reports 308 errors in 22 files, ruff reports one unused test binding, and two gfly compatibility tests fail on the incomplete pinned local environment. These checks do not invalidate saved-corpus replay or prove a fresh installation works. [Preserved seeded probes](docs/reviews/evidence/2026-10-03-built-stages/manifest.json) additionally motivate independent requirement/cost oracles and exercised-family acceptance manifests; byte integrity, schema validity, and nonempty claim coverage are distinct. Whole-repo cleanup/CI are not prerequisites for a narrower disclosed demo. [Fresh review and checks](docs/reviews/2026-10-03-built-stages-deep-review.md#engineering-and-operational-readiness). [Engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| G06 | Operational attempt/deadline bounds and safe partial outcomes | Explicit finite retry/timeout/page policy for live integration; composed deadlines before an end-to-end bound claim | Distinguish SDK invocations, repairs, HTTP attempts, and pages; test exhaustion and partial results. One offline SDK invocation made three HTTP attempts: initial plus two retries. The 2026-10-03 review confirms active model adapters inherit installed SDK timeout/retry defaults; whole-request deadlines and exhaustion checks remain proposed under this gate. [Current review](docs/reviews/2026-10-03-built-stages-deep-review.md#engineering-and-operational-readiness). [Engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| G07 | Privacy-safe evidence and honest demonstration | Before sharing traces or opening a recruiter-facing demo | Sanitized/synthetic public replay, no credentials/private travel, declared live-versus-replay mode, source permission check, clear current limitations. [Evidence rules](evidence/README.md), [trace implementation](src/award_agent/observability/llm_trace.py). |

These are scoped gates, not a requirement to complete every future feature before demonstrating a narrower, explicitly limited slice. G05–G07 consolidate engineering recommendations from this review; they do not silently establish new runtime policy.

## Parked features and conditional follow-ups

Status legend: **parked** means an existing deferral; **proposed** means a new review recommendation awaiting a decision. “Recorded” sources establish scope or a remaining issue; a proposed redesign is still a recommendation even when it addresses a recorded issue.

Most features wait for core completion. D02 and D14 intentionally start gathering evidence at the first pilot; do not postpone learning until all implementation is complete.

The owner-requested [future-stage goal review](docs/reviews/2026-09-19-future-stage-goals.md)
refines the recommendations under the existing IDs; all remain parked/proposed:

- **D02:** compare against the owner's current workflow; use frozen reviewed bundles to isolate
  strategy value before automation. Distinguish completed-option yield from useful-lead yield,
  count human preparation/checking, and do not score unqueried alternatives as empty.
- **D06/D15:** observed-option output can precede personal redeemability and component assembly;
  any stronger claim must first satisfy the corresponding eligibility/journey evidence.
- **D07:** use a demonstrated decision or authoring gap to choose structured, lexical, or hybrid
  retrieval; dropping an unnecessary RAG mechanism is an acceptable disposition.
- **D08:** record coverage gaps during the pilot, while keeping broad expansion conditional;
  measure useful tasks unlocked and added work rather than entity counts alone.
- **D09:** compare finite next-action control against deterministic ordering; delaying optional
  gateway generation is a proposed future workflow experiment, not an approved change to 2B/2C.
- **D14:** use a predeclared task rubric and current-workflow comparison, with a positive actionable
  option and all pilot failures reported. Choose a finite timebox and handoff target. The proposed
  pilot before full supplemental 2C automation needs an owner sequencing decision.

This supplements the sources and completion evidence below without changing any entry's status
or automatically satisfying its revisit trigger.

| ID / status | Work to revisit | Revisit trigger | Evidence needed to close it |
| --- | --- | --- | --- |
| D01 · proposed; improvement plan challenged and revised | Diagnose friction in an actual travel decision, then selectively improve interpretation, context, presentation/editing, or recovery; no shared-schema or correction-framework rewrite by default | Owner requested implementation remain deferred until after the core project; revisit when better understanding could reduce a real task's effort/error. Pull forward only scoped work needed for G01/G03 claims | Follow the [revised improvement plan](docs/reviews/2026-09-19-intent-clarification-improvement-plan.md): start with one observed task and an existing failure, compare the owner's actual workflow, separate qualifying options from prospectively defined leads, and distinguish upstream errors from scope/data limits. Expand evidence as needed; one observation is not qualification. Choose one useful comparison or retain upstream unchanged. Preserve date/state/provenance guarantees; G01/G03 remain separate. Context, alternatives, post-ready editing, and shared semantics are options, not a checklist. The [second review](docs/reviews/2026-10-03-built-stages-deep-review.md#compare-a-materially-smaller-interaction-design) proposes comparing current clarification, compact resolved-state context, and natural-language prefill plus editable fields; current READY remains terminal and no new correction authority is adopted. Scope recovery and adaptive control remain D04/D09. No implementation or policy adoption follows. |
| D02 · proposed | Measure whether gateway supplements and larger endpoint selections earn their cost; restrict/remove them if not | First provider pilot for observation yield; completed-journey comparison only when that journey type is supported | Same maximum budget, useful evidence/work, duplicates, latency, and human review. Hub component hits are not validated shortlist lift. The [2026-10-03 review](docs/reviews/2026-10-03-built-stages-deep-review.md#engineering-and-operational-readiness) additionally proposes within-run physical cash-query coalescing and equal-budget detail scheduling experiments, preserving activation provenance and old replay policies; the second pass also measures ten hub-only award transports across the three saved cases whose components current M1 cannot assemble. Compare complete-journey and research-lead value separately; no execution change is adopted. This evidence may inform future M2A cap/policy revision; it is not a qualification prerequisite. [Review §8](docs/reviews/2026-09-19-search-planning-architecture-review.md#8-experiments-that-would-change-the-design). |
| D03 · parked | Reopen 2B semantic/prompt/market policy only for demonstrated failure patterns, including same-market missed value and circuitousness | Downstream results or human review reveal material errors; explicit owner reopening | Targeted cases plus an independent review/holdout and a before/after result comparison. Do not start prompt-v7 simply because residual notes exist. [2B closeout](docs/handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md). |
| D04 · proposed | Scope recovery for trip-shaped input; linked one-way trips only if separately justified | Core complete and observed exclusion/re-entry cost establishes value; explicit ADR 0016 decision before a policy change | Compare current guidance with a reviewed mock offering explicit acceptance of a fresh outbound-only request. A displayed draft is nonexecuting; dependent facts require validation; measure remaining return work and reduced-scope recovery separately from original-task fulfillment. Linked trips additionally require parent-trip semantics, linked constraints, and independent one-way validation. [Scope-recovery option](docs/reviews/2026-09-19-intent-clarification-improvement-plan.md#scope-recovery-can-be-smaller-than-linked-trip-planning), [ADR 0016](docs/adr/0016-one-way-award-request-boundary.md). Neither option silently activates return state. |
| D05 · acquisition slice owner-complete 2026-09-23; broader cash scope parked | Provider Stage acquires direct endpoint and relevant access/egress cash observations. Cash presentation and candidate use belong to later ranking/output work. A cash-only product and broader cash/provider expansion remain parked | Remaining scope: observed user need after the later output stage and explicit owner decision | The opened acquisition slice has pinned capability, sanitized trace-derived fixtures, normalized source-attributed results, strict separate budgets, and owner acceptance. Pure-cash observations stay outside award ranking. [Provider Stage closeout](docs/handoffs/2026-09-23-provider-stage-closeout.md), [ADR 0022 amendment](docs/adr/0022-award-first-cash-observations.md#2026-09-22-amendment--provider-stage-boundary). |
| D06 · parked | Point balances, spending budgets, program access, and narrow transfer feasibility | Core complete and a real shortlisted option cannot be judged useful without these facts | Typed user inputs, sourced eligibility/ratio rules, deterministic arithmetic, explicit unknowns; no invented cross-program value. Add minimal eligibility earlier only if the core claim requires it. [Original deferral](docs/build-log/2026-08-30-defer-points-budgets.md), [review §7](docs/reviews/2026-09-19-search-planning-architecture-review.md#7-database-retrieval-and-eventual-agent-workflow). |
| D07 · parked; sequencing change proposed | Reviewed strategy-document authoring; separately consider runtime loyalty-rule retrieval | A result or explanation exposes a source-knowledge gap | Permissioned dated sources; structured/lexical comparison; citations and review. M3 is human-reviewed authoring and already has a usefulness gate; earlier provider feedback is the proposed change. [Roadmap](docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md#former-milestone-3--reviewed-strategy-documents-and-rag-assisted-authoring). |
| D08 · parked | Broader geography, airport-group/strategy coverage, richer lookup, catalog refresh/hosting | Core complete and unsupported demand or refresh cost demonstrates the need | Named gaps, reviewed new evidence, coverage/receipt diffs, regression tests, refresh/retention decision. Local source preservation is already resolved; remote hosting remains deferred. [ADR 0018](docs/adr/0018-sqlite-geographic-catalog.md), [M1 closeout record](docs/build-log/2026-09-15-m1a-catalog-publication.md#retention-correction-and-milestone-1b-closeout-2026-09-16). |
| D09 · proposed | Result-responsive model controller and evidence-driven clarification | Fixed execution ordering leaves measured value unrealized after core completion | Equal-budget comparison against deterministic actions; bounded action vocabulary, stopping rules, no constraint relaxation. [Review §7–8](docs/reviews/2026-09-19-search-planning-architecture-review.md#7-database-retrieval-and-eventual-agent-workflow). |
| D10 · parked; design proposed | Persistent sessions, query/result history, proposal caching, resume across processes | Repeated use needs history or recovery beyond a single run | Explicit retention and freshness rules, request/attempt/observation links, invalidation and recovery tests. Per-run traces and bounded fault handling belong in the core; a permanent store does not. [Review §7](docs/reviews/2026-09-19-search-planning-architecture-review.md#7-database-retrieval-and-eventual-agent-workflow). |
| D11 · parked | Deployed UI, authentication, and operational hosting | Core complete; choose a recruiting demo or actual personal-use delivery target | Safe demo data, secrets isolation, basic quotas/diagnostics, reproducible startup/deployment. The [2026-10-03 review](docs/reviews/2026-10-03-built-stages-deep-review.md#engineering-and-operational-readiness) adds advisory checks for the chosen provider access/display agreement, safe authored Markdown, private trace retention, cancellation/revision-safe publication, and shared admission limits when external use is opened. Demonstrate a smaller replay/local handoff first; deployment claims require actual deployment. [Current non-goals](AGENTS.md#current-non-goals), [engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| D12 · proposed | Broad historical-code retirement and contract simplification | Core complete and active entry points/tests are clearly identified | Active import/command map, preserved tagged historical artifacts, migration/regression evidence, passing active quality gate. Fix G05's declared gate earlier; avoid a wholesale refactor now. [Engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| D13 · proposed | Scale/performance and concurrency beyond one bounded workflow | Measured resource or concurrent-user demand after core completion | Representative load profile, bottleneck evidence, tested improvement with correctness preserved. No inferred enterprise scale from catalog row count. [Engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| D14 · proposed | Owner/user feedback, personal AI-engineering learning, then a concise evidence packet and independent handoff | Owner mock/replay walkthrough before full 2C qualification, repeated at pilot; reuse an existing failure for personal explanation; external observation when safe and available | Record the actual task/effort and a justified keep/change/drop decision; do not require a new feature or design change. The [2026-10-03 review](docs/reviews/2026-10-03-built-stages-deep-review.md#traveler-experience-and-product-value) proposes separate frozen-presentation comprehension/omission studies and counterbalanced full-workflow comparisons, including rechecking, failed tasks, and assistance; sample sizes and stop rules are recommendations, not accepted gates. The second pass brings opportunity discovery alongside Results, compares documented incumbent workflows, distinguishes portfolio/personal/external objectives, and adds an owner prediction/diagnosis rehearsal; none is a measured user or hiring outcome. Personally explain one failure/fix and assess an adjacent requirement, recording assistance and gaps. A later engineer's replay/handoff is distinct from customer adoption; self-directed work does not establish enterprise delivery. G05 applies to reproducibility claims; G07 to sharing. [FDE preparation](docs/reviews/2026-09-19-intent-clarification-improvement-plan.md#ai-engineering-and-fde-preparation), [engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| D15 · one-cash slice owner-complete 2026-09-30; wider topology parked | Ranking Stage may assemble one cash access + award or award + cash egress journey. The owner wants eventual cash access on **both** ends of one award when useful, but that three-component topology, hub substitution, airport changes, and general assembly remain deferred. Provider Stage only acquires component observations | Revisit the both-ends case when a real award option needs both cash legs and the one-cash Ranking Stage boundary is demonstrated; require an explicit versioned topology decision before implementation | The one-cash slice is owner-qualified under the [M1 closeout](docs/handoffs/2026-09-30-ranking-m1-closeout.md), with chronology, continuity, original departure, traveler/cabin treatment, positioning, self-transfer buffer, and separate-ticket receipts. For both ends, add separate validation of each transfer, whole-journey date/time and cost scope, fanout, and evidence from both cash searches. Never present component prices as a protected through-ticket claim. [Ranking Stage design](docs/handoffs/2026-09-25-ranking-stage-design.md), [ADR 0022 amendment](docs/adr/0022-award-first-cash-observations.md#2026-09-22-amendment--provider-stage-boundary). |
| D16 · owner-complete 2026-09-23 for Provider Stage boundary | Provider execution maps the complete M2C graph to bounded physical award and cash queries, and returns a typed, replayable `ProviderResultSet` with parsing, normalization, conservative deduplication, findings, resource accounting, and exact coverage receipts. Runtime rectangle batching remains disabled | Reopen only for a demonstrated execution defect or an explicit provider policy revision | Completed evidence: trace-derived sanitized captures including Qatar/DOH unknowns, a sampled 2 × 2-versus-singleton comparison, cash and hard-stop fixtures, pagination and failure outcomes, a fresh combined live task, byte-identical replay, independent review, and owner acceptance. This does not qualify provider reliability or enable runtime batching. [Provider Stage closeout](docs/handoffs/2026-09-23-provider-stage-closeout.md), [ADR 0021 amendment](docs/adr/0021-deterministic-search-strategy-compilation.md#2026-09-20-amendment-provider-neutral-compilation-and-structural-safety). |
| D17 · parked; ownership approved 2026-09-20 | Clean up misplaced intent/clarification artifact constraints. Request-expression constraints must be resolved upstream through omission or clarification with explicit user correction; 2C assumes the frozen request is valid | Reopen upstream intent/clarification maintenance or before claiming ownership is fully enforced across active artifacts | Audit and remove misplaced 31-day fixture/expression constraints without adding a 2C window cap; tests must prove invalid or ambiguous expressions stop or clarify upstream and valid finite windows, including more than 31 days, pass to 2C unchanged. Preserve ADR 0016/0017 state, provenance, and correction authority. [Revision record](docs/build-log/2026-09-20-m2c-provider-neutral-revision.md). |
| D18 · parked 2026-09-25 | Extend positioning cash acquisition beyond its current same-local-date sample to prior or following dates, including flights that enable a next-calendar-day connection. Ranking Stage initially matches only observations actually acquired; allowing a next-day connection does not imply that such flights were searched | Revisit when a reviewed award option needs positioning on another date that same-day acquisition misses, or before claiming next-day positioning-search coverage | Versioned bounded date-window and budget policy; exact sampled/omitted-date receipts; replay fixtures for access before and egress after the award date, timezone/date-line cases, original-departure compliance, provider failures, and incremental useful options versus added work. [Ranking Stage design](docs/handoffs/2026-09-25-ranking-stage-design.md), [current execution](src/award_agent/providers/execution.py). |

## Deliberate non-goals, not promises for later

- Multi-agent product orchestration or an agent framework without a measured need.
- Vector/graph databases, Kubernetes, microservices, or multi-user scale for recruiting keywords alone.
- Exhaustive provider/route coverage, inventory guarantees, automatic booking or points transfers.
- Broad card strategy, whole-trip concierge features, and ongoing inventory alerts without a new product decision.

These can be reconsidered only with a new demonstrated problem and explicit scope decision. The register does not commit the project to them.

## Do not resurrect completed or superseded tasks

- M1 source acquisition, lossless retained-row preservation, and local serving are complete. Remote hosting is a separate deferred question.
- The 35 reviewed catalog reconciliation quarantines are accepted limitations, not an automatic backlog to eliminate.
- The old scanner/selector workflow and its defects are historical; they are not the active intent architecture.
- The provider-wire shape correction and narrow initial reasonable-input reliability gate are complete. Broad behavioral qualification remains G01.
- 2B is owner-closed. The current v6 diagnostic is development evidence; lack of human qualification is not permission to resume prompt iteration.

## Maintenance rules

1. When a session discovers or changes a deferral, update this register and link the relevant decision/build log. Preserve the stable ID; do not create another competing TODO list.
2. Keep scope and authority explicit: recorded deferral, new recommendation, or owner-approved reopening. Adding a recommendation does not approve it.
3. At stage closeout, review entries whose triggers may now be met. Choose keep parked, open, complete, or drop; record why and link evidence. For bundled entries, explicitly dispose of individual options under the same ID rather than requiring all of them. Do not auto-open a closed stage.
4. Never park a known safety/correctness obligation beyond the claim that depends on it. Put it in the gate table and narrow the claim instead.
5. When work is opened, link its active plan/workboard entry. When finished or dropped, retain its ID in the disposition history with the date and evidence; do not erase the decision.

Disposition history: 2026-09-19 — created from build logs and current decisions; revised after fresh-context Astra challenge to correct historical/current evidence, narrow gates, move D02/D14 feedback earlier, and add D15. All entries remain parked/proposed; no implementation or adoption follows from this register.

2026-09-19 — future-stage goal review refined D02, D06–D09, D14 and D15 as documented above.
The owner requested strategic analysis; no entry was opened, completed, dropped, or adopted.

2026-09-19 — the owner's fresh Astra challenge strengthened the advisory completion criterion,
added the current-workflow comparison and finite stop rules, and proposed testing reviewed bundles
before committing to full supplemental 2C automation. See the
[debate record](docs/build-log/2026-09-19-future-stage-astra-challenge.md). The conflict with current
mandatory 2C scope is explicit; no parked entry, runtime policy or roadmap decision was adopted.

2026-09-19 — at the owner's request, expanded D01 into a dedicated [intent and clarification improvement plan](docs/reviews/2026-09-19-intent-clarification-improvement-plan.md), grounded in build logs, selected existing synthetic traces, current contracts, independent agent review, and primary engineering guidance. The owner intends to revisit implementation after the core project. G01/G03 retain their claim-specific timing; D04/D09 remain separate conditional proposals. [Session evidence](docs/build-log/2026-09-19-intent-clarification-improvement-plan.md). No runtime, prompt, evaluation, or stage reopening was performed.

2026-09-19 — the owner requested a fresh Astra challenge and back-and-forth revision of that plan.
D01 now selects an experiment from observed failure ownership rather than defaulting to contextual
corrections, and may conclude that upstream redesign is not worthwhile. D04 now distinguishes a
small explicit outbound-scope recovery prototype from linked-trip semantics. Both remain proposed;
G01/G03 are unchanged. The [debate record](docs/build-log/2026-09-19-intent-clarification-improvement-plan.md#fresh-astra-challenge-and-parent-debate)
documents semantic-authorization limits, fair comparisons, and exploratory-task measurement.

2026-09-19 — a further owner-requested real-use-case and FDE-preparation pass, followed by a separate
fresh Astra challenge, refined D01/D14. There is no assumed flexible-search niche or requirement to
add features for a portfolio story. Begin discovery with an actual task and reuse an existing
failure to practice personally owned AI diagnosis; expand evidence only for the next decision.
This is not a qualification shortcut or customer-adoption claim. See the
[record](docs/build-log/2026-09-19-intent-clarification-improvement-plan.md#real-use-case-and-fde-preparation-pass).
All entries remain proposed/parked; no implementation, scope policy, or career decision was adopted.

2026-09-19 — the owner opened Milestone 2C planning, requiring complete selected-endpoint
coverage with explicit overflow and a detailed deterministic compiler plan. The
[active planning handoff](docs/handoffs/2026-09-19-m2c-search-strategy-compilation-plan.md)
supersedes the advisory option to postpone that design; it does not authorize implementation.
D02/D14 retain the proposed early preview/pilot and task-value evidence; D15 component assembly
remains deferred. G01/G02 qualification and G03–G07 claim-specific prerequisites are unchanged.
No parked feature was implemented or adopted. [Session record](docs/build-log/2026-09-19-m2c-planning.md).

2026-09-19 — the owner subsequently authorized Milestone 2C implementation and chose in-place
replacement with no V1 compatibility path. The deterministic provider-neutral compiler is
implemented and offline verified; its integrated live diagnostic is model-only and makes no
provider call. This completes the compiler item above without satisfying provider/result gates,
adopting M2A, reopening 2B, or establishing human semantic or provider/product qualification.
[Implementation record](docs/build-log/2026-09-19-m2c-implementation.md). D02/D14 remain evidence
work for the downstream pilot, and D15 remains deferred.

2026-09-20 — the owner requested the active 19-case Intent corpus be run through clarification
state and current search planning without behavior changes. The one-trial diagnostic recorded
13/19 Intent passes, seven deterministic plans, two pending outcomes, and one safety-relevant
ambiguous-departure ready/plan miss. This supplies current evidence but does not satisfy G01's
holdout or qualification requirement; no gate or parked item changed status. See the
[evaluation record](docs/build-log/2026-09-20-intent-to-search-planning-evaluation.md).

2026-09-20 — the owner approved the provider-neutral M2C correction and assigned stable ownership
for two follow-ons. D16 places provider capability, rectangle-safe batching, execution resources,
result validation, and scheduled-versus-deferred accounting in the later provider stage. D17 places
request-expression validity and the cleanup of misplaced 31-day artifacts in intent/clarification;
2C accepts a valid frozen request and imposes no window-length limit. Both remain parked until their
stated triggers. See the [revision record](docs/build-log/2026-09-20-m2c-provider-neutral-revision.md).

2026-09-21 — after a read-only cash-source investigation and one isolated successful `gfly` smoke,
the owner approved the next award-first provider/result direction. D05 is open only for a brief
direct endpoint cash anchor and cash access/egress observations; a cash-only product remains parked.
D15 is open only for one cash access + award or award + cash egress journey; general assembly
remains parked. D16 is open for the capability-bound two-adapter execution design. This work
executes M2C's already complete search graph rather than adding a new planning milestone. Pure-cash
itineraries remain outside the ranked award list, and the active runtime is unchanged pending
implementation. See [ADR 0022](docs/adr/0022-award-first-cash-observations.md), the
[`gfly` intake](docs/provider-feasibility/2026-09-21-gfly-cash-search-intake.md), and the
[provider-stage handoff](docs/handoffs/2026-09-21-award-first-provider-results-plan.md).

2026-09-22 — the owner named the next cut Provider Stage and narrowed it to a typed, replayable
`ProviderResultSet` from bounded Seats.aero and `gfly` calls, parsing, normalization, conservative
deduplication, and complete attribution/coverage receipts. D05's acquisition slice and D16 remain
in Provider Stage. D15's opened bounded mixed assembly, along with ranking and output generation,
moves to the later stage. The owner accepted deterministic mandatory-first/progressive scheduling,
conditional exact rectangle batching, and choosing numerical provider budgets after representative
complete sanitized captures. The fixture campaign starts with actual upstream traces and includes
Qatar/DOH missing-tax field evidence. See [ADR 0022's amendment](docs/adr/0022-award-first-cash-observations.md#2026-09-22-amendment--provider-stage-boundary)
and the [revised handoff](docs/handoffs/2026-09-21-award-first-provider-results-plan.md).

2026-09-21 — the owner stated that they monitored the build and reviewed the results, and qualified
all completed search-planning milestones (M1, M2A, M2B, and M2C) for their declared boundaries.
G02 is therefore completed with its stable ID retained. Independent external/holdout corroboration
and useful-coverage measurement remain future policy-revision evidence, not an adoption or owner-
qualification gate. M0 is retired rather than a completed active milestone. See
[ADR 0023](docs/adr/0023-adopt-m2a-and-retire-m0-endpoint-selection.md).

Provider Stage implementation evidence (2026-09-22/23): D05's acquisition slice and D16 now have
local contracts, adapters, deterministic execution, replay, and offline tests. The bounded capture
campaign obtained Seats.aero summary/pagination/detail evidence and two cash successes before a
cash schema-drift stop. D16's exact rectangle experiment passed for its sampled case; runtime
batching remains disabled. A fresh combined two-provider live executor task remains an unmet
stage gate. D05/D16 are not marked owner-complete or provider-qualified. D15 remains assigned to
later ranking/output work. See the
[implementation record](docs/build-log/2026-09-22-provider-stage-implementation.md).


2026-09-23 — D05 acquisition and D16 engineering gates passed after the owner reopened bounded
investigation: a reproduced gfly empty-price failure received a narrow, reviewed compatibility
fix; all remaining cash contrasts completed; a fresh combined executor task returned four award
and four priced cash observations with byte-identical replay. All 25 graph coverage units are
accounted for (three complete, 22 budget-omitted). See the
[follow-up record](docs/build-log/2026-09-23-gfly-investigation-and-live-gates.md).
D05/D16 remain pending owner acceptance, not provider-qualified. Account quota, price/traveler
adequacy, and broad reliability remain unknown; local compatibility packaging is path-pinned.
D15 assembly and ranking/output remain later-stage work; no broader scope was reopened.


2026-09-23 — owner requested a single unambiguous reusable saved-search corpus and removal of
noncurrent historical searches. Current captures and replay evidence are consolidated under
[evidence/provider-stage/saved-searches](evidence/provider-stage/saved-searches/README.md), with
one active capability configuration. Superseded campaign artifacts are removed; minimal failure
regressions remain test fixtures. This changes evidence organization, not D05/D16 owner-acceptance
status, provider qualification, or D15 scope. See the
[consolidation record](docs/build-log/2026-09-23-saved-searches-consolidation.md).

2026-09-23 — after the Provider Stage walkthrough and review of the saved combined
`ProviderResultSet`, the owner explicitly approved finishing this stage. D05's opened
acquisition slice and D16 are owner-complete for the declared Provider Stage boundary. The
preceding pending-acceptance statements are historical. Provider reliability, bookability,
full-graph live coverage, candidate validation, and recommendation qualification remain
unclaimed. D15 assembly and ranking/output stay separately scoped; no broader cash or
provider scope was opened. See the
[Provider Stage closeout](docs/handoffs/2026-09-23-provider-stage-closeout.md).

2026-09-25 — the owner opened Ranking Stage for design, with M1 result matching and M2
deterministic heuristic ranking; model-driven Output Stage will follow separately. The owner's
manual award/Google Flights/spreadsheet workflow is the target: match every supported positioning
cash alternative to a promising award itinerary, validate the connection and whole journey, and
retain meaningful variants with provenance for later explanation. The owner selected one cash
component now, accepted retaining options with unknown price/traveler evidence as explicitly
conditional rather than silently omitting them, and accepted comparable-group heuristic ranking
and option-family grouping. Cash on both ends is a desired later topology under D15. Cash
acquisition remains same-local-date for now; earlier/later positioning searches are parked as
D18. The owner set a two-hour minimum transfer and, correcting the earlier two-night proposal,
requires the onward flight to depart on the transfer airport's local arrival date or the next
calendar date. Admission details, score weights, and fanout policy remain to be settled. See the
[Ranking Stage design record](docs/handoffs/2026-09-25-ranking-stage-design.md).

2026-09-25 — the owner required all current saved provider results to originate from frozen
search plans and requested live searches to replace standalone pairs. Two bounded plan-linked
live runs now provide timed LAX→BKK awards and same-plan SFO→LAX cash access observations.
This supplies component evidence for the opened D15 one-cash slice; it does not complete D15
journey validation, alter D18's same-day acquisition boundary, or qualify provider reliability.
See the [corpus refresh](docs/build-log/2026-09-25-plan-linked-provider-corpus.md).

2026-09-25 — Ranking M1's opened D15 one-cash slice is locally implemented with exhaustive
plan-backed matching, validation receipts, and offline saved outputs from the two current
provider runs. Owner qualification and full-workflow usefulness are not yet claimed. The
broader cash-on-both-ends and hub topologies remain parked in D15; D18's expanded acquisition
dates remain parked. See the [M1 build log](docs/build-log/2026-09-25-ranking-m1-matching.md).

2026-09-27 — the owner approved recording the gfly provider-returned `adults` query echo as
returned-traveler evidence (cash capability v2; v1 replays preserved) and ran the approved
full bounded live pipeline: a new positioning-permitted upstream case compiled through the
casebook harness (after fixing that harness's exact-single-day gateway precision defect),
bounded Seats.aero + pinned gfly execution, and M1 matching. The owner also decided the m1-v2
award-cabin rule: a confirmed matching journey-level cabin is accepted when award legs do not
report their own cabin, keeping the Seats.aero adapter unchanged. The new
`sfo_to_bkk_positioning` corpus run contributes the first live admitted mixed journeys
(five award-cash egress candidates). D15's one-cash slice now has positive journey evidence;
owner qualification, usefulness, M2, and the Output Stage remain unclaimed, and D18's
same-local-date acquisition boundary is unchanged. See the
[evidence run build log](docs/build-log/2026-09-27-ranking-m1-live-evidence-run.md) and the
[design record amendment](docs/handoffs/2026-09-25-ranking-stage-design.md#2026-09-27-amendment--m1-v2-cabin-rule-and-first-live-admitted-mixed-journeys).

2026-09-30 — the owner explicitly instructed “Close M1” after reviewing the closeout
recommendation against `sfo_to_bkk_positioning`. Ranking M1 and D15’s bounded one-cash
matching/validation slice are owner-qualified and closed. The accepted boundary retains the
current award-only cabin interpretation for separate cash positioning. D15’s wider topology
and D18 remain parked; M2 has no approved scoring weights or implementation, Output Stage
remains unopened, and full-workflow usefulness and provider reliability remain unclaimed.
See the [M1 closeout](docs/handoffs/2026-09-30-ranking-m1-closeout.md).

2026-10-01 — the owner opened M2 for deterministic overlapping solution styles and adopted
time/cost/premium policies, unified admitted/conditional comparison, explicit cost valuation
and estimates, provisional unknown-cost treatment, and two-or-more-style highlights. The
[policy and contract draft](docs/handoffs/2026-10-01-ranking-m2-styles-contract.md) preserve all
alternatives and pure cash as a separate presentation baseline. M2 core implementation remains
required, not deferred cleanup. No M2 qualification, Output Stage opening, or change to parked
D15/D18 scope follows. Earlier unapproved M2 directions remain historical.

2026-10-01 — at the owner's implementation request, M2 was locally implemented with independent
review/iteration, offline CLI, versioned USD/CAD input, source-preserving saved projections, and
replay receipts. G04 now explicitly records the observed-cost comparison evidence gap: unknown
price scope prevents a complete cost reference in all three saved requests. Synthetic tests cover
cost mechanics but do not supply live-cost evidence. M2 owner qualification, full-workflow
usefulness, and Output Stage completion remain unclaimed; no parked D15/D18 scope changed.
See the [implementation log](docs/build-log/2026-10-01-ranking-m2-implementation.md).

2026-10-02 — the owner explicitly instructed that Ranking Stage be marked closed. M1 remains
owner-qualified for its declared matching/validation boundary, and the stage is owner-closed for
that boundary plus the implemented M2 solution-style boundary. This does not add broader provider,
bookability, observed-cost-coverage, or full-workflow-usefulness claims. Unknown price scope still
prevents a complete cost reference in all three saved requests; source unknowns and conditional
status remain explicit. Output Stage remains unopened, and D15/D18 scope remains parked. See the
[Ranking Stage closeout](docs/handoffs/2026-10-02-ranking-stage-closeout.md) and
[dated closeout log](docs/build-log/2026-10-02-ranking-stage-closeout.md).

2026-10-02 — the owner instructed “Now we’re opening the results stage”. Results Stage is
open for design as the downstream user-facing stage previously called Output Stage. Its
detailed contract, presentation policy, and completion gates remain unsettled. Ranking stays
closed; G04’s price-scope gap and parked D06/D15/D18 scope carry forward. No implementation,
live evaluation, or full-workflow usefulness claim follows from opening the stage. See the
[opening record](docs/handoffs/2026-10-02-results-stage-opening.md).

2026-10-02 — the owner supplied high-level Results v1 direction and requested orchestrated
verification, investigation, and detailed architecture design. The
[discussion draft](docs/handoffs/2026-10-02-results-stage-v1-design.md) records source-field
mapping, missing cash cabin/leg evidence and endpoint rationale, grouping/variant safeguards,
fallback/input limits, and evaluation recommendations. All three saved M2 cases passed their
documented verification. Engineering choices remain proposals for discussion, not approved
implementation or new deferrals. Results core work remains required; G04 and parked D06/D15/D18
retain their current triggers and evidence requirements. See the
[design log](docs/build-log/2026-10-02-results-stage-v1-design.md).

2026-10-02 — following review, the owner accepted LLM editorial writing with code-filled data,
award grouping/conservative duplicate cleanup, and five displayed complete journeys including
alternates. Clear airline programs replace traveler-facing source presentation for current v1.
The owner expects cleaned input to fit and did not adopt a separate input cap. The owner
requested milestones and an additional LLM evaluation milestone; the
[milestone proposal](docs/handoffs/2026-10-02-results-stage-milestones.md) sequences cleaned
input, generated explanation/factual rendering, and calibrated LLM-assisted evaluation.
Failure/retry behavior and milestone details remain to be settled. Results core work remains
required; no implementation, qualification, new parked feature, or change to G04/D06/D15/D18
follows from these design decisions.

2026-10-02 — the owner requested further orchestrated investigation and detailed architecture
planning before Results implementation. The
[execution proposal](docs/handoffs/2026-10-02-results-stage-implementation-plan.md) specifies
M1/M2/M3 slices, compact/input-audit separation, same-observation duplicate rules, factual
rendering regressions, and a proposed calibrated LLM evaluation workload. Cleanup byte
measurements are incomplete exploratory prototypes, not context-fit or sufficient-input claims.
New engineering choices remain proposals; no Results runtime, qualification, input cap, or
new parked feature was added. Current G04 and D06/D15/D18 dispositions remain unchanged.
See the [planning log](docs/build-log/2026-10-02-results-stage-detailed-plan.md).

2026-10-03 — the owner clarified that Results output structure and prose must be LLM-authored,
with code filling factual blanks. The
[template refinement](docs/handoffs/2026-10-03-results-stage-authored-template.md) supersedes
the earlier assembled-answer interpretation. Tool submission versus structured output remains
a proposal. M1 preparation and M3 evaluation remain applicable; no runtime, new deferral, or
change to existing G04/D06/D15/D18 scope follows.

2026-10-03 — the owner requested an orchestrated deep review across product, AI/evaluation,
FDE portfolio, critical engineering, and additional perspectives, with current web research.
The [concise overview](docs/reviews/2026-10-03-built-stages-overview.md) and
[detailed review](docs/reviews/2026-10-03-built-stages-deep-review.md) synthesize six specialist
reviews and fresh offline verification. G05 records current handoff/check failures rather than
repeating the historical exported-CLI cause; G06 and D02/D11/D14 gain claim-specific advisory
experiments and sources. Existing statuses, owner-qualified stage boundaries, Results authorship,
and parked scope remain unchanged. No proposed experiment, user threshold, policy revision,
implementation, live evaluation, or deployment was adopted. See the
[review build log](docs/build-log/2026-10-03-built-stages-review.md).

2026-10-03 — the owner requested continued deeper review and more subagents. Six additional
specialists audited cross-stage correctness, evaluator detection power, provider semantics,
competitive product positioning, a smaller architecture alternative, and FDE ownership evidence.
A worker preserved and reran offline counterexamples in the
[review evidence pack](docs/reviews/evidence/2026-10-03-built-stages/manifest.json).
The same two review documents now distinguish reproduced synthetic behavior, seeded evaluator
faults, source-supported opportunities, and untested product hypotheses. G03/G04/G05 and
D01/D02/D14 carry the relevant findings/proposals under their existing IDs. The review recommends
source-specific cabin normalization, explicit M1 import authority, stronger independent oracles,
and earlier opportunity discovery. No runtime fixes, policy reinterpretation, quotation-scope
assignment, live qualification, external user contact, or scope expansion was performed.
Existing statuses and owner stage decisions remain unchanged.

2026-10-04 — the owner requested Results design/milestone review and explicitly reaffirmed LLM
control of output structure. Three specialist subagents verified architecture, actual contracts/
saved corpus and official LLM-call guidance. The active Results design replaces the old assembled
answer with model-authored scoped Markdown; code supplies facts/visible checks without a layout.
The [review](docs/reviews/2026-10-04-results-stage-design-review.md) adds concrete M1 import-authority
and independent-oracle prerequisites under G03/G05, and a proposed explicit Results attempt/deadline
profile under G06. These are required for their stated claims, not optional post-core cleanup.
No existing gate is closed by this design update; the narrow matching-owned verifier is still
proposed. Revisit before general imported Results acceptance (missing-condition/valid controls),
before M2 failure-handling acceptance (settled fallback policy and tested attempt bounds), and
before M3 quality claims (exercised cases and calibrated/held-out judge evidence).
Fallback breadth, model choices and numerical live budgets remain open. No new parked feature,
upstream policy reopening, runtime implementation or change to G04/D06/D15/D18 follows.
Fresh three-case M2 corpus verification and 50 focused tests passed; no Results/provider/model
evaluation ran. See the [build log](docs/build-log/2026-10-04-results-stage-design-review.md).
