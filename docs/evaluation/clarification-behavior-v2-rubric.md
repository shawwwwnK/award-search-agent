# Clarification behavioral evaluation v2

This is ADR 0012's offline behavioral diagnostic suite. It supplements, and
does not replace, the exact ADR 0011 v1 conformance evaluator.

Every v2 scenario labels an answer as `reasonably_resolvable`,
`safely_assumable`, `ambiguous`, `conflict`, `nonanswer`, or `correction`.
Its oracle states the requirements that must resolve, fields that must not
change, separately permitted observed statuses and semantic actions, semantic properties, whether an approximation needs
a visible disclosure, and forbidden outcomes. It intentionally does not
require exact customer-service wording or an arbitrary fuzzy date range.
The answer-class label is the report's semantic-family dimension; distributions
and failure slices are emitted under that name.

The exact safety gate remains 100%: immutable initial snapshots, prompt
coverage compared in canonical order against blockers recomputed from the
effective request, protected-field preservation, valid bounded temporal values,
every oracle-required remaining blocker, and ready only when that authoritative
blocker collector is empty. Fuzzy
range quality is not an exact gate: the behavioral oracle accepts a bounded
envelope, such as several plausible early-month windows, rather than one
prewritten date range. Behavioral metrics are reported separately: false
blocking, incorrect acceptance, unnecessary clarification, turns to ready,
disclosure coverage, materially incorrect assumptions, valid-sibling retention,
targeted questions, generic repeats, and paraphrase compatibility.

The checked-in corpus is a disclosed development set. A private holdout belongs
under `evals/clarification/holdout/` and is gitignored. Holdout artifacts emit
only a corpus hash, family counts, aggregate metrics, and failure counts—never
fixture paths, scenario IDs, answer text, or turn records. Once a holdout case
is used for debugging, move it into a public regression family and replace it.

Paired `accept`/`ask` scenarios are executable anti-overfitting checks: the
accept side must not false-block a safely assumable answer, and the ask side
must not incorrectly resolve a material alternative.
Reports identify the evaluator and scripted-adapter versions, pool, class
slices, actual stop reasons, and their explicitly zero-variance deterministic
single-run label. Human review remains authoritative for whether an assumption is materially
surprising; these scores are diagnostic until the owner sets release thresholds.
