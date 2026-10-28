# Independent diagnostic code review

An architect subagent reviewed candidate input, preservation audit, harness and
offline controls before live execution. Initial findings were fixed: exact count
response validation, noncompleted/refusal handling, reading-guide access for
analysis workers, per-count/check timing, unique named reservations and archived
source snapshots. The final review found no material blocker to medium sentinels.
The parent freshly ran offline harness controls, candidate audit, Ruff and diff
checks before calls. Candidate joins preserve all exact members, unknowns and roles.

One deliberate diagnostic difference: a noncompleted/refusal response is rejected
before document parsing, while the runtime structured adapter assigns those
subtypes after a parsing failure. No runtime code changes here. Report whether any
actual result is affected before comparing adoption outcomes.

During the third live run, raw `httpx.ReadTimeout` escaped SSE iteration because
only SDK `APIError` and `ValueError` were caught. Existing request/snapshot/ledger
remain unchanged and `failure-note.json` explicitly records the lost timing/usage.
The harness then added transport-error capture and a fake stream that raises after
partial events; the parent freshly reran `verify_harness.py` and Ruff successfully.
Subsequent snapshots distinguish this instrumentation fix from earlier runs. No
automatic retries were added. All source preparation and experimental input/model
settings remain unchanged by the fix.
