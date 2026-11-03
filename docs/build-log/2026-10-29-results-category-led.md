# Results M2 category-led implementation and evaluation

## Invocation and scope

2026-10-29: After confirming design interview Q1–Q8 and reviewing three
hand-authored saved-source examples, the owner accepted the direction with one
correction: flight information belongs in source-resolved cards. The owner
explicitly authorized implementation and review by appropriate subagents, live
evaluation without another permission question, and iteration until the M2
acceptance evidence supports closeout or twenty iterations have run. An architect
must review and reflect at every fifth version and maintain stage/task goals and
constraints. Interpret that cadence as new campaign versions 5, 10, 15 and 20.

This is a new campaign; the historical V3–V30 campaign remains stopped and its
evidence/grades are preserved. Starting HEAD is
`b7bedf5b13daab0ec0d170ba0b519877698ae0ff`, with substantial pre-existing modified
and untracked work. No commit, upstream stage change, travel-provider call, live
FX refresh, frontend implementation or M3 qualification is included.

## Accepted response design

- Flexible natural composition with recognizable time/cost/premium perspectives.
- Preserve materially distinct available category perspectives through selection;
  no fixed one-per-category quota or independent overall ranking.
- Explain an overlapping journey once, recognizing its multiple strengths.
- Give highlighted choices source-supported reasons, meaningful downsides or
  conditions, and useful comparisons without fabricated compensating benefits.
- Translate possible/undetermined costs into natural traveler implications;
  consolidate common missing information once, with distinct caveats local.
- Compare useful research directions when there is no complete journey; leads
  receive no invented Ranking memberships.
- Flight facts appear in code-resolved cards; narrative explains the decision.
- Full-origin-to-destination cash benchmark is one brief source-linked sentence.
- Keep Luna wording, the complete independent explorer, exact identities, frozen
  facts/FX, bounded correction and replay. Ordinary numerical prose remains
  model-authored and outside exhaustive mechanical truth guarantees.

## Prospective acceptance

Review complete answers for faithful category selection/overlap, natural useful
explanation, independent source factuality, source-resolved card delivery and
complete checked workflow latency (approximately twenty seconds, small overage
acceptable), including input counts and actual correction. Engineering tests,
semantic review, owner design acceptance and broader M3 qualification remain
separate claims. Campaign protocol and exact gates are recorded before live runs
in the [maintained plan](../plans/2026-10-29-results-category-led-campaign.md).

## Work and evidence

- Read current handover, project state, Results contract, ADR0029/index and
  deferred entries G06/G08; inspected late runtime/wire and saved-source cards.
- Captured starting 295 Python source/test file hashes and git status in
  `/private/tmp/results-category-start-inventory.json` for change attribution.
- Assigned architect goal stewardship, implementer runtime/tests, and investigator
  runner preparation. Required independent code/source reviews will follow.
- Implementation, tests, live results, failures and final disposition: pending.

ADR disposition: amend ADR0029 and index for this accepted refinement and new
explicit invocation. No Ranking ownership, valuation or trust-policy change.


### Initial regression checks

Parent ran `.venv/bin/python -m pytest tests/unit/test_results_default.py
 tests/unit/test_results_focused_v30.py tests/unit/test_results_focused_recovery.py
 -q`: **29 passed in95.82s**. This checks the existing provisional/default,
V30 and bounded-recovery behavior before new-path acceptance; it is not a full
Results/repository pass. Local documentation check resolved all431 links across
nine current instruction/contract/log/review files; `git diff --check` passed.


### c01 implementation preparation

Added isolated `results/category.py` and `category_contracts.py` with code-resolved
journey/lead cards, an exact source-bound inline cash sentence, category selection
and final-card checks, one conditional correction and exact replay. Implementer
reports12 new-path tests passing; parent independently observed11 passing before
the final duplicate-cash control was added, then independently ran Ruff (clean)
and mypy (no issues in2 source files). Parent ran the new campaign verifier tests:
9 passed in2.43s. Independent review found and coordinated fixes for selected
category disappearance, alias mismatch, missing selection findings, duplicate
cash context, incomplete failure handling, preview segment inference and archive
cross-bindings. Live evidence remains pending at this checkpoint.


### c01 scouts (live, no confirmation)

Runner froze `scout-c01.json` prospectively and ran all three declared source
archetypes sequentially. Complete checked Results timings: admitted16.22s,
conditional10.83s, incomplete9.21s; each used2 generations and2 exact input counts,
with zero cached input tokens reported, zero retries and no snapshot drift.
Ledger totals:6 generation/6 input-count reservations. Strict verifier exits0 for
all3 saved artifacts, exact replay, source/config/request/receipt cross-bindings.
Blind source reviews q001–q003 are pending at this checkpoint.

The admitted selector wrote omission notes for represented time/premium and absent
cost categories, producing3 failed spurious-omission findings; conditional wrote
one for absent cost. This contradicts the omission-audit contract; c01 cannot
advance to confirmation. Parent inspection additionally observed an unsupported
Singapore Airlines label for the HKG Aeroplan option, category-style framing for
incomplete leads, a contradictory cross-program lowest-points statement, and
repeated caveats. Independent grades remain separate. Next hypothesis: explicit
omission-only audit semantics and branch-aware natural authoring with exact source
identity, useful lead contrasts and shared-once uncertainty; retain original c01.

Additional offline controls in `test_results_category_controls.py`: implementer
reports3 passes (16.02s), covering real synthetic Ranking definite/possible cost,
saved undetermined costs, overlapping membership identity and successful bounded
correction/replay. Synthetic state controls are not live prose qualification.


### c01 independent disposition and c02 preparation

Independent reviews saved in q001–q003: q001 H fail (airline identity), K/U/C pass,
M2/P fail (repetition, omitted known cash-component schedule); q002 H/U/K pass,
C/M2/P fail (weak alternative rationale, repetition, component display); q003 H/U/
C/K/M2 fail (contradictory cross-program points, weak lead selection, false style
framing, repeated limits), P pass for truthful date-only cards. No timing/checker
verdicts were supplied to the source reviewer. All three fail combined acceptance;
no confirmation or repair diagnostic is authorized for c01 under this protocol.

