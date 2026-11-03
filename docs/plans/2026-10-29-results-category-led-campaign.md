# Results M2 category-led campaign: goals, constraints and review ledger

Recorded 2026-10-29. Final status: **stopped at the authorized twenty-iteration
ceiling, c01–c20 complete; fifth-, tenth-, fifteenth- and twentieth-iteration
architect reviews complete; no candidate qualifies. Results M2 revision remains
open. No further paid calls or c21 are authorized.**

The owner approved the response design through Q1–Q8, approved three saved-answer
examples with the correction that flight information belongs in cards, and then
instructed implementation/review by appropriate subagents, live evaluation without
another permission request, architect reflection every fifth iteration, and
continuation until M2 can close or 20 iterations have run. This invocation
supersedes the previous session's implementation stop for this new campaign. The
old V3–V30 campaign and its original grades remain stopped and intact.

Source context: [M2/workspace goal](2026-10-23-2334-feat-results-workspace-plan.md),
[ADR0029](../adr/0029-structured-results-and-local-workspace.md),
[current contract](../results-m2.md),
[V3–V30 handover](../handoffs/2026-10-29-results-m2-fast-profile-handover.md),
[Ranking policy](../handoffs/2026-10-01-ranking-m2-styles-contract.md), and
[session log](../build-log/2026-10-29-results-category-led.md).

## Goal and owner-confirmed constraints

M2 must help travelers understand useful award-led choices, compare their
tradeoffs, and know what to check next without reading dense itinerary prose.
The answer combines natural Luna explanation with source-resolved flight cards;
the independent explorer retains every eligible exact variant.

| Requirement | Acceptance meaning |
| --- | --- |
| Ranking-led choices | Preserve meaningful time, cost and premium perspectives and their source-assigned membership. Selection must consider available perspectives before composition. |
| Natural language | Flexible order and grouping with understandable category labels; no mandatory three-section skeleton, internal membership-state labels or recipe wording. |
| Coverage without quotas | Represent materially distinct available perspectives. One journey can serve multiple categories; no fixed one-per-category rule. An omitted category needs a source-supported rationale in the selection audit. |
| Useful overlap | Explain each exact journey once, identify its multiple strengths, and use brief cross-references if helpful. Overlap is not a best-overall claim. |
| Explanatory value | Explain why to consider each choice and its meaningful downside/condition, including supported differences when helpful. No compulsory numerical contrast or fabricated compensating benefit. |
| Flight facts in cards | Source-resolved cards carry routing, dates, local times, duration, program/points, actual cash obligations and relevant connection details. Narrative may repeat a specific fact to explain a choice, but must not recite the card. |
| Cost uncertainty | Explain its practical consequence naturally. Possible cost advantage remains qualified; undetermined membership is not called cost-focused. Shared missing facts appear once unless another option has a different material limitation. |
| Incomplete results | Compare materially useful supported research directions when available. One lead is sufficient if other leads add no supported choice. Leads never acquire complete-journey styles or booking certainty. |
| Brief full-cash context | At most one brief source-attributed comparison sentence, with exact benchmark identity. No full benchmark card or cash schedule. This does not limit cash-component information inside award-led journeys. |
| Factuality | Natural prose, captions and cards all agree with exact sources. Mechanical cleanliness alone does not prove this. |
| Responsiveness | Approximately 20 seconds, with a small overage acceptable, for the complete checked Results workflow including exact counts and actual correction. |

Luna remains the author. Ordinary numerical prose remains model-authored; the
rejected inline-clause binding proposal does not return. Ranking's fixed point
heuristic remains a preference rubric, never market value or cash payable.
Admitted and conditional complete journeys keep their source status/conditions;
party evidence never supplies missing price scope. Cross-program points numerals
do not establish economic value.

No new travel-provider or live FX calls, upstream request/planning/Ranking policy
changes, product multi-agent orchestration, frontend milestone implementation or
M3 qualification belong to this campaign. Native development subagents implement,
run and review the work. No commit or publication is implied.

## Lessons carried from V3–V30

- V3's fast but comparison-basic outputs mean brevity and latency alone do not
  satisfy M2. Source-supported choice usefulness must be reviewed explicitly.
- V11–V22 show that exact fact packets and added editors do not guarantee correct
  surrounding prose. Keep useful exact facts; begin with selection plus authoring
  and one correction only after actual recoverable mechanical failures.
- V23's passing factual cohort did not establish stable behavior; subsequent
  unchanged-path failures require fresh frozen confirmation rather than promotion
  from scouts.
- V27 shows that natural composition and mechanically clean output can coexist
  with material source errors. Factuality remains a separate hard gate.
- V28–V30 show that small reference ceilings and grouped records do not ensure
  useful choice coverage. q119's omitted premium perspective makes selection
  coverage a direct acceptance concern.
- The prior comparative-depth rubric missed category omission and did not
  explicitly test the newly confirmed incomplete-lead breadth standard. This
  prospective rubric tests the confirmed traveler goal; original campaign grades
  remain unchanged.

## Initial architecture for implementation

Use a separate `category` authoring path and versioned artifact/document/resolved
contracts, rather than extending the existing giant V1–V30 profile conditionals.
Reuse stable source projection, alias binding, factual card views, writer/count
adapters, pass receipts and bounded-attempt helpers where their semantics fit.
New checker and replay semantics must be explicit; no runtime monkeypatching of
legacy preparation or reinterpretation of saved V11 artifacts.

1. **Prepare once from the full trusted source.** Preserve full category
   availability, membership states, overlap and actual candidate identities.
   Keep source-global availability distinct from selected-pool facts.
2. **Select a useful authoring pool.** Luna chooses exact journey/lead references
   and one optional full-cash benchmark. Return an audit of category omissions
   when applicable. Code derives selected memberships and coverage from Ranking;
   it does not trust model-declared membership or rank candidates itself.
   An initial ceiling of six nonbenchmark references plus one cash reference is
   an engineering bound, not a number to fill or an accepted ranking policy.
3. **Build self-contained writer records.** Each exact reference owns its facts,
   price scope, category state and applicable conditions. Include a compact
   global category summary so selected records cannot masquerade as the complete
   landscape. Selector rationale is untrusted audit material, not factual writer
   evidence. Retain exact temporal pair facts if useful without mandatory cards.
4. **Compose the connected answer.** A journey/lead reference resolves to an
   existing factual card. A dedicated benchmark-inline form binds an exact cash
   source to the single authored sentence, without resolving a full cash card.
   The model controls reading order and explanation; code owns card data.
5. **Check and deliver.** Check reference roles, source bindings, actual style
   labels/coverage, duplicate cards, bounded benchmark form and visible internal
   IDs where deterministic. Semantic omission reasons, usefulness, repetition and
   free prose truth remain independently reviewed. One recoverable correction
   uses the same frozen selected facts and recomputed findings. Preserve explicit
   failed outcomes and all attempts; no SDK retries or unconditional editor.
6. **Replay and inspect actual presentation.** Reconstruct prepared requests,
   checks and resolved answer offline from immutable versioned artifacts. Produce
   a local review preview with real source-resolved cards and surrounding prose;
   an `[Display: ...]` placeholder is insufficient presentation evidence.

Initial LOW selection/LOW composition/LOW conditional correction is a bounded
hypothesis, not a qualified setting. A materially different next hypothesis gets
the next campaign iteration and preserves the previous exact configuration,
source/code archive, request/response and review. Prefer a small explicit frozen
configuration over a new runtime branch for every prompt experiment.

## Prospective evaluation and spending bounds

Campaign identity: `2026-10-29-category-led`; iterations `c01` through `c20`.
Evidence root: `evidence/results-stage/m2/structured/2026-10-29-category-led/`.
An iteration is a frozen design/configuration tested live and reviewed, not each
API call or an unchanged retry. A failed confirmation informs the next iteration.
Changing code or instructions invalidates the candidate's earlier confirmation.

Freeze a source manifest before the first call. The original admitted, conditional
and incomplete sources are development scouts. Three distinct saved Ranking
exports—mixed access, exact business and positioning—supply additional source
cases for confirmation. Verify digests and lineage before calling them distinct.
They are new to this campaign, not fresh live travel searches. No distinct saved
incomplete search has been found; reuse must be explicitly disclosed. A failed
confirmation source becomes development evidence; do not keep calling it unseen.

Offline synthetic controls cover definite/possible/undetermined cost, overlap,
empty categories, single-option cases, distinct quote scope, missing cabin/party
evidence and incomplete leads. Label them synthetic. They cannot establish live
provider cost coverage or substitute for independent natural-language review.

For each frozen iteration:

1. Run three fresh scout draws, one per original source archetype.
2. Independently review all complete delivered answers, including their cards,
   against source truth, category faithfulness and natural decision usefulness.
   Explicit failures count; do not replace unsuccessful draws in the cohort.
3. Only an all-gate passing scout candidate advances to six new frozen
   confirmations: the three originals and the three distinct saved exports.
4. Only an all-gate passing confirmed candidate advances to one controlled live
   correction diagnostic, plus offline positive/negative failure controls.
   The real correction must preserve factual/presentation quality and latency.

Engineering latency rule: each qualifying natural or controlled-repair workflow
must finish within **22 seconds**, with cohort median at most **20 seconds**.
This is a conservative prospective interpretation of the owner's small-overage
allowance, not a claim that the owner specified 22. Measure from input parsing /
preparation through exact count requests, generations, checks and resolution.
Record per-phase times, token usage, returned service tier and cached-token data;
do not make full-application or cold-cache guarantees from these samples.

The hard engineering maximum is **600 generation and 600 exact count attempts**,
declared upfront in the campaign manifest: 20 iterations × (3 scouts + 6
confirmations + 1 controlled-repair run) × at most 3 calls. These are ceilings,
not targets; skip follow-on calls after a failing gate. All reservations,
unknown-usage errors and actual calls must reconcile. No SDK retries.

## Acceptance gates and stopping rule

Stop before c20 only when an unchanged candidate has:

- source-faithful, useful and category-faithful cards-plus-prose for all scouts
  and the six prospective confirmations, with supported sparse-source exceptions
  recorded rather than decorative tradeoffs demanded;
- the stated checked-workflow latency evidence, including actual controlled
  repair and any naturally occurring repairs;
- passing meaningful offline behavior tests, archive/replay/tamper checks and
  code review, with unresolved findings explicitly dispositioned;
