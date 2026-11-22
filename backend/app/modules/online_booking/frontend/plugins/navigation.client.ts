import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

export default defineNuxtPlugin(() => {
  const active = useActiveModulesState()
  const { can } = usePermissions()
  registerSlot('app.overlays', {
    id: 'online_booking.navigation-count',
    component: defineAsyncComponent(() => import('../components/OnlineBookingNavigation')),
    condition: () => can('online_booking.read') && !!active.value?.some(module => module.name === 'online_booking')
  })
})
