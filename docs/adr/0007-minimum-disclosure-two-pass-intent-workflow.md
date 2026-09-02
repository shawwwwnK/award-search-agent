# 0007: Minimize disclosure across the two-pass intent workflow

- Status: Approved

## Context

The approved request-understanding workflow has two model passes separated by deterministic
grounding and calendar enrichment. That separation is a trust checkpoint, not merely a prompt
sequence:

`Pass 1 -> grounding/catalog construction -> Pass 2 -> deterministic evaluation`

The current adapter does not enforce that information boundary. `IntentExtractor.extract` accepts
and serializes the complete `RawRequest`, so pass one sees both `reference_date` and `timezone`.
`TemporalResolver.resolve_dates` then serializes the complete `RawRequest`, the complete
`CoarseIntentExtraction`, and every complete `ResolvedTemporalAnchor`. Pass two consequently sees
the reference date and timezone again, resolved anchor `start` and `end` dates, calendar/provider
source metadata, and unrelated non-temporal extraction fields. The Python protocols expose the same
broad domain objects, so prompts are the only barrier against using prohibited fields.

This encouraged a phase violation in the retained live evaluation: `next month` was represented in
pass one as an explicit September `MonthAnchor` when the request named no month. September is the
correct deterministic result for the supplied August context, but it is neither an explicit fact nor
a valid first-pass anchor.

ADR 0005 established canonical grounded evidence after pass one, but pass two still repeats raw
quotes and occurrence indexes instead of selecting those canonical entries. ADR 0006 moved calendar
arithmetic out of pass two, but pass two still receives the concrete calendar values that it is
forbidden to calculate. The post-fix 48-run evaluation reached ADR 0006's reliability revisit
trigger: 19 runs failed flat-wire conversion, 14 failed anchor or graph validation, three completed
runs failed strict grounding, and four completed with incorrect temporal semantics.

The workbook's general state-graph canvas allows a parse node to receive optional UI profile data.
For this milestone, the more specific repository boundary is narrower: pass one receives request
text only. This is an intentional refinement, not authorization to add profile state to the current
workflow.

## Current information-flow audit

| Stage | Current input | Current output | Boundary observation |
| --- | --- | --- | --- |
| CLI/workflow entry | Request text, reference date, timezone | `RawRequest` | Full context is correctly retained by deterministic orchestration. |
| Pass one adapter | Complete `RawRequest` JSON | `CoarseIntentExtraction` | Leaks reference date and timezone. The output combines non-temporal semantics, model-assigned anchor IDs, explicit anchors, raw quotes, occurrence indexes, and claim labels. |
| First-pass sanitation | `RawRequest`, coarse extraction | Sanitized coarse extraction | Deterministically grounds quotes, checks anchor kind/provenance, rejects duplicate anchor IDs, and removes an unsupported year. It currently retains model-assigned IDs. |
| Location preservation | `RawRequest`, coarse extraction | Coarse extraction with explicit airport codes preserved | Uses request text deterministically; it must not expand cities into airports. |
| Evidence grounding | `RawRequest`, coarse extraction | `GroundedTemporalEvidence[]` | Assigns offset-derived evidence IDs and exact source spans. This canonical result is not currently supplied to pass two. |
| Anchor enrichment | `RawRequest`, coarse extraction, optional holiday provider | `ResolvedTemporalAnchor[]` | Correctly owns reference-date/year selection, holiday lookup, concrete dates, and provider provenance. These private values currently cross into pass two. |
| Pass two adapter | Complete `RawRequest`, complete coarse extraction, complete resolved anchors | Flat nullable `TemporalRelationGraphWire`, then typed `TemporalRelationGraph` | Leaks reference date, timezone, resolved dates, holiday-provider metadata, inferred calendar years through resolved dates, and unnecessary travelers, locations, cabins, search modes, constraints, and ambiguities. It also asks the model to repeat quotes/occurrences and normalized duration bounds. |
| Relation validation/evaluation | Full request, coarse extraction, typed graph, resolved anchors | Deterministic `DateResolutionProposal` | Correctly owns grounding, references, dependency/cycle checks, calendar arithmetic, duration conversion, and unresolved preservation. Error detail is currently compressed at the adapter boundary. |
| Relation evidence grounding | Full request, graph, first-pass evidence | Combined grounded evidence | Re-grounds repeated pass-two quotes; this duplication disappears when pass two selects evidence IDs. |
| Conflict/unknown/clarification policy | Deterministic proposal, extraction, evidence, full request context | `ParsedRequest`, conflicts/unknowns, `ClarificationDecision` | Correctly remains deterministic and retains the complete request context and trace. |