C02 appends an immutable prompt hypothesis, leaving c01 exact requests replayable:
clarify genuine omission audits; preserve exact airline/program identity; branch
incomplete composition away from Ranking categories/cross-program points ordering;
use natural category meaning, one explanation per card and consolidated shared
limits; permit useful supported same-program quoted-mileage/cabin contrasts while
withholding complete-cost claims. Opt-in API exports and CLI measure/author/replay
are implemented with zero-retry owned client cleanup; public V27 remains unchanged.

Parent combined tests:18 passed in96.95s. Implementer targeted final c02/CLI checks:
3 passed in21.74s, Ruff and mypy clean. Independent code review found no new
runtime blocker. Runner prospectively fixes cash-component schedule presentation
and verifies historical previews with their SHA-checked archived renderer rather
than rewriting c01 evidence. C02 live results pending.


### c02 scouts and independent disposition

Three fresh frozen scouts completed11.262/10.142/11.124s, each two generations
and two exact counts, clean delivery, zero cached input, retries or source drift.
Strict verification passes all six c01/c02 artifacts and archived previews;
cumulative12 generation/12 input-count reservations. No confirmation followed.

Source reviews q004/q005 pass H/U/M2/C/K/P; minor category jargon is recorded.
The independent fresh q006 reviewer passes H/U/K/P and fails M2/C for repeated
card/caveat recitals and no explanation of useful same-program/date/cabin research
contrasts. Complete-card positioning schedules now pass. Q004/q005 reviewers
disclose prior source/code familiarity; q006 reviewer did not inspect profile,
timing, previous grades or hypotheses. A separate readiness-only reviewer
reported inadvertent prior-grade exposure and was not used to grade q006.

C03 hypothesis authorized from these failures: replace the accumulated author
brief with cohesive natural branch-specific explanation; no empty-category
announcements or repetitive shared gaps; trial lossless program-grouped incomplete
selector input while retaining full inventory and the six-reference engineering
bound. No new Ranking or deterministic lead-order policy. C01/c02 remain immutable.


### c03 scouts, natural repair and goal stewardship

C03 scouts completed15.436/9.655/11.295s; admitted required a real third-call
correction after `missing_cash_context`, final answer clean. Conditional and
incomplete each used two generations. All used Fast tier, with no drift/retries;
selector cached input reported83,219/72,422/1,550 tokens respectively. These
samples do not establish cold-cache latency. Cumulative19 generation/19 counts;
strict verification passes9 artifacts and their archived previews.

Q007 passes all axes. Q008 fails H/M2: the opening opposes earlier arrival and
business cabin although its business journey offers both; U/C/K/P pass because
the body explains a real economy connection-buffer tradeoff. Q009 original review
passes H/U/K and fails M2/C/P, including one cash sentence duplicated verbatim in
narrative and bound cash blocks. No c03 confirmation.

Architect stewardship before c05 flags potential C-rubric drift: the owner
explicitly accepted conditional program-access/date/cabin research reasons, not a
mandatory numerical or same-program comparison. Original q009 grade is preserved;
a separate adjudication records the disagreement. Prospective c04 instructions
clarify this original scope without lowering factual/card/latency requirements.
C04 is bounded to exact duplicate-cash detection under a new profile/check policy,
one-place cash guidance and source-consistent opening comparisons; retain c03
selector grouping/cap/effort rather than invent a new lead-ranking policy.


### c04 scouts and c05 targeted hypothesis

C04 scouts12.8145/10.6651/9.7958s, each two generations/counts, clean mechanical
outcomes, Fast tier, zero retries/errors/drift. Selector cached input reported
83,219/83,222;72,422/72,425;76,366/76,369 respectively. Strict verification passes
all12 artifacts/archived previews, cumulative25 generation/25 count attempts.
Q010 and q012 pass all six axes; q012's conditional program/date reasons meet
owner Q3 without a forced numerical pair. Q011 fails H/M2/P: identical business/
economy arrivals are called earlier for business, common protection is explained
three times, and cash wording includes confusing unsupported 'one-stop-free'
while source states two stops. U/C/K pass; source card joins remain correct.
No confirmation followed.

Guardian's pre-c05 steering chooses one bounded design hypothesis: keep LOW/LOW
and restore compact canonical selected-pair departure/arrival/elapsed relations,
including equality and exact deltas, to the writer packet. No full dossiers,
inline wording binding, extra editor or simultaneous MEDIUM effort change. New
neutral guidance separates Ranking's time band/overlap from selected-pair
superiority; shared protection once, brief source-faithful cash wording. Old
V11–V22 lessons mean facts cannot guarantee prose truth; source factuality remains
a separate hard gate. C05 actual evaluation must receive the mandatory fifth-
iteration architect review before continuing or qualification decisions.

Implementer targeted c05 controls:4 temporal tests pass; exact q011 oracle is
same arrival, economy elapsed shorter187min, business departure earlier187min.
Old12 actual artifacts replay under current code. Full category suite and c05
live results pending at this checkpoint.


### c05 final disposition and mandatory architect checkpoint

C05 complete checked times10.8838/22.8432/9.8216s; all three two-call clean outputs,
no drift/errors/SDK retries, high selector cache. The conditional draw exceeds
22 seconds and remains a failed draw without replacement. Cumulative31 generation/
31 exact count attempts. Strict verification passes all15 saved artifacts and
archived previews. All c05 source factuality axes pass, but q013 and q015 fail M2;
q014 passes every source-review axis but fails latency. No confirmation.

The [mandatory fifth-version architect review](../reviews/2026-10-29-results-category-led-c05-architect-review.md)
reads actual answers, guides/packet/schema, checks and timing receipts. An offline
five-to-two visible-card probe passes structural checks, confirming no forced
pool-display quota. The author guide's per-choice downside obligation plausibly
conflicts with common-gap consolidation; causality is not established. Matched
c04/c05 selector request bytes with similar output/cache have4.993/14.982s
selection generation, so no queue/compute attribution or temporal-aid blame.

