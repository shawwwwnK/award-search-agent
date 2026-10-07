## Problem Statement

A traveler needs to turn observed award-led journeys into understandable options to investigate.
Ranking already supplies trusted facts, eligibility, conditions and solution-style assessments,
but there is no Results implementation that explains these options. Raw variants obscure the
tradeoffs between award programs, cash positioning flights, timings, cabin evidence and costs.

The traveler should receive a useful answer even when authoring fails an important check. A
contradicted assertion or omitted disclosure should prompt correction and, if unresolved, a
clear notice beside the affected information. Such validation failures must not become system
errors or cause recoverable results to disappear. At the same time, annotations must not turn
unknown information into confirmed facts or change upstream eligibility.

## Solution

Build Results M2: a model-authored answer with source-bound facts, selected deterministic claim
checks, one bounded correction opportunity and annotated delivery. The model chooses the answer's
structure, wording, grouping and useful distinct journeys. Code fills factual slots and checks
important assertions without prescribing a recommendation layout.

Use one initial authoring invocation and at most one correction invocation. Deliver the
recoverable draft with fewer unresolved material check failures, preferring correction on ties.
Attach concrete Validation notices to affected claims or journeys, supplying known omitted
disclosures where necessary. Preserve recoverable content and show unresolved references as
“Details unavailable.” API failures and responses with no Recoverable draft are system/generation
failures; validation failures on recoverable content never block delivery.

Keep Results evaluation in M3: measure truthfulness, usefulness and clarity, including gaps in
check coverage, without acting as a runtime validator. Exact model and numerical settings follow
complete-input measurement; this spec does not authorize unspecified live calls.

## User Stories

