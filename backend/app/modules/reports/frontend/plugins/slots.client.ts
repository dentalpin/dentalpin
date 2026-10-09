import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

export default defineNuxtPlugin(() => {
  registerSlot('dashboard.hero', {
    id: 'reports.dashboard.overdueHero',
    component: defineAsyncComponent(() => import('../components/home/OverdueHeroTile.vue')),
    order: 30,
    permission: PERMISSIONS.reports.billingRead
  })

  registerSlot('dashboard.attention', {
    id: 'reports.dashboard.overduePanel',
    component: defineAsyncComponent(() => import('../components/home/OverdueInvoicesPanel.vue')),
    order: 20,
    permission: PERMISSIONS.reports.billingRead
  })

  registerSlot('dashboard.activity', {
    id: 'reports.dashboard.weekGlance',
    component: defineAsyncComponent(() => import('../components/home/WeekGlancePanel.vue')),
    order: 20,
    permission: PERMISSIONS.reports.billingRead
  })
})
