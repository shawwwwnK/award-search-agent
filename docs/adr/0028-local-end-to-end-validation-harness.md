# ADR 0028: Local end-to-end validation harness

- Status: Accepted
- Decision and recording date: 2026-10-08
- Source: owner's request to update Streamlit for end-to-end intent-to-Results testing.

## Context

The existing harness stopped after clarification. Planning, Provider, Ranking and Results
now expose local APIs, so the owner requested testing the complete workflow from that harness.
ADR 0011 and `AGENTS.md` previously excluded provider calls from the experimental UI.

## Options

Keep the clarification-only surface and require separate CLI invocations, or extend the
local harness to explicitly invoke existing stage APIs through an application module.
The owner's request selects the latter. These are engineering alternatives, not inferred
owner claims about product usefulness.

## Decision

Permit explicit local harness events to trigger bounded travel-provider acquisition through
`award_agent.harness.pipeline`. That module connects a ready immutable clarification revision
to M2A/M2B/M2C, Provider, Ranking matching/styles/export and Results. UI rendering does not
invoke network calls. The harness also supports saved provider replay and frozen Results drafts.
Saved runs are labeled historical and never silently attached to the current request.

Retain artifacts in ephemeral Streamlit session state; provider response capture uses temporary
local files with downloadable replay evidence. Downloads are an explicit owner action, not an
application persistence service. A changed session ID, revision or effective-request digest
invalidates the displayed downstream run. Each new stage invocation clears dependent output.
Stage failure preserves already completed stages for inspection and explicit retry.

Existing policies own eligibility, planning, acquisition budgets, valuation and Results checks.
Results model/token/time settings are visible editable run inputs; initial values mirror the
October 8 diagnostic and do not establish a newly adopted model policy.

## Consequences and supersession

This supersedes only ADR 0011's and `AGENTS.md`'s exclusion of provider calls from the local
validation harness. Calls remain outside the UI layer and require explicit run events.
No production UI, authentication, deployment, durable session service, automatic rerun calls,
adaptive controller or upstream scope expansion is introduced.

## Evaluation

Offline verification covers revision invalidation, explicit-event execution, provider replay,
ranking and Results integration. See the [build log](../build-log/2026-10-08-end-to-end-harness.md).
Implementation tests do not establish live full-workflow reliability, owner qualification,
bookability or traveler-task benefit. No paid/model/provider calls are needed for verification.

## Revisit trigger

Revisit before adding durable sessions, concurrent execution, automated retries, production UI
or a controller that chooses new work based on provider outcomes.
