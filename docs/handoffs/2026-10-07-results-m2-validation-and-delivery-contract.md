# Results M2: validation, recovery and delivery contract

**Current status, 2026-10-08:** Results M2 is [owner-closed](2026-10-08-results-m2-closeout.md) for its declared implemented boundary; M3 remains planned. This supersedes earlier open/unimplemented/pending-closeout status in this document, while preserving historical evidence and policy limits.

Date: 2026-10-07. Status: owner decisions Q1–Q20 recorded; final shared-understanding
confirmation pending. Runtime remains unimplemented. This interview does not authorize live calls.
Decision record: [ADR 0026](../adr/0026-model-authored-results-with-bound-facts.md).
Source: [design interview](../build-log/2026-10-06-results-m2-design-grilling.md).

## Authority and supersession

This consolidates the October 6–7 accepted directions for Results M2. It supersedes the older
Results contracts' terminal validation gates, hard five-choice cap, two-per-award-group cap,
no-repair/single-invocation proposal, and prohibition on code-added failure disclosures.
Earlier input trust, factual binding, cash benchmark, safe literal substitution, preservation
and exact replay requirements remain. M3 measures answer quality; it is not a runtime gate.

Ranking owns the factual SolutionView and private ProjectionReceipt. Results directly consumes
that view without revalidating upstream eligibility or reconstructing an equivalent brief.
The LLM owns headings, ordering, grouping, prose, tables, emphasis and recommendation layout,
including fallback layout. Code fills facts, performs selected checks and attaches notices.

## Authoring and factual obligations

Use a selection manifest and ordered scoped Markdown parts. Parts can repeat/interleave; code
concatenates authored separators, substitutes scoped slots once and preserves source maps.
When a journey resumes after another journey, visible identification must associate its facts
with that journey. Invisible scope metadata alone is insufficient. Exact span serialization
and Markdown implementation are engineering work, not additional owner policy decisions.

Bind material claim-bearing spans to typed claim kinds and exact journey/comparison scopes.
The wording remains model-authored. Deterministic checks test the declared proposition and scope;
they do not establish arbitrary paraphrase truth or detect all undeclared assertions.

Keep route, local schedule/timezone, cabin evidence, duration/waits, scoped prices/program,
status, unresolved requirements, separate-booking obligations and meaningful coverage visible.
Identical shared disclosures may appear once when applicability is clear. Preserve component
observation dates; precise times are shown when material. Detailed provenance stays in the artifact.
This permits a shared disclosure without requiring each journey part to repeat it; it does not
prohibit legitimate repetition elsewhere or impose a global occurrence limit.
When a known required disclosure remains missing after correction, an attached notice supplies
its source-backed content, rather than merely announcing the omission.

Full journey fact requirements apply to selected recommendations. Any unselected journey note must
preserve a stable visible identity, exact source status and its source requirements/reason. A
rejected note must remain visibly excluded with its source-grounded rejection reason; an admitted or
conditional note must preserve that status and must not be presented as rejected. Additional
preservation of conditions in concise notes is conservative engineering, not a separate owner
requirement. Results cannot turn a rejected candidate into a recommendation. The separate cash
benchmark and shared disclosures keep their existing contracts.

The versioned v3 engineering representation of a shared-once disclosure is
`ResultsPart.shared_disclosures: tuple[SharedDisclosureBinding]`; each binding contains `key` and
`journey_ids`. A binding belongs to a shared part and must name at least two distinct selected,
eligible journeys. The bound value must be the same existing source-slot value for every target.
Render the bound fact once for that binding, and keep the key and every target's unambiguous visible
stable identifier in the same part. A key can have only one binding within a part; a valid binding
may recur in another part, and the same fact may appear in other independently scoped occurrences.
Each authored slot occurrence is substituted once; the contract adds no global deduplication rule.
Metadata alone does not prove visible applicability. Do not infer applicability from prose. Invalid
or ambiguous targets, repeated keys within one part, differing source values, or missing visible
bindings/identifiers receive a failed finding and earn no shared disclosure credit. The model still
chooses part placement and surrounding prose.

Normal selection should favor useful distinct complete journeys, usually three. Five is a soft
presentation target, not a schema maximum or terminal delivery gate. Six or another deviation may
be delivered after correction with a notice; do not silently trim alternatives to enforce count.
Multiple materially distinct alternatives from one award group are allowed, with model justification
and avoidance of redundancy. Existing same-group alternate relationships remain meaningful.

Complete admitted/conditional alternatives are the recommendation pool. Full journey disclosure
requirements apply to the selected recommendation IDs. An unselected journey note needs stable
visible identity, its exact source status and source requirements/reason. For a rejected candidate,
the note also needs visible exclusion and its source-grounded rejection reason. For an admitted or
conditional candidate, preserve that status; do not mislabel it as rejected. Results cannot change
upstream status or assign admitted style labels to a rejected candidate.
Preserve recoverable authored content rather than
turn this selection failure into a system error. An unresolvable candidate or factual reference
displays “Details unavailable” with an associated notice, never another candidate's facts. The cash
anchor remains separate and cannot displace award recommendations.
Existing incomplete-only/empty/partial-search distinctions remain; do not invent complete journeys.

## Selected deterministic claim checks

