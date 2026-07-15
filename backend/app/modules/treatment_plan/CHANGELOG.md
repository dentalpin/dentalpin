# Changelog — treatment_plan module

## Unreleased

- i18n: add `fr` fallback to plan item name resolution in service
  layer so French-localized treatment names display correctly.

- refactor(scheduler): declare the ``auto_close_expired_plans`` cron job
  via ``get_scheduled_jobs()`` instead of being imported by name in
  ``app/core/scheduler.py``.

- feat(ux): ``PlanDetailView`` wires the new ``PlanNotesTimeline``
  ``item-hover`` event into the existing ``hoveredItemId`` highlight
  pipeline, so hovering or focusing a note in the timeline pulses the
  matching tooth/arch on the odontogram. Treatment-source notes resolve
  via ``itemByTreatmentId``; visit-source via ``itemByPlanItemId``;
  plan-level notes no-op.
- feat(sessions): plan items now own 1..N ``PlannedTreatmentItemSession``
  rows that capture the named, billable steps of a multi-session
  treatment (e.g. crown: "Toma de medidas" 200€ + "Colocación" 600€).
  Sessions are snapshotted from the catalog template at ``add_item``
  time (scaled if the treatment price overrides the catalog total) and
  are independent thereafter. New endpoints:
  - ``PATCH /items/{id}/sessions/{sid}/complete`` — publishes
    ``treatment_plan.item_session_completed`` (consumed by ``payments`` →
    earned ledger). Finalizes the parent item once all sessions are
    terminal and at least one was completed.
  - ``PATCH /items/{id}/sessions/{sid}/cancel`` — terminate a session
    without generating an earned entry.
  - ``PUT /items/{id}/sessions/{sid}`` — edit label/amount/notes on a
    pending session.
  - ``POST /items/{id}/sessions`` + ``DELETE /items/{id}/sessions/{sid}``
    — append/remove a session manually.
  The legacy ``PATCH /items/{id}/complete`` keeps working: it advances the
  next pending session. Migration ``tp_0006`` creates the new table and
  backfills one row per existing item.
- fix(events): ``on_treatment_performed`` handler uses
  ``SELECT FOR UPDATE SKIP LOCKED`` when looking up the matching
  planned item. Avoids a deadlock that surfaced as a client timeout
  on ``PATCH /treatment-plans/{id}/items/{id}/complete``: under the
  async-first event bus (sprint 3) the parent transaction held the
  row lock on ``planned_treatment_items`` and the handler — running
  inline before the parent commit, in a new session — blocked
  trying to update the same row. When the row is locked we skip
  silently; the originator's UPDATE drives the state transition.
- feat(plans): per-item assigned professional. `PlannedTreatmentItem` gains
  `assigned_professional_id` (FK to `users.id`, nullable). New items inherit
  the plan's doctor by default; the API and `PlanItemDoctorChip` lets the
  clinician override it (e.g. fillings by Dr A, endodontics by Dr B). When
  the plan-level doctor changes, the cascade is opt-in via a new write-only
  `reassign_pending_items` flag on `TreatmentPlanUpdate` — only pending items
  still pointing at the previous plan doctor are reassigned; explicit
  overrides and completed items are left alone. Migration `tp_0005` backfills
  existing items from the parent plan. Event payload
  `treatment_plan.treatment_added` now carries `assigned_professional_id`
  (additive, safe for the `budget` subscriber). Doctor reassignment bypasses
  the plan-lock guard (`_is_plan_locked`) — reassigning who performs a
  treatment doesn't change the patient-facing contract, so it stays
  available even after the plan is validated and the budget is active.
  Completed/cancelled items reject doctor changes (400) — the planned
  doctor is frozen at completion time. The completed-items section of
  `PlanTreatmentList` shows a read-only chip with the
  `assigned_professional_id` (the responsible clinician), not
  ``completed_by``: reception or an admin can mark items complete on
  behalf of the clinician and the chart's reference should stay on the
  treatment owner.
- fix(clinical/plans): treatment names in `PlanTreatmentList` no longer truncate with ellipsis and now take the full available row width — switched `truncate` to `break-words` and replaced the flex row with a `grid-cols-[1fr_auto]` layout so the name column grows deterministically into the free space before wrapping.
- refactor(perms): migrate hardcoded ``can('treatment_plan.plans.write')`` and ``can('clinical_notes.notes.write')`` strings in the treatment-plans page, ``PlansListPanel`` and ``VisitNotePanel`` to ``PERMISSIONS.treatmentPlans.write`` / ``PERMISSIONS.clinicalNotes.write``.
- perf(list): collapse the duplicated ``items → treatment`` eager-load
  chain in ``TreatmentPlanService.list`` into a single chain that
  attaches both ``Treatment.teeth`` and ``Treatment.catalog_item``
  through ``.options(...)``. Halves the SQLAlchemy batch queries
  per page.
- perf(cron): ``auto_close_expired_plans`` processes clinics
  concurrently behind an ``asyncio.Semaphore(5)`` instead of
  serially, so a slow clinic does not delay the rest of the run.
- chore(events): all publishers in this module now ``await
  event_bus.publish(...)`` — bus is async-first as of core sprint 3.
