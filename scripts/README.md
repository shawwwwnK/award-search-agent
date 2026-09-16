# Scripts

Future reproducible maintenance and evaluation commands may be added here.
## Milestone 1 source preparation

`prepare_m1_source_subsets.py` is a local, dependency-free transformation of
the manually acquired, ignored GeoNames and OurAirports source files. It
creates `data/source-inputs/m1-current-travel-identity/`, a compact input
bundle for the future importer. It is not a planner snapshot and does not
perform network lookup, airport-group authoring, route inference, or provider
execution.

The script selects current countries; meaningful current populated places;
explicitly named region taxonomies; airport reconciliation candidates; current
language-tagged aliases; and the owner-approved OurAirports endpoint set. It
records filtered records, source IDs, checksums, and quarantine reasons in the
bundle manifest. For every retained source row it also preserves the complete
original header and ordered values in lossless source-record sidecars. Those
descriptive fields are inspection/provenance data only: they do not become
aliases, airport-serving evidence, group policy, routes, or provider claims.

Use it only with the documented local source acquisition from
`docs/build-log/2026-09-13-m1-source-acquisition.md`.

To refresh the data, download the current source files under their documented
names into `data/source-inputs/` alongside the existing bundle, then run:

```text
.venv/bin/python scripts/prepare_m1_source_subsets.py \
  --replace-existing-bundle
```

The preparation command rejects `--prune-raw`: it cannot establish that a
replacement SQLite catalog has been fully validated. Raw-source removal is a
separate, post-validation maintenance action; it is never part of catalog
publication or serving. Without
`--replace-existing-bundle`, the script refuses to overwrite an existing
bundle.
