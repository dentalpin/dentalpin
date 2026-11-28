import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import ConsentPage from '../../module_layers/documents/frontend/pages/p/consent/index.vue'
import SignatureCanvas from '../../app/components/shared/SignatureCanvas.vue'

mockNuxtImport('useRuntimeConfig', () => () => ({ public: { apiBaseUrl: '' } }))

afterEach(() => {
  window.history.replaceState(null, '', '/')
  vi.unstubAllGlobals()
})

describe('public consent signing', () => {
  it.each([
    [undefined, true],
    [500, true],
    [429, true],
    [422, true],
    [404, false],
    [409, false]
  ])('after a failed submit (%s) keeps the form: %s (#1042)', async (statusCode, keeps) => {
    vi.stubGlobal('$fetch', vi.fn(async (_url: string, options: { method?: string }) => {
      if (options?.method === 'POST') throw Object.assign(new Error('failed'), { statusCode })
      return { data: { title: 'Synthetic consent', text: 'Synthetic text', patient: 'Patient Example', clinic: 'Example clinic', purpose: 'sign' } }
    }))
    window.history.replaceState(null, '', '/#synthetic-token')
    const wrapper = await mountSuspended(ConsentPage)
    await new Promise(resolve => setTimeout(resolve, 0))
    await flushPromises()
    try {
      wrapper.getComponent(SignatureCanvas).vm.$emit('update:modelValue', 'data:image/png;base64,synthetic')
      await flushPromises()
      await wrapper.findAll('button').at(-1)!.trigger('click')
      await flushPromises()
      expect(wrapper.find('canvas').exists()).toBe(keeps)
      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    } finally { wrapper.unmount() }
  })

  it('renders the server-sanitised body_html and never the raw text (#1171)', async () => {
    vi.stubGlobal('$fetch', vi.fn(async () => ({
      data: {
        title: 'Synthetic consent',
        text: '# Raw heading <b>RAW-SOURCE-MARKER</b>',
        body_html: '<h2>Rendered heading</h2><p>Some <strong>bold</strong> text<br>next line</p><ul><li>one</li></ul>',
        patient: 'Patient Example',
        clinic: 'Example clinic',
        purpose: 'sign'
      }
    })))
    window.history.replaceState(null, '', '/#synthetic-token')
    const wrapper = await mountSuspended(ConsentPage)
    await new Promise(resolve => setTimeout(resolve, 0))
    await flushPromises()
    try {
      const body = wrapper.get('[data-testid="consent-body"]')
      expect(body.find('h2').text()).toBe('Rendered heading')
      expect(body.find('strong').text()).toBe('bold')
      expect(body.find('br').exists()).toBe(true)
      expect(body.find('li').text()).toBe('one')
      expect(wrapper.html()).not.toContain('RAW-SOURCE-MARKER')
    } finally { wrapper.unmount() }
  })

  it('requires a drawn signature and a representative name', async () => {
    const fetch = vi.fn(async (_url: string, options: { method?: string }) => {
      if (options?.method === 'POST') return { data: { signed: true } }
      return { data: { title: 'Synthetic consent', text: 'Synthetic text', patient: 'Patient Example', clinic: 'Example clinic', purpose: 'sign' } }
    })
    vi.stubGlobal('$fetch', fetch)
    window.history.replaceState(null, '', '/#synthetic-token')
    const SelectStub = defineComponent({
      props: ['modelValue', 'items'],
      emits: ['update:modelValue'],
      template: `<select :value="modelValue" @change="$emit('update:modelValue', $event.target.value)"><option v-for="item in items" :key="item.value" :value="item.value">{{ item.label }}</option></select>`
    })
    const wrapper = await mountSuspended(ConsentPage, { global: { stubs: { USelect: SelectStub } } })
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
      // A guardian must give an ID document (#1171): confirm stays disabled without one.
      wrapper.getComponent(SignatureCanvas).vm.$emit('update:modelValue', 'data:image/png;base64,synthetic')
      await flushPromises()
      expect(wrapper.findAll('button').at(-1)!.attributes('disabled')).toBeDefined()
      // Raw input may carry spaces that the server strips: the cap matches the API schema (64).
      expect(wrapper.findAll('input')[1]!.attributes('maxlength')).toBe('64')
      await wrapper.findAll('input')[1]!.setValue('  12345678z ')
      wrapper.getComponent(SignatureCanvas).vm.$emit('update:modelValue', 'data:image/png;base64,synthetic')
      await flushPromises()
      const confirm = wrapper.findAll('button').at(-1)!
      expect(confirm.attributes('disabled')).toBeUndefined()
      await confirm.trigger('click')
      await flushPromises()
      expect(fetch).toHaveBeenLastCalledWith('/api/v1/documents/public/consents/current/sign', expect.objectContaining({
        method: 'POST', credentials: 'omit', headers: { Authorization: 'Bearer synthetic-token' }, body: expect.objectContaining({ signer_name: 'Guardian Example', relationship_to_patient: 'guardian', signer_id_document: '12345678z' })
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

  it('keeps the ID document optional for the patient and sends null when blank (#1171)', async () => {
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
      const idInput = wrapper.findAll('input')[1]!
      expect(idInput.attributes('required')).toBeUndefined()
      expect(idInput.attributes('autocomplete')).toBe('off')
      wrapper.getComponent(SignatureCanvas).vm.$emit('update:modelValue', 'data:image/png;base64,synthetic')
      await flushPromises()
      const confirm = wrapper.findAll('button').at(-1)!
      expect(confirm.attributes('disabled')).toBeUndefined()
      await confirm.trigger('click')
      await flushPromises()
      expect(fetch).toHaveBeenLastCalledWith('/api/v1/documents/public/consents/current/sign', expect.objectContaining({
        body: expect.objectContaining({ relationship_to_patient: 'patient', signer_id_document: null })
      }))
    } finally { wrapper.unmount() }
  })
})