- a final architect review against this goal ledger, including card rendering,
  selector coverage, uncertainty repetition, source diversity and scope limits;
- reconciled current contract, ADR0029/index, project state, deferred register
  and build log, preserving all previous campaign outcomes.

The owner has delegated iteration toward M2 closeout and accepted the design;
do not invent another mandatory permission round to run the authorized campaign.
If all gates pass, report a **scoped Results M2 revision closeout supported by this
evidence**, and explain that broader generalization, frontend integration and M3
remain separate. Do not claim the owner personally reviewed generated live answers
unless that occurs. Default wiring alone is not qualification. If c20 fails, stop
with the best evidence, remaining failure classes and a concrete next-cut proposal;
do not loosen gates to manufacture closeout or continue to c21.

## Verifier controls before qualification

The previous strict archive gate has four known assumption bugs. The new verifier
must have positive and negative controls for:

1. The controlled fault's actual identity, rather than a profile-name guess.
2. Valid one-pass API-incomplete/no-delivery handling, while still failing a false
   success or missing required evidence.
3. Complete versus incomplete branch instructions, without requiring an
   incomplete-only rule on unchanged complete input.
4. Present-but-empty comparison pairs when no eligible pair exists, distinguished
   from missing required data or missing pairs when expected.

A clean replay result establishes reconstruction, not prose truth or useful
selection. Old verifier failures remain recorded until separately corrected and
reverified; do not relabel the old campaign green from the new campaign's checks.

## Architect stewardship ledger

The architect checks the goals above at c05, c10, c15 and c20, and before any
earlier closeout. Each review must read the implementation and actual evaluation
evidence, state what changed/failed, challenge the next hypothesis, and retain or
readjust direction without changing owner policy silently. The parent owns final
integration and acceptance decisions. Healthy subagents are not replaced because
they are taking time.

| Checkpoint | State | Direction / evidence |
| --- | --- | --- |
| Initial architecture | Reviewed source/contracts; proposed here | Category-aware selection; typed cards; natural explanation; brief exact cash context; scoped two-call path with conditional correction. No live evidence yet. |
| Ahead of c04 | Source/code/evaluation reflection completed | Preserve conditional program/date/cabin research directions; no mandatory same-program pair. Fix exact duplicate cash prose with a profile-bound check and bounded correction. See reflection below. |
| Ahead of c05 | Bounded next hypothesis recommended | Keep LOW efforts and add compact source-owned selected-journey temporal relations, including equality. Preserve natural prose and independent factual review. |
| c05 | Completed; no candidate qualifies | [Mandatory reflection](../reviews/2026-10-29-results-category-led-c05-architect-review.md): accurate c05 temporal prose, two composition failures, one22.843s latency failure. Recommend coherent author-guide allocation of optional pool, local reasons and shared-once conditions for c06. |
| Ahead of c07 | Explicit category-addressed selector recommended | C06 composition succeeds in conditional/incomplete scouts, but admitted selection silently loses premium. Require explicit source-member selection or audited omission for every category, without a display quota or new repair topology. |
| Ahead of c09 | Bounded effort experiment accepted by parent | C08 category addressing works, but LOW composition repeats shared limits and one incomplete answer treats cross-program point numerals as an advantage. Test MED composition only; separately restore visible inline cash-role context lost during resolution/display. |
| Ahead of c10 | Lead-caption responsibility clarification recommended | C09 improves composition and all scouts meet timing; q026 still repeats lead status already supplied by the shared note and exact cards. Clarify the lead caption as a conditional next-check reason without changing selection, effort or recovery. |
| c10 | Completed; no candidate qualifies | [Mandatory review](../reviews/2026-10-29-results-category-led-c10-architect-review.md): q028/q029 M2 failures; q02924.2212s also fails latency; q030 passes. Recommend source-derived condition applicability input for c11, preserving natural placement, current wire and effort. |
| After c11 | Confirmation reviewed; candidate fails | Three scouts pass; five of six confirmation draws pass, q035 fails M2/C for weak individual choice/research reasons. All timing gates pass. Fresh architect proposes neutral selected-choice facts and a narrower card/prose responsibility guide; parent provisionally accepts subject to final review and scope guardrails. |
| After c12 | C13 effort-only change accepted by parent | All three source scouts pass; conditional24.8768s and median20.9246s fail timing. Preserve exact c12 design and test LOW composition; selector/correction remain LOW. |
| After c13 / before c14 | Deep review completed; bounded experiment accepted | Parent accepted c12 LOW/MEDIUM/LOW with a model-selected pool ceiling of three nonbenchmark refs plus one cash benchmark. Exact style witnesses, optional displayed subset, all current source aids and gates remain. No c14 quality or timing result yet. |
| Before c15 | Indexed bounded selector accepted | C14 overflow prevented one answer; q047 passes and q048 has qualified H/C failure. One bounded options array plus separate cash and indexed category audits prevents audits adding hidden identities. Semantic gates remain independent. |
| c15 | Completed; candidate fails | [Mandatory reflection](../reviews/2026-10-29-results-category-led-c15-architect-review.md): indexed selector works and timing passes; q049/q050 source-pass, q051 qualified H/C failure on cross-program count rationale. Parent read the completed review and accepted one precise author-clause clarification for c16; no outcome claimed. |
| After c16 | Source-condition normalization accepted | Q052 fails M2 only; q053/q054 pass every source axis and all times pass. Trace finds award point-scope and tax-scope conditions copied from one canonical component field; parent accepted provenance-checked normalization, without another guide change. |
| After c17 / before c18 | Natural-choice paragraph replacement accepted | Q055/q057 source-pass; q056 has qualified M2 editorial failure from classification language and an unprompted timing disclaimer. Replace only the complete-journey/category paragraph; retain factual comparison limits and flexible single-card choices. |
| After c18 / before c19 | Quote/condition interpretation paragraph accepted | Q058/q060 pass; q059 has qualified H failure from known amounts swept into unknown details and M2 failure from repeated quote basis. Replace only the scope/condition paragraph; both local and shared qualification remain sufficient. |
| Before c20 | Final candidate accepted | Replace only two c19 sentences to quantify one explanation per relevant condition group among shown choices, preserving all placement freedom. No c21. |
| c20 or earlier closeout | Pending | Mandatory review after actual c20 scouts and all source grades, before any confirmation or closeout; final addendum if unchanged c20 advances through downstream gates. |

ADR disposition: this plan records current owner decisions and an initial
engineering proposal. The parent must amend ADR0029 and its index in this session
for the accepted card/category/evaluation direction; this plan is not a substitute
for that decision record. No runtime or test success is claimed by this document.

## Ahead-of-c04 reflection: preserve the approved incomplete-answer goal

This review inspected the current category runtime and prospective rubric,
q001–q007 and q009 source reviews, q006/q009 full answers/documents/audits, and
c03 checked-workflow summaries. q008's independent review was not yet available
at the time of this reflection. It does not replace the mandatory c05 review.

| Iteration | Observed result | Design implication |
| --- | --- | --- |
| c01 | All three combined failures; identity, repetition, card-component coverage and incomplete category/value errors. | Preserve exact source identity and render actual component facts; keep incomplete leads outside styles. |
| c02 | q004/q005 pass all source-review axes; q006 passes factuality/useful next check/category/cards but fails composition and comparison. | Complete-answer direction is promising. q006 mostly recites card prices and repeats shared gaps, so retain the requirement for an individual practical reason. |
| c03 | q007 passes all axes after a natural missing-cash repair; q009 passes factuality/useful next check/category but fails composition/card presentation because its cash sentence is duplicated verbatim. Its C failure is interpretation-disputed below. q008 review pending. | Improve the specific duplicate-cash mechanism; do not use one review's preferred lead pair to introduce a new selection policy. |

C03 completed in 15.436/9.655/11.295 seconds. The first run made three actual
generation/count calls because of natural correction; the others made two.
Its selector reported 83,219 cached tokens of 83,222; the conditional selector
reported 72,422 of 72,425. Those measurements support this saved workflow under
the observed cache conditions, not cold-cache repair latency or stable quality.

### Incomplete C interpretation and owner alignment

The owner accepted conditional program-access, date and cabin reasons, and
accepted a hand-authored United-versus-Alaska example in which the traveler's
usable program determines which lead to investigate. No same-program-pair,
minimum numerical comparison, lowest-points or new lead-ranking policy was
adopted. An explanation such as “If you can use Alaska miles, check this lead”
can identify a useful next research action without asserting that the traveler
owns those miles or that Alaska is economically better than United.

Accordingly, q009's C rejection on the ground that program/date compatibility
does not itself establish a meaningful research choice is **interpretation-
disputed** against the owner's accepted examples. The cited same-program
January13 or cabin alternatives are legitimate possible improvements, but their
availability does not make them required selections. Retain the original review;
the [separate q009 adjudication](../reviews/2026-10-29-results-category-led-q009-adjudication.md)
records this interpretation dispute without changing any original grade.
This is not an automatic C pass: carrier-list counts still lack an explained
benefit, and a generic date label alone may merely repeat a card. Evaluate the
actual conditional action and source support, not whether a preferred numerical
contrast appears.

Q009 still fails overall regardless of that dispute: its identical unbound and
bound cash sentences violate the confirmed one-sentence presentation rule, and
its Aeroplan caption repeats a shared price-scope limitation. Q006's composition
and comparison concerns remain supported by its factual recitals without
individual conditional research reasons. The goal is useful natural guidance,
not increasing comparison intensity to satisfy a decorative tradeoff test.

Prospective reviewer clarification should explicitly permit actionable
conditional program/date/cabin research choices; require factual, noninvented
explanations and useful breadth where the source supports it; and distinguish
that requirement from optional same-program numerical contrasts. Preserve all
original grades and disclose this interpretation clarification.

### Bounded c04 direction

Retain c03 selection, source representation, reference ceiling and reasoning
efforts. Add a c04-specific deterministic finding when the normalized exact
benchmark sentence is repeated in another authored block, with one clear
instruction that full-cash context belongs only in its bound inline block.
Use the existing one-correction path after a recoverable finding; do not silently
delete prose or introduce an unconditional editor. Match exact duplication only;
do not claim that this detects every semantic restatement.

Positive and negative tests must distinguish one bound sentence, exact duplicate
in narrative, a distinct legitimate cash-positioning discussion and historical
c01–c03 replay. Review the corrected full answer, since repairing duplication
does not establish other prose truth or usefulness. Then run the frozen c04
scouts under the existing gates. Independent q008 review remains required before
claiming c03 source-review completion. No runtime edits, live calls or historical
regrading were performed by this architect reflection.

