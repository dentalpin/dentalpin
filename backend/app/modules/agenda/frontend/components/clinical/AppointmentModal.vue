<script setup lang="ts">
import type {
  Appointment,
  AppointmentCreate,
  NotificationChannel,
  Patient,
  PlannedTreatmentItem,
  Surface
} from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'
import { formatLocalDate, isoPartsToDateKey, parseIsoParts } from '../../utils/date'
import { errorMessage } from '~~/app/utils/error'

const props = defineProps<{
  open: boolean
  appointment?: Appointment | null
  initialDate?: Date
  initialTime?: string
  initialEndTime?: string
  initialProfessionalId?: string
  /** Pre-fill the cabinet field (#61, mobile free-slot tap when track = cabinet). */
  initialCabinet?: string | null
  initialPatientId?: string
  /** Preselect this plan's pending treatments (treatment-plan flow, #207). */
  initialPlanId?: string
  existingAppointments?: Appointment[]
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'saved': [appointment: Appointment]
  'cancelled': [appointmentId: string]
}>()

const { t } = useI18n()
const toast = useToast()
const auth = useAuth()
const clinic = useClinic()
const api = useApi()
const { can } = usePermissions()
const { isMobile } = useBreakpoint()
const { createAppointment, updateAppointment, cancelAppointment } = useAppointments()
const { professionals, fetchProfessionals, getProfessionalColor } = useProfessionals()
const { fetchSettings, getAutoSendStatus } = useNotificationSettings()
const { buttonsForPatient, preferredChannel } = useClinicNotificationChannels()
const { sendConfirmation, sendReminder, sendCancellation, isSending: isSendingNotification } = useNotificationSend()
const scheduleAvailability = useScheduleAvailability()

// Sentinel value for the "assign later" cabinet option. Reka UI's
// SelectItem rejects empty strings (it reserves them for the
// placeholder state), so we round-trip this token and normalise it
// to null on submit.
const UNASSIGNED_CABINET = '__unassigned__'

// Form state
const isSubmitting = ref(false)
const selectedPatient = ref<Patient | null>(null)
const selectedProfessionalId = ref<string>('')
// Create mode, auto-send OFF: the channel the confirmation goes out on.
// One control per clinic manual channel (issue #287); null = don't send.
const confirmationChannel = ref<NotificationChannel | null>(null)
const selectedTreatments = ref<PlannedTreatmentItem[]>([])
const formData = reactive({
  date: '',
  startTime: '09:00',
  duration: 30,
  cabinet: UNASSIGNED_CABINET
})

// Duration options (in minutes)
const durationOptions = [
  { value: 15, label: '15 min' },
  { value: 30, label: '30 min' },
  { value: 45, label: '45 min' },
  { value: 60, label: '60 min' },
  { value: 90, label: '90 min' },
  { value: 120, label: '120 min' }
]
const validDurations = durationOptions.map(d => d.value)

// Edit mode check
const isEditMode = computed(() => !!props.appointment)

// Auto-update duration based on selected treatments.
// Gated by initialDataLoaded so the initial edit-mode population (which sets
// selectedTreatments) does NOT overwrite the duration we just derived from the
// appointment's start/end times. Only user-driven treatment changes adjust it.
watch(selectedTreatments, (treatments) => {
  if (!initialDataLoaded.value) return
  const totalMinutes = treatments.reduce((acc, t) => {
    // Get duration from catalog_item if available
    const duration = t.catalog_item?.default_price ? 30 : 0 // Default 30 min
    return acc + duration
  }, 0)
  if (totalMinutes > 0) {
    formData.duration = validDurations.reduce((prev, curr) =>
      Math.abs(curr - totalMinutes) < Math.abs(prev - totalMinutes) ? curr : prev
    )
  }
})

// Cabinet options from clinic. Leading "assign later" entry (#51) —
// cabinets are optional at booking and decided at check-in.
const cabinetOptions = computed(() => {
  const assignLater = {
    value: UNASSIGNED_CABINET,
    label: t('appointments.cabinetAssignment.assignLater')
  }
  return [
    assignLater,
    ...clinic.cabinets.value.map(cab => ({
      value: cab.name,
      label: cab.name
    }))
  ]
})

