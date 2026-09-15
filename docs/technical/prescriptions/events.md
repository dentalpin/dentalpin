# prescriptions — events

| Event | When | Payload keys |
|---|---|---|
| `prescription.issued` | draft issued | `prescription_id`, `clinic_id`, `patient_id` |
| `prescription.cancelled` | issued/draft cancelled | `prescription_id`, `clinic_id`, `patient_id` |

Consumed by `patient_timeline` (added to its handler map).
