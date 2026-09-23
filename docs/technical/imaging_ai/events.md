---
module: imaging_ai
last_verified_commit: 0000000
---

# imaging_ai — events

| Event | Direction | Payload | Notes |
|---|---|---|---|
| `imaging.ai_job_done` | emits | `job_id`, `clinic_id`, `patient_id`, `study_id`, `status` | Fired on reaching a terminal state (`done`/`failed`). Timeline audit. |
