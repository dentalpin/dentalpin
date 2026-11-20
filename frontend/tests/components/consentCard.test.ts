import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ConsentCard from '../../module_layers/documents/frontend/components/consent/ConsentCard.vue'

const qr = vi.hoisted(() => vi.fn(async () => 'data:image/png;base64,c3ludGhldGlj'))
vi.mock('qrcode', () => ({ default: { toDataURL: qr } }))

const get = vi.fn(async (path: string) => {
  if (path.endsWith('/consent-templates')) return { data: [] }
  if (path.endsWith('/signature-status')) {
    return { data: [
      { id: 'unsigned', signed: false },
      { id: 'signed', signed: true },
      { id: 'signed-draft', signed: true },
      { id: 'revoked', signed: true, revoked: true }
    ] }
  }
  return { data: [
    { id: 'unsigned', title: 'Unsigned preview', status: 'generated', content: { text: 'Original' } },
    { id: 'signed', title: 'Signed consent', status: 'generated', content: { text: 'Signed text' } },
    { id: 'signed-draft', title: 'Signed with draft status', status: 'draft', content: { text: 'Signed text' } },
    { id: 'revoked', title: 'Prior consent', status: 'generated', content: { text: 'Signed text' } }
  ] }
})
const patch = vi.fn(async () => ({}))
const del = vi.fn(async () => ({}))
const post = vi.fn(async () => ({ data: { token: 'synthetic-token' } }))
mockNuxtImport('useApi', () => () => ({ get, patch, del, post, raw: vi.fn() }))
mockNuxtImport('usePermissions', () => () => ({ can: () => true }))

afterEach(() => {
  get.mockClear()
  patch.mockClear()
  del.mockClear()
  post.mockClear()
  qr.mockClear()
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
      const revoked = rows.find(row => row.text().includes('Prior consent'))!
      expect(revoked.text()).toMatch(/Revoked|documents\.consent\.revoked/)
      expect(revoked.findAll('button').some(button => /^(Create revocation link|documents\.consent\.revoke)$/.test(button.text()))).toBe(false)
      expect(revoked.text()).toMatch(/Download revocation|documents\.consent\.downloadRevocation/)
      expect(signed.text()).not.toMatch(/Download revocation|documents\.consent\.downloadRevocation/)
      await unsigned.findAll('button').find(button => /New signing link|documents\.consent\.signLink/.test(button.text()))!.trigger('click')
      await flushPromises()
      expect(qr).toHaveBeenCalledWith(`${window.location.origin}/p/consent#synthetic-token`, expect.any(Object))
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
