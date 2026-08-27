import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

/**
 * Slot registrations for the `payments` module.
 *
 * Hosts (`budget`) expose stable slot names. The slot registry is the
 * only contract — the budget module never imports payments code.
 */
export default defineNuxtPlugin(() => {
  // Cobros vinculados al presupuesto. Renders inside the budget-detail
  // sidebar with `ctx = { budget }`. Shows total / cobrado / pendiente
  // plus the allocation history and a "Cobrar" CTA that opens the
  // shared `PaymentCreateModal` pre-filled with budget + patient ids.
  registerSlot('budget.detail.sidebar', {
    id: 'payments.budget.detail.sidebar.collected',
    component: defineAsyncComponent(
      () => import('../components/BudgetPaymentsCard.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // Payments report card on /reports. Lets the reports module stay
  // unaware of payments while users still discover the dashboard from
  // the central reports landing.
  // Post-completion follow-up: "Cobrar" shortcut for the visit's
  // patient (#207). Agenda exposes the slot; payments registers into
  // it — agenda never imports payments code.
  registerSlot('appointment.completed.followup', {
    id: 'payments.appointment.collect-prompt',
    component: defineAsyncComponent(
      () => import('../components/CollectFollowupPrompt.vue')
    ),
    permission: 'payments.record.write',
    order: 20
  })

  registerSlot('reports.categories', {
    id: 'payments.reports.categories.dashboard',
    component: defineAsyncComponent(
      () => import('../components/PaymentsReportEntry.vue')
    ),
    permission: 'payments.reports.read',
    order: 40
  })

  // Patient ledger sub-mode inside the patient detail "Administración"
  // tab. The patients module exposes the slot name and renders
  // `<ModuleSlot>`; it never imports anything from payments.
  registerSlot('patient.detail.administracion.payments', {
    id: 'payments.patient.detail.administracion.panel',
    component: defineAsyncComponent(
      () => import('../components/PatientPaymentsPanel.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // Patient Resumen — balance smart-card. Same slot contract pattern as
  // the panel above; the patients host page exposes the slot name and
  // renders <ModuleSlot> only.
  registerSlot('patient.summary.cards', {
    id: 'payments.patient.summary.cards.balance',
    component: defineAsyncComponent(
      () => import('../components/summary/BalanceCard.vue')
    ),
    permission: 'payments.record.read',
    order: 30
  })

  // /patients list — per-row debt badge. Host (`patients`) renders
  // <ModuleSlot name="patients.list.row.financial" :ctx="{ patient_id, summary }" />.
  registerSlot('patients.list.row.financial', {
    id: 'payments.patients.list.row.debt',
    component: defineAsyncComponent(
      () => import('../components/PatientListDebtCell.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // /patients list — "Con deuda" filter chip in the toolbar.
  registerSlot('patients.list.filter', {
    id: 'payments.patients.list.filter.withDebt',
    component: defineAsyncComponent(
      () => import('../components/PatientListDebtFilter.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // /budgets list — per-row collected/pending mini-progress + status chip.
  registerSlot('budget.list.row.payments', {
    id: 'payments.budget.list.row.collected',
    component: defineAsyncComponent(
      () => import('../components/BudgetListPaymentsCell.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // /budgets list — payment-status multi-select chip in the toolbar.
  registerSlot('budget.list.filter', {
    id: 'payments.budget.list.filter.paymentStatus',
    component: defineAsyncComponent(
      () => import('../components/BudgetListPaymentsFilter.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })
})