Parent adopts c06: replace the author guide coherently, explicitly treating chosen
records as an optional authoring pool, preserving meaningful category perspectives
while omitting unhelpful extra variants. Use individual reasons or conditional
research actions, avoid a separate local downside when uncertainty is common,
and explain shared limitations once. Retain selector/LOW efforts, schema/checker,
caps, exact temporal facts, cash deduplication and Q3; no new ranking, forced lead
pairs, regex common-gap checker or extra editor. Implementation/live evidence
pending. Next mandatory architect checkpoint c10 or earlier closeout.


### c06 composition progress and category-selection failure

C06 scouts9.8750/10.7978/10.6440s, each two generations/counts; no retries/errors/
drift, high selector cache. Q017/q018 pass all six axes, including optional lead
subset and shared-once limitations. Q016 passes H/U/C but fails M2/K/P: five
selected economy records omit the available116 premium members without rationale;
generic availability repeats before canonical guidance; cash text adds irrelevant
unknown-fee-unit wording despite the known major-unit cash fare. The ambiguity is
not graded as an unambiguous H falsehood. Admitted selector finding is explicit;
no confirmation. Cumulative37 generation/count attempts;18 artifacts verify.

Guardian's next-cut review chooses explicit category-addressed references, with
identity union/dedup across witnesses/free choices. Model still selects every
journey; code never fills a category or imposes a visible card quota. Narrow
cash-fare projection drops unrelated absent-tax `fee_unit`, preserving actual
fare unit/raw evidence. No new selector-repair topology or fourth call.

### c07 preserved failure and c08 contract alignment

C07's39 category tests and18 historical-artifact replay checks passed before live,
but its three frozen draws all failed selection decoding before composition.
The JSON schema allowed a string explanation for absent categories while code
required null. Actual outputs did exactly that (cost in complete sources, all
styles in incomplete source). This is a schema/decoder mismatch the offline
controls missed, not an API outage or evidence of delivered answer quality.
Times10.0525/6.9392/4.0344s are failure timings, not qualifying response timings.
Each used one generation/count, no retry/drift; all raw wires/errors are saved.
Strict verification passes21 artifacts, cumulative40 generation/count attempts.

Blind IDs q019–q021 are reserved as not-delivered draws with exact artifact hashes;
no answer bundle or source grade is fabricated. New delivered draws start q022.
C08 narrows only its schema to literal null/null for absent styles and explicit
available witness-versus-omission branches. Keep c07's original error classification
and replay unchanged. C08 tests use all three actual c07 wires as negative controls
and source-valid null-adjusted offline controls; these are not model quality
proof. Live c08 results pending.


### c08 delivered scouts and remaining composition issues

C08 aligned schema branches and44 category tests passed before live. Three fresh
scouts delivered cleanly10.7664/10.7614/8.1079s, two generations/counts each, no
retry/error/drift. Selector receipts report cache writes rather than hits; these
are not solely warm-selector observations. Cumulative46 generation/count attempts;
strict verification passes24 artifacts including c07's original failures.

Q022/q023 pass H/U/C/K/P and fail M2 for repeated local/shared caveats; q023 also
prints the internal phrase `SOURCE-BOUND INLINE CASH SENTENCE`. Q024 passes U/M2/K
and fails H/C/P: source reviewer qualifies the interpretation of cross-program raw
points as an advantage; its bound USD686 quote is not visibly identified as cash.
No confirmation followed. No original source grade was changed.

Read-only delivery trace finds q024's document label `Cash benchmark` is dropped
by `_answer`'s cash-sentence branch and the preview renders only its text. A
prospective inline role label can preserve cash context without a prominent card
or numerical wording binding. Also clarified: legacy p/a codec semantics make
`selected_journey_ids` primary p references, not every displayed journey; all
visible blocks still carry exact canonical IDs and category checks inspect all
of them. No external CategoryAnswer consumer currently relies on that field.
Guardian is assessing c09 direction; no further calls at this checkpoint.


### c09 medium composition and c10 lead-caption cue

C09 changes only composition effort to MEDIUM for all three branches, with LOW
selection/correction and the same author guide/facts/schema/checks. Independent
request-difference probes and47 category tests pass; old24 artifacts replay.
The prospective preview adds an inline `Cash comparison` role label without
changing authored words/numbers or making a cash card; old previews stay exact.

Fresh c09 scouts18.0436/19.0452/13.8437s, all two generations/counts and clean,
no retries/errors/drift. Selector cache hits are substantial; MED composition
reports roughly1,550/1,494/1,504 reasoning tokens. Strict verification passes27
artifacts, cumulative52 generation/count attempts. Q025/q027 pass all axes;
q026 passes H/U/C/K/P and fails M2 because a shared missing-schedule warning is
also repeated in both research-lead captions. No confirmation. Different random
selector outputs prevent a general causal quality claim from this small cohort.

Guardian recommends c10 role-local guidance on existing lead caption `v`, reinforced
by a lead-only schema description. The code already renders research status and
source-reported gaps. Captions should provide a supported conditional next-check
reason; shared gaps once, distinct local action-changing conditions retained.
A new `why_check` wire/decoder was considered but not selected: field renaming
would add replay/contract surface without enforcing meaning. Parent adopts the
smaller cue while retaining c09 MED composition, LOW selection/correction and all
other facts/checks/limits. Mandatory post-c10 reflection remains required after
actual results, before c11 or closeout.

### c10 disposition, mandatory reflection and c11 confirmation failure

C10 scouts completed18.4219/24.2212/13.6486s. Q028/q029 failed M2 for
repeated conditions; q030 passed all six source axes. The conditional draw also
failed the unchanged22s individual gate. No confirmation followed. The mandatory
[post-c10 architect review](../reviews/2026-10-29-results-category-led-c10-architect-review.md)
recommended source-derived condition applicability rather than another wording
prohibition. The parent adopted that input-only c11 hypothesis.

C11 adds exact selected-record applicability for existing condition states;
the model still chooses the displayed subset, wording and local/shared placement.
Independent request/source probes found no new ranking, placement engine, output
binding or model call. Source-resolved cards now distinguish explicit absent and
unknown award taxes; known amounts including zero remain unchanged. Implementer
verification:57 category tests passed in212.20s; independent source/card probes
and strict replay of30 prior artifacts passed. Those earlier mypy claims covered
source files, not all new test modules; a later broad test typing check found
errors requiring separate correction.

