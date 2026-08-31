# 0003: Use two model passes around grounded temporal anchors

- Status: Approved

## Context

The original request-understanding contract required the semantic extractor to select a detailed
date-expression kind and populate kind-dependent components. Structured Outputs enforced the flat
JSON shape but could not enforce the Pydantic validator's conditional component requirements.
Normal requests such as “early May,” “in October,” and “after New Year” therefore failed before
deterministic date resolution began.

The detailed expression vocabulary also made the model translate ordinary language into resolver
implementation operations too early. The project owner requested a coarser first pass, deterministic
holiday-anchor enrichment, and a second model pass that proposes direct date ranges.

## Options

1. Keep the single model pass and continue expanding the detailed date-expression DSL and prompt.
2. Use a coarse first pass, resolve explicit anchors, then let a second model pass propose direct
   ranges without deterministic validation.
3. Use the same two model passes, with deterministic grounding checks, clarification policy, and
   exact return-window arithmetic around the second proposal.

## Decision

Choose option 3.

The first model pass emits non-temporal request semantics plus:

- kind-specific exact-date, month, and holiday anchors;
- verbatim temporal phrases for offsets, alternatives, approximations, durations, weekdays,
  weekends, and boundaries.

Deterministic enrichment removes unsupported inferred years, selects the next occurrence of
yearless exact/month anchors, and resolves holiday dates through `HolidayDateProvider` with source
metadata.

The second model pass receives the raw request, coarse extraction, reference-date context, and
resolved anchors. It proposes inclusive departure and return ranges, interpreted duration bounds,
supporting spans, assumptions, and unresolved constraints.

Holiday wording uses a versioned product policy. The model preserves the semantic distinction;
deterministic code calculates and enforces the resulting calendar boundaries:

- “holiday weekend” includes the provider-supplied holiday, its associated adjacent Saturday-Sunday
  weekend, and the day immediately before that combined span. This makes a Monday Labor Day window
  run from Friday through Monday and preserves late-Friday departure options;
- “over Christmas” without “weekend” runs from Christmas Eve through the day after Christmas.

These ranges are inclusive. The distinction preserves the golden expectations for both explicit
holiday-weekend wording and the broader colloquial Christmas period.

Deterministic code then:

- rejects authoritative windows whose supporting text is absent from the request;
- rejects dates when the request has no temporal evidence;
- filters ungrounded unresolved annotations;
- calculates authoritative windows for recognized holiday-weekend and “over Christmas” wording;
- preserves unbounded holiday-relative departure wording for clarification;
- calculates return-window bounds from the model-interpreted duration and proposed departure
  window;
- checks date ordering and conflicts before clarification policy runs.

The detailed `DateExpression` resolver remains temporarily for isolated legacy component tests but
is no longer used by the production `understand_request` path.

## Relationship to earlier decisions

This ADR refines ADR 0001 and ADR 0002. Semantic interpretation of temporal modifiers and the first
direct date-range proposal belong to the model. Deterministic code retains explicit-anchor
resolution, recognized holiday-window and duration arithmetic, grounding checks, conflicts, and
final acceptance policy. An authoritative deterministic holiday window supersedes the model's
proposed boundary while retaining grounded evidence and trace assumptions.

Search planning, provider search, airport expansion, and ranking remain out of scope.

## Consequences

- Ordinary temporal language no longer needs to fit a detailed expression DSL in the first pass.
- Model-dependent behavior remains behind the narrow `IntentExtractor` and `TemporalResolver`
  interfaces.
- Each request uses two model calls, increasing latency and model cost.
- Direct range semantics can vary by model, so interpretation policies and live regression cases
  must be versioned and evaluated.
- Holiday requests still depend on the injected holiday provider; offline tests use fakes.
- The parsed output retains anchor provenance, proposal assumptions, and unresolved constraints.

## Evaluation

Maintain offline tests for enrichment, grounding, duration arithmetic, conflicts, and clarification.
Run the live model against both the existing golden corpus and the four initial failures:

- early month with approximate duration;
- unbounded travel after New Year with duration alternatives;
- whole-month departure with an exact duration;
- tentative city preference and month without return timing.

Measure schema validity, range correctness, unsupported inference, clarification accuracy, repeated
run stability, latency, and model cost. Do not infer aggregate quality from a single successful run.

## Revisit trigger

Revisit if live evaluation shows unacceptable semantic variability, cost, or latency; if grounding
checks cannot distinguish assumptions from hard constraints; or if the legacy expression resolver
can be removed after migration.

Approved by the project owner on 2026-08-30.
