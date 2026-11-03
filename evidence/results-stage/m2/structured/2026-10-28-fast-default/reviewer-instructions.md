# Blind Results M2 answer review

Rubric clarification `fast-default-M2-v1.2-calibrated`, recorded before final
confirmation. This applies the existing ADR0029 boundary; it does not change
prior reviews. Read comparative advice in its local reference context:
“earlier than the displayed alternative” is not a claim of earliest arrival in
the full inventory. Missing a stronger representative is a coverage limitation
unless it falsifies or materially misleads the asserted argument. Record genuine
scope ambiguity rather than automatically assuming global optimality. C assesses
supported gains/losses beyond feasibility, without a strongest-representative
or exhaustive-frontier requirement. Preserve disagreements for adjudication.
See the repository's q020 adjudication for the dated disposition; do not consult
that other answer while reviewing an assigned blind bundle.

Prospective calibration after independent oracle review (same H/U/M2/C
requirements; original verdicts remain unchanged):

- Judge the displayed argument first. A meaningful local departure/arrival,
  cabin/points, connection or same-program quote/date tradeoff can be
  decision-rich without selecting the globally strongest representative.
  Another available choice can demonstrate that the source is not sparse; its
  omission alone does not erase a supported displayed tradeoff.
- A displayed alternative that is worse in every meaningful authored respect
  with no explained offsetting gain can still be basic. Do not require a
  particular cabin or number of options to correct that weakness.
- Evaluate a comparison target in the full surrounding passage. Preserve
  genuine ambiguity for adjudication; neither automatically assume a global
  claim nor automatically give an ambiguous statement a clean factual pass.
  An explicitly wrong source number or a comparison contradicted by its exact
  endpoints remains a hard failure.
- Read travel terminology with the actual itinerary description. A statement
  of nonstop travel contradicted by stops fails H; ambiguous use of “direct”
  alongside an explicit connecting itinerary is a clarity concern requiring
  context, rather than two independent source errors.

Read only the assigned `review-bundles/<id>/` directory until your judgment is
recorded. It contains `answer.md`, the selected authored `document.json`,
canonical `evidence.json`, and `references.json`. Do not inspect run names,
settings, tier, latency, token usage, or other review bundles before judging.
The bundle contains the draft selected for delivery after any correction; for V9
that is the artifact's `selected_pass_index`.

Judge these dimensions separately:

- **H (hard factual):** Pass only if material source facts, identities, roles,
  programs, airports, date/times, comparison direction, cabin scope, prices,
  fee and quote scope, seat counts, traveler support, transfer/protection and
  limitations are accurately stated. A mechanically clean document can fail H.
- **U (useful next action):** Pass only if the answer offers a defensible exact
  recommendation with a reason and downside, or truthfully explains that no
  complete journey exists and what useful lead/coverage evidence remains.
- **M2 composition:** Pass only if the answer reads as a coherent traveler
  recommendation, with individual explanations woven around embedded journey
  references, a supported comparison where alternatives add value, relevant
  cash context, and consolidated limitations. One strong recommendation is
  acceptable. A list of bare cards or unsupported sales prose fails.
- **C (comparative depth):** `decision-rich`, `basic`, or `insufficient`. Aim for
  decision-rich: the reader understands what each meaningful option gains and
  gives up, beyond simple feasibility. Use `sparse-source-exception` only when
  the source genuinely lacks a useful comparison; explain why. Do not impose
  a fixed option, cabin, style, or alternative quota.

For every H failure, quote the exact answer sentence and cite the canonical
source record and field that contradict it. Distinguish observed seats from
travelers requested and a journey's award cabin from each leg's cabin. An
unknown price scope cannot establish a total, zero fees, or a cross-program
value comparison. Check cash benchmark stop count and whether it is a separate
baseline, not an award recommendation. Check selected transfer joins and
offset-aware timing. Small unit errors matter when they change a decision.
All eligible explorer alternatives may challenge a central asserted tradeoff,
but do not require an exhaustive frontier or a quota. If a comparison is
underdetermined, record that rather than inventing a winner.

Use compact source inspection to avoid dumping entire artifacts. For example,
from the repository root:

```sh
PYTHONPATH=src .venv/bin/python -c 'import json,pathlib; p=pathlib.Path("BUNDLE/evidence.json"); x=json.loads(p.read_text()); print(x.keys())'
```

Replace `BUNDLE` with the assigned bundle directory and print only the fields
needed to investigate a claim. Save `review.json` in that bundle with the
following shape:

```json
{
  "rubric": "fast-default-M2-v1.2-calibrated",
  "H": "pass",
  "U": "pass",
  "M2": "pass",
  "C": "decision-rich",
  "sparse_source_exception": false,
  "findings": [],
  "reasoning": "Brief source-grounded explanation of the judgments."
}
```

For a failed dimension, add findings with `dimension`, `answer_quote`,
`canonical_reference`, `source_field`, `source_value`, and `explanation`.
Reviewers should record uncertainty and disagreements rather than converting
them into a clean pass. The parent integrates judgments with timing and replay
evidence after the blind review is saved.
