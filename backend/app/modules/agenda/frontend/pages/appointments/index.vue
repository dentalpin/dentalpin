<script setup lang="ts">
import type { Appointment } from '~~/app/types'
import { defineAsyncComponent } from 'vue'
import { formatLocalDate } from '../../utils/date'

// Mode-specific scheduler views are heavy (drag grids, overlap math, mobile
// timeline). Lazy-load each so the initial /agenda payload only ships the
// active mode for the current viewport.
const AppointmentCalendar = defineAsyncComponent(() => import('../../components/clinical/AppointmentCalendar.vue'))
const AppointmentDailyView = defineAsyncComponent(() => import('../../components/clinical/AppointmentDailyView.vue'))
const AppointmentKanbanView = defineAsyncComponent(() => import('../../components/clinical/AppointmentKanbanView.vue'))
const AppointmentMobileDayView = defineAsyncComponent(() => import('../../components/clinical/AppointmentMobileDayView.vue'))

const { t } = useI18n()
const toast = useToast()
const route = useRoute()
const router = useRouter()
const clinic = useClinic()
const { appointments, isLoading, error: loadError, fetchAppointments, updateAppointment } = useAppointments()
const { professionals, fetchProfessionals, getProfessionalColor } = useProfessionals()
const { isMobile } = useBreakpoint()

// Query params for pre-selecting patient from treatment plan flow
const initialPatientId = ref<string | undefined>(
  typeof route.query.patient_id === 'string' ? route.query.patient_id : undefined
)
// Set by the treatment-plan flow: preselect this plan's pending
// treatments in the create modal (#207).
const initialPlanId = ref<string | undefined>(
  typeof route.query.plan_id === 'string' ? route.query.plan_id : undefined
)

// View mode state
const viewMode = ref<'week' | 'day' | 'kanban'>('week')

// Week state (for weekly view)
const currentWeekStart = ref<Date>(getMonday(new Date()))

// Day state (for daily view)
const currentDate = ref<Date>(new Date())

// Cabinet filter state
const selectedCabinets = ref<string[]>([])

// Professional filter state
const selectedProfessionals = ref<string[]>([])

// Highlight state (from reschedule navigation)
const highlightedAppointmentId = ref<string | null>(
  typeof route.query.highlight === 'string' ? route.query.highlight : null
)
const highlightDate = typeof route.query.date === 'string' ? route.query.date : null

// Navigate to correct week if highlight date provided
if (highlightDate) {
  const targetDate = new Date(highlightDate + 'T00:00:00')
  currentWeekStart.value = getMonday(targetDate)
  currentDate.value = targetDate
}

// Clear highlight after a delay (let user see it, then clear for future interactions)
function clearHighlight() {
  highlightedAppointmentId.value = null
  router.replace({ query: { ...route.query, highlight: undefined, date: undefined } })
}

// Initialize selected cabinets when clinic loads
watch(() => clinic.cabinets.value, (cabinets) => {
  if (cabinets.length > 0 && selectedCabinets.value.length === 0) {
    selectedCabinets.value = cabinets.map(c => c.name)
  }
}, { immediate: true })

// Initialize selected professionals when professionals load
watch(professionals, (profs) => {
  if (profs.length > 0 && selectedProfessionals.value.length === 0) {
    selectedProfessionals.value = profs.map(p => p.id)
  }
}, { immediate: true })

// Filtered appointments based on selected cabinets and professionals
const filteredAppointments = computed(() => {
  let result = appointments.value

  // Filter by cabinet — unassigned appointments (#51) always pass the
  // cabinet filter so the receptionist can still see and drop-assign them.
  if (selectedCabinets.value.length > 0) {
    result = result.filter(
      apt => apt.cabinet === null || selectedCabinets.value.includes(apt.cabinet)
    )
  }

  // Filter by professional
  if (selectedProfessionals.value.length > 0) {
    result = result.filter(apt => selectedProfessionals.value.includes(apt.professional_id))
  }

  return result
})

// Cabinet filter options
const cabinetFilterOptions = computed(() => {
  return clinic.cabinets.value.map(cab => ({
    label: cab.name,
    value: cab.name,
    color: cab.color
  }))
})

// Professional filter options
const professionalFilterOptions = computed(() => {
  return professionals.value.map(prof => ({
    label: `${prof.first_name} ${prof.last_name}`,
    value: prof.id,
    color: getProfessionalColor(prof.id)
  }))
})