All three c11 scouts passed all six source axes at13.273/15.370/10.569s, two
generations and exact counts each. The unchanged candidate advanced to the
prospectively frozen six-source confirmation. All six delivered cleanly, without
correction, retry or source/config drift, at16.123/15.001/13.316/17.171/18.298/
12.706s (median15.562s). Five passed all six source axes. Q035 passed H/U/K/P but
failed M2/C: its economy caption offered no countervailing benefit and its
research lead restated verification work without a useful supported reason to
investigate it. Consolidated conditions themselves passed. No original grade was
changed, and these six sources are no longer unseen for subsequent candidates.

C11 therefore does not qualify. The gated controlled repair was not run and
public defaults remain unchanged. Strict verification passes39 saved artifacts,
76 generation and76 exact input-count attempts, with zero integrity issues.
No provider/FX calls or SDK retries occurred. Eleven iterations are used and nine
remain. A fresh architect critique is underway before selecting the c12 change;
the next mandatory five-iteration checkpoint is c15 or earlier final closeout.

### c12 accepted experiment

The parent accepted the fresh [c12 design review](../reviews/2026-10-29-results-category-led-c12-design-review.md):
add a neutral selected-choice facts table for all selected nonbenchmark records,
with exact program/cabin, reported points and scope, and all source connection
waits/kinds. Keep complete records, temporal relations and condition applicability.
Replace the blanket card-recap cue with permission to briefly reuse a fact when
it explains why to consider a choice. Luna decides relevance, wording and the
visible subset. No code advantage, ranking, economic comparison, safety claim,
forced pair, compensating benefit or card quota is added. Keep current effort,
schema, checks and bounded call topology. Implementation and independent review
precede fresh scouts; no c12 quality or latency result is yet claimed.

This is an input-salience experiment inside the accepted model/code boundary,
not a new ownership or evaluation decision; ADR0029 remains the governing ADR.

The bounded verification worker corrected41 test-typing errors with narrow
casts/assertions in seven new category test modules, without runtime edits or
weakened assertions. Declared `jsonschema>=4,<5` and `types-jsonschema>=4,<5`
as dev dependencies; installed only the missing stub package into the existing
environment. Mypy now passes55 source/test files, Ruff passes touched tests,
all57 category tests pass, and `git diff --check` passes. The independent full
offline suite remains in progress; no full-suite success is claimed yet.

C12 implementation is frozen. Independent source review caught and corrected
one new input label: component observation `kind` is `component_kind`, not a
claim about cabin coverage. All connection rows/kinds and source states remain
exact; a single overlapping journey still covers both time and premium.
The broader category run passed60 tests with one stale profile-list assertion;
after updating that assertion, the changed registry plus five new C12 controls
passed6/6. Ruff/mypy/diff checks pass, all39 prior artifacts replay exactly,
and an offline C12 run/replay plus table-tamper control passes. The parent
authorized strict archive verification, final scout freeze and three live
scouts in sequence, with independent source grades before any confirmation.

### c12 scout disposition and c13 effort experiment

All three c12 scouts pass H/U/M2/C/K/P in separate source reviews(q040–q042).
They delivered cleanly at20.9246/24.8768/12.4201s, two generations/counts each,
without correction or snapshot drift. Both the conditional22s individual and
20s cohort median gates fail. No confirmation or repair followed. Strict archive
verification passes42 artifacts,82 generation/count attempts, zero issues.

Composer generation took11.470/17.571/6.678s, with1538/2472/911 reported reasoning
tokens. Exact composer inputs were8629/7102/4162 tokens, with zero cache hits
and cache writes recorded; the selected-choice tables were1860/1851/1334 bytes.
Selected nonbenchmark pool sizes differ from c11(4→4,2→5,5→5), so these timings
do not isolate table cost. An offline identical-pool q035 comparison adds1323
table bytes and1348 full-input bytes, plus223 instruction bytes; no separate
paid measurement was made.

The goal guardian reviewed actual requests/receipts and all three source grades.
Parent adopted c13 with only LOW composition replacing MEDIUM; selection and
conditional correction remain LOW. Keep c12 facts, tables, guide, schema, checks,
pool bound and preview unchanged. The explicit condition/choice inputs distinguish
this test from earlier LOW failures, but do not guarantee semantic quality or
latency. All gates remain. Twelve iterations are used, eight remain; the next
mandatory architect reflection is after c15 or earlier final closeout.

### c13 implementation and fresh scouts

Implementer verified10 targeted phase/registry/integration controls, Ruff/mypy/
diff checks and42 old exact replays. Independent review compared all three
actual archived c12 request branches: selector identical; composer differs only
in MEDIUM→LOW reasoning; correction envelope remains exact LOW. All45 other
archived runtime/preview files are byte-identical. Offline three-pass recovery,
replay and phase/request tamper controls pass. Runner strict verification of42
old artifacts also passes with zero issues before the final scout freeze.

Three fresh c13 scouts deliver cleanly at12.217/11.827/8.898s, median11.827s,
two generations/counts each, no correction or snapshot drift. Timing gates pass.
Independent source reviews and final45-artifact verification are pending; no
confirmation, repair or qualification is yet claimed.

C13 final source review: q043 passes U/C/K/P but fails H/M2. Its prose compares
the business option with an economy option present only in the omitted pool,
and repeats shared award scope. Q044 passes H/U/C/K/P but fails M2 for repeated
traveler/tax/quote/separate-ticket conditions in both journey captions, and
repeated schedule/scope checks in lead captions/opening. Q045 passes all six
axes. No confirmation or repair followed. Strict verification passes45 actual
artifacts and88 generation/count attempts, zero integrity issues. Thirteen
iterations are used and seven remain. The goal guardian is assessing c14
against the actual pool/display and repetition failures; no new direction is
accepted yet and no source gate is relaxed.

### Broad offline baseline verification

The independent worker ran `.venv/bin/python -m pytest -q`:1310 passed,
99 skipped,2 failed in2472.52s(exit1). Both failures are historical
`test_gfly_compat.py` environment guards: the configured
`/private/tmp/gfly-live-py312/bin/python` resolves to Homebrew Python, whose
`sys.prefix` does not equal the required pinned environment. No other failures
were observed. Full output is `/private/tmp/results-category-full-pytest.log`.

