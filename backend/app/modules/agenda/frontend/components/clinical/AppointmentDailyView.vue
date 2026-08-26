<script setup lang="ts">
import type { Appointment, Professional } from '~~/app/types'
import type { BlockedSegment } from '../../composables/useBlockedSegments'
import { calculateOverlapGroups } from '../../composables/calculateOverlapGroups'
import { formatLocalDate } from '../../utils/date'

const notesIndicator = useAppointmentNotesIndicator()

interface ProfessionalWithColor extends Professional {
  color: string
}

const props = defineProps<{
  appointments: Appointment[]
  professionals: ProfessionalWithColor[]
  currentDate: Date
  isLoading?: boolean
  highlightedAppointmentId?: string | null
}>()

const emit = defineEmits<{
  'slot-click': [professionalId: string, time: string]
  'slot-drag-create': [professionalId: string, startTime: string, endTime: string]
  'appointment-click': [appointment: Appointment]
  'date-change': [date: Date]
  'appointment-move': [appointmentId: string, newProfessionalId: string, newStartTime: string, newEndTime: string]
  'appointment-resize': [appointmentId: string, newEndTime: string]
  'highlight-cleared': []
}>()

// Clear highlight after animation completes (5 seconds)
watch(() => props.highlightedAppointmentId, (newId) => {
  if (newId) {
    setTimeout(() => {
      emit('highlight-cleared')
    }, 5000)
  }
}, { immediate: true })

const { t, locale } = useI18n()

// Time slots configuration. Narrowed to actual clinic hours via
// schedules module; 8–21 fallback when that module is uninstalled.
const startHour = ref(8)
const endHour = ref(21)
const SLOT_MINUTES = 15
const SLOTS_PER_HOUR = 60 / SLOT_MINUTES

const { compute: computeCalendarBounds } = useCalendarBounds()
const { compute: computeBlockedSegments } = useBlockedSegments({
  startHour,
  endHour,
  slotMinutes: SLOT_MINUTES
})

const blockedSegments = ref<BlockedSegment[]>([])

async function refreshAvailability() {
  const bounds = await computeCalendarBounds({ start: props.currentDate, end: props.currentDate })
  startHour.value = bounds.startHour
  endHour.value = bounds.endHour

  blockedSegments.value = await computeBlockedSegments({
    start: props.currentDate,
    end: props.currentDate,
    professionals: props.professionals
  })
}

watch(
  () => [props.currentDate, props.professionals.map(p => p.id).join(',')],
  () => { void refreshAvailability() },
  { immediate: true }
)

const { density: _calendarDensity } = useDensity()
function getSlotHeight() {
  return _calendarDensity.value === 'compact' ? 18 : 28
}

// Drag state
const dragState = ref<{
  type: 'move' | 'resize' | null
  appointmentId: string | null
  startY: number
  startX: number
  originalTop: number
  originalHeight: number
  originalProfessionalIndex: number
  currentProfessionalIndex: number
  currentTop: number
  currentHeight: number
} | null>(null)

// Create drag state (drag on empty slot to define duration)
const createDragState = ref<{
  professionalId: string
  professionalIndex: number
  startSlot: number
  currentSlot: number
  startY: number
} | null>(null)

const calendarRef = ref<HTMLElement | null>(null)
const wasDragging = ref(false)
const hasMoved = ref(false)

onUnmounted(() => {
  document.removeEventListener('mousemove', handleDragMove)
  document.removeEventListener('mouseup', handleDragEnd)
})

// Generate time slots
const timeSlots = computed(() => {
  const slots: string[] = []
  for (let hour = startHour.value; hour < endHour.value; hour++) {
    for (let quarter = 0; quarter < SLOTS_PER_HOUR; quarter++) {
      const minutes = quarter * SLOT_MINUTES
      slots.push(`${hour.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`)
    }
  }
  return slots
})

