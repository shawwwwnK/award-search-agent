# 2026-09-04: Compiler-select ready-corpus smoke

## Objective evidence

- Ran one `gpt-4o-mini` trial across all sixteen ready intent-evaluation cases using
  `compiler_select_v1`.
- The artifact recorded 10 passing runs, 6 runs with failed checks, and 0 explicit errors.
- The compiler route made 16 non-temporal Pass-1 calls, with zero selector calls, zero Pass-2
  attempts, and zero repairs. This confirms the current ready corpus is auto-only and that the
  new runner did not construct or invoke legacy temporal resolution.
- Captured usage was 15,547 total tokens and 26.126 seconds aggregate latency. Cost is not
  calculated by the evaluator.
- Failed checks were evidence-envelope linkage for `labor_day_thursday_flexibility`; a production
  slot versus request-field reference expectation for `return_weekend_after_departure`; omitted
  traveler extraction in two cases; and destination/clarification outcomes in three cases. These
  are observations from one trial, not a product or architecture conclusion.

## Command and artifact

```text
.venv/bin/python -m award_agent.cli.intent_eval --strategy compiler_select_v1 --model gpt-4o-mini --trials 1 --no-trace --output evals/intent/baseline/2026-09-04-gpt-4o-mini-compiler-select-ready-1-trial.json
```

- Artifact: `evals/intent/baseline/2026-09-04-gpt-4o-mini-compiler-select-ready-1-trial.json`
- `jq empty` on the artifact — passed.
- `git diff --check` — passed.

## Not yet evidenced

- No frozen selector study has run: the `luna` model ID remains intentionally unspecified.
- No full compiler end-to-end matrix or selector activation decision is recorded.

## Owner interpretation

<!-- Project owner: record product/architecture conclusion and the next cut line here. -->
