import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import BudgetSignatureCard from '../../module_layers/budget/frontend/components/budget/BudgetSignatureCard.vue'
import PersonalInfoCard from '../../module_layers/patients/frontend/components/patient/info/PersonalInfoCard.vue'
import PatientTimeline from '../../module_layers/patient_timeline/frontend/components/patient/PatientTimeline.vue'

// Dates must be formatted in the UI language, not English for every
// locale other than Spanish (#1175).

const uiLocale = vi.hoisted(() => ({ value: 'hu' }))

mockNuxtImport('useI18n', () => () => ({
  t: (key: string, params?: Record<string, unknown>) => (params ? `${key} ${JSON.stringify(params)}` : key),
  locale: ref(uiLocale.value)
}))
mockNuxtImport('usePermissions', () => () => ({ can: () => true }))
mockNuxtImport('useProfessionals', () => () => ({
  professionals: ref([{ id: 'p1' }]),
  fetchProfessionals: vi.fn(),
  getProfessionalById: () => null,
  getProfessionalFullName: () => ''
}))
// With module layers linked (local dev) the real layer composables run and
// read through useApi; in CI (no layers) the vi.stubGlobal stand-ins run.
const apiGet = vi.hoisted(() => vi.fn())
mockNuxtImport('useApi', () => () => ({ get: apiGet, post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() }))
mockNuxtImport('useCurrency', () => () => ({ format: (n: number) => String(n) }))

const ENGLISH = /AM|PM|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec/

beforeEach(() => {
  uiLocale.value = 'hu'
  apiGet.mockReset()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('date formatting follows the UI locale (#1175)', () => {
  it('BudgetSignatureCard signed-at time in Hungarian', async () => {
    const signature = {
      signed_by_name: 'Test Signer',
      signed_at: '2026-03-19T15:30:00Z',
      signature_method: 'drawn',
      relationship_to_patient: 'self',
      document_hash: null
    }
    apiGet.mockResolvedValue({ data: signature })
    vi.stubGlobal('useBudgets', () => ({
      fetchSignature: async () => signature,
      downloadSignedPDF: vi.fn()
    }))
    const wrapper = await mountSuspended(BudgetSignatureCard, {
      props: { budgetId: 'b1', budgetStatus: 'accepted' }
    })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('2026. márc.')
    expect(text).not.toMatch(ENGLISH)
  })

  it('PersonalInfoCard date of birth in Hungarian', async () => {
    const wrapper = await mountSuspended(PersonalInfoCard, {
      props: {
        canEdit: false,
        patient: {
          id: 'pt1',
          first_name: 'Test',
          last_name: 'Patient',
          status: 'active',
          date_of_birth: '1985-03-15T12:00:00'
        } as never
      }
    })
    // hu: "1985. 03. 15."; the old es-ES fallback gave "15/03/1985".
    expect(wrapper.text()).toContain('1985. 03. 15.')
    expect(wrapper.text()).not.toContain('15/03/1985')
  })

  it('PatientTimeline weekday and time in German', async () => {
    uiLocale.value = 'de'
    const threeDaysAgo = new Date()
    threeDaysAgo.setDate(threeDaysAgo.getDate() - 3)
    threeDaysAgo.setHours(15, 30, 0, 0)
    const entry = {
      id: 'e1',
      event_type: 'appointment.completed',
      event_category: 'visit',
      title: 'Synthetic entry',
      description: null,
      occurred_at: threeDaysAgo.toISOString(),
      created_by: null,
      event_data: {}
    }
    apiGet.mockResolvedValue({ data: { entries: [entry], total: 1, has_more: false } })
    vi.stubGlobal('usePatientTimeline', () => ({
      entries: ref([entry]),
      total: ref(1),
      hasMore: ref(false),
      selectedCategory: ref(null),
      isLoading: ref(false),
      isLoadingMore: ref(false),
      categoryOptions: ref([]),
      loadMore: vi.fn(),
      setCategory: vi.fn(),
      getEventIcon: () => 'i-lucide-circle',
      getCategoryColor: () => 'neutral',
      isHighImpact: () => false,
      isLowImpact: () => false
    }))
    const wrapper = await mountSuspended(PatientTimeline, { props: { patientId: 'pt1' } })
    await flushPromises()
    const weekday = new Intl.DateTimeFormat('de', { weekday: 'long' }).format(threeDaysAgo)
    const text = wrapper.text()
    expect(text).toContain(weekday)
    expect(text).toContain('15:30')
    expect(text).not.toMatch(ENGLISH)
  })
})