// Professional options
const professionalOptions = computed(() => {
  return professionals.value.map(prof => ({
    value: prof.id,
    label: `${prof.first_name} ${prof.last_name}`,
    color: getProfessionalColor(prof.id)
  }))
})

// Computed
const modalTitle = computed(() =>
  isEditMode.value ? t('appointments.edit') : t('appointments.create')
)

// Send menu in edit mode — Nuxt UI v4 uses an items-prop API instead
// of <UDropdownMenuItem> children. One group per clinic manual channel
// the patient can actually receive (issue #287); items are the
// notification types the staff can (re)send on that channel.
const sendMenuItems = computed(() => {
  const apt = props.appointment
  if (!apt?.id || !apt.patient_id) return []
  const appointmentId = apt.id
  const patientId = apt.patient_id
  const groups: { label: string, icon: string, onSelect: () => void }[][] = []
  for (const btn of buttonsForPatient(apt.patient)) {
    if (btn.disabled) continue
    const channel = btn.channel
    const channelLabel = t(`notifications.channels.${channel}`)
    const group = [
      {
        label: t('appointments.resendConfirmationVia', { channel: channelLabel }),
        icon: 'i-lucide-check-circle',
        onSelect: () => { sendConfirmation(appointmentId, patientId, channel) }
      },
      {
        label: t('appointments.sendReminderVia', { channel: channelLabel }),
        icon: 'i-lucide-clock',
        onSelect: () => { sendReminder(appointmentId, patientId, channel) }
      }
    ]
    // Cancellation notice is only meaningful once the visit is cancelled.
    if (apt.status === 'cancelled') {
      group.push({
        label: t('appointments.sendCancellationVia', { channel: channelLabel }),
        icon: 'i-lucide-calendar-x',
        onSelect: () => { sendCancellation(appointmentId, patientId, channel) }
      })
    }
    groups.push(group)
  }
  return groups
})

const hasSendMenu = computed(() => sendMenuItems.value.length > 0)

const canSave = computed(() => {
  // Cabinet is optional (#51) — only patient + date + start time +
  // professional are required to book.
  return selectedPatient.value && formData.date && formData.startTime && selectedProfessionalId.value
})

// Notification computed properties
const autoSendEnabled = computed(() => getAutoSendStatus('appointment_confirmation'))

// Create mode: one control per manual channel; disabled entries stay
// visible so reception sees why a channel is off (no email / no phone).
const confirmationButtons = computed(() => buttonsForPatient(selectedPatient.value))

function channelDisabledReason(reason?: 'no_email' | 'no_phone' | 'channel_not_manual'): string | undefined {
  if (reason === 'no_email') return t('notifications.channels.noEmail')
  if (reason === 'no_phone') return t('notifications.channels.noPhone')
  return undefined
}

// Default the confirmation channel to the clinic preference (falling
// back to the first channel the patient can receive) whenever the
// patient changes in create mode.
function resetConfirmationDefault() {
  const enabled = confirmationButtons.value.filter(b => !b.disabled)
  const preferred = enabled.find(b => b.channel === preferredChannel.value)
  confirmationChannel.value = (preferred ?? enabled[0])?.channel ?? null
}

watch(selectedPatient, () => {
  if (!isEditMode.value) resetConfirmationDefault()
})

// Check for overlapping appointments
const overlappingAppointments = computed(() => {
  if (!formData.date || !formData.startTime || !props.existingAppointments || props.existingAppointments.length === 0) {
    return { sameProfessional: [], sameCabinet: [] }
  }

  // Parse form time as minutes from midnight for comparison
  const formTimeParts = formData.startTime.split(':').map(Number)
  const formStartMinutes = (formTimeParts[0] ?? 0) * 60 + (formTimeParts[1] ?? 0)
  const formEndMinutes = formStartMinutes + formData.duration

  const sameProfessional: Appointment[] = []
  const sameCabinet: Appointment[] = []

  for (const apt of props.existingAppointments) {
    // Skip the current appointment being edited
    if (props.appointment && apt.id === props.appointment.id) continue
    // Skip cancelled appointments
    if (apt.status === 'cancelled') continue

    // Check if same date (compare date strings directly)
    const aptDate = apt.start_time.split('T')[0]
    if (aptDate !== formData.date) continue

    // Parse appointment times as minutes from midnight
    const aptStartTime = apt.start_time.split('T')[1]?.substring(0, 5) ?? '00:00'
    const aptEndTime = apt.end_time.split('T')[1]?.substring(0, 5) ?? '00:00'

    const aptStartParts = aptStartTime.split(':').map(Number)
    const aptEndParts = aptEndTime.split(':').map(Number)

    const aptStartMinutes = (aptStartParts[0] ?? 0) * 60 + (aptStartParts[1] ?? 0)
    const aptEndMinutes = (aptEndParts[0] ?? 0) * 60 + (aptEndParts[1] ?? 0)

    // Check if times overlap
    const overlaps = formStartMinutes < aptEndMinutes && formEndMinutes > aptStartMinutes

    if (overlaps) {
      if (apt.professional_id === selectedProfessionalId.value) {
        sameProfessional.push(apt)
      }
      if (apt.cabinet === formData.cabinet) {
        sameCabinet.push(apt)
      }
    }
  }

  return { sameProfessional, sameCabinet }
})

