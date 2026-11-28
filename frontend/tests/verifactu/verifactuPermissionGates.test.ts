import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import RejectedGlobalBanner from '../../../backend/app/modules/verifactu/frontend/components/verifactu/RejectedGlobalBanner.vue'
import InvoiceVerifactuSlot from '../../../backend/app/modules/verifactu/frontend/components/verifactu/InvoiceVerifactuSlot.vue'

// The banner polls GET /verifactu/health (needs verifactu.settings.read)
// and the invoice slot fetches GET /verifactu/records (needs
// verifactu.records.read). Calling either without the permission makes
// useApi toast "Access denied" (#1269).

const { get, granted } = vi.hoisted(() => ({
  get: vi.fn(async (_url: string) => ({ data: [] as unknown })),
  granted: { value: [] as string[] }
}))

mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))
mockNuxtImport('useApi', () => () => ({ get, post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() }))
mockNuxtImport('usePermissions', () => () => ({
  can: (p: string) => granted.value.includes(p)
}))

beforeEach(() => {
  // Layer composables are not auto-imports in CI (no module layers);
  // with layers linked the real ones run against the mocked useApi.
  vi.stubGlobal('useVerifactu', () => ({
    health: async () => (await get('/api/v1/verifactu/health') as { data: unknown }).data,
    getLatestRecordForInvoice: async (id: string) => {
      const r = await get(`/api/v1/verifactu/records?invoice_id=${id}&page_size=1`) as { data: unknown[] }
      return r.data?.[0] ?? null
    },
    retryRecord: vi.fn(),
    checkNif: async (value: string) =>
      (await get(`/api/v1/verifactu/nif-check?value=${encodeURIComponent(value)}`) as { data: unknown }).data
  }))
  vi.stubGlobal('useInvoices', () => ({ updateBillingParty: vi.fn(), fetchInvoice: vi.fn() }))
  get.mockReset()
  get.mockImplementation(async () => ({ data: [] }))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

const calledHealth = () => get.mock.calls.some(([url]) => String(url).includes('/verifactu/health'))
const calledNifCheck = () => get.mock.calls.some(([url]) => String(url).includes('/verifactu/nif-check'))
const calledRecords = () => get.mock.calls.some(([url]) => String(url).includes('/verifactu/records'))

describe('RejectedGlobalBanner permission gate (#1269)', () => {
  it('does not poll /health with only records.read (dentist, receptionist)', async () => {
    granted.value = ['verifactu.records.read']
    const w = await mountSuspended(RejectedGlobalBanner)
    await flushPromises()
    expect(calledHealth()).toBe(false)
    w.unmount()
  })

  it('does not poll /health with only queue.manage', async () => {
    granted.value = ['verifactu.queue.manage']
    const w = await mountSuspended(RejectedGlobalBanner)
    await flushPromises()
    expect(calledHealth()).toBe(false)
    w.unmount()
  })

  it('polls /health with settings.read', async () => {
    granted.value = ['verifactu.settings.read']
    get.mockResolvedValueOnce({ data: { rejected_count: 0 } })
    const w = await mountSuspended(RejectedGlobalBanner)
    await flushPromises()
    expect(calledHealth()).toBe(true)
    w.unmount()
  })
})

describe('InvoiceVerifactuSlot permission gate (#1269)', () => {
  const ctx = { invoice: { id: 'inv-1', compliance_data: { ES: { state: 'accepted' } } }, clinic: { country: 'ES' } }

  it('skips the live-record fetch without records.read (hygienist, assistant)', async () => {
    granted.value = ['billing.read']
    await mountSuspended(InvoiceVerifactuSlot, { props: { ctx } })
    await flushPromises()
    expect(calledRecords()).toBe(false)
  })

  it('fetches the live record with records.read', async () => {
    granted.value = ['billing.read', 'verifactu.records.read']
    await mountSuspended(InvoiceVerifactuSlot, { props: { ctx } })
    await flushPromises()
    expect(calledRecords()).toBe(true)
  })
})

describe('InvoiceVerifactuSlot rejected-alert actions (#1269)', () => {
  const ctx = {
    invoice: { id: 'inv-1', billing_tax_id: 'B12345678', compliance_data: { ES: { state: 'rejected' } } },
    clinic: { country: 'ES' }
  }
  const stubs = { UModal: { template: '<div><slot name="body" /><slot name="footer" /></div>' } }

  async function mountRejected() {
    const w = await mountSuspended(InvoiceVerifactuSlot, { props: { ctx }, global: { stubs } })
    await flushPromises()
    return w
  }
  const hasRegenerate = (w: Awaited<ReturnType<typeof mountRejected>>) =>
    w.findAll('button').some(b => b.text().includes('verifactu.queue.regenerateAndRetry'))

  async function blurTaxId(w: Awaited<ReturnType<typeof mountRejected>>) {
    await w.findAll('button').find(b => b.text().includes('verifactu.queue.ctas.edit_billing_party'))!.trigger('click')
    await flushPromises()
    const inputs = w.findAll('input')
    await inputs[inputs.length - 1]!.trigger('blur')
    await flushPromises()
  }

  it('hides Regenerate without queue.manage (dentist, receptionist)', async () => {
    granted.value = ['billing.read', 'billing.write', 'verifactu.records.read']
    const w = await mountRejected()
    expect(hasRegenerate(w)).toBe(false)
  })

  it('shows Regenerate with queue.manage', async () => {
    granted.value = ['billing.read', 'billing.write', 'verifactu.records.read', 'verifactu.queue.manage']
    const w = await mountRejected()
    expect(hasRegenerate(w)).toBe(true)
  })

  it('skips the NIF check without settings.read', async () => {
    granted.value = ['billing.read', 'billing.write', 'verifactu.records.read']
    const w = await mountRejected()
    await blurTaxId(w)
    expect(calledNifCheck()).toBe(false)
  })

  it('runs the NIF check with settings.read', async () => {
    granted.value = ['billing.read', 'billing.write', 'verifactu.records.read', 'verifactu.settings.read']
    get.mockImplementation(async (url: string) =>
      ({ data: String(url).includes('nif-check') ? { warning: null } : [] }))
    const w = await mountRejected()
    await blurTaxId(w)
    expect(calledNifCheck()).toBe(true)
  })
})
