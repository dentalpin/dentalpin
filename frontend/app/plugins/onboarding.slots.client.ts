/**
 * Mounts the "getting started" card on the dashboard hero row (admins
 * only). Client-only: slot entries carry components, which the SSR
 * payload cannot serialize.
 */
import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~/composables/useModuleSlots'
import { PERMISSIONS } from '~/config/permissions'

export default defineNuxtPlugin(() => {
  registerSlot('dashboard.hero', {
    id: 'host.dashboard.onboarding',
    component: defineAsyncComponent(() => import('~/components/onboarding/OnboardingCard.vue')),
    order: 0,
    permission: PERMISSIONS.admin.clinicWrite
  })
})