The run began before c12 runtime edits, without a source fingerprint or exact
start timestamp. It is baseline evidence with a mixed-worktree caveat, not a
full-suite pass for the latest candidate. Later changes have their own targeted
tests, static checks and exact archive verification above. Ordinary test paths
were inspected for fake-writer injection; no live model/provider call was part
of this suite. The initial broad mypy test errors are resolved by the separately
recorded typing worker, not ignored as source success.

### c14 deep design escalation and accepted bounded experiment

The goal guardian recommended deep-architect escalation: LOW composition fails
both omitted-pool referents and shared-condition allocation, while current MEDIUM
composition passed c12 semantics but failed timing. Status-based effort branches
had no supported semantic basis; a display declaration alone did not address
both failures. No speculative output-binding wire was adopted.

The deep architect recommended c12's LOW/MEDIUM/LOW phase settings with a
three-nonbenchmark-plus-one-cash authoring-pool ceiling. Parent accepted this
bounded experiment after the implementer traced its schema/decoder/union seams.
All three c12 passing answers displayed2/3/3 choices from4/5/5-record pools;
ten of eleven c11–c12 source-passing answers displayed at most three. This is
not causal latency proof: larger pools have also passed timing. Keep the full
selector inventory, exact style-witness union, optional smaller visible subset,
all facts/aids/checks/preview and full explorer. Code must reject overflow rather
than clip references or choose winners. Three disjoint style witnesses must fit;
overlap consumes one slot. This limit is not a card quota or new Ranking policy.

Implementation is authorized while the deep review finishes its durable report;
the final report, independent code review and archive gates precede live calls.
No c14 result is claimed. The next mandatory architect checkpoint remains after
actual c15, or final closeout if a candidate qualifies earlier.

Parent read the completed [deep design review](../reviews/2026-10-29-results-category-led-c14-deep-design-review.md)
and retained that decision. The report explicitly limits causal claims and
requires a schema-valid union-overflow control that stops after one selector
call, three disjoint styles plus cash, lead-only three plus cash, same-pool c12
composer/correction request equality, and old45 exact preservation. The selector
schema bounds free choices; the decoder authoritatively bounds their union with
style witnesses. No new ADR is required for this engineering ceiling within the
accepted Ranking/model/code boundary. The parent authorized fresh c14 scouts
only after implementation review, strict archives and final freeze pass.

C14 runtime/tests are frozen. Twelve targeted pool/registry controls pass,
including three disjoint styles plus cash, overlap/deduplication, grouped leads,
schema-valid union overflow saved as a one-call failure with exact replay,
optional display/category omission, identical c12 composer/correction requests
for valid small pools, and tamper rejection. Ruff/mypy/diff checks pass and all45
old artifacts replay exactly. Independent review caught and restored old error
wording(`six`, not `6`) in both decoder paths; historical failure behavior is
part of isolation even where the saved45 do not exercise that error.

C14 formal source clearance and strict old45 verification passed before freeze.
All three fresh scouts are saved. The admitted draw stopped after one selector
generation/count at6.363s: choices J13/J7/J11/C1 plus style witness J217 produce
four unique nonbenchmark references plus cash. The authoritative union check
correctly records `schema_error: selection choices exceed the 4-reference bundle`;
no clipping, retry, composition or answer followed. Q046 is reserved as
undelivered, with no fabricated answer bundle or source grade.

The other draws deliver at12.101/11.342s with two generations/counts each and
zero snapshot drift. Q047/q048 source reviews and strict48 verification are
pending. The undelivered first draw already prevents confirmation; its failure
timing is not qualifying response latency. The guardian is assessing c15's
selection representation before the mandatory post-c15 results review. No
new selection wire or changed policy is accepted yet.

C14 final: q047 passes all six axes. Q048 passes U/M2/K/P and receives qualified
H/C failures: its correct raw Alaska/United point ordering is used as a research
advantage. The reviewer explicitly records a possible literal-only reading and
does not reject the valid conditional Alaska/date reason. Original grade and
uncertainty remain; no broader ban on conditional program reasons is inferred.
Strict verification passes48 saved artifacts,93 generation/count attempts,
zero issues. Two delivered timings are12.101/11.342s; the6.363s first draw is an
undelivered failure, not passing response evidence. Fourteen iterations are used
and six remain. No confirmation or repair follows.

### c15 accepted bounded indexed selection

Guardian and parent accepted one selector-interface change: at most three exact
journey/lead choices, one separate benchmark alias or null, and time/cost/premium
audits that reference a zero-based index within those returned choices. Audits
can no longer add identities. Decoder checks actual integer/range, journey role,
exact source membership, full chosen-array coverage and omission consistency;
cash identity, duplicates and invalid roles also fail explicitly. Normalize to
the existing canonical selection, retaining c14 MEDIUM composition, LOW selection/
correction, facts/aids/author guide/checks and optional displayed subset.

This fixes the concrete cross-field pool-growth representation, not ordinary
prose truth or q048's interpretive issue. No numerical guide, inline binding,
new ranking, card quota or extra call is bundled. Historical wires/failures stay
immutable. The new profile-specific selector wire stays inside the accepted
model-selection/code-validation boundary; no new ADR ownership decision is
needed. Runner tooling must support the new audit shape with offline controls
before freeze. Parent authorized scouts only after code/control/archive gates;
the mandatory post-c15 architect review follows all three scout outcomes/source
grades and precedes any confirmation or c16, even if scouts pass.

C15 implementation is frozen. Initial13 targeted controls pass; two subsequently
added controls also pass, covering incidental style membership, omission-state
branches, positioning-cash misuse, overfull choices and a schema-valid invalid
index saved as a one-call failure with exact replay. Ruff/mypy pass; all48 old
artifacts replay exactly, including q046's original union-overflow failure.
Independent probes on all three real sources confirm identical normalized
selection/focus/composer/correction requests versus c14 MEDIUM/LOW.

