# 0017: Use LLM-owned initial intent semantics with deterministic validation

- Status: Accepted
- Date: 2026-09-11

## Context

The live initial request-understanding path currently combines a non-temporal model extraction
with a deterministic temporal scanner and an opaque temporal selector. The scanner recognizes
surface phrases in `RawRequest.text`, so a typo, a new but reasonable paraphrase, or a supported
calendar meaning expressed in an unfamiliar way can fail before the deterministic calendar
evaluator receives a meaningful representation. Adding another regular expression or candidate
group would make the set of accepted English expressions the accidental product boundary.

The clarification boundary has established a safer division of responsibility. A model reads raw
language and emits grounded, typed semantic material. Deterministic code validates that material,
performs calendar arithmetic, preserves ambiguity and conflicts, and decides whether the request
is ready, needs clarification, or is unsupported. The same division is needed for the initial
request, while retaining the one-way award boundary in ADR 0016.

The initial stage must also distinguish a reasonable user request from a system or model-contract
failure. A user typo or understandable paraphrase is not an exception. An ambiguous, incomplete,
conflicting, or genuinely unbounded request should reach clarification. Recognized return/trip-
duration and cash-only intent should receive the explicit unsupported outcome required by ADR
0016. Only a genuine preflight, authentication/configuration, network/transport, or provider
operational failure may become a pending/retryable outcome. A model-result contract, grounding,
or shape failure is never pending; after its bounded repair it completes as clarification with
the independently salvaged facts and explicit blockers.

## Options

1. Keep deterministic raw-text scanning and extend its phrase catalog as new language appears.
2. Keep the selector-only path and let the model choose from a larger deterministic candidate
   catalog.
3. Use one initial-intent model receiver for all raw-language semantics, emit generic typed
   calendar operations and grounded facts, and let deterministic code validate, evaluate, and
   assemble the request.

Choose option 3.

## Decision

### One model receiver owns initial-language interpretation

The live workflow has one semantic receiver for the initial request:

```text
RawRequest
  -> InitialIntentInterpreter
  -> deterministic grounding, validation, and calendar evaluation
  -> ParsedRequest
  -> ClarificationDecision
```

The receiver is the only component allowed to interpret the raw request's language. It extracts
locations as resolver candidates, traveler information, cabin and award/cash intent, supported
outbound timing semantics, recognized unsupported return/duration intent, and ambiguity or
conflict evidence. It must not expand a city into airports, call travel providers, calculate and
authoritatively submit final dates, choose the clarification authority, or return a state patch or
customer-facing clarification copy.

The internal receiver contract is provider-independent and versioned. It contains typed facts,
exact source quotes with occurrences, and generic temporal calculation proposals. A provider
adapter may use a flatter wire schema for structured-output compatibility, but its translation is
structural and must not inspect raw text to recover meaning. Every accepted fact is grounded to
the original request by deterministic evidence resolution; a model assertion without a valid
source span is not silently accepted.

### Generic semantic operations, not a phrase grammar

Temporal meaning is represented as a small generic operation algebra rather than a catalog of
English constructions. The receiver may express, subject to the contract, a literal interval,
an interval anchored to a named calendar event or calendar period, a recurring interval, an
offset or composition from an anchor/fact, a bounded interval, or an explicitly unresolved or
unsupported temporal fact. Operations may reference only immutable request context or another
fact in the same response through an opaque fact ID. References must form an acyclic graph.

The receiver decides how a phrase maps to an operation. Deterministic code does not recognize,
rewrite, normalize, or special-case the words that produced it. This includes typos and
unfamiliar-but-understandable expressions. For example, a misspelled holiday or a paraphrase of a
weekday relation can be accepted when the receiver maps it to a supported grounded operation;
the evaluator then checks the resulting bounded date envelope and not the receiver's internal
spelling.

Generic operations are calculations, not a second language parser. Deterministic code may:

- resolve exact source evidence and occurrence numbers;
- validate schemas, fact references, anchor kinds, authority, conflicts, boundedness, and
  dependency topology;
