# Treatment plan module

Patient treatment plans with budget + odontogram sync. **Heaviest
`depends` in the system** — this module is an integration hub. Read
this file before changing any cross-module flow.

## State machine

```
draft ──confirm──► pending ──accept──► active ──complete──► completed
  ▲                  │                    │
  │                  │ rejected/expired   │ cancelled by clinic
  │                  ▼                    ▼
  └─── reactivate ◄──────  closed  ◄─────┘
                       (closure_reason)
```

`closure_reason` ∈ `{rejected_by_patient, expired,
cancelled_by_clinic, patient_abandoned, other}`. See ADR 0006 and
`docs/workflows/plan-budget-flow.md` (staff manual).

One extra edge (issue #162): a plan closed as `rejected_by_patient`
jumps straight back to `active` when the patient accepts a **resent**
budget version (`budget.accepted` on the new version) — the doctor's
original confirmation stands, so it skips draft/pending and keeps
`confirmed_at`. Other closure reasons never auto-revive.

## Public API

Routes mounted at `/api/v1/treatment-plans/`.

- `GET   /treatment-plans`              — list; `treatment_plan.plans.read`
- `POST  /treatment-plans`              — create; `treatment_plan.plans.write`
- `GET   /treatment-plans/{id}`         — detail
- `PUT   /treatment-plans/{id}`         — update; status transitions
- `POST  /treatment-plans/{id}/items`   — add item from catalog or odontogram tooth treatment
- `PUT   /treatment-plans/{id}/items/reorder`
- `POST  /treatment-plans/{id}/items/{item_id}/complete`
- `POST  /treatment-plans/{id}/confirm`     — `plans.confirm`; draft → pending
- `POST  /treatment-plans/{id}/reopen`      — pending → draft, cancels linked budget
- `POST  /treatment-plans/{id}/close`       — `plans.close`; any → closed
- `POST  /treatment-plans/{id}/reactivate`  — `plans.reactivate`; closed → draft
- `POST  /treatment-plans/{id}/contact-log` — record reception touchpoint
- `GET   /treatment-plans/pipeline`         — bandeja (5 tabs)

> **Notes endpoints moved.** Since issue #60 the `clinical_notes` module
> owns every clinical-note CRUD path (`/api/v1/clinical_notes/*`). The
> per-item completion endpoint here no longer accepts `note_body` — the
> client orchestrates a follow-up POST to `clinical_notes` when the
> dentist captures a note at completion time.

## Dependencies

`manifest.depends = ["patients", "agenda", "odontogram", "catalog", "budget", "media"]`.
Six dependencies. Anything not on this list is off-limits — no imports,
no FKs.

## Permissions

`treatment_plan.plans.{read,write}`. Clinical-note permissions live in
the `clinical_notes` module since issue #60.

## Events emitted

| Event | When | Notes |
|---|---|---|
| `treatment_plan.created` | plan created | consumed by `patient_timeline` |
| `treatment_plan.status_changed` | status transition | currently no subscribers |
| `treatment_plan.confirmed` | draft → pending | snapshot payload (items, totals, patient). Subscriber: `patient_timeline`. |
| `treatment_plan.closed` | any → closed | payload includes `closure_reason`. Subscriber: `patient_timeline`. |
| `treatment_plan.reactivated` | closed → draft | Subscriber: `patient_timeline`. |
| `treatment_plan.treatment_added` | item added | snapshot payload (catalog_item_id, tooth, surfaces, unit_price, budget_id). Subscriber: `budget`. |
| `treatment_plan.treatment_removed` | item removed | payload includes `budget_id`. Subscriber: `budget`. |
| `treatment_plan.treatment_completed` | item marked done | consumed by `patient_timeline`, `recalls`. Payload includes `treatment_category_key` (snapshot, may be null) so subscribers can map a completed treatment to a follow-up policy without importing catalog or treatment_plan models (issue #62). Earned-ledger generation **moved out** of this event since the multi-session feature — see `item_session_completed` below. |
| `treatment_plan.item_session_completed` | one session of a multi-session item marked done | payload: `{plan_id, item_id, session_id, sequence, label, amount, treatment_id, patient_id, completed_by, occurred_at}`. Consumed by `payments` (earned entry, idempotent on `(treatment_id, session_id)`). Fires for every completed session — single-session items publish it once on completion. |
| `treatment_plan.budget_sync_requested` | manual resync | snapshot payload includes full `items[]`. Subscriber: `budget`. |
| `treatment_plan.item_completed_without_note` | completion check | consumed by `patient_timeline` |

Clinical-note created events (`clinical_notes.{administrative,diagnosis,treatment,plan}_created`) live in the `clinical_notes` module.

> All events above are declared in `EventType` and published via the
> constants. ``items_reordered`` used to be a string-only literal —
> it now lives at `EventType.TREATMENT_PLAN_ITEMS_REORDERED`.

## Events consumed

| Event | Handler | Effect |
|---|---|---|
| `appointment.completed`         | `on_appointment_completed`  | mark planned items as performed if linked |
| `budget.accepted`               | `on_budget_accepted`        | pending → active; also closed(rejected_by_patient) → active on a resent version (idempotent). Reprices pending sessions from the payload's `items[].net_amount` (issue #167) |
| `budget.rejected`               | `on_budget_rejected`        | pending → closed (closure_reason=rejected_by_patient) |
| `budget.renegotiated`           | `on_budget_renegotiated`    | pending → draft via `reopen_from_budget` (never writes the budget row) |
| `budget.cancelled`              | `on_budget_cancelled`       | pending → draft via `reopen_from_budget`; no-op without `plan_id` |
| `budget.superseded`             | `on_budget_superseded`      | repoint `budget_id` to the resent version (only while still pointing at the old one) |
| `odontogram.treatment.performed` | `on_treatment_performed`   | mark planned item completed when its tooth treatment is performed |

## Lifecycle

- `removable=False`. Plans tie patients ↔ budgets ↔ tooth treatments;
  removing the module would orphan all three.

## Gotchas

- **Plan → budget direct call is the carve-out.** `confirm()` calls
  `BudgetService.create_from_plan_snapshot` synchronously to keep the
  draft-budget creation transactional with the state transition.
  Allowed because `budget` is in `manifest.depends`. Item-level
  add/remove sync remains event-driven (the snapshot payloads carry
  enough data so `budget` doesn't import treatment_plan).
- **`confirm()` relinks `budget_id` whenever the provisioned budget
  differs.** A reactivated or renegotiated plan still points at its
  terminal budget; the idempotency check in
  `BudgetService.create_from_plan_snapshot` treats
  cancelled/rejected/expired as terminal and provisions a fresh draft
  (issue #162). Don't revert the link condition to `budget_id is None`.
- **A plan is locked only while its budget is `sent`/`accepted`.**
  Terminal budgets (cancelled/rejected/expired) are dead paper and do
  not freeze the plan. Mirrored in `PlanDetailView.vue` and
  keep the two predicates in sync. (`TreatmentPlanDetail.vue` was
  dead code and was removed in #167.)
- **Budget-side reopens go through `reopen_from_budget`,** which never
  writes the budget row: the publisher's open transaction holds it
  locked and the bus awaits handlers inline — calling `reopen()` from a
  handler would hang. `reopen()` itself cancels the linked budget with
  `publish_event=False` for the symmetric reason.
- **Plan ↔ budget item sync goes through events**, not direct calls.
  Adding a treatment to a plan publishes
  `treatment_plan.treatment_added` with a denormalized snapshot
  (catalog_item_id, tooth, surfaces, unit_price, budget_id); the
  budget module's handler creates the matching budget line.
- **Item completion has two paths**: the user marks an item complete
  here, or the odontogram fires `odontogram.treatment.performed`. Both
  must converge to the same state — keep them idempotent.
- **Sessions are the source of earned signal.** Every plan item now
  owns ≥1 `PlannedTreatmentItemSession` (backfilled by `tp_0006`).
  Per-session completion fires `item_session_completed`; the item
  finalizes (and `treatment_completed` fires) only when every session
  is in a terminal state and at least one is `completed`. Editing a
  completed session is refused — its amount is the snapshot that
  payments already booked.
- **Completing a session/item requires the plan to be `active`.**
  `complete_session` (and the `complete_item` shim) raise `ValueError`
  → 400 otherwise, and `PlanTreatmentList` hides the action until then.
  Money is booked on completion and sessions are repriced to the
  accepted quote only at acceptance, so completing earlier would book
  catalog prices (issue #167). The odontogram-first
  (`on_treatment_performed`) and appointment paths are deliberately
  **not** gated — they record a clinical fact that already happened.
- **Sessions are repriced at acceptance, pending ones only.**
  `_reprice_sessions` scales an item's pending sessions so that
  Σ(all sessions) == the accepted line's `net_amount` (ex-tax, line +
  prorated global discount), matched by `treatment_id`. Completed
  sessions keep their amount (payments already booked it); cancelled
  ones are inert. Cent drift lands on the last pending session.
- **A treatment's price is booked exactly once** — by sessions or by
  the odontogram, never both. Finalization calls
  `TreatmentService.perform(publish_price=False)` so the performed
  event carries `unit_price: null` (sessions already booked the money);
  conversely, `on_treatment_performed` (odontogram-first) cancels the
  item's pending sessions so they can't book on top of the full-price
  row payments just wrote. Breaking either side double-charges the
  patient.
- **Completion still emits an audit event.** `treatment_plan.item_completed_without_note`
  fires whenever an item is completed; the timeline reconciles it with a
  follow-up `clinical_notes.treatment_created` event when the client
  captured a note. Don't bypass — the event is the only signal that an
  item was completed at all.
- **Don't import `clinical_notes`.** The dependency is one-way:
  `clinical_notes → treatment_plan`. The frontend calls both modules
  during completion; do not add a server-side cross-module import.
- **Auto-close cron lives here** (`tasks.py:auto_close_expired_plans`),
  not in budget — closing a plan is a treatment_plan write and budget
  is in this module's depends, so the read of `budgets` from the
  cron query is allowed.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0006-budget-public-link-2-factor-auth.md`

## CHANGELOG

See `./CHANGELOG.md`.
