# Iteration 001 review

Status: agent review rejected the admitted answer; owner review pending.
The conditional and incomplete cases were intentionally not run in this iteration
after the admitted result exposed presentation and validation failures.

The admitted live answer uses local travel times, readable fares, and option labels.
It still contains six validation notices, including a raw 64-character benchmark ID.
The lead sentence repeats the coverage phrasing (“Search coverage was Search
coverage is…”). Three journey explanations assert that there are no unresolved
requirements even though the source retains an all-in-price requirement; two
of those claims fail directly and a third has an invalid claim scope. The
benchmark lacks the visible short label required by the v4 checker. The selected
options also use repetitive field lists and source terminology such as “quote
scope: unknown.” This is not a product-ready answer.

The run made two live Results authoring calls using the saved admitted Ranking
export. It delivered an annotated artifact with exact offline replay. Its receipt
records 785,660 and 791,039 counted input tokens, 8,317 and 6,398 output tokens,
34 failed findings across both attempts, nine unchecked findings, and one
insufficient-evidence finding. These counts describe this one experimental case,
not the full corpus. The Results source used for the call is archived in
`results-source-snapshot.zip` with hashes and dependency versions in
`source-snapshot.json`; restoring that source in an isolated checkout is needed
for exact historical replay after later v4 edits. Do not reinterpret a replay
failure under revised v4 code as a change to the saved 001 artifact.

Next iteration should prevent internal IDs in notices, tighten the writer's
eligibility language and visible label instruction, and avoid leading text that
duplicates complete coverage/status slot sentences. Then rerun the same admitted
source before widening to the conditional and incomplete cases.
