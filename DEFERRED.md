# Deferred work — finish the core workflow first

Last reviewed: 2026-09-19.

This is the living register of work we are deliberately not doing now. Revisit an entry when its trigger is met; that means decide whether to build, narrow, or drop it. It does not mean automatically implement everything here.

For this register, **core complete** means one declared one-way award workflow reaches real provider observations, validates them, and returns a source-linked shortlist under a bounded search budget, with correct empty/partial behavior as well. The revised advisory completion criterion requires at least one predeclared owner-relevant task yielding a supported actionable option with less total owner effort than the current workaround; only producing caveats or empty/partial outcomes is insufficient. Report all pilot tasks, and do not treat one positive example as reliability qualification. It does not require worldwide coverage, every possible request, RAG, multiple providers, or a public service. This is a working organizational cut line, refined by the [fresh Astra challenge](docs/build-log/2026-09-19-future-stage-astra-challenge.md), not an owner-approved new runtime gate or a completion claim.

Current focus: Milestone 2C deterministic search-strategy compilation is implemented in place and
offline verified. The [implementation record](docs/build-log/2026-09-19-m2c-implementation.md)
captures its boundary and model-only integrated diagnostic. Provider execution remains the next
separately scoped core cut. This register does not reopen 2B, adopt diagnostic-only M2A, or override
active ADRs. The [project state](docs/project-state.md) and
[milestone roadmap](docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md) retain their authority.

**Quick cut:** now, use the bounded 2C output in one separately reviewed provider-backed scenario
and put the validated result in front of the owner. Later, consider upstream simplification,
component assembly, round-trip/cash, points, RAG, wider coverage, persistence, adaptive control,
and deployment. User feedback is not postponed until everything is finished; the detailed entries
below preserve the conditions and evidence.

**Sequencing recommendation disposition:** the revised [future-stage review](docs/reviews/2026-09-19-future-stage-goals.md)
proposes comparing a narrow baseline pilot against the current workaround, then testing frozen
reviewed supplemental query bundles before deciding how much 2C to automate. The owner instead
authorized the full bounded compiler with all-selected-endpoint coverage. Progressive coverage was
not adopted. The proposed current-workflow comparison remains useful for the downstream pilot;
other sequencing recommendations and closed/deferred stage statuses remain unchanged.

## Keep on the path to the first complete workflow

These are remaining core work, not optional items to postpone until after completion:

- **2C compilation — completed 2026-09-19:** mandatory endpoint coverage, bounded supplemental
  hypotheses, deterministic budgets/deduplication, replay identity, and explicit positioning and
  separate-ticket obligations are implemented. This completion does not satisfy provider/result gates.
- **One provider integration:** capability acceptance, request mapping, bounded attempts/pages/time, and truthful empty/partial/error behavior.
- **Observed results:** validate dates, provider-returned itinerary boundaries, cabin, travelers, provenance, and supported requirements. Hub components or incomplete access journeys remain research leads; automatic cross-query assembly is D15, not a first-slice prerequisite.
- **Useful output:** a small transparent shortlist and grounded explanation, including what could not be verified. A supported empty result must not be padded with invented options.
- **Early feedback:** an owner walkthrough can start with labeled mock/replay output before full 2C qualification, then repeat with real pilot evidence. Record usefulness and remaining work. External observation requires consent and safe evidence.

