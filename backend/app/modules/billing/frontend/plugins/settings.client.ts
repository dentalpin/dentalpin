/**
 * Getting-started rule: an invoice cannot be issued without a series.
 * ``FAC``/``RECT`` are seeded by ``clinic.created``; this rule catches
 * clinics that predate the seed or deleted their series.
 */
import {
  registerGettingStartedRule,
  registerSettingsPage
} from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

interface SeriesOnboardingState { loaded: boolean, count: number }

const useSeriesOnboardingState = () =>
  useState<SeriesOnboardingState>('billing:onboarding-series', () => ({ loaded: false, count: 0 }))

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'preferences',
    category: 'billing',
    labelKey: 'billingSettings.title',
    descriptionKey: 'billingSettings.description',
    icon: 'i-lucide-settings-2',
    permission: PERMISSIONS.billing.read,
    component: () => import('../components/BillingSettingsPage.vue'),
    searchKeywords: ['factura', 'invoice', 'pago', 'payment', 'banco', 'bank', 'pie', 'footer'],
    order: 30
  })

  registerGettingStartedRule({
    id: 'invoice-series',
    labelKey: 'invoiceSeries.onboarding.label',
    descriptionKey: 'invoiceSeries.onboarding.description',
    icon: 'i-lucide-receipt-text',
    to: '/settings/invoice-series',
    permission: PERMISSIONS.billing.read,
    order: 60,
    severity: 'warning',
    load: async (api) => {
      const state = useSeriesOnboardingState()
      // Background onboarding probe — never toast from here.
      const res = await api.get<{ data: unknown[] }>('/api/v1/billing/series', { errorToast: false })
      state.value = { loaded: true, count: res.data.length }
    },
    when: () => {
      const s = useSeriesOnboardingState().value
      return s.loaded && s.count === 0
    }
  })
})
