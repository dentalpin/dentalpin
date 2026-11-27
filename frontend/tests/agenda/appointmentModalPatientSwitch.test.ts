import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import AppointmentModal from '../../module_layers/agenda/frontend/components/clinical/AppointmentModal.vue'

// #1234: planned items belong to one patient. Switching the patient in the
// appointment modal kept the previous patient's items, and the save sent
// them with the new patient_id (backend 400 "does not belong to patient").

const { get, put } = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }))

const catalogA = { id: 'cat-A', names: { es: 'Endodoncia Ana', en: 'Root canal Ana' }, default_duration_minutes: 60 }
const itemA = {
  id: 'item-A1',
  status: 'pending',
  treatment_plan: { id: 'plan-A', plan_number: 'PT-A' },
  treatment: { catalog_item: catalogA, teeth: [{ tooth_number: 36 }] },
  catalog_item: catalogA
}
const patientA = { id: 'patient-A', first_name: 'Ana', last_name: 'Alpha', phone: '600000001' }
const patientB = { id: 'patient-B', first_name: 'Bea', last_name: 'Beta', phone: '600000002' }

function pendingFor(path: string) {
  return path.includes('patient-A') ? [itemA] : []
}

mockNuxtImport('useApi', () => () => ({ get, post: vi.fn(), patch: vi.fn(), put, del: vi.fn(), raw: vi.fn() }))

