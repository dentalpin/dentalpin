import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { registerGettingStartedRule } from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

interface PatientsOnboardingState { loaded: boolean, total: number }

const usePatientsOnboardingState = () =>
  useState<PatientsOnboardingState>('patients:onboarding', () => ({ loaded: false, total: 0 }))

export default defineNuxtPlugin(() => {
  registerSlot('dashboard.activity', {
    id: 'patients.dashboard.recent',
    component: defineAsyncComponent(() => import('../components/home/RecentPatientsPanel.vue')),
    order: 10,
    permission: PERMISSIONS.patients.read
  })

  // QuickActionsCard — patients-owned card. Renders last in the grid
  // (order 60) so the data snapshots from other modules surface first.
  registerSlot('patient.summary.cards', {
    id: 'patients.patient.summary.cards.quickActions',
    component: defineAsyncComponent(() => import('../components/patient/QuickActionsCard.vue')),
    order: 60,
    permission: PERMISSIONS.patients.read
  })

  // Getting-started (optional): the first patient is the natural "try it"
  // step once the clinic is configured.
  registerGettingStartedRule({
    id: 'first-patient',
    labelKey: 'patients.onboarding.label',
    descriptionKey: 'patients.onboarding.description',
    icon: 'i-lucide-user-plus',
    to: '/patients?new=1',
    permission: PERMISSIONS.patients.read,
    order: 90,
    optional: true,
    severity: 'info',
    load: async (api) => {
      const state = usePatientsOnboardingState()
      // Background onboarding probe (best-effort via allSettled) — must
      // never toast on failure.
      const res = await api.get<{ total: number }>('/api/v1/patients?page_size=1', { errorToast: false })
      state.value = { loaded: true, total: res.total }
    },
    when: () => {
      const s = usePatientsOnboardingState().value
      return s.loaded && s.total === 0
    }
  })
})