No holiday-provider output or expected evaluation answer is sent to pass one today. The expected
answer is also absent from the production pass-two call. Those properties remain mandatory.

## Relation-vocabulary audit

The ready scenarios and relevant draft component, adversarial, stability, and metamorphic cases
require the following semantic coverage:

| Meaning | Representative cases | Required representation / finding |
| --- | --- | --- |
| Explicit anchor windows | exact outbound/return dates; Labor Day and Christmas windows; named May, June, October, and January | Exact-date, named-month, and supported named-holiday anchors are allowed only with literal source support. Window policy is selected semantically and evaluated deterministically. |
| Month portions | `early May`, `mid February`, `late February`, plain/whole October, `first week of June` | Early/mid/late/whole are represented today. `first week of June` is a ready-case need not explicitly represented by the current four-value `month_portion` vocabulary and must be addressed deliberately rather than widened silently. |
| Relative weekends | `weekend afterwards`, first weekend after New Year, two weekends after Thanksgiving, first weekend following Christmas | Direction, ordinal, and a catalog reference are sufficient; calendar dates remain deterministic. |
| Relative weekdays | flexible preceding Thursday and draft weekday alternatives | Weekday, direction, ordinal, and reference are sufficient for a single relation. Alternative weekdays require explicit alternative semantics or preservation without widening them into one continuous range. |
| Relative offsets | `two weeks after New Year`; loose `a couple weeks past Thanksgiving` | A point offset must remain distinct from duration. The current single `amount` cannot faithfully express the draft loose one-to-three-week offset; preserve it unresolved unless the vocabulary is deliberately extended. |
| Relative calendar periods | ready `next month` | Needs a typed relation to symbolic `context:request_date` with direction, unit, ordinal, and whole-calendar-period semantics. It must not become an explicit named-month anchor. It differs from adding one month to a date point. |
| Durations | exact/approximate days and weeks, alternatives, `about a week`, month units, cross-month/year arithmetic | Pass two should extract literal quantities, unit, and modifier. It must not author normalized day bounds or invariant return/departure wiring. Deterministic policy performs all conversions. |
| Unbounded boundaries | `after New Year`, `not before New Year`, and variants | Remain directional but unbounded and lead to explicit unresolved/clarification state unless combined by an approved bounded relation. Duration must not create a departure bound. |
| Unresolved relations | unsupported holidays, ambiguous holiday phrases/references, uncovered temporal wording | Every meaningful claim must be consumed by a compatible relation or explicitly preserved as unresolved; invalid items cannot be silently dropped. |
| Seasons | ready `next spring` | No approved deterministic season policy exists. Preserve `next spring` as unresolved. Do not create a March anchor or infer season boundaries. |

The draft bounded `after January 10 but before January 20` case and non-contiguous date-alternative
cases also expose composition needs beyond individual relation kinds. The current evaluator combines
multiple produced windows by their outer minimum/maximum, which can erase holes and does not define
general boundary intersection. This ADR does not invent an intersection/alternative operator; those
cases must remain explicitly unsupported or be governed by a later approved contract.

## Decision

Keep two model passes and replace broad domain-object serialization with dedicated, structurally
narrow model views.

### Pass one

Pass one receives `CoarseExtractionInput` containing request text only. It must not contain a
reference-date value, timezone, resolved calendar date, provider output, or inferred calendar value.
Its output contains non-temporal request fields; only literally named exact-date, named-month, and
supported named-holiday anchors; and verbatim temporal evidence linked to coarse claim labels.
Deictic phrases such as `next month` and `next spring` remain evidence, not normalized anchors.

### Deterministic checkpoint

After pass one, deterministic code:

