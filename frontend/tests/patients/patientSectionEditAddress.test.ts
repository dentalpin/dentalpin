import { mount } from '@vue/test-utils'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import PatientSectionEditModal from '../../module_layers/patients/frontend/components/patient/PatientSectionEditModal.vue'

/**
 * #1092: the edit modal dropped any address without a street. The
 * demographics form shows no address fields at all, so a patient
 * imported with only a postal code lost it on an unrelated save; the
 * billing form nulled a city + postal code entered with a blank street.
 */
const put = vi.fn(async () => ({}))
mockNuxtImport('useApi', () => () => ({ put, del: vi.fn() }))
mockNuxtImport('useToast', () => () => ({ add: vi.fn() }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string, fallback?: string) => fallback ?? key }))

const stubs = {
  UModal: { template: '<div><slot name="content" /></div>' },
  UCard: { template: '<div><slot name="header" /><slot /><slot name="footer" /></div>' },
  UButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  UFormField: { props: ['label'], template: '<label :data-label="label"><slot /></label>' },
  UInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)">'
  },
  UTextarea: true,
  USelect: true,
  USwitch: true,
  EmergencyContactForm: true,
  LegalGuardianForm: true,
  MedicalHistoryForm: true
}

function patient(overrides: Record<string, unknown> = {}) {
  return {
    id: 'p1',
    first_name: 'Ana',
    last_name: 'García',
    phone: '600000000',
    preferred_language: 'es',
    address: null,
    billing_address: null,
    ...overrides
  }
}

function mountModal(section: string, p: Record<string, unknown>) {
  return mount(PatientSectionEditModal, {
    props: { open: true, section, patient: p } as never,
    global: { stubs }
  })
}

async function save(wrapper: ReturnType<typeof mountModal>) {
  const button = wrapper.findAll('button').find(b => b.text() === 'common.save')!
  await button.trigger('click')
  await nextTick()
  return put.mock.calls.at(-1) as unknown as [string, Record<string, unknown>]
}

function input(wrapper: ReturnType<typeof mountModal>, label: string) {
  return wrapper.find(`label[data-label="${label}"] input`)
}

describe('PatientSectionEditModal addresses (#1092)', () => {
  beforeEach(() => put.mockClear())

  it('keeps a postal-code-only address when saving demographics', async () => {
    const p = patient({ address: { street: null, city: null, postal_code: '28013', province: null, country: 'ES' } })
    const wrapper = mountModal('demographics', p)
    await input(wrapper, 'patients.phone').setValue('611111111')

    const [url, body] = await save(wrapper)
    expect(url).toBe('/api/v1/patients/p1/extended')
    expect(body.phone).toBe('611111111')
    expect(body.address).toMatchObject({ postal_code: '28013', country: 'ES' })
  })

  it('sends a billing address entered without a street', async () => {
    const wrapper = mountModal('billing', patient())
    await input(wrapper, 'invoice.city').setValue('Madrid')
    await input(wrapper, 'invoice.postalCode').setValue('28013')

    const [, body] = await save(wrapper)
    expect(body.billing_address).toMatchObject({ city: 'Madrid', postal_code: '28013', country: 'ES' })
  })

  it('sends null when every billing address field is blank', async () => {
    const wrapper = mountModal('billing', patient({
      billing_address: { street: 'Calle Mayor 1', city: 'Madrid', postal_code: '', province: '', country: 'ES' }
    }))
    await input(wrapper, 'invoice.street').setValue('  ')
    await input(wrapper, 'invoice.city').setValue('')

    const [, body] = await save(wrapper)
    expect(body.billing_address).toBeNull()
  })

  it('edits a copy, so Cancel leaves the shown patient untouched', async () => {
    const p = patient({ billing_address: { street: 'Calle Mayor 1', city: 'Madrid', postal_code: '28013', province: '', country: 'ES' } })
    const wrapper = mountModal('billing', p)
    await input(wrapper, 'invoice.city').setValue('Toledo')

    expect((p.billing_address as Record<string, string>).city).toBe('Madrid')
  })
})
