import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ConsentCard from '../../module_layers/documents/frontend/components/consent/ConsentCard.vue'

const get = vi.fn(async (path: string) => {
  if (path.endsWith('/consent-templates')) return { data: [] }
  if (path.endsWith('/signature-status')) {
    return { data: [
      { id: 'unsigned', signed: false },
      { id: 'signed', signed: true },
      { id: 'signed-draft', signed: true }
    ] }
  }
  return { data: [
    { id: 'unsigned', title: 'Unsigned preview', status: 'generated', content: { text: 'Original' } },
    { id: 'signed', title: 'Signed consent', status: 'generated', content: { text: 'Signed text' } },
    { id: 'signed-draft', title: 'Signed with draft status', status: 'draft', content: { text: 'Signed text' } }
  ] }
})
const patch = vi.fn(async () => ({}))
const del = vi.fn(async () => ({}))
mockNuxtImport('useApi', () => () => ({ get, patch, del, post: vi.fn(), raw: vi.fn() }))
mockNuxtImport('usePermissions', () => () => ({ can: () => true }))

afterEach(() => {
  get.mockClear()
  patch.mockClear()
  del.mockClear()
})

describe('consent patient card', () => {
  it('allows editing or archiving an unsigned preview but protects a signed consent', async () => {
    const wrapper = await mountSuspended(ConsentCard, { props: { ctx: { patient: { id: 'patient' } } } })
    await flushPromises()
    try {
      const rows = wrapper.findAll('li')
      const unsigned = rows.find(row => row.text().includes('Unsigned preview'))!
      const signed = rows.find(row => row.text().includes('Signed consent'))!
      expect(unsigned.text()).toMatch(/Edit consent|documents\.consent\.editConsent/)
      expect(unsigned.text()).toMatch(/Archive|documents\.consent\.archiveConsent/)
      expect(unsigned.text()).toMatch(/Generate preview|documents\.consent\.generatePreview/)
      expect(signed.text()).not.toMatch(/Edit consent|documents\.consent\.editConsent/)
      expect(signed.text()).not.toMatch(/Archive|documents\.consent\.archiveConsent/)
      expect(signed.text()).toMatch(/Download signed PDF|documents\.consent\.download/)
      const signedDraft = rows.find(row => row.text().includes('Signed with draft status'))!
      expect(signedDraft.text()).not.toMatch(/Edit consent|documents\.consent\.editConsent/)
      expect(signedDraft.text()).not.toMatch(/Archive|documents\.consent\.archiveConsent/)
      await unsigned.findAll('button').find(button => /Edit consent|documents\.consent\.editConsent/.test(button.text()))!.trigger('click')
      await unsigned.get('input').setValue('Updated title')
      await unsigned.get('textarea').setValue('Updated text')
      await unsigned.findAll('button').find(button => /^(Save|common\.save)$/.test(button.text()))!.trigger('click')
      await flushPromises()
      expect(patch).toHaveBeenCalledWith('/api/v1/documents/unsigned', {
        title: 'Updated title', content: { text: 'Updated text' }
      })
      const refreshed = wrapper.findAll('li').find(row => row.text().includes('Unsigned preview'))!
      await refreshed.findAll('button').find(button => /Archive|documents\.consent\.archiveConsent/.test(button.text()))!.trigger('click')
      await flushPromises()
      expect(del).toHaveBeenCalledWith('/api/v1/documents/unsigned')
    } finally { wrapper.unmount() }
  })
})
