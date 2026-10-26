# Luna Results M2 latency investigation

2026-10-25. Owner requested investigation, mitigations and experiments while keeping
Luna. This authorizes a new bounded diagnostic, superseding the previous note's
documentation-only scope for this session. Runtime code/defaults are unchanged.

## Measured results

Eight saved-input generations, no retries, corrections, token-count requests,
travel searches or FX calls. All use **gpt-6-luna**, standard processing/reasoning
mode, 32,768 maximum output tokens and streaming for telemetry. Explicit effort
and exact reversible input factoring are the experimental controls.

Total usage: 1,380,923 input / 28,122 output tokens; estimated generation cost
**$0.14050**, including the schema-invalid answer. Native Codex work is excluded.

| Probe | Input tokens | First text | Full response | Failed checks | Quality disposition |
| --- | ---: | ---: | ---: | ---: | --- |
| Admitted, original medium | 207,324 | 77.42 s | 87.25 s | 2 | Material factual/reference failures |
| Admitted, original low | 207,324 | 7.16 s | 16.52 s | 0 | Material arithmetic/choice failures |
| Conditional, original medium | 189,806 | 34.14 s | 42.84 s | Unparsed | Document fails Pydantic validation |
| Conditional, original low | 189,806 | 9.62 s | 17.06 s | 0 | Misleading cabin/arrival tradeoff |
| Incomplete, original low | 171,065 | 4.67 s | 13.11 s | 3 | Source-sound narrative; invalid benchmark selection |
| Admitted, factored medium | 142,367 | 45.60 s | 55.95 s | 3 | Reference/claim failures |
| Conditional, factored medium | 130,864 | 36.53 s | 43.22 s | 0 | Misleading cabin/arrival tradeoff |
| Admitted, factored low | 142,367 | 7.41 s | 15.09 s | 1 | Material date/arrival errors |

These are **initial-generation timings**, not accepted complete-answer or application
latency. Production would add correction for recoverable failed checks. Schema-invalid
conditional medium has no recoverable draft. Clean checks do not establish narrative
truth. No probe establishes a quality-preserving latency solution. See the independent
[source/composition review](review.md), [all request/response metrics](summary.json)
and each probe directory's actual `answer-preview.md` or raw `response.json`.

## Findings

**Observed:** medium is currently implicit, with no explicit reasoning setting in
`structured_token_request`. Fresh medium admitted spent 7,054 of 8,366 output tokens
on reasoning, versus 360 of 1,366 at low. It took 87.25 s despite 207,321 cached input
tokens; low had zero cached tokens and took 16.52 s. This is strong evidence that
reasoning is a major latency contributor, not evidence that input processing is free
or that queue/network time has been isolated. Cache conditions differ and each arm is
one stochastic draw. The original medium baseline also fails quality, so the experiment
does not establish that lowering effort alone caused the quality failures.

**Observed:** repeated journey `reasons`, `cost`, `assessments` and
`positioning_reason` dominate much of the input. Exact per-field catalogs reduce
prompt bytes 39.6% admitted/39.0% conditional, and actual API input tokens
31.33%/31.05%. [Factoring audit](audit.json) proves inverse decoding restores the
entire original request and every member/lead/benchmark alias. All 258 admitted and
232 conditional exact journey choices remain. These counts are from these saved
sources, not the earlier corpus's eligible-alternative totals. The incomplete request
is unchanged because it has no journeys; its 383 component groups and 378 leads
require another approach. Identity summaries are retained to avoid the earlier lead
association failures.

**Observed, mixed:** factoring at medium reduced admitted 87.25→55.95 s, but
conditional was effectively unchanged, 42.84→43.22 s. At low admitted changed
16.52→15.09 s. This is no reliable proportional speedup; changed reasoning token
counts, cache warmth and ordinary sampling variance prevent isolating prefill savings.

**Observed:** first stream event arrived in 0.67–1.51 s, but medium first visible
JSON waited 34–77 s. The current structured document requires full parsing and
reference checks before usable delivery. Streaming can improve perceived progress;
this probe does not implement safe incremental rendering or demonstrate usable
flight cards at first text. Do not label first event/text a completed recommendation.

