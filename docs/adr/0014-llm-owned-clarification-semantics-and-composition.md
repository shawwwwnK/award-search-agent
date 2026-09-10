# 0014: Let the LLM interpret clarification answers and compose follow-up questions

- Status: Accepted
- Date: 2026-09-10

## Context

The clarification session has a different language requirement from the frozen initial
request-understanding boundary. It must accept ordinary conversational answers, including
typos, paraphrases, corrections, and several independent facts in one message. The current
continuation design mixes that language task into deterministic answer grammar, temporal
normalization, endpoint-cue recovery, and fallback-copy generation. That makes a harmless answer
such as “mid october for depature ... about 12 days” look like a same-field collision instead of
two independently understandable facts.

The system still needs deterministic safety. A model must not be allowed to mutate an effective
request, choose calendar dates authoritatively, hide a conflict, or turn an ambiguous answer into
an invented constraint. The required boundary is therefore not “model versus deterministic code
for every sentence”; it is semantic interpretation versus validation and state reduction.

Follow-up wording has the same separation. The reducer knows which blockers and issue records
remain only after an answer has been interpreted and applied. A model that writes a question
before reduction can be stale or generic, while deterministic copy cannot express the supplied
phrase naturally. The question should be authored by a model after the authoritative issue set
exists.

## Options

1. Expand deterministic answer grammar, typo tables, endpoint heuristics, and copy fallbacks.
2. Let a model return arbitrary request patches and prose, with deterministic code accepting the
   result directly.
3. Let an LLM produce a constrained semantic answer representation, let deterministic code
   validate and reduce it, and call a separate post-reduction LLM composer for the next question.

Choose option 3.

## Decision

### The answer receiver owns raw-answer semantics

For a clarification turn, the receiver LLM is the only component that interprets the raw answer
text. It receives the answer message and its identity, the active typed blocker descriptors, and
an allowlist of supported already-resolved fields that may be corrected. It does not receive the
full session ledger, unrestricted effective state, concrete calendar values, or authority to
change policy.

The receiver returns a typed `ClarificationAnswerSemantics` contract, not a dictionary patch or
customer-facing question. The contract can contain:

- a discourse classification such as answer, correction, conflict, decline/cancel, non-answer,
  or unsupported request;
- zero or more independently targeted amendments, each with an allowed field, operation
  (`set`/`replace`), requirement or correction target, and exact answer-local evidence span;
- closed symbolic temporal semantics for dates, windows, relative periods, and durations, rather
  than model-calculated calendar dates;
- explicit alternatives, ambiguities, conflicts, and unsupported fragments when one bounded
  interpretation is not truthful.

Semantic normalization is model work. The receiver should recognize ordinary spelling errors such
as `depature`, casing and punctuation variation, and natural equivalents without a phrase-specific
deterministic rule. It may return multiple independent facts in one answer. It must not return
arbitrary fields, silently discard an unrelated hard constraint, or convert a disjunction into one
chosen value.

The model may quote a span for grounding, but a span is evidence, not a semantic instruction to
deterministic code. Model output must not contain authoritative resolved dates or unbounded free
form state mutations.

### Deterministic code validates and reduces; it does not parse answer language

Deterministic continuation code has no raw-answer semantic parser, regex candidate harvester,
typo-repair table, endpoint-cue heuristic, numbered-line grammar, or deterministic copy policy.
It may perform only mechanical evidence checks on receiver output, such as message-ID identity,
offset bounds, and exact substring integrity. Those checks do not infer what a span means or which
field it should target.

After mechanical validation, deterministic code remains authoritative for:

- contract and closed-vocabulary validation, including allowed requirement/correction targets;
- compilation of symbolic temporal semantics under the immutable initial request context and all
  calendar arithmetic;
- conflict detection, bounded/nonempty window checks, unsupported-value handling, and full
  blocker recomputation;
- immutable revisions, answer-turn provenance, atomic independent-subset application,
  optimistic concurrency, message-ID idempotency, and preservation of unrelated hard constraints.

An invalid, under-specified, contradictory, or unauthorized model proposal is recorded as an
explicit issue or rejected fragment. It is never repaired by inspecting the raw answer and never
becomes a success-shaped result. The frozen initial boundary remains unchanged:

`raw request -> ParsedRequest -> ClarificationDecision`.

### The post-reduction composer owns clarification copy

