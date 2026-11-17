import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { expect, it, vi } from 'vitest'
import type { Appointment } from '../../app/types'
import AppointmentModal from '../../module_layers/agenda/frontend/components/clinical/AppointmentModal.vue'
import AppointmentNotesPanel from '../../module_layers/clinical_notes/frontend/components/AppointmentNotesPanel.vue'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))
mockNuxtImport('useToast', () => () => ({ add: vi.fn() }))
mockNuxtImport('useAuth', () => () => ({ user: ref({ id: 'staff-1' }) }))
mockNuxtImport('useClinic', () => () => ({ cabinets: ref([]) }))
mockNuxtImport('useApi', () => () => ({ get, post }))
mockNuxtImport('usePermissions', () => () => ({ can: () => true }))
mockNuxtImport('useBreakpoint', () => () => ({ isMobile: ref(false) }))
mockNuxtImport('useAppointments', () => () => ({}))
mockNuxtImport('useProfessionals', () => () => ({ professionals: ref([]) }))
mockNuxtImport('useNotificationSettings', () => () => ({ getAutoSendStatus: () => false }))
mockNuxtImport('useClinicNotificationChannels', () => () => ({ buttonsForPatient: () => [] }))
mockNuxtImport('useNotificationSend', () => () => ({ isSending: ref(false) }))
mockNuxtImport('useScheduleAvailability', () => () => ({}))
mockNuxtImport('useNoteTypeMeta', () => () => ({
  metaFor: () => ({ labelKey: 'clinicalNotes.types.appointment_clinical' })
}))

const Modal = defineComponent({
  props: { open: Boolean },
  setup: (props, { slots }) => () => props.open ? h('div', slots.content?.()) : null
})

const NotesSlot = defineComponent({
  props: {
    name: { type: String, required: true },
    ctx: { type: Object, required: true }
  },
  setup: props => () => props.name === 'appointment.detail.notes'
    ? h(AppointmentNotesPanel, { ctx: props.ctx as { appointmentId: string, patientId: string } })
    : null
})

const NoteCard = defineComponent({
  props: { body: String },
  setup: props => () => h('p', props.body)
})

const NoteComposer = defineComponent({
  props: { patientId: String },
  emits: ['submit'],
  setup: (props, { emit }) => () => h('button', {
    'data-patient': props.patientId,
    'data-testid': 'save-note',
    'onClick': () => emit('submit', { body: 'New note', toothNumber: null, attachmentDocumentIds: [] })
  }, 'Save')
})

it('loads and saves appointment notes using the context emitted by the agenda modal', async () => {
  const existing = { id: 'note-1', body: 'Existing note', author_id: 'staff-1' }
  const saved = { id: 'note-2', body: 'New note', author_id: 'staff-1' }
  get.mockResolvedValueOnce({ data: [existing] }).mockResolvedValueOnce({ data: [existing, saved] })
  post.mockResolvedValueOnce({ data: saved })
  const appointment = {
    id: 'appointment-1', patient_id: 'patient-1', status: 'scheduled',
    start_time: '2026-12-01T09:00:00Z', end_time: '2026-12-01T09:30:00Z'
  } as Appointment
  const wrapper = await mountSuspended(AppointmentModal, {
    props: { open: true, appointment },
    global: {
      stubs: {
        UModal: Modal, UCard: { template: '<div><slot /></div>' },
        UButton: { template: '<button><slot /></button>' },
        UFormField: { template: '<div><slot /></div>' },
        UInput: true, USelect: true, UIcon: true,
        PatientVisualSelector: true, PlannedTreatmentSelector: true,
        ModuleSlot: NotesSlot, NoteComposer, NoteCard
      }
    }
  })
  try {
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/api/v1/clinical_notes/notes?owner_type=appointment&owner_id=appointment-1')
    expect(wrapper.text()).toContain('Existing note')
    await wrapper.findAll('button')
      .find(button => button.text() === 'clinicalNotes.appointment.addByType')!
      .trigger('click')
    const save = wrapper.get('[data-testid="save-note"]')
    expect(save.attributes('data-patient')).toBe('patient-1')
    await save.trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith(
      '/api/v1/clinical_notes/notes',
      expect.objectContaining({ owner_type: 'appointment', owner_id: 'appointment-1', body: 'New note' }),
      { errorToast: false }
    )
    expect(get).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('New note')
  } finally {
    wrapper.unmount()
  }
})
