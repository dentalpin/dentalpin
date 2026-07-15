# payments — CHANGELOG

## Unreleased

- i18n: add French locale (`fr.json`) with full UI coverage.

- fix(security): lock the payment row `FOR UPDATE` before the refund
  cap check (audit S3/C1, #97). Two concurrent refunds could both read
  `already_refunded` before either inserted, letting Σrefund exceed
  `payment.amount` and driving `net_paid` negative. The row lock
  serializes them so the cap holds.

- feat(agents): two new copilot tools — `record_payment` (WRITE, wraps
  `workflow.record_payment`, allocation-sum errors surfaced structurally)
  and `patient_payment_history` (READ, collection axis only: drops
  `total_earned`/`patient_credit`/`clinic_receivable` from the ledger).

- feat(agents): expose `tools.py` — `payments_summary`,
  `collections_by_method` (READ). Off-books: **collection-axis only**
  (gross collected/refunded; never receivable/credit/pending). Issue #81
  P0 batch.

- chore(migration ``pay_0003``): drop the ``ck_earned_amount_nonneg``
  check on ``patient_earned_entries``. Migration imports need to land
  Gesdén's ``Nota Económica`` credit-note rows (negative
  ``TtosMed.Importe``) so the patient ledger reconciles with the
  source's running total. Event-driven publishers still emit
  non-negative amounts in normal operation.
- feat(earned-per-session): ``PatientEarnedEntry`` gains
  ``source_session_id`` + ``description`` and is now keyed on
  ``(treatment_id, source_session_id)`` so multi-session treatments
  produce one row per session. Replaced the ``treatment_plan
  .treatment_completed`` subscription with
  ``treatment_plan.item_session_completed`` (handler
  ``on_session_completed``). Migration ``pay_0002`` adds the column,
  best-effort backfills ``source_session_id`` from
  ``planned_treatment_item_sessions`` when the module is installed, and
  swaps the unique index.
- feat(pending-charges): new ``GET /payments/patients/{id}/pending-charges``
  returns the FIFO-virtual list of earned entries not yet covered by
  net payments. ``PatientPaymentsPanel`` renders a "Pendiente de
  cobrar" card at the top of the patient ``Pagos`` tab so reception
  can collect when the patient leaves the box, with the amount
  pre-filled in ``PaymentCreateModal``.
- refactor(perms): migrate hardcoded ``can('payments.record.{write,refund,read}')`` strings in the payments list, ``PatientPaymentsPanel`` and ``BudgetPaymentsCard`` to ``PERMISSIONS.payments.*`` (new entries in the host permissions config).
- docs(user-manual): reescribir pantalla /payments e index del módulo (ES + EN).

### Changed (reports dashboard redesign, 2026-05-17)

- `/reports/payments` reescrito con calm-design: hero KPIs (cobrado
  neto + sparkline + delta vs periodo anterior, pendiente con mini
  bars por bucket de antigüedad), KPIs secundarios con sparkline,
  tendencia full-width (consume por primera vez
  `GET /reports/trends`), donut por método, top profesionales,
  aging detail y devoluciones por motivo. Toda interacción dispara
  drill-down a `/payments` (o `/patients` para aging) con el rango
  preservado por query string. Sin dependencias nuevas: viz
  resuelta con SVG en `frontend/app/components/charts/*`
  (`Sparkline`, `BarRow`, `DonutChart`, `TrendAreaChart`), genéricos
  y reusables por cualquier módulo. Mantiene el invariante
  off-books (sin cruces paid↔invoiced).
- `FilterDateRange` con presets reemplaza los `UInput type=date`
  crudos; `useCurrency` reemplaza el `Intl.NumberFormat` inline y
  el fallback hardcoded a `'EUR'`.
- i18n del módulo: nuevas keys bajo `payments.reports.*`
  (granularity, hero, trend, empty, drilldown, bucket, refresh,
  hints) en ES y EN.

### Added (lists redesign, 2026-05-14)

- `POST /api/v1/payments/summary/by-budgets` — bulk per-budget
  collected/pending/payment_status (cap 100 ids). Off-books safe.
- `POST /api/v1/payments/summary/by-patients` — bulk per-patient
  total_paid/debt/on_account (cap 100 ids). Off-books safe.
- `GET  /api/v1/payments/filters/budgets-by-status` — clinic-wide
  budget id set by payment status (cap 1000 ids, `truncated` flag).
- `GET  /api/v1/payments/filters/patients-with-debt` — clinic-wide
  patient id set with debt ≥ min_debt (cap 1000 ids).
- New slot fillers registered: `patients.list.row.financial`,
  `patients.list.filter`, `budget.list.row.payments`,
  `budget.list.filter`. Enables /patients debt column + "Con deuda"
  filter and /budgets payment-progress column + "Cobro" filter
  without violating module isolation.
- `GET /api/v1/payments` accepts new params: `has_refunds`,
  `has_unallocated`, `amount_min`, `amount_max`, `sort=field:dir`
  (whitelist: `payment_date`, `amount`, `created_at`).
- `/payments` UI rewritten on top of `DataListLayout` + `FilterBar`
  + `useListQuery`. Chips for method, date range with presets,
  paciente como autocomplete (sustituye al campo UUID).
- Initial module skeleton (issue #53).
- Models: `Payment`, `PaymentAllocation`, `Refund`, `PatientEarnedEntry`, `PaymentHistory`.
- Workflow: `record_payment`, `reallocate_payment`, `refund_payment`.
- Read services: `PaymentService`, `PaymentReadService`, `LedgerService`, `PaymentReportsService`.
- Endpoints under `/api/v1/payments/` covering CRUD, refunds, ledger, per-budget allocations, and reports (summary, by-method, by-professional, aging-receivables, refunds, trends).
- Events emitted: `payment.recorded`, `payment.allocated`, `payment.refunded`.
- Events consumed: `odontogram.treatment.performed`, `treatment_plan.treatment_completed` → upsert into `patient_earned_entries`.
- Migration `pay_0001_initial` on the `payments` branch (chains after `bud_0003`).
- `BudgetPaymentsCard` redesign compacto: resumen `Cobrado / Total` con barra de progreso, estado de pendiente en una línea, historial con icono de método + fecha relativa, único CTA "Cobrar" en el header (oculto cuando saldado). Mueve la tarjeta al top del sidebar del detalle de presupuesto (antes caía al fondo del grid).
- `AllocationResponse` ahora expone `method` (del pago padre) — aditivo, sin queries nuevas (ya estaba joinedloaded).
- `BudgetCollectModal` usa `useCurrency().format` en lugar de un `Intl.NumberFormat` inline; prop `currency` retirado (era vestigial).
- `PatientPaymentsPanel` registrado en el slot `patient.detail.administracion.payments` (host: módulo `patients`). Surfacing del ledger del paciente (banner deuda/crédito, KPIs `total_paid` / `clinic_receivable` / `on_account_balance`, sidebar con saldo a favor y último pago, timeline cronológico con menú overflow por pago para reembolsar) dentro del tab Administración de la ficha. Consume `GET /payments/patients/{id}/ledger` ya existente; sin endpoints nuevos.
- `RefundConfirmModal` — formulario corto (importe, método, motivo, nota) usado desde el menú overflow del timeline para `POST /payments/{id}/refunds`.
