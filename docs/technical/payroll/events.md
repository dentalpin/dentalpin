---
module: payroll
last_verified_commit: 0f333000
---

# payroll — events

| Event | When | Payload keys |
|---|---|---|
| `payroll.profile.updated` | profile created or updated | `clinic_id`, `profile_id`, `user_id` |
| `payroll.period.status_changed` | period transitions | `clinic_id`, `period_id`, `month`, `from_status`, `to_status` |

Payloads are masked by contract: ids and statuses only — never
amounts, bank/tax values (plaintext or ciphertext), or notes. No
bundled subscriber; `activity_journal` may subscribe without importing
payroll.
