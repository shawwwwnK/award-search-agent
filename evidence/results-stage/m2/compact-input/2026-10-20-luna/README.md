# Compact Results input: bounded Luna diagnostic

This run tests the compact Results M2 writer input on the three frozen iteration 006
cases. It is request-specific diagnostic evidence, not M2/M3 qualification or owner
acceptance. The saved run used `gpt-6-luna`, made five generation calls and five input
count calls, and recorded 843,051 writer input tokens plus 21,591 output tokens. No
provider calls or automatic reruns were made. No dollar cost is asserted because an
invoice and current rates were not verified.

## Live results

| Case | Iteration 006 initial input | Compact initial input | Reduction vs. iteration 006 | Attempts | Delivery/check outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| Admitted | 822,377 | 199,377 | 75.76% | 1 | Delivered, clean; 2 journeys and cash benchmark |
| Conditional | 732,878 | 179,488 | 75.51% | 2 | Delivered annotated; correction retained with two shared-disclosure key findings |
| Incomplete | 253,293 | 141,023 | 44.32% | 2 | Delivered, clean after correction; 2 incomplete leads and cash benchmark |

The iteration 006 comparisons used `gpt-6.1-sol`, while the new run used Luna. A
separate same-model comparison for the admitted case used iteration 003's Luna request
with the same canonical projection: 820,736 input tokens versus 199,377, a 75.71%
reduction. Its earlier prompt/source differs, so this is still not a controlled
same-version comparison. Exact request and output receipts are retained in each case
folder and summarized in [summary.json](summary.json).

## Inspect a case

The request contains the exact serialized request envelope; the decoded input makes
the compact prepared source easier to inspect. Each response artifact also retains the
canonical facts and bound rendering for replay.

- **Admitted:** [initial request](admitted/01-initial-request.json) · [decoded input](admitted/01-initial-input.json) · [writer receipt](admitted/01-initial-writer-receipt.json) · [answer](admitted/answer.md) · [artifact](admitted/artifact.json) · [run receipt](admitted/receipt.json)
- **Conditional:** [initial request](conditional/01-initial-request.json) · [decoded input](conditional/01-initial-input.json) · [correction request](conditional/02-correction-request.json) · [correction input](conditional/02-correction-input.json) · [answer](conditional/answer.md) · [artifact](conditional/artifact.json) · [run receipt](conditional/receipt.json)
- **Incomplete:** [initial request](incomplete/01-initial-request.json) · [decoded input](incomplete/01-initial-input.json) · [correction request](incomplete/02-correction-request.json) · [correction input](incomplete/02-correction-input.json) · [answer](incomplete/answer.md) · [artifact](incomplete/artifact.json) · [run receipt](incomplete/receipt.json)

## Offline preservation and measurement

- [Field disposition](field-disposition.md) explains which fields are sent, grouped,
  summarized or retained locally.
- [Offline request measurement](offline-measurement.json) includes full initial and
  representative correction request JSON bytes and hashes. Input payload bytes fell
  66.06%, 65.44% and 35.24% for admitted, conditional and incomplete; complete outer
  request JSON fell 64.13%, 63.42% and 32.11%. These byte changes are separate from
  the measured live token counts above.
- [Preservation probe](offline/preservation.json) checks canonical facts, selectable
  aliases, exclusion summaries, comparisons, component/member timestamps and grouping.
  [Negative controls](offline/negative-controls.json) check cases that must stay
  distinct, and the writer requests contain no long opaque hash identifiers.
- [Source snapshot](source-snapshot.json) and
  [snapshot archive](results-source-snapshot.zip) bind the saved inputs to the tested
  source version.
- [Answer review](answer-review.md) audits source fidelity, conditions, usefulness and
  presentation against the canonical source and prior iteration. It found no unsupported
  positive claims about availability, protection, per-leg cabin or party-wide price. It
  also records material defects: incomplete leads omit points units/program names and
  have malformed/awkward schedule text; conditional delivery retains two visible
  “Please check” notices and chooses two economy options sharing one award observation,
  while a business-cabin alternative remained in the canonical pool. The admitted answer
  surfaces a useful calendar-arrival tradeoff. These observations do not isolate the
  effect of compaction because model, guidance and settings also differ.
- The original [pre-fix replay report](replay-verification.json) records the V5
  incomplete artifact's seed-37 check-receipt mismatch. The narrow fix changed only
  `src/award_agent/results/core.py` after the live run. The [post-fix replay report](post-fix-replay-verification.json)
  passes all seven artifacts (the three new V5 artifacts plus saved V1–V4 artifacts)
  at seeds 11, 23 and 37. The [request/artifact integrity report](post-fix-request-verification.json)
  confirms all five original live requests and artifact hashes remain unchanged and
  records zero paid calls. The [replay-fix source manifest](replay-fix-source.json)
  and [source snapshot](replay-fix-source-snapshot.zip) preserve the exact post-live
  code. An independent architect review confirmed tampered or reordered findings
  remain rejected. This closes the V5-specific seed-37 issue; it does not close the
  separately recorded older finding-order concern for historical behavior.

## Engineering checks

Before the narrow post-live replay fix, the repository-wide suite reported 878
passed, 99 skipped and two known gfly environment failures. After the fix, the
focused Results/evaluation/harness suite passed 162 tests in 172.36 seconds; mypy on
eleven files and scoped Ruff passed. The full repository suite was not rerun after
the core change. The final implementation log records this chronology and the
two environment failures.

## Limits

Three saved cases and five generation calls do not establish broad answer quality,
context fit, traveler benefit or owner acceptance. A clean mechanical outcome does not
prove semantic truth. The conditional annotated result is a visible failed check, and
the answer review identified choice-diversity and presentation problems. Full evaluation
and repository test evidence is summarized in the
[implementation build log](../../../../../docs/build-log/2026-10-20-results-m2-compact-input.md).
