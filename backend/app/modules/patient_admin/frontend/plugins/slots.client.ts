import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

/**
 * Slot registration for the `patient_admin` module.
 *
 * Contributes its own card into `patient.summary.cards` — the same
 * extension point `patients_clinical`'s MedicalHistoryCard uses — without
 * either module importing the other. order: 60 places it just after
 * MedicalHistoryCard (order: 50).
 */
export default defineNuxtPlugin(() => {
  registerSlot('patient.summary.cards', {
    id: 'patient_admin.patient.summary.cards.admin',
    component: defineAsyncComponent(
      () => import('../components/summary/PatientAdminCard.vue')
    ),
    order: 60,
    permission: 'patient_admin.relationships.read'
  })
})
