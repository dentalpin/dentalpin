---
module: patient_intake
last_verified_commit: 0000000
---

# Intake events

| Event | When published | Payload |
|---|---|---|
| `patient.updated` | Patient service applies selected contact fields | Clinic and patient IDs, changed field names |
| `patient.medical_updated` | Clinician applies clinical answers | Clinic, patient and user IDs, section and generic summary |
| `gdpr.consent.granted`, `gdpr.consent.withdrawn` | GDPR service appends a managed intake choice | Clinic, patient and consent IDs, canonical purpose |

The request owns the transaction. The medical timeline event follows commit because its subscriber uses a separate session. The reviewed answers and contact details
stay in the role-gated submission and patient record.
