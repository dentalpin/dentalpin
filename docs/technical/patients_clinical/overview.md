---
module: patients_clinical
last_verified_commit: 0000000
---

# Patients Clinical — technical overview

Deletes are soft-deletes (house rule: never hard-delete patient data).
`DELETE` endpoints answer 204 and set `status = "archived"`; list
endpoints show only active rows, single-item GETs still return archived
rows for history, contact upserts revive the 1:1 row, and the bulk
history replace archives the superseded set instead of destroying it
(`pc_0003`).

Auto-discovered facts about the `patients_clinical` module. See the module's
own notes at `backend/app/modules/patients_clinical/CLAUDE.md` for context
the scaffold could not infer.

## API surface

- `DELETE /api/v1/patients_clinical/patients/{patient_id}/allergies/{allergy_id}`
- `DELETE /api/v1/patients_clinical/patients/{patient_id}/emergency-contact`
- `DELETE /api/v1/patients_clinical/patients/{patient_id}/legal-guardian`
- `DELETE /api/v1/patients_clinical/patients/{patient_id}/medications/{medication_id}`
- `DELETE /api/v1/patients_clinical/patients/{patient_id}/surgical-history/{surgery_id}`
- `DELETE /api/v1/patients_clinical/patients/{patient_id}/systemic-diseases/{disease_id}`
- `GET /api/v1/patients_clinical/patients/{patient_id}/alerts`
- `GET /api/v1/patients_clinical/patients/{patient_id}/allergies`
- `GET /api/v1/patients_clinical/patients/{patient_id}/emergency-contact`
- `GET /api/v1/patients_clinical/patients/{patient_id}/legal-guardian`
- `GET /api/v1/patients_clinical/patients/{patient_id}/medical-context`
- `GET /api/v1/patients_clinical/patients/{patient_id}/medical-history`
- `GET /api/v1/patients_clinical/patients/{patient_id}/medications`
- `GET /api/v1/patients_clinical/patients/{patient_id}/surgical-history`
- `GET /api/v1/patients_clinical/patients/{patient_id}/systemic-diseases`
- `POST /api/v1/patients_clinical/patients/{patient_id}/allergies`
- `POST /api/v1/patients_clinical/patients/{patient_id}/medications`
- `POST /api/v1/patients_clinical/patients/{patient_id}/surgical-history`
- `POST /api/v1/patients_clinical/patients/{patient_id}/systemic-diseases`
- `PUT /api/v1/patients_clinical/patients/{patient_id}/allergies/{allergy_id}`
- `PUT /api/v1/patients_clinical/patients/{patient_id}/emergency-contact`
- `PUT /api/v1/patients_clinical/patients/{patient_id}/legal-guardian`
- `PUT /api/v1/patients_clinical/patients/{patient_id}/medical-context`
- `PUT /api/v1/patients_clinical/patients/{patient_id}/medical-history`
- `PUT /api/v1/patients_clinical/patients/{patient_id}/medications/{medication_id}`
- `PUT /api/v1/patients_clinical/patients/{patient_id}/surgical-history/{surgery_id}`
- `PUT /api/v1/patients_clinical/patients/{patient_id}/systemic-diseases/{disease_id}`

## Frontend

_This module ships no Nuxt pages._

## Permissions

`medical.read`, `medical.write`, `emergency.read`, `emergency.write`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** _(none)_
- **Subscribes:** _(none)_

module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/patients_clinical/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
