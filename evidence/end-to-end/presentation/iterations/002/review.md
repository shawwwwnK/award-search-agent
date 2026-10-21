# Iteration 002 review

Status: agent review rejected the admitted answer; owner review pending.
The conditional and incomplete cases were held because a separate review found
v4 checker and notice edges affecting those cases, and the admitted answer still
needs correction. This iteration has one live Results-only case.

The revised answer uses compact option sections and no raw source ID appears in
its final notices. It remains annotated with ten visible “Please check” notices.
Every selected journey omitted the `award_program`, `status`, and `styles` bindings,
so the checker inserted those three facts after the option. The cash comparison
also has a declared sentence that is not literally visible and receives a notice.
The traveler prose repeats dates (“Depart Jan 15, 2027 at Jan 15, 2027 at…”),
puts the full-sentence quote-scope slot inside another sentence, and repeats
booking and cabin caveats. The result is not product-ready.

The run used the identical saved admitted Ranking export as iteration 001 and
made two live Results authoring calls. Exact replay matched the saved answer;
source and code hashes were unchanged during both calls. Across attempts the
artifact records 785,756 and 789,701 counted input tokens, 6,540 and 6,869
output tokens, 25 failed findings and 14 unchecked findings. These counts apply
only to this experimental case. The exact Results package and dependency
versions are archived with this iteration for historical replay.

Next iteration needs to keep every required factual binding visible without
mechanical labels, treat each product slot as a complete value or sentence as
documented, and use local time slots without adding duplicate date prefixes.
The v4 checker/notice issues identified separately for empty-result and
incomplete-result cases should be resolved before expanding the live cohort.
