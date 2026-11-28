# Recalls — patient call-back workflow

> Status: planned (issue #62). Module: `recalls`. Spec last updated:
> 2026-05-01.

## Why

When a patient leaves the clinic without booking the next visit
(hygiene, check-up, ortho review, implant follow-up, post-op control),
there is no structured way to bring them back. Receptionists rely on
memory, sticky notes, or ad-hoc spreadsheets. Patients fall through
the cracks → lost revenue and worse continuity of care.

The clinic needs a first-class **recalls** workflow:

- Mark a patient to be called in month *X* with a reason and an
  assigned professional.
- Work a reliable monthly **call list** with filters and inline
  actions.
- Track every contact attempt so a patient is not called five times
  in two days — or forgotten for a year.
- Auto-link the booked appointment back to the recall so reception
  can see the loop closed at a glance.
- Reduce manual entry: many recalls should be auto-suggested from
  completed treatments (hygiene → +6 months, post-op → +1 week).

The feature is operational, not marketing — it does not run
campaigns, it gives front desk a list to work.

## Module placement

A new optional module `recalls` lives at `backend/app/modules/recalls/`
with a matching Nuxt layer. Placement decisions:

| Manifest field   | Value                  |
|------------------|------------------------|
| `depends`        | `["patients", "agenda"]` |
| `installable`    | `True`                 |
| `auto_install`   | `True`                 |
| `removable`      | `True`                 |
| `category`       | `"official"`           |

Sibling to agenda + patients, *not* embedded inside agenda. The recall
state machine, monthly list workflow, and `recall.*` events are
independent of the appointment lifecycle and deserve their own module.
The future outreach module will subscribe to `recall.*` events without
touching agenda.

## What we build (in V1)

### Data

- `recalls` table (per-clinic, per-patient): `due_month` (day-1 of
  target month, indexed), optional `due_date`, `reason` enum,
  `reason_note`, `priority`, `status`, `recommended_by`,
  `assigned_professional_id`, `last_contact_attempt_at`,
  `contact_attempt_count`, `linked_appointment_id`,
  `linked_treatment_id` (no FK — snapshot only),
  `linked_treatment_category_key` (snapshot string), timestamps.
- `recall_contact_attempts` table: per-attempt log
  (`channel`, `outcome`, `note`, `attempted_at`, `attempted_by`).
- `recall_settings` table (per-clinic, JSONB): `reason_intervals`,
  `category_to_reason`, two automation toggles.

### Lifecycle (status transitions)

```
pending ───log_attempt(no_answer/voicemail/wrong_number)──► contacted_no_answer
       │                                                           │
       ├──link_appointment / log_attempt(scheduled)────► contacted_scheduled
       │                                                           │
       │                                          appointment.completed
       │                                                           │
       ├──log_attempt(declined)────► contacted_declined            ▼
       │                                                          done
       ├──cancel ───► cancelled
       │
       ▼
   needs_review  (set by patient.archived or do_not_contact rules)
```

Snooze bumps `due_month` forward N months, keeps status `pending`.

### Entry points

- **Patient record** — "Set recall" action in summary hero (slot
  `patient.summary.actions`).
- **Appointment close-out** — when transitioning an appointment to
  `completed`, AppointmentModal renders any components in the
  `appointment.completed.followup` slot. Recalls registers a
  "Schedule a recall?" prompt.
- **Treatment plan / odontogram per item** — slot
  `odontogram.condition.actions` (existing). Pre-fills reason from
  the treatment's category.
- **Auto-suggest** — recalls listens to
  `treatment_plan.treatment_completed`. If the clinic's mapping has
  the treatment's category → a reason, surfaces a non-blocking
  suggestion in `patient.summary.feed`. Never auto-creates without
  user confirmation.

### Monthly call list (`/recalls`)

- Default: current month, status `pending`, sorted by priority + due
  date.
- Filters: month, reason, professional, status, priority, overdue
  toggle, patient.
- Counters strip: due this week, overdue, scheduled this month,
  conversion rate. "Due this week" reads `due_date` inside the
  clinic's Monday-to-Sunday week; month-only recalls (`due_date`
  NULL) are not in any week and count only under the month.
- Per-row inline actions: click-to-call (`tel:` on mobile), log
  attempt (one tap for "no answer"), book appointment (opens agenda
  composer pre-filled, links recall on save), snooze, cancel.
- Bulk actions: export CSV, bulk snooze, bulk reassign professional.
- Mobile-first: collapses to single column, touch targets ≥44px.

### Patient-side surfaces

- Recall pill in summary hero (next due month + reason).
- History card in summary feed (last 5 recalls, link to filtered
  `/recalls`).
- No new patient-detail tab — keeps the existing 5-tab layout.

### Settings (per clinic)

A settings section `Recordatorios` registered into the existing
`settings.sections` slot:

