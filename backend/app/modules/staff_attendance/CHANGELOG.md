# Changelog — staff_attendance

## Unreleased

- Initial module: clock in/out events (`POST /events`, 409 on
  consecutive same-kind punches), current state (`GET /status/{id}`),
  daily pairing report (`GET /report`, open shifts flagged).
- Clinic-scoped member picker (`GET /members`) — staff list reads the
  module endpoint, not the admin-only `/auth/users` surface.
- Attendance page (`/attendance` nav, order 93) with clock form,
  today feed, and report table; 10 layer locales.
- HTTP coverage for denied roles (403) and cross-clinic isolation.
- Later (own design): shifts, overtime, payroll linkage (see CLAUDE.md).
