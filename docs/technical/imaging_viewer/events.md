---
module: imaging_viewer
last_verified_commit: 0000000
---

# imaging_viewer — events

| Event | Direction | Payload | Notes |
|---|---|---|---|
| `imaging.study_indexed` | emits | `study_id`, `clinic_id`, `patient_id`, `document_id`, `study_uid` | Fired on every index (manual + auto-index). Timeline audit. |
| `media.photo_uploaded` | subscribes | `document_id`, `clinic_id`, `patient_id`, … | Auto-indexes DICOM-mime uploads only; best-effort, never raises. |
| `patient.archived` | subscribes | `patient_id`, `clinic_id` | Cascade soft-archive of the patient's studies. |
