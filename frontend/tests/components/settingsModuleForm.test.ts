import { flushPromises } from '@vue/test-utils'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsModuleForm from '~/components/settings/SettingsModuleForm.vue'
import BillingSettingsPage from '../../module_layers/billing/frontend/components/BillingSettingsPage.vue'

const api = vi.hoisted(() => ({
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  raw: vi.fn()
}))

mockNuxtImport('useApi', () => () => api)
mockNuxtImport('useToast', () => () => ({ add: vi.fn() }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))

const payload = {
  module: 'billing',
  settings: [
    {
      key: 'default_payment_term_days',
      type: 'integer',
      default: 30,
      writable: true,
      label_key: 'billingSettings.fields.defaultPaymentTermDays.label',
      description_key: null,
      choices: [],
      min_value: 0,
      max_value: 365,
      max_length: null,
      multiline: false,
      nullable: false
    },
    {
      key: 'invoice_footer_text',
      type: 'string',
      default: null,
      writable: true,
      label_key: 'billingSettings.fields.invoiceFooterText.label',
      description_key: null,
      choices: [],
      min_value: null,
      max_value: null,
      max_length: null,
      multiline: true,
      nullable: true
    },
    {
      key: 'bank_account_info',
      type: 'string',
      default: null,
      writable: false,
      label_key: 'billingSettings.fields.bankAccountInfo.label',
      description_key: null,
      choices: [],
      min_value: null,
      max_value: null,
      max_length: null,
      multiline: true,
      nullable: true
    },
    {
      key: 'reminders_enabled',
      type: 'boolean',
      default: true,
      writable: true,
      label_key: 'settings.demo.remindersEnabled.label',
      description_key: null,
      choices: [],
      min_value: null,
      max_value: null,
      max_length: null,
      multiline: false,
      nullable: false
    }
  ],
  values: {
    default_payment_term_days: 45,
    invoice_footer_text: 'Gracias',
    bank_account_info: 'ES00',
    reminders_enabled: true
  }
}

describe('SettingsModuleForm', () => {
  beforeEach(() => {
    api.get.mockReset()
    api.patch.mockReset()
    api.get.mockResolvedValue({ data: payload })
    api.patch.mockResolvedValue({ data: payload })
  })

  it('renders declared settings and disables read-only fields', async () => {
    const wrapper = await mountSuspended(SettingsModuleForm, {
      props: { module: 'billing' }
    })
    await flushPromises()

    const number = wrapper.find('input[type="number"]')
    expect((number.element as HTMLInputElement).value).toBe('45')

    const textareas = wrapper.findAll('textarea')
    expect((textareas[0].element as HTMLTextAreaElement).disabled).toBe(false)
    expect((textareas[1].element as HTMLTextAreaElement).disabled).toBe(true)
    expect(api.get).toHaveBeenCalledWith('/api/v1/settings/billing', { errorToast: false })
  })

  it('does not send a request when nothing changed', async () => {
    const wrapper = await mountSuspended(SettingsModuleForm, {
      props: { module: 'billing' }
    })
    await flushPromises()

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.patch).not.toHaveBeenCalled()
  })

  it('submits a toggled boolean', async () => {
    const wrapper = await mountSuspended(SettingsModuleForm, {
      props: { module: 'billing' }
    })
    await flushPromises()

    await wrapper.find('[role="switch"]').trigger('click')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.patch).toHaveBeenCalledWith('/api/v1/settings/billing', {
      values: { reminders_enabled: false }
    }, { errorToast: false })
  })

  it('saves only the fields the user changed', async () => {
    const wrapper = await mountSuspended(SettingsModuleForm, {
      props: { module: 'billing' }
    })
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue('60')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.patch).toHaveBeenCalledWith('/api/v1/settings/billing', {
      values: { default_payment_term_days: 60 }
    }, { errorToast: false })
  })

  it('blocks save and reports a required integer left empty', async () => {
    const wrapper = await mountSuspended(SettingsModuleForm, {
      props: { module: 'billing' }
    })
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue('')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.patch).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('settings.moduleSettings.invalidInteger')
  })

  it('resolves the generic form inside the billing settings page', async () => {
    const wrapper = await mountSuspended(BillingSettingsPage)
    await flushPromises()

    expect(wrapper.text()).toContain('billingSettings.fields.defaultPaymentTermDays.label')
  })
})
