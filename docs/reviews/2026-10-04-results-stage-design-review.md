# Results Stage design and milestone review

Date: 2026-10-04. Scope: design revision, independent subagent review, current official LLM-call
research and offline upstream verification. No Results runtime implementation or live-model/provider
evaluation was performed.

The revised design gives the **LLM full control of the supported answer structure**: headings,
order, grouping, paragraphs, lists, tables and emphasis. Code fills factual slots and validates
content. The owner explicitly reiterated this constraint during the review. The earlier
code-assembled skeleton and opening/per-journey editorial contract have been replaced in the
active documents, rather than left behind additional supersession notices.

## Findings and dispositions

| Priority | Finding | Design disposition |
| --- | --- | --- |
| High | Active M2 skeleton/ResultsWritingPlan sections contradicted the October 3 owner clarification. | Replace them with one ResultsDocument manifest and freely ordered scoped Markdown parts. Code creates no cards, sections, headings, order or missing-note insertions. |
| High | One contiguous journey block would restrict comparison tables and other model-chosen layouts. | Permit repeated/interleaved scopes and model-written separators; count unique selected journeys, not parts. Test prose and table layouts. |
| High | Required tokens could exist without visible disclosure, including syntax spanning part boundaries. | Parse the final concatenation, retain slot source maps, enforce visible obligations, escape substitutions and reject unsupported markup. Missing content invalidates the draft. |
| High | Schema/hash/M2 derivation checks accept a seeded import missing M1 seat/party blockers. | Propose a narrow matching-owned, versioned source-requirement verifier before general Results imports. Keep an independently pinned reviewed-fixture prototype as an explicitly narrower path. No copying matching policy or retrospective reinterpretation. |
| High | A seeded cost-summary omission could hide limitations while canonical missing parts remain. | Project canonical cost/component limitations and check summaries. Add independent source oracles so writer and judge do not share an unchecked projection error. |
| Medium | Invocation counts masked SDK retries; refusal/incomplete/deadline behavior lacked a concrete contract. | Recommend one strict response, SDK retries disabled, no automatic repair, explicit finite settings and distinct outcomes. Numerical budgets/model choice must be recorded before calls. |
| Medium | Exact replay and new generation were not sufficiently distinguished. | Save the accepted document and bound versions/inputs; exact substitution replay makes zero calls. New authoring is a new artifact. |
| Medium | Nullable cash selection could omit the ADR 0022 anchor silently. | Require a separate suitable observed benchmark or the supplied unavailable/unsuitable explanation; never infer comparability/savings. |
| Medium | Fallback was described both as unsettled and as adopted owner direction. | Keep the original factual-summary idea, mark exact breadth open, and define explicit failure artifacts. Successful answers always preserve model structural control. |
| Medium | M3 could share projection mistakes, tune/evaluate on the same labels, count unexercised families or duplicate M2 calls. | Independent source assertions, valid controls, actual feature predicates, frozen calibration/held-out labels, full error denominators and hash-qualified reuse. |

These fixes strengthen the declared Results boundary without changing frozen planning/provider/
ranking policies. The proposed import verifier is a narrow acceptance extension that still needs
implementation and tests; this design does not claim it already exists or that normal matching
outputs exhibit the seeded corruption.

## Structure and fact binding

The selected design is `ResultsDocument {selections, benchmark_id, incomplete_ids, parts}`. Each
part contains model-written Markdown and an invisible shared/journey/benchmark/incomplete scope.
Several parts may share one journey ID. A table can have separate journey-scoped rows followed
by conditions in later parts; code concatenates exact strings before filling/validating. This
retains a local wrong-variant lookup guard without forcing each alternative into one card.

The rejected alternatives were a code-owned assembled answer (contrary to owner direction), a
single contiguous block per journey (unnecessary layout restriction), and an unrestricted generic
template engine (unnecessary execution/escaping hazards). One unscoped Markdown string with fully
qualified references would be simpler to serialize, but offers less local fact-binding protection.
The selected contract adds no model tool loop or multi-agent product orchestration.