// Track initial overlaps when modal opens (to avoid warning about pre-existing overlaps)
const initialOverlapIds = ref<{ professional: Set<string>, cabinet: Set<string> }>({
  professional: new Set(),
  cabinet: new Set()
})
// Flag to know when initial data has been loaded
const initialDataLoaded = ref(false)
// Track if we've already shown the overlap warning for current config
const lastOverlapWarningKey = ref('')

// Show toast when NEW overlaps are detected (not pre-existing ones)
watch(overlappingAppointments, (overlaps) => {
  // Only warn while the modal is open — prevents a false positive when the
  // parent reloads `existingAppointments` right after save/close and the
  // just-created appointment re-triggers the overlap computation.
  if (!props.open) return
  // Don't check until initial data is loaded
  if (!initialDataLoaded.value) return

  // Filter out overlaps that existed when modal opened
  const newProfessionalOverlaps = overlaps.sameProfessional.filter(
    apt => !initialOverlapIds.value.professional.has(apt.id)
  )
  const newCabinetOverlaps = overlaps.sameCabinet.filter(
    apt => !initialOverlapIds.value.cabinet.has(apt.id)
  )

  const hasNewProfessionalOverlap = newProfessionalOverlaps.length > 0
  const hasNewCabinetOverlap = newCabinetOverlaps.length > 0

  if (!hasNewProfessionalOverlap && !hasNewCabinetOverlap) {
    lastOverlapWarningKey.value = ''
    return
  }

  // Create a key to avoid showing the same warning repeatedly
  const warningKey = `${formData.date}-${formData.startTime}-${formData.duration}-${selectedProfessionalId.value}-${formData.cabinet}`

  if (warningKey === lastOverlapWarningKey.value) return
  lastOverlapWarningKey.value = warningKey

  // Build warning message
  const warnings: string[] = []
  if (hasNewProfessionalOverlap) {
    warnings.push(t('appointments.overlapProfessional', { count: newProfessionalOverlaps.length }))
  }
  if (hasNewCabinetOverlap) {
    warnings.push(t('appointments.overlapCabinet', { count: newCabinetOverlaps.length }))
  }

  toast.add({
    title: t('appointments.overlapWarning'),
    description: warnings.join('. '),
    color: 'warning',
    icon: 'i-lucide-alert-triangle'
  })
}, { deep: true })