- evaluate operations against immutable reference context and the holiday-date provider;
- reject impossible, empty, cyclic, ungrounded, or otherwise unsafe calculations;
- preserve unknowns and conflicts and construct the existing temporal relation graph where it is
  compatible with the new contract; and
- produce the canonical outbound window, provenance, and `ClarificationDecision`.

It may not scan the request for temporal phrases, repair a quote semantically, infer a missing
operation from the raw wording, or treat a model-calculated concrete date as authoritative.

### One-way award policy remains deterministic

ADR 0016 remains the active product boundary. A ready request has only:

- origin;
- destination;
- a bounded, non-empty outbound departure window; and
- traveler count.

Cabin and repositioning remain nonblocking. A recognized return date or trip duration is retained
as grounded semantic evidence and produces the stable separate-one-way guidance. It never becomes
active request/session state, a return field, a duration field, or a missing-information blocker.
A cash-only request produces an explicit unsupported/invalid outcome. A mixed award-and-cash request
may proceed for its award portion, without implying that cash prices or cash search are available.

The deterministic policy layer—not the receiver—decides these state and product consequences. No
outbound subset is silently accepted in place of a recognized unsupported return request, and no
hard constraint is invented to make a request ready.

### User-language outcomes and bounded repair

The initial workflow has four externally meaningful outcomes:

- `ready`: the required one-way award facts are grounded, valid, and executable;
- `clarification`: one or more missing, ambiguous, conflicting, or otherwise user-resolvable
  blockers are preserved and enumerated deterministically;
- `unsupported`: recognized return/duration scope or cash-only intent receives explicit guidance;
  and
- `pending_retryable`: a genuine preflight, authentication/configuration, network/transport, or
  provider operational failure prevented completion, without mutating the request. A model-result
  contract, grounding, or representation failure is not this outcome.

The first three are normal request outcomes. A reasonable user input must never surface as a raw
exception or `pending_retryable`, including when it contains a typo, recognizable paraphrase, or
provider-wire representation/shape noise. The receiver and adapter must internally normalize and
repair that ordinary input into `ready`, `clarification`, or `unsupported` according to its
grounded meaning. `pending_retryable` is reserved for a genuine preflight,
authentication/configuration, network/transport, or provider operational failure; it is never a
fallback for ordinary language, representation variance, or an inference-reached model result
that remains unusable after repair.

If deterministic validation or calculation rejects a model result, the workflow may make exactly
one shared model-owned repair call. The repair receives the original permitted receiver input,
the rejected typed result, and structured validation errors. It may preserve valid independent
facts and revise only the rejected semantic material. It cannot add a raw-text parser, alter the
original request, or widen model authority. There is one repair budget across schema, grounding,
semantic, graph, and calendar failures—not one attempt per field.

If the repaired result is still unusable, the workflow completes as `clarification`, retaining
independently valid facts and converting the rejected or unresolved required components into
explicit deterministic blockers. It must not become `ready`, invent a date, silently fall back to
a scanner or selector, or discard valid siblings. A provider schema rejection before inference is
an adapter/preflight pending outcome and does not consume the semantic repair budget; retrying the
identical rejected schema is not a semantic retry. A provider, authentication/configuration,
network, or transport failure may remain `pending_retryable` because no usable semantic result was
available; this is the only pending path.
The local harness preserves the original request and deterministic context, shows only a stable
stage/code status, and offers an explicit user-triggered initial-interpretation retry without
creating a clarification session or displaying raw provider/validation detail.

### No live scanner, selector, fallback, or strategy switch

The receiver/evaluator path above is the sole live initial workflow. The deterministic raw-text
temporal scanner and its candidate compiler are retired from live intent semantics. The opaque
temporal selector, selector-only strategy, sequential temporal resolver, and any scanner,
selector, or legacy fallback are not runtime alternatives. There is no runtime strategy switch.

