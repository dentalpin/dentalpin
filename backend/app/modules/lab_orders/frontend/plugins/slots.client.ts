import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

export default defineNuxtPlugin(() => {
  registerSlot('dashboard.attention', {
    id: 'lab_orders.dashboard.pending',
    component: defineAsyncComponent(() => import('../components/LabOrdersDashboardWidget.vue')),
    permission: 'lab_orders.read',
    order: 60
  })
})
