# 0002: Use Nager.Holidays for U.S. federal-holiday anchor dates

- Status: Approved

> Refined by ADR 0003: the provider's grounded holiday date is now supplied to a second temporal
> model pass before deterministic proposal validation.

## Context

The request-understanding workflow supports holiday-based expressions, but its date resolver
previously hand-coded only Labor Day, Thanksgiving, and Christmas. The domain contract already
enumerates all U.S. federal holidays. The project is Python, while the offline Nager.Date package is
distributed for .NET and requires a license; Nager.Holidays also exposes a language-neutral REST
API.

## Options

1. Continue maintaining holiday formulas in Python.
2. Call Nager.Holidays directly from date-resolution code.
3. Put Nager.Holidays behind a narrow holiday-date interface and inject an offline fake in tests.

## Decision

Choose option 3. `NagerHolidayProvider` uses the Nager.Holidays Community API v4 for country `US`.
The resolver consumes only a `HolidayDateProvider`, uses the returned date as an anchor, and retains
deterministic ownership of date-window and relative-weekend arithmetic.

The workflow does not provide a hidden fallback. Network errors, invalid response data, absent
holidays, and conflicting dates raise `HolidayDateResolutionError`.

## Consequences

- Holiday-based CLI requests require Nager.Holidays availability.
- Exact, range, month, relative-month, and bound expressions remain network-independent.
- Unit tests stay offline by injecting fakes or a stub transport.
- The current provider is intentionally limited to `US` because the `Holiday` enum represents U.S.
  federal holidays and the request contract has no holiday-country field.
- API-supported year limits apply to holiday-based expressions.

## Evaluation

Test every holiday in the current enum against representative Nager API v4 data. Test API endpoint
construction, per-year caching, malformed payloads, absent holidays, and existing holiday-window
policies without live network access.

## Revisit trigger

Revisit when the request contract supports holidays from another country, Nager API lifecycle or
availability becomes unacceptable, or offline production resolution becomes a requirement.

Approved by the project owner on 2026-08-30.
