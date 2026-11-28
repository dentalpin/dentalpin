import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NotificationTemplatesPage from '#module-layers/notifications/frontend/components/settings/NotificationTemplatesPage.vue'

const { api, access } = vi.hoisted(() => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn() },
  access: { write: true }
}))

mockNuxtImport('useApi', () => () => api)
mockNuxtImport('usePermissions', () => () => ({
  can: (permission: string) => permission === 'notifications.templates.write' ? access.write : true,
  canAny: () => true,
  canAll: () => true,
  isAdmin: ref(true)
}))

const stubs = {
  UCard: { template: '<section><slot name="header" /><slot /></section>' },
  UFormField: { props: ['label', 'error'], template: '<label>{{ label }}<slot /><span v-if="error">{{ error }}</span></label>' },
  UButton: { props: ['label', 'disabled'], template: '<button :disabled="disabled"><slot />{{ label }}</button>' },
  UTextarea: {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template: '<textarea :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  UInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  USelect: {
    props: ['modelValue', 'items', 'disabled'],
    emits: ['update:modelValue'],
    template: '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="item in items" :key="item.value" :value="item.value">{{ item.label }}</option></select>'
  },
  UBadge: { template: '<span><slot /></span>' },
  UAlert: { props: ['title'], template: '<p>{{ title }}</p>' },
  UCheckbox: true,
  USkeleton: true
}

const selection = {
  editable: true,
  current: null,
  has_override: false,
  default_locale: 'es',
  variables: [{ key: 'patient_name', example: 'Alex Example', optional: false }]
}

const mountEditor = () => mountSuspended(NotificationTemplatesPage, { global: { stubs } })
const templatePath = '/api/v1/notifications/templates/editor/appointment_confirmation'
type EditorWrapper = Awaited<ReturnType<typeof mountEditor>>

function button(wrapper: EditorWrapper, pattern: RegExp) {
  const match = wrapper.findAll('button').find(element => pattern.test(element.text()))
  if (!match) throw new Error(`No button matched ${pattern}`)
  return match
}

describe('notification template editor', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    access.write = true
    api.get.mockResolvedValue({ data: selection })
    api.post.mockResolvedValue({ data: { subject: null, body_html: null, body_text: null } })
    api.put.mockResolvedValue(undefined)
    api.del.mockResolvedValue(undefined)
  })

  it('inserts a variable, previews unsaved text, and persists the selected variant', async () => {
    const wrapper = await mountEditor()
    await flushPromises()
    await wrapper.findAll('select')[1]!.setValue('whatsapp')
    await flushPromises()
    expect(api.get).toHaveBeenLastCalledWith(templatePath, { query: { channel: 'whatsapp', locale: expect.any(String) } })
    await wrapper.get('textarea').setValue('Hola ')
    await button(wrapper, /patient_name/).trigger('click')
    expect(wrapper.get('textarea').element.value).toBe('Hola {{ patient_name }}')
    api.post.mockResolvedValueOnce({ data: { body_text: 'Hola Alex Example' } })
    await button(wrapper, /refreshPreview|Refresh preview|Actualizar vista previa/i).trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenLastCalledWith(
      `${templatePath}/preview`,
      expect.objectContaining({ content: expect.objectContaining({ body_text: 'Hola {{ patient_name }}' }) }),
      expect.objectContaining({ query: expect.objectContaining({ channel: 'whatsapp' }) })
    )
    expect(wrapper.text()).toContain('Hola Alex Example')

    await button(wrapper, /^(Save|Guardar|common.save)$/i).trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith(
      templatePath,
      expect.objectContaining({ body_text: 'Hola {{ patient_name }}' }),
      expect.objectContaining({ query: expect.objectContaining({ channel: 'whatsapp' }) })
    )
    wrapper.unmount()
  })

  it('preserves the draft and displays field validation returned by the server', async () => {
    const wrapper = await mountEditor()
    await flushPromises()
    api.put.mockRejectedValueOnce({
      data: { detail: { field: 'body_html', code: 'unknown_variable', line: 1, variable: 'misspelt' } }
    })
    await wrapper.findAll('textarea')[0]!.setValue('<p>{{ misspelt }}</p>')
    await button(wrapper, /^(Save|Guardar|common.save)$/i).trigger('click')
    await flushPromises()
    expect(wrapper.text()).toMatch(/unknown_variable|unknown variable|variable desconocida/i)
    expect(wrapper.findAll('textarea')[0]!.element.value).toBe('<p>{{ misspelt }}</p>')
    wrapper.unmount()
  })

  it('allows preview with read-only permission and hides mutation controls', async () => {
    access.write = false
    api.get.mockResolvedValueOnce({ data: { ...selection, has_override: true } })
    const wrapper = await mountEditor()
    await flushPromises()
    expect(wrapper.findAll('textarea')).toHaveLength(0)
    expect(wrapper.text()).not.toMatch(/restore default|volver al texto por defecto|templateEditor.restore/)
    expect(api.post).toHaveBeenCalled()
    await wrapper.findAll('select')[1]!.setValue('push')
    await flushPromises()
    expect(api.get).toHaveBeenLastCalledWith(templatePath, { query: { channel: 'push', locale: expect.any(String) } })
    expect(api.put).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('requires confirmation to remove an override and reloads the missing-system state', async () => {
    api.get
      .mockResolvedValueOnce({ data: { ...selection, has_override: true, current: { body_html: '<p>Hi</p>' } } })
      .mockResolvedValueOnce({ data: { ...selection, default_locale: null } })
    const wrapper = await mountEditor()
    await flushPromises()
    const restore = /^(Restore default|Volver al texto por defecto|notifications.templateEditor.restore)$/i
    await button(wrapper, restore).trigger('click')
    expect(api.del).not.toHaveBeenCalled()
    await button(wrapper, restore).trigger('click')
    await flushPromises()
    expect(api.del).toHaveBeenCalledWith(templatePath, expect.objectContaining({ query: expect.objectContaining({ channel: 'email' }) }))
    expect(wrapper.text()).toMatch(/no system text|sin texto de sistema|templateEditor.noSystem/i)
    wrapper.unmount()
  })
})
