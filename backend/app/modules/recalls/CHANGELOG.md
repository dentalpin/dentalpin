# Changelog — recalls module

## Unreleased

- i18n: correct French wording in seed note (Contrôle mensuel).

- i18n: add French translations to seed data; fix `t()` dict pattern.

- fix(security): reject `create` when `patient_id` belongs to another
  clinic (audit multi-tenancy #1, #95). Previously the recall was
  inserted with the caller's `clinic_id` but no check that the patient
  was theirs, and the list/export join had no `Patient.clinic_id`
  predicate — so a caller could point a recall at a foreign patient and
  read that patient's name/phone back. `create` now 404s on a foreign
  patient (HTTP and copilot tool paths), and the list join is scoped to
  `Patient.clinic_id` as defense in depth.

- feat(agents): expose `tools.py` for the copilot agentic layer —
  `list_due_recalls`, `get_recall` (READ; the latter `exposes_free_text`),
  `create_recall`, `log_contact_attempt`, `snooze_recall`,
  `complete_recall` (WRITE). Thin wrappers over `RecallService`;
  clinic-scoped; RBAC via existing `recalls.read`/`recalls.write`.

- refactor(perms): migrate the hardcoded ``can('recalls.read')`` route guard on ``/recalls`` to ``PERMISSIONS.recalls.read`` (new entry in the host permissions config; also covers ``recalls.write`` / ``recalls.delete``).
- perf(list): rewrite ``RecallService.list`` to count via a direct
  ``COUNT(Recall.id)`` over the joined ``recalls × patients`` filter
  set instead of materialising the data query as a subquery. Pairs
  with the new ``patients`` indices on ``status`` /
  ``do_not_contact`` to keep the monthly call-list page sub-second.
- docs(user-manual): reescribir pantallas con guía operativa (ES + EN).
- Initial release. Patient call-back workflow (issue #62).
- Tables: `recalls`, `recall_contact_attempts`, `recall_settings`
  on the `recalls` Alembic branch (`rec_0001`).
- Endpoints under `/api/v1/recalls/*` — list, create (duplicate
  guard), detail, snooze, cancel, mark-done, log-attempt, link
  appointment, settings, dashboard stats, suggestions/next, CSV
  export.
- Events published: `recall.created`, `recall.completed`,
  `recall.snoozed`, `recall.cancelled`. `recall.due` enum value
  reserved for a future cron — not published in V1.
- Events consumed: `appointment.scheduled` (auto-link),
  `appointment.completed` (auto-close), `appointment.cancelled`
  (revert), `treatment_plan.treatment_completed` (suggestion hook,
  stateless), `patient.archived` (move active → needs_review).
- Frontend layer registers slot entries in:
  - `patient.summary.actions` — "Set recall" button
  - `patient.summary.feed` — recall pill + recent history
  - `odontogram.condition.actions` — per-treatment "Set recall"
  - `appointment.completed.followup` — "Schedule recall?" prompt
  - `dashboard.attention` — due/overdue/conversion widget
  - `settings.sections` — reason-interval + category-map editor
- Permissions: `recalls.{read,write,delete}`. Receptionist + dentist
  + hygienist + assistant get read+write; admin gets `*`.
- Auto-link policy on `appointment.scheduled` is **conservative**:
  fires only when the patient has exactly one matching active recall.
  Two-plus candidates → no-op, reception links manually from the
  call-list row. Avoids silent wrong-association across multiple
  reasons (no reliable signal in agenda's free-text `treatment_type`).
- `installable=True`, `auto_install=True`, `removable=True`.
  Round-trip uninstall test verifies all three tables drop cleanly.
- Sidebar entry registered via `manifest.frontend.navigation`
  (`/recalls`, icon `i-lucide-bell`, gated by `recalls.read`,
  `order: 25` — between `Agenda` and `Planes de tratamiento`).
  Host i18n adds `nav.recalls` for ES/EN.
