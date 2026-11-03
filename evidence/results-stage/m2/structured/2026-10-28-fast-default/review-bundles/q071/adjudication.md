# q071 traveler-support adjudication

Recorded 2026-10-28 against `fast-default-M2-v1.2-calibrated`.

**H: disputed.** Preserve the original H-fail review. This adjudication establishes neither a hard contradiction under every contextual reading nor an unqualified factual pass. Original U/M2 pass and decision-rich C remain unchanged; no sparse-source exception applies.

The disputed sentence is:

> Award seats and taxes/fees are unknown, and the results do not establish the traveler count or whether the separate-ticket combination is bookable.

The canonical [evidence](evidence.json) distinguishes three facts:

- `source.view.request.travelers` is **1**.
- Award component `14b3bb859ea1e228df21afeb9e3d11e5a5464c89b9df807499bb1c499647f0e8` has `returned_travelers.state = absent` and `seats.state = unknown`.
- Cash positioning component `c68429d41d46aa1be531319ac4b6eedeefab61d4e4fc24149a0ec7a4c616b388` has `returned_travelers.state = value`, `value = 1`, and `source_field = query.adults`.

Journey `0286e918614a7b41ec9aa8f5d5ec9042bf1bd5234d22fba3e9d968b1511b0bee` binds those exact components. Its `internal.reason_codes` includes `award_travelers_unknown`; the corresponding `reason_details` says the requested traveler count is not confirmed by the award result. That concerns support for the requested party, not knowledge of the request itself. The cash component's returned count does not establish award support, live award availability, or a known price scope.

The clause begins with award seats and fees, so its local context permits a narrower reading: the award result does not establish the party to which it applies. Under that reading, the known request count and cash echo do not contradict the statement. The broader wording, however, can also suggest that the requested count or all returned party evidence is unknown. It does not explicitly delimit the unknown to award support. This ambiguity prevents an unqualified pass.

The fixed [rubric](../../reviewer-instructions.md) requires evaluating a claim in its surrounding passage, preserving genuine ambiguity, and neither automatically treating an ambiguous statement as a global claim nor automatically granting it a clean factual pass. H covers accurate traveler support and limitations. Applying those rules produces **disputed**, rather than replacing the original finding with a clean pass or asserting that the source proves every contextual reading false. This remains unresolved for any gate requiring all answers to have an unqualified H pass.

A clarity revision, **not applied to the saved answer**, would be: “The request is for one traveler, but the award results do not verify support for that traveler. Current award availability and separate-ticket bookability remain unconfirmed.”

Verification: read the fixed rubric, assigned answer, original review and canonical request/component/journey fields before inspecting generation outputs. Subsequent trace inspection found the same ambiguous sentence in the draft and final answer; the editor retained it while changing program-associated point terminology. No timing data informed this adjudication. No runtime changes, live calls, new answer generation, or regrading of another answer was performed. Only separate adjudication files were added; the original review and answer remain intact. No escalation recommended.
