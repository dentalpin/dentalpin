import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ConversationThread from '#module-layers/notifications/frontend/components/ConversationThread.vue'

/**
 * #1231: the reply box sends on Enter, and only the send button was
 * disabled while the POST was in flight. A second Enter posted the same
 * WhatsApp message again.
 */
const { get, post, pending } = vi.hoisted(() => {
  const pending: Array<() => void> = []
  return {
    pending,
    get: vi.fn(async (path: string) => {
      if (path.endsWith('/notifications/channels')) {
        return { data: { available: ['whatsapp'], whatsapp_session_available: true } }
      }
      return { data: [] }
    }),
    post: vi.fn((_path: string, body: { body: string }) => new Promise((resolve) => {
      pending.push(() => resolve({
        data: {
          id: `m${pending.length}`,
          channel: 'whatsapp',
          direction: 'outbound',
          message_kind: 'free',
          status: 'sent',
          sent_manually: false,
          subject: null,
          body_text: body.body,
          template_key: '',
          error_message: null,
          created_at: new Date().toISOString(),
          sent_at: null,
          delivered_at: null,
          read_at: null
        }
      }))
    }))
  }
})

mockNuxtImport('useApi', () => () => ({ get, post, patch: vi.fn(), del: vi.fn(), raw: vi.fn() }))

describe('ConversationThread reply (#1231)', () => {
  it('ignores a second Enter while the first reply is in flight', async () => {
    const wrapper = await mountSuspended(ConversationThread, { props: { ctx: { patient: { id: 'p1' } } } })
    await vi.waitFor(() => expect(wrapper.find('input').exists()).toBe(true))
    const input = wrapper.find('input')
    await input.setValue('Su cita es mañana a las 10')

    await input.trigger('keydown', { key: 'Enter' })
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(post).toHaveBeenCalledTimes(1)

    pending.forEach(release => release())
    await flushPromises()
    expect(post).toHaveBeenCalledTimes(1)
    expect((input.element as HTMLInputElement).value).toBe('')

    // Once the first send settles, the next message goes through.
    await input.setValue('Gracias')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(post).toHaveBeenCalledTimes(2)
    expect(post.mock.calls[1]![1]).toEqual({ channel: 'whatsapp', body: 'Gracias' })
  })
})