- grounds every quote against the immutable request;
- validates explicit-anchor provenance and kind compatibility;
- assigns canonical evidence IDs, exact offsets, claim labels, and source ordering/envelopes;
- assigns stable explicit-anchor IDs and kinds;
- privately resolves anchors with the reference date, timezone, calendar rules, and holiday provider;
- constructs the allowed symbolic-reference catalog, including `context:request_date`; and
- retains the complete `RawRequest` for later deterministic evaluation and trace output.

Model-supplied IDs are not authoritative catalog membership. No invalid evidence or anchor advances
past this checkpoint.

### Pass two

Pass two receives `TemporalInterpretationInput` containing only:

- a temporal transcript or the minimum bounded request wording needed for semantic coreference;
- grounded evidence IDs, exact text, claim labels, source order, and bounded envelopes;
- explicit anchor IDs and kinds, without resolved dates; and
- allowed symbolic-reference keys, without their private values.

Pass two selects supplied evidence, anchor, and reference identifiers. It does not repeat raw quotes
or occurrence indexes. It emits fixed per-relation collections that deterministically convert to the
typed internal graph. It receives no concrete reference date, timezone, resolved anchor boundary,
holiday-provider metadata, inferred year, expected answer, or unrelated non-temporal extraction.

The semantic contract includes distinct forms for point offsets and whole relative calendar
periods. Thus `next month` means ordinal one, direction after, unit month, whole calendar period,
referenced to `context:request_date`; “one month after this date” is a point offset. Concrete results
are never model output.

### Deterministic evaluation

Deterministic code retains all concrete calendar state and owns catalog membership, relation/evidence
compatibility, dependency and cycle validation, calendar and holiday policies, duration
normalization, window construction, conflict detection, unknown preservation, and clarification
policy. Strict failures remain explicit rather than becoming success-shaped fallbacks.

One bounded repair attempt may be made separately at the first-pass checkpoint and pass-two
validation boundary. A repair receives the same narrow original input, the rejected model output,
and structured validation errors only. It cannot receive private calendar values, expected results,
or an inferred correction. The full deterministic validation runs again; a second failure is final.

## Relationship to earlier decisions

This ADR refines ADR 0001 by making the model boundary structural rather than prompt-only. It refines
ADR 0003 by preserving two passes while removing resolved anchors and request context from the second
model payload. It refines ADR 0005 by making canonical evidence IDs the pass-two evidence contract;
pass one may still emit exact quotes and occurrence indexes because deterministic grounding has not
yet occurred. It refines ADR 0006 by hiding enriched calendar values, adding symbolic context-relative
relations, and replacing the flat nullable wire object with fixed per-relation collections.

ADR 0006 remains authoritative for the typed semantic graph and deterministic calendar ownership.
This ADR does not approve a season policy, a general relation-composition operator, search planning,
provider search, airport expansion, or any functionality beyond request understanding.

## Consequences

- Prohibited context is structurally absent from model inputs and testable at the serialized-payload
  boundary.
- The same deictic request can produce identical model-facing semantics under different request
  dates while deterministic results vary correctly.
- Pass two cannot invent source evidence, anchors, or references without failing catalog validation.
- Catalog construction and model-view contracts add explicit adapter code and migration work for
  interfaces, fakes, fixtures, traces, and evaluation metrics.
- A single bounded repair adds at most one extra call at either validation boundary and must be
  measured separately from first-attempt completion.
- Unsupported seasons and relation-composition gaps remain visible instead of being guessed.

## Evaluation

Offline tests must inspect serialized payloads, not prompts alone. They cover pass-one context
invariance, pass-two semantic invariance, deterministic result variation by request date, named month
versus deictic month, absence of private dates/timezone/provider metadata, catalog membership,
claim coverage, unsupported seasons, structured failure preservation, and repair non-leakage.

Live evaluation reports pass-one, pass-two wire, grounding, semantic validation, deterministic
output, and clarification failures separately. It also reports first-attempt completion, repair
attempts/successes, final completion, latency, and usage/cost when available. Historical artifacts
remain evidence under their original evaluator contracts and are not silently treated as directly
comparable.

## Revisit trigger

Revisit if catalog-only context cannot resolve recurring coreference, if a ready scenario requires a
new calendar policy such as seasons, if relation composition is approved, or if measured two-pass
reliability, latency, or cost no longer justifies the deterministic trust checkpoint.

Approved by the project owner through the explicit two-pass redesign direction on 2026-09-01.