This is not a proof of arbitrary prose truth. A correct amount can still appear under a false
“per person” table heading, or a conditional option can be described as guaranteed. M3 evaluates
the final visible document, including association, framing and implied comparisons. Code-visible
slot checks do not certify natural-language entailment or user comprehension.

## Verified repository evidence

A read-only investigator rechecked all three saved M2 artifacts and actual M1/M2/provider contracts.

| Case | Retained candidates | Eligible | Award observation groups | Repeated eligible award/cash pairs | Cost reference |
| --- | ---: | ---: | ---: | ---: | --- |
| Mixed access | 473 | 257 | 23 | 0 | Absent |
| Exact business | 396 | 106 | 3 | 0 | Absent |
| Positioning | 123 | 64 | 4 | 0 | Absent |

All 427 eligible cost assessments are undetermined. Coverage is partial in all three: mixed access
26 completed/128 omitted units; exact business 12 completed/4 empty/39 omitted; positioning
19 completed/1 partial/53 omitted. Units overlap in the graph and cannot be turned into a simple
percentage of flight searches or evidence of exhaustive coverage. These are candidate records,
not independently unique flight schedules. [Saved corpus](../../evidence/ranking-stage/m2/README.md).

Current M1 status checks depend on supplied reasons; its artifact checks do not rederive all
source-required conditions. M2 rederives its own features/styles from the attached M1 artifact.
[Matching contracts](../../src/award_agent/ranking/contracts.py),
[requirement logic](../../src/award_agent/ranking/matching.py),
[style validation](../../src/award_agent/ranking/style_contracts.py).

The October 3 preserved probe removed `award_travelers_unknown` and
`result_validation_minimum_award_seats` from candidate `d1826c2e…`, changed it to admitted and
updated accounting while retaining attached source evidence; downstream checks accepted it.
Another probe emptied 64 nonempty cost `validation_needs` lists while underlying missing parts
survived. These are **previously recorded seeded faults**, reviewed here, not newly observed
production failures or freshly rerun mutations.
[Probe results](evidence/2026-10-03-built-stages/evaluation_oracles.json).

Fresh verification:

```sh
.venv/bin/python scripts/ranking_style_corpus.py --fx-snapshot data/ranking/m2/fx-2026-09-29.json --output-dir evidence/ranking-stage/m2/styled --verify
.venv/bin/python -m pytest -q tests/unit/test_ranking_m1.py tests/unit/test_ranking_m2.py tests/unit/test_ranking_m2_corpus.py
```

The corpus verifier passed all three cases; the focused suite passed **50 tests in 63.35 seconds**.
This verifies the existing declared upstream boundaries, not the unimplemented Results design or
closure of the seeded import/oracle gaps. Earlier cleaned-byte measurements remain incomplete
prototypes; no complete model-context fit or Results model quality was measured.

## Current LLM-call guidance and application to this design

An independent investigator used the OpenAI Docs skill, searched and fetched official documentation,
and inspected installed local adapters/SDK. Sources below were accessed on 2026-10-04. API facts
are distinguished from project-specific choices; source pages may change.

