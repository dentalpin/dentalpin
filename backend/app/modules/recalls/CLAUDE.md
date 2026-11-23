# Recalls module

Patient call-back workflow. Receptionists mark a patient to be called
in month *X*, work a monthly call list, log attempts, auto-link
booked appointments. Foundation for a future outreach module that
will subscribe to `recall.*` events with WhatsApp/SMS/email
automation. Recalls itself never sends.

Issue #62. Spec: `docs/features/recalls.md`.

## Public API

Routes mounted at `/api/v1/recalls/`.

| Method | Path                              | Permission        |
|--------|-----------------------------------|-------------------|
| GET    | `/`                               | `recalls.read`    |
| POST   | `/`                               | `recalls.write`   |
| GET    | `/stats/dashboard`                | `recalls.read`    |
| GET    | `/suggestions/next`               | `recalls.read`    |
| GET    | `/settings`                       | `recalls.read`    |
| PUT    | `/settings`                       | `recalls.write`   |
| GET    | `/export.csv`                     | `recalls.read`    |
| GET    | `/patients/{patient_id}`          | `recalls.read`    |
| GET    | `/{id}`                           | `recalls.read`    |
| PATCH  | `/{id}`                           | `recalls.write`   |
| POST   | `/{id}/snooze`                    | `recalls.write`   |
| POST   | `/{id}/cancel`                    | `recalls.write`   |
| POST   | `/{id}/done`                      | `recalls.write`   |
| POST   | `/{id}/attempts`                  | `recalls.write`   |
| GET    | `/{id}/attempts`                  | `recalls.read`    |
| POST   | `/{id}/link-appointment`          | `recalls.write`   |
| DELETE | `/{id}`                           | `recalls.delete`  |

## Dependencies

`manifest.depends = ["patients", "agenda"]`.

Treatment-plan integration is **event-driven only** — recalls reads
the `treatment_category_key` snapshot field that treatment_plan added
to its `treatment_plan.treatment_completed` payload. Recalls does
NOT depend on treatment_plan or catalog: no imports, no FKs.

## Permissions

`recalls.read`, `recalls.write`, `recalls.delete`. Default role
mapping grants read+write to admin, dentist, hygienist, assistant,
receptionist; only admin gets delete.

## Tools exposed

Agent tools in `tools.py` (wrap `RecallService`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_due_recalls` | READ | `RecallService.list` | `recalls.read` |
| `get_recall` | READ (`exposes_free_text`) | `RecallService.get_with_attempts` | `recalls.read` |
| `create_recall` | WRITE | `RecallService.create` | `recalls.write` |
| `log_contact_attempt` | WRITE | `RecallService.log_attempt` | `recalls.write` |
| `snooze_recall` | WRITE | `RecallService.snooze` | `recalls.write` |
| `complete_recall` | WRITE | `RecallService.mark_done` | `recalls.write` |

`list_due_recalls` keeps the service defaults (archived + do_not_contact
excluded) and omits `reason_note`, so it stays cloud-eligible under
redaction. `get_recall` returns the free-text notes and attempt log —
flagged `exposes_free_text=True`, the bridge drops it from the tool list
when redaction is on.

## Events emitted

| Event              | When                                                 |
|--------------------|------------------------------------------------------|
| `recall.created`   | new recall row inserted (duplicate-guard fires = no event) |
| `recall.due`       | reserved for future cron — not published in V1       |
| `recall.completed` | recall transitions to `done`                         |
| `recall.snoozed`   | recall snoozed N months                              |
| `recall.cancelled` | recall cancelled (manual or via `patient.archived`)  |

## Events consumed

| Event                                | Handler                          | Effect |
|--------------------------------------|----------------------------------|--------|
| `appointment.scheduled`              | `on_appointment_scheduled`       | Auto-link a pending recall (same patient, due_month ≤ appt month) when `auto_link_on_appointment_scheduled` is on. |
| `appointment.completed`              | `on_appointment_completed`       | Mark linked recall as `done`. |
| `appointment.cancelled`              | `on_appointment_cancelled`       | Unlink, revert `contacted_scheduled` → `pending`. |
| `treatment_plan.treatment_completed` | `on_treatment_plan_completed`    | Logging-only stub. Suggestion is pulled by the frontend via `GET /suggestions/next`; keeps state stateless and avoids stale dismissals. |
| `patient.archived`                   | `on_patient_archived`            | Active recalls (`pending`/`contacted_no_answer`/`contacted_scheduled`) → `needs_review`. |
| `gdpr.erasure.executed` | `erasure.RecallsErasureContributor` (contributor, not a subscribed handler) | Clears the patient's contact-attempt notes whose channel matches an erased contact category; the recall and its clinical `reason_note` stay (#546, ADR 0038). |

## Frontend integration (slot registrations)

Registered in `frontend/plugins/slots.client.ts`:

- `patient.summary.actions` — "Set recall" button on patient hero.
- `patient.summary.feed` — recall pill + recent history.
- `odontogram.condition.actions` — per-treatment "Set recall".
- `appointment.completed.followup` — close-out prompt (modal body).
- `dashboard.attention` — due / overdue / conversion widget.
- `settings.sections` — reason intervals + category map editor.

The `/recalls` page (`pages/recalls/index.vue`) is the receptionist's
monthly call list. Mobile-first layout via `useBreakpoint`.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=True`.
- `uninstall()` (default no-op) + Alembic downgrade drop the three
  tables. Round-trip uninstall test enforces this.
- No backup-on-uninstall data dump in V1 — recall history is lost
  on uninstall (documented in admin UI).

## Gotchas

- **No FKs to treatment_plan or catalog.** `linked_treatment_id`
  is a nullable UUID without FK; `linked_treatment_category_key` is
  a string snapshot. Required to keep the dependency contract.
- **Multi-tenancy.** Every query filters by `clinic_id`. The
  `RecallFilters` dataclass + `RecallService.list` always join
  `Patient` to apply the do-not-contact + archived exclusion.
- **Duplicate guard.** Creating a recall for `(patient, reason)`
  that already has an `active` row updates the existing row instead
  of inserting. The endpoint returns 201 either way; `recall.created`
  is published only when a new row was actually inserted.
- **Snooze unlinks, closed is final** (#1010). Snoozing clears
  `linked_appointment_id`, so the old visit can't close the recall; `PATCH`
  on a done / cancelled recall is a 409 like every other write.
- **Patient exclusions.** Active call list excludes
  `Patient.status="archived"` AND `Patient.do_not_contact=True`.
  Affected recalls go to the `needs_review` bucket (separate filter,
  not deleted).
- **Auto-link is conservative — no-op when ambiguous.** Match policy:
  same patient + due_month ≤ appointment month + status active +
  no existing link. Reason match is not gated on agenda's free-text
  `treatment_type`. When the patient has **two or more** active
  recalls that match, the auto-link bails out and waits for an
  explicit link via the "Agendar cita" row action (which passes
  `recall_id`) or `POST /recalls/{id}/link-appointment`. Better one
  miss than one wrong link — recall history is patient-trust-critical.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0002-per-module-alembic-branches.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0005-relative-permissions.md`

## CHANGELOG

See `./CHANGELOG.md`.
