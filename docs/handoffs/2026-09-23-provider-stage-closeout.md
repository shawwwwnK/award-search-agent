# Provider Stage closeout

Date: 2026-09-23. Status: **owner-complete for the declared boundary**.

## Owner decision and boundary

After a walkthrough of the Provider Stage workflow and output structure, inspection of the
saved combined `ProviderResultSet` example, and the owner's explicit statement, “Ok I approve
this stage. Mark this stage finish,” the owner accepted Provider Stage as complete on
2026-09-23. The accepted deliverable is the typed, replayable `ProviderResultSet` in
[ADR 0022](../adr/0022-award-first-cash-observations.md#2026-09-22-amendment--provider-stage-boundary)
and the [stage handoff](2026-09-21-award-first-provider-results-plan.md).

Provider Stage consumes the frozen `EffectiveRequest` and complete `CompiledSearchPlan`, executes
bounded Seats.aero award and `gfly` cash acquisitions, and returns source-attributed normalized
observations, evidence references, validation findings, resource usage, and exact completed or
omitted coverage receipts. The full provider-neutral planning graph remains intact. The separate
CLI/API does not change the upstream ADR 0016 request/session boundary.

## Evidence supporting closeout

- The [implementation record](../build-log/2026-09-22-provider-stage-implementation.md) records
  the contracts, adapters, execution policy, offline tests, and earlier stopped capture campaign.
- The [live-gate follow-up](../build-log/2026-09-23-gfly-investigation-and-live-gates.md) records
  the reviewed narrow `gfly` compatibility repair, completed cash contrasts, a fresh combined
  two-provider executor task, and byte-identical offline replay. That combined SFO–BKK task
  produced four award-summary and four priced cash observations. Its result truthfully reports
  `partial`: three completed and 22 omitted coverage units under a deliberately small budget.
- The saved-search corpus at closeout held a combined result reviewed in the owner walkthrough.
  That artifact was retired in the 2026-09-25 [plan-linked corpus refresh](../build-log/2026-09-25-plan-linked-provider-corpus.md);
  the [current corpus](../../evidence/provider-stage/saved-searches/README.md) contains new live
  results. The
  [independent consolidation review](../reviews/2026-09-23-saved-searches-review.md) found no
  blocking artifact-integrity or replay issue.

Closeout verification: the nine scoped Provider Stage unit-test modules passed (60 tests).
The then-current `scripts/provider_saved_searches.py verify` passed and reported 20 Seats.aero captures, six
cash captures, 81 controlled cash observations, eight combined observations, and all 25 combined
coverage units. `git diff --check` passed. During verification, the two combined runtime
response copies were found reformatted with unchanged JSON values. Restoring their canonical
evidence serialization reproduced their original SHA-256 filenames and index digests; no
observation, receipt, result, or planning input was changed.

## Limits and next boundary

Owner completion applies to the declared Provider Stage result contract and its local development
evidence. It does not establish provider reliability, current inventory, booking availability,
traveler or cabin adequacy where the providers did not supply it, or broad market coverage.
The saved combined task's omitted searches are not empty searches. Runtime rectangle batching
remains disabled; the accepted sampled comparison does not imply general batching qualification.

Mixed-journey assembly, candidate admission, ranking, redemption-value calculation, direct-cash
presentation, explanation, and recommendations belong to a separately scoped ranking/output
stage. The owner's Provider Stage acceptance does not itself authorize or complete that later
stage. The remaining claim gates and parked work stay in [DEFERRED.md](../../DEFERRED.md).
