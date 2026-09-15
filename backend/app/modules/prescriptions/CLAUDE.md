# prescriptions module

Clinical prescriptions with per-country compliance hooks (issue #269).
Country-agnostic base: drafts, issue/cancel lifecycle, templates,
prescriber profiles, PDF download/print.

## Public API

Routes mounted at `/api/v1/prescriptions/`.

- `GET    /patients/{id}/prescriptions` — list; `prescriptions.read`
- `POST   /patients/{id}/prescriptions` — create draft (201); `prescriptions.write`
- `GET    /prescriptions/{id}` — single; `prescriptions.read`
- `PATCH  /prescriptions/{id}` — edit draft (all-optional + `exclude_unset`); `prescriptions.write`
- `POST   /prescriptions/{id}/issue` — validate hook, freeze, emit; `prescriptions.issue`
- `POST   /prescriptions/{id}/cancel` — cancel (409 if already); `prescriptions.issue`
- `GET    /prescriptions/{id}/pdf` — PDF download (WeasyPrint, HTML fallback); `prescriptions.read`
- `GET    /patients/{id}/prescribe-warnings` — allergy/interaction banner (never blocking); `prescriptions.read`
- Templates CRUD under `/templates`; prescriber profile GET/PUT. No DELETE
  on prescriptions themselves (templates are config, not clinical
  records — their delete is allowed).

## Dependencies

`manifest.depends = ["patients"]`. Soft integrations without depends:
`patients_clinical` allergies (try-import), `medical_reference` flags
(registry-gated), catalog autofill (free-text + soft `catalog_ref`).

## Permissions

`prescriptions.read`, `prescriptions.write`, `prescriptions.issue`.
Admin/dentist `*`; others read-only (issuing stays prescriber-only).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_prescriptions` | READ | `list_for_patient` | `prescriptions.read` |
| `create_prescription_draft` | WRITE | `create_draft` (empty) | `prescriptions.write` |

Draft-only for the agent; issuing stays human.

## Events emitted / consumed

- Emits `prescription.issued` / `prescription.cancelled`
  (prescription_id, clinic_id, patient_id). Consumed by
  patient_timeline (added to its handler map).
- Consumes none.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`, but
  `uninstall()` raises while any issued prescription exists
  (clinical retention, verifactu precedent).
- Own Alembic branch (`prescriptions`, `psc_0001`, depends_on pat_0003).

## Gotchas

- **Issued rows freeze** — corrections are cancel + reissue; no PATCH,
  no DELETE, ever.
- **Prescriber snapshot at issue** — profile edits never rewrite history.
- **Hooks never return HTML** (PR #210 rule); PDF renderer escapes.
- **No email delivery** (MX pharmacies reject it).

## CHANGELOG

See `./CHANGELOG.md`.
