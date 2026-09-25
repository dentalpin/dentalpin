# staff_attendance — permissions

| Permission | Grants | Gated endpoints |
|---|---|---|
| `staff_attendance.read` | list events, members, status, report, page | `GET /events`, `GET /members`, `GET /status/{user_id}`, `GET /report` |
| `staff_attendance.write` | clock in/out | `POST /events` |

Role defaults: admin `*`, dentist/assistant/receptionist read+write,
hygienist read.