Before freeze, runner audit tooling was updated for indexed witnesses and separate
benchmark, preserving raw wires and legacy audit behavior. Twenty-four controls
pass. Independent probes verified reordered journey/lead binding, canonical
identities and invalid-index rejection, with no changes to old bundles, preview
or rubric. Final code clearance and strict48 verification still gate live scouts.

C15 formal implementation/tooling clearance and strict old48 verification passed
before freeze. All three fresh scouts deliver cleanly at17.565/17.134/12.107s,
median17.134s, two generations/counts each, no correction or snapshot drift.
Timing gates pass. Q049–q051 source reviews and strict51 verification are in
progress. The mandatory post-c15 architect review has started and must read
all three final source grades before disposition; no confirmation or c16 can
precede that checkpoint. No M2 qualification is inferred from the timings.

C15 source grades are final: q049/q050 pass all six axes, with q050's loose
opening/reporting wording noted as nonblocking. Q051 passes U/M2/K/P and has
qualified H/C failures for “check this lead for its lower points quote” across
Alaska/United. Counts are exact and conditional program use is valid; the
reviewer records the interpretive distinction between raw numeric order and an
unsupported recommendation advantage. No original grade is changed.

The indexed selector, exact cards, category coverage and composition pass for
these draws, but c15 cannot qualify or advance to confirmation. Strict full
verification passes51 actual artifacts,99 generation/count attempts, zero issues.
The mandatory architect report is being finalized against all three grades;
c16 remains blocked on that checkpoint. Fifteen iterations are used, five remain.

### Mandatory post-c15 disposition and c16 accepted clarification

Parent read the completed [mandatory architect report](../reviews/2026-10-29-results-category-led-c15-architect-review.md)
against all three final source grades, requests, timings and verified totals.
The checkpoint is complete. It confirms c15 is not qualified; the indexed selector
fits the stage boundary, but numerical prose remains independently reviewable.
No confirmation follows c15 and no historical grade is changed.

Parent accepted its c16 recommendation: replace only the ambiguous “Do not force
… cross-program economic ranking” author clause with an explicit separation of
optional comparisons and program-unit meaning. A smaller raw count in a different
program does not establish an advantage or justify favoring/checking that lead.
Conditional program/date/cabin reasons remain valid on their own; same-program
reported comparisons preserve scope and incomplete status. Keep raw card quotes,
indexed selector/brief, all factual aids/output schema/checks/preview and
LOW/MEDIUM/LOW settings unchanged. No q050 wording cleanup, extra data/editor,
numerical binding or semantic regex is bundled.

This clarifies an existing economic/source boundary; plausible instruction
ambiguity is not claimed as a proven cause. No new ADR policy/ownership decision
is required. C16 implementation and actual-request/replay isolation review are
authorized; strict51 preservation, final freeze and all source/time gates still
precede follow-on evidence. The next scheduled mandatory architect review is
after c20 or before earlier scoped closeout.

C16 source/tests are frozen. Five targeted request/registry/run/replay/tamper
controls pass, with Ruff/mypy/diff clean and51 old exact replays. Independent
probes against all three actual c15 branches confirm selector requests are exact,
author/correction requests differ only by the adopted clause, and focus/selection/
findings/settings are unchanged. Offline replay of a saved wire is mechanical
evidence only; q051's semantic failure is not regraded or treated as fixed by a
unit test. Formal clearance and strict51 gate precede the fresh c16 scouts.

C16 formal source clearance and strict old51 verification passed before freeze.
All three fresh scouts deliver cleanly at18.733/17.876/14.450s, median17.876s,
with two generations/counts each, no correction and zero snapshot drift. Timing
gates pass. Q052–q054 independent source grades and strict54 verification are
pending; no confirmation or semantic improvement is yet claimed.

C16 final source grades: q052 passes H/U/C/K/P and fails M2 for restating the same
shared award-tax quote-scope condition, once for both awards and again for the
Aeroplan tax quote. Distinct business tax-amount/support/positioning conditions
are not counted as repetition. Q053/q054 pass all six axes, with q054's minor
caption/“three leads” wording limits retained. The program-unit clarification
coincides with a passing incomplete draw; no causal or general-reliability claim
is made. No confirmation or repair follows.

Strict verification passes54 actual artifacts,105 generation/count attempts,
zero issues. Sixteen iterations are used, four remain. The goal guardian is
tracing duplicate condition provenance before recommending c17; no next
implementation is yet accepted and no gate is changed.

### c17 accepted same-source condition normalization

The guardian traced q052's two condition rows to one canonical source field:
`focused_records` binds the award quote by `member.award_ref`, while
`currency.observed_money` and `journey_money` copy the same
`SolutionComponent.price_scope` into the tax quote and award-point projections.
Parent accepted a c17-only normalization into `award_points_and_tax_quote_scope`.
Per alias, require journey role, nonempty `member.award_ref == award_component.ref`,
`quote.kind=award_taxes`, and both explicit scope states unknown. The trusted
construction/provenance path must remain intact. Equal unknown strings alone
are insufficient. Missing identity, mismatched references or states keep the
appropriate old rows; mixed pools may merge only some aliases.

Retain raw records, tax-amount unknown/absent/null states, requested-party support,
separate-ticket/positioning conditions and positioning/benchmark cash scopes.
Keep c16's guide/unit clarification, indexed selection, LOW/MEDIUM/LOW phases,
output wire/checks/preview and optional display unchanged. This is normalization
of duplicate projections of a source fact, not a new price/economic conclusion,
prose guarantee or proven cause of q052. No new ADR ownership/trust policy is
required. Source identity, mixed-state, zero/missing, request/replay/tamper and
historical54 controls precede fresh scouts; all qualification gates remain.

C17 source/tests are frozen. Seven targeted controls pass with Ruff/mypy/diff
clean and54 historical exact replays. Independent provenance tracing confirms
the component-to-quote/reference path and same canonical scope source;45 further
negative identity/state probes prevent arbitrary merging. All three actual c16
selector requests remain exact; whole author/correction envelopes differ only
by the condition table, including unchanged instructions/schema/MEDIUM/LOW.
Admitted/conditional tables change8→7 rows, incomplete remains3→3. Raw records
and unrelated condition families remain exact. Formal clearance and strict54
verification precede fresh c17 scouts; no semantic success is yet claimed.

