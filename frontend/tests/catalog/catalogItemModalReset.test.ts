import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { computed } from 'vue'
import { afterAll, describe, expect, it, vi } from 'vitest'
import CatalogItemModal from '../../module_layers/catalog/frontend/components/catalog/CatalogItemModal.vue'

// #1233: the form was only (re)populated when the `item` prop changed. The
// settings page passes `item: null` for every "New treatment" and the same
// object for Edit on the same row after Cancel, so the next opening showed
// the item just created, or the discarded edit.

const { get } = vi.hoisted(() => ({ get: vi.fn(async () => ({ data: [] })) }))
mockNuxtImport('useApi', () => () => ({ get, post: vi.fn(), patch: vi.fn(), put: vi.fn(), del: vi.fn(), raw: vi.fn() }))
// CI's frontend-test registers no module layers, so the layer composables
// are not auto-imported there: provide them as globals. With layers
// registered the real ones run against the mocked useApi above.
vi.stubGlobal('useCatalog', () => ({ formatPrice: (p: number) => String(p) }))
vi.stubGlobal('useVatTypes', () => ({
  vatTypeOptions: computed(() => []),
  defaultVatType: computed(() => undefined),
  fetchVatTypes: async () => {}
}))
afterAll(() => vi.unstubAllGlobals())

interface ModalVm {
  formData: { internal_code?: string, default_price?: number, names?: Record<string, string> }
  itemName: string
  sessionsEnabled: boolean
  handleSubmit: () => void
}

const categories = [{ id: 'cat1', key: 'conservative', names: { es: 'Conservadora', en: 'Conservative' } }]
const item = {
  id: 'x',
  internal_code: 'OBT-01',
  category_id: 'cat1',
  names: { es: 'Obturación', en: 'Filling' },
  default_price: 60,
  cost_price: 10,
  pricing_strategy: 'flat',
  default_duration_minutes: 30,
  requires_appointment: true,
  vat_type_id: null,
  treatment_scope: 'tooth',
  is_diagnostic: false,
  requires_surfaces: false,
  is_active: true,
  sessions: []
}

// Only `open` toggles: the page keeps passing the same `item` value.
async function reopen(wrapper: Awaited<ReturnType<typeof mountSuspended>>) {
  await wrapper.setProps({ open: false })
  await flushPromises()
  await wrapper.setProps({ open: true })
  await flushPromises()
}

describe('CatalogItemModal (#1233)', () => {
  it('opens "New treatment" empty after one was created', async () => {
    const wrapper = await mountSuspended(CatalogItemModal, { props: { open: true, item: null, categories, loading: false } })
    await flushPromises()
    const vm = wrapper.vm as unknown as ModalVm
    vm.formData.internal_code = 'IMP-01'
    vm.itemName = 'Implante'
    vm.formData.default_price = 1200
    vm.handleSubmit()
    expect((wrapper.emitted('create') as unknown[][])[0]![0]).toMatchObject({ internal_code: 'IMP-01', default_price: 1200 })

    // The page closes the modal on success and reopens it with item=null.
    await reopen(wrapper)
    expect(vm.formData.internal_code).toBe('')
    expect(vm.itemName).toBe('')
    expect(vm.formData.default_price).toBe(0)
  })

  it('reopening the same item after Cancel drops the discarded edit', async () => {
    const wrapper = await mountSuspended(CatalogItemModal, { props: { open: true, item, categories, loading: false } })
    await flushPromises()
    const vm = wrapper.vm as unknown as ModalVm
    expect(vm.formData.default_price).toBe(60)
    vm.formData.default_price = 999
    vm.formData.internal_code = 'CHANGED'

    await reopen(wrapper)
    expect(vm.formData.default_price).toBe(60)
    expect(vm.formData.internal_code).toBe('OBT-01')
  })
})
