# Results M2 cheaper-model experiment

The owner requested Luna again and Terra as an incremental candidate because the
passing Sol writer was too expensive. Runtime code, input, source and final brief
are unchanged. Only model differs from Sol; no answer/exemplar was fed back.

## Observed results

| Configuration | Coverage | Generations / counts | Input tokens | Output tokens | Estimated generation cost | Summed generation time |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Luna retry | Three saved cases | 4 / 4 | 739,968 | 14,677 | $0.09934 | 233.23 s |
| Terra | Admitted sentinel only | 1 / 1 | 207,324 | 1,464 | $0.53588 | 17.22 s |
| Sol baseline, unchanged | Three saved cases | 4 / 4 | 740,382 | 6,044 | $1.90099 | 113.47 s |

Luna's retry is **94.77% cheaper** than the passing Sol cohort, with about
twice the summed generation time. Individual case generation sums: admitted90.71s,
conditional72.75s,incomplete69.77s. These exclude counting/local processing and are
not concurrent session wall time. Terra admitted is nearly the same cost as Sol's
admitted($0.53588 versus$0.53616), though faster in this sample.

Luna's three answers pass composition review. Source reviewer flagged the conditional
opening's “quicker” wording despite equal economy/business durations; adjudication
retains it as a minor ambiguity because the paragraph repeatedly states their same
schedule. Read [the full review including disagreement](review.md). Do not describe
this as an unqualified unanimous factual pass. Earlier Luna failures under the same
brief are preserved; repeatability and safe unattended use remain unestablished.

Terra's source quantities reconcile, but its scattered limitations and unreferenced
business discussion miss the complete composition target. Stop after sentinel rather
than spend on a full cohort with no observed cost benefit.

## Actual answers

- Luna: [admitted](luna-retest/round-1/admitted/answer-preview.md),
  [conditional](luna-retest/round-1/conditional/answer-preview.md),
  [incomplete](luna-retest/round-1/incomplete/answer-preview.md).
- Terra: [admitted](terra/round-1/admitted/answer-preview.md).
- [Original passing Sol cohort](../2026-10-25-composition-sol/README.md).

Previews preserve the model prose and exact card insertion points, not a rendered
frontend. Full source/card/explorer facts remain in each artifact/resolved JSON.

## Costs, bounds and verification

This experiment used **5 generations and5 input counts**, totaling947,292 input
and16,141 output tokens; estimated generation cost **$0.63521**. The Sol baseline
was reused, not regenerated. No travel-provider, FX or runtime-policy change occurred.

[Metadata](metadata.json) includes each attempt, reasoning/cache tokens, selected
attempt, latency, monetary estimate and per-case comparisons. Recompute with:

```bash
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-cost-experiments/summarize.py
```

Estimates use [published pricing](https://developers.openai.com/api/docs/pricing)
and [cache accounting](https://developers.openai.com/api/docs/guides/prompt-caching),
including default30-minute cache writes. No request exceeds272k input. Token-count
fees, native Codex work, account-specific billing and taxes are excluded; this is
not an invoice. [Terra documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
confirms its model identity/context support, not workload quality or cheaper pricing.

[Campaign bounds](luna-retest/campaign.json) and [Terra bounds](terra/campaign.json)
were declared before calls; both preserve one cohort and at most two attempts/run.
Unused limits are not new authorization. All artifacts/requests/receipts are immutable.
Luna [integrity audit](luna-retest/audit-summary.json) passed9 fresh-process replays;
Terra [audit](terra/audit-summary.json) passed3. Snapshots/aliases/counts/usage/ledgers
reconcile. Replay is not prose-quality evidence. No runtime code changed, so the
previous full suite was not rerun or claimed fresh; the summary script passes types
and Ruff. No default, frontend, owner presentation acceptance or M3 change is adopted.