C17 formal clearance and strict old54 verification passed before freeze. All
three fresh scouts deliver cleanly at18.911/16.343/12.034s, median16.343s, two
generations/counts each, zero correction or snapshot drift. Timing gates pass.
Q055–q057 source reviews and strict57 verification are pending; no confirmation
or source/composition success is yet claimed.

C17 final: q055/q057 pass all six axes. Q056 passes H/U/C/K/P and has an
editorial M2 failure: its one-card answer exposes “time-qualified set,” repeats
cabin classification and offers an unanchored earlier-arrival precaution; its
caption is checks rather than natural choice guidance. The review explicitly
does not fail a single card or require an omitted economy pair. Exact source
joins, overlap and useful cabin/time-versus-booking burden support the narrower
C pass. This is distinct from c16's repeated scope condition, which is not
repeated here; no causal guarantee is inferred from that observation.

No confirmation or repair follows. Strict verification passes57 actual artifacts,
111 generation/count attempts, zero issues. Seventeen iterations are used, three
remain. The guardian is investigating the internal-language/decision-reason seam
before recommending c18; gates and original grades remain unchanged.

### c18 accepted traveler-reason paragraph replacement

The guardian traced q056's “time-qualified set” and unprompted earlier-arrival
precaution to the current complete-journey/category guide. Parent accepted a
replacement of that compact paragraph, not an additional generic reminder or
journey schema field. Journey captions should explain naturally when/why to
choose the option; a practical local condition may accompany that reason, while
checks alone do not supply it. Source category rules constrain reasoning rather
than becoming classification explanations or disclaimers for comparisons never
made. Actual temporal comparisons retain exact relation/metric safeguards.

Single overlap cards remain valid; no pair, numerical contrast, invented benefit
or extra card is required. Preserve all other c17 unit/scope/cash instructions,
facts/aids, indexed selection/caps, LOW/MEDIUM/LOW settings, schema/checks/preview
and bounded correction. Instruction leakage is a grounded hypothesis, not a
proven cause or semantic fix. Request-difference, replay/tamper and historical57
controls plus independent review precede fresh scouts. No new ADR ownership,
ranking or evaluation decision is required for this author-role clarification.

Parent integration refined the paragraph's first sentence before freeze: use
nonexclusive supported-fact examples, explicitly including scope-qualified cost
or point quotes alongside cabin/time/duration/connections. This prevents the
rewrite from accidentally narrowing the approved cost perspective. The exact
plan span was updated and implementer/reviewer/runner notified; no candidate
manifest or live draw had been frozen. All existing unit/scope rules remain.

C18 final source/tests are frozen after that refinement. Five targeted controls,
Ruff/mypy/diff checks and57 historical exact replays pass. Independent checks
against all three actual c17 requests confirm selector equality, unchanged
input/schema/settings and only the approved author/correction paragraph delta.
The new saved-wire run/replay/tamper controls establish compatibility, not natural
language improvement. Strict57 preservation and formal final clearance gate scouts.

C18 formal source clearance and strict old57 verification passed before freeze.
All three fresh scouts deliver cleanly at18.641/13.532/12.580s, median13.532s,
with two generations/counts each, no correction or snapshot drift. Timing gates
pass. Q058–q060 independent source reviews and strict60 verification are pending;
no confirmation or qualification is inferred from mechanical/timing success.

C18 final: q058/q060 pass all six axes. Q059 passes U/C/K/P, with qualified H
failure for blanket “points and tax amounts and their scope … unknown” wording
despite known110000/275000 reported point amounts; a final-payable-amount reading
is acknowledged as a charitable alternative. M2 also fails because the shared
quote-scope warning appears in an economy caption and again in the common
checklist. Distinct tax-amount/party/ticket conditions are not penalized. Original
grades/uncertainties remain, and no confirmation or repair follows.

Strict verification passes60 saved artifacts,117 generation/count attempts,
zero issues. Eighteen iterations are used; only c19/c20 remain. The guardian is
tracing observed amounts versus unconfirmed price basis and repeated conditions
before recommending c19. No next runtime change or gate relaxation is accepted.

### c19 accepted reported-amount and condition-allocation clarification

The guardian traced q059's actual packet: reported points are present, tax
amount states and scope states are separate, and the condition table has one
shared award-scope row. No source fact is missing and no duplicate input row
remains. Parent accepted a replacement of only the quote-scope/condition guide
paragraph: a known reported number stays a reported observation when its basis
is unconfirmed; each unknown applies to its actual field/aliases; a qualification
already given locally or commonly counts as that condition's explanation, and
later common prose covers only remaining distinct unknowns. Catch-all “details
unknown” must not sweep in known point values.

Retain restrictions on per-person/full-trip/cheapest claims, role-specific tax
amount/support/positioning/benchmark limits, c16 program-unit meaning, c17 source
normalization and c18 natural-reason paragraph. No raw-data, schema/checker,
selector, effort, output field, extra call or numerical binding change is bundled.
This is a precise authoring-responsibility clarification, not a proven semantic
fix or a new ADR policy. Exact span review, request/replay/static controls and
historical60 preservation precede fresh scouts. Only c19/c20 remain.

Before freeze, independent review caught a dropped guard in the exact proposed
replacement: it covered unknown scope but omitted incomplete quotes with known
scope. Parent restored “incomplete quotes or reported amounts with unknown
scope do not establish…” in the plan, and notified implementation/review/runner.
Only that preservation clause changes; no candidate manifest/live call had been
frozen. Known reported amounts remain known observations without implying a
confirmed full journey price.

C19 source/tests are frozen after that correction. Five targeted request/registry/
run/replay/tamper controls pass, with Ruff/mypy/diff clean and60 historical exact
replays. Independent actual-c18 three-branch probes confirm selectors exact and
whole author/correction envelopes differ only by the final approved paragraph;
inputs/schema/settings and runtime function/class behavior remain unchanged.
Strict60 preservation and formal final clearance precede fresh scouts. These
mechanical tests do not regrade q059 or prove semantic compliance.