**Observed:** local workspace/preparation/check/resolution took roughly 0.67–1.79 s
per case in a separate one-pass offline profile (excluding source parse and any
full-run replay). [Local timing](local-timing.json) rules these measured operations
out as a sufficient explanation for the minute-long generation receipt. It is not
a full application profile. Token-count requests occur **before** generation and
remain unmeasured; they cannot explain the generation timer itself but add user wait.

**Observed:** current payload serialization puts `feedback` before the large stable
`prepared` view. In the saved incomplete correction, the initial/correction input
shares only 13 bytes before divergence; moving unchanged preparation first would
share 597,318 bytes. The historical correction cached only 1,444 tokens.
[Prefix probe](prefix-audit.json) is offline evidence of avoidable prefix churn,
not a measured new cache hit or speedup. This mitigation affects corrections and
same-evidence follow-ups, not the first cold request.

## Recommended next experiment

Keep Luna. **Do not adopt low effort or claim this factoring fixes latency.**

1. Build an isolated decision-oriented writer view: concise candidate facts and
   exact schedules/prices/cabins beside each selectable alias; factor repeated
   internal evidence. Preserve all eligible choices and unknowns, complete canonical
   evidence and independent explorer. Avoid forcing the writer to infer a schedule
   advantage from a cabin difference: show same-schedule economy/business variants
   together. A comparison aid can supply deterministic date/time differences without
   changing Ranking or imposing the answer structure. This is a proposed input
   experiment, not an adopted stronger inline-factual-binding requirement.
2. First test that representation at medium, then low with the **same** composition
   and source criteria. Use repeated interleaved draws with cache conditions recorded;
   include failed attempts and correction latency. The same-schedule economy controls,
   cross-midnight arrival arithmetic and exact benchmark/lead roles seen here should
   be explicit review checks. A faster invalid answer is not a successful sample.
3. Put stable preparation before feedback/prior draft in a separate prefix-control
   probe. Measure count, preparation, generation and full application completion;
   retain full context protection. Consider skipping live counting only where an
   independently conservative local bound proves safety under the chosen limits.
   Current counting behavior is unchanged.
4. Treat streaming as a later frontend delivery experiment with an exact first-usable
   bound/reference measurement. Fast processing is another possible paid lever, but
   was not tested or priced here; cost-sensitive input/reasoning work comes first.

No numeric acceptance target is assumed. Frontend M1/M2, owner presentation acceptance
and Results M3 remain separate. The owner preference is Luna; this diagnostic does not
change shared defaults or qualify it for unattended use.

## Reproduction and verification

`probe.py` makes live calls and has an eight-attempt persisted reservation bound, now
exhausted. Do not rerun it to reproduce offline findings. `factor.py` and `verify.py`
are offline:

```bash
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-latency/factor.py
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-latency/verify.py
.venv/bin/ruff check evidence/results-stage/m2/structured/2026-10-25-latency/*.py
.venv/bin/pytest -q tests/unit/test_results_structured.py tests/unit/test_structured_results_eval.py tests/unit/test_results_structured_cli.py
```

The focused suite passed **27 tests**. Exact request/source integrity and offline
resolution rechecks pass for seven parsed documents; the eighth retains its validation
failure. This is an isolated probe format, not a new canonical Results artifact/replay
version. Full historical/source-version replay and full suite were not rerun because
runtime code did not change. Original source/diagnostic bytes remain unchanged.

Native agent review time is separate from application measurements. Calls were launched
in small concurrent groups; summed request durations are not session wall time. The
eight-call cap and all failed results are retained in [campaign bounds](campaign.json).

Official guidance supports testing lower effort rather than assuming quality is
preserved ([reasoning](https://developers.openai.com/api/docs/guides/reasoning)),
prioritizing generated-token work and measuring massive-context effects
([latency](https://developers.openai.com/api/docs/guides/latency-optimization)),
and stable-prefix reuse ([caching](https://developers.openai.com/api/docs/guides/prompt-caching)).
These are mechanisms, not workload-specific performance guarantees. Token-cost estimates
in `summary.json` use [current pricing](https://developers.openai.com/api/docs/pricing),
including cached input and default 30-minute cache writes; they exclude native Codex
work and are not an invoice.