Historical implementations, fixtures, artifacts, and scores remain available as historical
evidence, but they do not qualify this contract and must not be presented as evidence for it.
Deterministic calendar evaluation, evidence validation, conflict handling, clarification policy,
and immutable-state guarantees are retained where their contracts are compatible with this ADR.

## Consequences

- Ordinary language can be extended through model/schema and generic-operation support without
  adding phrase-specific deterministic branches.
- The model boundary becomes broader, so evidence grounding, typed validation, and repair
  attribution are more important than a single terminal parser score.
- Calendar arithmetic, boundedness, conflict detection, state policy, and provenance remain
  auditable deterministic behavior.
- A repair call adds bounded latency and cost. A genuine operational failure is visibly retryable
  and non-mutating. An inference-reached model/representation failure instead completes as
  clarification with salvaged facts and explicit blockers. Ordinary reasonable language and
  representation noise therefore remain normal outcomes.
- The provider adapter and generated-schema version/hash must be recorded in traces so preflight
  failures are separated from semantic behavior.
- The existing initial contracts, prompts, tests, corpora, evaluator, and configuration require a
  coordinated replacement. They must not preserve a hidden scanner/selector fallback for
  compatibility.

## Implementation plan

1. Define and version the provider-independent initial interpretation contract, including typed
   facts, grounded evidence, generic temporal operations, unsupported targets, repair errors, and
   clarification salvage behavior.
2. Add the provider-specific structured-output adapter and schema smoke. Keep its translation
   structural and record adapter/schema versions and hashes.
3. Reuse or adapt the deterministic evidence, graph, calendar, conflict, one-way policy, and
   clarification machinery. Add exhaustive validation for references, cycles, bounds, empty
   windows, and immutable reduction.
4. Replace the initial workflow atomically with the single receiver plus deterministic evaluator.
   Remove live scanner/selector construction, strategy switches, and fallback paths.
5. Add fake-typed-output offline tests and the action/property evaluator in the companion
   acceptance protocol. Add bounded live evaluation only after the offline hard gate passes.
6. Have an independent architecture review inspect implementation traces and safety properties;
   revise the contract only through a new version and re-run the offline gate.

## Evaluation

Use [the intent acceptance evaluation protocol](../evaluation/intent-acceptance-evaluation-protocol.md).
The hard offline gate is 100% for deterministic safety and boundary invariants. It covers
evidence grounding, operation validation and calendar arithmetic, one-way non-mutation,
clarification blocker completeness, cash policy, repair limits, clarification salvage, operational
pending behavior, privacy, and the absence of raw-text semantic parsing or live fallback paths.

Live evaluation uses a disclosed development baseline, a locked external holdout, and rotating
post-freeze metamorphic challenges. It reports semantic diagnosis, behavioral action/property
success, safety violations, and operational/repair outcomes as distinct dimensions. It records
first-pass, repaired, clarification-after-repair, operational-pending, provider-preflight, and
inference-reached outcomes separately.
Behavioral thresholds are owner-approved and preregistered after a non-vacuous baseline; no
diagnostic development score is silently promoted to qualification.

## Supersession

This ADR supersedes ADR 0010's selector-only initial request-understanding decision and its live
selector requirement. It supersedes the raw-request scanner and scanner-authored temporal
candidate portions of ADR 0009. It also supersedes any earlier live two-pass or selector runtime
choice for initial intent. Historical evidence and deterministic calendar/evidence ownership from
those ADRs remain useful where not contradicted here.

ADR 0016 remains authoritative for the one-way award-only product boundary. ADRs 0014 and 0015
remain authoritative for clarification-answer receiver/composer separation, generic calendar
proposals, grounding, repair, immutable state, and pending semantics where their scope is
clarification rather than initial intent.

## Revisit trigger

Revisit this decision if the generic operation algebra cannot represent a recurring supported
intent, if ordinary understandable language repeatedly reaches a raw exception or pending rather
than a normal user outcome, if one repair is insufficient to salvage a clarification for a
demonstrated contract failure, or if an independent holdout exposes unsafe acceptance, ungrounded
state, or materially surprising one-way behavior.
