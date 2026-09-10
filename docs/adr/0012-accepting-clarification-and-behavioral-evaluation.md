# 0012: Make clarification accepting and evaluate user friction separately from safety

- Status: Accepted

## Context

The frozen initial request-understanding workflow intentionally uses conservative semantic
extraction. It must not invent hard travel constraints from an unstructured first request.
The iterative clarification session has a different job: help a user turn a partly specified,
already-grounded trip into a usable `EffectiveRequest` through a natural conversation.

The current continuation implementation has safe state and provenance behavior, but its language
policy is too narrow for that job. A reasonable answer can be rejected solely because its temporal
wording does not fit the small supported grammar. In particular, a response such as “early next
month for a week” can leave both date requirements blocked. The current answer interpreter may
also propose follow-up copy before deterministic reduction, but the controller discards that copy
when a fragment is rejected—the precise case in which a targeted follow-up would help most. The
generic fallback then repeats the original question rather than addressing the supplied wording.

The existing exact offline and live continuation corpora remain valuable evidence of reducer and
controller correctness. They are not, by themselves, an adequate optimization target for a
conversation that must accept varied ordinary language. Exact per-fixture projections and literal
protected phrases can reward matching known examples while hiding false blocking and unnatural
re-asks.

## Options

1. Keep strict continuation grammar and generic deterministic fallbacks.
2. Accept arbitrary model-authored values and prompts without deterministic validation.
3. Keep deterministic state/safety ownership, add a post-reduction prompt-composer boundary, and
   accept grounded natural-language interpretations that compile to approved bounded semantics.

## Decision

Choose option 3.

Clarification is intentionally more accepting than the frozen intent stage. When a response is
reasonably interpretable as one continuous, bounded constraint, the session should move forward
with a visible, traceable approximation instead of rejecting the response merely because it does
not use a narrow canonical phrase. An accepted approximation is an explicit answer-derived
assumption, never a silently invented exact fact.

The answer interpreter may recognize open-ended surface language, but must map it to a closed set
of symbolic temporal semantics. Deterministic code validates grounding and ownership, calculates
all calendar values, and requires every resulting date window to be bounded, nonempty, and valid.
The first implementation must support natural equivalents of a month and its early/middle/late
portion, along with ordinary duration forms such as “a week,” “one week,” and “about a week.” The
exact configured envelope for each fuzzy portion must be documented, versioned, and retained with
the answer span and chosen interpretation. It must be visible to the user as an assumption.

This latitude does not apply to material choices that cannot be represented truthfully by one
bounded window: discrete alternatives (for example, “October 3 or October 10”), contradictory
facts, unresolved endpoint ownership, and unsupported revisions remain blocking. The system asks
about that specific issue instead of inventing a resolution.

Prompt composition becomes a separate, post-reduction model boundary. After an answer is
deterministically interpreted, validated, reduced, and re-evaluated, the controller derives
authoritative issue records for each remaining requirement: `missing`, `ambiguous`, `unsupported`,
or `conflict`. Each issue optionally includes the exact answer-local span and a stable reason code.
The composer receives only the ordered active requirements and these issue records; it does not
receive the effective request, session ledger, concrete calendar context, or authority to alter
state. It returns structured question items linked to requirement and issue IDs. Deterministic
validation requires complete, ordered blocker coverage and issue linkage. The composer is used for
the initial prompt and each nonterminal follow-up.

If composition fails validation or the model call fails, the semantic answer transition remains
committed and a deterministic **issue-specific** fallback is rendered. A rejection-driven
follow-up must identify the unresolved phrase or decision; it must not simply repeat the original
generic question.

Evaluation separates exact safety conformance from flexible behavioral quality:

- Exact conformance remains a 100% gate for snapshot immutability, grounding, authorized-field
  mutation, calendar arithmetic after interpretation, bounded date windows, state/revision
  behavior, ready-state policy, privacy/redaction, and explicit handling of genuine conflicts.
- Behavioral qualification uses acceptable properties and actions rather than a single golden
  phrase or exact fuzzy range. It measures false blocking, unnecessary clarification, turns to
  ready, valid-sibling retention, assumption disclosure, materially incorrect assumptions,
  targeted-question quality, generic-repeat rate, and paraphrase consistency.
- A disclosed development set, locked private holdout, and rotating semantic challenge set limit
  corpus overfitting. Newly exposed holdout cases become regressions and are replaced.
- Human review is authoritative while the rubric is calibrated. An LLM judge may assist with
  naturalness and specificity only after calibration, and never overrides a deterministic safety
  failure.

The false-blocking rate and materially incorrect-assumption rate must be reported separately;
neither may be hidden inside terminal correctness. Behavioral scores begin as trend and diagnostic
measures. Release thresholds are set only after a baseline is measured and the project owner
reviews the tradeoff.

## Consequences

- A reasonable answer such as “early next month for a week” can resolve required dates with an
  explicit bounded assumption, rather than consuming a no-progress turn.
- A necessary question can quote or name the actual unresolved phrase and request the missing
  decision, while typed requirement IDs remain the authoritative coverage contract.
- The clarification path incurs one additional model call whenever it needs a prompt. The model
  boundaries remain narrow and separately traceable.
- Existing exact corpora remain conformance evidence and historical qualification artifacts; they
  are not rewritten or used as the sole proof of user experience.
- The frozen initial parser, selector, temporal compiler, and ready corpus remain unchanged.
- This supersedes the ADR 0011 restrictions that model follow-up copy must originate in the
  answer-interpreter call, that any rejected fragment forces a generic fallback, and that no
  second prompt-composition call is made. ADR 0011's immutable session, provenance, deterministic
  reduction, and all-blockers requirements remain in force.

## Evaluation

The behavioral v2 corpus must classify each answer as reasonably resolvable, safely assumable,
materially ambiguous, conflicting, non-answer, or correction. Its oracle specifies required
resolutions, protected fields, acceptable actions and interpretation properties, disclosure
requirements, and forbidden outcomes; it does not require one sentence or one arbitrary fuzzy
date range. Paired boundary cases and metamorphic variants must prevent an accept-everything
strategy.

Public reports include the model and evaluator versions, corpus/holdout hashes, scenario-family
distribution, exact conformance results, behavioral metrics by slice, variance, calls, latency,
tokens, errors, and stop reasons. Private model traces remain gitignored and redacted public
artifacts contain no raw answer text or model payloads.

## Revisit trigger

Revisit the symbolic approximation policy if human review finds that its visible assumptions are
regularly surprising, if false blocking remains high, or if product needs require truthful
representation of disjoint alternatives rather than targeted clarification. Revisit behavioral
thresholds after baseline and holdout evidence is available, not merely because an existing
fixture passes or fails.