// Professionals with colors for calendar
const professionalsWithColors = computed(() => {
  return professionals.value.map(prof => ({
    ...prof,
    color: getProfessionalColor(prof.id)
  }))
})

// Toggle cabinet filter
function toggleCabinet(cabinetName: string) {
  const index = selectedCabinets.value.indexOf(cabinetName)
  if (index === -1) {
    selectedCabinets.value.push(cabinetName)
  } else {
    selectedCabinets.value.splice(index, 1)
  }
}

// Select all cabinets
function selectAllCabinets() {
  selectedCabinets.value = clinic.cabinets.value.map(c => c.name)
}

// Toggle professional filter
function toggleProfessional(professionalId: string) {
  const index = selectedProfessionals.value.indexOf(professionalId)
  if (index === -1) {
    selectedProfessionals.value.push(professionalId)
  } else {
    selectedProfessionals.value.splice(index, 1)
  }
}

// #51: clicking a pill on the kanban professionals strip focuses the
// board on that single pro. Null = clear the filter and restore the
// full selection.
function handleProfessionalFilter(professionalId: string | null) {
  if (professionalId === null) {
    selectedProfessionals.value = professionals.value.map(p => p.id)
  } else {
    selectedProfessionals.value = [professionalId]
  }
}

// Select all professionals
function selectAllProfessionals() {
  selectedProfessionals.value = professionals.value.map(p => p.id)
}

// Modal state
const isModalOpen = ref(false)
const selectedAppointment = ref<Appointment | null>(null)
const initialDate = ref<Date | undefined>()
const initialTime = ref<string | undefined>()
const initialEndTime = ref<string | undefined>()
const initialProfessionalId = ref<string | undefined>()
const initialCabinet = ref<string | null | undefined>()

// Get Monday of the current week
function getMonday(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  d.setHours(0, 0, 0, 0)
  return d
}

// Get week end (Sunday)
function getWeekEnd(start: Date): Date {
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  end.setHours(23, 59, 59, 999)
  return end
}

// Load appointments for current week
async function loadWeekAppointments() {
  const start = currentWeekStart.value
  const end = getWeekEnd(start)
  await fetchAppointments(start, end)
}

// Reload whichever window the active view is showing. Used both after
// local mutations and when another surface (e.g. the copilot) signals it
// changed agenda data.
async function reloadActiveView() {
  if (!isMobile.value && viewMode.value === 'week') {
    await loadWeekAppointments()
  } else {
    await loadDayAppointments()
  }
}

// The copilot (or any other surface) can book/cancel appointments without
// this page knowing. Refetch when the data bus signals an ``agenda`` change.
useDataBus().on('agenda', reloadActiveView)

// Handle week change
async function handleWeekChange(newStart: Date) {
  currentWeekStart.value = newStart
  await loadWeekAppointments()
}

// Handle slot click from weekly view - open modal for new appointment
function handleSlotClick(date: Date, time: string) {
  selectedAppointment.value = null
  initialDate.value = date
  initialTime.value = time
  initialEndTime.value = undefined
  initialProfessionalId.value = undefined
  initialCabinet.value = undefined
  // Keep initialPatientId from URL so patient is pre-selected
  isModalOpen.value = true
}

// Handle free-slot tap from mobile timeline (#61) — pre-fill the
// composer with the gap's start, duration (via end time) and the
// resource (professional or cabinet) the user was viewing.
function handleFreeSlotTap(payload: {
  slot: { start: Date, end: Date, durationMin: number }
  resource: { kind: 'professional' | 'cabinet', id: string }
}) {
  const { slot, resource } = payload
  selectedAppointment.value = null
  initialDate.value = new Date(slot.start)
  initialTime.value = `${String(slot.start.getHours()).padStart(2, '0')}:${String(slot.start.getMinutes()).padStart(2, '0')}`
  // Cap suggested end at the gap end so the modal picks the closest
  // valid duration option without overflowing into the next event.
  initialEndTime.value = `${String(slot.end.getHours()).padStart(2, '0')}:${String(slot.end.getMinutes()).padStart(2, '0')}`
  if (resource.kind === 'professional') {
    initialProfessionalId.value = resource.id
    initialCabinet.value = undefined
  } else {
    initialProfessionalId.value = undefined
    initialCabinet.value = resource.id
  }
  isModalOpen.value = true
}