| Official guidance | Results-specific recommendation |
| --- | --- |
| Structured response formatting and function calls serve different purposes; strict schemas constrain the response envelope, not semantic truth. Required fields can use null; object schemas disallow extra properties. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). | One strict response containing freeform Markdown strings and scoped metadata. No submission/lookup tool is needed to author this document. Validate IDs, slots, status and content separately. |
| Refusals can fall outside the requested schema. Reasoning tokens consume the output budget and can exhaust it before visible text. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs#refusals-with-structured-outputs), [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning). | Refusal or incomplete status becomes explicit generation failure; never publish a partly parsed answer. Measure a suitable budget for the evaluated model. |
| Responses storage can be disabled; conversation state is optional. [Responses migration guide](https://developers.openai.com/api/docs/guides/migrate-to-responses). | Stateless writer/judge calls with `store=False`. Keep explicit private local traces; do not equate this setting with zero provider retention. |
| Retries consume rate capacity and need bounded handling. [Rate limits](https://developers.openai.com/api/docs/guides/rate-limits). Local SDK 1.109.1 defaults were independently inspected: two retries and 600-second read timeout. | Initial Results profile: one invocation, SDK `max_retries=0`, no repair, finite recorded timeout/output/cancellation behavior. This is an engineering proposal, not a universal no-retry recommendation. |
| Instructions and data should be clearly separated; adversarial testing is necessary. [Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering), [safety testing](https://developers.openai.com/api/docs/guides/safety-best-practices). | Stable instructions/slot rules and contrasting layouts; delimited brief, untrusted provider/planning text, no action tools. Test semantic prompt injection and Markdown hiding independently. |
| Evaluation should be task-specific, calibrated with human feedback and use clear grading criteria. [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices). | Advisory ordinary Responses judge, passage/fact references, independent labeled holdout, planted faults and valid controls. Human review remains necessary; the judge does not authorize runtime output or repair it. |
| Prefix caching can benefit repeated prompts on supported models. [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching). | Put stable instructions/schema before variable data where the API allows; observe cached-token usage. Do not add custom cache architecture or claim savings before measurement. |

Existing adapters demonstrate `responses.parse`, Pydantic output types and `store=False`, but
inherit client defaults. Reuse their narrow interface pattern while explicitly configuring the
new Results adapter. [Intent adapter](../../src/award_agent/intent/openai_extractor.py),
[gateway adapter](../../src/award_agent/search_planning/gateway_generator.py).
No writer or judge model was selected from generic guidance; Results evidence must support that choice.

## Milestone consequences and remaining choices

M1 gains an explicit import-authority gate and independent preservation checks. M2.1 proves the
same facts can support different model-authored structures; M2.2 adds bounded call/failure/replay
behavior; M2.3 obtains actual answer evidence. M3's rubric starts early, and its calibrated repeated
review follows stable outputs. Hard factual violations, legitimate layout/selection variation and
quality concerns have distinct reporting. No generic overall score excuses hard errors.

The 12 × 3 writer plus 47 judge-call proposal still totals 83 application calls before any extra
held-out/calibration/model-comparison work. Such extra work needs its own finite run budget. No
model/provider call was made or qualified in this review. Valid M2 generations may be reused only
with matching frozen configuration and no duplicate counting.

Open choices remain exact failed-generation delivery/fallback breadth, evaluated writer/judge
models and numerical live-call budgets. They do not block offline M1 or hand-authored M2.1.
The requested design update is complete without guessing the owner's acceptance of those choices.
Broader task benefit and external delivery remain separate from Results Stage acceptance.

## Review process and limits

Three subagents independently reviewed architecture/milestones, verified repository contracts/
corpus, and researched official LLM-call guidance. The architect additionally challenged the
scoped-part design against the owner's reiterated structural-control requirement. Parent integrated
the changes and obtained final architecture and source-guidance checks. The final pass confirmed
structural control and corrected a maximum-only selection rule (successful answers require at
least one complete choice when available), narrowed the import-verifier guarantee to its declared
requirement subset, applied explicit call-failure discipline to the judge, and corrected proposed
calibration fixtures that had been called existing. Agents made no edits
and did not delegate further. No deep-architect escalation was needed.

The relevant workbook sections were consulted read-only; newer narrower repository decisions take
precedence. Existing October 3 review artifacts and pre-existing deferred-register changes were
preserved. No runtime, saved provider/ranking artifact, credential, or private travel export was
changed. See the [build log](../build-log/2026-10-04-results-stage-design-review.md) for checks and
final review disposition.
