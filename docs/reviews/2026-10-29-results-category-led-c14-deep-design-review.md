# C14 deep design review: reduce the selected pool while retaining MEDIUM composition

Recorded 2026-10-29 after the architect recommended escalation following C13.
**The parent accepted one bounded C14 experiment: C12 with a three-reference
nonbenchmark authoring-pool ceiling.** Adoption followed the preliminary
recommendation and implementation-seam inspection; the final report must be read
before the live freeze. Thirteen iterations are used and seven remain. No
candidate qualifies. This review makes no runtime change or live call and does
not replace the required post-C15 review.

Sources: [goal ledger](../plans/2026-10-29-results-category-led-campaign.md),
[C10 review](2026-10-29-results-category-led-c10-architect-review.md),
[C12 review](2026-10-29-results-category-led-c12-design-review.md),
[V3–V30 handover](../handoffs/2026-10-29-results-m2-fast-profile-handover.md),
[review index](../../evidence/results-stage/m2/structured/2026-10-29-category-led/review-index.json),
and [campaign record](../../evidence/results-stage/m2/structured/2026-10-29-category-led/README.md).

## Decision and causal limits

Use **LOW selection, MEDIUM composition and LOW conditional correction**, exactly
as C12. Change the model-selected pool bound from six to **at most three unique
journey/lead references**, plus the existing one cash benchmark. Preserve the full
selector inventory, explicit style audits, all selected records, choice facts,
temporal relations, condition applicability, current composer instructions and
output schema, source-resolved cards, and optional smaller displayed subset.
The complete explorer remains independent. Code does not select or truncate the
pool. Three is a ceiling, not a requested card count or a category quota.

The hypothesis is that a smaller pool reduces the composer's work of comparing
candidate identities, choosing useful visible references and assigning condition
scope, while retaining the MEDIUM setting that produced C12's three source passes.
This is a workload hypothesis, **not a demonstrated latency cause or semantic
fix**. The baseline for interpreting this experiment is C12, not an assertion that
C13 differs from C14 in only one setting. C13 remains the failed LOW-effort control.

The current evidence supports trying this bounded intervention before another
representation or output-contract change. It does not justify choosing MEDIUM
only for particular source statuses, accepting a timing miss, or claiming that
the remaining quality problem is solved.

## What the actual evidence establishes

Saved requests, outputs and generation receipts give these results. Pool/card
counts exclude the full-cash benchmark; reasoning tokens are reported usage.

| Draw | Pool → visible cards | Composition seconds / reasoning tokens | Full checked seconds | Source result |
| --- | --- | --- | --- | --- |
| C12 q040 admitted | 4 → 2 | 11.470 / 1,538 | 20.9246 | All six axes pass; cohort median fails. |
| C12 q041 conditional | 5 → 3 | 17.571 / 2,472 | 24.8768 | All six axes pass; individual latency fails. |
| C12 q042 incomplete | 5 → 3 | 6.678 / 911 | 12.4201 | All six axes pass. |
| C13 q043 admitted | 5 → 2 | 4.603 / 274 | 12.2173 | H/M2 fail. |
| C13 q044 conditional | 4 → 4 | 5.156 / 258 | 11.8273 | M2 fails. |
| C13 q045 incomplete | 5 → 4 | 4.000 / 249 | 8.8979 | All six axes pass. |

[Q043](../../evidence/results-stage/m2/structured/2026-10-29-category-led/review-bundles/q043/review.md)
shows Aeroplan economy J1 and Turkish business J217. Its business prose compares
against a supposedly shown Turkish economy J124, which is only in the candidate
pool. J124 and J217 really have equal arrivals; displayed J1 arrives105 minutes
later. The economy caption also refers to other shown economy awards when none
is displayed. Correct source temporal rows did not prevent a false visible
referent. Award price-scope uncertainty also appears in both captions.

[Q044](../../evidence/results-stage/m2/structured/2026-10-29-category-led/review-bundles/q044/review.md)
shows all four pool choices. Its journey captions repeat the same party-support,
tax/scope and separate-booking checks. Both lead captions repeat schedule/scope
checks after the opening already identifies date-only leads. A declaration of
displayed references alone would leave this failure untouched. The factual
temporal claims, useful reasons, category membership and cards pass independently.

