import { expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import type { InvoiceListItem } from '~/types'

mockNuxtImport('useApi', () => () => ({
  get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn()
}))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: { value: 'en' } }))

const invoice: InvoiceListItem = {
  id: 'invoice-test',
  invoice_number: 'SYN-01',
  is_historical: true,
  status: 'issued',
  total: 100,
  total_paid: 0,
  balance_due: 0,
  created_at: '2026-11-18T00:00:00Z'
}

it.each(['draft', 'issued', 'partial', 'paid'] as const)(
  'keeps a historical %s invoice read-only',
  async (status) => {
    const { useInvoices } = await import('#module-layers/billing/frontend/composables/useInvoices')
    const actions = useInvoices()
    const historical = { ...invoice, status }

    expect(actions.canSend(historical)).toBe(false)
    expect(actions.canRecordPayment(historical)).toBe(false)
    expect(actions.canCreateCreditNote(historical)).toBe(false)
    expect(actions.canEdit(historical)).toBe(false)
    expect(actions.canIssue(historical)).toBe(false)
    expect(actions.canVoid(historical)).toBe(false)
  }
)

it('keeps collection, sending and credit notes available for operational issued invoices', async () => {
  const { useInvoices } = await import('#module-layers/billing/frontend/composables/useInvoices')
  const actions = useInvoices()
  const current = { ...invoice, is_historical: false, balance_due: 100 }

  expect(actions.canSend(current)).toBe(true)
  expect(actions.canRecordPayment(current)).toBe(true)
  expect(actions.canCreateCreditNote(current)).toBe(true)
})
