# 0004: Model-normalized location names are resolver candidates

- Status: Approved

## Context

The intent extractor can recognize that `SF`, `San Francisco`, and similar surface forms refer to
the same place, but model-generated spelling, spacing, and diacritics are not deterministic. A
future city-to-airport map needs a stable geographic key rather than a display string. The current
milestone does not include location resolution or airport expansion.

## Options

1. Treat the model-generated normalized string as the canonical location key.
2. Preserve only the user's verbatim string and defer all semantic normalization.
3. Ask the model for a normalized semantic-name candidate, then let a later deterministic resolver
   validate it and assign a stable location identifier.

## Decision

Choose option 3. `LocationRef.raw_text` remains exact request evidence. `LocationRef.value` is a
model-proposed normalized semantic-name candidate, not an authoritative canonical name or stable
identifier. The model must preserve ambiguity rather than silently selecting among multiple places.

Until deterministic resolution exists, eval goldens may enumerate accepted candidate strings.
Matching is exact membership in those explicit aliases; unrestricted fuzzy matching is prohibited.
Wrong kinds, wrong geographic meanings, and omitted locations remain failures.

Location resolution and city-to-airport expansion are separate stages. A future resolver will own
stable entity IDs and canonical display names. Search planning will own airport-set expansion and
policies such as whether San Francisco includes SFO only or the wider Bay Area.

## Consequences

- The model can help expand abbreviations and repair obvious spelling without becoming the source
  of truth for location identity.
- Current evals do not fail solely because of an explicitly accepted display-string variant.
- Downstream airport maps will be keyed by stable resolved entities rather than model strings.
- A deterministic location catalog and ambiguity policy are still required before search planning.

## Evaluation

- Assert verbatim `raw_text` preservation where it matters.
- Accept only explicit per-golden candidate aliases.
- Verify that unlisted variants do not match accidentally.
- Continue failing omitted locations, incorrect kinds, and different geographic entities.

## Revisit trigger

Revisit when deterministic location resolution is implemented or when search planning needs the
first city-to-airport mapping.

Approved by the project owner on 2026-08-31.
