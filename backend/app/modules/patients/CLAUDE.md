# Patients module

Patient identity: name, contact, demographics, status. Foundational
module — most other modules depend on it. Soft-deleted via `status`,
never hard-deleted.

## Public API

Routes mounted at `/api/v1/patients/`.

- `GET    /patients`        — list (paginated); `patients.read`
- `GET    /patients/{id}`   — detail; `patients.read`
- `POST   /patients`        — create; `patients.write`
- `POST   /patients/import.csv` — CSV import (dry-run default, `dry_run=false`
  commits; validation reuses `PatientCreate`); `patients.write`
- `PUT    /patients/{id}`   — update; `patients.write`
- `DELETE /patients/{id}`   — soft-archive (status → archived); `patients.write`

## Dependencies

`manifest.depends = []`. Foundational. **Other modules may declare
`depends: ["patients"]`** — keeping this module stable matters for the
whole system.

## Permissions

`patients.read`, `patients.write` (declared relative; registry
namespaces them).

## Tools exposed

Agent tools in `tools.py` (wrap `PatientService`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `search_patients` | READ | `PatientService.list_patients` | `patients.read` |
| `get_patient` | READ | `PatientService.get_patient` | `patients.read` |
| `create_patient` | WRITE | `PatientService.create_patient` | `patients.write` |
| `import_patients_csv` | WRITE | `csv_import.validate/import` (dry-run default) | `patients.write` |
| `update_patient` | WRITE | `PatientService.update_patient` | `patients.write` |

`update_patient` covers contact data only (phone, email) — identity
fields stay manual.

## Events emitted

| Event | When | Payload keys |
|---|---|---|
| `patient.created` | `PatientService.create` succeeds | `patient_id`, `clinic_id` |
| `patient.updated` | `PatientService.update` succeeds | `patient_id`, `clinic_id`, `changes` |
| `patient.archived` | `PatientService.archive` (soft-delete) | `patient_id`, `clinic_id` |

See `service.py:113`, `service.py:131`, `service.py:142`.

## Events consumed

None.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=False` —
  removing patients would orphan most of the system.

## Gotchas

- **Soft delete only.** `DELETE /patients/{id}` flips `status` to
  archived; the row stays. Do not add a hard-delete endpoint.
- **Multi-tenancy.** Every query MUST filter `Patient.clinic_id`.
  This includes future agent tools.
- **No cross-module FKs into patients without `depends: ["patients"]`**
  in the consuming module's manifest.
- **`do_not_contact` flag** — operational opt-out used by recalls and
  any future outreach module. Sibling modules MUST filter
  `Patient.do_not_contact == False` in addition to the
  `Patient.status != "archived"` filter when building call/outreach
  lists.
- **Patient-detail slots** — three stable contracts exposed by this
  module so siblings can plug into the patient file without imports:
  - `patient.summary.cards` — entries in the Resumen grid. Ctx
    `{ patient }`. Order convention: 10 plan, 20 next appointment,
    30 balance, 40 diagnoses, 50 medical history, 60 quick actions.
  - `patient.header.alerts` — clinical chips inside
    ``PatientStickyHeader``. Ctx `{ patient }`. Owner: ``patients_clinical``.
  - `patient.summary.actions` — module-contributed action buttons
    (recalls "Set recall", etc.). Rendered in both the sticky header
    and the Quick-Actions card. Ctx `{ patient }`. Kept under its
    legacy name so existing registrations keep working.
  - `patient.detail.administracion.payments` — owned by ``payments``,
    drives the Cobros sub-mode in the Administración tab.
  - `patient.detail.sidebar` — deprecated, kept registered for
    community modules. Renders as a section at the bottom of Resumen.
  - `patient.diagnosis.subtabs` — optional sub-tabs rendered inside
    the *Diagnosis* mode of `ClinicalTab`, alongside the implicit
    "Odontograma" tab. Ctx `{ patientId, readonly? }`. Order
    convention: 10 odontogram (implicit), 20 periodontogram. With
    zero registered entries `DiagnosisModeContainer.vue` falls back
    to the bare `<DiagnosisMode>` render — uninstalling every
    optional consumer restores the pre-slot UI verbatim.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0005-relative-permissions.md`

## CHANGELOG

See `./CHANGELOG.md`.
