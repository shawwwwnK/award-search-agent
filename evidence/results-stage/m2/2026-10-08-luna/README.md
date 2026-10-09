# Results M2 Luna live diagnostic — retained evidence

This directory retains ten Results runs over the three saved Ranking `SolutionProjection` inputs. No provider data was refreshed. The [run plan](run-plan.json) declared the original settings and six-call campaign ceiling; the owner's [budget amendment](budget-amendment.json) lifted the campaign ceiling while each Results run still allowed one initial writer call and at most one correction. The additional guided, bound, and declared runs are retained separately. No run replaces another.

The per-run [summary](summary.json) lists source/config hashes, every attempt, count and writer receipts, raw response retention, status, findings, selection, latency, usage, cost tier, rendered digest, and exact Markdown replay bytes. [summarize.py](summarize.py) recomputes it locally and checks an existing summary without network access. The artifact JSON retains the full raw model response and any failure. The Markdown file is the replayed delivery, including local notices; an empty Markdown file indicates no delivery.

| Run | Case | Writer calls | Failed findings, initial → correction | Selected | Delivery | Notices | Replay bytes | Estimated generation cost |
| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: |
| baseline | [positioning](sfo_to_bkk_positioning.artifact.json) | 2 | 34 → 3 | correction | annotated | 3 | 10,395 | $0.04966490 |
| guided | [positioning](sfo_to_bkk_positioning.guided.artifact.json) | 2 | 62 → 88 | initial | annotated | 62 | 14,312 | $0.04991820 |
| guided | [exact business](exact_business.guided.artifact.json) | 2 | 70 → 75 | initial | annotated | 70 | 14,022 | $0.20062840 |
| guided | [mixed access](mixed_access.guided.artifact.json) | 1 | incomplete at output limit | none | none | 0 | 0 | $0.15007640 |
| bound | [positioning](sfo_to_bkk_positioning.bound.artifact.json) | 1 | 0 | initial | clean | 0 | 9,122 | $0.02582240 |
| bound | [exact business](exact_business.bound.artifact.json) | 1 | 0 | initial | clean | 0 | 8,924 | $0.09777837 |
| bound | [mixed access](mixed_access.bound.artifact.json) | 1 | 0 | initial | clean | 0 | 6,921 | $0.14318867 |
| declared | [positioning](sfo_to_bkk_positioning.declared.artifact.json) | 1 | 0 | initial | clean | 0 | 10,653 | $0.02508100 |
| declared | [exact business](exact_business.declared.artifact.json) | 2 | 3 → 1 | correction | annotated | 1 | 10,366 | $0.19888988 |
| declared | [mixed access](mixed_access.declared.artifact.json) | 2 | 6 → 3 | correction | annotated | 3 | 9,290 | $0.28664388 |

Across all retained attempts, there were **15 writer calls**, 6,444,535 input tokens, 108,897 output tokens (including 50,275 reasoning tokens), 8,780 cached input tokens, and 6,435,710 cache-write tokens. Estimated generation cost is **$1.22769210**. Each call uses the declared Luna rate tier: input at $0.10/M and output at $0.50/M for inputs through 272,000 tokens; longer inputs at $0.20/M and output at $0.75/M. Cached input uses 10% of its tier's input rate. Cache writes receive no discount in this estimate. Count-endpoint billing is unclaimed. The incomplete guided mixed call is included in these totals.

The original baseline artifact embeds a config without `max_input_tokens`. [baseline.original.config.json](baseline.original.config.json) was derived from that embedded receipt after [config.json](config.json) gained the 922,000 input cap for later use; the derived file is a reproduction aid, not a pre-run plan. The guided, bound, and declared artifacts match their respective [guided](guided.config.json), [bound](bound.config.json), and [declared](declared.config.json) configs. Exact initial input counts and the one retained failed preflight count are in the case-specific `*.count*.json` files. Initial and correction count receipts for the later runs are embedded in each artifact.

The bound batch's zero failed findings means the configured mechanical slot, identity, disclosure, and claim checks found no failure. It does not establish that every sentence is true. Read-only review found misleading cash-cabin labels, an unsupported earlier-departure explanation, repeated units, and absent or unchecked claim declarations. The declared batch tested targeted guidance and retained its annotated corrections; it still contains unchecked claims and visible notices. No M3 semantic evaluation or owner qualification is claimed.

To recheck the complete saved corpus, run `.venv/bin/python evidence/results-stage/m2/2026-10-08-luna/summarize.py` from the repository root. This validates every artifact against its saved Ranking source and config, replays it offline, compares exact Markdown bytes, and verifies [summary.json](summary.json). The [index](index.json) records a SHA-256 manifest for this directory's retained input, output, and receipt files.
