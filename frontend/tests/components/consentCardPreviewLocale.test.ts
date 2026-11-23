import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ConsentCard from '../../module_layers/documents/frontend/components/consent/ConsentCard.vue'

// #1041: the preview posted /documents/generate without a locale, so the
// route's `es` default gave every clinic Spanish captions and watermark.

const get = vi.fn(async (path: string) => {
  if (path.endsWith('/consent-templates')) return { data: [] }
  if (path.endsWith('/signature-status')) return { data: [{ id: 'unsigned', signed: false }] }
  return { data: [{ id: 'unsigned', title: 'Unsigned preview', status: 'draft', content: { text: 'Text' } }] }
})
const post = vi.fn(async () => ({}))
mockNuxtImport('useApi', () => () => ({ get, post, patch: vi.fn(), del: vi.fn(), raw: vi.fn() }))
mockNuxtImport('usePermissions', () => () => ({ can: () => true }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: ref('hu') }))

describe('consent card preview', () => {
  it('renders the preview in the UI language', async () => {
    const wrapper = await mountSuspended(ConsentCard, { props: { ctx: { patient: { id: 'patient' } } } })
    await flushPromises()
    try {
      const row = wrapper.findAll('li').find(item => item.text().includes('Unsigned preview'))!
      await row.findAll('button').find(button => button.text() === 'documents.consent.generatePreview')!.trigger('click')
      await flushPromises()
      expect(post).toHaveBeenCalledWith('/api/v1/documents/generate?locale=hu', { document_id: 'unsigned' })
    } finally { wrapper.unmount() }
  })
})
