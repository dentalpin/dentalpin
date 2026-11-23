import { describe, expect, it } from 'vitest'
import { defineComponent, h, onMounted } from 'vue'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import PatientSectionEditModal from '../../../backend/app/modules/patients/frontend/components/patient/PatientSectionEditModal.vue'

mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))

// Stands in for the form, which edits the object it is given in place.
const RemovingForm = defineComponent({
  props: { modelValue: { type: Object, required: true } },
  setup(props) {
    onMounted(() => (props.modelValue as { allergies: unknown[] }).allergies.splice(0, 1))
    return () => h('div', { 'data-testid': 'history-form' })
  }
})

function mountModal(medicalHistory?: unknown) {
  return mountSuspended(PatientSectionEditModal, {
    props: { open: true, section: 'medical', patient: { id: 'patient-a' }, medicalHistory } as never,
    global: {
      stubs: {
        UModal: { template: '<div><slot name="content" /></div>' },
        MedicalHistoryForm: RemovingForm,
        PatientMedicalHistoryForm: RemovingForm
      }
    }
  })
}

describe('medical history edit modal (#1045)', () => {
  it('edits a copy, so Cancel discards', async () => {
    const stored = { allergies: [{ name: 'Penicillin', severity: 'high' }], medications: [], systemic_diseases: [], surgical_history: [] }
    const modal = await mountModal(stored)

    expect(modal.find('[data-testid="history-form"]').exists()).toBe(true)
    expect(stored.allergies).toHaveLength(1)
  })

  it('hands the edited copy over on Save', async () => {
    const stored = { allergies: [{ name: 'Penicillin', severity: 'high' }], medications: [], systemic_diseases: [], surgical_history: [] }
    const modal = await mountModal(stored)

    await modal.findAll('button').find(b => b.text().includes('common.save'))!.trigger('click')
    const [sent] = modal.emitted('saveMedical')![0] as [{ allergies: unknown[] }]
    expect(sent.allergies).toHaveLength(0)
  })

  it('cannot be saved before the history loaded', async () => {
    const modal = await mountModal(undefined)
    const save = modal.findAll('button').find(b => b.text().includes('common.save'))!

    expect(save.attributes('disabled')).toBeDefined()
  })
})
