# Results presentation iterations

**Current state (2026-10-09): paused at the owner's request after the in-flight
iteration 006 incomplete-case call. No more live calls are queued.** The latest
agent-reviewed [admitted answer](iterations/006/admitted/answer.md) and
[conditional answer](iterations/006/conditional/answer.md) are improved examples,
but their language still needs review. The [incomplete case](iterations/006/incomplete/receipt.json)
did not deliver an answer: its one writer call exhausted the declared output
token cap. Owner review is pending. Three other early-2027 final cases were not
rerun, so this is not six-case confirmation or Results M2 quality closeout.
See the [live index](index.md) and [cost report](cost-report.md) for all retained
iterations and exact authoring usage.

This directory compares user-facing Results answers against the saved October 8
end-to-end diagnostic. The source cohort is fixed initially to three early-2027
cases: an admitted award itinerary (`admitted`), conditional separate-ticket
journeys (`conditional`), and a search with incomplete award leads (`incomplete`).
The runner also names the three remaining early-2027 final cases
(`holiday_window`, `home_airport`, `early_month`) for a later six-case confirmation.
The original `answer.md`, `results-artifact.json`, and `solutions.json` files remain
in their source case directories. Do not overwrite them.

`iterations/<number>/` is append-only. Each live case holds `answer.md` (the text
to review), `artifact.json` (full Results receipts and exact source), and
`receipt.json` (source/baseline/config hashes, input/output token counts, outcomes,
finding counts, replay status). The iteration has the exact `config.json`, including
writer guidance. `review.md` records agent presentation findings and a distinct
owner-review status, separately from generated artifacts. Keep a new iteration
number when changing guidance, code, or selected
source. Never recast an earlier answer as a later one.
Each live iteration also archives the exact Results Python package and dependency
versions. After later Results edits, replay an experimental artifact with that
archived package in a temporary copy of `src`:

```sh
.venv/bin/python evidence/end-to-end/presentation/verify_archived.py 001 admitted
```

This verifies the ZIP's file hashes, restores the archived package into the
temporary copy, and checks exact `answer.md` bytes without changing the working
checkout. It assumes the non-Results source and listed dependencies remain
compatible; the iteration receipt also records the repository commit and dirty
paths at call time. Final stabilized artifacts should replay against current code.

The runner loads the repository `.env` locally, calls only the Results writer and
input counter, and consumes each saved Ranking `solutions.json`. It performs no
provider search or upstream pipeline call. The stored artifact can be replayed
offline. Use the explicit config and one or more cases:

**Resume only if the owner explicitly reauthorizes API spend after cost review.**

```sh
.venv/bin/python evidence/end-to-end/presentation/run_live.py 001 \
  --config evidence/end-to-end/presentation/configs/001.json
```

The Results API permits an initial authoring call and at most one correction for
each case. Read the generated answer and record concrete problems in the
iteration's `review.md`; revise the next numbered config or Results code and run
the same saved source cohort into a new iteration. A clean mechanical check and
exact replay do not establish natural language quality or factual semantic truth.
Keep owner review pending until the owner inspects the answers. A later live
end-to-end run requires separate authorization; this runner intentionally begins
after Ranking.

`build_iteration.py` writes `offline/<number>/` as a separate **offline authored diagnostic**. It freezes
hand-authored `ResultsDocument` fixtures, checks and renders them against the same
saved sources without model or provider calls. Its artifacts are examples for
comparing presentation and checker behavior. They are not evidence that the live
model improved. Do not substitute them for the live iteration record.

For review, check: (1) useful options or an honest no-complete-option answer;
(2) plain headings and natural travel language; (3) local departure/arrival times,
correct dates and readable money; (4) no IDs, hashes, UTC strings, machine labels,
or raw coverage dumps; (5) clear status, cabin evidence, fare scope, separate-ticket
conditions and incomplete-search limits; (6) no invented booking, availability,
protection, total-price or comparison claim. Compare with the linked baseline and
check the exact replay and failure counts in `receipt.json`.