| Initial family | Evidence boundary |
| --- | --- |
| Cabin | Distinguish journey-level cabin from reported leg cabins; all-leg assertions require corresponding evidence. |
| Connection protection | Preserve separate-ticket obligations; timing-rule success or a single award alone does not establish protection. |
| Price scope | Compare per-traveler/party assertions with the reported quote scope; unknown scope remains unknown. |
| Fastest/cheapest comparisons | Use supplied exact references, pool/conditional scope, completeness and heuristic assumptions; no new valuation. |
| Eligibility | Preserve conditional status and concrete requirements when the model claims no unresolved requirements. |

Distinguish supported, failed, unchecked and insufficient_evidence outcomes in receipts.
Unchecked means no applicable important check exists; insufficient_evidence means a defined
check cannot establish or contradict the claim from supplied evidence. Both pass through without
counting as confirmed truth or material check failures. Existing source-backed disclosure
obligations still apply. M3 findings inform proposed future checks; changes are not automatic.

## Bounded recovery and annotated delivery

1. Make one initial authoring invocation and check the recoverable document.
2. If correction is needed, make at most one correction invocation with all detected failures
   supplied together. Recheck the corrected recoverable document. No unbounded loop or third
   fallback call is adopted.
3. Choose the recoverable draft with fewer unresolved material check failures; prefer the
   corrected draft on a tie. Unchecked/insufficient_evidence outcomes are not counted as failures.
   Retain both drafts, their check receipts and the draft-selection reason.
4. Deliver that draft with unresolved failure notices attached to the affected claim/journey.
   Shared notices apply only to shared failures. Use concrete traveler language identifying
   the unreliable assertion and the supplied facts; a distant generic footer is insufficient.
5. If correction has an API failure, retain the first recoverable draft, its notices and the
   API-failure receipt. A failed correction does not discard a recoverable answer.

Notices and unavailable-detail markers are a narrow code-added-content exception. They can
supply omitted known disclosures and explain contradictory/unsupported selections. They do
not authorize a code-owned recommendation skeleton or rewrite normal prose. Preserve safe
literal rendering; do not fabricate source facts or execute provider/model markup.

Validation failures, including residual failures after correction, never become system errors.
Annotated delivery is not a clean validation pass. API failures are system errors. A response
with no recoverable document, such as undecodable schema output, is a system/generation failure;
cover this boundary in development. Existing malformed/unresolvable source acceptance errors
remain source errors, not opportunities to fabricate fallback facts.

## Input fit, settings and evidence

Clean irrelevant fields and factor shared data while retaining every distinct alternative and
decision-relevant fact. Measure the complete prepared prompt/schema and output allowance. Capped
searches and cleaning are expected to make fit practical, but byte sizes do not establish fit.
If it still does not fit, record context-limit evidence before changing the authoring strategy.
No silent preselection, truncation, hidden input cap or staged selection architecture is adopted.

Model, token/output allowance, timeout/cancellation and numerical live-campaign settings follow
prepared-input measurement. Judge settings/calibration remain M3 work. Neither this interview
nor the two-invocation policy authorizes an unspecified live diagnostic.

Offline implementation evidence must cover valid prose/table layouts, repeated scoped parts,
source-bound slot substitution, five claim families and unknown distinctions, local notices,
missing disclosures supplied as notices, more than five choices, rejected selections with
unchanged status, unavailable references, schema/generation failures, at-most-two invocations,
correction API failure retaining original content, persistent validation failures, worsening
correction/ties, shared-once bindings with equal/differing obligations and explicit/ambiguous
applicability, concise unselected notes in rejected/admitted/conditional statuses with missing-field
controls, full disclosures for selected recommendations, and exact annotated-artifact replay.
Include valid controls, not only failures. Preserve v1/v2 preparation,
checks, serialization and rendering replay when v3 checking behavior is introduced.

M3 reports output truthfulness, selection usefulness, clarity, unchecked/insufficient evidence,
annotated failures and misleading paraphrases without changing delivery verdicts. Historical
single-call campaign arithmetic must be revised before evaluation if correction is enabled.
No broader bookability/provider/task-benefit qualification follows from mechanical checks.

## Immediate sequence

Begin with offline preparation, rendering, notices and check fixtures on saved Ranking views.
Measure the complete authoring input. Then settle writer/runtime numerical settings, implement
bounded writer/recovery/replay, and declare the budget before any actual-authoring diagnostic.
There are no remaining owner policy questions in the current interview frontier; engineering
mechanics and measurement-dependent settings remain future work. Final shared-understanding
confirmation closes this interview and is distinct from authorizing implementation or live calls.

The owner resolved the disclosure scope on 2026-10-08: full journey facts apply to selected
recommendations; unselected journey notes preserve identity, exact source status and
source requirements/reason, with rejected notes visibly excluded. A fresh challenge corrected
the earlier documentation that had narrowed concise notes to rejected candidates alone. Use the
versioned v3 representation while preserving v1/v2 replay. See the dated
[ADR 0026 amendment](../adr/0026-model-authored-results-with-bound-facts.md#2026-10-08-amendment--rejected-candidate-note-disclosures)
and [fresh challenge record](../build-log/2026-10-08-results-m2-disclosure-reconciliation.md#fresh-policy-challenge).
