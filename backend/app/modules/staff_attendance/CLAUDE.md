# staff_attendance module

Clock in/out events for clinic staff, current state, and a daily pairing
report. No shifts, rosters, overtime math, or payroll linkage.

## Public API

Routes mounted at `/api/v1/staff_attendance/`.

- `POST   /events` — clock in/out (409 on consecutive same-kind); `staff_attendance.write`
- `GET    /members` — active clinic members for the picker; `staff_attendance.read`
- `GET    /events` — list (user/day filters); `staff_attendance.read`
- `GET    /status/{user_id}` — current state; `staff_attendance.read`
- `GET    /report?day=` — paired seconds per member, open flag; `staff_attendance.read`

Events are append-only; corrections happen via a later opposite punch,
never rewrite.

## Events published

- `staff_attendance.clocked` on every punch — payload: `event_id`,
  `clinic_id`, `user_id`, `kind`, `created_by` (nullable). Consumed by
  `activity_journal`.

## Dependencies

None (core auth reads only — users are global rows, gated by
clinic membership). Payroll linkage deliberately absent.

## Permissions

`staff_attendance.read`, `staff_attendance.write` (dentist/assistant/
receptionist rw, hygienist read).

## Frontend

`pages/attendance/index.vue` — clock form, today feed, daily report.

## Later (out of scope, needs its own design)

- Shift templates + rosters + planned-vs-actual.
- Overtime math + payroll linkage (payroll owns amounts).
- Absence flags.
- Kiosk/PIN clocking (no shared-device auth today).

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Own Alembic branch (`staff_attendance`, `satt_0001`).

## CHANGELOG

See `./CHANGELOG.md`.
