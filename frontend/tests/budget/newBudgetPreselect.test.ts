import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import NewBudgetPage from '#module-layers/budget/frontend/pages/budgets/new.vue'

const { get, toastAdd, query } = vi.hoisted(() => ({
  get: vi.fn(),
  toastAdd: vi.fn(),
  query: { value: {} as Record<string, string> }
}))
mockNuxtImport('useApi', () => () => ({ get, post: vi.fn() }))
mockNuxtImport('useToast', () => () => ({ add: toastAdd }))
mockNuxtImport('useRoute', () => () => ({ query: query.value, fullPath: '/budgets/new' }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: ref('en') }))
mockNuxtImport('usePermissions', () => () => ({ can: () => true }))
// useBudgets lives in the budget layer (not auto-imported when CI runs without layers).
vi.stubGlobal('useBudgets', () => ({ createBudget: vi.fn() }))

// Minimal selector: shows the selected patient and lets a test pick another.
const PatientVisualSelector = defineComponent({
  props: { modelValue: { type: Object, default: null } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('div', [
      h('span', { 'data-test': 'selected' }, (props.modelValue as { first_name?: string } | null)?.first_name ?? ''),
      h('button', {
        'type': 'button',
        'data-test': 'pick',
        'onClick': () => emit('update:modelValue', { id: 'p-2', first_name: 'Bea' })
      })
    ])
  }
})

const mountPage = () => mountSuspended(NewBudgetPage, {
  global: { stubs: { PatientVisualSelector, ModuleSlot: true } }
})

describe('New budget page patient preselection (#1221)', () => {
  let wrapper: VueWrapper | undefined
  beforeEach(() => {
    get.mockReset()
    toastAdd.mockReset()
    query.value = {}
  })
  afterEach(() => wrapper?.unmount())

  it('preselects the patient from ?patient_id', async () => {
    query.value = { patient_id: 'p-1', from: 'patient' }
    get.mockResolvedValue({ data: { id: 'p-1', first_name: 'Ana' } })
    wrapper = await mountPage()
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/api/v1/patients/p-1')
    expect(wrapper.get('[data-test="selected"]').text()).toBe('Ana')
  })

  it('does not fetch anything without ?patient_id', async () => {
    wrapper = await mountPage()
    await flushPromises()
    expect(get).not.toHaveBeenCalled()
    expect(wrapper.get('[data-test="selected"]').text()).toBe('')
  })

  it('stays empty without an error toast when the patient cannot be loaded', async () => {
    query.value = { patient_id: 'p-1' }
    get.mockRejectedValue(new Error('404'))
    wrapper = await mountPage()
    await flushPromises()
    expect(wrapper.get('[data-test="selected"]').text()).toBe('')
    expect(toastAdd).not.toHaveBeenCalled()
  })

  it('does not overwrite a patient picked before the fetch resolves', async () => {
    query.value = { patient_id: 'p-1' }
    let resolve!: (v: unknown) => void
    get.mockReturnValue(new Promise((r) => {
      resolve = r
    }))
    wrapper = await mountPage()
    await wrapper.get('[data-test="pick"]').trigger('click')
    resolve({ data: { id: 'p-1', first_name: 'Ana' } })
    await flushPromises()
    expect(wrapper.get('[data-test="selected"]').text()).toBe('Bea')
  })
})