// Watch for initial values
watch(() => props.open, async (isOpen) => {
  if (!isOpen) {
    // Disable overlap warnings while closed so reloads of existingAppointments
    // don't trigger a late false positive.
    initialDataLoaded.value = false
    // Re-check the "has notes" indicator for this appointment so the
    // sticky-note icon appears immediately after the user creates a
    // note from the slot panel. Bounded — single id round-trip.
    if (props.appointment?.id) {
      useAppointmentNotesIndicator().fetchFor([props.appointment.id])
    }
    return
  }
  // Reset flags when modal opens
  initialDataLoaded.value = false
  lastOverlapWarningKey.value = ''
  initialOverlapIds.value = { professional: new Set(), cabinet: new Set() }

  // Fetch professionals always. Notification settings only if the user
  // has permission to read them — receptionists don't, and unconditional
  // fetching produced "Access denied" / "Error loading settings" toasts
  // every time they opened the modal. When skipped, getAutoSendStatus
  // falls back to its sensible default (auto-send on).
  const tasks: Array<Promise<unknown>> = [fetchProfessionals()]
  if (can(PERMISSIONS.notifications.settingsRead)) {
    tasks.push(fetchSettings())
  }
  await Promise.all(tasks)

  if (props.appointment) {
    // Edit mode - populate from appointment
    const apt = props.appointment
    selectedPatient.value = apt.patient || null
    selectedProfessionalId.value = apt.professional_id
    formData.date = apt.start_time.split('T')[0] ?? ''
    formData.startTime = apt.start_time.split('T')[1]?.substring(0, 5) ?? '09:00'
    // null cabinet (#51) maps to the "assign later" option.
    formData.cabinet = apt.cabinet ?? UNASSIGNED_CABINET

    // Map each AppointmentTreatmentBrief into a PlannedTreatmentItem shape so the
    // shared selector can render it. The Treatment.id is not available in the
    // brief, so we leave treatment_id empty; it is only used server-side when
    // submitting, and the selector keys off the PlannedTreatmentItem.id.
    if (apt.treatments && apt.treatments.length > 0) {
      selectedTreatments.value = apt.treatments.map((t): PlannedTreatmentItem => ({
        id: t.planned_item_id,
        clinic_id: apt.clinic_id,
        treatment_plan_id: t.plan_id || '',
        treatment_id: '',
        sequence_order: 0,
        status: t.planned_item_status,
        completed_without_appointment: false,
        completed_at: undefined,
        completed_by: undefined,
        notes: undefined,
        created_at: '',
        updated_at: '',
        treatment: {
          id: '',
          clinical_type: 'crown',
          scope: 'tooth',
          arch: null,
          status: 'planned',
          catalog_item_id: t.catalog_item_id,
          price_snapshot: t.default_price ? String(t.default_price) : null,
          teeth: t.tooth_number
            ? [{
                tooth_number: t.tooth_number,
                role: null,
                surfaces: (t.surfaces as Surface[] | undefined) ?? null
              }]
            : []
        },
        catalog_item: t.catalog_item_id
          ? {
              id: t.catalog_item_id,
              internal_code: t.internal_code,
              names: t.names,
              default_price: t.default_price != null ? String(t.default_price) : null
            }
          : undefined
      }))
    } else {
      selectedTreatments.value = []
    }

    // Calculate duration from start/end time, rounded to nearest valid option
    const start = new Date(apt.start_time)
    const end = new Date(apt.end_time)
    const calculatedDuration = Math.round((end.getTime() - start.getTime()) / 60000)
    formData.duration = validDurations.reduce((prev, curr) =>
      Math.abs(curr - calculatedDuration) < Math.abs(prev - calculatedDuration) ? curr : prev
    )
  } else {
    // Create mode - use initial values
    if (props.initialDate) {
      formData.date = formatLocalDate(props.initialDate)
    } else {
      formData.date = formatLocalDate(new Date())
    }

    if (props.initialTime) {
      formData.startTime = props.initialTime
    } else {
      formData.startTime = '09:00'
    }

    // Set professional - use initialProfessionalId, current user if professional, or first available
    if (props.initialProfessionalId) {
      selectedProfessionalId.value = props.initialProfessionalId
    } else {
      // Check if current user is a professional
      const currentUserId = auth.user.value?.id
      const isCurrentUserProfessional = professionals.value.some(p => p.id === currentUserId)
      if (isCurrentUserProfessional && currentUserId) {
        selectedProfessionalId.value = currentUserId
      } else {
        selectedProfessionalId.value = professionals.value[0]?.id || ''
      }
    }

    // Pre-select patient if initialPatientId provided
    if (props.initialPatientId) {
      try {
        const response = await api.get<{ data: Patient }>(`/api/v1/patients/${props.initialPatientId}`)
        selectedPatient.value = response.data
      } catch {
        selectedPatient.value = null
      }
    } else {
      selectedPatient.value = null
    }
    if (props.initialEndTime) {
      const startParts = formData.startTime.split(':').map(Number)
      const endParts = props.initialEndTime.split(':').map(Number)
      const startMin = (startParts[0] ?? 9) * 60 + (startParts[1] ?? 0)
      const endMin = (endParts[0] ?? 9) * 60 + (endParts[1] ?? 0)
      const draggedMinutes = endMin - startMin
      formData.duration = draggedMinutes > 0
        ? validDurations.reduce((prev, curr) =>
            Math.abs(curr - draggedMinutes) < Math.abs(prev - draggedMinutes) ? curr : prev)
        : clinic.slotDuration.value || 30
    } else {
      formData.duration = clinic.slotDuration.value || 30
    }
    // Default to unassigned (#51): the cabinet is decided at check-in.
    // Free-slot tap (#61) may pre-fill a cabinet when the user was
    // viewing a cabinet-track on mobile.
    if (props.initialCabinet) {
      const matchesClinicCabinet = clinic.cabinets.value.some(c => c.name === props.initialCabinet)
      formData.cabinet = matchesClinicCabinet ? props.initialCabinet : UNASSIGNED_CABINET
    } else {
      formData.cabinet = UNASSIGNED_CABINET
    }
    selectedTreatments.value = []
    // Reset the confirmation channel for create mode (clinic preference
    // first, then whatever the patient can receive).
    resetConfirmationDefault()
  }

  // Wait for next tick so overlappingAppointments computed can recalculate
  await nextTick()

  // Capture initial overlaps (these existed before user made changes)
  const currentOverlaps = overlappingAppointments.value
  initialOverlapIds.value = {
    professional: new Set(currentOverlaps.sameProfessional.map(apt => apt.id)),
    cabinet: new Set(currentOverlaps.sameCabinet.map(apt => apt.id))
  }

  // Now enable overlap warnings for new overlaps only
  initialDataLoaded.value = true
})