// Handle drag-to-create from weekly view - open modal with end time pre-filled
function handleSlotDragCreate(date: Date, startTime: string, endTime: string) {
  selectedAppointment.value = null
  initialDate.value = date
  initialTime.value = startTime
  initialEndTime.value = endTime
  initialProfessionalId.value = undefined
  initialCabinet.value = undefined
  // Keep initialPatientId from URL so patient is pre-selected
  isModalOpen.value = true
}

// Handle slot click from daily view - open modal with professional pre-selected
function handleDailySlotClick(professionalId: string, time: string) {
  selectedAppointment.value = null
  initialDate.value = currentDate.value
  initialTime.value = time
  initialEndTime.value = undefined
  initialProfessionalId.value = professionalId
  initialCabinet.value = undefined
  // Keep initialPatientId from URL so patient is pre-selected
  isModalOpen.value = true
}

// Handle drag-to-create from daily view - open modal with professional and end time pre-filled
function handleDailySlotDragCreate(professionalId: string, startTime: string, endTime: string) {
  selectedAppointment.value = null
  initialDate.value = currentDate.value
  initialTime.value = startTime
  initialEndTime.value = endTime
  initialProfessionalId.value = professionalId
  initialCabinet.value = undefined
  // Keep initialPatientId from URL so patient is pre-selected
  isModalOpen.value = true
}

// Handle date change in daily view
function handleDateChange(newDate: Date) {
  currentDate.value = newDate
  loadDayAppointments()
}

// Load appointments for current day (daily view)
async function loadDayAppointments() {
  const start = new Date(currentDate.value)
  start.setHours(0, 0, 0, 0)
  const end = new Date(currentDate.value)
  end.setHours(23, 59, 59, 999)
  await fetchAppointments(start, end)
}

// Handle appointment move in daily view (changes professional)
async function handleDailyAppointmentMove(appointmentId: string, newProfessionalId: string, newStartTime: string, newEndTime: string) {
  const date = formatLocalDate(currentDate.value)

  // Check for overlaps and show warning (with new professional)
  checkAndWarnOverlaps(appointmentId, date, newStartTime, newEndTime, newProfessionalId)

  try {
    await updateAppointment(appointmentId, {
      professional_id: newProfessionalId,
      start_time: `${date}T${newStartTime}:00`,
      end_time: `${date}T${newEndTime}:00`
    })
    toast.add({
      title: t('common.success'),
      description: t('appointments.updated'),
      color: 'success'
    })
    await loadDayAppointments()
  } catch (error: unknown) {
    const fetchError = error as { statusCode?: number }
    if (fetchError.statusCode === 409) {
      toast.add({
        title: t('common.error'),
        description: t('appointments.conflict'),
        color: 'error'
      })
    } else {
      toast.add({
        title: t('common.error'),
        description: t('common.serverError'),
        color: 'error'
      })
    }
    await loadDayAppointments()
  }
}

// Handle appointment resize in daily view
async function handleDailyAppointmentResize(appointmentId: string, newEndTime: string) {
  const date = formatLocalDate(currentDate.value)
  const appointment = appointments.value.find(a => a.id === appointmentId)
  const startTime = appointment?.start_time.split('T')[1]?.substring(0, 5) ?? '00:00'

  // Check for overlaps and show warning
  checkAndWarnOverlaps(appointmentId, date, startTime, newEndTime)

  try {
    await updateAppointment(appointmentId, {
      end_time: `${date}T${newEndTime}:00`
    })
    toast.add({
      title: t('common.success'),
      description: t('appointments.updated'),
      color: 'success'
    })
    await loadDayAppointments()
  } catch (error: unknown) {
    const fetchError = error as { statusCode?: number }
    if (fetchError.statusCode === 409) {
      toast.add({
        title: t('common.error'),
        description: t('appointments.conflict'),
        color: 'error'
      })
    } else {
      toast.add({
        title: t('common.error'),
        description: t('common.serverError'),
        color: 'error'
      })
    }
    await loadDayAppointments()
  }
}

