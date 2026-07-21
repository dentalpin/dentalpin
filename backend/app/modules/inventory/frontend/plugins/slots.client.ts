import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

export default defineNuxtPlugin(() => {
  registerSlot('dashboard.attention', {
    id: 'inventory.dashboard.low-stock',
    component: defineAsyncComponent(() => import('../components/InventoryDashboardWidget.vue')),
    permission: 'inventory.read',
    order: 50
  })
})
