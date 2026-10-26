# Results M2 Luna latency investigation — 2026-10-25

## Subsequent advisor review and next-session handoff

The owner requested independent milestone/constraint review and then a handoff for
a new session. An architect reviewed the current objective, ownership/recovery
contracts, milestone map, workbook and diagnostic evidence. It recommended narrowing
the next cut to existing input ergonomics and bounded measurement: limited factual
comparison aids, no pairwise engine, no new runtime blocking gate, and no numeric
SLA invented or required before offline work. These are advisory restrictions
preserving existing decisions, not a new implementation invocation.

Added the [next-session handoff](../handoffs/2026-10-25-results-m2-luna-latency-next-cut.md)
and linked it from project state. No runtime code or new paid calls; no new ADR is
needed for recording this continuation under unchanged boundaries. Handoff local
links and diff whitespace were checked; runtime tests were not rerun for prose.

The owner subsequently asked about parallel subagents plus final composition and
requested adding that alternative to the handoff. Recorded an optional all-Luna
two-analysis-worker/one-composer probe after the improved-input baseline, including
sequential synthesis cost, exact-reference/source preservation, explicit failure
bounds and quality/cost/wall-time comparison. This is a proposed experiment only;
no runtime topology, current multi-agent non-goal or one-composer decision changed.
Runtime adoption would need the ADR disposition described in the handoff. No new
live calls or tests were run for this documentation addition.

## Invocation and scope

Owner: “latency is very very high, more than1minute”, keep Luna, investigate causes,
mitigations and experiment. This opens a new bounded saved-input diagnostic after
the prior documentation-only checkpoint. No travel-provider/FX calls, runtime
changes, shared-default adoption, frontend work, commit or push occurred.

Read current project state, ADR0029/ADR index, deferred register, prior latency note,
cost/composition evidence, writer/runner/CLI paths and relevant workbook latency
budget (unfilled; no SLA invented). Applied design-lab, OpenAI Docs and
verification-before-completion skills. An investigator traced payload repetition
and produced the isolated factor/audit script; an architect independently reviewed
all eight raw answers against original source objects and the composition contract.

## Evidence and changed files

Added `evidence/results-stage/m2/structured/2026-10-25-latency/`: campaign reservation
bounds,8exact requests/raw responses/timings,7parsed documents/resolved previews/checks,
one explicit Pydantic failure, factor/verify/probe scripts, exact round-trip audit,
local timing/prefix probes, independent review and report. The request model is
`gpt-6-luna`, explicit low/medium, standard mode,32768output cap,240second SDK timeout,
zero automatic retries. Streaming adds timing only. The SDK timeout is not claimed
as a composed whole-application deadline. Calls were concurrent in small groups.

The source is the unchanged Luna cost-retry initial requests and source artifacts.
Probe request/source hashes, returned usage and exact request controls reconcile.
Canonical source and every eligible option remain unchanged. Isolated probe documents
are not claimed as versioned runtime artifacts or historical source replay evidence.
Updated project state, latency note, ADR0029/index and deferred G06/G08 disposition.

See [report](../../evidence/results-stage/m2/structured/2026-10-25-latency/README.md),
[summary](../../evidence/results-stage/m2/structured/2026-10-25-latency/summary.json),
and [review](../../evidence/results-stage/m2/structured/2026-10-25-latency/review.md).

## Observed outcomes

- Original low initial generations13.11–17.06seconds; all fail mechanical or semantic
  review. Medium originals87.25s admitted/42.84s conditional also fail; the latter
  cannot be parsed under existing document invariants. No clean accepted answer
  speedup is established. No corrections were run, so answer-level latency remains
  unmeasured. Earlier passing Luna evidence remains intact.
- Exact factoring saves39.6%/39.0%prompt bytes and31.33%/31.05%API input tokens,
  preserving258/232exact journey aliases. Incomplete remains unchanged. Medium
  factored admitted55.95s and conditional43.22s; both fail required quality/delivery
  criteria. Low factored admitted15.09s also fails.
- Medium admitted first text77.42s despite207321cached tokens; low original7.16s
  first text and16.52s full with zero cached tokens. Reasoning is a major contributor;
  this is not isolated server profiling or a causal quality result.
- Offline local operations total about0.67–1.79seconds per case excluding source
  parsing/full-run replay/counting. Feedback-first serialization defeats stable
  preparation prefixes on correction (13shared input bytes versus597318with
  preparation first); this is a proposed cache aid, not measured live savings.

## Verification

Commands actually run:

```bash
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-latency/factor.py
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-latency/verify.py
.venv/bin/ruff check evidence/results-stage/m2/structured/2026-10-25-latency/*.py
.venv/bin/pytest -q tests/unit/test_results_structured.py tests/unit/test_structured_results_eval.py tests/unit/test_results_structured_cli.py
git diff --check
```

Focused suite:27passed in98.67seconds. Offline factoring restores whole original
requests and alias inventories. Seven parsed documents reproduce exact saved findings
and resolution; the eighth validation failure remains explicit. No runtime code
changed; full suite/full historical replay were not rerun. Existing unrelated
untracked end-to-end diagnostic files were preserved. No credentials are captured.
Estimated generation cost and total usage are recomputed in summary.json using
current official pricing, including failed generation and cache writes; not an invoice.

## ADR and next-cut disposition

Amended ADR0029's experiment disposition and index; no new ADR required for isolated
settings/encoding probes. No model/code ownership, Ranking/eligibility, trust or
evaluation acceptance boundary changed. Future comparison aids remain proposals.
No tested candidate is adopted. Owner preference to retain Luna is recorded;
presentation acceptance, frontend/M3 and G06/G08 claims remain separate.

Owner conclusions/accepted next cut: **not supplied in this investigation**. Agent
recommendation is a decision-oriented input/comparison experiment, stable preparation
before feedback, and repeated matched timing including corrections before changing
runtime defaults. Do not treat this recommendation as an implementation invocation.
