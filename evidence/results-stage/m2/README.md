# Results M2 offline preparation and replay evidence

Generated with the public `prepare_results`, `run_results`, and `replay_results` APIs and a deterministic fixture writer. No model, network, or travel-provider calls were made. The fixtures are code-authored control documents, not model-authored quality evidence. They establish no semantic quality, M3 evaluation, model selection, live budget, practical context fit, bookability, provider reliability, or traveler-task benefit.

All alternatives from the three current Ranking M2 solution exports remain in each prepared source; no pruning was applied. Measurements include instructions, prepared source, slot catalog, strict response schema, and output reservation. UTF-8 bytes provide the recorded conservative upper bound with 100 tokens of protocol overhead. They are not model-specific token counts or a context-fit claim. Settings are explicit in `offline-config.json`; its `offline-fixture-only` model identifier is fictional and is not a live setting.

| Ranking export | Alternatives | Eligible complete | Components | Complete input bytes | Conservative total bound |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Mixed access](../../ranking-stage/m2/solutions/mixed_access.json) | 473 | 257 | 315 | 1,855,734 | 1,865,834 |
| [Exact business](../../ranking-stage/m2/solutions/exact_business.json) | 396 | 106 | 119 | 1,248,191 | 1,258,291 |
| [SFO to BKK positioning](../../ranking-stage/m2/solutions/sfo_to_bkk_positioning.json) | 123 | 64 | 115 | 601,136 | 611,236 |

Source file SHA-256 and prepared source digests, in table order:

- Mixed access: `c4e38eddaeb394f08f08e4bea6330a073c0ef74167da523aed604a7ad2b8a6e0`; prepared source `9cc7a7d55aad8699373bc273bf3476aaf66ed4c5a999d9c439d5649e147f45c8`.
- Exact business: `2e71c670f6266b81d9998300c5bddc8285cf2873ac9401e305e33bcd3007ff85`; prepared source `e47a32debb8074ffe135e16dfee181db484e6b7df13bbdcf84c8ed111746db91`.
- Positioning: `5faf6cc5d2bd1c43e0a3ae3c2d44a3eca5a71dcbb03960735011bc724097f6df`; prepared source `092349649a193ad6b51ce605d64d7386c604d757198a69c7c9f7906025681c45`.

The positioning export produced [clean](sfo_to_bkk_positioning.clean.md) and
[annotated](sfo_to_bkk_positioning.annotated.md) replay outputs for candidate
`f7d024bb65a87fe25bd14e71dbbf51c35f0a1995e3e9cc22fa112e677ed7eab9`. Each authored document
includes all four prepared shared slots and all 33 prepared slots for that journey. The clean fixture
used one deterministic writer call and had zero failed findings. The annotated fixture used two calls:
the initial draft made one false protected-connection claim, and the correction repeated it and added
a false business-cabin claim. The drafts had one and two failed findings, so the artifact retained the
initial draft with one local validation notice. Both serialized artifacts were reloaded with
`model_validate_json` and replayed byte-for-byte without a writer.

| Fixture | Outcome | Writer calls | Artifact bytes | Replay bytes | Replay SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| Clean | clean; 0 failed findings | 1 | 2,652,575 | 4,036 | `8bd98ea5c52b96a4f1376e52681cd5db5e79726d7241545ec77a522ba751c619` |
| Annotated | initial 1 failure, correction 2; initial retained | 2 | 2,659,062 | 4,291 | `19867135dffc366886e3bdae951f27ee33d0761626d67a3959100cf0ff365e45` |

The initial prompt digest is `c7835646d56f96cf876cffc6e041ea99722d4b137f34956b0f4b41064e8efb24`; the correction prompt digest is `91856e9a2f1a1dd5da80de25d51529bf2f20c25b5fddd9f5f4050d7e3fc602e5`. The strict schema digest is `e03e827838a5b97dda9f9a0cacf20d0c76830c98422bdfe3a941446adedd1dc5` for both attempts. `index.json` records exact source, configuration, artifact, draft, and replay digests, byte sizes, outcomes, call counts, slot coverage, and prompt/schema digests. Per-case API measurements are in `*.measurement.json`; `measurements.index.json` collects them.

Regenerate the checked-in evidence from the repository root:

```sh
.venv/bin/python evidence/results-stage/m2/generate.py
```

Generate into a separate directory for comparison:

```sh
.venv/bin/python evidence/results-stage/m2/generate.py --output-dir /private/tmp/results-m2-rebuild
```

The generator consumes canonical Ranking exports read-only. It writes only Results M2 output files and the copied fictional offline config in the selected output directory.
