import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

/**
 * Slot registration for the `patient_segments` module.
 *
 * Contributes its card into `patient.summary.cards` — the same
 * extension point `patient_relationships` uses. order: 56 places it
 * just after the relationships card (order: 55).
 */
export default defineNuxtPlugin(() => {
  registerSlot('patient.summary.cards', {
    id: 'patient_segments.patient.summary.cards.segments',
    component: defineAsyncComponent(
      () => import('../components/summary/PatientSegmentsCard.vue')
    ),
    order: 56,
    permission: PERMISSIONS.patientSegments.read
  })
})
