# Orthodontics module

Orthodontic case tracking: monthly controls, archwires, photo
evolution, one-quote monthly collection (issue #270). **Optional,
removable**.

## Public API

- Routes mounted at `/api/v1/orthodontics/`.
  - `POST   /cases` — `orthodontics.cases.write`
  - `GET    /cases?patient_id&status` — `orthodontics.cases.read`
  - `GET    /cases/{id}` — `orthodontics.cases.read`
  - `PATCH  /cases/{id}` — `orthodontics.cases.write` (all-optional + `exclude_unset`)
  - `POST   /cases/{id}/status` — `orthodontics.cases.write`
  - `POST   /cases/{id}/controls` — `orthodontics.controls.write` (201)
  - `GET    /cases/{id}/controls` — `orthodontics.cases.read`
  - `PATCH  /controls/{id}` — `orthodontics.controls.write`
  - `GET    /settings` — `orthodontics.cases.read` (lazy-seeds chip catalogs)
  - `POST   /cases/{id}/plan-link` — `orthodontics.cases.write`
  - `DELETE /cases/{id}/plan-link` — `orthodontics.cases.write`
  - `POST   /cases/{id}/schedule` — `orthodontics.cases.write` (201)
  - `GET    /cases/{id}/installments` — `orthodontics.cases.read`
  - `PUT    /settings` — `orthodontics.settings.manage` (chip catalogs)

## Dependencies

`manifest.depends = ["patients", "agenda", "media", "recalls", "treatment_plan"]`.
Plan sessions are written only through `TreatmentPlanService`;
recalls only through `RecallService.create` (duplicate-guarded).

## Permissions

`orthodontics.cases.read`, `orthodontics.cases.write`,
`orthodontics.controls.write`, `orthodontics.settings.manage`.

## Events emitted

| Event | When | Payload keys |
|---|---|---|
| `orthodontics.case_created` | case created | `case_id`, `clinic_id`, `patient_id`, `appliance_type` |
| `orthodontics.case_status_changed` | status transition | `case_id`, `clinic_id`, `patient_id`, `previous_status`, `status`, `previous_finished_at` |
| `orthodontics.control_registered` | control registered | `case_id`, `control_id`, `clinic_id`, `patient_id`, wires, `procedures`, `next_due` |

Consumed by `patient_timeline` (payload-only rows).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `get_ortho_case_status` | READ | `OrthoCaseService.get` | `orthodontics.cases.read` |
| `list_overdue_ortho_controls` | READ | `OrthoCaseService.list_overdue` | `orthodontics.cases.read` |
| `register_ortho_control` | WRITE | `OrthoControlService.register` | `orthodontics.controls.write` |

Readers omit free-text notes (cloud-eligible); registration also
drives the recall upsert.

## Later (v2, separate issues)

- Open-ended monthly pricing, per-tray aligner tracking, WhatsApp summary.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Alembic branch: `branch_labels=("orthodontics",)`.
- Media owners `ortho_case` / `ortho_control` registered in
  `on_activate()` (ADR 0007).

## Gotchas

- **Controls refused on terminal cases** (`finished`,
  `transferred_out`) — corrections need reopening a finished case to
  `active` (a transferred-out case has no exit).
- **Status machine is explicit** (`VALID_TRANSITIONS` in service.py):
  `transferred_out` terminal, `finished` reopens only to `active`.
  `finished_at` is stamped on each entry into a terminal state and never cleared; reopen stamps `reopened_at`.
- **Wire names are chips, not gates** — unknown labels allowed
  (free-text escape hatch); length capped at 40.
- **`performed_by` defaults to the caller** (`ctx.user_id`), clinic
  membership validated (L32); only the case's named orthodontist
  needs the professional flag.
- **Next-due is computed, not stored** — inbox overdue tab derives from
  the latest control; the `ortho_review` recall upsert (duplicate-guarded)
  fires on control save except while paused.
- **Collection never happens here** — the widget deep-links to
  `/payments?patient_id=`; session completion books the money (ADR 0010).

## CHANGELOG

See `./CHANGELOG.md`.