C19 formal source clearance and strict historical60 verification passed before
freeze. Three fresh scouts deliver cleanly at17.963/12.488/15.752s, median15.752s,
two generations/counts each, no correction or snapshot drift. Timing gates pass.
Q061–q063 independent source grades and strict63 verification are pending;
no confirmation or qualification is inferred yet.

C19 final: q062/q063 pass all six axes. Q061 passes H/U/C/K/P, with a qualified
editorial M2 failure: the common award quote-basis caveat appears separately in
each journey caption. Each exact quote is locally qualified once and no later
shared paragraph repeats it; the reviewer records this close interpretation of
the shared-limits-once goal without imposing a mandatory shared block. Distinct
business-only conditions are not counted as duplicates. Known reported values
remain distinct from unknown basis. Original grade/uncertainty remain.

No confirmation or repair follows. Strict verification passes63 actual artifacts,
123 generation/count attempts, zero issues. Nineteen iterations are used; c20 is
the final candidate. The guardian is assessing cross-choice condition grouping
and flexible explanation placement before proposing that last experiment. No
gate relaxation, regrading, c21 or unused-budget extension is authorized.

### c20 final accepted condition-group quantifier

Parent accepted the guardian's last bounded experiment: replace only c19's two
condition explanation/placement sentences with an explicit group quantifier.
Intersect a condition row's affected aliases with actually shown choices; one
explanation covers that group, not one per quote/card. Its placement remains
flexible(first caption/comparison/opening/other prose), with no mandatory shared
section. Singleton and genuinely distinct amount/party/ticket/cash conditions
remain distinct. This clarifies a close editorial ambiguity without regrading
q061 or adding a new acceptance criterion.

Keep all other c19/c18/c17/c16 facts/instructions, indexed selection, three-plus-
cash pool, LOW/MEDIUM/LOW settings, output/checks/preview and correction bounds.
No new schema, binding, editor or code-written sentence. Exact passage/request/
replay/static and historical63 gates precede the final scouts. Mandatory post-c20
architecture review follows all three outcomes and source grades before any
confirmation or qualification decision. An unchanged all-gate candidate may
complete its already-declared confirmation/repair protocol; no c21, replacement
draw or new experiment is authorized after the hard iteration cap.

Parent read and approved the exact c20 span unchanged. Final source/tests are
frozen: five targeted request/registry/run/replay/tamper controls, Ruff/mypy/diff
and63 historical exact replays pass. Independent actual-c19 three-branch probes
confirm selector equality and only the approved two-sentence author/correction
delta, with all other text/input/schema/settings unchanged. Formal final code
clearance and strict63 preservation gate the last three scouts; no semantic
success is inferred from these mechanical controls.

C20 formal source clearance and strict historical63 verification passed before
the final freeze. All three final scouts deliver cleanly at18.759/16.873/12.450s,
median16.873s, two generations/counts each, no correction or snapshot drift.
Timing gates pass. Q064–q066 source reviews and strict66 verification are pending.
All20 candidate iterations have now run. Mandatory post-c20 architecture review
must consider all three final source grades before any unchanged-candidate
confirmation or final disposition. No c21 or design correction is authorized.

### Final c20 source disposition and frozen-code verification

Q064 passes H/U/C/K/P and fails M2: the business caption requests checking the
separate-ticket arrangement, then later prose repeats uncertainty about the same
ticket obligations with no distinct added consequence. The shared award scope
itself is consolidated. Q065/q066 pass all six axes; q066's minor adjacent
date-only wording repetition remains nonblocking as reviewed. No grade is changed
because this is the last candidate. No confirmation or controlled repair follows.

Strict full verification passes66 actual artifacts,129 generation and129 exact
input-count reservations, zero integrity issues. The runner reports62 delivered
(59 clean,3 annotated) and4 historical undelivered selectors(q019–q021/q046),
with their original errors preserved. Recorded generation usage sums5,350,074
input/100,976 output tokens, with73,520 reported reasoning;3,423,307 cached input and
1,926,380 cache-write input tokens. These are saved usage sums, not cost estimates.
There were no SDK retries or provider/live FX calls. No c21, spare-budget spend,
replacement draw, current-candidate confirmation or repair is authorized.

The independent final worker ran `.venv/bin/python -m pytest -q
tests/unit/test_results_category*.py`:112 passed in358.46s, exit0. Ruff on Results/
CLI/category tests and mypy on64 source/test files pass; `git diff --check` passes.
Captured hashes of category.py, category_contracts.py, CLI and all category tests
are identical before/after. Tests use saved/fake writers; the sole `--live` CLI
test monkeypatches OpenAI and the runner. Log:
`/private/tmp/results-category-final-pytest.log`. This is current focused evidence,
not a repository-wide pass. The earlier broad baseline remains1310 passed,
99 skipped,2 historical gfly pinned-interpreter failures with its mixed-worktree
caveat; no full-suite rerun or environment repair is claimed.

Parent updated AGENTS, project state, current contract/workspace plan, ADR0029/
index and G06/G08 deferred history to record the c20 stop without M2 qualification.
The accepted architecture/Ranking/trust policy is unchanged; ADR disposition is
an execution-status amendment, not adoption of a future mechanism. The mandatory
post-c20 architect report was subsequently completed and read by the parent:
[mandatory final review](../reviews/2026-10-29-results-category-led-c20-architect-review.md).
All required5/10/15/20 checkpoints are complete. It confirms the unqualified stop
and proposes only a future offline condition-ownership interface prototype,
preserving Luna wording/order and ordinary numerical prose. Declared ownership
would not prove untagged prose or numerical truth; semantic review and new
source/time/confirmation/actual-repair evidence would remain necessary. Parent
records this as a proposal, not an accepted architecture, implementation task,
paid campaign or c21 authorization. No further runtime or live-evaluation work
under this invocation is authorized.
Public default remains provisional/unqualified V27; latest category opt-in is c20.
Frontend and M3 remain separate.

Final documentation verification:18 current/closeout documents,546 local links,
zero missing targets; `git diff --check` passes. The campaign ledger reads
`stopped_at_c20_unqualified`. Runtime/tests remain the frozen code independently
verified above. No commit, default switch, provider call or further live request
was made during closeout.
