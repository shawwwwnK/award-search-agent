# Two-Pass Temporal Resolution Session

- **Date:** 2026-08-30
- **Goal for this session:** Replace the production detailed date-expression extraction path with
  coarse temporal anchors, deterministic anchor enrichment, and a second model date-range proposal.
- **User outcome shipped:** `award-intent` now runs two stored-disabled model calls. The first emits
  kind-specific exact-date, month, or holiday anchors plus verbatim temporal phrases. The second
  receives resolved anchors and proposes direct date windows, duration bounds, assumptions, and
  unresolved constraints. Deterministic code grounds evidence, strips unstated years, protects
  unbounded holiday-relative requests, calculates return bounds, detects conflicts, and selects at
  most one clarification.
- **Files changed:** Domain and model-adapter contracts, extractor/resolver interfaces, temporal
  enrichment and validation, workflow/CLI composition, unit tests, four golden cases, architecture
  documentation, ADRs, project state, and build logs.
- **Commands and tests run:**
  - `.venv/bin/pytest -q`
  - `.venv/bin/ruff check src tests`
  - `.venv/bin/mypy src tests`
  - The four reported live `.venv/bin/award-intent --model gpt-4o-mini ...` commands, with targeted
    repeated runs of the early-May request while stabilizing interpretation policy.
- **Evaluation result:** The final offline suite passed 52 tests with 89% measured line coverage;
  Ruff, mypy, and `git diff --check` passed. All four original live commands exited successfully in
  the final four-case regression. The unbounded New Year request asked for departure clarification;
  October plus two weeks produced an October 1-31 departure and October 15-November 14 return; the
  tentative São Paulo request asked for return timing. After adding explicit month-portion and
  approximate-duration policies, the final early-May run produced May 1-10, interpreted “about 10
  days” as 9-11 days, and produced May 10-21 return bounds.
- **Most instructive failure:** The first live run after implementation still failed because the
  model inferred years that were absent from the request and the deterministic evidence guard
  rejected them. After unsupported years were stripped, the next run exposed two semantic issues:
  the model invented an upper bound for “after New Year,” and its flexible-month duration arithmetic
  ended too early. Narrow deterministic acceptance policies now preserve the first case for
  clarification and calculate the second from model-interpreted duration bounds.
- **Failure classification:** Schema/semantic boundary mismatch, unsupported inference, and exact
  arithmetic inconsistency.
- **Trace observation:** The parsed output now retains the sanitized coarse extraction, resolved
  anchor dates and sources, second-pass interpretations and assumptions, interpreted duration, and
  unresolved constraints. The production workflow no longer emits detailed date expressions.
- **Decision made:** The project owner selected two model passes around grounded temporal anchors.
  Model pass one preserves coarse evidence; model pass two owns ordinary modifier interpretation and
  proposes ranges; deterministic code retains final grounding, exact arithmetic, conflicts, and
  clarification authority. This is recorded in ADR 0003.
- **What Codex generated:** Two-pass implementation, deterministic acceptance checks, adapter and
  workflow tests, four regression cases, live evaluation evidence, ADR and architecture updates,
  and this build log.
- **What the project owner changed or rejected:** The project owner identified that the detailed
  deterministic expression design was dominating normal-language parsing and explicitly requested
  the two-pass design implemented here.
- **Next cut line:** Run and score the entire sixteen-case live baseline with repeated trials; use
  the traces to decide whether the legacy detailed `DateExpression` resolver can be removed.
