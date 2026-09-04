# Payments module

Patient-centric collections, allocations to budgets / on-account,
refunds, patient ledger, and dental payment reports.

Issue #53. ADR 0010 documents the architectural inversion: billing
depends on payments, the reverse is forbidden. The link
``invoice ↔ payment`` lives in the billing module's own
``invoice_payments`` table; payments does not import billing.

## Public API

Routes mounted at `/api/v1/payments/`.

| Path | Method | Permission |
|---|---|---|
| `/` | GET | `payments.record.read` |
| `/` | POST | `payments.record.write` |
| `/{id}` | GET | `payments.record.read` |
| `/{id}/reallocate` | POST | `payments.record.write` |
| `/{id}/refunds` | GET | `payments.record.read` |
| `/{id}/refunds` | POST | `payments.record.refund` |
| `/patients/{patient_id}/ledger` | GET | `payments.record.read` |
| `/patients/{patient_id}/pending-charges` | GET | `payments.record.read` |
| `/budgets/{budget_id}/allocations` | GET | `payments.record.read` |
| `/reports/summary` | GET | `payments.reports.read` |
| `/reports/trends` | GET | `payments.reports.read` |
| `/reports/by-method` | GET | `payments.reports.read` |
| `/reports/by-professional` | GET | `payments.reports.read` |
| `/reports/aging-receivables` | GET | `payments.reports.read` |
| `/reports/refunds` | GET | `payments.reports.read` |

## Dependencies

`manifest.depends = ["patients", "budget"]`. **Never add billing** —
that would create a cycle (billing.depends includes payments). Read
ADR 0010 before touching the dependency list.

## Permissions

`payments.record.{read,write,refund}`, `payments.reports.read`.

Refund is admin/dentist by default. Clinic admins may grant
`payments.record.refund` to receptionists via the roles UI — no code
change required.

## Tools exposed

