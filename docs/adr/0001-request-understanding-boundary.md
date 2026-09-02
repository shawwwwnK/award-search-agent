# 0001: Request understanding is a typed workflow node, not a general-purpose autonomous agent

- Status: Approved

> Refined by ADR 0003: temporal modifiers are now interpreted in a second model pass that proposes
> direct ranges; deterministic code retains anchor resolution, grounding, exact duration arithmetic,
> conflict checks, and acceptance policy.
>
> Refined by ADR 0006: the second pass now emits semantic temporal relations rather than
> authoritative ranges; deterministic code evaluates all calendar windows.
>
> Refined by ADR 0007: dedicated model-view contracts structurally hide concrete calendar context;
> deterministic catalogs form the trust checkpoint between the two model passes.

## Context

Natural-language interpretation is useful for ambiguous travel requests, but exact date arithmetic, validation, conflict checks, and clarification rules should be reproducible and testable.

## Options

1. One model call parses the request, resolves dates, decides whether to clarify, and creates a search plan.
2. A model performs semantic extraction while deterministic code validates the schema, resolves dates, detects conflicts, and applies clarification policy.

## Decision

Choose option 2 for the first implementation.

## Consequences

- More explicit interfaces.
- More testable behavior.
- Easier failure classification.
- Additional implementation code.
- Search planning remains a separate later responsibility.

## Evaluation

Evaluate using:

- schema validity;
- extraction accuracy;
- unsupported inference count;
- date-resolution tests;
- conflict-detection tests;
- clarification-decision accuracy.

## Revisit trigger

Revisit only if evaluation evidence shows that the deterministic clarification policy cannot represent important conversational context.

Approved by the project owner on 2026-08-30.
