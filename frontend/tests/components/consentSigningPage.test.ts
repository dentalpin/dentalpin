import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ConsentPage from '../../module_layers/documents/frontend/pages/p/consent/index.vue'
import SignatureCanvas from '../../app/components/shared/SignatureCanvas.vue'

mockNuxtImport('useRuntimeConfig', () => () => ({ public: { apiBaseUrl: '' } }))

afterEach(() => {
  window.history.replaceState(null, '', '/')
  vi.unstubAllGlobals()
})

describe('public consent signing', () => {
  it('requires a drawn signature and a representative name', async () => {
    const fetch = vi.fn(async (_url: string, options: { method?: string }) => {
      if (options?.method === 'POST') return { data: { signed: true } }
      return { data: { title: 'Synthetic consent', text: 'Synthetic text', patient: 'Patient Example', clinic: 'Example clinic', purpose: 'sign' } }
    })
    vi.stubGlobal('$fetch', fetch)
    window.history.replaceState(null, '', '/#synthetic-token')
    const wrapper = await mountSuspended(ConsentPage)
    await new Promise(resolve => setTimeout(resolve, 0))
    await flushPromises()
    try {
      expect(fetch).toHaveBeenCalledWith('/api/v1/documents/public/consents/current', expect.objectContaining({
        credentials: 'omit', headers: { Authorization: 'Bearer synthetic-token' }
      }))
      expect(wrapper.text()).toContain('Synthetic consent')
      expect((wrapper.get('input').element as HTMLInputElement).value).toBe('Patient Example')
      await wrapper.get('select').setValue('guardian')
      expect((wrapper.get('input').element as HTMLInputElement).value).toBe('')
      await wrapper.get('input').setValue('Guardian Example')
      wrapper.getComponent(SignatureCanvas).vm.$emit('update:modelValue', 'data:image/png;base64,synthetic')
      await flushPromises()
      const confirm = wrapper.findAll('button').at(-1)!
      expect(confirm.attributes('disabled')).toBeUndefined()
      await confirm.trigger('click')
      await flushPromises()
      expect(fetch).toHaveBeenLastCalledWith('/api/v1/documents/public/consents/current/sign', expect.objectContaining({
        method: 'POST', credentials: 'omit', headers: { Authorization: 'Bearer synthetic-token' }, body: expect.objectContaining({ signer_name: 'Guardian Example', relationship_to_patient: 'guardian' })
      }))
      expect(wrapper.find('canvas').exists()).toBe(false)
      window.history.replaceState(null, '', '/#second-token')
      window.dispatchEvent(new Event('hashchange'))
      await flushPromises()
      expect(fetch).toHaveBeenLastCalledWith('/api/v1/documents/public/consents/current', expect.objectContaining({
        credentials: 'omit', headers: { Authorization: 'Bearer second-token' }
      }))
      expect(wrapper.find('canvas').exists()).toBe(true)
    } finally { wrapper.unmount() }
  })
})
