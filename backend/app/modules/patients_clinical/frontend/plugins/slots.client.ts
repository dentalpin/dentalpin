import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

/**
 * Slot registrations for the ``patients_clinical`` module.
 *
 * The patients module exposes ``patient.summary.cards`` (Resumen grid)
 * and ``patient.header.alerts`` (sticky header). patients_clinical
 * contributes its medical-history card and inline alert chips without
 * either side importing the other.
 */
export default defineNuxtPlugin(() => {
  registerSlot('patient.summary.cards', {
    id: 'patients_clinical.patient.summary.cards.medical',
    component: defineAsyncComponent(
      () => import('../components/summary/MedicalHistoryCard.vue')
    ),
    order: 50,
    permission: PERMISSIONS.medicalHistory.read
  })

  registerSlot('patient.header.alerts', {
    id: 'patients_clinical.patient.header.alerts',
    component: defineAsyncComponent(
      () => import('../components/header/PatientHeaderAlertsChips.vue')
    ),
    order: 10,
    permission: PERMISSIONS.medicalHistory.read
  })
})