Agent tools in `tools.py` (wrap `PaymentReportsService`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `payments_summary` | READ | `PaymentReportsService.summary` | `payments.reports.read` |
| `collections_by_method` | READ | `PaymentReportsService.by_method` | `payments.reports.read` |
| `record_payment` | WRITE | `workflow.record_payment` | `payments.record.write` |
| `patient_payment_history` | READ | `LedgerService.get_patient_ledger` (filtered) | `payments.record.read` |

**Off-books boundary.** These expose the **collection axis only** (gross
collected / refunded). They drop `clinic_receivable_total` /
`patient_credit_total` — "what's owed" is the invoiced-minus-collected
diff this module must never surface (see the gotcha below). Aging /
ledger-**balance** tools are deliberately NOT exposed to the agent:
`patient_payment_history` strips the ledger down to payments + refunds
(+ on-account balance, which is a subset of what was paid) and drops
`total_earned` / `patient_credit` / `clinic_receivable` before
returning. Enforced by tests in `tests/test_module_tools.py`.

## Events emitted

- `payment.recorded` — payload `{clinic_id, payment_id, patient_id, amount, currency, method, payment_date, occurred_at}`.
- `payment.allocated` — payload `{clinic_id, payment_id, patient_id, actor_id, allocation_id, target_type, target_id, amount, previous_target_type, previous_target_id, context, occurred_at}`. Fired once per allocation row on create and on reallocate. **Published transactionally** (`db=db`, ADR 0019): billing's `payment_bridge` runs inside the same session and mirrors budget allocations onto the budget's invoices — a failure there rolls the payment back. `context` is an opaque dict echoed from `record_payment(context=...)`; this module never reads it.
- `payment.refunded` — payload `{clinic_id, payment_id, refund_id, amount, reason_code, refunded_by, occurred_at}`. **Published transactionally** (billing recomputes invoice status in-tx).

## Events consumed

| Event | Handler | Effect |
|---|---|---|
| `odontogram.treatment.performed` | `on_treatment_performed` | Upsert `PatientEarnedEntry` (single-session row, `source_session_id=NULL`) |
| `treatment_plan.item_session_completed` | `on_session_completed` | Upsert per-session `PatientEarnedEntry` keyed on `(treatment_id, source_session_id)`. Replaces the legacy `treatment_plan.treatment_completed` subscription since the multi-session feature — see ADR/changelog. |

Both handlers require `unit_price`/`price_snapshot` in the payload. If
the publisher omits it, the entry is skipped with a warning — see
gotchas below. **A null price is deliberate, not an error**: when
treatment_plan finalizes a sessioned item it publishes
`odontogram.treatment.performed` with `unit_price: null` because the
sessions already booked the money per-session. Exclusivity between the
two earned paths is the publishers' responsibility
(`docs/technical/payments/events.md`); this module stays a dumb ledger.
Idempotency is DB-level: `uq_earned_treatment_session` (session rows) +
partial index `uq_earned_treatment_null_session` (NULL rows, `pay_0004`
— plain unique constraints treat NULLs as distinct).

## Frontend slots rendered

Entry points for payment-*gateway* modules (#365 / #263, ADR 0010).
`payments` registers nothing into them; on a clean install they render
nothing. Country gating is the gateway's `condition` (same as
`verifactu` / `india_gst`), never ours.

| Slot | Where | `ctx` |
|---|---|---|
| `payments.collect.actions` | next to "New payment" (payments page), "Cobrar" (`PatientPaymentsPanel`, both buttons), "Collect" (`BudgetPaymentsCard`) | `{ patient?, budget?, prefer_invoice_id? }` — each host passes what it has |
| `payments.list.row.meta` | payments list row, under the date · method line | `{ payment }` |
| `payments.ledger.row.meta` | patient ledger row, under the meta line | `{ entry }` |
| `payments.detail.sections` | payments list row, above the refund action (there is no dedicated detail view yet — this is its stand-in) | `{ payment }` |

## Frontend slots consumed

| Slot | Component | Permission |
|---|---|---|
| `budget.detail.sidebar` | `BudgetPaymentsCard` (cobrado / pendiente / allocations + "Cobrar" CTA) | `payments.record.read` |
| `reports.categories` | `PaymentsReportEntry` (card on `/reports` linking to `/reports/payments`) | `payments.reports.read` |
| `patient.detail.administracion.payments` | `PatientPaymentsPanel` (patient ledger inside the Administración tab — KPIs + timeline + row menu with refund / "Asignar a presupuesto…" (`PaymentReallocateModal` → `/reallocate`) + "Pendiente de cobrar" card) | `payments.record.read` |

Registered in `frontend/plugins/slots.client.ts`. Cards receive `ctx`
from the host page (`{ budget }`, `{ patient, patientId }`) and never
import anything from the host module's code — only the slot name and
the public endpoints.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=False`.
- Fiscal/contable retention forbids data deletion; uninstall is
  blocked by manifest.

## Gotchas

- **Methods are a closed list** — `PAYMENT_METHODS` (models) and the
  `PaymentMethod` Literal (schemas) must stay in sync; `upi` /
  `netbanking` (#365) exist for India gateway modules; the create modal
  and the list's method filter show them only when the clinic's
  server-side country is `IN` (`useClinicCountry`). The refund modal
  always offers the source payment's method, whatever the country.
- **`idempotency_key` short-circuits `record_payment`** (#365): a key
  hit returns the existing payment *before* any validation — the
  caller's retry gets the original row, allocations untouched. Unique
  per clinic via a partial index (`NOT NULL` only); `None`/empty never
  collides.

- **No `is_voided` flag.** Total reverso is `Refund(amount=Payment.amount)`.
  Don't reintroduce the legacy flag — the report stack relies on
  Refund rows being the only adjustment vector.
- **No paid-vs-invoiced metrics.** Reports must not subtract `paid` from
  `invoiced` or `earned` from `invoiced`. Dental clinics legitimately
  leave some treatments off the invoice; exposing that diff documents
  the operative and is a stopper for adoption. See ADR 0010.
- **No imports from odontogram or treatment_plan.** Earned data enters
  through event payloads only. Add fields to the publisher when needed —
  the snapshot pattern is the contract.
- **Allocations sum invariant** is enforced in the service, not the DB.
  Schemas validate at the boundary so 4xx never reach the workflow.
- **Cross-clinic budgets** are rejected by the workflow. UI must filter
  budget pickers to current clinic — `AllocationTargetSelect` lists the
  patient's accepted/completed budgets from `/api/v1/budget/budgets`
  (issue #178: never ask reception for a UUID).
- **`on_account` is unlinked by design.** An anticipo touches neither
  invoices nor budgets until reassigned; the create modal says so
  under "Destino" and the ledger offers "Asignar a presupuesto…". Money
  allocated to a **budget** *is* mirrored onto that budget's invoices by
  billing (transactional `payment.allocated` subscriber) — that is
  billing's concern, this module only publishes.
- **`Clinic.currency` snapshot.** Payments capture the clinic currency
  at write time. If a clinic ever switches currency, historical
  payments stay in the old one (correct behaviour).

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0010-payments-as-primitive-module.md`
- `docs/adr/0019-transactional-event-handlers.md`

## CHANGELOG

See `./CHANGELOG.md`.