Sources: [planning completion map](docs/handoffs/2026-09-12-search-planning-design.md#9-what-remains-after-this-design), [2B closeout](docs/handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md), [architecture recommendations](docs/reviews/2026-09-19-search-planning-architecture-review.md#9-recommended-sequence). Earlier provider feedback is advisory. The existing roadmap already makes RAG and coverage evidence-driven.

## Gates that cannot be postponed past their associated claim

These can be outside the current stage without disappearing into an indefinite backlog.

| ID | Gate | Latest safe point to resolve | Required evidence / source |
| --- | --- | --- | --- |
| G01 | Current supported intent/clarification behavioral qualification | Before claiming dependable conversational input; 2C can use reviewed frozen requests | Current holdout covering ambiguity, corrections, and partial answers. The 2026-09-20 active-corpus end-to-end trial recorded 13/19 Intent passes, including an unsafe ambiguous-departure ready/plan result and two pending outcomes; it is diagnostic evidence, not qualification. ADR 0015's unsafe return cases are historical, not demonstrated current supported-path defects; ADR 0016 changed that scope. [Historical closeout](docs/handoffs/2026-09-10-adr-0015-stage-closeout.md), [current intent evidence](docs/build-log/2026-09-11-initial-intent-semantic-redesign.md), [end-to-end diagnostic](docs/build-log/2026-09-20-intent-to-search-planning-evaluation.md), [improvement-plan measurement and evidence limits](docs/reviews/2026-09-19-intent-clarification-improvement-plan.md#6-measure-the-whole-task-then-diagnose-the-boundary). The post-core redesign does not defer this claim gate. |
| G02 | M2A semantic qualification and adoption | Before enabling model endpoint selection as a qualified default | Independent human review, preregistered holdout, useful coverage versus work, explicit adoption decision. [M2A handoff](docs/handoffs/2026-09-17-m2a-llm-endpoint-airport-selection.md). |
| G03 | Typed requirements and actual constraint enforcement | Before claiming that a hard requirement filters searches or is satisfied by a recommendation | Typed value/provenance/correction contract and tested filter/validation mapping; otherwise visibly unresolved. [Planning completion map](docs/handoffs/2026-09-12-search-planning-design.md#9-what-remains-after-this-design). |
| G04 | Provider capability semantics, freshness, and result validation | Before presenting provider observations as satisfying the supported travel request | Accepted request/response contract, success and failure fixtures, actual supported evidence, no invented availability/bookability. [Provider intake](docs/provider-feasibility/2026-09-08-initial-provider-intake.md). |
| G05 | Reproducible reviewer verification and truthful quality gates | Before claiming a clean-checkout handoff or reproducible evaluation, not every local preview | Reproduce the declared command with exact permitted artifacts/dependencies and a passing scoped gate. The exported golden CLI and mypy currently fail; whole-repo cleanup/CI are not prerequisites for a narrower disclosed demo. [Engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| G06 | Operational attempt/deadline bounds and safe partial outcomes | Explicit finite retry/timeout/page policy for live integration; composed deadlines before an end-to-end bound claim | Distinguish SDK invocations, repairs, HTTP attempts, and pages; test exhaustion and partial results. One offline SDK invocation made three HTTP attempts: initial plus two retries. [Engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
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
| D01 · proposed; improvement plan challenged and revised | Diagnose friction in an actual travel decision, then selectively improve interpretation, context, presentation/editing, or recovery; no shared-schema or correction-framework rewrite by default | Owner requested implementation remain deferred until after the core project; revisit when better understanding could reduce a real task's effort/error. Pull forward only scoped work needed for G01/G03 claims | Follow the [revised improvement plan](docs/reviews/2026-09-19-intent-clarification-improvement-plan.md): start with one observed task and an existing failure, compare the owner's actual workflow, separate qualifying options from prospectively defined leads, and distinguish upstream errors from scope/data limits. Expand evidence as needed; one observation is not qualification. Choose one useful comparison or retain upstream unchanged. Preserve date/state/provenance guarantees; G01/G03 remain separate. Context, alternatives, post-ready editing, and shared semantics are options, not a checklist. Scope recovery and adaptive control remain D04/D09. No implementation or policy adoption follows. |
| D02 · proposed | Measure whether gateway supplements and larger endpoint selections earn their cost; restrict/remove them if not | First provider pilot for observation yield; completed-journey comparison only when that journey type is supported | Same maximum budget, useful evidence/work, duplicates, latency, and human review. Hub component hits are not validated shortlist lift. Keep M2A adoption G02 separate. [Review §8](docs/reviews/2026-09-19-search-planning-architecture-review.md#8-experiments-that-would-change-the-design). |
| D03 · parked | Reopen 2B semantic/prompt/market policy only for demonstrated failure patterns, including same-market missed value and circuitousness | Downstream results or human review reveal material errors; explicit owner reopening | Targeted cases plus an independent review/holdout and a before/after result comparison. Do not start prompt-v7 simply because residual notes exist. [2B closeout](docs/handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md). |
| D04 · proposed | Scope recovery for trip-shaped input; linked one-way trips only if separately justified | Core complete and observed exclusion/re-entry cost establishes value; explicit ADR 0016 decision before a policy change | Compare current guidance with a reviewed mock offering explicit acceptance of a fresh outbound-only request. A displayed draft is nonexecuting; dependent facts require validation; measure remaining return work and reduced-scope recovery separately from original-task fulfillment. Linked trips additionally require parent-trip semantics, linked constraints, and independent one-way validation. [Scope-recovery option](docs/reviews/2026-09-19-intent-clarification-improvement-plan.md#scope-recovery-can-be-smaller-than-linked-trip-planning), [ADR 0016](docs/adr/0016-one-way-award-request-boundary.md). Neither option silently activates return state. |
| D05 · parked | Cash search/comparison and additional inventory providers | Core complete; a documented blind spot or comparison need justifies another provider | Access/quota/permission feasibility, error fixtures, normalized results, measured incremental value. Current cash-only scope remains unsupported. [Provider intake](docs/provider-feasibility/2026-09-08-initial-provider-intake.md), [ADR 0016](docs/adr/0016-one-way-award-request-boundary.md). |
| D06 · parked | Point balances, spending budgets, program access, and narrow transfer feasibility | Core complete and a real shortlisted option cannot be judged useful without these facts | Typed user inputs, sourced eligibility/ratio rules, deterministic arithmetic, explicit unknowns; no invented cross-program value. Add minimal eligibility earlier only if the core claim requires it. [Original deferral](docs/build-log/2026-08-30-defer-points-budgets.md), [review §7](docs/reviews/2026-09-19-search-planning-architecture-review.md#7-database-retrieval-and-eventual-agent-workflow). |
| D07 · parked; sequencing change proposed | Reviewed strategy-document authoring; separately consider runtime loyalty-rule retrieval | A result or explanation exposes a source-knowledge gap | Permissioned dated sources; structured/lexical comparison; citations and review. M3 is human-reviewed authoring and already has a usefulness gate; earlier provider feedback is the proposed change. [Roadmap](docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md#milestone-3--reviewed-strategy-documents-and-rag-assisted-authoring). |
| D08 · parked | Broader geography, airport-group/strategy coverage, richer lookup, catalog refresh/hosting | Core complete and unsupported demand or refresh cost demonstrates the need | Named gaps, reviewed new evidence, coverage/receipt diffs, regression tests, refresh/retention decision. Local source preservation is already resolved; remote hosting remains deferred. [ADR 0018](docs/adr/0018-sqlite-geographic-catalog.md), [M1 closeout record](docs/build-log/2026-09-15-m1a-catalog-publication.md#retention-correction-and-milestone-1b-closeout-2026-09-16). |
| D09 · proposed | Result-responsive model controller and evidence-driven clarification | Fixed execution ordering leaves measured value unrealized after core completion | Equal-budget comparison against deterministic actions; bounded action vocabulary, stopping rules, no constraint relaxation. [Review §7–8](docs/reviews/2026-09-19-search-planning-architecture-review.md#7-database-retrieval-and-eventual-agent-workflow). |
| D10 · parked; design proposed | Persistent sessions, query/result history, proposal caching, resume across processes | Repeated use needs history or recovery beyond a single run | Explicit retention and freshness rules, request/attempt/observation links, invalidation and recovery tests. Per-run traces and bounded fault handling belong in the core; a permanent store does not. [Review §7](docs/reviews/2026-09-19-search-planning-architecture-review.md#7-database-retrieval-and-eventual-agent-workflow). |
| D11 · parked | Deployed UI, authentication, and operational hosting | Core complete; choose a recruiting demo or actual personal-use delivery target | Safe demo data, secrets isolation, basic quotas/diagnostics, reproducible startup/deployment. Demonstrate a smaller replay/local handoff first; deployment claims require actual deployment. [Current non-goals](AGENTS.md#current-non-goals), [engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| D12 · proposed | Broad historical-code retirement and contract simplification | Core complete and active entry points/tests are clearly identified | Active import/command map, preserved tagged historical artifacts, migration/regression evidence, passing active quality gate. Fix G05's declared gate earlier; avoid a wholesale refactor now. [Engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| D13 · proposed | Scale/performance and concurrency beyond one bounded workflow | Measured resource or concurrent-user demand after core completion | Representative load profile, bottleneck evidence, tested improvement with correctness preserved. No inferred enterprise scale from catalog row count. [Engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| D14 · proposed | Owner/user feedback, personal AI-engineering learning, then a concise evidence packet and independent handoff | Owner mock/replay walkthrough before full 2C qualification, repeated at pilot; reuse an existing failure for personal explanation; external observation when safe and available | Record the actual task/effort and a justified keep/change/drop decision; do not require a new feature or design change. Personally explain one failure/fix and assess an adjacent requirement, recording assistance and gaps. A later engineer's replay/handoff is distinct from customer adoption; self-directed work does not establish enterprise delivery. G05 applies to reproducibility claims; G07 to sharing. [FDE preparation](docs/reviews/2026-09-19-intent-clarification-improvement-plan.md#ai-engineering-and-fde-preparation), [engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md#11-engineering-evidence-for-fde-recruiting). |
| D15 · proposed | Assemble independently observed hub/access components into a complete journey | A useful pilot lead justifies the extra validation and the owner opens this scope | Choose supported topology; validate chronology, continuity, original departure constraints, seats, positioning and separate-ticket tolerance. Never sum component prices into a through-ticket claim. Until then, leads do not count as completed-option lift. [Review §5](docs/reviews/2026-09-19-search-planning-architecture-review.md#strategy-semantics). |

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