// Calculate end time from start time and duration
function calculateEndTime(): string {
  const timeParts = formData.startTime.split(':').map(Number)
  const startHours = timeParts[0] ?? 9
  const startMinutes = timeParts[1] ?? 0

  // Add duration in minutes
  const totalMinutes = startHours * 60 + startMinutes + formData.duration
  const endHours = Math.floor(totalMinutes / 60) % 24
  const endMinutes = totalMinutes % 60

  // Build end time string in same format as start time
  const endTimeStr = `${endHours.toString().padStart(2, '0')}:${endMinutes.toString().padStart(2, '0')}`

  return `${formData.date}T${endTimeStr}:00`
}

async function handleSave() {
  if (!canSave.value || !selectedPatient.value) return

  isSubmitting.value = true
  // Silence the overlap watcher: createAppointment mutates the shared
  // appointments array, so the brand-new appointment would otherwise
  // self-overlap with formData before the modal closes.
  initialDataLoaded.value = false

  try {
    // Build start_time ISO string
    const startTime = `${formData.date}T${formData.startTime}:00`
    const endTime = calculateEndTime()

    // Schedules-module enforcement (UI-only). The composable is
    // 404-tolerant: if schedules is uninstalled it returns null and
    // we skip the check. Otherwise warn the user when the slot is
    // outside open hours and ask for confirmation.
    const availability = await scheduleAvailability.fetch({
      start: formData.date,
      end: formData.date,
      professional_id: selectedProfessionalId.value
    })
    if (availability) {
      // Compare wall-clock minutes against the clinic-TZ ranges instead
      // of routing both sides through ``new Date()``. The form values are
      // naive (browser-local) while ``r.start``/``r.end`` carry the clinic
      // offset (e.g. ``-04:00`` for an NY clinic), so comparing instants
      // shifted slots by the browser↔clinic gap and flagged in-hours
      // slots as outside hours when the two zones disagree. Mirrors the
      // wall-clock approach used by ``useCalendarBounds`` /
      // ``useBlockedSegments``.
      const [fh, fm] = formData.startTime.split(':').map(Number)
      const formStart = (fh ?? 0) * 60 + (fm ?? 0)
      const formEnd = formStart + formData.duration
      const conflict = availability.ranges.find((r) => {
        if (r.state === 'open') return false
        const sParts = parseIsoParts(r.start)
        const eParts = parseIsoParts(r.end)
        const sDate = isoPartsToDateKey(sParts)
        const eDate = isoPartsToDateKey(eParts)
        if (sDate !== formData.date && eDate !== formData.date) return false
        const rStart = sDate === formData.date ? sParts.hour * 60 + sParts.minute : 0
        const rEnd = eDate === formData.date ? eParts.hour * 60 + eParts.minute : 24 * 60
        return rStart < formEnd && rEnd > formStart
      })
      if (conflict) {
        const confirmed = window.confirm(t('schedules.availability.confirmOutside'))
        if (!confirmed) {
          isSubmitting.value = false
          return
        }
      }
    }

    // The "assign later" sentinel (#51) means no cabinet yet — normalise
    // to null so the API stores NULL and downstream UIs can identify
    // unassigned appointments unambiguously.
    const cabinetValue = formData.cabinet && formData.cabinet !== UNASSIGNED_CABINET
      ? formData.cabinet
      : null

    const appointmentData: AppointmentCreate = {
      patient_id: selectedPatient.value.id,
      professional_id: selectedProfessionalId.value,
      cabinet: cabinetValue,
      start_time: startTime,
      end_time: endTime,
      planned_item_ids: selectedTreatments.value.length > 0
        ? selectedTreatments.value.map(t => t.id)
        : undefined
    }

    let savedAppointment: Appointment

    if (isEditMode.value && props.appointment) {
      savedAppointment = await updateAppointment(props.appointment.id, appointmentData)
      toast.add({
        title: t('common.success'),
        description: t('appointments.updated'),
        color: 'success'
      })
    } else {
      savedAppointment = await createAppointment(appointmentData)
      toast.add({
        title: t('common.success'),
        description: t('appointments.created'),
        color: 'success'
      })

      // Explicit send only when auto-send is off and a channel is picked —
      // with auto-send on, the appointment.scheduled event drives it.
      if (!autoSendEnabled.value && confirmationChannel.value) {
        await sendConfirmation(
          savedAppointment.id,
          savedAppointment.patient_id || '',
          confirmationChannel.value
        )
      }
    }

    emit('saved', savedAppointment)
    emit('update:open', false)
  } catch (error: unknown) {
    const fetchError = error as { statusCode?: number, data?: { message?: string, detail?: string } }

    if (fetchError.statusCode === 409) {
      toast.add({
        title: t('common.error'),
        description: t('appointments.conflict'),
        color: 'error'
      })
    } else {
      toast.add({
        title: t('common.error'),
        description: fetchError.data?.detail || fetchError.data?.message || t('common.serverError'),
        color: 'error'
      })
    }
  } finally {
    isSubmitting.value = false
  }
}

