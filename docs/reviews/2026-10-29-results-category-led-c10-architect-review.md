# Mandatory post-c10 architect review

Recorded 2026-10-29. **C10 does not qualify. Ten iterations remain.** This is the
required review after the tenth actual iteration, distinct from pre-c10 steering.
The parent owns integration and acceptance. No runtime edits or live calls were
made for this review.

Sources: [campaign goal ledger](../plans/2026-10-29-results-category-led-campaign.md),
[build log](../build-log/2026-10-29-results-category-led.md),
[campaign evidence](../../evidence/results-stage/m2/structured/2026-10-29-category-led/README.md),
[V3–V30 handover](../handoffs/2026-10-29-results-m2-fast-profile-handover.md), and
[prior mandatory review](2026-10-29-results-category-led-c05-architect-review.md).

## Evidence and goal assessment

| Draw | Source review | Checked workflow | Result |
| --- | --- | --- | --- |
| q028 admitted | H/U/C/K/P pass; M2 fail | 18.4219s | Business seat/tax/separate-ticket conditions recur in its caption and the closing paragraph. |
| q029 conditional | H/U/C/K/P pass; M2 fail | 24.2212s | A shared lead-schedule explanation is repeated in both lead captions; individual latency exceeds22s. |
| q030 incomplete | All six axes pass | 13.6486s | Conditional program-access reasons and shared limitations satisfy this saved-source review. |

These are clean two-call artifacts, not qualified results. The runner reports30
strict-verified archives and58 generation plus58 exact-count attempts. No
confirmation cohort or controlled correction diagnostic has run. Original grades
and failures remain unchanged. Median latency is below20s, but the individual
24.2212s draw fails the frozen gate; the excess is not rounded away.

The current design preserves source Ranking membership and overlapping category
coverage, useful choices without a one-per-category quota, exact flight cards,
one visibly identified cash sentence and Q3's conditional research directions.
The observed remaining blocker is natural composition, with a separate latency
failure. Mechanical checks and replay do not establish those properties. The
incomplete passing draw does not prove stable behavior on fresh incomplete
sources; no such source has been added to this campaign.

### What was inspected

The architect read q028/q029 delivered answers, q029/q030 source reviews, the c10
profile guide and lead-only schema description, q029's saved composition request,
selected authoring records and saved count/generation timing/usage receipts.
The c09 conditional receipts provide the comparison below. Code inspection
covered `category.py` request construction, `focused_wire.py` delegation and the
campaign preview's lead/journey card rows. The implementer independently traced
the same caption and missing-tax cases. No fresh source grade was substituted.

Q028's business caption already explains confirming seats and taxes and checking
separate-ticket positioning. The closing paragraph explains that same local
cluster again. This is not a shared-versus-local classification ambiguity: the
unknowns are local to the business choice, but their prose appears twice. Q029
has two supported program-access reasons; each also repeats date-only/schedule
scope already described in the common paragraph. The source cards independently
identify research status and show the exact missing-schedule indicator. The
c10 guide replacement and schema description were present in the actual request.

The current packet repeats relevant evidence across nested quote, fact, caveat
and traveler-support records. For example, a conditional business record has
unknown tax amount in its component quote and award facts, seat uncertainty in
facts/caveats/traveler evidence, and separate-ticket status in booking/caveats.
Those representations are not contradictory. The writer must nevertheless infer
which repeated fields describe one condition and which options share it. This
is a plausible allocation burden, not a demonstrated causal explanation of the
model's repetitions.

### Timing evidence and limits

For the c10 conditional draw, exact counts total0.51145s, selection generation
3.06241s, and composition generation18.07366s. Selection reports73182 cached
input tokens. Composition reports5523 input tokens,3521 output tokens including
3081 reasoning tokens, with first text at16393ms. Roughly2.574s of checked wall
remains outside those measured calls.

C09's corresponding composition took11.11146s and reported1920 output tokens,
including1494 reasoning tokens. These draws differ in selected records and
composition instructions/schema; they are not a controlled causal comparison.
Higher reported reasoning/output and longer composition coincide in c10. No
queue, network or compute cause, and no claim that the c10 cue caused the delay,
is supported. MED composition has now both met and exceeded the workflow gate.

## Readjustment recommended for c11

**Make condition applicability explicit in the input instead of adding another
prohibition to free-form captions.** Add a compact, profile-scoped source-derived
condition table for the selected authoring pool, retaining all existing records.
Each entry identifies a known source condition/state and the exact aliases to
which it applies. No model-written omission reason, inferred traveler preference,
new severity judgment or generated explanation enters the table.

Bound the first implementation to the demonstrated facts: award quote scope,
positioning/benchmark quote scope separately, unavailable award-tax amount,
award-party support, separate-ticket/positioning conditions already represented
by source caveats, and incomplete lead schedules. Reuse explicit source states
and canonical condition meanings. Unknown and absent remain distinct; known
amounts or seats are not converted into unknown conditions. A generic missing
JSON field must not by itself invent a new limitation. Avoid broad synonym
merging or treating party evidence as price scope. Existing aliases and the
six-nonbenchmark-plus-cash pool bound already bound this projection.

