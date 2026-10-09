import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

/**
 * Slot registration for the `patient_relationships` module.
 *
 * Contributes its own card into `patient.summary.cards` — the same
 * extension point `patients_clinical`'s MedicalHistoryCard uses — without
 * either module importing the other. order: 55 places it just after
 * MedicalHistoryCard (order: 50) and before patients' QuickActionsCard
 * (order: 60, meant to render last — don't tie with it).
 */
export default defineNuxtPlugin(() => {
  registerSlot('patient.summary.cards', {
    id: 'patient_relationships.patient.summary.cards.relationships',
    component: defineAsyncComponent(
      () => import('../components/summary/PatientRelationshipsCard.vue')
    ),
    order: 55,
    permission: PERMISSIONS.patientRelationships.read
  })
})
