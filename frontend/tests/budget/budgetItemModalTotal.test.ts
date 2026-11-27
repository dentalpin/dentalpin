import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import BudgetItemModal from '#module-layers/budget/frontend/components/budget/BudgetItemModal.vue'
import { budgetLineAmounts } from '../../../backend/app/modules/budget/frontend/utils/budgetLineAmounts'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
mockNuxtImport('useApi', () => () => ({ get, post: vi.fn() }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: ref('en') }))
mockNuxtImport('useCurrency', () => () => ({ format: (n: number) => `€${Number(n).toFixed(2)}` }))
// useCatalog / useBudgets live in module layers, which CI's frontend-test does
// not register, so they are global stubs rather than mockNuxtImport targets.
vi.stubGlobal('useCatalog', () => ({ formatPrice: (n: number) => `€${Number(n).toFixed(2)}` }))
vi.stubGlobal('useBudgets', () => ({ addItem: vi.fn() }))

// The catalog search endpoints return CatalogItemBrief: vat_type_id only, no
// rate, and default_price as a JSON decimal string.
const whitening = { id: 'c1', internal_code: 'BLA-01', names: { en: 'Whitening' }, default_price: '100.00', vat_type_id: 'vat-21' }

const TreatmentVisualSelector = defineComponent({
  emits: ['update:modelValue'],
  setup(_, { emit }) {
    return () => h('button', { 'type': 'button', 'data-test': 'pick', 'onClick': () => emit('update:modelValue', whitening) })
  }
})

describe('budgetLineAmounts (#1235)', () => {
  it('matches BudgetItemService._calculate_line_totals', () => {
    expect(budgetLineAmounts({ unit_price: 100, quantity: 1 }, 21))
      .toEqual({ subtotal: 100, discount: 0, tax: 21, total: 121 })
    expect(budgetLineAmounts({ unit_price: 100, quantity: 1, discount_type: 'absolute', discount_value: 150 }, 21))
      .toEqual({ subtotal: 100, discount: 100, tax: 0, total: 0 })
    expect(budgetLineAmounts({ unit_price: 40, quantity: 2, discount_type: 'percentage', discount_value: 25 }, 10))
      .toEqual({ subtotal: 80, discount: 20, tax: 6, total: 66 })
    // Total rounds from the unrounded taxable + tax, half away from zero:
    // 10.05 at 10 % = 11.055 -> 11.06 (stored by Numeric(10, 2)).
    expect(budgetLineAmounts({ unit_price: 10.05, quantity: 1 }, 10).total).toBe(11.06)
  })
})

describe('BudgetItemModal line total (#1235)', () => {
  let wrapper: VueWrapper | undefined
  beforeEach(() => {
    get.mockReset()
    get.mockImplementation(async (url: string) => url.startsWith('/api/v1/catalog/vat-types')
      // An inactive VAT type still applies: the backend reads the item's type by id.
      ? { data: [{ id: 'vat-10', rate: 10, is_default: true, is_active: true }, { id: 'vat-21', rate: 21, is_default: false, is_active: false }] }
      : { data: [] })
  })
  afterEach(() => wrapper?.unmount())

  it('adds the catalog item\'s VAT and caps an absolute discount at the line', async () => {
    wrapper = await mountSuspended(BudgetItemModal, {
      props: { open: true, budgetId: 'b1' },
      global: { stubs: { TreatmentVisualSelector, UModal: { template: '<div><slot name="content" /></div>' } } }
    })
    await flushPromises()
    await wrapper.find('[data-test="pick"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('€121.00')

    const vm = wrapper.vm as unknown as { form: { discount_type?: string, discount_value?: number } }
    vm.form.discount_type = 'absolute'
    vm.form.discount_value = 150
    await flushPromises()
    expect(wrapper.text()).toContain('€0.00')
    expect(wrapper.text()).not.toContain('-€')
    expect(get).toHaveBeenCalledWith('/api/v1/catalog/vat-types', expect.objectContaining({ query: { include_inactive: true } }))
  })
})