C12's successful answers already fit within three visible nonbenchmark choices.
Across C11–C12, ten of eleven source-passing answers display at most three; q033
displays four. This demonstrates compatibility with several observed useful
answers, not that three references always suffice or that a constrained selector
will choose those same identities. Q033's fourth lead must not be retroactively
called redundant merely to support this proposal.

There is material counterevidence to a simple count-to-latency explanation. C11
q034 selects six references and passes at16.1230s, whereas C12 q040 selects four
and takes20.9246s. C12 q041 has two journeys and three leads, only three temporal
rows, and takes longer than q040 with eighteen rows. Its composition input is
7,102 tokens versus q040's8,629. Shrinking pair tables or input bytes alone cannot
explain the observed difference. The selector is also stochastic: these are fresh
end-to-end draws, not matched compositions on identical selected pools. The
original-source selectors report nearly fully cached inputs, while these
composers report zero cached input tokens. No cold-cache or population guarantee
follows.

## Why three, and why this is still a risky experiment

Three references can structurally hold one exact witness for each of the three
Ranking perspectives even when their memberships are disjoint. Overlap can use
fewer references and leaves room for other useful choices. This is a feasibility
fact about the bound; it does not prescribe one witness per category or assert
that every member within a category is interchangeable. No selector may justify
losing a material category merely by citing the ceiling.

V28–V30's two-reference experiments failed useful coverage/depth, and q119 omitted
premium. Their failures rule out treating a small pool as sufficient. C14 retains
the later category-addressed selection, source-membership checks and prospective
category/usefulness oracle, and uses a bound that can contain three disjoint style
witnesses. It also retains C12's choice facts and its MEDIUM composer. These are
concrete differences from V30, not proof against repeating its failure class.

The downside is real: a useful fourth direction can be lost before composition,
and LOW selection may spend longer resolving the tighter bound or choose a weak
representative. A source-faithful but shallow answer still fails. Incomplete
sources retain conditional program/date/cabin reasons, without a same-program
pair, minimum numeric contrast, forced three leads, or invented preferences.
An answer that needs a fourth direction cannot be declared sparse because C14
withheld it. Review the full source as well as the selected packet.

The bound also leaves pool-to-visible reduction possible, so it does not
mechanically prevent Q043's referent error or Q044's repetition. The proposed
advantage is less composition work at MEDIUM, with those properties still tested
by independent review. No new semantic-correctness guarantee is claimed.

## Implementation seam and controls

Implement a profile-specific pair of limits in
[`category.py`](../../src/award_agent/results/category.py): C14 nonbenchmark3 /
total4; C01–C13 retain6 /7. Derive the selection schema, decoder limits and error
messages from the same profile settings. Change C14's selector ceiling wording
accordingly; retain the existing union and audit semantics. Do not change global
constants in a way that reinterprets historical artifacts.

`_selection_schema` must use the total limit4. `_decode_selection` must apply that
limit after the existing union/deduplication of nonnull style witnesses and free
choices, then enforce the nonbenchmark limit3. Reusing a witness in multiple
styles or also in choices consumes one reference. A witness absent from choices
still consumes a reference. Keep cash-role cardinality/identity checks. Retain
the existing `_focus` adapter that avoids the legacy V30 two-reference composer
ceiling. The full selector packet and source inventory are unchanged.

JSON Schema's `choices.maxItems` does not enforce the cardinality of a union with
separate `style_audit` fields. Do not describe it as doing so. The decoder remains
the authoritative cross-field check. A schema-valid response with too many unique
union members must produce an explicit saved selection failure; it must not be
clipped, have a witness discarded, receive an extra selection retry, or proceed
to composition. This distinction needs a negative control, not an expanded schema
that enumerates all possible witness combinations.

Before live calls, add meaningful controls alongside the current category tests:

1. Three disjoint source-style witnesses plus one benchmark fit; overlap and a
   witness repeated in choices count once; one overlapping journey plus cash is
   valid without filling the ceiling.
2. A fourth unique nonbenchmark reference fails even when raw `choices` alone
   satisfies the schema. Include the witness-only selection case and preserve
   role/reference validation. A failed selection stops after its one actual call.
3. A lead-only pool of three with cash fits and has no fabricated styles;
   optional smaller display remains valid. Omitting the only visible member of
   a selected category still triggers the existing finding. Possible and
   undetermined cost states retain their existing meaning.
