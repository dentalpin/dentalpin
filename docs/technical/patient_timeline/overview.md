---
module: patient_timeline
last_verified_commit: 0000000
---

# Patient Timeline — technical overview

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Auto-discovered facts about the `patient_timeline` module. See the module's
own notes at `backend/app/modules/patient_timeline/CLAUDE.md` for context
the scaffold could not infer.

## API surface

- `GET /api/v1/patient_timeline/patients/{patient_id}`

## Frontend

_This module ships no Nuxt pages._

## Permissions

`read`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** _(none)_
- **Subscribes:** `agenda.visit_note_updated`, `appointment.cancelled`, `appointment.checked_in`, `appointment.completed`, `appointment.confirmed`, `appointment.in_treatment`, `appointment.no_show`, `appointment.scheduled`, `budget.accepted`, `budget.expired`, `budget.rejected`, `budget.reminder_sent`, `budget.renegotiated`, `budget.sent`, `budget.viewed`, `clinical_notes.administrative_created`, `clinical_notes.appointment_administrative_created`, `clinical_notes.appointment_clinical_created`, `clinical_notes.diagnosis_created`, `clinical_notes.plan_created`, `clinical_notes.treatment_created`, `document.uploaded`, `email.failed`, `email.sent`, `invoice.issued`, `invoice.paid`, `media.pair_created`, `media.photo_uploaded`, `odontogram.treatment.performed`, `patient.medical_updated`, `treatment_plan.closed`, `treatment_plan.confirmed`, `treatment_plan.created`, `treatment_plan.item_completed_without_note`, `treatment_plan.reactivated`, `treatment_plan.treatment_completed`

See [`./events.md`](./events.md) for the per-event detail (when the
module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/patient_timeline/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
