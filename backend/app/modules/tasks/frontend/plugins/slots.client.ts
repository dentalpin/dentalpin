import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

export default defineNuxtPlugin(() => {
  registerSlot('dashboard.attention', {
    id: 'tasks.dashboard.open-count',
    component: defineAsyncComponent(() => import('../components/TasksDashboardWidget.vue')),
    permission: 'tasks.read',
    order: 40
  })
})