## Ahead-of-c05 direction: exact temporal relations before more reasoning

C04 q010 and q012 pass all six source-review axes. Q012's incomplete answer
passes under the disclosed Q3 interpretation: conditional program access and date
choices can guide research without numerical superiority or invented styles.
Keep that direction; do not introduce same-program comparison requirements.

Q011 fails H/M2/P while U/C/K pass. Both selected journeys arrive at Bangkok at
08:50 on January10 and use the same TK64 onward flight, yet its opening and
business-card explanation claim business arrives earlier. Business departs
earlier and takes 33h10; economy takes 30h03. The true cabin-versus-elapsed-time /
connection-buffer choice does not repair the false arrival advantage. Shared
separate-ticket protection is narrated three times, and the one cash sentence
contains the unsupported confusing phrase “one-stop-free” beside “two stops.”
Source-resolved cards remain correct. See the [q011 review](../../evidence/results-stage/m2/structured/2026-10-29-category-led/review-bundles/q011/review.md).

The c04 cohort completed in 12.81/10.67/9.80 seconds with substantial reported
selector caching, no repair and no qualification. These results do not establish
cold-cache latency. Repeated saved sources and the limited cost/incomplete source
coverage remain explicit constraints.

### Recommended c05 hypothesis

Keep LOW selection and LOW authoring, the existing conditional correction path,
source-wide choice policy and category/card contracts. Add **compact exact
temporal relations for selected complete journeys** to the writer input:

- exact writer reference identities for both endpoints;
- separate departure, arrival and whole-journey elapsed metrics;
- source-derived direction or explicit equality, with the exact minute delta;
- unavailable or scope-incompatible metrics remain unavailable, not zero.

Reuse the existing `build_temporal_registry` arithmetic and source scope rules.
Do not restore every quote/cabin/seat pair dossier or expose a mandatory temporal
card/inline prose clause. Natural comparative wording remains Luna's. The current
category writer has individual time facts but omits the old pair relations, so
this is a precise missing-evidence hypothesis rather than another broad editor.
Earlier V11–V22 results show that supplied comparisons cannot guarantee truthful
prose; retain independent H review as a hard gate.

The c05 brief should state neutrally that time membership describes Ranking's
global threshold, not an earlier-arrival or shortest-among-selected guarantee.
Overlapping membership likewise does not establish an overall winner.
An arrival equality cannot become a departure or elapsed advantage. Remove the
c04 illustrative conditional about one option offering both earlier arrival and
premium cabin from the new brief; it may prime an unsupported example, although
the campaign does not isolate that causal mechanism.

Reinforce the existing presentation requirements narrowly: narrate shared
separate-ticket protection once, keeping genuinely different buffers or conditions
local; use ordinary source-supported route/amount/uncertainty wording in the
single cash sentence, with no creative stop-label compounds. These are contract
clarifications, not a new semantic checker or another generation stage. Keep
incomplete selection/representation and its accepted conditional-research standard.

Version the new writer packet and profile so c01–c04 preparation and replay remain
unchanged. Verify the real q011 equal-arrival pair, reversed pair orientation,
distinct departure-versus-elapsed differences, and empty relations for a single
journey or no complete journey. Measure the added request size and complete live
latency. Do not simultaneously raise authoring to MEDIUM: preserve that as a
separate hypothesis if exact relations still fail, so the next result is more
interpretable and does not spend latency headroom without evidence.

This is pre-c05 steering only. The mandatory architect checkpoint after c05 must
inspect the actual code, three generated answers, source reviews, requests and
timing/cache evidence before continuing or advancing to confirmation. No runtime
edits, live calls, old-grade changes or milestone closure are performed here.

## Mandatory post-c05 disposition

The [fifth-iteration architect review](../reviews/2026-10-29-results-category-led-c05-architect-review.md)
inspected actual code, requests, answers, source reviews and timing. All three c05
scouts pass H/U/C/K/P, but q013/q015 fail M2 for repeated shared uncertainty and
q013's redundant cards. Q014 passes all source-review axes but takes22.8432s,
failing the unchanged22s ceiling. The runner reports15 strict-verified artifacts
and31 paired generation/count reservations. No confirmation follows c05.

The schema and checker permit omitting redundant authoring-pool members while
preserving selected category perspectives; an offline q013 five-to-two-card probe
produced no failed findings. The actual guide's per-choice downside language is
a plausible contributor to recurring generic caveats, not a demonstrated cause.
The c04/c05 conditional selector requests are byte-identical, with similar tokens
and cache but a much longer c05 generation; its latency cause remains unknown.
Do not blame the later temporal input or relax the gate.

Recommended c06: replace the author guide coherently to make the pool optional,
retain only materially useful cards, explain each distinct choice/conditional
action, and discuss shared missing facts once without a per-card downside quota.
Keep LOW efforts, selector input/instructions, six-reference bound, schema/checker,
compact temporal facts and c04 cash-dedup policy unchanged. Preserve Q3's approved
program/date/cabin research standard. No new ranking or mandatory numeric pair.

Five iterations are consumed; fifteen remain. Source novelty/cost/incomplete
coverage limits and all M2 acceptance requirements remain. C10 is the next
mandatory fifth-version review if reached; earlier closeout still requires a
final architect audit. Parent integration decides the final frozen c06 design.

## Ahead-of-c07 direction: make category addressing explicit in selection

C06 q017/q018 pass every source-review axis; the optional display subset and
shared-once guidance now work in those conditional/incomplete draws. Q016 passes
H/U/C but fails M2/K/P. Its full source has116 premium members, yet all five
selected pool journeys are economy and the omission audit is empty. Code records
`category_omitted`; authoring cannot recover the lost perspective from that pool.
Both displayed cards are faithful, but category preservation must begin upstream
of composition. Q016 also repeats canonical availability advice and attaches
“fee unit unknown” to a USD440 cash quote whose actual source unit is major.

C06 checked times are9.875/10.798/10.644 seconds, two generation/count calls each;
the admitted artifact is annotated. The runner reports18 strict-verified artifacts
and37 paired generation/count reservations. No confirmation or qualification follows.

### Alternatives and recommendation

- **Explicit category-addressed wire (recommended):** make every category an
  unavoidable selection/audit decision in the strict response shape, using
  authoritative source membership enums. This directly addresses forgetting a
  material perspective while preserving model selection and overlap.
- **Repair selector before authoring (not selected now):** a bounded third call
  could repair missing category coverage, but moves correction across phases and
  needs new attempt/replay/latency evidence for multiple recovery branches. The
  present failure can be addressed at the handoff without that topology change.
- **Another prompt-only reminder (not selected now):** the current selector
  already explicitly asks for category coverage and omissions. C06 demonstrates
  that these instructions can be ignored while producing schema-valid output.

Recommended c07 schema retains a free `choices` list and replaces the optional-
length omission array with required `style_audit` entries for time/cost/premium.
Each entry contains one exact source-member `r` or null, plus an audit-only
`omission_reason`. The parent accepted the explicit witness-reference union and
this field name before implementation.
The alias enum comes from that category's authoritative Ranking index; an absent
category permits only null. A nonnull alias is itself an **explicit model
selection** into the authoring pool. Union these with free choices, deduplicate
exact identities and apply the existing six-nonbenchmark-plus-cash bound to the
union. Code never chooses a member that the model did not name.

One reference can witness time and premium simultaneously and appears once in
the union. The free list can retain multiple useful representatives, uncategorized
alternatives, leads and the benchmark. A single per-category witness is an audit
mechanism, not a one-per-category card/selection quota, forced layout or new ranking.
The composer retains its optional subset subject to source-derived category
coverage. The full independent explorer remains unchanged.

Validate nonnull witnesses against source membership and require their reason to
be empty. A null entry for a genuinely uncovered available category needs a
nonempty omission reason; an unavailable category uses null/empty. Omission notes
must agree with the union's actual memberships, including overlap, rather than
relying on model-declared status. Legitimate omissions remain audit-only and
semantically unchecked pending source review. No generated-purpose prose becomes
writer evidence. Contradictory or overfull selections remain explicit failures;
do not auto-fill categories, truncate the pool or silently promote them to clean.

### Bounded ancillary correction and verification

Q016's actual benchmark authoring record has `facts.fee_unit="unknown"` alongside
`quote.kind="cash_fare"`, `quote.source_unit="major"` and `quote.display="USD440"`
(formatted with a space and decimals in the request). The former is irrelevant
absent-tax metadata. A c07-only projection may remove that irrelevant field for
cash-fare benchmark records while retaining canonical evidence; it must preserve
the actual fare unit, amount, currency, scope and source identity. Keep plain cash
wording and remind the author that canonical availability guidance is appended
by the display. Do not add a fuzzy semantic repetition checker or a broad packet
rewrite alongside the selector change.

Use a profile-bound new selector schema/decode policy; keep c01–c06 raw wire,
requests, findings and replay unchanged. Tests must cover a category-selected ref
absent from free choices entering the union, overlap selecting one journey,
explicit justified omission, absent categories, wrong-role/nonmember refs,
contradictory omission versus incidental overlap, useful free alternatives and an
overfull union. Keep LOW efforts, the existing authoring correction boundary,
compact temporal facts, c04 exact cash dedup and Q3 research policy.

This is pre-c07 direction for parent integration. Six iterations have run and
fourteen remain. The missing-category gate and22s/20s timing gates stay intact;
c10 remains the next mandatory fifth-iteration checkpoint, with final architect
review still required before any earlier scoped closeout.


## C07–c08 evidence and ahead-of-c09 direction

The parent accepted c07's explicit witness-reference union, bounded to six
nonbenchmark references plus one benchmark, with authoritative source coverage
including overlap. No automatic member choice, display quota or new recovery
phase was introduced. The narrow cash-fare projection omits irrelevant
`facts.fee_unit` metadata while retaining the actual quote unit and canonical
source; the author guide reminds the model that display appends availability
advice. These are accepted engineering choices, not a change to Ranking policy.

C07's three selector calls all failed decoding before composition because the
schema permitted explanation strings where code required null for unavailable
styles. This is a schema/decoder mismatch, not a delivered-answer quality result
or an API outage. The original failures, receipts and reserved q019–q021 IDs stay
intact. Offline tests missed this valid-wire/decoder disagreement. C08 aligns the
schema's unavailable-style and available witness/omission branches; replay keeps
c07's original behavior. The runner reports the actual c07 wires are now negative
controls, alongside separately labeled source-valid adjusted offline controls.

