import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

/**
 * Slot registrations for the `orthodontics` module (issue #270).
 *
 * Sub-tab inside the Diagnosis mode of the patient clinical tab
 * (periodontogram pattern) plus a case-status card on the summary grid.
 */
export default defineNuxtPlugin(() => {
  registerSlot('patient.diagnosis.subtabs', {
    id: 'orthodontics',
    component: defineAsyncComponent(
      () => import('../components/OrthodonticsView.vue')
    ),
    order: 21,
    permission: 'orthodontics.cases.read',
    labelKey: 'orthodontics.tab.label'
  })
  registerSlot('patient.summary.cards', {
    id: 'orthodontics.patient.summary.cards.status',
    component: defineAsyncComponent(() => import('../components/summary/OrthoCard.vue')),
    permission: 'orthodontics.cases.read',
    order: 58
  })
})
