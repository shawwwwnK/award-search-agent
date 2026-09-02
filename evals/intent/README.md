# Intent Evals

These scenarios will become an executable golden set.

Exact checks should be used for schema and deterministic behavior. Invariants should be used where multiple valid semantic representations exist.

Temporal evidence is evaluated per typed claim rather than as an exact set of preferred phrases.
Executable fixtures use `evidence_expectations` with exact allowed envelopes, required-all
fragments, required-any groups, and optional preferred spans. Fixture strings compile to Python
start-inclusive/end-exclusive offsets before scoring; missing or ambiguous fixture strings fail
loading. Candidate evidence remains subject to strict exact-substring grounding, must fit one
common envelope for its linked claim, and must cover the claim's required fragments. Preferred span
agreement is recorded only as a prompt-quality diagnostic and does not determine case success.

Location `raw_text` is verbatim evidence. Location `value` is a model-proposed normalized name
candidate until a deterministic location resolver exists; it is not a stable identifier or an
authoritative display name. Instead of one exact `value`, a golden may use `accepted_values` to
enumerate semantically equivalent candidate strings. The scorer performs exact membership only and
never fuzzy matching.

Live-model evals and offline deterministic tests must be separable. Baseline results should be saved under `evals/intent/baseline/`.

Temporal evaluation is split by responsibility. `temporal_relations` expectations partially match
typed semantic invariants such as kind, target, reference, direction, ordinal, weekday, and unit;
they intentionally ignore equivalent evidence-span segmentation and unlisted trace fields. Final
`departure_window`, `return_window`, duration, conflict, and clarification checks score the
deterministic evaluator and end-to-end workflow separately. Calendar arithmetic belongs in offline
unit tests rather than live-model scoring.

Failing cases should be preserved and investigated rather than deleted. Evaluation should drive architecture changes rather than merely produce a score.

## Live baseline runner

Run only scenarios marked `status: ready` and save the full structured output:

```bash
python -m award_agent.cli.intent_eval \
  --model gpt-4o-mini \
  --trials 3 \
  --output evals/intent/baseline/YYYY-MM-DD-gpt-4o-mini-3-trials.json
```

The runner scores explicit structured expectations and keeps individual failures and errors from
aborting the corpus. Free-text invariants are retained in the artifact for human review but are not
included in the automatic pass rate. The current OpenAI adapter does not retain response usage, so
the artifact cannot yet report token counts or cost.

Use `--strategy one_pass` for the deliberately naive experiment arm. It sends only the raw request
and context to one model call and asks directly for `RequestUnderstandingResult`; it does not run
the production workflow's extraction, enrichment, temporal validation, conflict, or clarification
stages. The golden expected values are used only by the scorer after generation and are never sent
to the model.
