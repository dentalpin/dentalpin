---
module: patient_intake
last_verified_commit: 0000000
---

# Intake permissions

Routes are mounted under `/api/v1/patient_intake`.

| Permission | Endpoints | Default grant |
|---|---|---|
| `patient_intake.configure` | `POST /forms`, `PUT /retention` | Administrator |
| `patient_intake.issue` | `GET /forms`, `POST /intakes` | Reception |
| `patient_intake.review_admin` | `GET /patients/{patient_id}/pending/admin`, `GET /intakes/{intake_id}/admin`, `POST /intakes/{intake_id}/admin`, `POST /intakes/{intake_id}/discard` | Reception |
| `patient_intake.review_clinical` | `GET /patients/{patient_id}/pending/clinical`, `GET /intakes/{intake_id}/clinical`, `POST /intakes/{intake_id}/clinical` | Dentist |
| `patient_intake.withdraw` | `POST /patients/{patient_id}/consents/{purpose}/withdraw` | Reception |

Administrators have the module wildcard. Administrative application also
requires `patients.write` and `gdpr.consents.write`. Clinical reads require
`patients_clinical.medical.read` and application requires
`patients_clinical.medical.write`. Withdrawal requires `gdpr.consents.write`.
Detail reads use the patient access log.
