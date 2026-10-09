/**
 * Getting-started rule: the clinic needs at least one catalog item to
 * budget / plan / bill. Seeded by ``clinic.created`` on setup; this rule
 * catches installs where the seed failed or was emptied, and resolves it
 * inline (mini-modal → ``POST /catalog/seed``) or hands off to the page.
 */
import { registerGettingStartedRule } from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

interface CatalogOnboardingState { loaded: boolean, total: number }

const useCatalogOnboardingState = () =>
  useState<CatalogOnboardingState>('catalog:onboarding', () => ({ loaded: false, total: 0 }))

export default defineNuxtPlugin(() => {
  registerGettingStartedRule({
    id: 'catalog-empty',
    labelKey: 'catalog.onboarding.label',
    descriptionKey: 'catalog.onboarding.description',
    icon: 'i-lucide-list-checks',
    to: '/settings/catalog',
    permission: PERMISSIONS.catalog.read,
    modal: () => import('../components/catalog/CatalogSeedQuickModal.vue'),
    order: 50,
    severity: 'warning',
    load: async (api) => {
      const state = useCatalogOnboardingState()
      const res = await api.get<{ total: number }>('/api/v1/catalog/items?page_size=1')
      state.value = { loaded: true, total: res.total }
    },
    when: () => {
      const s = useCatalogOnboardingState().value
      return s.loaded && s.total === 0
    }
  })
})
