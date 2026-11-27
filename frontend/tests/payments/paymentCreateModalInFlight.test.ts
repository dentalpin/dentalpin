import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PaymentCreateModal from '../../module_layers/payments/frontend/components/PaymentCreateModal.vue'

// A second Enter while the first POST /api/v1/payments is still pending
// must not record the payment twice (#1230).

const { post, pending } = vi.hoisted(() => {
  const pending: Array<(v: unknown) => void> = []
  const post = vi.fn((_url: string, _body: unknown, _opts?: unknown) =>
    new Promise((resolve) => { pending.push(resolve) }))
  return { post, pending }
})

mockNuxtImport('useApi', () => () => ({
  get: vi.fn(async () => ({ data: [], total: 0 })),
  post,
  put: vi.fn(),
  patch: vi.fn(),
  del: vi.fn()
}))

beforeEach(() => {
  // Layer composables are not Nuxt auto-imports in CI (no module layers),
  // so stub usePayments as a global; with layers linked the real one runs
  // against the mocked useApi above.
  vi.stubGlobal('usePayments', () => ({
    create: async (payload: unknown) => {
      const resp = await post('/api/v1/payments', payload, { errorToast: false }) as { data: unknown }
      return resp.data
    }
  }))
  post.mockClear()
  pending.length = 0
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

function pressEnter(el: Element) {
  el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
}

describe('PaymentCreateModal in-flight guard (#1230)', () => {
  it('ignores a second Enter while the first submit is pending', async () => {
    const wrapper = await mountSuspended(PaymentCreateModal, {
      props: { open: true, defaultPatientId: 'p1', defaultPatientName: 'Ana Test', defaultAmount: 50 },
      attachTo: document.body
    })
    await flushPromises()

    const amount = document.body.querySelector('input[type="number"]')
    expect(amount).not.toBeNull()

    pressEnter(amount!)
    await flushPromises()
    pressEnter(amount!)
    await flushPromises()

    expect(post).toHaveBeenCalledTimes(1)
    expect(post.mock.calls[0]![0]).toBe('/api/v1/payments')

    pending.forEach(resolve => resolve({ data: { id: 'pay-1' } }))
    await flushPromises()
    expect(post).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('created')).toHaveLength(1)
  })
})
