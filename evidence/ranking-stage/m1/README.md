# Ranking M1 saved matching results

These are deterministic local development outputs from the two [plan-linked Provider Stage
runs](../../provider-stage/saved-searches/README.md). Each `MatchedJourneySet` embeds its frozen
request, compiled plan, full provider result, validation reasons, and pairing receipts. It
preserves the provider's partial coverage and unknown fields. No provider or model call was
made to create these files.

| Input run | Output | Direct award | Mixed conditional | Mixed rejected | Scoped mixed pairs |
| --- | --- | ---: | ---: | ---: | ---: |
| `mixed_access` | [JSON](mixed_access.json) | 17 admitted | 240 | 216 | 456 |
| `exact_business` | [JSON](exact_business.json) | 0 | 106 | 290 | 396 |

The mixed options that pass route and schedule checks remain **conditional** because returned
traveler, cabin, or positioning-permission evidence is unresolved. The 17 admitted direct awards
pass the modeled M1 checks for that request; their price evidence remains incomplete, and
admission is not a booking or availability guarantee. Direct cash benchmarks are retained
separately and never become award-led journeys. Source duplicates remain distinct observations
and candidate variants.

Rebuild a result from the repository root with the offline command, choosing a new output path:

```sh
PYTHONPATH=src .venv/bin/python -m award_agent.cli.ranking_match \
  --bundle evidence/provider-stage/saved-searches/runs/mixed_access/bundle.json \
  --result evidence/provider-stage/saved-searches/runs/mixed_access/result.json \
  --output /private/tmp/mixed-access-m1.json
```

The saved output SHA-256 digests are:

- `mixed_access.json`: `38a897a175c37561e3dc21c7104edc37453afffee85bef3876219391204eb3f7`
- `exact_business.json`: `46ead3748ff5a6dcdac48a41861efe1a88fb7b7d31a1b0b2562135aea520ff3b`

The cash egress and next-day boundary tests use synthetic fixtures because the saved live runs
contain access positioning only. M1 does not rank these candidates or produce user-facing
recommendations.
