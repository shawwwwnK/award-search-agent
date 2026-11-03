# Results direction after owner prototype review

2026-10-29. Owner decisions: keep Luna's natural wording; full-cash journey context
is one comparison sentence; recommendations retain Ranking categorization. Other
prototype questions are superseded, not independently answered.

## Trace

Ranking exports time/cost/premium assessments and indexes under the approved
styles contract. `interactive_packet.py:98,139` retains them in full selector
input. `focused_packet.py:455` restricts the authoring pool to chosen journeys.
`focused_records.py:29` retains selected facts including styles, while its retained
fields at75 omit global Ranking indexes. The selector treats highlights as a
starting point; the writer asks for a defensible choice and alternatives, without
a category-led requirement or a one-sentence cash limit. Thus categories survive
as facts but need not survive the answer. In saved q108/q119 source there are
11time members,116premium members and0cost members. q119 displays two time-member
economy options and cash, omitting premium. No new live execution was performed.

## Direction and changes

Accepted product direction is recorded in ADR0029/index, current project state
and Results contract. The inline-binding prototype proposal is marked rejected;
its historical examples remain, with an owner-decision banner. Questions C/D are
withdrawn/superseded. No historical verdicts are changed.

The next cut should restore the category-to-selection-to-authoring handoff and
make pure-cash context brief. Preserve overlap, exact membership, conditional
requirements and provisional cost states; no invented one-per-category quota or
new ranking. No complete journey means no styled recommendation; research leads
stay explicitly separate. Cash positioning inside award-led recommendations is
not covered by the brief full-cash benchmark rule.

No product code, tests, config, Ranking behavior, live model/provider/FX calls,
default adoption or paid-campaign restart. No M2/M3 closeout. ADR disposition:
amended0029 for accepted owner wording/presentation direction; no new ADR number.
Verification: read-only source/contract trace and independent investigator report;
prototype rebuild and DOM-logic smoke check; local-link/diff checks recorded at
closeout. The classification handoff itself remains to be implemented and tested.

## Documentation-only handover closeout

The owner explicitly requested no implementation and a new-session handover,
including the main iteration cycles through V30. Created the
[handover](../handoffs/2026-10-29-results-m2-fast-profile-handover.md), linked it
from current state/contracts/ADR index/plan and AGENTS, and marked the old V3
handoff and pending prototype decisions historical. Reconciled the campaign
README's V19 review status, V21 timings, V27 case/timing mapping and V28 selector
failure description against preserved evidence. No source response, original
review grade, runtime, test or configuration was changed.

ADR disposition: amended0029 and index for the already-authorized product
direction and documentation-only stop; no new ADR or workflow policy required.
G06/G08 remain open as recorded in DEFERRED; no new work was parked or qualified.
Verification: documentation link checks, unchanged source/test byte inventory,
HEAD check and git diff whitespace check are recorded at completion below.
No model, provider or FX calls, and no commit.

Completion checks: all297 local links across12 touched documentation files resolve;
all295 Python source/test files match the pre-handover byte inventory. `git diff
--check` passes. HEAD remains `b7bedf5b13daab0ec0d170ba0b519877698ae0ff`.
No runtime tests were rerun for this documentation-only closeout; earlier test
and strict-verifier limitations remain stated in the handover.
