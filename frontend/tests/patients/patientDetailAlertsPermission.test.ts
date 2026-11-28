import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import PatientDetailPage from '#module-layers/patients/frontend/pages/patients/[id].vue'

/**
 * #1268: the alerts route needs patients_clinical.medical.read. The
 * receptionist role lacks it, and useApi toasts every 403 even when the
 * caller catches it, so the page must not request it for that role.
 */
const { get, granted } = vi.hoisted(() => ({ get: vi.fn(), granted: new Set<string>() }))

mockNuxtImport('useApi', () => () => ({ get, del: vi.fn() }))
mockNuxtImport('useToast', () => () => ({ add: vi.fn() }))
mockNuxtImport('useRoute', () => () => ({ params: { id: 'p-1' }, query: {}, fullPath: '/patients/p-1' }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: ref('en') }))
mockNuxtImport('usePermissions', () => () => ({ can: (p: string) => granted.has(p) }))
// patients_clinical layer composable (not auto-imported when CI runs without layers).
vi.stubGlobal('useMedicalHistory', () => ({
  medicalHistory: ref(null),
  isLoaded: ref(false),
  error: ref(null),
  isSaving: ref(false),
  fetchMedicalHistory: vi.fn(),
  saveMedicalHistory: vi.fn()
}))

const ALERTS_URL = '/api/v1/patients_clinical/patients/p-1/alerts'

function respond(url: string) {
  if (url === '/api/v1/patients/p-1/extended') {
    return Promise.resolve({ data: { id: 'p-1', first_name: 'Ana', last_name: 'Ruiz' } })
  }
  if (url === ALERTS_URL) {
    return Promise.resolve({ data: { alerts: [{ type: 'allergy', severity: 'critical', title: 'Latex' }] } })
  }
  return Promise.resolve({ data: null })
}

const mountPage = () => mountSuspended(PatientDetailPage, { shallow: true })

describe('Patient detail page alerts fetch (#1268)', () => {
  let wrapper: VueWrapper | undefined
  beforeEach(() => {
    get.mockReset()
    get.mockImplementation(respond)
    granted.clear()
    clearNuxtData()
  })
  afterEach(() => wrapper?.unmount())

  it('does not request alerts without medical.read (receptionist)', async () => {
    granted.add('patients_clinical.emergency.read')
    wrapper = await mountPage()
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/v1/patients/p-1/extended')
    expect(get).not.toHaveBeenCalledWith(ALERTS_URL)
  })

  it('requests alerts with medical.read', async () => {
    granted.add('patients_clinical.medical.read')
    wrapper = await mountPage()
    await flushPromises()

    expect(get).toHaveBeenCalledWith(ALERTS_URL)
  })
})
