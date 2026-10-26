# Results M2 complete-answer composition correction

Date: 2026-10-25. Status: owner-agreed requirements; implementation and live review invoked.
Source: current owner interview Q1–Q5 and explicit implement/subagent/code-review/live-iteration instruction.
Starting commit: `4d951d52d9cae26525f8c2922f0f617321401d25`.

## Accepted goal and ownership

Results supplies one complete, naturally flowing LLM-authored answer. It highlights
meaningful exact options informed by Ranking, explains them individually, discusses
relevant alternatives, and connects those explanations into an overall comparison.
Compact journey cards occur inside that explanation. The cash search supplies a
baseline. Limitations are consolidated into a readable passage identifying affected
options. The frontend supplies the complete independent explorer at the end.
These responsibilities are not a mandatory section order, paragraph count,
recommendation count or cabin/style quota.

Ranking highlights are the starting point; Results may choose another eligible
exact option with an explicit supported rationale. Ranking policy and upstream
trust remain unchanged. Internally admitted and conditional journeys share one
eligible pool. Incomplete leads and cash benchmarks retain their distinct meanings.

The model owns final words, order, emphasis, selections and comparative prose.
The owner explicitly accepts model-written numerical prose for now: do not add an
inline-value/reference span contract. Code continues to resolve exact card facts,
validate reference/selection association and check existing declared claim families.
Those checks do not verify arbitrary narrative values or semantic composition.
Cards support the answer; a frontend cannot repair disconnected authored text.

## Alternatives and decision

A runtime agent per recommendation plus a synthesizer was suggested as a means,
not a requirement. Investigation found the schema does not require one paragraph/card
per option, and a synthesizer would still own whole-answer composition. Start with
one composer and a clear whole-answer brief. No runtime multi-agent orchestration,
new Ranking policy or frontend implementation is opened here.

A narrow inline-fact contract was considered and declined for this correction.
The existing ordered narrative/reference contract can represent the accepted goal.
The owner permits intentional development compatibility breaks; preserve original
evidence and document any changed replay behavior instead of making compatibility
the design constraint. Historical V1–V5 paths remain out of scope.

## Implementation and verification

1. Replace the structured base composition brief, retaining source/date/airport,
   eligibility, quote-scope, separate-booking and incomplete-lead safeguards.
2. Keep typed exact references, deterministic facts and bounded recovery unchanged.
   Test composed-document preservation through existing U3 prepare/run/resolve/replay
   seams. Fake writers or prompt assertions do not prove live composition quality.
3. Extend the existing offline-default saved-case runner to select a new campaign
   directory with isolated immutable ledgers and exact requests/receipts/snapshots.
4. Run independent Standards and Spec code reviews; fix material findings.
5. Run the complete admitted/conditional/incomplete live authoring cohort over the
   original saved projections. Independently review narrative AND source facts.
   Iterate observed failures, retaining every attempt and review disposition.
   Finish with a complete cohort under the final shared configuration.
6. Run scoped tests/types during implementation, then the full repository suite
   once runtime settles. Audit new-artifact replay in fresh processes and record
   original-artifact compatibility without modifying original evidence.
7. Update ADR/index, project state, usage, deferred-register disposition and build
   log; commit current-branch changes within this task only.

## Live campaign and review boundary

The owner authorizes full saved-case live runs and evidence-driven iteration.
New evidence: `evidence/results-stage/m2/structured/2026-10-25-composition-luna/`.
Use previously evaluated explicit Luna numerical settings, not an implicit default.
The initial operational envelope is three rounds, at most 18 generations and 18
input counts, with one initial generation and at most one mechanical correction
per run. No automatic API retries, provider searches or FX refreshes. A necessary
extension must be recorded before calls; owner iteration authorization remains the
authority, not unused historical campaign budget.

Review each answer for connected argument, individual option usefulness,
Ranking-informed meaningful choice, embedded references, relevant alternatives,
cash context, consolidated applicable limitations, and factual/date/price fidelity.
The empty-eligible case must truthfully explain the absence of complete options,
using supported leads without inventing missing connections. Do not require highlights
from an empty pool. Mechanically clean output can still fail narrative/source review.

Stop after a final complete cohort has no unresolved material composition or factual
defect found in independent review, plus the declared engineering checks. This is
scoped development evidence. Owner presentation acceptance, frontend rendering,
Results M3 qualification and traveler task benefit remain separate and unclaimed.

## Evidence-driven input refinement

Round-one and round-two review found repeated lead prose/alias contradictions despite
clean checks. The third iteration adds a compact identity beside every incomplete
lead alias in structured preparation only. Identity is copied from existing exact
component-group member facts (route/date/program/cabin/points/scope and cash fields),
preserving state/value and all lead rows, order, aliases and full evidence. This is
an input ergonomics experiment, not an output restriction or semantic verifier.
Shared historical compact authoring is unchanged. Source-fidelity and new replay
controls are required before the next live cohort. The prior outputs remain evidence
of failures, not overwritten drafts. No broader architecture or milestone changes.

## Recorded live envelope extension

After three cohorts, independent review still found material admitted selection and
exact-time association errors and a conditional opening contrast needing correction.
The owner-authorized iteration therefore extends the operational envelope to four
rounds, at most 24 generations/24 input counts (two per run maximum). The initial
campaign and dated extension are preserved in the new evidence directory before
round-four calls. No provider, FX, frontend or model scope is added. Fourteen
generations/counts had been used at extension time.

## Stronger-composer comparison

Four Luna cohorts did not meet the complete-answer boundary. Before more prompt
changes, an architect recommended testing one stronger composer on the same current
input/brief/contract. `2026-10-25-composition-sol/campaign.json` records GPT-6.1 Sol,
at most two rounds/12 generations+12 input counts. Run admitted first and independently
review it before completing that same-config cohort. This fits the owner's current
live-iteration authority, not historical unused budget; no global default or broad
model qualification follows. The final complete cohort passed both independent reviews. Code and source remain
identical to Luna round4. See the final evidence linked below.

## Execution disposition

Implemented and independently code-reviewed; Standards 0 findings, Spec 0 findings.
Four Luna cohorts remain failed development evidence. The complete same-code/input/
brief Sol cohort meets the agreed composition target in bounded source-backed review.
[Final answers/configuration](../../evidence/results-stage/m2/structured/2026-10-25-composition-sol/README.md)
and [build log](../build-log/2026-10-25-results-m2-composition-correction.md) preserve
all attempts, review limitations, exact counts and commands. Total session: 15 runs,
22 generations and 22 counts, with no new provider search or FX refresh. Final replay
9/9, all archived-source replays 45/45; full suite 931 passed, 99 skipped, 2 unchanged
gfly environment failures. Owner presentation acceptance, frontend and M3 remain open.

## Subsequent latency disposition

The owner rejected the measured request-to-full-response delay as too long. The
composition result above is scoped to content quality; it does not qualify interactive
latency. See the [latency gap and proposed investigation](2026-10-25-results-m2-latency-investigation.md).
Smaller writer context, lower reasoning and first-token/full-answer measurement remain
proposals, with no new implementation, numeric target or paid campaign invoked.
Milestone sequence, canonical facts, full eligible selection and explorer guarantees
are unchanged. This latency issue remains open for interactive readiness.