Example shape, illustrative rather than a new source vocabulary:

```json
{"code":"itinerary_schedule_incomplete","state":"incomplete","applies_to":["A2…","A3…"]}
```

The source-derived table describes **applicability**, not a precomputed
shared/local paragraph assignment. The model can omit redundant pool candidates,
so it must consider only the intersection with actually displayed references.
A condition affecting one shown option can be explained once beside that option;
one affecting several can be explained once with its scope made clear. A useful
shorter connection or program-access reason remains model-authored. No code
chooses narrative placement, fixes headings, binds clauses/numbers, deletes prose
or creates a compulsory separate limitations section. Compact factual card
indicators remain allowed. Generic availability guidance stays in its existing
canonical footer and does not become a new per-option condition.

Use a concise guide replacement explaining the table and one-place allocation,
rather than accumulating another set of negative examples. Preserve current
selection/witness semantics, temporal facts, optional display subset, cash
sentence, exact dedup checks, output wire and recovery topology. Keep MED
composition and LOW selection/correction fixed for this input experiment. Record
the added bytes and tokens; adding a table is not itself a latency optimization.

This is a falsifiable engineering hypothesis, not a claim that a table is
structurally necessary or sufficient. Q030 already passes without it. Retaining
raw records avoids suppressing evidence needed for truthful explanations, but
also means duplicates remain available to the model. Independent source/M2
review stays the oracle; no fuzzy semantic checker is proposed.

### Alternatives considered

- **Lead-only `why_check` wire:** the stronger field cue may help, but does not
  address q028's complete-journey repetition. It can also invite schedule-check
  language, which is literally a next check. C10's actual description failed;
  renaming the same unconstrained text adds schema/decode/correction/replay work
  without exposing the missing cross-option scope. Do not choose it for c11.
- **LOW or NONE author now:** may reduce time, but mixes an effort experiment
  with the new input representation and revisits the repeated LOW composition
  failures. Past NONE-selector failure does not establish NONE-author failure;
  nevertheless, no current positive author evidence supports choosing it first.
  If the new input passes source/composition gates but fails timing, a separately
  frozen LOW-composition candidate is a reasonable next test. No automatic rerun
  or replacement of the failed draw follows.
- **Additional editor, prose suppression or compulsory layout:** these change
  the authorized natural-authoring or latency boundary and are not recommended.

### Card fact ownership

Q028's card shows party-support uncertainty and separate-ticket connections,
but `_money` returns no row when the award-tax amount is unknown. Thus the guide's
broad statement that cards show fees is incomplete for this case. A narrow,
prospective display correction can show a short neutral unavailable-tax indicator
when the exact attached award-tax quote explicitly carries that state. Known
quotes retain their current amounts/units; no zero is invented, no unrelated
benchmark fee metadata appears, and raw source evidence remains intact.

This card correction is independently justified by the source/display trace,
not evidence that repetition will disappear. Do not broaden to a matrix of every
missing field or remove narrative limitations wholesale. Version historical
rendering behavior, and check both Markdown and HTML. Canonical availability
advice already appears once in these answers and needs no new change.

## Verification required before and after c11

Offline controls must establish exact applicability for the q028 singleton
business unknowns, q029 shared lead schedule and business conditions, mixed known/
unknown taxes and party evidence, separate award/positioning/benchmark quote
scope, absent-versus-unknown distinctions, and a composer choosing a smaller
subset. The projection must be deterministic, selected-source-bound and free of
omission-rationale prose. Preserve c01–c10 replay/request behavior. Test the
explicit unknown-tax card row and known-tax behavior separately if implemented.

Then use the same three fresh scouts and unchanged H/U/M2/C/K/P and timing gates.
No broad confirmation follows a failure. Qualification still needs the declared
fresh six-run confirmation and actual controlled-correction diagnostic, along
with offline controls and final architecture review. No result is promoted solely
because fewer iterations remain.

## Scope, uncertainty and escalation

Ten iterations are used and ten remain under the owner-authorized ceiling. The
next mandatory fifth-iteration checkpoint is post-c15, or a final review before
earlier scoped closeout. The600/600 hard attempt cap,22s individual/20s median
gates, no SDK retries and no provider/FX calls remain unchanged. Ranking policy,
Q3 research usefulness, Luna natural prose, source-resolved cards, independent
explorer, frontend/M3 separation and the historical stopped campaign all remain
protected.

The architect's c10 description-only hypothesis failed; that is recorded without
retroactive regrading. The recommended c11 change addresses a broader evidence
pattern and has a bounded source-to-input seam. Semantic compliance and latency
remain materially unproven as empirical outcomes. There is no unresolved
cross-system ownership or trust decision requiring deep-architect escalation at
this checkpoint. If this explicit applicability representation again fails the
same allocation behavior, obtain a fresh architecture critique before another
near-identical prompt/schema variation; do not spend the remaining iterations
renaming unconstrained fields. The parent may choose that escalation sooner.
