# Scripts

Future reproducible maintenance and evaluation commands may be added here, but no scripts are required for this scaffold task.
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
bundle manifest. It verifies the bundle before an optional `--prune-raw`
removes only source files that the bundle supersedes.

Use it only with the documented local source acquisition from
`docs/build-log/2026-09-13-m1-source-acquisition.md`.
