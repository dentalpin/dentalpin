---
module: imaging_ai
last_verified_commit: ad339611ade2847809b6478a60a7a1354990b432
---

# imaging_ai — events

| Event | Direction | Payload | Notes |
|---|---|---|---|
| `imaging.ai_job_done` | emits | `job_id`, `clinic_id`, `patient_id`, `status` | Fired on reaching a terminal state (`done`/`failed`). Timeline audit. |
| `imaging.ai_job_confirmed` | emits | `job_id`, `clinic_id`, `patient_id`, `confirmed_by` | Fired when a clinician confirms drafts (authorizes a proposed run or records the draft review). |
