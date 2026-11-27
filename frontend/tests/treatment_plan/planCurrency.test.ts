import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { reactive, ref } from 'vue'
import ConfirmPlanModal from '../../module_layers/treatment_plan/frontend/components/clinical/modals/ConfirmPlanModal.vue'
import PipelineTabPanel from '../../module_layers/treatment_plan/frontend/components/treatment-plans/PipelineTabPanel.vue'

// Plan totals follow the clinic currency, not a literal € (#1178).

const { get } = vi.hoisted(() => ({ get: vi.fn() }))

mockNuxtImport('useApi', () => () => ({ get, post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() }))
mockNuxtImport('useClinic', () => () => ({ currentClinic: ref({ id: 'clinic-1', currency: 'HUF' }) }))
// Layer locales are not loaded in the test app: echo the key.
mockNuxtImport('useI18n', () => () => ({
  t: (key: string) => key,
  locale: ref('en'),
  locales: ref([]),
  setLocale: vi.fn()
}))

const row = {
  plan_id: 'plan-1',
  plan_number: 'PLAN-2026-0001',
  plan_title: null,
  plan_status: 'pending',
  days_in_status: 3,
  closure_reason: null,
  items_total: 2,
  items_completed: 0,
  patient: { id: 'p-1', first_name: 'Ana', last_name: 'Kiss', phone: null },
  budget: {
    id: 'b-1',
    status: 'sent',
    total: 125000,
    valid_until: null,
    last_reminder_sent_at: null,
    viewed_at: null
  },
  next_appointment: null
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('plan totals use the clinic currency (#1178)', () => {
  it('ConfirmPlanModal formats the estimated total in HUF', async () => {
    await mountSuspended(ConfirmPlanModal, {
      props: { open: true, planNumber: 'PLAN-2026-0001', itemCount: 2, totalEstimated: 125000 },
      attachTo: document.body
    })
    await flushPromises()
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/HUF\s125,000/)
    expect(text).not.toContain('€')
  })

  it('PipelineTabPanel formats the quote total in HUF and translates its status', async () => {
    get.mockResolvedValue({ data: [row], total: 1, page: 1, page_size: 20 })
    // usePipeline lives in the treatment_plan layer. CI's frontend-test runs
    // without module layers, so it is not an auto-import there: stub it as a
    // global. With layers linked the real composable runs on the mocked useApi.
    vi.stubGlobal('usePipeline', () => ({
      rows: ref([row]),
      total: ref(1),
      page: ref(1),
      pageSize: ref(20),
      loading: ref(false),
      filters: reactive({}),
      fetchPipeline: vi.fn()
    }))
    const wrapper = await mountSuspended(PipelineTabPanel, {
      props: { tab: 'esperando_paciente', q: '' }
    })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toMatch(/HUF\s125,000/)
    expect(text).not.toContain('€')
    expect(text).toContain('budget.status.sent')
  })
})
