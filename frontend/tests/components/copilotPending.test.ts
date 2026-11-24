import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import CopilotPending from '../../module_layers/copilot/frontend/components/CopilotPending.vue'

// "Pendientes" shows a bounded slice per kind; the section total must be
// visible when it is larger, with a link to the full list (#1137).

const { get, navigate } = vi.hoisted(() => ({ get: vi.fn(), navigate: vi.fn() }))

mockNuxtImport('useApi', () => () => ({ get, post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() }))
mockNuxtImport('navigateTo', () => navigate)
// Layer locales are not loaded in the test app: echo the key + params.
mockNuxtImport('useI18n', () => () => ({
  t: (key: string, params?: Record<string, unknown>) => (params ? `${key} ${JSON.stringify(params)}` : key),
  locale: ref('en')
}))

function item(kind: 'recall' | 'budget', i: number) {
  return {
    kind,
    id: `${kind}-${i}`,
    patient_id: null,
    title: `Patient ${i}`,
    link: kind === 'recall' ? '/recalls' : `/budgets/${kind}-${i}`,
    reason: null,
    priority: null,
    number: null,
    amount: null
  }
}

beforeEach(() => {
  // Layer composables are not Nuxt auto-imports in CI (no module layers),
  // so stub them as globals; with layers linked the real ones run.
  vi.stubGlobal('useCopilot', () => ({ open: ref(true) }))
  vi.stubGlobal('useCopilotFormat', () => ({ money: (v: number) => String(v) }))
  get.mockReset()
  navigate.mockReset()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CopilotPending', () => {
  it('says how many are hidden and links to the full list', async () => {
    get.mockResolvedValue({
      data: {
        items: [
          ...Array.from({ length: 20 }, (_, i) => item('recall', i)),
          ...Array.from({ length: 3 }, (_, i) => item('budget', i))
        ],
        sections: [
          { kind: 'recall', total: 35, link: '/recalls?overdue=true&month=&status=__any__' },
          { kind: 'budget', total: 3, link: '/budgets?status=sent' }
        ]
      }
    })
    const wrapper = await mountSuspended(CopilotPending)
    await flushPromises()
    try {
      const more = wrapper.find('[data-testid="pending-more-recall"]')
      expect(more.exists()).toBe(true)
      expect(more.text()).toBe('copilot.pending.more {"shown":20,"total":35}')
      // Every budget is already shown: no "more" line.
      expect(wrapper.find('[data-testid="pending-more-budget"]').exists()).toBe(false)

      await more.trigger('click')
      await flushPromises()
      expect(navigate).toHaveBeenCalledWith('/recalls?overdue=true&month=&status=__any__')
    } finally { wrapper.unmount() }
  })
})
