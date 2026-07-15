# Changelog — patients module

## Unreleased

- i18n: replace hardcoded strings in patient components with `$t()`
  calls; add French patient names/contacts to demo seed data.

- fix(events): include `clinic_id` in the `patient.archived` and
  `patient.updated` payloads (audit event-bus #11, #95). Every event
  must carry the tenant per the multi-tenancy convention; the omission
  broke the media archive cascade and forced the recalls handler into an
  unscoped query.

- feat(agents): new copilot tool `update_patient` (WRITE) — updates a
  patient's contact data (phone, email) via `PatientService.update_patient`.
  Identity fields stay manual.

- fix(search): multi-term patient search. `PatientService.list_patients`
  now splits the `search` string on whitespace and requires **every**
  term to match **some** field (AND across terms, OR across fields),
  matching against `first_name`, `last_name`, the concatenated full
  name, `phone`, `email` and `national_id`. Fixes "Nombre Apellido"
  (and reversed "Apellido Nombre") returning no results — previously the
  whole input was one substring ILIKE'd against each field separately,
  so a name split across `first_name`/`last_name` never matched. Same
  fix reaches the copilot `search_patients` tool (shared service path);
  its arg description now tells the agent to pass the full name as one
  query. No frontend change — UI already routes through this service.

- feat(agents): expose `tools.py` for the copilot agentic layer —
  `search_patients`, `get_patient` (READ), `create_patient` (WRITE).
  Thin wrappers over `PatientService`; clinic-scoped; RBAC via existing
  `patients.read`/`patients.write`. Issue #81 Layer B.

- feat(ux): patient list default sort changed from ``last_name:asc`` to
  ``last_visit:desc`` so patients seen most recently surface first.
  ``last_visit`` is computed via a ``MAX(start_time) GROUP BY patient_id``
  subquery against the ``agenda.appointments`` table, LEFT JOINed with
  NULLS LAST so never-seen patients fall to the bottom. The patients
  module keeps ``depends = []``: the appointments table is referenced
  via ``sqlalchemy.table()`` rather than importing the ``Appointment``
  model — same workaround as ``get_recent_patients``. ``updated_at`` is
  also exposed as an opt-in sort field. Frontend sort menu order:
  Última visita, Apellidos, Nombre, Registro, Editado recientemente.
- feat(ux): ``PatientVisualSelector`` (shared) gains an inline "create patient" mode. When the typed query has no match and the user has ``patients.write``, a footer row in the search dropdown opens a 3-field mini-form (nombre, apellidos, teléfono). Submitting POSTs ``/api/v1/patients`` and emits the selection upward. Includes soft-duplicate phone lookup (debounced + ``AbortController``-cancelled) reusing ``GET /patients?search=``. No backend changes — feeds into the agenda's *Nueva cita* flow. See ``docs/features/agenda-quick-patient-create.md``.
- feat(ux): redesigned patient detail as a dashboard-first IA. The
  Resumen tab is now a grid of slot-driven smart cards (Plan, Próxima
  cita, Saldo, Diagnósticos, Historial médico, Acciones rápidas) plus
  the clinical-notes feed. A persistent ``PatientStickyHeader``
  replaces the dense left rail and stays visible across every tab.
  Mobile gets a ``PatientBottomActionBar`` with the three most-used
  actions (cita, cobrar, nota). Saves one click to Plan, Cobros,
  Próxima cita and Odontograma.
- feat(slots): exposes two new slot contracts: ``patient.summary.cards``
  (grid entries on Resumen) and ``patient.header.alerts`` (chips in the
  sticky header). The existing ``patient.summary.actions`` slot is
  preserved and now renders both in the sticky header and in the
  Quick-Actions card. Each smart card lives in (and is registered by)
  its owning module — ``patients`` keeps ``depends = []``.
- refactor: dropped ``PatientSummaryHero.vue`` and the legacy
  ``ActivePlanWidget`` / ``NextAppointmentWidget`` props pipeline. The
  page no longer reaches into agenda or treatment_plan APIs to compute
  widgets; each module fetches its own data inside its card.
- chore(shared): ``SegmentedControl`` accepts ``badge`` /
  ``badgeColor`` per option and a ``fullWidth`` mode so the
  Clínica/Administración sub-nav can surface contextual counts.
- refactor(perms): migrate the hardcoded ``can('payments.record.read')`` gate on the patients list to ``PERMISSIONS.payments.recordRead``.
- fix(isolation): drop the cross-module ORM coupling to ``agenda`` and
  ``patient_timeline``. ``Patient`` no longer declares
  ``relationship(back_populates=...)`` to ``Appointment`` /
  ``PatientTimeline`` (the foundational module cannot point at
  consumers) — the sibling side keeps a one-directional reference.
  ``get_recent_patients`` no longer lazily imports
  ``agenda.models.Appointment``; it reads ``appointments`` through a
  raw SQL fragment with the same fallback semantics.
- perf(list): drop subquery-count anti-pattern; count uses
  ``COUNT(Patient.id)`` over the same filter set as the data query.
- perf(indexes): new migration ``pat_0003_recall_filter_indices`` adds
  ``(clinic_id, status)`` and a partial ``(clinic_id)`` where
  ``do_not_contact = false`` so recalls / outreach list builders
  stop falling back to a full table scan once a clinic accumulates
  patients.

### Added (lists redesign, 2026-05-14)

- `GET /api/v1/patients` accepts new params: `patient_ids[]`, `city`,
  `do_not_contact`, `include_archived`, `sort=field:dir` (whitelist:
  `last_name`, `first_name`, `created_at`).
- New slots exposed on `/patients` list page: `patients.list.filter`
  (toolbar chip injection) and `patients.list.row.financial` (per-row
  cell injection). Payments module registers fillers for "Con deuda"
  toggle + debt badge.
- List page rewritten on `DataListLayout` + `FilterBar` +
  `useListQuery`. Card view <md, URL-synced filters, sort dropdown,
  status/city/do-not-contact filters.

- **`do_not_contact: bool` flag** added to the patient model
  (issue #62, recalls). Operational opt-out — patients with this flag
  set are excluded from the recalls call list and any future
  outreach automation. Defaults to `false`. Editable from the
  Demographics edit modal. Migration: `pat_0002`.
- New slot mount `patient.summary.actions` rendered on
  `PatientSummaryHero` so sibling modules (e.g. `recalls`) can
  contribute action buttons to the patient summary without modifying
  the patients module UI.
- New slot `patient.detail.administracion.payments` exposed inside
  `AdministrationTab` (ctx: `{ patient, patientId }`). Optional
  sub-mode "Pagos" appears in the segmented toggle only when the slot
  has at least one provider visible to the user — the `payments`
  module registers a panel here. Patients module stays free of any
  payments imports; the contract is the slot name alone. URL
  `?adminMode=payments` falls back to `budgets` when the slot is
  empty.

- Patient detail → Administración → Presupuestos: paginated (page_size=20).
  `AdministrationTab` now owns its own paginated fetch via the shared
  `PaginationBar`; the parent `[id].vue` no longer prefetches budgets.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).
- Issue #60: patient detail page lands on a new **Summary** tab by
  default (replaces Info as default; Info stays accessible via tab
  list and `?tab=info`). Summary renders `patient.summary.feed` slot —
  filled by the clinical_notes module.
- Removed left sidebar (`PatientQuickInfo`) from patient detail. All
  tabs now span full width. Sidebar widgets (avatar, status, alerts,
  contact strip, active plan, next appointment, emergency contact)
  collapsed into a new `PatientSummaryHero` rendered at the top of
  the **Summary** tab. The `patient.detail.sidebar` slot is preserved
  by re-mounting it inside the hero so community modules keep their
  extension point.
- **Summary** tab now uses a 2-column layout: a sticky left rail
  (`PatientSummaryHero`) and a main column for the clinical-notes feed.
  Other tabs (info, clinical, administration, timeline) keep their
  full-width layout.

## 0.1.0 — initial

- Patient identity model: name, contact, demographics, `status`.
- `/api/v1/patients/*` CRUD with soft-delete via archive.
- Events: `patient.created`, `patient.updated`, `patient.archived`.
- Permissions: `patients.read`, `patients.write`.