C08 q022–q024 delivered cleanly in10.7664/10.7614/8.1079 seconds, two generation/count
calls each, with selector cache writes rather than cache hits. All three pass
category fidelity. Q022/q023 pass H/U/C/K/P but fail M2: party, ticket or tax
limitations recur in captions and the shared ending, and q023 exposes the internal
phrase `SOURCE-BOUND INLINE CASH SENTENCE`. Q024 passes U/M2/K but fails H/C/P:
its lower Alaska raw point numeral is used as an advantage relative to a different
program, despite the access qualification; its bound USD686 quote lacks visible
cash-role context. Original grades remain unchanged. The runner reports24 exact
verified archives and46 paired generation/count attempts. No confirmation ran.

### Diagnosis and bounded next experiment

The c06 author guide already allocates shared limitations once, distinguishes
card facts from decision reasons and forbids cross-program economic ranking.
C08 still regresses on those obligations. Available source facts and category
coverage are no longer the principal demonstrated blocker in these scouts.
Another reminder or broad packet rewrite would add a new interpretation without
isolating why the current coherent instructions are not followed.

**Parent-accepted c09 engineering direction: MED composition on all branches,
retaining LOW selection and LOW conditional correction.** Preserve
the exact c08 author guide, writer packet, output schema, checks, reference limits
and two-call path with at most one genuine correction. This tests whether more
author reasoning improves allocation and source-faithful choice language. It is
not a guarantee of semantic correctness, and no extra editorial call is added.
Version the phase effort and replay it exactly; actual receipts must show the
intended effort for each phase rather than merely a profile name.

V29/V30 support considering this experiment: their complete branches used LOW
selection/MED composition and passed factual/useful/composition scouts at about
12–19 seconds. They did not qualify overall, and their incomplete branch used
MED selection/LOW composition. Therefore incomplete MED composition is new
prospective evidence here, not a previously proven setting. Earlier slow full
writer/editor experiments remain a latency caution. Do not generalize the c08
headroom to a timing guarantee, infer queue causes, or relax the frozen22-second
individual/20-second median gates. One failing scout prevents confirmation.

This effort experiment deliberately preserves the author guide's internal wire
terminology for this version. Successful role rendering does not excuse leaking
that terminology into authored prose: q023's phrase would still fail natural
composition if repeated. A future prompt change should follow the observed c09
result rather than being bundled into this reasoning-effort test.

### Independent cash-role display correction

The runner traced q024's document label `Cash benchmark` to a resolved
`cash_sentence` with no label; `_answer` drops the label and the preview prints
only the prose. The wire carried role context that never reached the traveler.
The parent accepted a narrow prospective correction displaying a brief inline
**Cash comparison** label from the existing cash-sentence kind. It must remain one brief sentence,
not a flight card, cash schedule, second explanatory paragraph or numerical
wording binding. This is source-role presentation, independent of the MED
hypothesis. Preserve prior artifact/rendering interpretation, and test both
Markdown and HTML output. Source fidelity and natural sentence quality still
receive independent review.

Legacy `selected_journey_ids` records primary `p` references, whereas an `a`
alternative can also render a source-bound journey card. Q022's business card is
such an alternative, and category checks already inspect all shown cards. The
runner found no downstream category-answer consumer relying on that field as a
complete display inventory. Document the distinction; do not bundle a metadata
refactor into c09 or misclassify the visible premium card as a category omission.

Eight iterations have been attempted, including c07's three retained failures;
twelve remain under the twenty-iteration ceiling. The mandatory post-c10
architect review remains required, as does a final audit before earlier scoped
closeout. Cards, natural Luna language, shared-once limitations, Q3's conditional
research directions, source-owned Ranking membership, complete explorer,
qualification gates and frontend/M3 exclusions all remain unchanged. No runtime
change or live call was made by the architect during this reflection.


## C09 evidence and ahead-of-c10 lead-caption boundary

C09 q025/q027 pass all six source-review axes. Q026 passes H/U/C/K/P but fails M2:
one shared paragraph explains that its two research leads provide dates rather
than full schedules, then both lead captions append “this is a lead, not a
scheduled itinerary” to otherwise useful conditional program-access reasons.
All three delivered cleanly with two calls, at18.044/19.045/13.844 seconds. These
meet the individual22-second and median20-second gates for these scouts. The
runner reports roughly1500 composition reasoning tokens,52 paired calls and27
exact-verified archives. No confirmation followed the composition failure.

This is evidence that MED composition can fit the current three-source scout
budget and produce useful, grounded answers; it does not establish causality,
repeatability or correction-path latency. Keep MED composition and LOW selection/
correction fixed for the next experiment. C09's incomplete MED result is now an
observed passing scout, distinct from the historical V29/V30 incomplete settings.

The architect inspected q026's actual answer and saved composition schema, the
current guide, `focused_wire` delegation and campaign preview. The wire uses
`v` as natural text for journey, benchmark and lead blocks. The guide tells the
model to put a short decision reason there and consolidate common gaps, but
never explicitly identifies the display guarantee that each lead card is labeled
“research lead” and renders source `missing_information`. Q026's two cards indeed
already say “Needs checking: itinerary schedule incomplete.” The repeated caption
clauses add no decision information and are not necessary to keep the cards honest.

### Recommendation and alternative considered

Clarify the **lead caption's responsibility**, preserving the existing text wire:
`k=l` / `v` supplies a supported conditional reason or next action for checking
that exact program/date/cabin. The card supplies research status and the actual
source gap indicators. Shared scope belongs once in prose; the caption should
not restate generic lead/incomplete/schedule status already covered there. A
materially different local limitation remains appropriate when it changes that
choice's action. Preserve Q3's program-access/date/cabin options, without requiring
same-program comparisons or inventing unsupported benefits.

A concise replacement in the guide, plus an optional profile-scoped description
on the existing lead-only `v` schema property, makes this responsibility explicit
at the authoring field. Keep other block roles, model ordering, source records,
selection, reference limits, cash presentation, temporal facts, dedup checks and
phase efforts unchanged. No generic semantic regex, prose deletion, added call,
mandatory shared-paragraph position or card quota is proposed.

The implementer proposed renaming only the lead text field to `why_check`, with
a profile-specific adapter translating it back to `v`. This is a reasonable
schema-local cue, but the architect prefers the description on existing `v`:
either value remains free natural language, so a rename cannot enforce the
semantic restriction, while it introduces a schema/decode/correction/replay
translation obligation. C07's schema/decoder mismatch is a concrete reason to
avoid an unnecessary new wire contract. The useful intervention is the explicit
role and display guarantee, not a claim that a field name prevents repetition.
The parent owns this bounded implementation choice; no runtime edits or live
calls accompany this recommendation.

Nine iterations have been attempted; eleven remain. The mandatory architect
review must read actual c10 implementation and source-evaluated outputs after
that iteration; this pre-c10 recommendation does not count as the checkpoint.
The full M2 goal, all six source axes, timing gates and later confirmation/actual
correction prerequisites remain unchanged.


## Post-c10 direction and remaining scope

The [mandatory tenth-iteration review](../reviews/2026-10-29-results-category-led-c10-architect-review.md)
reads the actual c10 guide/schema, answers, selected records and call receipts.
Q028/q029 pass H/U/C/K/P but fail M2 on repeated local/business or shared/lead
limitations; q030 passes all six axes. Checked times18.4219/24.2212/13.6486s include
an individual latency failure. Runner accounting is30 verified archives and58
paired generation/count attempts. There is no confirmation or qualification.

The c10 description-only experiment did not solve allocation. The architect
recommends a compact source-derived condition applicability table for c11, with
exact states and affected selected aliases. It describes facts, not mandatory
paragraph placement; the model applies it to the displayed subset and retains
natural wording/order. Preserve source records, MED composition/LOW other
phases, current wire, selector witnesses, pair facts, cash context, dedup and
bounded correction. A lead-field rename alone misses complete-journey repetition;
a simultaneous effort change would obscure the input experiment. Timing remains
a hard gate, not an assumed improvement. If composition improves but timing
fails, a separately versioned LOW author experiment may follow.

The source/card trace also confirms that explicitly unknown award-tax amounts
currently produce no card row. A narrow state-based display indicator is a
separate recommended omission fix, preserving known quote formatting and older
renderers. No broad missing-field checklist or suppression of prose is proposed.
Full implementation scope and controls are in the mandatory review; these are
architect recommendations pending parent integration, not unmeasured success.

Ten iterations remain. Post-c15 is the next scheduled mandatory reflection, with
final architect review before any earlier scoped closeout. All owner-approved
natural-language/card/category/Q3 goals and evidence/timing gates remain intact.
No deep escalation is required for a presently unresolved boundary decision;
empirical effectiveness remains uncertain. If the explicit applicability
representation again fails the same behavior, seek fresh architecture critique
before repeating another nearly identical prompt or field-name experiment.


## C11 confirmation and provisional c12 direction

The parent adopted c11's source-derived condition applicability input and narrow
source-state tax-card correction. All three scouts pass H/U/M2/C/K/P at13.273/
15.370/10.569 seconds. The unchanged candidate then completed its prospectively
frozen six-source confirmation at16.123/15.001/13.316/17.171/18.298/12.706 seconds,
median15.562s. These are clean two-call deliveries without retry, correction or
source/config drift. The runner reports39 strict-verified artifacts and76 paired
generation/count attempts. All nine c11 workflows meet the declared timing gates.

Five of six confirmation draws pass every source axis. Q035 passes H/U/K/P but
fails M2/C: the economy option is described only as an alternative if business
is unnecessary, while all explained timing/cabin benefits belong to business;
the Aeroplan research lead merely asks the traveler to verify its missing
schedule/scope without explaining why that lead merits investigation. Source
cards, category coverage, cash context and condition applicability remain sound.
Shared limitations are consolidated; this failure is not a recurrence of repeated
common conditions. The guardian read q035's delivered answer and source review.

The review is consistent with Q3: conditional program access or another supported
conditional reason would suffice. It does not impose numerical contrast,
same-program lead pairs, a lead quota or a new ranking policy. A supported buffer
explanation is an available option, not a mandatory compensating benefit. The
writer may instead omit a redundant candidate while preserving materially
useful category perspectives; overlap can let one journey serve several styles.

