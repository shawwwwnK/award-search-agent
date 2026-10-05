# Ranking M2 solution-export review

Date: 2026-10-04. Verdict: **ready for the declared export boundary; no remaining Critical/Important findings**.

An independent architect reviewed the uncommitted production exporter/contracts, package exports,
offline CLI/entry point, corpus script and preservation tests against the
[owner-approved contract](../handoffs/2026-10-04-ranking-m2-solution-export.md). Review was read-only.
The reviewer received requirements/source pointers rather than the parent's deliberation history.

| Finding | Verified disposition |
| --- | --- |
| Omitted detail work lost route/date context because executed query IDs were empty. | Resolve recorded logical scopes; retain omitted status and empty executed IDs. |
| Logical units could inherit unrelated batched physical routes. | Prefer unit-specific logical scope over physical batch scope. |
| Omitted cash work had neither executed IDs nor logical IDs. | Preserve separately resolved planned physical scope without claiming execution. |
| Discovery/provider/transport limitations were missing. | Typed issues, limitations, coverage and findings are carried into the view. |
| Reported cash flight numbers existed only in raw fields and were lost. | Explicitly copy flightNumbers, alongside observation-scoped MixedCabinPct; exclude other raw fields/booking tokens. |
| Receipt checked counts but accepted wrong candidate/coverage associations. | Validate its own associations, uniqueness, group membership and indexes; planted mutations reject. |
| Corpus hash omitted the written trailing newline; mutation check followed publish. | Hash exact written bytes and check source bytes before publication. |
| Repeated cost payloads and technical candidate links inflated the view. | Share normalized components and move technical provenance into the receipt, retaining all material facts and candidates. |

Reviewer verification: 28 export/CLI/corpus tests passed; separate mutation probes rejected wrong
candidate source links and nonexistent coverage groups. Omitted SFO–LAX cash work retained planned
October 5 context with empty executed-query IDs; JSON round-trip equality was checked.
Parent verification additionally passed 62 existing Ranking tests, scoped lint/type checks and
three saved-export byte/hash replays. Exact commands are in the
[build log](../build-log/2026-10-04-ranking-m2-solution-export.md).

Nonblocking limits remain explicit: host timezone database release is unpinned; compact views
retain full excluded records and measure 2,011,912 / 1,302,037 / 654,408 bytes. Frozen saved outputs
are available, but cross-host regeneration and model-context fit are unqualified.

The reviewer declined to judge upstream matching/style correctness, Results authorship/display,
model suitability, live provider qualification and owner acceptance because those are outside
this export review. No escalation was recommended. No Results runtime or model/provider calls ran.