// Check for overlaps and show warning toast
function checkAndWarnOverlaps(
  appointmentId: string,
  newDate: string,
  newStartTime: string,
  newEndTime: string,
  professionalId?: string,
  cabinet?: string
) {
  const appointment = appointments.value.find(a => a.id === appointmentId)
  if (!appointment) return

  const effectiveProfessionalId = professionalId ?? appointment.professional_id
  const effectiveCabinet = cabinet ?? appointment.cabinet

  // Parse times as minutes from midnight
  const startParts = newStartTime.split(':').map(Number)
  const endParts = newEndTime.split(':').map(Number)
  const newStartMinutes = (startParts[0] ?? 0) * 60 + (startParts[1] ?? 0)
  const newEndMinutes = (endParts[0] ?? 0) * 60 + (endParts[1] ?? 0)

  let sameProfessionalCount = 0
  let sameCabinetCount = 0

  for (const apt of appointments.value) {
    if (apt.id === appointmentId) continue
    if (apt.status === 'cancelled') continue

    const aptDate = apt.start_time.split('T')[0]
    if (aptDate !== newDate) continue

    const aptStartTime = apt.start_time.split('T')[1]?.substring(0, 5) ?? '00:00'
    const aptEndTime = apt.end_time.split('T')[1]?.substring(0, 5) ?? '00:00'

    const aptStartParts = aptStartTime.split(':').map(Number)
    const aptEndParts = aptEndTime.split(':').map(Number)
    const aptStartMinutes = (aptStartParts[0] ?? 0) * 60 + (aptStartParts[1] ?? 0)
    const aptEndMinutes = (aptEndParts[0] ?? 0) * 60 + (aptEndParts[1] ?? 0)

    const overlaps = newStartMinutes < aptEndMinutes && newEndMinutes > aptStartMinutes

    if (overlaps) {
      if (apt.professional_id === effectiveProfessionalId) {
        sameProfessionalCount++
      }
      if (apt.cabinet === effectiveCabinet) {
        sameCabinetCount++
      }
    }
  }

  if (sameProfessionalCount > 0 || sameCabinetCount > 0) {
    const warnings: string[] = []
    if (sameProfessionalCount > 0) {
      warnings.push(t('appointments.overlapProfessional', { count: sameProfessionalCount }))
    }
    if (sameCabinetCount > 0) {
      warnings.push(t('appointments.overlapCabinet', { count: sameCabinetCount }))
    }

    toast.add({
      title: t('appointments.overlapWarning'),
      description: warnings.join('. '),
      color: 'warning',
      icon: 'i-lucide-alert-triangle'
    })
  }
}

// Handle appointment click - open modal for edit
function handleAppointmentClick(appointment: Appointment) {
  selectedAppointment.value = appointment
  initialDate.value = undefined
  initialTime.value = undefined
  initialEndTime.value = undefined
  initialProfessionalId.value = undefined
  initialCabinet.value = undefined
  initialPatientId.value = undefined
  isModalOpen.value = true
}

// Handle modal save
async function handleSaved() {
  // Clear initial patient and URL params so it doesn't pre-select on next open
  if (initialPatientId.value) {
    initialPatientId.value = undefined
    router.replace({ query: {} })
  }
  await reloadActiveView()
}

// Handle appointment cancelled
async function handleCancelled() {
  // Clear initial patient and URL params
  if (initialPatientId.value) {
    initialPatientId.value = undefined
    router.replace({ query: {} })
  }
  await reloadActiveView()
}

// Handle appointment move (drag to different day/time)
async function handleAppointmentMove(appointmentId: string, newDate: string, newStartTime: string, newEndTime: string) {
  // Check for overlaps and show warning
  checkAndWarnOverlaps(appointmentId, newDate, newStartTime, newEndTime)

  try {
    await updateAppointment(appointmentId, {
      start_time: `${newDate}T${newStartTime}:00`,
      end_time: `${newDate}T${newEndTime}:00`
    })
    toast.add({
      title: t('common.success'),
      description: t('appointments.updated'),
      color: 'success'
    })
    await loadWeekAppointments()
  } catch (error: unknown) {
    const fetchError = error as { statusCode?: number }
    if (fetchError.statusCode === 409) {
      toast.add({
        title: t('common.error'),
        description: t('appointments.conflict'),
        color: 'error'
      })
    } else {
      toast.add({
        title: t('common.error'),
        description: t('common.serverError'),
        color: 'error'
      })
    }
    await loadWeekAppointments() // Refresh to reset visual state
  }
}

