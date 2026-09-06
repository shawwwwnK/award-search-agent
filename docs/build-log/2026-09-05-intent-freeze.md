# 2026-09-05: Request-understanding implementation freeze

## Objective evidence

- The project owner froze further request-understanding implementation and live-evaluation
  follow-up for now. No source behavior changed in this documentation session.
- The initial freeze ready-corpus artifact completed 48 Luna compiler-selector records: 44 passed
  and 4 failed, with zero errors, repairs, Pass-1 boundary failures, selector failures, Pass-2
  wire failures, or grounding failures. This is an initial historical milestone; the final
  qualification record is appended below.
- A dedicated handoff records the raw request, Pass-1 output, relevant evaluated output, expected
  output, and failure explanation for each of the four records:
  [intent freeze handoff](../handoffs/2026-09-05-intent-freeze-handoff.md).
- The four failures are two repeats of tentative São Paulo handling, one false San Jose origin
  ambiguity, and one adversarial request that omitted traveler and first-cabin extraction.

## Commands and tests

- Documentation review only; no automated test suite was run.
- `git diff --check` — passed.

## Owner decision

- Initial decision: freeze request-understanding implementation for now. Reopen only with an
  explicit owner request. The 44/48 record above is preserved as the initial freeze milestone,
  not the final qualification result.

## Final owner conclusion (2026-09-06)

- Request-understanding implementation is complete and frozen. The selector-only Luna path is the
  sole live path; sequential two-pass resolution is retired from the live code path and
  configuration.
- The final qualification artifact is
  `evals/intent/baseline/2026-09-06-gpt-5.6-luna-selector-only-prompt-repair-3-trials.json`.
  It passed 47/48 records (97.92%) over three trials, with 90 calls, zero errors, zero Pass-1,
  selector, grounding, semantic, or deterministic-output failures, and one clarification miss:
  `repositioning_allowed` asked for `origin` rather than `departure`.
- Its 48 all-call trace sidecars remain private/local under `evals/intent/traces/` and are not
  committed as public evidence.
- No further prompt, schema, compiler, clarification-policy, or ready-corpus changes are
  authorized unless the project owner explicitly reopens intent work. The earlier 44/48 and
  40/48 records remain historical milestones.
