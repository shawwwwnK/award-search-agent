# Results M2 disclosure-policy reconciliation

Date: 2026-10-08. Status: corrected policy implemented and scoped engineering verification passed.

## Owner decision and scope

The owner accepted the proposal to show a rejected candidate's identifier, mark it excluded and
explain why, while requiring full timing, cabin, cost and booking disclosures only for recommended
options. A fresh policy challenge found that the initial documentation narrowed the concise-note
scope to rejected candidates alone. Parent accepted the correction: unselected journey notes retain
stable visible identity, exact source status and source requirements/reason. Rejected notes must be
visibly excluded with source-grounded rejection reason; admitted or conditional notes retain those
exact statuses. This does not change Ranking eligibility or promote rejected candidates. Benchmark
and shared disclosures retain their existing contracts.

The decision reconciles the two issues recorded under G08 in
[`DEFERRED.md`](../../DEFERRED.md): shared-once disclosures were not counted by the checker outside
same-journey parts, and the checker required full recommendation disclosures for all journey
mentions. The owner decision applies full journey disclosures only to selected recommendations.
Preserving requirements and conditions in concise notes is conservative engineering behavior, not
an additional owner requirement.

## Versioned implementation representation

The architecture review specified a v3 checker/artifact contract. A shared part binds an existing
fact key to at least two distinct selected eligible journey IDs only when every target has the same
exact source-slot value. The shared part must contain the visible bound fact and unambiguous visible
stable identifiers for all targets; metadata alone does not establish applicability. Binding keys
are unique within each part; valid repetition across parts or occurrences remains allowed. Invalid,
ambiguous, unequal or incompletely visible bindings fail and earn no shared credit. The model
retains control of part placement and surrounding prose.

For any unselected journey note, preserve stable visible identity, exact source status and source
requirements/reason. A rejected note additionally needs visible exclusion and its source-grounded
rejection reason; admitted/conditional notes preserve their source status. Full timing/cabin/cost/
booking disclosures apply to selected recommendation IDs. Preserve v1/v2 preparation, check and
replay semantics while introducing v3. The checker does not validate arbitrary prose or qualify
semantic truth.

## Verification before the fresh challenge

The earlier narrower implementation passed the following checks; they do **not** verify the
corrected broader unselected-note policy or the newly identified contiguous-part identity case:

- Results suite: 105 passed.
- Scoped Ruff and mypy passed; mypy covered nine source files.
- V3 disclosure suite: 14 passed after a friendly-identifier boundary fix.
- Ten retained Luna v1/v2 artifact/Markdown pairs replayed byte-identically; the offline historical
  generator reproduced twelve legacy fixture files byte-identically.
- `git diff --check` passed.

The fresh reviewer independently probed a same-journey contiguous continuation part without a
repeated part-level identifier. The initial probe produced `shared_binding_identity`,
`unavailable_fact` and missing booking-obligation findings. Although an initial fix and suite passed,
a stronger follow-up found two branches still failing when the raw `journey_id` slot is absent: a
selected journey with a visible friendly identifier can receive `missing_disclosure:journey_id`,
and unselected friendly notes can receive `unselected_identity` or `rejected_identity`. The
implementer pinned a factored stable-visible-label rule across the affected branches while
preserving protections against ambiguous or aliased IDs. The accepted regression control is a friendly-label selected journey split between a labeled
first part and immediate unlabeled same-reference continuation, retaining identical rendered bytes;
the same continuation is allowed for concise unselected notes. After an intervening journey, a
visible identity is required again; changed/reused/substring labels must fail.

After the selection-scope correction but before the stronger identity probe, the implementer
reported 18 focused v3 tests and a fresh 109-test Results suite passing. Those checks preceded the
stronger probe and did not close G08.

## Final verification

After the stable-label fix, the parent reran the eight-module Results suite:

```sh
.venv/bin/python -m pytest -q tests/unit/test_results_adapter.py tests/unit/test_results_cli.py tests/unit/test_results_evidence.py tests/unit/test_results_m2.py tests/unit/test_results_markdown.py tests/unit/test_results_token_measurement.py tests/unit/test_results_notice_v2.py tests/unit/test_results_v3_disclosures.py
```

Result: 112 passed. `.venv/bin/ruff check src/award_agent/results src/award_agent/cli/results.py evidence/results-stage/m2/generate.py tests/unit/test_results_v3_disclosures.py tests/unit/test_results_notice_v2.py` passed;
`.venv/bin/mypy src/award_agent/results src/award_agent/cli/results.py` passed for six source files;
`git diff --check` passed. Ten saved Luna v1/v2 artifact/Markdown pairs replayed byte-identically,
and the offline generator reproduced twelve historical fixture files byte-identically.

The independent reviewer confirmed selected friendly-label continuations without raw ID slots keep
identical rendered bytes; concise rejected/admitted/conditional unselected notes and continuations
pass; missing status and requirements produce specific findings; selected journeys still require
full facts; selected rejected IDs fail; resuming after another journey requires a visible identity;
and missing, changed, reused or substring-aliased labels fail.

G08's shared-disclosure, selection-based journey-note and contiguous-identity engineering
reconciliation is complete for these tested contracts. This does not establish full
authored-document coverage, arbitrary prose truth, owner qualification, M2 owner closeout or M3
quality.

## Fresh policy challenge

The reviewer compared the accepted policy with the original authored template, where selection
activates full journey disclosure obligations ([template](../handoffs/2026-10-03-results-stage-authored-template.md#factual-slots-and-visible-obligations),
[ADR 0026 original scope](../adr/0026-model-authored-results-with-bound-facts.md#context)).
The owner dialogue reported by the parent included the proposal “Require the full timing, cabin,
cost, and booking disclosures only for recommended options”; the owner answered “Ok.” The review
found the prior documentation had narrowed this to rejected notes. Parent accepted the correction.
No additional rationale is attributed to the owner: this record corrects the written scope to match
the accepted wording.

This fresh policy challenge also surfaced the contiguous-part identity issue described above. It is
recorded as a separate implementation finding, not a change to the owner's decision. Revisit this
disposition if the corrected implementation or later owner review changes the accepted scope.

The reviewer also probed a prose negation, “Options A/B do NOT have this condition,” while the
valid source-bound booking-obligation slot was present; it produced zero failed findings. This is
an existing semantic
expressiveness gap. The current change does not add negation inference or broaden semantic checking;
record this as a limitation, not as evidence the negative claim is true or as M3 evaluation.

## Decision-record disposition

The accepted policy and implementation status are recorded in [ADR 0026](../adr/0026-model-authored-results-with-bound-facts.md#2026-10-08-amendment--rejected-candidate-note-disclosures)
and the active [Results M2 contract](../handoffs/2026-10-07-results-m2-validation-and-delivery-contract.md).
Results M2 owner closeout and M3 qualification remain unclaimed.
