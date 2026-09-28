# Provider parser fixtures

These raw response bodies are byte-for-byte copies of provider captures retained
as adapter regression fixtures so parser tests do not depend on the mutable
saved-search corpus. Original capture locations:

- `japan_sample.json` — `evidence/provider-stage/saved-searches/gfly/japan_sample.json`
- `mixed_exact__call-01.json` — `evidence/provider-stage/saved-searches/seats/search-contrasts/mixed_exact__call-01.json`
- `qatar_jfk_doh__call-01.json` — `evidence/provider-stage/saved-searches/seats/search-contrasts/qatar_jfk_doh__call-01.json`
- `japan_lax_hnd__call-01.json` — `evidence/provider-stage/saved-searches/seats/search-contrasts/japan_lax_hnd__call-01.json`
- `whole_month_pages__call-01.json` through `whole_month_pages__call-05.json` — matching filenames under `evidence/provider-stage/saved-searches/seats/pagination-and-details/`
- `qatar_inline_trips__call-01.json` and `qatar_get_trips__call-01.json` — matching filenames under `evidence/provider-stage/saved-searches/seats/pagination-and-details/`

The tests construct capture receipts around these bodies and compute the body
digest at runtime. These fixtures preserve provider payload content; they do
not stand in for the original capture receipt metadata.