4. On an identical, already-valid pool of up to three references, C14's composer
   and correction requests are exactly C12's, including MEDIUM/LOW settings,
   raw records, all three factual aids, output schema and checks. Selector-request
   differences are limited to the declared bound/schema. No metadata pruning or
   guide rewrite is bundled into this experiment.
5. C01–C13 requests and saved artifact replay remain unchanged, including older
   pools larger than three and C07's preserved failures. Current C12/C13 frozen
   requests provide useful regression controls. C14 overflow artifacts must replay
   as failures, and normal correction must stay inside the three-generation cap.

No change to [`category_contracts.py`](../../src/award_agent/results/category_contracts.py)
or [`focused_records.py`](../../src/award_agent/results/focused_records.py) is
needed. Record the accepted experiment in the existing campaign/build log; it is
an engineering bound under the accepted design, not a new
Ranking policy or ADR decision.

## Alternatives rejected for C14 and acceptance

- **LOW composition with another visibility/condition declaration:** leaves
  arbitrary prose unverified and adds a new wire without addressing both observed
  failure classes. Q044 already displays the entire pool.
- **MEDIUM only for complete or conditional cases:** source status is not a
  validated predictor of required reasoning or latency. It would fit these draws
  without resolving the underlying selection/composition problem.
- **Lossless factoring or metadata pruning now:** possible later engineering
  work, but the slow conditional request is already smaller than the admitted
  request. Shared component facts require resolving context-dependent meanings
  such as `same_as_journey` before reuse. Reintroducing joins adds identity risk;
  a byte reduction alone is weak evidence for this latency problem.
- **Extra editor, forced layout, code-written conditions/comparisons, shorter
  output-token cutoff, or relaxed gate:** either changes the accepted ownership
  boundary, repeats failed latency approaches, or risks incomplete answers without
  evidence of useful improvement. None belongs in this experiment.

Freeze C14, then run the declared three fresh scouts with unchanged H/U/M2/C/K/P
and22s individual/20s median gates. Record unique pool size, role mix, visible
count, exact input tokens, per-phase time, reported reasoning tokens and caches
alongside normal receipts; these diagnostics do not replace acceptance. Do not
repeat a failed draw or attribute any improvement solely to the bound.

Only an all-gate scout pass advances to the six frozen confirmations. Only their
all-gate pass advances to the already fixed admitted-source controlled-correction
diagnostic. A smaller natural answer does not establish correction latency; the
actual correction must be measured. Keep the600/600 attempt ceiling, zero SDK
retries, no provider/FX calls, unchanged historical grades and the hard C20 stop.
The next mandatory architect checkpoint remains after actual C15, or before an
earlier scoped closeout. If C14 fails, preserve the result and identify whether
selection quality, source fidelity, composition or measured latency failed;
this recommendation does not authorize an automatic cap2 or new prompt ladder.

## Review verification, uncertainty and disposition

This review read repository/project instructions, the relevant workbook ownership
section, ADR0029/index and deferred-work context; C10/C12 reviews and historical
cycle lessons; current selection/authoring/check/replay code and contracts; the
actual C12/C13 requests, selector/composer outputs and timing receipts; q043/q044
answers and source reviews; C12 positive answers; and q031–q045 metadata. The
archived `category.py` bytes in both C12 complete scouts and both C13 complete
scouts were hashed and matched their saved snapshot manifests. Read-only JSON
inspection independently confirmed the eleven C11–C12 source passes and ten
answers with at most three displayed choices. These are inspections of saved
evidence, not new evaluations or a complete archive-integrity rerun.

Only this requested review document is written. Document link/whitespace checks
are recorded in the handoff. No runtime tests, fresh replay, model/provider/FX
calls, frontend implementation, default adoption or M3 qualification are claimed.
The older workbook's generic weighted-ranking ideas remain refined by current
Ranking decisions; this review does not reopen them or any deferred work.

The unresolved uncertainty is empirical: three references may still be too many
for reliable natural composition, too few for a useful choice, or unrelated to
the long MEDIUM tail. There is no additional ownership or user decision needed
to test this one authorized experiment. The parent has accepted the experiment
and owns integration and acceptance; the design guardian owns continuing goal
stewardship. No further escalation is recommended before seeing this bounded
result.