C11 therefore does not qualify. The gated controlled-repair diagnostic remains
unrun and public defaults remain unchanged. Preserve q035 and the entire failed
confirmation cohort; do not replace a draw or retrograde it into a pass. The six
confirmation sources have now been seen and must not be described as unseen for
subsequent candidates. Later confirmation draws can be fresh generations on those
saved sources, with the source-novelty limitation explicit.

A fresh architect is preparing the c12 design review. Its preliminary proposal
adds a compact neutral table of selected-choice source facts, including program,
cabin, reported points with scope and local connection waits, while preserving
existing exact temporal relations and condition applicability. It also replaces
the broad prohibition on repeating card facts with a precise responsibility:
use a fact in prose when it explains a supported choice; let cards carry itinerary
recaps. This is an input-salience hypothesis, not proven causality or an assertion
that earlier comparison dossiers guaranteed useful prose.

The parent **provisionally accepts** that bounded direction subject to the final
fresh architect document and these goal guardrails. The guardian has reviewed the
preliminary recommendation, not the yet-unfinished final document:

- Code exposes exact facts without advantage labels, numeric/economic ranking or
  generated traveler preferences. Different program point totals remain different
  units, and unknown quote scope remains explicit.
- Luna retains choice reasoning, ordinary numerical prose, optional omissions,
  layout and ordering. There is no forced comparison pair, one-card-per-style
  quota, new rationale checker, bound clause, additional call or recovery phase.
- A larger connection buffer is a source fact; it does not establish safety,
  ticket protection or bookability. Conditional program/date/cabin reasons remain
  acceptable, and no supported alternative must appear merely because it exists.
- Preserve all other current source, effort, schema, correction, card/cash and
  evaluation settings. An independent source review must still judge whether
  the resulting explanation helps a traveler choose.

Eleven iterations have been used and nine remain. No runtime work is authorized
by this provisional note itself; parent integration follows the final design.
Post-c15 or earlier final closeout is the next mandatory architect checkpoint.
All prior timing, six-axis review, confirmation and actual-repair requirements,
provider/FX exclusions, Ranking ownership and frontend/M3 separation remain intact.


## C12 source success, timing failure and accepted c13 effort experiment

The parent accepted and implemented the final
[c12 fresh design review](../reviews/2026-10-29-results-category-led-c12-design-review.md):
neutral selected-choice source facts plus replacement of the broad card-recap
cue, retaining source records, temporal relations, condition applicability and
model-owned reasons/ordering/subset selection. The guardian read the completed
design, actual c12 generation requests, source reviews and timing/usage receipts;
the final design retains the previously recorded goal guardrails.

Q040/q041/q042 pass all six source-review axes. Q041 now explains the reported
same-program point distinction and a conditional Alaska research reason, with
shared journey conditions consolidated and the lead gap stated separately once.
The source reviewer treats “SFO–LAX transfer” for the LAX connection buffer as a
minor contextual precision issue, not an unambiguous factual error; preserve
that judgment without claiming perfect wording. Q040 has a minor unnecessary
known-tax recap. Neither nonblocking note warrants another bundled prompt change.

Checked times are20.9245765/24.8768204/12.4200746 seconds. The conditional draw
fails22 seconds and the cohort median20.9245765 fails20 seconds. All are clean
two-call deliveries. No confirmation or controlled repair followed. The runner
reports42 strict-verified archives,82 generation and82 exact-count attempts, and
no integrity failures. The candidate does not qualify despite all source passes.

The actual requests contain the new choice table and omit the old blanket cue;
composition effort is MEDIUM. Measured composition generation is11.4695/17.5710/
6.6778 seconds with1538/2472/911 reported reasoning tokens. Composition caches
show zero hits and8626/7099/4159 written input tokens. Selection has substantial
cache hits. Compared with c11 scouts, the selected nonbenchmark pool sizes change
4→4,2→5,5→5; exact selected records also vary. Therefore neither the table/cue nor
MED alone is established as the cause of the timing difference. These receipts
identify measured work, not queue/network/compute causes.

**Parent-accepted c13 direction: change only composition from MEDIUM to LOW.**
Keep the exact c12 guides, all source aids, schema, checker, pool bounds, preview
and correction topology. Selection and conditional correction remain LOW. This
isolates effort with the current representation: the earlier c08 LOW failures
occurred before explicit condition applicability and selected-choice facts, so
they neither prove nor disprove this candidate's semantic reliability. No new
source facts, extra editor, NONE effort, reminder ladder or changed limits are
bundled into the experiment.

Before live execution, request-level tests should verify that the c13 composition
reasoning setting is the intended sole effective request change for the same
source/selection, and that selection/correction requests and prior replay remain
unchanged. Fresh scouts still require all H/U/M2/C/K/P axes and both timing gates;
a faster weak answer cannot advance. Passing scouts still need the declared fresh
six-source confirmation and actual controlled correction, with no replacement of
failures. All six saved confirmation sources are now known, regardless of fresh
generation; do not describe later cohorts as unseen-source validation.

Twelve iterations are used and eight remain. The next mandatory actual checkpoint
is post-c15, or earlier final architecture review before scoped closeout. This
pre-c13 stewardship does not replace it. All owner-approved natural Luna language,
flight-card, Ranking/Q3, independent-explorer and cash-sentence requirements remain
unchanged, as do frontend/M3 separation and provider/FX exclusions. No runtime edit
or live call was made by the guardian. Lower-effort semantic quality and latency
remain empirical uncertainties; no unresolved design boundary requires escalation.


## C13 outcome and architecture escalation recommendation

C13 changed only composition effort to LOW relative to the c12 design. All
checked workflows meet timing at12.2172771/11.8272644/8.8979303 seconds. The runner
reports45 strict-verified archives and88 paired generation/count attempts. No
confirmation follows the failed source gate; controlled repair remains unrun.

Q043 passes U/C/K/P and fails H/M2. The business caption says it arrives at the
same time as a “shown Turkish economy option,” but that exact Turkish economy
J124 is present only in the optional input pool. The displayed economy is
Aeroplan J1, arriving105 minutes later than business J217. The J124/J217 equal
arrival relation in the input is correct; its endpoint is not displayed. The
other caption also refers to nonexistent “other shown economy awards.” The
writer validly reduces five pool records to two cards but leaves unsupported
prose referents behind. Shared award price scope is repeated in both captions.
This is not an alias resolution/card failure or grounds to require every pool
member to be displayed.

Q044 passes H/U/C/K/P and fails M2. All four relevant options are displayed, but
both complete-journey captions repeat shared party/tax/price/separate-ticket
checks, and both lead captions repeat schedule/scope checks. Its conditional
program reasons and temporal comparisons are valid. Thus optional-pool leakage
is not the sole defect: explicit displayed-reference planning alone would not
address this second draw's repeated limitations. Q045 passes every source axis,
with useful conditional program/date/cabin research reasons and consolidated
scope. These grades are preserved; a passing incomplete case does not qualify
the complete branches.

The guardian inspected the actual q043 guide, selected-choice records, all
thirty selected temporal relations and source review, plus final q044/q045 source
reviews and saved summaries/settings. The guide already explicitly prohibits
referring to omitted members. C12's admitted MED draw selected four pool members
and carried18 temporal relations; c13's admitted LOW draw selected five and
carried30. Different selections and facts prevent a causal effort-only quality
claim from these draws despite the fixed candidate intervention. Earlier c12
MED scouts passed all source axes but failed timing; current LOW complete scouts
fail source composition/factuality despite ample timing margin.

### Why no speculative c14 seam is selected here

The architect recommended **deep-architect escalation before freezing c14**,
and the parent invoked a fresh deep architect with the actual failure evidence
and protected goals. The remaining choice of intervention is materially uncertain:

- An admitted/conditional-status effort branch has no established semantic
  relationship to authoring complexity. Both complete sources regressed here;
  restoring MED only for mixed-status/admitted input would not address q044.
- A new leading displayed-reference declaration could expose the subset decision
  within the same composition call, while keeping prose unbound, but it does not
  address q044 where every discussed card is shown. It adds an output/check/replay
  contract without demonstrated benefit for both current failure modes.
- A uniformly smaller engineering pool ceiling, starting from c12 MED, could
  bound author input and pair counts while preserving model selection, exact
  category witnesses, optional subsets and the full explorer. It could also lose
  useful research breadth; V28–V30 show that a small ceiling does not establish
  coverage or meaningful explanation. Current coverage audits improve that
  boundary but do not prove this tradeoff is worthwhile.
- A compact lossless author projection could reduce repeated evidence, but the
  largest fields are source records and comparison relations. In c12 admitted,
  serialized records occupy roughly12.9k characters and temporal relations4.1k;
  the other major tables preserve useful choice/condition facts. Naive component
  factoring must handle context-dependent `same_as_journey` times without changing
  meaning. Trimming small metadata alone is not supported as sufficient, and
  input size does not establish reasoning duration.

The escalation question is concrete: choose one bounded next experiment that
preserves current natural-authoring/source boundaries while addressing the
observed quality/latency tradeoff, or identify the specific remaining blocker.
Compare the actual failed requests and positive c11/c12 evidence; do not choose
an effort branch by saved case identity, introduce code ranking or quotas, bind
numerical clauses, add an unconditional editor, relax gates or reinterpret
historical failures. This is an architecture recommendation for parent routing,
not authorization for runtime changes or a claim that any alternative succeeds.

Thirteen iterations are used and seven remain. The pending actual post-c15
checkpoint and earlier final review requirements remain. All owner-confirmed
Q3/card/Ranking/cash/natural-language goals, six-axis source review,22s individual/
20s median gates, bounded three-call path, known-source limitations and frontend/
M3 exclusions stay intact. The guardian made no runtime changes or live calls.


## Accepted c14 experiment after deep architecture review

The parent read and accepted the completed
[c14 deep design review](../reviews/2026-10-29-results-category-led-c14-deep-design-review.md).
The guardian also read the final report and finds no conflict with the protected
M2 goals. Implementation and independent union-cap/historical-failure checks are
underway; no live c14 result or quality claim is recorded here.

