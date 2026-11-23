import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DocumentsConsentTemplatesPage from '../../module_layers/documents/frontend/components/settings/DocumentsConsentTemplatesPage.vue'

const registered = vi.hoisted(() => [] as Array<Record<string, unknown>>)
vi.mock('~~/app/composables/useSettingsRegistry', () => ({
  registerSettingsPage: (entry: Record<string, unknown>) => { registered.push(entry) }
}))

let templates: Array<{ id: string, title: string, body: string, is_active?: boolean }> = []
const get = vi.fn(async () => ({ data: templates }))
const post = vi.fn(async () => ({ data: {} }))
const put = vi.fn(async () => ({ data: {} }))
mockNuxtImport('useApi', () => () => ({ get, post, put }))

beforeEach(() => {
  templates = [
    { id: 'tpl-1', title: 'Extraction', body: 'Synthetic extraction text' },
    { id: 'tpl-2', title: 'Whitening', body: 'Synthetic whitening text' },
    { id: 'tpl-3', title: 'Old implant text', body: 'Synthetic archived text', is_active: false }
  ]
})
afterEach(() => {
  get.mockClear()
  post.mockClear()
  put.mockClear()
})

const button = (wrapper: Awaited<ReturnType<typeof mountSuspended>>, pattern: RegExp) =>
  wrapper.findAll('button').find(b => pattern.test(b.text()))!

describe('consent templates settings page', () => {
  it('lists templates from the existing endpoint', async () => {
    const wrapper = await mountSuspended(DocumentsConsentTemplatesPage)
    await flushPromises()
    try {
      expect(get).toHaveBeenCalledWith('/api/v1/documents/consent-templates?include_archived=true')
      expect(wrapper.text()).toContain('Extraction')
      expect(wrapper.text()).toContain('Whitening')
    } finally { wrapper.unmount() }
  })

  it('creates a template with POST and trims the values', async () => {
    const wrapper = await mountSuspended(DocumentsConsentTemplatesPage)
    await flushPromises()
    try {
      const save = button(wrapper, /Save template|documents\.consent\.saveTemplate/)
      expect(save.attributes('disabled')).toBeDefined()
      await wrapper.get('input').setValue('  New template  ')
      await wrapper.get('textarea').setValue('  New text  ')
      await button(wrapper, /Save template|documents\.consent\.saveTemplate/).trigger('click')
      await flushPromises()
      expect(post).toHaveBeenCalledWith('/api/v1/documents/consent-templates', { title: 'New template', body: 'New text' })
      expect(put).not.toHaveBeenCalled()
      expect(get).toHaveBeenCalledTimes(2)
    } finally { wrapper.unmount() }
  })

  it('edits an existing template with PUT', async () => {
    const wrapper = await mountSuspended(DocumentsConsentTemplatesPage)
    await flushPromises()
    try {
      const row = wrapper.findAll('li').find(li => li.text().includes('Whitening'))!
      await row.get('button').trigger('click')
      expect((wrapper.get('input').element as HTMLInputElement).value).toBe('Whitening')
      expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('Synthetic whitening text')
      await wrapper.get('textarea').setValue('Updated whitening text')
      await button(wrapper, /Save template|documents\.consent\.saveTemplate/).trigger('click')
      await flushPromises()
      expect(put).toHaveBeenCalledWith('/api/v1/documents/consent-templates/tpl-2', {
        title: 'Whitening', body: 'Updated whitening text'
      })
      expect(post).not.toHaveBeenCalled()
    } finally { wrapper.unmount() }
  })
})

describe('consent template archive actions', () => {
  it('shows archived templates muted with a badge and a restore action', async () => {
    const wrapper = await mountSuspended(DocumentsConsentTemplatesPage)
    await flushPromises()
    try {
      const archived = wrapper.findAll('li').find(li => li.text().includes('Old implant text'))!
      expect(archived.text()).toMatch(/Archived|documents\.settings\.consentTemplateArchive\.archived/)
      expect(archived.html()).toContain('opacity-60')
      expect(archived.text()).toMatch(/Restore|documents\.settings\.consentTemplateArchive\.restore/)
      const active = wrapper.findAll('li').find(li => li.text().includes('Extraction'))!
      expect(active.text()).not.toMatch(/Archived\b/)
      expect(active.html()).not.toContain('opacity-60')
    } finally { wrapper.unmount() }
  })

  it('archives an active template with POST and reloads the list', async () => {
    const wrapper = await mountSuspended(DocumentsConsentTemplatesPage)
    await flushPromises()
    try {
      const row = wrapper.findAll('li').find(li => li.text().includes('Extraction'))!
      await row.findAll('button').find(b => /^(Archive|documents\.settings\.consentTemplateArchive\.archive)$/.test(b.text()))!.trigger('click')
      await flushPromises()
      expect(post).toHaveBeenCalledWith('/api/v1/documents/consent-templates/tpl-1/archive', {})
      expect(get).toHaveBeenCalledTimes(2)
    } finally { wrapper.unmount() }
  })

  it('restores an archived template with POST', async () => {
    const wrapper = await mountSuspended(DocumentsConsentTemplatesPage)
    await flushPromises()
    try {
      const row = wrapper.findAll('li').find(li => li.text().includes('Old implant text'))!
      await row.findAll('button').find(b => /Restore|documents\.settings\.consentTemplateArchive\.restore/.test(b.text()))!.trigger('click')
      await flushPromises()
      expect(post).toHaveBeenCalledWith('/api/v1/documents/consent-templates/tpl-3/unarchive', {})
    } finally { wrapper.unmount() }
  })
})

describe('documents settings plugin', () => {
  it('registers the page under Settings → Clinical, gated on documents.write', async () => {
    registered.length = 0
    const plugin = (await import('../../module_layers/documents/frontend/plugins/settings.client')).default as unknown as (app: unknown) => void
    plugin(useNuxtApp())
    const entry = registered.find(e => e.path === 'consent-templates')
    expect(entry).toBeDefined()
    expect(entry).toMatchObject({ category: 'clinical', permission: 'documents.write' })
    // The letterhead page stays registered.
    expect(registered.some(e => e.path === 'documents-letterhead')).toBe(true)
  })
})