// Handle appointment resize (change duration)
async function handleAppointmentResize(appointmentId: string, newEndTime: string) {
  const appointment = appointments.value.find(a => a.id === appointmentId)
  if (!appointment) return

  const date = appointment.start_time.split('T')[0] ?? ''
  const startTime = appointment.start_time.split('T')[1]?.substring(0, 5) ?? '00:00'

  // Check for overlaps and show warning
  checkAndWarnOverlaps(appointmentId, date, startTime, newEndTime)

  try {
    await updateAppointment(appointmentId, {
      end_time: `${date}T${newEndTime}:00`
    })
    toast.add({
      title: t('common.success'),
      description: t('appointments.updated'),
      color: 'success'
    })
    await loadWeekAppointments()
  } catch (error: unknown) {
    const fetchError = error as { statusCode?: number }
    if (fetchError.statusCode === 409) {
      toast.add({
        title: t('common.error'),
        description: t('appointments.conflict'),
        color: 'error'
      })
    } else {
      toast.add({
        title: t('common.error'),
        description: t('common.serverError'),
        color: 'error'
      })
    }
    await loadWeekAppointments() // Refresh to reset visual state
  }
}

// Open create modal from header button
function openCreateModal() {
  selectedAppointment.value = null
  initialDate.value = viewMode.value === 'day' ? currentDate.value : new Date()
  initialTime.value = '09:00'
  initialEndTime.value = undefined
  initialProfessionalId.value = undefined
  initialCabinet.value = undefined
  // Keep initialPatientId from URL so patient is pre-selected
  isModalOpen.value = true
}

// Watch view mode changes to load appropriate data
watch(viewMode, async (mode) => {
  if (mode === 'week') {
    await loadWeekAppointments()
  } else {
    // Daily + kanban views share the same one-day window.
    await loadDayAppointments()
  }
})

// Load initial data
onMounted(async () => {
  await Promise.all([
    isMobile.value ? loadDayAppointments() : loadWeekAppointments(),
    fetchProfessionals()
  ])
  if (route.query.new === '1') {
    openCreateModal()
    router.replace({ query: { ...route.query, new: undefined } })
  }
})

// Reload on mobile/desktop toggle so we have the right data window
watch(isMobile, async (mobile) => {
  if (mobile) {
    await loadDayAppointments()
  } else if (viewMode.value === 'week') {
    await loadWeekAppointments()
  } else {
    await loadDayAppointments()
  }
})
</script>