// Cancelling an appointment is destructive (no undo endpoint) — the footer
// button opens a confirmation first (issue #101). Mirrors the confirm step
// AppointmentQuickActions already applies to the cancel transition.
const showCancelConfirm = ref(false)

async function handleCancel() {
  if (!props.appointment) return

  isSubmitting.value = true

  try {
    await cancelAppointment(props.appointment.id)
    toast.add({
      title: t('common.success'),
      description: t('appointments.cancelled'),
      color: 'success'
    })
    emit('cancelled', props.appointment.id)
    emit('update:open', false)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('common.serverError')),
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
    showCancelConfirm.value = false
  }
}

function closeModal() {
  emit('update:open', false)
}

function openPatientFile() {
  if (!selectedPatient.value) return
  const id = selectedPatient.value.id
  closeModal()
  navigateTo(`/patients/${id}`)
}
</script>

<template>
  <UModal
    :open="open"
    :fullscreen="isMobile"
    @update:open="$emit('update:open', $event)"
  >
    <template #content>
      <UCard
        :ui="{
          root: isMobile ? 'h-full flex flex-col' : 'sm:max-w-2xl',
          body: isMobile ? 'flex-1 min-h-0 overflow-hidden p-0' : ''
        }"
      >
        <template #header>
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="text-h1 text-default truncate">
                {{ modalTitle }}
              </h2>
              <div
                v-if="selectedPatient"
                class="flex items-center gap-2 mt-0.5 flex-wrap min-w-0"
              >
                <p class="text-caption text-subtle truncate min-w-0">
                  {{ selectedPatient.first_name }} {{ selectedPatient.last_name }}
                </p>
                <UButton
                  v-if="can(PERMISSIONS.patients.read)"
                  variant="link"
                  color="primary"
                  size="xs"
                  icon="i-lucide-external-link"
                  :padded="false"
                  :aria-label="`${t('appointments.openPatientFile')} — ${selectedPatient.first_name} ${selectedPatient.last_name}`"
                  @click="openPatientFile"
                >
                  {{ t('appointments.openPatientFile') }}
                </UButton>
              </div>
            </div>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              size="sm"
              :aria-label="t('common.close', 'Cerrar')"
              @click="closeModal"
            />
          </div>
        </template>

        <div
          :class="isMobile
            ? 'h-full overflow-y-auto px-4 py-4'
            : 'max-h-[65vh] overflow-y-auto pr-1'"
        >
          <form
            class="space-y-6"
            @submit.prevent="handleSave"
          >
            <!-- Section 1: Paciente -->
            <section class="space-y-3">
              <div class="flex items-center gap-2 text-caption uppercase tracking-wide text-subtle">
                <UIcon
                  name="i-lucide-user"
                  class="w-3.5 h-3.5"
                />
                {{ t('appointments.selectPatient') }}
              </div>
              <PatientVisualSelector
                v-model="selectedPatient"
                in-modal
              />
              <div v-if="selectedPatient">
                <p class="text-caption text-subtle mb-1.5">
                  {{ t('appointments.treatments') }}
                </p>
                <PlannedTreatmentSelector
                  v-model="selectedTreatments"
                  :patient-id="selectedPatient?.id"
                  :preselect-plan-id="!appointment ? initialPlanId : undefined"
                />
              </div>
            </section>

            <!-- Section 2: Cuándo (date + time + duration chips) -->
            <section class="space-y-3">
              <div class="flex items-center gap-2 text-caption uppercase tracking-wide text-subtle">
                <UIcon
                  name="i-lucide-calendar-clock"
                  class="w-3.5 h-3.5"
                />
                {{ t('appointments.when', 'Cuándo') }}
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <UFormField
                  :label="t('appointments.date')"
                  required
                >
                  <UInput
                    v-model="formData.date"
                    type="date"
                    :size="isMobile ? 'lg' : 'md'"
                    icon="i-lucide-calendar"
                    required
                  />
                </UFormField>
                <UFormField
                  :label="t('appointments.startTime')"
                  required
                >
                  <UInput
                    v-model="formData.startTime"
                    type="time"
                    :size="isMobile ? 'lg' : 'md'"
                    icon="i-lucide-clock"
                    required
                  />
                </UFormField>
              </div>
              <div>
                <p class="text-caption text-subtle mb-1.5">
                  {{ t('appointments.duration') }}
                </p>
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="d in durationOptions"
                    :key="d.value"
                    type="button"
                    class="px-3 py-1.5 rounded-token-md text-sm font-medium transition-colors border"
                    :class="formData.duration === d.value
                      ? 'border-primary bg-primary/10 text-primary-accent'
                      : 'border-default bg-default text-default hover:bg-elevated'"
                    :aria-pressed="formData.duration === d.value"
                    @click="formData.duration = d.value"
                  >
                    {{ d.label }}
                  </button>
                </div>
              </div>
            </section>

            <!-- Section 3: Dónde + quién (cabinet + professional) -->
            <section class="space-y-3">
              <div class="flex items-center gap-2 text-caption uppercase tracking-wide text-subtle">
                <UIcon
                  name="i-lucide-map-pin"
                  class="w-3.5 h-3.5"
                />
                {{ t('appointments.whereWho', 'Gabinete y profesional') }}
              </div>
              <UFormField :label="t('appointments.cabinet')">
                <USelect
                  v-model="formData.cabinet"
                  :items="cabinetOptions"
                  value-key="value"
                  label-key="label"
                  :size="isMobile ? 'lg' : 'md'"
                  :placeholder="t('appointments.cabinet')"
                  icon="i-lucide-door-open"
                />
              </UFormField>

              <UFormField
                :label="t('appointments.professional')"
                required
              >
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="p in professionalOptions"
                    :key="p.value"
                    type="button"
                    class="inline-flex items-center gap-2 px-3 py-1.5 rounded-token-md text-sm font-medium transition-colors border"
                    :class="selectedProfessionalId === p.value
                      ? 'border-primary bg-primary/10 text-primary-accent'
                      : 'border-default bg-default text-default hover:bg-elevated'"
                    :aria-pressed="selectedProfessionalId === p.value"
                    @click="selectedProfessionalId = p.value"
                  >
                    <span
                      class="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                      :style="{ background: p.color }"
                      aria-hidden="true"
                    />
                    {{ p.label }}
                  </button>
                </div>
              </UFormField>
            </section>

            <!-- Section 4: Notas — slot rendered by clinical_notes when an
                 appointment exists (edit mode). On create, the modal hides
                 it: the appointment must be saved first so we have an id to
                 anchor the polymorphic notes to. -->
            <section
              v-if="isEditMode && appointment?.id"
              class="space-y-3"
            >
              <div class="flex items-center gap-2 text-caption uppercase tracking-wide text-subtle">
                <UIcon
                  name="i-lucide-sticky-note"
                  class="w-3.5 h-3.5"
                />
                {{ t('appointments.notes') }}
              </div>
              <ModuleSlot
                name="appointment.detail.notes"
                :ctx="{ appointmentId: appointment.id, patientId: appointment.patient_id }"
              />
            </section>
          </form>
        </div>

        <template #footer>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-2 flex-wrap">
              <UButton
                v-if="isEditMode && appointment?.status !== 'cancelled'"
                variant="outline"
                color="error"
                icon="i-lucide-x"
                :loading="isSubmitting"
                @click="showCancelConfirm = true"
              >
                {{ t('appointments.cancel') }}
              </UButton>

              <!-- Send menu in edit mode — items follow the clinic's
                   manual channels and the patient's contact details. -->
              <UDropdownMenu
                v-if="isEditMode && hasSendMenu"
                :items="sendMenuItems"
              >
                <UButton
                  variant="outline"
                  icon="i-lucide-send"
                  :loading="isSendingNotification"
                >
                  {{ t('appointments.sendMessage') }}
                </UButton>
              </UDropdownMenu>
            </div>
            <div class="flex flex-col-reverse sm:flex-row sm:items-center gap-2 sm:gap-3">
              <!-- Send-confirmation channel controls surface inline on
                   desktop, stack above on mobile so the primary action
                   stays at the thumb. Hidden when auto-send is on: the
                   appointment.scheduled event drives the send. -->
              <div
                v-if="!isEditMode && !autoSendEnabled && selectedPatient && confirmationButtons.length"
                class="flex items-center gap-3 flex-wrap text-sm text-muted"
              >
                <span>{{ t('appointments.sendConfirmationEmail') }}:</span>
                <label
                  v-for="btn in confirmationButtons"
                  :key="btn.channel"
                  class="flex items-center gap-2"
                  :class="btn.disabled ? 'opacity-60' : 'cursor-pointer'"
                  :title="channelDisabledReason(btn.reason)"
                >
                  <UCheckbox
                    :model-value="confirmationChannel === btn.channel"
                    :disabled="btn.disabled"
                    @update:model-value="(v: boolean | 'indeterminate') => confirmationChannel = v === true ? btn.channel : null"
                  />
                  <span>{{ t(`notifications.channels.${btn.channel}`) }}</span>
                </label>
              </div>
              <div class="flex flex-col-reverse sm:flex-row gap-2">
                <UButton
                  variant="ghost"
                  color="neutral"
                  @click="closeModal"
                >
                  {{ t('common.cancel') }}
                </UButton>
                <UButton
                  icon="i-lucide-calendar-plus"
                  :loading="isSubmitting"
                  :disabled="!canSave"
                  @click="handleSave"
                >
                  {{ t('common.save') }}
                </UButton>
              </div>
            </div>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>

  <!-- Cancel-appointment confirmation (destructive, no undo endpoint) -->
  <UModal v-model:open="showCancelConfirm">
    <template #content>
      <div class="p-4 space-y-4">
        <h2 class="text-h3 text-default">
          {{ t('appointments.cancel') }}
        </h2>
        <p class="text-caption text-subtle">
          {{ t('appointments.confirmCancelMessage') }}
        </p>
        <div class="flex justify-end gap-2">
          <UButton
            variant="ghost"
            @click="showCancelConfirm = false"
          >
            {{ t('actions.cancel') }}
          </UButton>
          <UButton
            color="error"
            :loading="isSubmitting"
            @click="handleCancel"
          >
            {{ t('appointments.cancel') }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
