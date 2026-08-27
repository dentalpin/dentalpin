// Treatment-plan slot registrations.
//
// Clinical-notes-related slots (patient.timeline.treatments,
// patient.summary.feed, odontogram.diagnosis.sidebar,
// odontogram.condition.actions) are owned by the ``clinical_notes``
// module since issue #60.
import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

export default defineNuxtPlugin(() => {
  // Patient Resumen — active-plan smart card. The patients module
  // exposes the ``patient.summary.cards`` slot and never imports
  // anything from treatment_plan; this registration is the contract.
  registerSlot('patient.summary.cards', {
    id: 'treatment_plan.patient.summary.cards.plan',
    component: defineAsyncComponent(
      () => import('../components/summary/PlanCard.vue')
    ),
    order: 10,
    permission: 'treatment_plan.plans.read'
  })

  // Post-completion follow-up: linked plan treatments the visit left
  // unmarked, with one-click "mark as performed" (#207). Rendered by
  // agenda's CompletionFollowupHost; the slot is the only contract.
  registerSlot('appointment.completed.followup', {
    id: 'treatment_plan.appointment.mark-performed-prompt',
    component: defineAsyncComponent(
      () => import('../components/clinical/MarkPerformedFollowupPrompt.vue')
    ),
    order: 5,
    permission: 'treatment_plan.plans.write'
  })

  // "New quote" form — tells reception the patient already has a plan
  // without a quote and sends them to generate it from the plan (#177).
  registerSlot('budget.new.form', {
    id: 'treatment_plan.budget.new.form.plan-hint',
    component: defineAsyncComponent(
      () => import('../components/budget/NewBudgetPlanHint.vue')
    ),
    order: 10,
    permission: 'treatment_plan.plans.read'
  })
})