// Format date for header
const formattedDate = computed(() => {
  return props.currentDate.toLocaleDateString(locale.value, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
})

// Check if current date is today
const isToday = computed(() => {
  const today = new Date()
  return props.currentDate.toDateString() === today.toDateString()
})

// Navigate days
function prevDay() {
  const newDate = new Date(props.currentDate)
  newDate.setDate(newDate.getDate() - 1)
  emit('date-change', newDate)
}

function nextDay() {
  const newDate = new Date(props.currentDate)
  newDate.setDate(newDate.getDate() + 1)
  emit('date-change', newDate)
}

function goToToday() {
  emit('date-change', new Date())
}

// Calculate slot index from time string
function getSlotIndex(timeStr: string): number {
  const parts = timeStr.split(':').map(Number)
  const hours = parts[0] ?? 0
  const minutes = parts[1] ?? 0
  return (hours - startHour.value) * SLOTS_PER_HOUR + Math.floor(minutes / SLOT_MINUTES)
}

function slotIndexToTime(slotIndex: number): string {
  const totalMinutes = startHour.value * 60 + slotIndex * SLOT_MINUTES
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`
}

// Get appointment style
function getAppointmentStyle(appointment: Appointment): Record<string, string> {
  if (dragState.value?.appointmentId === appointment.id) {
    return {
      top: `${dragState.value.currentTop}px`,
      height: `${dragState.value.currentHeight}px`,
      minHeight: `${getSlotHeight()}px`,
      opacity: '0.8',
      zIndex: '50'
    }
  }

  const startTime = appointment.start_time.split('T')[1]?.substring(0, 5) ?? '08:00'
  const endTime = appointment.end_time.split('T')[1]?.substring(0, 5) ?? '08:15'

  const startSlot = getSlotIndex(startTime)
  const endSlot = getSlotIndex(endTime)
  const spanSlots = Math.max(1, endSlot - startSlot)

  const height = spanSlots * getSlotHeight()
  const topOffset = startSlot * getSlotHeight()

  return {
    top: `${topOffset}px`,
    height: `${height}px`,
    minHeight: `${getSlotHeight()}px`
  }
}

// Tint + rail for an appointment block (DESIGN §7.3): fill alpha 0.12, left border 3 px.
function getProfessionalFill(hex: string): Record<string, string> {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return {
    backgroundColor: `rgba(${r}, ${g}, ${b}, 0.12)`,
    borderLeftColor: hex,
    borderLeftWidth: '3px'
  }
}

// Status styling — fill tinted from professional colour (inline), status modulates text/opacity.
function getStatusClass(status: Appointment['status']): string {
  const baseClass = 'bg-surface ring-1 ring-[var(--color-border)]'
  switch (status) {
    case 'scheduled':
    case 'confirmed':
      return `${baseClass} text-default`
    case 'checked_in':
    case 'in_treatment':
      return `${baseClass} text-default`
    case 'completed':
      return `${baseClass} text-muted opacity-70`
    case 'cancelled':
      return `${baseClass} text-subtle line-through opacity-50`
    case 'no_show':
      return `${baseClass} text-subtle opacity-60`
    default:
      return baseClass
  }
}

function getStatusIcon(status: Appointment['status']): string {
  switch (status) {
    case 'confirmed': return 'i-lucide-check'
    case 'checked_in': return 'i-lucide-door-open'
    case 'in_treatment': return 'i-lucide-stethoscope'
    case 'completed': return 'i-lucide-check-check'
    case 'cancelled': return 'i-lucide-x'
    case 'no_show': return 'i-lucide-user-x'
    default: return ''
  }
}

// Handle drag-to-create on empty slot
function startCreateDrag(professionalId: string, timeSlot: string, profIndex: number, event: MouseEvent) {
  if (dragState.value) return
  event.preventDefault()

  const startSlot = getSlotIndex(timeSlot)
  createDragState.value = {
    professionalId,
    professionalIndex: profIndex,
    startSlot,
    currentSlot: startSlot,
    startY: event.clientY
  }

  document.addEventListener('mousemove', handleDragMove)
  document.addEventListener('mouseup', handleDragEnd)
}

// Handle appointment click
function handleAppointmentClick(appointment: Appointment, event: Event) {
  if (dragState.value || wasDragging.value) return
  event.stopPropagation()
  emit('appointment-click', appointment)
}

// Drag handlers
function startDrag(appointment: Appointment, event: MouseEvent, type: 'move' | 'resize') {
  event.preventDefault()
  event.stopPropagation()

  const startTime = appointment.start_time.split('T')[1]?.substring(0, 5) ?? '08:00'
  const endTime = appointment.end_time.split('T')[1]?.substring(0, 5) ?? '08:15'
  const startSlot = getSlotIndex(startTime)
  const endSlot = getSlotIndex(endTime)
  const professionalIndex = props.professionals.findIndex(p => p.id === appointment.professional_id)

  dragState.value = {
    type,
    appointmentId: appointment.id,
    startY: event.clientY,
    startX: event.clientX,
    originalTop: startSlot * getSlotHeight(),
    originalHeight: Math.max(1, endSlot - startSlot) * getSlotHeight(),
    originalProfessionalIndex: professionalIndex,
    currentProfessionalIndex: professionalIndex,
    currentTop: startSlot * getSlotHeight(),
    currentHeight: Math.max(1, endSlot - startSlot) * getSlotHeight()
  }

  document.addEventListener('mousemove', handleDragMove)
  document.addEventListener('mouseup', handleDragEnd)
}

function handleDragMove(event: MouseEvent) {
  if (createDragState.value) {
    const deltaY = event.clientY - createDragState.value.startY
    const slotDelta = Math.floor(deltaY / getSlotHeight())
    const maxSlot = (endHour.value - startHour.value) * SLOTS_PER_HOUR - 1
    createDragState.value.currentSlot = Math.max(
      createDragState.value.startSlot,
      Math.min(maxSlot, createDragState.value.startSlot + slotDelta)
    )
    return
  }

  if (!dragState.value) return

  const deltaY = event.clientY - dragState.value.startY
  const deltaX = event.clientX - dragState.value.startX

  if (Math.abs(deltaY) > 5 || Math.abs(deltaX) > 5) {
    hasMoved.value = true
  }

  if (dragState.value.type === 'resize') {
    const newHeight = Math.max(getSlotHeight(), dragState.value.originalHeight + deltaY)
    const slots = Math.round(newHeight / getSlotHeight())
    dragState.value.currentHeight = slots * getSlotHeight()
  } else if (dragState.value.type === 'move') {
    const newTop = Math.max(0, dragState.value.originalTop + deltaY)
    const slots = Math.round(newTop / getSlotHeight())
    const maxSlots = (endHour.value - startHour.value) * SLOTS_PER_HOUR - Math.round(dragState.value.currentHeight / getSlotHeight())
    dragState.value.currentTop = Math.min(slots, maxSlots) * getSlotHeight()

    // Calculate professional change
    if (calendarRef.value && props.professionals.length > 1) {
      const calendarWidth = calendarRef.value.offsetWidth
      const columnWidth = calendarWidth / (props.professionals.length + 1) // +1 for time column
      const profDelta = Math.round(deltaX / columnWidth)
      const newProfIndex = Math.max(0, Math.min(props.professionals.length - 1, dragState.value.originalProfessionalIndex + profDelta))
      dragState.value.currentProfessionalIndex = newProfIndex
    }
  }
}

function handleDragEnd() {
  document.removeEventListener('mousemove', handleDragMove)
  document.removeEventListener('mouseup', handleDragEnd)

  if (createDragState.value) {
    const { professionalId, startSlot, currentSlot } = createDragState.value
    createDragState.value = null
    const startTime = slotIndexToTime(startSlot)
    if (currentSlot > startSlot) {
      emit('slot-drag-create', professionalId, startTime, slotIndexToTime(currentSlot + 1))
    } else {
      emit('slot-click', professionalId, startTime)
    }
    return
  }

  if (hasMoved.value) {
    wasDragging.value = true
    setTimeout(() => {
      wasDragging.value = false
    }, 100)
  }
  hasMoved.value = false

  if (!dragState.value || !dragState.value.appointmentId) {
    dragState.value = null
    return
  }

  const appointment = props.appointments.find(a => a.id === dragState.value?.appointmentId)
  if (!appointment) {
    dragState.value = null
    return
  }

  if (dragState.value.type === 'resize') {
    const startTime = appointment.start_time.split('T')[1]?.substring(0, 5) ?? '08:00'
    const startSlot = getSlotIndex(startTime)
    const newEndSlot = startSlot + Math.round(dragState.value.currentHeight / getSlotHeight())
    const newEndTime = slotIndexToTime(newEndSlot)

    const oldEndTime = appointment.end_time.split('T')[1]?.substring(0, 5) ?? ''
    if (newEndTime !== oldEndTime) {
      emit('appointment-resize', dragState.value.appointmentId, newEndTime)
    }
  } else if (dragState.value.type === 'move') {
    const newStartSlot = Math.round(dragState.value.currentTop / getSlotHeight())
    const durationSlots = Math.round(dragState.value.currentHeight / getSlotHeight())
    const newEndSlot = newStartSlot + durationSlots

    const newStartTime = slotIndexToTime(newStartSlot)
    const newEndTime = slotIndexToTime(newEndSlot)
    const newProfessional = props.professionals[dragState.value.currentProfessionalIndex]

    const oldStartTime = appointment.start_time.split('T')[1]?.substring(0, 5) ?? ''
    const oldProfessionalId = appointment.professional_id

    if (newProfessional && (newStartTime !== oldStartTime || newProfessional.id !== oldProfessionalId)) {
      emit('appointment-move', dragState.value.appointmentId, newProfessional.id, newStartTime, newEndTime)
    }
  }

  dragState.value = null
}

// Pre-bucket the current day's appointments by professional id. One pass over
// props.appointments instead of N (one per professional column).
const appointmentsByProfId = computed(() => {
  const dateStr = formatLocalDate(props.currentDate)
  const map = new Map<string, Appointment[]>()
  for (const apt of props.appointments) {
    if (apt.status === 'cancelled') continue
    if (apt.start_time.split('T')[0] !== dateStr) continue
    const profId = apt.professional_id
    if (!profId) continue
    let bucket = map.get(profId)
    if (!bucket) {
      bucket = []
      map.set(profId, bucket)
    }
    bucket.push(apt)
  }
  return map
})

// Per-id overlap position {index,total}. Independent of drag state so it does
// not recompute on every mousemove.
const overlapPositions = computed(() => {
  const positions = new Map<string, { index: number, total: number }>()
  for (const bucket of appointmentsByProfId.value.values()) {
    const profPositions = calculateOverlapGroups(bucket)
    profPositions.forEach((pos, id) => positions.set(id, pos))
  }
  return positions
})

function getOverlapStyle(appointment: Appointment): Record<string, string> {
  const pos = overlapPositions.value.get(appointment.id)
  if (!pos || pos.total <= 1) {
    return { left: '2px', right: '2px' }
  }
  const widthPercent = 100 / pos.total
  const leftPercent = pos.index * widthPercent
  return {
    left: `calc(${leftPercent}% + 1px)`,
    width: `calc(${widthPercent}% - 2px)`,
    right: 'auto'
  }
}

// Day's appointments keyed by the column index the template iterates. Splits
// the dragged appointment into its current column so the template still finds
// it; no per-column .filter() in the v-for.
const appointmentsByProfIndex = computed(() => {
  const map = new Map<number, Appointment[]>()
  const dragId = dragState.value?.appointmentId
  const dragType = dragState.value?.type
  const dragProfIdx = dragState.value?.currentProfessionalIndex
  for (let i = 0; i < props.professionals.length; i++) {
    const profId = props.professionals[i]!.id
    map.set(i, appointmentsByProfId.value.get(profId)?.slice() ?? [])
  }
  if (dragId && dragType === 'move' && typeof dragProfIdx === 'number') {
    const dragged = props.appointments.find(a => a.id === dragId)
    if (dragged) {
      const originalIdx = props.professionals.findIndex(p => p.id === dragged.professional_id)
      if (originalIdx !== dragProfIdx) {
        const fromBucket = map.get(originalIdx)
        if (fromBucket) {
          const idx = fromBucket.findIndex(a => a.id === dragId)
          if (idx >= 0) fromBucket.splice(idx, 1)
        }
        const toBucket = map.get(dragProfIdx)
        if (toBucket) toBucket.push(dragged)
      }
    }
  }
  return map
})
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4 flex-shrink-0">
      <div class="flex items-center gap-2">
        <UButton
          variant="outline"
          color="neutral"
          icon="i-lucide-chevron-left"
          :aria-label="t('common.previous')"
          @click="prevDay"
        />
        <UButton
          variant="outline"
          color="neutral"
          @click="goToToday"
        >
          {{ t('appointments.today') }}
        </UButton>
        <UButton
          variant="outline"
          color="neutral"
          icon="i-lucide-chevron-right"
          :aria-label="t('common.next')"
          @click="nextDay"
        />
      </div>

      <h2
        class="text-h2 capitalize"
        :class="isToday ? 'text-[var(--color-primary-soft-text)]' : 'text-default'"
      >
        {{ formattedDate }}
      </h2>
    </div>

    <!-- Loading -->
    <div
      v-if="isLoading"
      class="flex items-center justify-center py-12"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="w-8 h-8 animate-spin"
        :style="{ color: 'var(--color-primary)' }"
      />
    </div>

    <!-- No professionals message -->
    <div
      v-else-if="professionals.length === 0"
      class="flex items-center justify-center py-12 text-muted"
    >
      {{ t('appointments.noProfessionals') }}
    </div>

    <!-- Calendar grid -->
    <div
      v-else
      ref="calendarRef"
      class="flex-1 overflow-auto ring-1 ring-[var(--color-border)] rounded-token-lg"
    >
      <div
        class="min-w-[600px]"
        :style="{ minWidth: `${200 * professionals.length + 80}px` }"
      >
        <!-- Professional headers -->
        <div
          class="grid border-b border-default bg-surface-muted sticky top-0 z-10"
          :style="{ gridTemplateColumns: `80px repeat(${professionals.length}, 1fr)` }"
        >
          <div class="p-2 text-center text-caption text-subtle border-r border-subtle" />
          <div
            v-for="prof in professionals"
            :key="prof.id"
            class="p-2 text-center border-r border-subtle last:border-r-0"
          >
            <div class="flex items-center justify-center gap-2">
              <span
                class="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-semibold"
                :style="{ backgroundColor: prof.color }"
              >
                {{ prof.first_name.charAt(0) }}{{ prof.last_name.charAt(0) }}
              </span>
              <span class="text-ui text-default">
                {{ prof.first_name }} {{ prof.last_name }}
              </span>
            </div>
          </div>
        </div>

        <!-- Time rows -->
        <div class="relative">
          <div
            v-for="(slot, slotIndex) in timeSlots"
            :key="slot"
            class="grid border-b border-[var(--color-border-subtle)] h-[var(--density-slot-height,28px)]"
            :class="{ 'border-[var(--color-border)]': slotIndex % SLOTS_PER_HOUR === 0 }"
            :style="{ gridTemplateColumns: `80px repeat(${professionals.length}, 1fr)` }"
          >
            <div class="p-1 text-right border-r border-subtle flex items-center justify-end pr-2">
              <span
                v-if="slotIndex % SLOTS_PER_HOUR === 0"
                class="text-caption text-subtle tnum"
              >
                {{ slot }}
              </span>
            </div>
            <div
              v-for="(prof, profIdx) in professionals"
              :key="`${prof.id}-${slot}`"
              class="border-r border-[var(--color-border-subtle)] last:border-r-0 cursor-cell hover:bg-[var(--color-primary-soft)]/50 transition-colors relative"
              :class="{ 'border-[var(--color-border)]': slotIndex % SLOTS_PER_HOUR === 0 }"
              @mousedown="startCreateDrag(prof.id, slot, profIdx, $event)"
            />
          </div>

          <!-- Appointments overlay -->
          <div class="absolute inset-0 pointer-events-none">
            <div
              class="grid h-full"
              :style="{ gridTemplateColumns: `80px repeat(${professionals.length}, 1fr)` }"
            >
              <div class="border-r border-subtle" />

              <!-- Professional columns -->
              <div
                v-for="(prof, profIndex) in professionals"
                :key="`appointments-${prof.id}`"
                class="relative border-r border-subtle last:border-r-0"
              >
                <!-- Blocked availability overlay (schedules module) -->
                <div
                  v-for="(seg, segIdx) in blockedSegments.filter(s => s.professionalId === prof.id)"
                  :key="`blocked-${prof.id}-${segIdx}`"
                  class="absolute inset-x-0 pointer-events-none z-10 schedules-blocked"
                  :title="seg.reason || (seg.state === 'clinic_closed' ? 'Clínica cerrada' : 'No disponible')"
                  :style="{
                    top: `${seg.startSlot * getSlotHeight()}px`,
                    height: `${(seg.endSlot - seg.startSlot) * getSlotHeight()}px`
                  }"
                />

                <!-- Ghost block during drag-to-create -->
                <div
                  v-if="createDragState && createDragState.professionalIndex === profIndex"
                  class="absolute left-1 right-1 rounded border-2 border-dashed border-[var(--color-primary)] bg-[var(--color-primary-soft)] pointer-events-none z-40 flex items-start p-1"
                  :style="{
                    top: `${createDragState.startSlot * getSlotHeight()}px`,
                    height: `${Math.max(1, createDragState.currentSlot - createDragState.startSlot + 1) * getSlotHeight()}px`,
                    minHeight: `${getSlotHeight()}px`
                  }"
                >
                  <span
                    v-if="createDragState.currentSlot > createDragState.startSlot"
                    class="text-xs text-primary-700 dark:text-primary-300 font-medium leading-none"
                  >
                    {{ slotIndexToTime(createDragState.startSlot) }} – {{ slotIndexToTime(createDragState.currentSlot + 1) }}
                  </span>
                </div>

                <div
                  v-for="appointment in (appointmentsByProfIndex.get(profIndex) ?? [])"
                  :key="appointment.id"
                  class="group absolute rounded overflow-hidden pointer-events-auto select-none shadow-sm border-l-4"
                  :class="[
                    getStatusClass(appointment.status),
                    dragState?.appointmentId === appointment.id ? 'cursor-grabbing ring-2 ring-primary-500' : 'cursor-grab hover:ring-2 hover:ring-primary-500',
                    highlightedAppointmentId === appointment.id ? 'ring-4 ring-warning-500 animate-pulse z-50' : ''
                  ]"
                  :style="{
                    ...getAppointmentStyle(appointment),
                    ...getOverlapStyle(appointment),
                    ...getProfessionalFill(prof.color)
                  }"
                  @click="handleAppointmentClick(appointment, $event)"
                  @mousedown="startDrag(appointment, $event, 'move')"
                >
                  <!-- Content -->
                  <div class="px-1.5 h-full flex flex-col py-0.5 relative">
                    <!-- Quick-action dropdown (shown on hover) -->
                    <div
                      class="absolute top-0.5 right-0.5 opacity-0 group-hover:opacity-100 transition-opacity z-20"
                      @click.stop
                      @mousedown.stop
                    >
                      <AppointmentQuickActions
                        :appointment="appointment"
                        dense
                      />
                    </div>
                    <div class="flex items-center gap-1 min-h-[18px] pr-6">
                      <UIcon
                        v-if="getStatusIcon(appointment.status)"
                        :name="getStatusIcon(appointment.status)"
                        class="w-3 h-3 flex-shrink-0"
                      />
                      <span class="text-xs font-medium truncate">
                        {{ appointment.patient ? `${appointment.patient.first_name} ${appointment.patient.last_name}` : 'Sin paciente' }}
                      </span>
                      <UIcon
                        v-if="notesIndicator.has(appointment.id)"
                        name="i-lucide-sticky-note"
                        class="w-3 h-3 flex-shrink-0 text-primary"
                        :title="t('appointments.hasNotes', 'Tiene notas')"
                      />
                    </div>
                    <div
                      v-if="appointment.treatment_type"
                      class="text-xs opacity-60 truncate"
                    >
                      {{ appointment.treatment_type }}
                    </div>
                  </div>

                  <!-- Resize handle -->
                  <div
                    class="absolute bottom-0 left-0 right-0 h-2 cursor-ns-resize hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
                    @mousedown.stop="startDrag(appointment, $event, 'resize')"
                  >
                    <div class="absolute bottom-0.5 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-current opacity-30 rounded" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.schedules-blocked {
  background-image: repeating-linear-gradient(
    45deg,
    rgba(148, 163, 184, 0.18),
    rgba(148, 163, 184, 0.18) 6px,
    rgba(148, 163, 184, 0.32) 6px,
    rgba(148, 163, 184, 0.32) 12px
  );
}
</style>
