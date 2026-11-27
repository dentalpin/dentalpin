import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import PatientTimeline from '../../module_layers/patient_timeline/frontend/components/patient/PatientTimeline.vue'

// The timeline heading must be shown in the UI language, not the Spanish
// title the backend stores on every row (#1174).

// Value of EventType.APPOINTMENT_SCHEDULED in backend/app/core/events/types.py
// (the frontend has no event-type constants).
const APPOINTMENT_SCHEDULED = 'appointment.scheduled'

const en = vi.hoisted(() => ({ messages: {} as Record<string, unknown> }))
en.messages = JSON.parse(
  readFileSync(resolve(__dirname, '../../i18n/locales/en.json'), 'utf-8')
) as Record<string, unknown>

function lookup(key: string): string | undefined {
  let node: unknown = en.messages
  for (const part of key.split('.')) {
    if (node === null || typeof node !== 'object') return undefined
    node = (node as Record<string, unknown>)[part]
  }
  return typeof node === 'string' ? node : undefined
}

mockNuxtImport('useI18n', () => () => ({
  t: (key: string, params: Record<string, unknown> = {}) =>
    (lookup(key) ?? key).replace(/\{(\w+)\}/g, (_, name: string) => String(params[name])),
  te: (key: string) => lookup(key) !== undefined,
  locale: ref('en')
}))
mockNuxtImport('usePermissions', () => () => ({ can: () => true }))
mockNuxtImport('useProfessionals', () => () => ({
  professionals: ref([{ id: 'p1' }]),
  fetchProfessionals: vi.fn(),
  getProfessionalById: () => null,
  getProfessionalFullName: () => ''
}))
// With module layers linked (local dev) the real usePatientTimeline runs and
// reads through useApi; in CI (no layers) the vi.stubGlobal stand-in runs.
const apiGet = vi.hoisted(() => vi.fn())
mockNuxtImport('useApi', () => () => ({ get: apiGet, post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() }))
mockNuxtImport('useCurrency', () => () => ({ format: (n: number) => String(n) }))

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PatientTimeline entry heading (#1174)', () => {
  it('shows an appointment heading in English, not the stored Spanish title', async () => {
    const entry = {
      id: 'e1',
      event_type: APPOINTMENT_SCHEDULED,
      event_category: 'visit',
      source_table: 'appointments',
      source_id: 'a1',
      title: 'Cita programada: Limpieza',
      description: null,
      occurred_at: new Date().toISOString(),
      created_by: null,
      event_data: { treatment_type: 'Limpieza', cabinet: 'G1', professional_id: null }
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
    const text = wrapper.text()
    expect(text).toContain('Appointment scheduled: Limpieza')
    expect(text).not.toContain('Cita programada')
  })
})