1. As a traveler, I want a readable explanation of observed award-led journeys, so that I can decide which options to investigate next.
2. As a traveler, I want the answer organized around useful comparisons, so that I can understand tradeoffs without reading raw observations.
3. As a traveler, I want useful distinct choices rather than redundant variants, so that I can focus my investigation.
4. As a traveler, I want multiple meaningful alternatives within an Award group when helpful, so that I can compare different cash components or transfer timings.
5. As a traveler, I want the number of choices to remain flexible, so that an arbitrary presentation target does not hide useful options.
6. As a traveler, I want every selected journey's facts to belong to that exact variant, so that another variant's price or duration is never substituted.
7. As a traveler, I want a journey identified when its explanation resumes later, so that I can associate caveats and facts with the right option.
8. As a traveler, I want redemption programs named clearly, so that I know where the award is offered.
9. As a traveler, I want operating airlines distinguished from redemption programs, so that I do not infer an unsupported carrier.
10. As a traveler, I want local departure and arrival dates, times and timezone context, so that overnight and date-line travel are understandable.
11. As a traveler, I want complete elapsed time and relevant waits, so that I can compare the entire journey.
12. As a traveler, I want journey-level, leg-level and cash-flight cabin evidence distinguished, so that I understand what business-class assertions establish.
13. As a traveler, I want reported mixed cabins and unreported cabin details disclosed, so that I do not assume every leg has the same cabin.
14. As a traveler, I want points, fees and cash components displayed with their units and quote scope, so that I understand what each amount covers.
15. As a traveler, I want missing costs distinguished from observed zero amounts, so that unknown fees do not appear free.
16. As a traveler, I want incomplete price scope to remain explicit, so that indicative quotes do not appear to be complete party totals.
17. As a traveler, I want fastest and cheapest statements tied to supported references and assumptions, so that I understand the limits of those comparisons.
18. As a traveler, I want existing solution-style memberships preserved, so that Results does not invent a new ranking or eligibility policy.
19. As a traveler, I want conditional journeys and concrete unresolved requirements explained, so that I know what must be checked before proceeding.
20. As a traveler, I want separate-ticket obligations disclosed beside the affected journey, so that timing checks do not imply connection protection.
21. As a traveler, I want missing connection-protection evidence distinguished from confirmed protection, so that I do not rely on an unsupported promise.
22. As a traveler, I want component observation dates shown, with precise times when material, so that a cash observation does not appear to refresh the award.
23. As a traveler, I want actual provider coverage and omitted work explained, so that partial searches do not appear exhaustive.
24. As a traveler, I want a direct cash benchmark kept separate from award recommendations, so that a benchmark does not displace an award option or imply unsupported savings.
25. As a traveler, I want an unavailable or unsuitable benchmark explained, so that missing benchmark evidence does not invite invented prices.
26. As a traveler, I want supported incomplete possibilities distinguished from complete journeys and rejected combinations, so that research leads do not appear ready to book.
27. As a traveler, I want genuinely empty searches distinguished from failed or omitted work, so that I understand what absence of results means.
28. As a traveler, I want unsupported important assertions checked against the source, so that avoidable mistakes can be corrected.
29. As a traveler, I want a correction attempt when important checks fail, so that the workflow improves the answer without immediately stopping.
30. As a traveler, I want remaining failures described beside the affected information, so that a distant generic warning does not hide a contradiction.
31. As a traveler, I want omitted known disclosures supplied in Validation notices, so that I receive the actual decision-changing information.
32. As a traveler, I want Recoverable drafts delivered with clear limitations, so that validation failures do not erase useful results.
33. As a traveler, I want unavailable factual references identified honestly, so that another journey's information is not used to fill the gap.
34. As a traveler, I want a rejected candidate visibly identified as excluded, so that an authored recommendation cannot override upstream rejection.
35. As a traveler, I want the more reliable Recoverable draft retained if correction worsens it, so that revision does not automatically degrade the delivered answer.
36. As a traveler, I want the original Recoverable draft retained when correction encounters an API failure, so that a failed correction does not discard existing results.
37. As a project owner, I want Unchecked claims distinguished from Insufficient evidence, so that I can separate missing logic from missing source information.
38. As a project owner, I want unknown outcomes excluded from confirmed passes and material failure counts, so that metrics do not invent certainty or penalize absent checks.
39. As a project owner, I want the initial check catalog focused on important claim families, so that the system does not overconstrain semantic expression.
40. As a project owner, I want claim checks separated from upstream eligibility, so that Results does not reopen completed stages.
41. As a project owner, I want every distinct alternative retained in the prepared input, so that hidden pruning does not determine the writer's choices.
42. As a project owner, I want complete cleaned-input measurements, so that context fit and numerical settings are based on evidence.
43. As a project owner, I want context-limit outcomes recorded explicitly, so that oversized inputs are not silently truncated.
44. As a project owner, I want both drafts, attempt outcomes and check receipts preserved, so that Annotated delivery can be explained and audited.
45. As a project owner, I want exact saved-artifact replay without model calls, so that delivered wording, facts and notices can be reproduced.
46. As a project owner, I want schema and generation failures exercised during development, so that no-document failures have tested behavior.
47. As a project owner, I want offline tests using fake writers and frozen source inputs, so that correctness checks require neither live models nor providers.
48. As a project owner, I want M3 to report misleading paraphrases, undeclared assertions and notice clarity, so that important new checks can be proposed from observed failures.
49. As a project owner, I want validation, generation, delivery and evaluation outcomes kept distinct, so that delivered results are not mistaken for clean validation or semantic qualification.
50. As a project owner, I want explicit scope and evidence limits, so that local implementation does not become a claim of bookability, provider reliability or traveler-task benefit.

## Implementation Decisions

