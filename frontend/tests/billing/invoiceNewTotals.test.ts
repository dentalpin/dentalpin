import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import NewInvoicePage from '#module-layers/billing/frontend/pages/invoices/new.vue'
import { lineAmounts, sumLineAmounts } from '../../../backend/app/modules/billing/frontend/utils/lineAmounts'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
mockNuxtImport('useApi', () => () => ({ get, post: vi.fn() }))
mockNuxtImport('useClinic', () => () => ({
  currentClinic: ref({ id: 'clinic-1' }),
  fetchClinic: vi.fn(),
  defaultPaymentTermDays: ref(30)
}))
mockNuxtImport('useInvoices', () => () => ({ createInvoice: vi.fn() }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: ref('en') }))
mockNuxtImport('useCurrency', () => () => ({ format: (n: number) => `€${Number(n).toFixed(2)}` }))

describe('lineAmounts (#1032)', () => {
  it('takes a percentage discount off before VAT', () => {
    expect(lineAmounts({ unit_price: 100, quantity: 1, discount_type: 'percentage', discount_value: 50 }, 21))
      .toEqual({ subtotal: 100, discount: 50, tax: 10.5, total: 60.5 })
  })

  it('takes an absolute discount off before VAT, capped at the line', () => {
    expect(lineAmounts({ unit_price: 40, quantity: 2, discount_type: 'absolute', discount_value: 30 }, 10))
      .toEqual({ subtotal: 80, discount: 30, tax: 5, total: 55 })
    expect(lineAmounts({ unit_price: 20, quantity: 1, discount_type: 'absolute', discount_value: 50 }, 21).total)
      .toBe(0)
  })

  it('rounds each line amount to cents half up and sums the rounded lines, like the backend', () => {
    // Backend stores 0.03 per line (0.025 rounded) and an invoice total of 0.09, not 0.08.
    const line = lineAmounts({ unit_price: 0.05, discount_type: 'percentage', discount_value: 50 }, 0)
    expect(line).toEqual({ subtotal: 0.05, discount: 0.03, tax: 0, total: 0.03 })
    expect(sumLineAmounts([line, line, line])).toEqual({ subtotal: 0.15, discount: 0.09, tax: 0, total: 0.09 })
  })
})

describe('New invoice page totals (#1032)', () => {
  let wrapper: VueWrapper | undefined
  afterEach(() => wrapper?.unmount())

  it('applies percentage and absolute line discounts to row totals and summary', async () => {
    get.mockResolvedValue({ data: [{ id: 'vat-21', rate: 21, is_default: false }, { id: 'vat-10', rate: 10, is_default: false }] })
    wrapper = await mountSuspended(NewInvoicePage)
    await vi.waitFor(() => expect(get).toHaveBeenCalled())
    await flushPromises()
    const vm = wrapper.vm as unknown as { items: unknown[] }
    vm.items.push(
      { description: 'Filling', unit_price: 100, quantity: 1, vat_type_id: 'vat-21', discount_type: 'percentage', discount_value: 50, display_order: 0 },
      { description: 'Cleaning', unit_price: 40, quantity: 2, vat_type_id: 'vat-10', discount_type: 'absolute', discount_value: 30, display_order: 1 }
    )
    await nextTick()
    const text = wrapper.text()
    // Rows: 100 @21% -50% = 60.50; 2 x 40 @10% -30 = 55.00
    expect(text).toContain('€60.50')
    expect(text).toContain('€55.00')
    expect(text).not.toContain('€121.00')
    // Summary: subtotal 180, discount 80, tax 15.50, total 115.50
    expect(text).toContain('€180.00')
    expect(text).toContain('-€80.00')
    expect(text).toContain('€15.50')
    expect(text).toContain('€115.50')
  })
})
