---
module: staff_attendance
screen: attendance
route: /attendance
last_verified_commit: c3a21e8f65cbef6fc5e97a025a86c5474f19cd76
related_endpoints:
  - POST /api/v1/staff_attendance/events
  - GET /api/v1/staff_attendance/members
  - GET /api/v1/staff_attendance/events
  - GET /api/v1/staff_attendance/status/{user_id}
  - GET /api/v1/staff_attendance/report
related_permissions:
  - staff_attendance.read
  - staff_attendance.write
related_paths:
  - backend/app/modules/staff_attendance/frontend/pages/attendance/index.vue
---

# Attendance

Found under the **Attendance** sidebar entry. Clock staff in and out,
see today's punches, and review the daily pairing report.

## What you can do

- **Clock** any clinic member in or out (front-desk flow included).
  Punching the same kind twice answers 409 — the roster, not the log,
  is where corrections happen (a later opposite punch supersedes).
- **Review** today's feed and the per-member daily totals, bucketed by
  the clinic's local day. Each feed line shows the punch time. An
  open (unpaired) punch is flagged and counted up to now, never past
  the end of the reported day; an overnight shift counts on the day
  it ends.