After deterministic reduction and blocker recomputation, a separate composer LLM call authors the
initial prompt and every nonterminal follow-up. Its input is limited to the ordered authoritative
blocking requirements and structured `ClarificationIssue` records (including a bounded
answer-local evidence excerpt when needed for specificity). It receives no effective request,
session ledger, concrete calendar context, or state-mutation authority.

The composer returns a structured question set with one natural question item per blocker. Each
item links to exactly one requirement ID and, when applicable, one issue ID. Deterministic code
checks schema validity, complete coverage, canonical order, and linkage. It does not author or
rewrite the question text. Composer copy is never allowed to alter blocker policy or session
state.

If composition fails, times out, or fails structural validation, the semantic transition remains
intact and the caller receives an explicit retryable `prompt_composition_failed` result. The
system does not emit a robotic or generic fallback question. Composition retries are keyed to
the same post-reduction issue signature and are side-effect free; a failed composer call cannot
roll back or duplicate an accepted answer transition.

The normal clarification path therefore has two narrow model calls after an answer: receiver,
then reducer, then composer. The receiver remains independently configurable from the composer.
The initial clarification prompt has no receiver call and is composed from its initial blocker
and issue set.

### Model selection and implementation boundary

The first implementation keeps `gpt-5.6-luna` as the clarification answer receiver. Composer
model selection is an independent experiment: compare Luna with `gpt-4o-mini` using the protocol
in [the clarification acceptance evaluation protocol](../evaluation/clarification-acceptance-evaluation-protocol.md).
No composer result may affect the receiver, reducer, or deterministic safety gates.

Do not introduce LangChain or LangGraph for this boundary. Explicit model protocols, Pydantic
contracts, and deterministic state reduction remain the appropriate implementation shape.

## Supersession

This ADR supersedes ADR 0013 in full. The receiver no longer owns follow-up copy, and there is no
deterministic issue-specific fallback question. It also supersedes the raw-answer semantic parts
of ADR 0011: the clarification-specific temporal grammar, numbered-answer ownership, deterministic
endpoint-cue recovery, and cross-answer text interpretation are retired. ADR 0011 remains
authoritative for immutable session state, all-blocker collection, provenance, atomic reduction,
revision/idempotency behavior, explicit stopping, and the no-framework boundary. ADR 0012 remains
the source for the accepting-behavior intent and property-oriented evaluation, as refined here.

## Consequences

- Ordinary clarification language, including spelling mistakes and mixed corrections plus new
  answers, can be represented without a growing deterministic phrase grammar.
- The trust boundary is easier to audit: the model proposes typed semantics; deterministic code
  validates, evaluates, reduces, and recomputes.
- Follow-up questions can be specific to the authoritative remaining issue set and can quote a
  supplied phrase without becoming policy.
- Clarification generally costs a receiver call and a composer call. Composer latency and model
  choice are measured independently rather than hidden in semantic correctness.
- Composer outages produce an explicit retryable error rather than misleading copy. The accepted
  semantic transition is retained and remains idempotently recoverable.
- Unit tests can prove contracts, grounding, arithmetic, reduction, and safety without pretending
  that a hand-written phrase golden is a language-understanding oracle.

## Evaluation

Use the separate evaluation protocol linked above. The hard offline guardrail gate must remain
100% for schema/grounding, allowed mutation, symbolic temporal compilation and arithmetic,
conflict handling, atomicity, provenance, revision/idempotency, privacy, blocker coverage, and
ready-state policy. It must include a negative check that deterministic continuation code does not
semantically parse raw answer text.

Receiver behavior is evaluated on disclosed development data, a locked external holdout, and a
rotating post-freeze challenge set. Behavioral qualification measures acceptance of ordinary
language and typos, false blocking, incorrect acceptance, valid-sibling retention, assumption
disclosure, conflict preservation, and convergence; it does not require one exact fuzzy range or
one exact sentence. Composer qualification separately measures complete ordered coverage,
issue-specificity, naturalness, invalid-output rate, generic-repeat rate, latency, and token
cost. Human review remains authoritative for naturalness and materially surprising assumptions.

## Revisit trigger

Revisit this boundary if holdout evidence shows that the typed semantic contract cannot represent
important clarification patterns, if the receiver repeatedly proposes unsafe or ungrounded
semantics despite validation, if composer failures materially prevent continuation, or if the
two-call latency cannot meet the owner-approved product budget after the preregistered model
experiment.