Use **c12 as the baseline: LOW selection, MEDIUM composition, LOW conditional
correction**, changing only the selected authoring-pool ceiling from six to three
unique nonbenchmark journey/lead references, plus at most one cash benchmark.
Corresponding selector wording, schema and explicit union validation carry this
engineering bound. This is not an assertion that c13→c14 changes only one setting.
All source records, choice facts, temporal relations, condition applicability,
composer guide/wire, source cards, cash context and correction topology stay as
in c12. The full selector inventory and independent explorer remain unchanged.

Three is a ceiling, not a requested card count, one-per-style quota or ranking
rule. Nonnull style witnesses and free choices are unioned and identity-deduped;
witnesses absent from free choices still count. Three disjoint category witnesses
can fit, while overlap may use fewer. The author may show a smaller useful subset.
Code cannot select, truncate, drop a witness or invent an omission rationale to
fit the bound. A schema-valid free list can still overflow through separate style
witnesses: the explicit decoder union check remains authoritative, and failure
stops after the actual selector call without an added retry. Historical profiles
retain their original limits and replay, including c07 failures.

The hypothesis is reduced comparison/subset/scope-allocation work at MEDIUM,
not proven faster inference or reliable prose. Q034 previously selected six and
passed at16.123s; q040 selected four and took20.925s. Q041 was slower despite fewer
temporal relations and smaller input than q040. The change therefore must not be
sold as count-causes-latency. It still permits omitted-pool references and cannot
mechanically prevent q043's prose mistake or q044's repetition.

Coverage risk remains explicit: q033 used four useful displayed leads, and no
retroactive redundancy claim is made. V28–V30's small-pool failures remain relevant.
Current exact category audits and full-source review help detect omissions but do
not prove three choices always suffice. Losing a material direction due to the
ceiling is a failure, not evidence that the source is sparse. Q3 still allows
conditional program/date/cabin reasons without mandatory pairs or numerical
contrast. No automatic cap-two follow-up or new prompt ladder is authorized by
this experiment.

Before live freeze, require exact union/overlap/witness-only overflow controls,
valid three-lead-plus-cash and three-disjoint-style cases, optional subset/category
checks, unchanged c12 composer/correction requests on the same valid pool, and
historical replay isolation. Then apply the unchanged three-scout gates; only
complete success advances to six fresh confirmation draws on the six now-known
sources, then the actual fixed-source controlled-correction diagnostic. Preserve
all failures and22s individual/20s median gates. Record pool/visible counts, input
size, phase timings, reasoning usage and cache observations without causal claims.

This is an engineering ceiling under the accepted design; no new ADR policy is
needed. Parent integration/build-log ownership remains unchanged. Thirteen
iterations are used and seven remain before c14 runs. Post-c15 or earlier final
closeout is still the next mandatory architect review. The guardian made only
this plan update; no runtime edits, live calls or delegation occurred.


## C14 disposition and accepted c15 indexed selector

All three c14 scout attempts are complete. The admitted selector returns free
choices J13/J7/J11/C1 and a premium witness J217; after deduplication that is four
nonbenchmark identities plus cash. The c14 decoder correctly rejects overflow
and saves a one-call schema failure at6.363 seconds. No answer exists for q046;
this is not qualifying response latency or a source-composition grade. The main
array satisfied its own bound, but independent audit aliases expanded the union.
No witness was clipped, no fallback answer emitted and no extra retry occurred.

The conditional answer q047 passes all six source axes at12.101 seconds. It gives
valid same-program reported-point, cabin and timing reasons, with shared checks
consolidated. The incomplete q048 delivers at11.342 seconds and passes U/M2/K/P,
but fails H/C under an explicitly qualified interpretation: its Alaska/date
condition is valid, while calling Alaska's raw point count the lowest among the
shown economy leads is used as a rationale against United. The raw numeric order
is true; the review judges the recommendation context to imply unsupported
cross-program economic advantage and acknowledges that a strictly literal reading
could pass. Preserve the original grade and this uncertainty. Conditional program
or date reasons remain allowed; no same-program pair or numeric quota is added.

The guardian read the actual overflow response, schema/decode/preparation code,
both delivered answers and final q047/q048 source reviews. The runner reports48
strict-verified archives and93 generation plus93 exact-count attempts, with no
drift or retry. No confirmation follows. Fourteen iterations are used and six
remain. The failed selector already prevents qualification, independent of the
qualified semantic failure in q048.

### Parent-accepted c15 experiment

Change only the selector response representation to one bounded identity list:

- `choices`: at most three exact nonbenchmark journey/lead records, retaining
  explicit source role and alias; no benchmark may appear here.
- A separate exact cash-benchmark alias or null, with current identity/cardinality
  and available-cash omission checks preserved.
- Required time/cost/premium audits referring to a zero-based `choice_index`
  in0..2, or null with the appropriate explicit omission reason. Audit fields
  cannot add source identities to the selected pool.

This makes the schema's three-item bound cover every possible nonbenchmark
identity. Code still validates actual array length, duplicate identities, exact
roles and source membership. An index must be an integer, not a boolean or
fractional value, refer to an existing array element and identify a journey in
the addressed authoritative source category. A lead cannot witness a category.
One overlapping journey may serve several style audits without another entry.
Unavailable styles use null with no reason; genuine available omissions need a
reason, and omission claims must agree with actual coverage from the whole array,
including incidental overlap. No code-selected member, guessed alias, truncation,
new ranking or automatic repair is introduced.

The loss of the old audit field's per-style source-alias enum is explicit:
indexed audits cannot prove membership through native schema alone. Exact decoder
checks supply that semantic validation, and malformed selections retain explicit
saved failures. Normalize valid choices into the existing `StructuredSelection`
so identical chosen references yield the same authoring/correction requests and
facts. Keep LOW selection, MEDIUM composition, LOW conditional correction, the
three-plus-cash ceiling, all c12 source aids, current author wire/guide, optional
smaller display subset, source cards, cash context and maximum three-call path.
Historical profiles retain old schemas and replay, including q046's overflow.

This is a structural fix for a demonstrated selector failure, not a claim to
resolve ordinary cross-program prose meaning or ensure useful selection. Do not
bundle a numerical-prose prompt rewrite or criteria change. Q048's independent
H/C risk remains subject to the same source gate. No inline clause binding,
compulsory layout or another editing call is added.

Before live freeze, test in-range/source-member audits, three disjoint categories,
overlap, witness index reuse, leads without styles, empty/absent-category branches,
invalid integer types and bounds, nonmember/lead category slots, contradictory
omissions, duplicate choices and wrong cash identities. Four nonbenchmark entries
must fail the native schema; no audit can produce a fourth identity. Verify exact
historical failure replay and unchanged downstream requests for equivalent
selections. The parent integrates implementation and records the build log; the
guardian made no runtime edits or live calls in this steering review.

The mandatory **actual post-c15 architect review occurs after all three scouts
and source grades, before any confirmation or next candidate**, even if the
scouts pass. This pre-c15 design steering does not satisfy that checkpoint. All
other quality/timing, known-source, actual-repair, stage ownership and frontend/M3
constraints remain unchanged. No further escalation is needed for this bounded
selector seam before seeing its evidence.


## Mandatory post-c15 disposition and accepted c16 clarification

The [mandatory fifteenth-iteration review](../reviews/2026-10-29-results-category-led-c15-architect-review.md)
is complete after all three source grades and runner verification. Q049/q050 pass
all six axes; q051 passes U/M2/K/P but fails H/C for using lower raw Alaska points
as a reason to investigate it against displayed United. Exact numbers and valid
conditional program reasons do not establish that economic advantage. Preserve
the source review's literal-count interpretation uncertainty and original grade.
Q050's opening/“requires” wording has explicitly nonblocking contextual limits.

All checked times17.56484/17.13351/12.10720s pass, median17.13351s. All are clean
two-call deliveries without drift, retry or correction. Runner strict verification
completed51 archived runs and99 paired generation/count attempts with zero issues.
No confirmation or controlled repair follows q051's failure; no adoption/closeout
claim is made.

The indexed selector successfully keeps all identities in its single bounded
array and separates cash, while exact source validation remains in the decoder.
Actual pools2/2/3 become2/2/2 cards, with model-owned order and optional subset.
Ranking perspectives, source cards, consolidated conditions and cash context pass
their source gates. Semantic prose remains independently judged: the corrected
selector cannot make cross-program raw counts economically comparable. No causal
latency improvement is claimed from these different selected pools/cache states.

The parent read the complete mandatory report and accepted the architect’s c16
experiment: replace only the ambiguous writer clause “Do not force same-program
pairs, a lowest-points rule, or cross-program economic ranking.”
Separate optional comparison methods from an explicit statement that different
programs' point counts are different units: a smaller count in another program
is not an advantage or a reason to favor/investigate that lead. Supported
conditional program/date/cabin reasons remain sufficient on their own, and
scoped same-program reported comparisons remain permitted. All raw facts/card
numbers remain, with no clause binding, new checker, required pair, layout change
or added call. The recommendation is grounded in q048/q051 and an actual guide
ambiguity; causality and future effectiveness remain unproven.

Keep all other c15 selector, pool, effort, input aids, output schema/checks,
card/cash and correction settings. Only prospective author/repair guides change
under this accepted experiment; the selector and historical replay remain
unchanged. Implementation, independent review and bounded evaluation may proceed
under the existing authorization. No quality result or success is implied by
acceptance. Five iterations remain, with the hard c20 stop and mandatory c20
or earlier final review intact. All quality/timing/confirmation/actual-repair,
known-source, stage ownership and frontend/M3 constraints remain unchanged.


## C16 evidence and accepted c17 same-source scope normalization

C16 completes at18.733/17.876/14.450 seconds, all timing gates passing, without
correction or drift. Q053/q054 pass H/U/M2/C/K/P. Q052 passes H/U/C/K/P but fails
M2: a paragraph first explains that both awards have unknown tax-quote scope,
then immediately repeats that the Aeroplan CAD107.40 quote has unknown scope.
The second sentence adds no new condition. Business-only party support, tax
amount and positioning quote scope are distinct and are not counted as this
failure. The guardian read q052's actual answer, writer request and sidecar,
plus all three final source reviews. The runner verified54 archives and105 paired
generation/count attempts with zero integrity issues. No confirmation follows.

Q054's conditional program reasons avoid the prior cross-program advantage.
This coincides with the c16 clarification but does not establish causality or
stable compliance. Repetitive caption syntax and the wording introducing three
shown leads are recorded as minor, nonblocking observations under the unchanged
rubric. Do not reopen program-unit policy, indexed selection or card count to
address q052's different failure. Sixteen iterations are used and four remain.

