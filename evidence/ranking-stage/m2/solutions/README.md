# Ranking M2 factual solution exports

These offline exports extend Ranking M2 with the factual preparation formerly planned as Results
M1. Each artifact is a `SolutionProjection` containing one `SolutionView` and a private-facing
source `ProjectionReceipt`. Results M2 will consume the view directly and add answer-specific
slots, selection and disclosure rules. No Results runtime or model/provider call is included.

The source files in `../styled/` remain unchanged. The [index](index.json) records exact source
and output hashes, source/view digests, complete accounting and measured byte sizes.

| Case | All candidates | Eligible complete | Components | Compact view bytes | Full artifact bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Mixed access](mixed_access.json) | 473 | 257 | 315 | 2,011,912 | 3,911,674 |
| [Exact business](exact_business.json) | 396 | 106 | 119 | 1,302,037 | 2,502,403 |
| [Positioning](sfo_to_bkk_positioning.json) | 123 | 64 | 115 | 654,408 | 1,267,942 |

View bytes use `view.model_dump_json()` encoded as UTF-8. Full artifacts are indented JSON with
one trailing newline and include the receipt. These are factual export measurements, not complete
authoring-prompt sizes or token counts. No model-context fit is established. All candidates,
including rejected/research records, remain; no input cap, aliasing or new selection policy was added.

Factoring shares source observations, reason sets, normalized cost components, cost breakdowns and
style decisions. Technical candidate query/support/dependency links and evidence references live
in the receipt. Supplied statuses, scope, conditions, style memberships and original comparison
references remain unchanged. All three cost references remain absent; provider coverage is partial.

The positioning tests independently pin the Aeroplan USD 196 / 29h50 / 6h20-transfer and USD 290 /
27h30 / 3h50-transfer variants. Local schedules derive from aware instants and IANA timezone
evidence; misleading raw provider local strings remain receipt-only. The export records no host
timezone-database release, so regeneration across different timezone databases is unqualified.

Verify all three saved exports without a model or provider:

```sh
.venv/bin/python scripts/ranking_solution_corpus.py \
  --output-dir evidence/ranking-stage/m2/solutions --verify
```

Generate into a new directory:

```sh
.venv/bin/python scripts/ranking_solution_corpus.py --output-dir /private/tmp/new-solutions
```

Export one saved ranked input:

```sh
.venv/bin/python -m award_agent.cli.ranking_solutions \
  --ranked evidence/ranking-stage/m2/styled/sfo_to_bkk_positioning.json \
  --output /private/tmp/new-positioning-solutions.json
```

Commands refuse to replace existing output evidence. Receipt association checks cover the export's
own references; they do not reverify upstream eligibility. See the
[extension contract](../../../../docs/handoffs/2026-10-04-ranking-m2-solution-export.md) and
[build log](../../../../docs/build-log/2026-10-04-ranking-m2-solution-export.md).
