# Orthodontics module

Orthodontic case tracking: monthly controls, archwires, photo
evolution (issue #270). **Optional, removable**. Slice-a is clinical
tracking only — no money code (see Later).

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

## Dependencies

`manifest.depends = ["patients", "media"]`. Slice-b extends to
`["patients", "agenda", "media", "recalls", "treatment_plan"]`.

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

None in slice-a (copilot tools are a slice-b follow-up).

## Later (slice-b + follow-ups, user-approved 2026-09-08)

- **Slice-b PR:** treatment-plan installment link (`treatment_plan_id` +
  `plan_item_id`, optional for transfer patients), recall upsert
  (`ortho_review`, paused freezes generation per Q3), appointment link
  (`appointment_id` FK + agenda dep), `session_id` audit pointer,
  installments widget + deep-link-only "Collect installment" (Q2, ADR
  0010), `transferred_out` plan-close prompt (Q3).
- **Follow-ups:** chip-catalog settings UI (seed-only now, Q4), copilot
  tools `get_ortho_case_status` / `list_overdue_ortho_controls` /
  `register_ortho_control` (Q5), v2 items from the issue (open-ended
  pricing, per-tray aligner tracking, WhatsApp summary).

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
  `finished_at` is set once, never cleared; reopen stamps `reopened_at`.
- **Wire names are chips, not gates** — unknown labels allowed
  (free-text escape hatch); length capped at 40.
- **`performed_by` defaults to the caller** (`ctx.user_id`), membership
  validated as professional (L32).
- **Next-due is computed, not stored** — inbox overdue tab derives from
  the latest control; no Recall rows until slice-b.

## CHANGELOG

See `./CHANGELOG.md`.
