# Patients clinical module

Normalized medical history, allergies, medications, emergency contacts.
Separate from `patients` because the data is sensitive and should be
gated by clinical roles.

## Public API

Routes mounted at `/api/v1/patients_clinical/`.

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

- **The medical-history PUT replaces everything** (#1045), so the client
  only saves a history it loaded (`isLoaded`), and the edit modal works on
  a copy: never hand the live object to `MedicalHistoryForm` for editing.

- **Hygienists do NOT have write access** to medical history.
  Receptionists read only emergency contacts (in some clinic
  configurations not even that — check role policy).
- **Gate every medical read on `medical.read` in the client** (#1268).
  `useApi` toasts a 403 even when the caller catches it, so
  `useMedicalHistory`, `usePatientAlerts` and the patient page's alerts
  call skip the request without `PERMISSIONS.medicalHistory.read`.
- **Allergies and medications drive UI alerts.** Schema changes here
  affect the patient header banner — coordinate frontend.
- **Audit every write.** This is the most sensitive surface in the
  product after billing.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0005-relative-permissions.md`

## CHANGELOG

See `./CHANGELOG.md`.