### Traced duplication and exact accepted contract

`category._condition_applicability` currently emits both `award_price_scope`
from `facts.award.price_scope` and `award_tax_quote_scope` from the attached
award-tax quote. In q052 both rows are unknown and apply to exactly J1/J82.
These are not independent scope observations in the current source construction:
`currency.observed_money` copies `SolutionComponent.price_scope` into award-tax
money scope, and `journey_money` copies that same award component's field into
point scope. `focused_records.writer_packet` binds component quotes through the
journey's exact award reference and checks that component reference against the
member. The two conditions expose the same underlying uncertainty twice.

The parent accepted one c17-only input normalization, with no prompt/effort/selection
or output changes. Emit `award_points_and_tax_quote_scope`, state `unknown`, for
an exact journey alias only if all of the following hold:

1. The record is a journey, with a nonempty exact `member.award_ref` equal to
   `award_component.ref`.
2. The attached quote is explicitly `kind=award_taxes`.
3. Both `facts.award.price_scope` and the attached quote's `price_scope` are
   explicitly `unknown`; absence, null or another state does not satisfy this.
4. The existing source-preparation provenance remains established: both fields
   are projections of that exact award component's canonical `price_scope`, not
   independently sourced values that merely happen to have equal strings.

The new code means **one source price-basis uncertainty applies to the reported
award points and its award-tax quote**. It says nothing new about the amount,
party support, total fare or economic value. It replaces the two old scope codes
for that alias only. Mixed pools may merge some aliases and retain separate old
codes for others. If identity/provenance is unavailable or conditions differ,
retain the original separate rows; do not invent a match or silently drop a fact.
The current trusted preparation seam supplies provenance; a broad new upstream
matching verifier is not proposed.

Keep `award_tax_amount` and its absent/null/unknown distinctions, award-party
support, positioning permission, separate-ticket obligation, positioning-cash
scope and benchmark-cash scope unchanged. Never merge distinct components or
roles just because they both say unknown. Lead conditions are unchanged because
this observed duplicate is in journey projection. Raw source records, cards and
all quote states remain available, and any actually shared condition still uses
its exact affected aliases. There is no new narrative placement or wording rule.

This normalization is more specific than another instruction to avoid repetition,
but its causal contribution to q052 is unproven. The guide already asks for one
explanation per condition, and Luna could still repeat a single row. The source
review remains authoritative; fewer input rows are not a semantic pass. The
traveler-facing goal stays a natural explanation of the practical cost uncertainty,
not reciting technical scope codes. Do not bundle a prompt rewrite or new
presentation criterion under that goal.

Before live freeze, require positive q052 controls (both aliases normalize,
eight rows become seven), same-valued unknown scopes with mismatched component
refs not merging, distinct/missing states not merging, one-sided point/tax scope
conditions retaining their appropriate code, mixed-pool partial normalization,
separate cash/benchmark contexts, and preservation of known zero amounts and
unknown-versus-absent tax amounts. Old profiles and all54 saved artifacts keep
exact prior condition tables/replay. For a fixed selection, all other c16 request
content remains unchanged, including its program-unit clause and LOW/MEDIUM/LOW
settings. No additional call, checker, code-written sentence or inline binding
is introduced.

This is an engineering normalization inside the existing trust boundary, with
no new ADR policy required. The parent adopted this precise contract and owns integration; no c17 result
is claimed. The parent owns the build log. The next
mandatory checkpoint remains post-c20 or earlier final closeout, with all source,
timing, confirmation, actual-repair, known-source and stage-scope limits intact.
No runtime edits, live calls or delegation were made by the guardian.


## C17 evidence and accepted c18 natural-choice explanation experiment

C17 completes at18.911/16.343/12.034 seconds, all timing gates passing. Runner strict
verification passes57 archives and111 paired generation/count attempts with zero
issues. Q055/q057 pass all six source axes. Q056 passes H/U/C/K/P and fails M2 on
an explicitly editorial judgment: its opening describes a “time-qualified set,”
restates business cabin as a premium-cabin choice and adds an unanchored disclaimer
that this does not establish earlier arrival. The single card's caption consists
entirely of conditions to check. The source reason exists, but the response reads
as classification explanation rather than natural guidance for a traveler.

The guardian read q056's actual answer, source review, author guide, category
landscape and schema. The guide's “qualifying duration band” and negative timing
rule correspond closely to the delivered classification/disclaimer language; this
is an observed textual connection, not proof of causality. The condition table
avoids the c16 duplicate-scope pattern in the current draws without proving a
stable semantic fix. Do not treat a schema/sidecar pass as composition quality.

Q056's one real time/premium overlap card is valid. C passes narrowly for business/
time benefits with separate-booking burdens; its omitted economy alternative is
not a mandatory-pair or card-count failure. The qualified editorial M2 grade is
preserved without changing the rubric. Full source facts, useful perspectives,
Q3 research options, exact cards and consolidated uncertainty remain protected.

The parent accepted **one bounded c18 author-paragraph replacement**. It gives
complete-journey captions an explicit choice-explanation responsibility and keeps
technical comparison constraints in model reasoning, rather than offering them
as traveler-facing qualification prose. No schema description, output field,
layout template, comparison minimum, forced benefit or card quota is introduced.

The exact old span to replace is the following paragraph plus its trailing space:

```text
For complete journeys, explain the supported benefit that distinguishes each shown choice, such as a shorter trip, cabin or connection buffer. Use Ranking's time/cost/premium memberships as source facts, but describe the traveler benefit in ordinary language, with no empty category notices or mandatory headings. Time membership means a qualifying duration band, not earlier arrival or dominance over another selected journey. Use selected_temporal_relations for relative departure, arrival or duration claims; preserve equal arrivals as equal and do not substitute one metric for another. Category overlap does not create an overall winner.
```

The exact replacement is the following paragraph plus its trailing space:

```text
For each shown complete journey, explain when a traveler might choose it using a supported fact, such as cabin, timing, trip duration, connection details or a scope-qualified cost or point quote. Put that decision reason in k=p or a's v; a relevant local condition may accompany it, but a checklist alone is not a reason. Use Ranking's time/cost/premium memberships to preserve the useful perspectives, and express overlapping strengths once in traveler language rather than explaining category qualification. One journey can be enough; do not invent a benefit or add a comparison just to fill a pattern. Keep these evidence limits in your reasoning: time membership alone proves neither earlier arrival nor superiority over another shown journey, and overlap is not an overall winner. For any relative departure, arrival or duration claim, use selected_temporal_relations, preserve equal arrivals as equal and do not substitute one metric for another. If no useful supported comparison is being made, omit it rather than adding a disclaimer about a comparison the answer never makes.
```

Apply the replacement only in the prospective c18 profile. Preserve every other
c17 guide section, including c16's program-unit rule and shared-condition/cash
instructions, and preserve all source facts, c17 provenance-backed normalization,
selected temporal/choice aids, indexed selector, three-plus-cash ceiling, current
LOW/MEDIUM/LOW effort, author wire, checks, card display and bounded correction.
The ordinary model-written numbers remain unbound. A single option remains valid,
and the instruction does not require a benefit that the source cannot support.

Verify exact old-span removal/new-span insertion, with no other effective request
change for a fixed source/selection; the selector and source packet remain exact.
Historical requests and57 archives must retain their original replay behavior.
Fresh source review must judge the delivered language independently: less internal
terminology alone does not prove useful explanation, and natural wording cannot
excuse false comparisons or missing category perspectives. No reviewer criteria
or timing gates change, and no confirmation follows c17's failed scout gate.

Seventeen iterations are used and three remain: c18–c20. The hard c20 stop and
mandatory post-c20 or earlier final review remain. The parent owns integration
and build-log recording; this is an engineering authoring experiment under the
existing design, not a new stage/Ranking/ADR policy. No runtime edits, live calls
or delegation were made by the guardian, and no broader quality or causal claim
is implied by acceptance.


## C18 evidence and accepted c19 quote/condition interpretation experiment

C18 completes at18.641/13.532/12.580 seconds, all timing gates passing. Strict
runner verification passes60 archives and117 paired generation/count attempts
with zero issues. Q058/q060 pass all six source axes. Q059 passes U/C/K/P but has
a qualified H failure and an M2 failure. No confirmation or repair follows.

Q059 accurately reports110,000 and275,000 Turkish points in its caption/cards,
but later asks to clarify point/tax amounts and scope and calls “these details”
unknown. The source distinguishes known reported point amounts from unknown
pricing basis and unknown tax amounts. The source review preserves a charitable
final-payable-amount interpretation, while judging the blanket claim materially
misleading without that qualification. It also fails M2 because the economy
caption already qualifies both quotes' scope, and the shared checklist repeats
that same uncertainty. Distinct tax amount, party support and ticket conditions
are not duplicates. Original grades and interpretation limits remain unchanged.

The guardian read the actual q059 answer, review, writer guide, condition table,
selected-choice rows and exact award records. The normalized table contains only
one shared award-scope condition; raw110000/275000 values are present, and tax
amount state is independently unknown. No missing source fact or duplicate
condition row was found. The merged code's contribution to the prose conflation
is uncertain; do not undo correct c17 normalization or claim it caused the error.

The parent accepted one **c19 quote/condition paragraph replacement**, preserving
all c18 facts/settings and earlier unit/natural-choice rules. It clarifies how
to interpret and allocate already-correct conditions: known reported amount versus
unknown basis, precise affected fields/choices, and existing local or shared
qualification satisfying the one-explanation responsibility. This is not a new
criterion requiring qualifications next to every numerical comparison. Shared
qualification remains equally valid, with no mandatory limitations block or
fixed position. The model still writes practical traveler language.

Exact old span, followed by its trailing space:

```text
Preserve each quote's scope: incomplete or unknown-scope amounts do not establish a per-person fare, all-in trip cost or cheapest-overall choice. The condition_applicability table gives source condition codes, states and exact selected-pool aliases, not words to copy. Consider only the choices you actually show; explain each relevant condition once in natural language, locally when it changes that choice's next action or together when it applies across shown choices. Do not repeat a condition in both places or infer one from a missing field.
```

Exact replacement span, followed by its trailing space:

