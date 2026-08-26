# Patients clinical module

Normalized medical history, allergies, medications, emergency contacts.
Separate from `patients` because the data is sensitive and should be
gated by clinical roles.

## Public API

Routes mounted at `/api/v1/patients-clinical/`.

## Dependencies

`manifest.depends = ["patients"]`.

## Permissions

`patients_clinical.medical.{read,write}`,
`patients_clinical.emergency.{read,write}`.

## Events emitted

- Backend: `patient.medical_updated` — consumed by `patient_timeline`.
- Client (`useDataBus`, ADR 0021): a `patients_clinical` namespace tick
  is published after every successful medical-history save, so anonymous
  subscribers (e.g. medical_reference's patient warning chips) refetch
  without any coupling in either direction.

## Events consumed

- Client (`useDataBus`, ADR 0021): `usePatientAlerts` subscribes to this
  module's own `patients_clinical` tick so the header alert chips it
  registers into `patient.header.alerts` refresh after a save.

## Lifecycle

- `removable=False`. Clinical decisions reference this data.

## Gotchas

- **Hygienists do NOT have write access** to medical history.
  Receptionists read only emergency contacts (in some clinic
  configurations not even that — check role policy).
- **Allergies and medications drive UI alerts.** Schema changes here
  affect the patient header banner — coordinate frontend.
- **Audit every write.** This is the most sensitive surface in the
  product after billing.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0005-relative-permissions.md`

## CHANGELOG

See `./CHANGELOG.md`.
