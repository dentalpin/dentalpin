# Changelog — staff_attendance

## Unreleased

- Follow-up: `AttendanceService.clock()` requires `created_by` (keyword-only)
  and the `clocked` payload no longer carries a null branch (review nit on #501).
- Follow-up: fold `satt_0002_created_by` back into `satt_0001`
  (`created_by` NOT NULL from the start — single-release module);
  dev DBs that applied `satt_0002` must re-stamp the branch.
- Follow-up: nav self-places under `practice`; screen docs mention
  the feed punch times; the attendance page imports the shared core
  `clinicToday()` instead of its own copy (review cross-ref).
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
  (NOT NULL column, folded into `satt_0001`), `staff_attendance.clocked` event.

- Initial module: clock in/out events (`POST /events`, 409 on
  consecutive same-kind punches), current state (`GET /status/{id}`),
  daily pairing report (`GET /report`, open shifts flagged).
- Clinic-scoped member picker (`GET /members`) — staff list reads the
  module endpoint, not the admin-only `/auth/users` surface.
- Attendance page (`/attendance` nav, order 93) with clock form,
  today feed, and report table; 10 layer locales.
- HTTP coverage for denied roles (403) and cross-clinic isolation.
- Later (own design): shifts, overtime, payroll linkage (see CLAUDE.md).
