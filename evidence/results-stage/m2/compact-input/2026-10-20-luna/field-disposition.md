# Compact authoring field disposition

The canonical `SolutionProjection` and original Results facts/slots remain in the artifact. This manifest describes only the new writer input. It is not an eligibility or evidence-strength policy.

| Canonical fields | Writer representation | Local retention and rationale |
|---|---|---|
| Request origins, destinations, departure window, travelers, cabins, search modes, positioning permission, hard constraints, unknowns and conflicts | Resolved request fields | Preserve supported requirements and unresolved state |
| Request raw text and field-provenance lineage | Omitted | Canonical request retains original wording and evidence; the writer consumes resolved semantics |
| Request temporal contributions/context | Retained | Preserve time interpretation, context and explicit limitations |
| Matching policy version, Ranking style policy | Retained | Preserve eligibility/comparison interpretation and declared valuation assumptions |
| FX rates, date and source | Retained without snapshot hash/ID | Preserve conversion assumptions; local receipt retains identity and digest |
| Candidate, award and cash observation identities | J/A/C handles | Local typed maps retain exact canonical identities |
| Candidate status, topology, original route/date, local schedule, elapsed time, transfer airport/wait/day offset | Direct common journey facts | Preserve complete-journey meaning and schedule tradeoffs |
| Candidate award/cash observation links | Member-specific A/C references | Preserve exact components even when reported facts are grouped |
| Candidate price completeness, booking obligation, award cabin, premium-economy add-on and positioning reason | Retained | Preserve price, cabin and separate-ticket decisions |
| Candidate retrieval times through award/cash components | Exact member-specific timestamps | Never choose a latest representative or invent supersession |
| Option family, strategy, reason-set, cost and assessment IDs | Resolved facts or component references | Opaque identities remain canonical; the writer receives decision facts rather than machine joins |
| Matching reasons: code, dimension, state and detail | Resolved per-journey reasons | Preserve passed, failed and unknown requirements |
| Journey cost completeness, known/complete amounts and missing parts | Resolved cost facts | Preserve cost meaning; missing prices stay missing |
| Nested cost component kind, state, scope, reason and per-traveler amount | Resolved component facts | Preserve valuation limitations; original observation binding stays canonical |
| Exact cost fractions and microsecond arithmetic | Omitted from writer input | Canonical code remains authoritative for exact comparisons; no model arithmetic is added |
| Style, membership state, feature label, reasons and validation needs | Resolved assessments | Preserve style interpretations and conditional membership |
| Assessment numeric reference/threshold arithmetic | Local only | Policy, duration/cost facts and existing canonical checks retain comparison authority |
| Component kind, provider, origin/destination/date, airport sequence and schedule | Common component facts | Preserve award-summary/itinerary/cash distinctions and complete reported routing |
| Projected time local ISO and timezone | Retained | Preserve full local dates and calendar comparisons |
| Projected time instant when local time is absent | Retained fallback | Do not erase the sole known instant or invent a local time |
| Redundant instant when local ISO is present | Local only | Local ISO includes offset; canonical time arithmetic remains local |
| Component legs: endpoints, schedule, carrier, flight number and cabin | Retained with raw state/value | Preserve leg evidence independently of journey-level cabin |
| Reported component flight numbers | Retained from canonical component | Do not lose cash flight identity merely because the legacy prepared source omitted this field |
| Requested travelers/cabins and returned-traveler evidence | Retained | Distinguish requested party from provider-returned evidence |
| Cabin, program, points, taxes/fees, units/currency, seats, cash amount/currency, quote scope, duration, stops, carriers and mixed-cabin percentage | Raw state/value plus units/scope | Preserve absent/unknown/value distinctions and avoid inferring totals or uniform leg cabins |
| Component findings: code, severity, message and field | Retained from canonical component | Preserve unsupported-program, missing-tax and ambiguous-zero-seat warnings |
| RawField source-field paths | Local only | State/value and semantic findings remain visible; original field attribution remains canonical |
| Backend/version, provider-record ID, query/logical-use/strategy IDs | Local only | Full canonical values still constrain grouping; no machine lineage is needed in prose |
| Component observed time and provider-update evidence | Member-specific | Preserve exact capture binding independently of shared facts |
| Observation receipt and evidence hashes/raw local/timezone fields | Local only | Nonempty matching evidence and canonical facts govern grouping; hashes do not become inventory certainty |
| Full comparison pool IDs and exact canonical references | Local P1 expansion | Writer receives original pool count, supported time/cost reference and scope; display selection never narrows comparison authority |
| Benchmark and incomplete observation sets/dispositions | Explicit A/C catalogs | Every canonical lead/benchmark remains selectable under its original scope |
| Rejected candidates | Counts, route/date scope, failed reasons and separate unresolved caveats | Never selectable; full rejected records remain local; unknown prices alone are not reported as rejection causes |
| Coverage status, completeness, pair coverage, route/date scope, planning/discovery issues and limitations | Semantic coverage summary | Preserve acquisition limitations without query/transport ID lists |
| Coverage query/transport/unit/support identities | Local only | Detailed receipts remain in canonical projection |
| Repeated per-candidate required disclosure lists | D profiles referenced by journey facts | Exact key-set exceptions preserve mixed-cabin and equal-schedule rules |
| Shared/benchmark/incomplete disclosure rules, claim catalog, slot catalog and display vocabulary | Retained | Preserve visible disclosures, supported claims and slot grammar |
| Source digest, alias reverse maps and binding digests | Local only | Frozen maps/view are verified against canonical evidence without sending hashes to the model |

Grouping factors repeated reported facts; it does not delete candidates, merge observations, strengthen evidence, prove unique-flight identity, or choose which retrieval is authoritative. Each original member remains selectable. Uncertain equivalence leaves separate compact records.

Independent verification is retained in `offline/preservation_probe.py`, `offline/preservation_negative_controls.py` and their JSON results. These compare canonical fields directly rather than calling the serializer's internal fact-construction helpers. The initial probe exposed missing component findings; the corrected implementation passed the rerun. The isolated synthetic evidence-hash mutation deliberately bypasses projection-digest validation to test the grouping predicate alone.
