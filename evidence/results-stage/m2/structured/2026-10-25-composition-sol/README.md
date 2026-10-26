# Results M2 composition — final source-reviewed cohort

The owner invoked implementation, code review and full saved-case live iteration.
One composer writes a connected answer with individual Ranking-informed highlights,
relevant alternatives, embedded exact references, cash context and consolidated
applicable limitations. Code still resolves factual cards and the independent explorer.
No frontend renderer, new travel-provider search or FX refresh was implemented here.

## Final answers

All three use [one explicit evaluated configuration](evaluated-config.json), GPT-6.1 Sol.
No global model default is adopted. Each actual answer passed independent composition
and source review for its inspected scope; see [answer review](answer-review.md).

| Case | Eligible journeys | Readable text inspection | Exact source/artifact |
| --- | ---: | --- | --- |
| Admitted | 258 | [Answer with card markers](round-1/admitted/answer-preview.md) | [Artifact](round-1/admitted/artifact.json), [resolved](round-1/admitted/resolved.json) |
| Conditional | 232 | [Answer with card markers](round-1/conditional/answer-preview.md) | [Artifact](round-1/conditional/artifact.json), [resolved](round-1/conditional/resolved.json) |
| Incomplete | 0 | [Answer with lead/card markers](round-1/incomplete/answer-preview.md) | [Artifact](round-1/incomplete/artifact.json), [resolved](round-1/incomplete/resolved.json) |

Previews preserve model prose verbatim; compact quoted lines are source-resolved card
insertion markers, not a frontend. The full explorer remains in artifact.evidence and
is placed at the end by future frontend work. These results do not close owner
presentation acceptance or qualify M3, repeatability or traveler task benefit.

## Iteration and engineering evidence

Four [Luna cohorts](../2026-10-25-composition-luna/README.md) remain failed development
evidence. Lead identities were enriched beside aliases without dropping any member;
prose/reference duplication and selection/contrast instructions were corrected. Luna
still omitted material choices and made numerical errors. A stronger single composer
was trialed before adding further prompt patches or an agent framework.

[Model comparison](model-comparison.json) proves only model changed from final Luna:
same source digest, complete input, instructions and code snapshot. Official
[model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
provided context/Responses/structured-output compatibility guidance, not quality proof.
Stochastic samples differ; no broad model-superiority claim follows.

This campaign used **4 generations and 4 input counts**, with 740,382 input and 6,044
output tokens in writer receipts. [Integrity audit](audit-summary.json) passed 9
fresh-process archived/current-source-equivalent replays at seeds 11/23/37. Exact
resolved digests, aliases, source/member/group IDs, raw responses, usage, requests
and reserved calls reconcile. All three snapshots/configs match final current code.
Original October24/compact-source evidence is unchanged.

Combined session: 15 saved-case runs, 22 generations and 22 counts; 3,935,205 writer
input and 59,351 output tokens. These are usage totals, not billing estimates.
No automatic SDK retries or provider searches occurred. See the
[implementation log](../../../../../docs/build-log/2026-10-25-results-m2-composition-correction.md)
and [code review](../2026-10-25-composition-luna/code-review.md).

The full suite finished 931 passed, 99 skipped and 2 unchanged gfly environment failures;
see [captured output](../2026-10-25-composition-luna/full-suite-output.txt) and
[fresh environment probe](../2026-10-25-composition-luna/gfly-environment.json).
The repository suite is not green. Focused structured tests 18 passed, combined types
(five files), scoped Ruff and source/receipt audits passed. Legacy matrix outcomes
match 15 passes / 3 historical V4 preparation failures across 18checks; old V6 preparation
replay intentionally differs after the new instructions, with original archives intact.

Reproduce integrity without paid calls:

```bash
.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-composition-luna/audit.py --campaign-root evidence/results-stage/m2/structured/2026-10-25-composition-sol --final-round 1
```

The completed campaign is evidence, not authorization to reuse leftover budget.
New live invocations must use new output directories and their declared scope.