- Scope this work to Results M2. Ranking is closed; Results runtime is unimplemented. Treat the owner's request to synthesize this spec as direction to document the settled conversation, not as authorization to implement or run live diagnostics.
- Consume Ranking's trusted SolutionView directly and retain its ProjectionReceipt internally. Do not create another equivalent factual projection, rederive matching policy or add an upstream requirement verifier.
- Build Results preparation, authoring contracts, factual rendering, claim checks, recovery/delivery orchestration and replay around one public Results API. Add a narrow writer interface, a live adapter and a local CLI; production workflow/UI integration remains separate.
- Preserve all distinct alternatives, source-linked facts and dispositions. Factor shared data and omit irrelevant technical fields from model context without hidden input preselection or a separate input cap.
- Represent authored answers as ResultsDocument: a selection manifest, separate benchmark and incomplete references, and ordered scoped Markdown parts. Parts may repeat and interleave; invisible scopes are not cards or a required layout.
- Bind factual slots to exact scopes. Preserve same-variant association, timezone-aware schedules, quote scope, missing costs, cabin distinctions, conditions and coverage. Perform single literal substitution without recursive interpolation or source markup execution.
- Associate material claim-bearing spans with Declared claims containing typed claim kinds and exact journey/comparison scopes. The model controls wording; deterministic checks do not prove arbitrary paraphrase truth or detect every undeclared assertion. Exact serialization is engineering work; there is no implemented prototype to freeze.
- Start with five check families: cabin, connection protection, price scope, fastest/cheapest comparisons, and eligibility assertions. Use existing source evidence and supplied references; do not infer absent protection, leg cabins, scope, personal redeemability or new valuation arithmetic.
- Record supported, failed, unchecked and insufficient-evidence outcomes. Unchecked claims have no applicable important check; Insufficient evidence means a defined check lacks enough information to establish or contradict the proposition. Both are non-blocking, neither confirms truth, and neither counts as a material failure.
- Retain required disclosure checks in addition to the claim catalog. Unknown claim outcomes do not waive source-backed obligations. M3 findings inform proposed additions; they do not automatically install new runtime checks.
- Let the model choose useful distinct admitted/conditional complete journeys and justify nonredundant choices. Usually three and roughly five are presentation guidance, not a schema maximum. Do not cap an Award group at two. Over-target output remains deliverable with an associated notice after correction.
- Preserve upstream statuses and styles. A rejected candidate shown in authored content is visibly excluded, with its reason attached; it cannot acquire admitted status or style labels. Unresolvable factual references show “Details unavailable” with a local notice rather than borrowed facts.
- Keep direct cash as a separate benchmark with limitations or an unavailable/unsuitable outcome. Preserve complete/incomplete/rejected/empty/partial distinctions and existing scope restrictions.
- Make one initial authoring invocation and at most one correction invocation. Send all detected failures together and recheck correction. No unbounded correction loop, third fallback call or automatic model-switch policy is adopted.
- Retain the Recoverable draft with fewer unresolved material check failures; prefer correction on ties. Preserve both drafts, their receipts and the selection reason. On correction API failure, retain the initial Recoverable draft and its notices with the API-failure receipt.
- Deliver recoverable content even when validation failures remain. Attach concrete traveler-facing Validation notices to affected claims or journeys; use shared notices only for genuinely shared failures. Supply omitted known disclosures from trusted source facts within those notices.
- Keep answer and fallback layout model-authored. Code-added notices and unavailable-detail markers are a narrow exception; they do not authorize a code-owned recommendation skeleton, broad editorial rewrite or new facts.
- Treat API errors and schema/generation responses with no recoverable document as system/generation failures. Existing malformed or unresolved source acceptance errors remain source errors. Residual validation failure on recoverable content never becomes a system error.
- Preserve source, search evidence, generation, validation, delivery and evaluation outcomes separately. Annotated delivery is not a clean pass. Retain versions/digests, settings, attempts, selected document, inserted-fact/source map, notices and final rendered bytes for exact replay.
- Measure complete prompt/schema size and output allowance before selecting model/output/timeout/cancellation/live-campaign settings. Residual overflow becomes an explicit context-limit outcome before authoring strategy changes. No numeric settings or paid campaign are invented here.
- Keep M3 as separate output-quality evaluation with no runtime semantic judge. M3 measures residual semantic gaps and usefulness; Results validation is not a terminal delivery gate.

## Testing Decisions