```text
Preserve each quote's meaning: a reported number and its pricing basis are different facts. Unknown scope does not make a known points, tax or cash amount unknown, and incomplete quotes or reported amounts with unknown scope do not establish a per-person fare, all-in trip cost or cheapest-overall choice. Use the condition_applicability table only for the specific source fields and shown choices to which each condition applies; keep amount uncertainty, quote basis, party support and separate cash roles distinct. Explain the practical consequence of a relevant condition once, in your own words. Its explanation may sit with a choice or comparison, or in shared prose; either placement is sufficient. If it is already qualified locally, a later shared paragraph should cover only the remaining distinct conditions, not restate that qualification as another check. Do not turn the table into an extra checklist after those conditions have already been explained. Do not group known reported amounts into a blanket 'these details are unknown' statement or infer a condition from a missing field.
```

Apply only to c19's author guide and the existing correction requests that inherit
it. Keep c16's cross-program rule, c17's provenance-checked scope normalization,
c18's natural-choice paragraph, all raw records/cards/sidecars, indexed selector,
three-plus-cash bound, LOW/MEDIUM/LOW settings, output schema/checker and maximum
three-call path unchanged. No known value is suppressed or converted to missing;
no numerical clause binding, semantic regex, new field or editorial call appears.
The experiment targets both q059 findings through condition interpretation and
responsibility; it does not prove future compliance or revise the frozen rubric.

Request-isolation controls must show exact old/new replacement and no other
content change for a fixed source/selection; selector requests and source packets
stay identical. Historical60 archives retain their original requests/replay.
Known numeric zero remains known, reported amounts never acquire a per-person/
all-in basis through this instruction, and genuinely unknown amount/party/cash
conditions still need their appropriate treatment. Actual independent source
review, rather than a hand-edited example or text-presence test, judges whether
the generated answer respects these distinctions without repetition.

Eighteen iterations are used; only c19 and c20 remain. The hard c20 stop and
mandatory post-c20 or earlier final review remain unchanged. Parent integration
and build-log ownership remain; the parent will read the exact passage before
freeze. No quality or causal improvement is claimed, and all source/timing,
confirmation/actual-repair, known-source, Ranking/Q3, card/cash and frontend/M3
constraints persist. The guardian made no runtime edits, live calls or delegation.


## C19 evidence and accepted c20 final candidate

C19 completes at17.963/12.488/15.752 seconds, all timing gates passing. Runner
strict verification passes63 archives and123 paired generation/count attempts
with zero issues. Q062/q063 pass all six axes; q061 passes H/U/C/K/P and has a
qualified editorial M2 failure. No confirmation or repair follows c19.

The guardian read q061's actual answer, source review, writer condition paragraph
and applicability table, plus the final q062/q063 source reviews. Q061 gives one
local scope qualification for the economy quote and another for the business
award quote, with no later shared paragraph repeating them. The review explicitly
calls this close: each exact quote is qualified once, and local placement is
allowed. Under the frozen common-limits-once goal, the shared award-basis condition
still needs one explanation covering the affected choices. Distinct unknown tax
amount, party support, ticket obligations and positioning cash scope are not
penalized. Preserve that original editorial grade and uncertainty; do not invent
a mandatory shared paragraph or retroactively change the rubric.

Q062 preserves known amounts versus unknown scope and uses accurate same-arrival/
departure/duration comparisons; its later positioning-cost consequence concerns
a distinct cash role rather than another award-scope warning. Q063 preserves
known reported taxes and shared scope while offering valid Q3 program reasons.
These passes do not establish repeatability or make the q061 grade disappear.

The parent accepted **one final c20 change**, clarifying the quantifier in two
c19 condition-explanation sentences. A relevant row describes a condition shared
by its affected visible choices; once means once for that group, not once for
each quote. Omitted pool members do not acquire visible disclosure obligations.
No data, grouping code, schema, checker, selection, effort or criteria change is
included. No additional architectural variant is authorized after c20.

Exact old span, followed by its trailing space:

```text
Explain the practical consequence of a relevant condition once, in your own words. Its explanation may sit with a choice or comparison, or in shared prose; either placement is sufficient.
```

Exact replacement span, followed by its trailing space:

```text
For each relevant condition_applicability row, consider only its applies_to choices that you actually show. Explain the condition's practical consequence once for that whole affected group, in your own words, not separately for each quote or card; make clear which shown choices it covers. A condition affecting only one shown choice can stay local. This explanation may sit in a caption, comparison, opening or other prose; no separate shared-limits block is required.
```

Every other c19 sentence remains, including the pre-freeze correction retaining
**incomplete quotes with known scope** as unable to establish per-person/all-in/
cheapest conclusions. Known amount versus unknown basis distinctions, genuine
singleton conditions, different source fields/party/tax-amount/cash roles and the
later-paragraph responsibility stay intact. The explanation can appear in the
first suitable caption, comparison, opening or other prose; neither a dedicated
shared block nor a fixed order is required. Natural Luna wording, source cards,
Q3, category coverage/overlap and numerical prose ownership remain unchanged.

Verify exact two-sentence replacement and otherwise identical fixed-input
requests; selector, source tables, output wire, card display, LOW/MEDIUM/LOW,
three-plus-cash bound and three-call maximum remain exact. Historical63 artifacts
retain original requests/replay. Any empirical benefit is unproven; this is a
precise interpretation experiment rather than a guarantee of semantic compliance.
The reviewer must continue judging actual prose against the same frozen standard,
with editorial uncertainties disclosed.

Nineteen iterations are used and c20 is the final permitted candidate. After its
three actual scouts and all source grades, the **mandatory post-c20 architect
report must precede any confirmation or closeout**, even if scouts pass. If all
scout gates pass, that report may clear only the unchanged c20 candidate for the
predeclared six-confirmation cohort and, only after that passes, the fixed-source
actual controlled repair. A final architect addendum must consider those outcomes
before scoped qualification. No c21, automatic follow-on design change, failed-draw
replacement, lowered source/timing gate or spare-budget extension is permitted.

The parent owns integration and build-log recording and will read the exact span
before freeze. The guardian made no runtime edits, live calls or delegation.
All known-source,600/600 attempt, zero-retry, provider/FX, independent-explorer and
frontend/M3 constraints remain. A failed final candidate leaves the declared M2
revision open; the iteration ceiling must not be treated as success evidence.


## Final c20 evidence, mandatory reflection and goal disposition

The [mandatory post-c20 architect review](../reviews/2026-10-29-results-category-led-c20-architect-review.md)
is complete after all final source grades and runner verification. C20 completes
at18.759/16.873/12.450 seconds, median16.873, with two generation/count calls per
workflow, clean delivery and no correction/drift. All timing gates pass. Q065/q066
pass all six source axes. Q064 passes H/U/C/K/P but fails M2: the business caption
requests checking its separate-ticket arrangement and later prose repeats the
same ticket-obligation uncertainty without a distinct consequence. Its source
table has only one singleton condition, and the final guide already requires
one explanation. Common award scope is correctly consolidated. This does not
justify another condition-group prompt, relaxed standard or retroactive pass.

The original review's wording limits remain, including q066's minor adjacent
date-only descriptor/explanation overlap judged nonblocking. No mandatory shared
block, card quota or comparison pair is introduced. Q064's exact shorter-trip
versus earlier-arrival comparison, q065's true time/premium overlap and optional
same-program alternative, and q066's conditional Q3 program choices demonstrate
the intended cards-and-natural-reasons shape without establishing consistency.

Strict verification passes66 archives and129 generation plus129 exact-count
attempts with zero issues. There are62 delivered artifacts (59 clean,3 annotated)
and4 original undelivered selectors (q019–q021 and q046). Zero SDK retries and no
provider/live FX calls occurred. Only c11 reached six confirmations, with five
source passes and one M2/C failure. No controlled-repair diagnostic was reached;
c03's ordinary natural repair is historical-profile evidence only. No c20
confirmation, repair, replacement draw or extra paid call follows its failed gate.

Current frozen-code verification reported by the independent worker is112 category
tests passed in358.46s with unchanged source hashes, Ruff and mypy over64 files
passing. Runner verification is separate from semantic acceptance. The earlier
1310-pass/99-skip/two-gfly-environment-failure baseline has a mixed-worktree caveat;
no current full-repository pass is claimed. The guardian's own verification is
read-only source/request/answer/receipt inspection plus local-link/diff checks.

All six sources are previously seen. No novel incomplete source or observed full
cost-reference case exists; offline synthetic controls remain labeled. C20's
selectors report near-total cache hits and composers cache writes, not a fully
cold end-to-end cohort. Population reliability, correction latency, interactive
explorer/frontend behavior, current provider availability and M3 are unqualified.

**All20 iterations are used and all four mandatory architecture checkpoints are
complete. The user-authorized iteration stop is satisfied; M2 revision is not.**
Public default remains provisional/unqualified V27 and latest category opt-in is
c20, with no adoption. The full acceptance gates, natural Luna wording, Ranking
ownership/overlap, Q3, source cards, one cash sentence, separate source conditions,
independent explorer and frontend/M3 boundaries remain. Required M2 acceptance is
unfinished core work, not an optional follow-up. Parent owns final integration,
state/contracts/ADR/deferred/build-log updates and final response.

### One proposed future cut, with no current implementation authorization

The final architect review proposes an **offline condition-ownership author-wire
prototype**, replacing further prompt-only iteration as the next investigation.
Within the existing composition response, model-authored text fragments would
declare which exact source condition identities they explain; each condition has
one owning visible fragment, with flexible location and Luna-owned words. Code
would validate declared identity/applicability/uniqueness and retention, without
writing explanation prose, imposing a shared section or binding ordinary numeric
comparisons. Required coverage keeps its existing policy; optional tags cannot
redefine it. No extra editorial/model call, product agent, new ranking, pair
quota or mandatory card layout is proposed.

This would verify only declared ownership. Untagged repeated or false prose can
still pass that mechanical check and must fail independent semantic review.
The prototype must test that distinction explicitly against q064 singleton
repetition, q061 group repetition, q059 known-value conflation and q065/q066 valid
flexible answers, alongside negative identity/role/omitted-reference controls.
Adding a clean tag ledger alone would not be a successful outcome. Any future
live qualification would still require the full frozen quality, timing,
confirmation and actual-repair gates under a separately opened task.

This is a proposed next cut, **not an accepted architecture, policy change, c21,
new campaign or authorization to implement/spend**. A prospective contract/ADR
decision may be needed if it is later adopted. No further escalation is needed
for the current stop; material uncertainty in a later interface design should be
escalated before implementation. The guardian made no runtime edits, live calls
or delegation for this closeout.
