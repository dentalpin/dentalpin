import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import EmergencyContactForm from '../../../backend/app/modules/patients_clinical/frontend/components/patient/EmergencyContactForm.vue'
import LegalGuardianForm from '../../../backend/app/modules/patients_clinical/frontend/components/patient/LegalGuardianForm.vue'
import PatientSectionEditModal from '../../../backend/app/modules/patients/frontend/components/patient/PatientSectionEditModal.vue'

const del = vi.fn()
const put = vi.fn()
mockNuxtImport('useApi', () => () => ({ del, put }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))

afterEach(() => vi.clearAllMocks())

describe.each([
  ['emergency contact', EmergencyContactForm],
  ['legal guardian', LegalGuardianForm]
])('%s form (#1064)', (_name, Form) => {
  it('hands over an incomplete edit, for the API to refuse', async () => {
    const stored = { name: 'María', phone: '600000000', relationship: 'parent' }
    const form = await mountSuspended(Form, { props: { modelValue: stored } as never })
    await flushPromises()

    const phone = form.findAll('input').find(input => (input.element as HTMLInputElement).value === '600000000')!
    await phone.setValue('')
    await flushPromises()

    const sent = form.emitted('update:modelValue')!.at(-1)![0] as { phone: string }
    expect(sent.phone).toBe('')
  })
})

describe('contact sections of the edit modal (#1064)', () => {
  async function save(section: string, patient: object) {
    const modal = await mountSuspended(PatientSectionEditModal, {
      props: { open: true, section, patient: { id: 'patient-a', ...patient } } as never,
      global: { stubs: { UModal: { template: '<div><slot name="content" /></div>' } } }
    })
    await modal.findAll('button').find(b => b.text().includes('common.save'))!.trigger('click')
    await flushPromises()
  }

  it.each(['emergency', 'guardian'])('never deletes a %s it did not load', async (section) => {
    await save(section, {})
    expect(del).not.toHaveBeenCalled()
  })
})