- Default intervals per reason (hygiene 6mo, checkup 12mo,
  ortho_review 1mo, implant_review 6mo, post_op 1wk,
  treatment_followup 3mo, other 3mo).
  Each interval is 0..60 months; 0 turns the suggestion off for that
  reason, and the API rejects anything outside the range (#1244).
- Treatment-category → recall-reason map (preventivo→hygiene,
  ortodoncia→ortho_review, cirugia→post_op, …).
- Toggle: auto-suggest on treatment completion (default on).
- Toggle: auto-link on appointment scheduled (default on).

### Permissions

| Permission        | Default roles                                                    |
|-------------------|------------------------------------------------------------------|
| `recalls.read`    | admin, dentist, hygienist, assistant, receptionist               |
| `recalls.write`   | admin, dentist, hygienist, assistant, receptionist               |
| `recalls.delete`  | admin                                                            |

### Events published

| Event              | When                                                |
|--------------------|-----------------------------------------------------|
| `recall.created`   | new recall row inserted (duplicate-guard fired = no event) |
| `recall.due`       | reserved for future cron; not published in V1       |
| `recall.completed` | recall transitions to `done`                        |
| `recall.snoozed`   | recall snoozed N months                             |
| `recall.cancelled` | recall cancelled (manual or by `patient.archived`)  |

These are the foundation for the future outreach module
(WhatsApp/SMS/email automation) — that work is a separate issue.

### Events consumed

| Event                              | Effect                                                                 |
|------------------------------------|------------------------------------------------------------------------|
| `appointment.scheduled`            | Auto-link a pending recall if (patient, due_month) overlaps. Best-effort: agenda's `treatment_type` is free-text so reason match isn't reliable. |
| `appointment.completed`            | If linked to a recall in `contacted_scheduled`, transition to `done`.  |
| `appointment.cancelled`            | Unlink recall, revert to `pending`, log synthetic attempt note.        |
| `treatment_plan.treatment_completed` | Look up reason mapping, surface non-blocking suggestion in patient feed. |
| `patient.archived`                 | Active recalls for the patient → `needs_review` (not deleted).         |

### Module isolation contract

- Cross-module FKs only to `patients.id` and `appointments.id`.
- `linked_treatment_id` stored without FK; treatment_plan is *not* in
  `depends`. The treatment category arrives via
  `treatment_plan.treatment_completed` payload (enriched at
  publish-time in treatment_plan).
- New slots added by this PR:
  - `patient.summary.actions` (host: patients module)
  - `appointment.completed.followup` (host: agenda module)
- Slots reused from existing modules:
  `patient.summary.feed`, `odontogram.condition.actions`,
  `dashboard.attention`, `settings.sections`.
- Agenda gains a small `initialRecallId` prop on `AppointmentModal`
  so booking from a recall row links the resulting appointment back
  on save.

## Copilot

The AI agent can work the call list conversationally: list due/overdue
recalls, open a recall's detail (notes + attempt history), create
recalls, log contact attempts (auto-linking the booked appointment with
`outcome=scheduled`), snooze and complete. Same RBAC strings as the
HTTP routes; do-not-contact and archived patients stay excluded. See
`backend/app/modules/recalls/CLAUDE.md` § Tools exposed.

## What we don't build (out of scope)

- Outbound automation (WhatsApp / SMS / email). A future module will
  subscribe to `recall.*` events.
- Online self-booking from a recall link.
- Marketing-style mass recalls.
- Patient `deceased` status + GDPR erasure markers — separate issue.
  In V1 we filter `Patient.status = "archived"` and the new
  `Patient.do_not_contact = true` flag.
- Cron-driven `recall.due` event. The enum value is reserved.
- Backup-on-uninstall data dump. Uninstall drops the three tables.

## Acceptance criteria (mirrors issue #62)

- [ ] Recall created from patient record, appointment close-out, and
  treatment plan / odontogram, with reason + month + optional note.
- [ ] `/recalls` lists current month's pending recalls with filters
  and inline actions.
- [ ] Click-to-call works on mobile; logging "no answer" is one tap.
- [ ] Booking an appointment from a recall row pre-fills agenda
  composer and links the appointment back on save.
- [ ] Completing the linked appointment auto-closes the recall and
  surfaces the next-recall suggestion when settings map to one.
- [ ] Duplicate-recall guard updates the existing pending recall
  instead of creating a new row for the same `(patient, reason)`.
- [ ] Patients with `status = archived` or `do_not_contact = true`
  are excluded from the active call list and surface in
  `needs_review`.
- [ ] Permissions enforced on every endpoint.
- [ ] Module is installable and removable cleanly (round-trip
  uninstall test passes).
- [ ] Events `recall.{created,completed,snoozed,cancelled}` published.
- [ ] Dashboard widget shows due / overdue / conversion counters.
- [ ] Mobile-first responsive on the call list.

## Related

- Issue: <https://github.com/dentalpin/dentalpin/issues/62>
- ADRs: `docs/adr/0001-modular-plugin-architecture.md`,
  `docs/adr/0003-event-bus-over-direct-imports.md`,
  `docs/adr/0005-relative-permissions.md`.
- Glossary: `docs/glossary.md` — recall ↔ recordatorio, call list ↔
  lista de llamadas, snooze ↔ posponer, recall reason ↔ motivo.
