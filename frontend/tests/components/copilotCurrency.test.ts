import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import CopilotPending from '../../module_layers/copilot/frontend/components/CopilotPending.vue'
import CopilotResultCard from '../../module_layers/copilot/frontend/components/CopilotResultCard.vue'
import { useCopilotFormat } from '../../module_layers/copilot/frontend/composables/useCopilotFormat'

// Copilot amounts use the clinic currency, never a hardcoded euro, and
// counts whose key looks like money render as plain numbers (#1177).

const { get } = vi.hoisted(() => ({ get: vi.fn() }))

mockNuxtImport('useApi', () => () => ({ get, post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() }))
mockNuxtImport('useClinic', () => () => ({ currentClinic: ref({ id: 'clinic-1', currency: 'HUF' }) }))
mockNuxtImport('useI18n', () => () => ({
  t: (key: string) => key,
  locale: ref('en'),
  locales: ref([]),
  setLocale: vi.fn()
}))

beforeEach(() => {
  // Layer composables are not Nuxt auto-imports in CI (no module layers):
  // expose the real formatter as a global so the clinic currency path runs.
  vi.stubGlobal('useCopilot', () => ({ open: ref(true) }))
  vi.stubGlobal('useCopilotFormat', useCopilotFormat)
  get.mockReset()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

async function rows(name: string, result: unknown): Promise<Record<string, string>> {
  const wrapper = await mountSuspended(CopilotResultCard, { props: { name, result } })
  try {
    const labels = wrapper.findAll('dt').map(d => d.text())
    const values = wrapper.findAll('dd').map(d => d.text())
    return Object.fromEntries(labels.map((l, i) => [l, values[i]!]))
  } finally { wrapper.unmount() }
}

describe('copilot money formatting', () => {
  it('formats amounts without a currency in the clinic currency', async () => {
    const r = await rows('reports.billing_report', {
      date_from: '2026-01-01', date_to: '2026-01-31', total_invoiced: 150000, invoice_count: 12
    })
    expect(r['total invoiced']).toContain('HUF')
    expect(r['total invoiced']).not.toContain('€')
    expect(r['invoice count']).toBe('12')
  })

  it('renders counts as numbers, not money', async () => {
    const stats = await rows('reports.patient_stats_report', { total_patients: 150, age_bands: [] })
    expect(stats['total patients']).toBe('150')

    const ops = await rows('reports.operational_report', { completed_total: 40, by_professional: [] })
    expect(ops['completed total']).toBe('40')

    const sched = await rows('reports.scheduling_report', { total_appointments: 61, completion_rate: 80.5 })
    expect(sched['total appointments']).toBe('61')

    // A list envelope's `total` is its row count…
    const list = await rows('billing.list_invoices', {
      total: 150, invoices: [{ id: 'i1', number: 'F-1', total: 99.5 }]
    })
    expect(list.total).toBe('150')

    // …while a single record's `total` stays money.
    const invoice = await rows('billing.get_invoice', {
      id: 'i1', number: 'F-1', status: 'issued', total: 150, items: [{ description: 'x', quantity: 1, total: 150 }]
    })
    expect(invoice.total).toContain('HUF')
  })

  it('shows pending budget amounts in the clinic currency', async () => {
    get.mockResolvedValue({
      data: {
        items: [{
          kind: 'budget', id: 'b1', patient_id: null, title: 'Patient', link: '/budgets/b1',
          reason: null, priority: null, number: 'P-1', amount: 25000
        }],
        sections: [{ kind: 'budget', total: 1, link: '/budgets?status=sent' }]
      }
    })
    const wrapper = await mountSuspended(CopilotPending)
    await flushPromises()
    try {
      expect(wrapper.text()).toContain('HUF')
      expect(wrapper.text()).not.toContain('€')
    } finally { wrapper.unmount() }
  })
})