- Owner-confirmed primary seam: exercise the public Results API with a trusted SolutionView, source receipt, explicit configuration and a deterministic fake writer, and assert the delivered ResultsArtifact. This is the highest cohesive seam for preparation, authored rendering, claim checks, recovery and notices. The owner confirmed this primary seam; the Results API itself is not yet implemented.
- Prefer external behavior: rendered visible content and associations, retained statuses/facts, invocation counts, draft selection, notices, outcome dimensions and replay bytes. Avoid assertions about private helpers, module count or internal processing order except where an observable guarantee depends on it.
- Reuse frozen Ranking exports and existing independent source-backed expectations. Prior art includes Ranking solution-projection preservation and saved-corpus tests, which check exact variant identities, scopes and conditions against upstream facts rather than projector-generated expected values.
- Exercise valid prose-led and table-led answers, repeated/interleaved journey scopes, resumed visible identification and layouts crossing part boundaries. Include valid alternate wording and layouts so a reject-everything check cannot pass the suite.
- Cover factual binding through the public API: points/fees/cash scope, zero versus missing costs, carrier/program differences, local/UTC and date-line timing, journey/leg/cash cabin evidence, exact variant waits and price/duration association. Do not rerun upstream eligibility as a Results requirement.
- Cover the five initial claim families with supported, contradicted, unchecked and insufficient-evidence cases. Demonstrate that unknown outcomes are non-blocking without becoming confirmed passes or material failures, and that required disclosures remain independent obligations.
- Cover one correction containing all failures, clean correction, persistent failure with Annotated delivery, worsening correction, equal failure counts, and exclusion of unknown outcomes from draft comparison. Verify at most two application-level invocations.
- Cover notice placement beside the affected prose or table entry, shared versus journey-specific notices, omitted known disclosures supplied in notices, contradictory claim explanations, over-target choice counts, rejected status preservation and unavailable references without cross-journey substitution.
- Cover genuinely empty, incomplete-only, rejected and partial-coverage answers, separate usable/unusable cash benchmarks, and absence of any new provider calls or hidden candidate truncation.
- Cover initial and correction API failure, refusal/incomplete/schema outcomes, recoverable content versus no recoverable document, and preservation of the initial draft on correction API failure. Cover source errors causing zero writer calls. Use boundary-focused fake transport tests only where the Results API cannot observe a necessary adapter guarantee.
- Test exact replay of clean and annotated artifacts, including whichever draft was retained, inserted facts, unavailable markers and notices, with a writer that raises if called. Prior art is provider replay's explicit never-live guard and immutable evidence checks.
- Use minimal CLI contract tests for argument handling, output serialization, immutable/atomic evidence behavior and outcome reporting. Prior art is Ranking solution-export CLI testing; the CLI must delegate Results behavior rather than contain workflow logic.
- Treat fixture checks as offline development evidence. Prepared-input size measurements are evidence, not semantic quality or context-fit qualification. Live diagnostics require separately recorded settings and budgets, and all attempts/failures remain in reported denominators.

## Out of Scope

- Reopening intent, clarification, search planning, provider execution, Ranking eligibility or solution-style policy.
- New travel-provider calls, acquisition-date expansion, additional providers, booking, transfers, purchases or external actions.
- Round trips, cash-only recommendations, broader mixed-journey assembly, both-end cash positioning or new cabin constraints.
- Weighted overall ranking, new FX or valuation/savings arithmetic, inferred quote scope, hidden pruning or forced style quotas.
- A code-owned normal-answer or fallback recommendation layout, runtime semantic judge, automatic evaluator approval or unbounded repair.
- Production UI, authentication, persistence infrastructure, deployment or multi-agent product orchestration.
- Implementing M3's judge, calibration, repeated quality campaign or task-benefit study as part of M2.
- Selecting numeric live/model settings without measured inputs, running unspecified paid calls, or claiming live bookability/provider reliability/complete task benefit.

## Further Notes

This spec synthesizes the owner's twenty accepted interview answers and ADR 0026's October 6–7
amendments, while preserving ADR 0027's Ranking-owned export and upstream-trust boundary. It adds
no new owner policy, changes no runtime and records no new behavioral qualification.

Start with offline preparation/rendering/notice/check fixtures on saved Ranking views, then measure
complete model input. Implement bounded writer/recovery/replay after dependent settings are settled;
declare the budget before an actual-authoring diagnostic. M3 remains downstream quality evaluation.
Existing historical campaign arithmetic assumed one writer invocation and must be revised before
an evaluation budget uses optional correction attempts.

Publication is pending project tracker setup. The repository's GitHub Issues feature is enabled,
but no explicit to-spec tracker configuration was found and ready-for-agent is absent from its
labels. Run /setup-matt-pocock-skills to establish the tracker and triage vocabulary; do not silently
substitute another label or invent repository-wide triage policy. The owner confirmed the Results API seam. Once setup
is resolved, publish this spec with ready-for-agent without another design interview.