- docs(user-manual): reescribir pantallas con guía operativa (ES + EN).
- **0.2.0 (issue #55)** — `TreatmentMedia` model + `treatment_media`
  table dropped (migration `tp_0004`, depends on `med_0002`). Existing
  rows are migrated into `media.media_attachments` with
  `owner_type='plan_item'`; the legacy `media_type` enum maps onto the
  new `media_kind` / `media_category` / `media_subtype` columns on
  `documents`. Service methods `add_media` / `remove_media` and the
  `POST/DELETE /treatment-plans/items/{id}/media` endpoints are gone
  — clients call `POST /api/v1/media/attachments` with
  `owner_type='plan_item'` instead. New `owner_resolvers.py` registers
  the `plan_item` resolver with `media.attachment_registry` at module
  import time.

- Enrich `treatment_plan.treatment_completed` event payload with a
  `treatment_category_key` snapshot (issue #62, recalls). Allows
  sibling modules to map completed treatments to follow-up policies
  without importing catalog or treatment_plan models. Loaded via
  the existing `_treatment_loader` selectinload chain (now also
  pulls `catalog_item.category`); event-handler paths use a small
  helper query when the relationships aren't already loaded.

- Patient detail → Clínica → Planes: `PlansMode` paginates plans at
  page_size=20. `PlansListView` now exposes `page` / `total-pages`
  props and renders the shared `PaginationBar` below the grouped lists.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).
- Documented one string-literal event (`treatment_plan.items_reordered`)
  that is not yet in the `EventType` enum.

### Changed (frontend, 2026-04-30)

- Unified `Planes de tratamiento` and `Bandeja de planes` into a single
  page at `/treatment-plans` with six tabs (5 pipeline workflow tabs +
  `Listado`). The dedicated `/treatment-plans/pipeline` route and the
  `nav.pipeline` sidebar entry are removed; pipeline content is now
  reachable as the default tab on the merged page. Tab body extracted to
  reusable `PipelineTabPanel` and `PlansListPanel` components.

### Removed (2026-04-29)

- Legacy unlock flow (`POST /treatment-plans/{id}/unlock`,
  `TreatmentPlanService.unlock`, `treatment_plan.unlocked` event,
  ``Modificar plan`` button + modal). Superseded by the new workflow:
  ``Reabrir`` for ``pending`` plans and ``Renegociar`` from the
  budget UI for accepted budgets.

### Added (frontend, 2026-04-29 — PR2)

- Page `/treatment-plans/pipeline` (bandeja de planes) with five
  tabs powered by the new `usePipeline` composable. Search box +
  call/WhatsApp quick-actions per row.
- Workflow modals (`components/clinical/modals/`):
  `ConfirmPlanModal`, `ReopenPlanModal`, `ClosePlanModal`,
  `ReactivatePlanModal`, `ContactLogModal`.
- `useTreatmentPlans` gains `confirmPlan`, `reopenPlan`, `closePlan`,
  `reactivatePlan`, `logContact` actions wired to the PR1 endpoints.
- `PlanDetailView` exposes `Confirm` / `Reopen` / `Reactivate` buttons
  contextual to the plan status; the legacy "Cancel plan" button now
  delegates to the unified `ClosePlanModal` (closure_reason +
  closure_note).
- Navigation entry `nav.pipeline` linked to the bandeja.
- Status filter on the plans index updated to the new state set.

### Added (plan/budget workflow rework, 2026-04-29 — PR1)

- New plan states: `pending` (between confirm and accept) and `closed`
  (terminal non-completed state) with `closure_reason`, `closure_note`,
  `closed_at`, `confirmed_at` columns.
- Workflow transitions: `confirm` (draft → pending, auto-creates draft
  budget via direct call to BudgetService), `reopen`, `close`,
  `reactivate`, plus `accept_from_budget` / `reject_from_budget` for
  the budget event handlers.
- New endpoints:
  - `POST /treatment-plans/{id}/{confirm,reopen,close,reactivate}`
  - `POST /treatment-plans/{id}/contact-log`
  - `GET  /treatment-plans/pipeline` (5-tab cross-module bandeja).
- Granular permissions `plans.{confirm,close,reactivate}`.
  Receptionist role gains close + reactivate.
- Three new events with snapshot payloads:
  `treatment_plan.{confirmed,closed,reactivated}`. Subscribers
  (patient_timeline) consume payload data only — no cross-module ORM
  reads.
- `auto_close_expired_plans` cron (daily 03:00) — closes pending plans
  whose budget has been expired beyond the per-clinic threshold.
- Plan ↔ budget direct call carve-out: `confirm()` calls
  `BudgetService.create_from_plan_snapshot` synchronously (budget is
  in `manifest.depends`). Documented in CLAUDE.md.

### Removed

- Legacy `cancelled` plan status (migrated to
  `closed` + `closure_reason='cancelled_by_clinic'`).

### Removed (issue #60 — clinical-notes extraction)

- `ClinicalNote` and `ClinicalNoteAttachment` models, schemas, service
  (`notes_service.py`) and router endpoints. Ownership moved to the new
  `clinical_notes` module.
- `treatment_plan.{plan,item}_note_created` events (replaced by
  `clinical_notes.{administrative,diagnosis,treatment,plan}_created`).
- `note_body` and `attachment_document_ids` fields from
  `CompleteItemRequest`. The client now POSTs a follow-up note to
  `/api/v1/clinical_notes/notes` after a successful completion.
- `note_templates.py` (moved into `clinical_notes`).
- Frontend components `PlanNotesTimeline.vue`, `PatientClinicalNotesByPlan.vue`,
  `useClinicalNotes` composable. Replacement components are provided by
  the `clinical_notes` Nuxt layer with the same names so existing
  imports (`<PlanNotesTimeline />`) keep resolving.

## 0.1.0 — initial

- Treatment plan CRUD with status workflow.
- Items linked to catalog services and odontogram tooth treatments.
- Clinical notes at plan and item level with media attachments.
- Bidirectional sync with `budget` via events.
- Subscribes to `appointment.completed`, `budget.accepted`,
  `odontogram.treatment.performed`.
