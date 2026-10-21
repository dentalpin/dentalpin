import { describe, expect, it } from 'vitest'
import type { ModuleSettings } from '~/utils/settingsForm'
import { initialFormValues, writableValues } from '~/utils/settingsForm'

const data: ModuleSettings = {
  module: 'billing',
  settings: [
    {
      key: 'default_payment_term_days',
      type: 'integer',
      default: 30,
      writable: true,
      label_key: 'billingSettings.fields.defaultPaymentTermDays.label',
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
      writable: true,
      label_key: 'billingSettings.fields.bankAccountInfo.label',
      choices: [],
      min_value: null,
      max_value: null,
      max_length: null,
      multiline: true,
      nullable: true
    }
  ],
  values: {
    default_payment_term_days: 45,
    invoice_footer_text: 'Gracias',
    bank_account_info: 'ES00'
  }
}

describe('settingsForm helpers', () => {
  it('initialises from stored values and falls back to defaults', () => {
    const values = initialFormValues({
      ...data,
      values: { default_payment_term_days: 45 }
    })

    expect(values.default_payment_term_days).toBe(45)
    expect(values.invoice_footer_text).toBeNull()
    expect(values.bank_account_info).toBeNull()
  })

  it('sends nothing when no writable value changed', () => {
    const payload = writableValues(data, initialFormValues(data))

    expect(payload).toEqual({})
  })

  it('sends only changed writable settings', () => {
    const form = initialFormValues(data)
    form.default_payment_term_days = 60

    const payload = writableValues(data, form)

    expect(payload).toEqual({ default_payment_term_days: 60 })
  })

  it('ignores changes to read-only settings', () => {
    const readOnly = {
      ...data,
      settings: data.settings.map(setting =>
        setting.key === 'bank_account_info' ? { ...setting, writable: false } : setting
      )
    }
    const form = initialFormValues(readOnly)
    form.bank_account_info = 'ES11'

    const payload = writableValues(readOnly, form)

    expect(payload).toEqual({})
  })

  it('keeps an unchanged fallback value out of the payload', () => {
    const fallback = { ...data, values: { ...data.values, invoice_footer_text: null } }
    const payload = writableValues(fallback, initialFormValues(fallback))

    expect(payload).toEqual({})
  })

  it('omits an emptied non-nullable integer', () => {
    const form = initialFormValues(data)
    form.default_payment_term_days = ''

    const payload = writableValues(data, form)

    expect(payload).toEqual({})
  })

  it('clears a nullable string when the field is emptied', () => {
    const form = initialFormValues(data)
    form.invoice_footer_text = ''

    const payload = writableValues(data, form)

    expect(payload.invoice_footer_text).toBeNull()
  })
})