<template>
  <div class="h-full flex flex-col w-full min-w-0 overflow-hidden">
    <PageHeader :title="t('appointments.title')">
      <template #actions>
        <SegmentedControl
          v-if="!isMobile"
          :model-value="viewMode"
          :options="[
            { value: 'week', label: t('appointments.weeklyView'), icon: 'i-lucide-calendar-days' },
            { value: 'day', label: t('appointments.dailyView'), icon: 'i-lucide-calendar' },
            { value: 'kanban', label: t('appointments.kanbanView'), icon: 'i-lucide-kanban-square' }
          ]"
          @update:model-value="(v) => (viewMode = v as 'week' | 'day' | 'kanban')"
        />
        <UButton
          v-if="!isMobile"
          color="primary"
          variant="soft"
          icon="i-lucide-plus"
          @click="openCreateModal"
        >
          {{ t('appointments.create') }}
        </UButton>
      </template>
    </PageHeader>

    <!-- Filters (hidden on mobile to save space; mobile uses simple day view) -->
    <div
      v-if="!isMobile"
      class="flex flex-wrap items-center gap-x-6 gap-y-[var(--density-gap,0.75rem)] mb-[var(--density-gap,1rem)] shrink-0"
    >
      <div
        v-if="cabinetFilterOptions.length > 0"
        class="flex items-center gap-2 flex-wrap"
      >
        <span class="text-caption text-subtle">
          {{ t('appointments.cabinet') }}
        </span>
        <FilterChip
          v-for="cabinet in cabinetFilterOptions"
          :key="cabinet.value"
          :label="cabinet.label"
          :color="cabinet.color"
          :selected="selectedCabinets.includes(cabinet.value)"
          @toggle="toggleCabinet(cabinet.value)"
        />
        <UButton
          v-if="selectedCabinets.length < cabinetFilterOptions.length"
          variant="ghost"
          color="neutral"
          size="xs"
          @click="selectAllCabinets"
        >
          {{ t('common.selectAll') }}
        </UButton>
      </div>

      <div
        v-if="professionalFilterOptions.length > 0"
        class="flex items-center gap-2 min-w-0 flex-1"
      >
        <span class="text-caption text-subtle shrink-0">
          {{ t('appointments.professional') }}
        </span>
        <div class="flex items-center gap-2 overflow-x-auto no-scrollbar min-w-0 [&>*]:shrink-0">
          <FilterChip
            v-for="prof in professionalFilterOptions"
            :key="prof.value"
            :label="prof.label"
            :color="prof.color"
            :initials="prof.label.split(' ').map((n: string) => n.charAt(0)).join('').substring(0, 2).toUpperCase()"
            :selected="selectedProfessionals.includes(prof.value)"
            @toggle="toggleProfessional(prof.value)"
          />
        </div>
        <UButton
          v-if="selectedProfessionals.length < professionalFilterOptions.length"
          variant="ghost"
          color="neutral"
          size="xs"
          class="shrink-0"
          @click="selectAllProfessionals"
        >
          {{ t('common.selectAll') }}
        </UButton>
      </div>
    </div>

    <!-- Calendar -->
    <div class="flex-1 min-h-0 min-w-0">
      <!-- Load error — never render a blank calendar that reads as a
           free week (issue #101). The banner replaces the grid until a
           retry succeeds. -->
      <UAlert
        v-if="loadError && !isLoading"
        icon="i-lucide-triangle-alert"
        color="error"
        variant="subtle"
        :title="t('appointments.loadError')"
        :actions="[{
          label: t('common.retry'),
          color: 'error',
          variant: 'soft',
          onClick: () => reloadActiveView()
        }]"
      />

      <!-- Mobile day view (replaces all desktop views on <md) -->
      <AppointmentMobileDayView
        v-else-if="isMobile"
        :appointments="filteredAppointments"
        :professionals="professionalsWithColors"
        :cabinets="clinic.cabinets.value"
        :current-date="currentDate"
        :is-loading="isLoading"
        :highlighted-appointment-id="highlightedAppointmentId"
        @appointment-click="handleAppointmentClick"
        @date-change="handleDateChange"
        @create-at="(d) => { currentDate = d; openCreateModal() }"
        @free-slot-tap="handleFreeSlotTap"
        @highlight-cleared="clearHighlight"
      />

      <!-- Weekly view -->
      <AppointmentCalendar
        v-else-if="viewMode === 'week'"
        :appointments="filteredAppointments"
        :cabinets="clinic.cabinets.value"
        :professionals="professionalsWithColors"
        :current-week-start="currentWeekStart"
        :is-loading="isLoading"
        :highlighted-appointment-id="highlightedAppointmentId"
        @slot-click="handleSlotClick"
        @slot-drag-create="handleSlotDragCreate"
        @appointment-click="handleAppointmentClick"
        @week-change="handleWeekChange"
        @appointment-move="handleAppointmentMove"
        @appointment-resize="handleAppointmentResize"
        @highlight-cleared="clearHighlight"
      />

      <!-- Daily view -->
      <AppointmentDailyView
        v-else-if="viewMode === 'day'"
        :appointments="filteredAppointments"
        :professionals="professionalsWithColors"
        :current-date="currentDate"
        :is-loading="isLoading"
        :highlighted-appointment-id="highlightedAppointmentId"
        @slot-click="handleDailySlotClick"
        @slot-drag-create="handleDailySlotDragCreate"
        @appointment-click="handleAppointmentClick"
        @date-change="handleDateChange"
        @appointment-move="handleDailyAppointmentMove"
        @appointment-resize="handleDailyAppointmentResize"
        @highlight-cleared="clearHighlight"
      />

      <!-- Kanban view -->
      <AppointmentKanbanView
        v-else
        :appointments="filteredAppointments"
        :cabinets="clinic.cabinets.value"
        :professionals="professionalsWithColors"
        :current-date="currentDate"
        :is-loading="isLoading"
        @appointment-click="handleAppointmentClick"
        @date-change="handleDateChange"
        @professional-filter="handleProfessionalFilter"
      />
    </div>

    <!-- Appointment Modal -->
    <AppointmentModal
      v-model:open="isModalOpen"
      :appointment="selectedAppointment"
      :initial-date="initialDate"
      :initial-time="initialTime"
      :initial-end-time="initialEndTime"
      :initial-professional-id="initialProfessionalId"
      :initial-cabinet="initialCabinet"
      :initial-patient-id="initialPatientId"
      :initial-plan-id="initialPlanId"
      :existing-appointments="appointments"
      @saved="handleSaved"
      @cancelled="handleCancelled"
    />

    <!-- Renders the post-completion follow-up modal once for the
         whole agenda page. Triggered by `useCompletionFollowup()`
         from QuickActions and Kanban after a `completed` transition. -->
    <CompletionFollowupHost />
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
