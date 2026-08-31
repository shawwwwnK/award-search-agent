# Live Intent Schema Failure Diagnosis

- **Date:** 2026-08-30
- **Goal for this session:** Reproduce and diagnose four user-reported `gpt-4o-mini`
  request-understanding failures involving vague month, holiday-relative, duration-range, region,
  and tentative-destination language.
- **Work attempted:** Ran each reported request through `award-intent` with reference date
  `2026-08-29` and timezone `America/Los_Angeles`; inspected the Pydantic output schema,
  extraction prompt, date contracts, workflow, golden cases, and offline tests.
- **Files changed:** This build-log entry only. No runtime or test behavior was changed.
- **Commands and tests run:**
  - The four reported `.venv/bin/award-intent --model gpt-4o-mini ...` commands.
  - `.venv/bin/python -c ...` to inspect the generated `IntentExtraction` JSON Schema.
  - `.venv/bin/pytest -q` returned 41 passing tests in 0.23 seconds.
- **Evaluation result:** All four live commands exited with `IntentExtractionError`. Their causes
  were Pydantic validation errors after the model returned schema-shaped JSON: unresolved date
  expressions without a reason; a relative-month expression without an offset; an exact date
  without a day; and a range without boundary days.
- **Most instructive failure:** The flat `DateExpression` JSON Schema makes most component fields
  nullable and does not encode the component requirements associated with each `kind`. Those
  requirements exist only in a Pydantic model validator, after model output has already been
  generated. Structured output therefore does not prevent combinations that the application
  rejects.
- **Failure classification:** Model/schema contract mismatch, plus missing contract coverage for
  duration ranges and some vague or holiday-relative date phrases.
- **Trace observation:** The adapter replaces the actionable validation cause with the generic
  message `OpenAI intent extraction failed`; the CLI exposes the underlying cause only through a
  full traceback. The offline suite uses fake, already-valid `IntentExtraction` objects, and the
  eval-case test checks corpus metadata rather than executing or scoring live extraction.
- **Suggested next cut:** Replace the flat date-expression wire schema with kind-specific nested
  variants (or a permissive wire DTO followed by an explicit deterministic conversion), add
  intentional representations/policy for vague month portions and duration ranges, add these four
  cases to an executable live baseline, and preserve structured validation details in traces.
- **What Codex generated:** Reproduction evidence, contract diagnosis, proposed fix order, and this
  build log.
- **Architectural or product decisions:** **PROJECT OWNER INPUT NEEDED:** choose the exact meaning
  of phrases such as “early May,” whether “after New Year” should always trigger clarification,
  and whether a 1–2 week duration is accepted as bounded flexibility or clarified.
- **Interpretation of what was learned:** **PROJECT OWNER INPUT NEEDED.**
- **What the project owner changed or rejected:** **PROJECT OWNER INPUT NEEDED.**
- **Final next cut line:** **PROJECT OWNER INPUT NEEDED.**
