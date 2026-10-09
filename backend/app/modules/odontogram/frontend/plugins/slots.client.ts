import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

/**
 * Slot registrations for the ``odontogram`` module.
 *
 * Host pages (``patients``) expose stable slot names. The slot
 * registry is the only contract — neither side imports the other.
 */
export default defineNuxtPlugin(() => {
  // Patient Resumen — diagnoses smart-card. Counts planned tooth
  // treatments and shows a sample.
  registerSlot('patient.summary.cards', {
    id: 'odontogram.patient.summary.cards.diagnoses',
    component: defineAsyncComponent(
      () => import('../components/summary/DiagnosesCard.vue')
    ),
    order: 40,
    permission: PERMISSIONS.odontogram.treatmentsRead
  })
})
