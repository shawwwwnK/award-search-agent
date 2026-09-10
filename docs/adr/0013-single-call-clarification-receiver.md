# 0013: Return follow-up copy from the clarification receiver

- Status: Accepted
- Date: 2026-09-10

## Context

ADR 0012 introduced a separate post-reduction prompt-composer model call. It
made issue-specific prose possible, but adds a second sequential model request
after every nonterminal clarification answer. The project owner rejected that
latency cost.

## Decision

The answer receiver is the sole model call for a processed clarification
answer. Its structured response may include one ordered question item for each
requirement it expects to remain unresolved. The initial prompt is
deterministic because there is no prior receiver response.

After deterministic grounding, validation, reduction, and blocker
recomputation, the controller renders receiver-provided items only when their
ordered requirement IDs exactly equal the authoritative remaining blockers.
Otherwise it renders the existing deterministic issue-specific fallback. The
receiver's copy never changes state, blocker policy, issue records, or the
acceptance of an answer.

The continuation normalizer also accepts two exact date facts joined by one
`and` or `then` as an ordered answer to the active departure and
return/duration questions. It still rejects alternatives, extra facts,
cross-sentence pairings, and swapped endpoint targets.

## Consequences

- A nonterminal answer uses one model call, not two.
- A response such as `10/25 and 11/1` can resolve departure then return when
  the receiver returns two narrow, correctly targeted date amendments. If it
  conservatively rejects that exact closed grammar instead, deterministic
  recovery derives the same two answer-grounded amendments.
- A bad or incomplete predicted follow-up safely degrades to deterministic
  issue-specific copy; it does not trigger another model request.
- This supersedes ADR 0012's separate prompt-composer runtime boundary. The
  composer contracts and historical qualification artifacts remain retained
  evidence, but are not invoked by the controller or local harness.
