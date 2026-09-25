import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

/**
 * Slot registrations for the `prescriptions` module.
 *
 * No `patient.detail.tabs` consumer exists on the patient page, so the
 * module surfaces through the live extension points instead: a "Nueva
 * receta" action (deep-link with the patient preselected) plus a recent
 * prescriptions card on the summary grid.
 */
export default defineNuxtPlugin(() => {
  registerSlot('patient.summary.actions', {
    id: 'prescriptions.patient.new-prescription',
    component: defineAsyncComponent(() => import('../components/NewPrescriptionButton.vue')),
    permission: 'prescriptions.write',
    order: 21
  })
  registerSlot('patient.summary.cards', {
    id: 'prescriptions.patient.summary.cards.recent',
    component: defineAsyncComponent(() => import('../components/summary/PrescriptionsCard.vue')),
    permission: 'prescriptions.read',
    order: 57
  })
})
