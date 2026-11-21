---
module: online_booking
last_verified_commit: 0000000
---
# Permissions

`online_booking.settings` controls configuration; `online_booking.read` permits listing requests; `online_booking.write` permits decisions. Acceptance additionally requires `agenda.appointments.write` and `patients.write`. Public routes do not use staff sessions and must be exposed separately from the private API.
