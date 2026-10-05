# Build Log

Build logs capture lightweight evidence from real development sessions. They should not become detailed diaries.

Their purpose is to preserve:

- what was attempted;
- what worked;
- what failed;
- what was measured;
- what changed;
- what was learned;
- what the next cut line is.

Each meaningful session records its ADR disposition: IDs created/amended, or a brief reason
no consequential architectural decision changed. Apply [the ADR workflow](../adr/README.md)
before closeout or commit. Link accepted decisions rather than relying on a build-log entry
as their only durable record. Preserve owner conclusions separately from agent analysis and
unsettled proposals. Documentation-only sessions use link/consistency checks; behavior changes
require appropriate tests.
