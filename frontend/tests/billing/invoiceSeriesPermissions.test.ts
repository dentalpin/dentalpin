import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import InvoiceSeriesPage from '#module-layers/billing/frontend/pages/settings/invoice-series/index.vue'
import settingsRegistryPlugin from '~/plugins/settings.registry'

// #1273: series management is `billing.admin` on the API, and `dentist`
// holds it (#542). The settings entry and the create/edit/reset buttons
// must follow that permission, not admin-only `admin.*` ones.

const registered = vi.hoisted(() => [] as Array<{ path: string, permission?: string | string[] }>)
vi.mock('~/composables/useSettingsRegistry', () => ({
  registerSettingsPage: (entry: { path: string, permission?: string | string[] }) => { registered.push(entry) },
  registerGettingStartedRule: () => {}
}))

// What `/me` gives each role (billing manifest: admin and dentist `*`).
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ['admin.users.write', 'admin.clinic.read', 'billing.read', 'billing.write', 'billing.admin'],
  dentist: ['billing.read', 'billing.write', 'billing.admin'],
  receptionist: ['billing.read', 'billing.write']
}
const role = ref('dentist')
mockNuxtImport('usePermissions', () => () => {
  const can = (p: string) => (ROLE_PERMISSIONS[role.value] ?? []).includes(p)
  return { can, isAdmin: ref(can('admin.users.write')) }
})
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: ref('en') }))

const series = [
  { id: 's-1', prefix: 'FAC', series_type: 'invoice', description: '', current_number: 3, reset_yearly: true, is_default: true, is_active: true },
  { id: 's-2', prefix: 'RECT', series_type: 'credit_note', description: '', current_number: 0, reset_yearly: true, is_default: true, is_active: true }
]
// useInvoices lives in the billing layer. CI's frontend-test runs without
// the layers, so a global stub stands in for the auto-import there; with the
// layers loaded the real composable runs on the mocked useApi.
mockNuxtImport('useApi', () => () => ({ get: vi.fn(async () => ({ data: series })), post: vi.fn(), put: vi.fn() }))
vi.stubGlobal('useInvoices', () => ({
  fetchSeries: vi.fn(async () => series),
  createSeries: vi.fn(),
  updateSeries: vi.fn(),
  resetSeriesCounter: vi.fn()
}))

describe('invoice series settings permissions (#1273)', () => {
  afterEach(() => {
    role.value = 'dentist'
  })

  it('registers the settings entry behind billing.admin', () => {
    registered.length = 0
    const registerHostPages = settingsRegistryPlugin as unknown as () => void
    registerHostPages()
    const entry = registered.find(e => e.path === 'invoice-series')
    expect(entry?.permission).toBe('billing.admin')
  })

  it.each([
    ['dentist', true],
    ['admin', true],
    ['receptionist', false]
  ])('%s sees the create and edit buttons: %s', async (r, visible) => {
    role.value = r
    const wrapper = await mountSuspended(InvoiceSeriesPage)
    await flushPromises()
    try {
      expect(wrapper.text()).toContain('FAC')
      expect(wrapper.text().includes('invoiceSeries.new')).toBe(visible)
      expect(wrapper.find('button[aria-label="common.edit"]').exists()).toBe(visible)
    } finally { wrapper.unmount() }
  })
})
