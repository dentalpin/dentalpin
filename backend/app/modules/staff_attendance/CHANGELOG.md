# Changelog — staff_attendance

## Unreleased

- Maintainer round 3: reject future-dated punches (422 past now + 5 min
  skew), cross-day open shifts appear on later days (pre-window
  unclosed `in` seeds the report), `punch()` reads the API `message`
  envelope via `errorDetail()`; day feed shows punch times; events.md +
  CLAUDE.md document the `staff_attendance.clocked` payload.
- Round 2: pairs clip to the window on both ends (multi-day sums are
  exact), `open` means no closing punch exists at all (forward query),
  half-open day windows, single toast on 409 (`errorToast: false`).

- Clinic-local day windows (`Clinic.timezone`, naive input = wall clock),
  positional duplicate guard (neighbours, not tail), overnight-shift
  carry-over with day-boundary cap, `created_by` on every punch
  (new nullable column, `satt_0002`), `staff_attendance.clocked` event.

- Initial module: clock in/out events (`POST /events`, 409 on
  consecutive same-kind punches), current state (`GET /status/{id}`),
  daily pairing report (`GET /report`, open shifts flagged).
- Clinic-scoped member picker (`GET /members`) — staff list reads the
  module endpoint, not the admin-only `/auth/users` surface.
- Attendance page (`/attendance` nav, order 93) with clock form,
  today feed, and report table; 10 layer locales.
- HTTP coverage for denied roles (403) and cross-clinic isolation.
- Later (own design): shifts, overtime, payroll linkage (see CLAUDE.md).
