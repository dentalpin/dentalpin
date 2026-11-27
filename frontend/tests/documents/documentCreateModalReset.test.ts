import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterAll, describe, expect, it, vi } from 'vitest'
import DocumentCreateModal from '../../module_layers/documents/frontend/components/DocumentCreateModal.vue'

// #1232: the form was only (re)initialised when the `document` prop changed.
// "New document" passes `document: null` every time, so after a create (or a
// cancel) the next opening showed the previous patient's draft.

const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(async () => ({ data: { id: 'patient-A', first_name: 'Ana', last_name: 'Alpha' } })),
  post: vi.fn(async () => ({ data: { id: 'doc-1' } })),
  patch: vi.fn(async () => ({ data: { id: 'doc-1' } }))
}))

mockNuxtImport('useApi', () => () => ({ get, post, patch, put: vi.fn(), del: vi.fn(), raw: vi.fn() }))
// CI's frontend-test registers no module layers, so the layer composable is
// not auto-imported there: provide it as a global. With layers registered it
// is auto-imported and goes through the mocked useApi above.
vi.stubGlobal('useManagedDocuments', () => ({
  createDocument: (data: unknown) => post('/api/v1/documents', data),
  updateDocument: (id: string, data: unknown) => patch(`/api/v1/documents/${id}`, data)
}))
afterAll(() => vi.unstubAllGlobals())

interface ModalVm {
  form: { patient_id: string, document_type: string, title: string, content: { diagnosis: string, medications: unknown[] } }
  selectedPatient: { id: string, label: string } | undefined
  submit: () => Promise<void>
}

async function fillForPatientA(vm: ModalVm) {
  vm.selectedPatient = { id: 'patient-A', label: 'Alpha, Ana' }
  await flushPromises()
  vm.form.title = 'Receta Ana'
  vm.form.content.diagnosis = 'Pulpitis 36'
  vm.form.content.medications.push({ name: 'Amoxicilina 750', dose: '1', frequency: '8h', duration: '7d', notes: '' })
}

// Only `open` toggles: the page keeps passing the same `document` value
// (null for "New document", the same record when an edit is reopened).
async function reopen(wrapper: Awaited<ReturnType<typeof mountSuspended>>) {
  await wrapper.setProps({ open: false })
  await flushPromises()
  await wrapper.setProps({ open: true })
  await flushPromises()
}

function expectEmpty(vm: ModalVm) {
  expect(vm.form.patient_id).toBe('')
  expect(vm.selectedPatient).toBeUndefined()
  expect(vm.form.document_type).toBe('prescription')
  expect(vm.form.title).toBe('')
  expect(vm.form.content.diagnosis).toBe('')
  expect(vm.form.content.medications).toEqual([])
}

describe('DocumentCreateModal (#1232)', () => {
  it('opens "New document" empty after a document was created', async () => {
    const wrapper = await mountSuspended(DocumentCreateModal, { props: { open: true, document: null } })
    const vm = wrapper.vm as unknown as ModalVm
    await fillForPatientA(vm)
    await vm.submit()
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/api/v1/documents', expect.objectContaining({ patient_id: 'patient-A', title: 'Receta Ana' }))

    // The page closes the modal on `created` and reopens it with document=null.
    await reopen(wrapper)
    expectEmpty(vm)
  })

  it('opens "New document" empty after a cancelled draft', async () => {
    const wrapper = await mountSuspended(DocumentCreateModal, { props: { open: true, document: null } })
    const vm = wrapper.vm as unknown as ModalVm
    await fillForPatientA(vm)

    await reopen(wrapper)
    expectEmpty(vm)
  })

  it('reopening the same document drops discarded edits', async () => {
    const doc = {
      id: 'doc-1',
      patient_id: 'patient-A',
      document_type: 'medical_certificate',
      title: 'Certificado',
      content: { diagnosis: 'Original' }
    }
    const wrapper = await mountSuspended(DocumentCreateModal, { props: { open: true, document: doc } })
    const vm = wrapper.vm as unknown as ModalVm
    await flushPromises()
    vm.form.title = 'Edited but cancelled'
    vm.form.content.diagnosis = 'Edited'

    await reopen(wrapper)
    expect(vm.form.patient_id).toBe('patient-A')
    expect(vm.form.document_type).toBe('medical_certificate')
    expect(vm.form.title).toBe('Certificado')
    expect(vm.form.content.diagnosis).toBe('Original')
  })

  it('reopening a prescription drops discarded medication edits', async () => {
    const doc = {
      id: 'doc-2',
      patient_id: 'patient-A',
      document_type: 'prescription',
      title: 'Receta',
      content: {
        diagnosis: 'Pulpitis 36',
        medications: [{ name: 'Amoxicilina 750', dose: '1', frequency: '8h', duration: '7d', notes: '' }]
      }
    }
    const original = structuredClone(doc.content.medications)
    const wrapper = await mountSuspended(DocumentCreateModal, { props: { open: true, document: doc } })
    const vm = wrapper.vm as unknown as ModalVm & { addMedication: () => void }
    await flushPromises()
    const meds = vm.form.content.medications as Array<{ dose: string }>
    meds[0]!.dose = '2'
    vm.addMedication()

    await reopen(wrapper)
    expect(vm.form.content.medications).toEqual(original)
  })
})