beforeEach(() => {
  get.mockReset()
  put.mockReset()
  put.mockImplementation(async (_path: string, body: Record<string, unknown>) => ({ data: { id: 'apt', ...body } }))
  get.mockImplementation(async (path: string) => {
    if (path.startsWith('/api/v1/patients/patient-A')) return { data: patientA }
    // useTreatmentPlans.fetchPatientPendingItems: plan list, then plan detail.
    if (path.includes('/treatment-plans?')) {
      return { data: path.includes('patient-A') ? [{ id: 'plan-A', plan_number: 'PT-A', status: 'active' }] : [] }
    }
    if (path.endsWith('/treatment-plans/plan-A')) return { data: { items: [itemA] } }
    if (path.includes('/schedules/availability')) throw Object.assign(new Error('nf'), { statusCode: 404 })
    return { data: [] }
  })
  // CI's frontend-test registers no module layers, so the layer
  // composables these components auto-import are absent there. Locally
  // (layers registered) the real ones run on top of the mocked useApi.
  vi.stubGlobal('useTreatmentPlans', () => ({
    fetchPatientPendingItems: async (id: string) => pendingFor(`patient_id=${id}`)
  }))
  vi.stubGlobal('useCatalog', () => ({ formatPrice: (v: number) => String(v) }))
  vi.stubGlobal('useAppointments', () => ({
    createAppointment: vi.fn(),
    // Same wire call as the real composable, so one assertion covers both.
    updateAppointment: async (id: string, data: Record<string, unknown>) => (await put(`/api/v1/agenda/appointments/${id}`, data)).data,
    cancelAppointment: vi.fn()
  }))
  vi.stubGlobal('useNotificationSettings', () => ({ fetchSettings: vi.fn(async () => {}), getAutoSendStatus: () => true }))
  vi.stubGlobal('useClinicNotificationChannels', () => ({ buttonsForPatient: () => [], preferredChannel: ref(null) }))
  vi.stubGlobal('useNotificationSend', () => ({ sendConfirmation: vi.fn(), sendReminder: vi.fn(), sendCancellation: vi.fn(), isSending: ref(false) }))
  vi.stubGlobal('useScheduleAvailability', () => ({ fetch: async () => null, fetchOpenRanges: async () => [] }))
  vi.stubGlobal('useAppointmentNotesIndicator', () => ({ fetchFor: vi.fn() }))
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

const baseProps = { initialDate: new Date('2026-12-01T00:00:00'), initialTime: '10:00' }

async function openModal(props: Record<string, unknown>) {
  const wrapper = await mountSuspended(AppointmentModal, { props: { open: false, ...baseProps, ...props } })
  await wrapper.setProps({ open: true })
  await flushPromises()
  return wrapper
}

async function set(vm: Record<string, unknown>, key: string, value: unknown) {
  vm[key] = value
  await flushPromises()
}

function editOf(patient: { id: string }, itemId: string) {
  return {
    id: `apt-${patient.id}`,
    clinic_id: 'clinic-1',
    patient_id: patient.id,
    patient,
    professional_id: 'prof-1',
    start_time: '2026-12-01T10:00:00',
    end_time: '2026-12-01T11:00:00',
    cabinet: null,
    status: 'scheduled',
    treatments: [{
      planned_item_id: itemId,
      planned_item_status: 'pending',
      plan_id: `plan-${patient.id}`,
      catalog_item_id: 'cat-A',
      names: catalogA.names,
      tooth_number: 36
    }]
  }
}

const ids = (vm: Record<string, unknown>) => (vm.selectedTreatments as Array<{ id: string }>).map(t => t.id)

describe('AppointmentModal patient switch (#1234)', () => {
  it('drops the previous patient\'s treatments when a different patient is picked', async () => {
    const vm = (await openModal({})).vm as unknown as Record<string, unknown>
    await set(vm, 'selectedPatient', patientA)
    await set(vm, 'selectedTreatments', [itemA])
    await set(vm, 'selectedPatient', null) // X on the patient card
    await set(vm, 'selectedPatient', patientB)
    expect(ids(vm)).toEqual([])
  })

  it('drops them on a direct switch too', async () => {
    const vm = (await openModal({})).vm as unknown as Record<string, unknown>
    await set(vm, 'selectedPatient', patientA)
    await set(vm, 'selectedTreatments', [itemA])
    await set(vm, 'selectedPatient', patientB)
    expect(ids(vm)).toEqual([])
  })

  it('keeps them when the same patient is picked again', async () => {
    const vm = (await openModal({})).vm as unknown as Record<string, unknown>
    await set(vm, 'selectedPatient', patientA)
    await set(vm, 'selectedTreatments', [itemA])
    await set(vm, 'selectedPatient', null)
    await set(vm, 'selectedPatient', { ...patientA })
    expect(ids(vm)).toEqual(['item-A1'])
  })

  it('keeps an edited appointment\'s linked items on open, clears them on a real switch', async () => {
    const appointment = {
      id: 'apt-1',
      clinic_id: 'clinic-1',
      patient_id: 'patient-A',
      patient: patientA,
      professional_id: 'prof-1',
      start_time: '2026-12-01T10:00:00',
      end_time: '2026-12-01T11:00:00',
      cabinet: null,
      status: 'scheduled',
      treatments: [{
        planned_item_id: 'item-A1',
        planned_item_status: 'pending',
        plan_id: 'plan-A',
        catalog_item_id: 'cat-A',
        names: catalogA.names,
        tooth_number: 36
      }]
    }
    const vm = (await openModal({ appointment })).vm as unknown as Record<string, unknown>
    expect(ids(vm)).toEqual(['item-A1'])
    await set(vm, 'selectedPatient', patientB)
    expect(ids(vm)).toEqual([])
  })

  it('keeps the plan items preselected by the schedule-from-plan flow', async () => {
    const vm = (await openModal({ initialPatientId: 'patient-A', initialPlanId: 'plan-A' })).vm as unknown as Record<string, unknown>
    expect((vm.selectedPatient as { id: string } | null)?.id).toBe('patient-A')
    expect(ids(vm)).toEqual(['item-A1'])
  })

  it('keeps the next appointment\'s linked items when the same modal is reopened for another patient', async () => {
    // The agenda page keeps one modal instance; selectedPatient and
    // selectedTreatments survive a close, so the reopen goes A -> B with
    // B's items already assigned. That is not a user switch.
    const wrapper = await openModal({ appointment: editOf(patientA, 'item-A1') })
    const vm = wrapper.vm as unknown as Record<string, unknown>
    expect(ids(vm)).toEqual(['item-A1'])
    await wrapper.setProps({ open: false })
    await flushPromises()
    await wrapper.setProps({ appointment: editOf(patientB, 'item-B1') })
    await wrapper.setProps({ open: true })
    await flushPromises()
    expect((vm.selectedPatient as { id: string }).id).toBe('patient-B')
    expect(ids(vm)).toEqual(['item-B1'])
    await (vm.handleSave as () => Promise<void>)()
    await flushPromises()
    const body = put.mock.calls.at(-1)?.[1] as { patient_id: string, planned_item_ids: string[] }
    expect(body.patient_id).toBe('patient-B')
    expect(body.planned_item_ids).toEqual(['item-B1'])
  })
})
