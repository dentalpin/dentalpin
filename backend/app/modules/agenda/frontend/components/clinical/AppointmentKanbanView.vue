<script setup lang="ts">
import type { Appointment, AppointmentStatus } from '~~/app/types'
import { errorDetail } from '~~/app/utils/error'

interface Cabinet {
  id?: string
  name: string
  color: string
}

interface ProfessionalWithColor {
  id: string
  first_name: string
  last_name: string
  color: string
}

const props = defineProps<{
  appointments: Appointment[]
  cabinets: Cabinet[]
  professionals: ProfessionalWithColor[]
  currentDate: Date
  isLoading?: boolean
}>()

const emit = defineEmits<{
  'appointment-click': [appointment: Appointment]
  'date-change': [date: Date]
  'professional-filter': [professionalId: string | null]
}>()

const { t, locale } = useI18n()
const toast = useToast()
const { fetchAppointments, transition, assignCabinet } = useAppointments()
const completionFollowup = useCompletionFollowup()
const { canTransition, statusColour, statusLabel } = useAppointmentStatus()
// Manual 30-second tick — @vueuse/core is not a dependency in this repo.
const now = ref(new Date())

// Professional pill filter: click a pill to focus the board on one pro;
// click the same pill again to clear. Single-select (not multi) to keep
// the strip unambiguous.
const pillFilteredId = ref<string | null>(null)
const stripRef = ref<{ refresh?: () => Promise<void> } | null>(null)

function onPillClick(professionalId: string) {
  pillFilteredId.value = pillFilteredId.value === professionalId
    ? null
    : professionalId
  emit('professional-filter', pillFilteredId.value)
}

// Columns: 5 operational buckets, not 7 per-status columns. Grouping
// sched+confirmed and no_show+cancelled keeps the board readable on a
// regular-width screen.
interface ColumnDef {
  id: 'upcoming' | 'waiting' | 'in_chair' | 'done' | 'missed'
  labelKey: string
  icon: string
  statuses: AppointmentStatus[]
  dropPrimary: AppointmentStatus
  dropAlternatives?: AppointmentStatus[]
  collapsedByDefault?: boolean
}

const COLUMNS: readonly ColumnDef[] = [
  {
    id: 'upcoming',
    labelKey: 'appointments.kanban.upcoming',
    icon: 'i-lucide-calendar',
    statuses: ['scheduled', 'confirmed'],
    dropPrimary: 'scheduled'
  },
  {
    id: 'waiting',
    labelKey: 'appointments.kanban.waiting',
    icon: 'i-lucide-armchair',
    statuses: ['checked_in'],
    dropPrimary: 'checked_in'
  },
  {
    id: 'in_chair',
    labelKey: 'appointments.kanban.inChair',
    icon: 'i-lucide-stethoscope',
    statuses: ['in_treatment'],
    dropPrimary: 'in_treatment'
  },
  {
    id: 'done',
    labelKey: 'appointments.kanban.done',
    icon: 'i-lucide-check-check',
    statuses: ['completed'],
    dropPrimary: 'completed',
    collapsedByDefault: true
  },
  {
    id: 'missed',
    labelKey: 'appointments.kanban.missed',
    icon: 'i-lucide-user-x',
    statuses: ['no_show', 'cancelled'],
    dropPrimary: 'no_show',
    dropAlternatives: ['cancelled'],
    collapsedByDefault: true
  }
]

const collapsedColumns = ref<Set<string>>(
  new Set(COLUMNS.filter(c => c.collapsedByDefault).map(c => c.id))
)

function toggleCollapsed(id: string) {
  const next = new Set(collapsedColumns.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  collapsedColumns.value = next
}

// Only keep appointments for the currently selected day. Uses local-date
// comparison so timezone shifts don't lose edge-case cards.
function isSameDay(iso: string, target: Date): boolean {
  const d = new Date(iso)
  return (
    d.getFullYear() === target.getFullYear()
    && d.getMonth() === target.getMonth()
    && d.getDate() === target.getDate()
  )
}

const dayAppointments = computed(() =>
  props.appointments.filter(apt => isSameDay(apt.start_time, props.currentDate))
)

function appointmentsForColumn(col: ColumnDef): Appointment[] {
  const list = dayAppointments.value.filter(a => col.statuses.includes(a.status))
  if (col.id === 'waiting') {
    // Longest-waiting first — most urgent in the chair.
    return [...list].sort((a, b) =>
      new Date(a.current_status_since).getTime()
      - new Date(b.current_status_since).getTime()
    )
  }
  if (col.id === 'done') {
    return [...list].sort((a, b) =>
      new Date(b.current_status_since).getTime()
      - new Date(a.current_status_since).getTime()
    )
  }
  return [...list].sort((a, b) =>
    new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
  )
}

// Cabinet sub-grouping inside "in chair" — answers "which cabinets are
// occupied right now?" at a glance. Each cabinet block shows either the
// patient card or a "Libre" placeholder. The computed ``state`` drives
// the accent colour: green (free + active), blue (in use), gray
// (inactive).
type CabinetState = 'free' | 'in_use' | 'inactive'

const inChairByCabinet = computed(() => {
  const grouped = new Map<string, Appointment | null>()
  for (const c of props.cabinets) {
    grouped.set(c.name, null)
  }
  for (const apt of dayAppointments.value) {
    if (apt.status === 'in_treatment' && apt.cabinet) {
      grouped.set(apt.cabinet, apt)
    }
  }
  return Array.from(grouped.entries()).map(([cabName, apt]) => {
    const cabinet = props.cabinets.find(c => c.name === cabName) ?? {
      name: cabName,
      color: '#6B7280'
    }
    const isActive = (cabinet as { is_active?: boolean }).is_active !== false
    const state: CabinetState = !isActive
      ? 'inactive'
      : apt !== null
        ? 'in_use'
        : 'free'
    return { cabinet, appointment: apt, state }
  })
})

const CABINET_STATE_ACCENT: Record<CabinetState, string> = {
  free: '#22C55E',
  in_use: '#2563EB',
  inactive: '#9CA3AF'
}

// Next upcoming appointment per cabinet (to show when the cabinet is free).
function nextForCabinet(cabinetName: string): Appointment | null {
  const later = dayAppointments.value
    .filter(a => a.cabinet === cabinetName && ['scheduled', 'confirmed'].includes(a.status))
    .sort((a, b) =>
      new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    )
  return later[0] ?? null
}

// ---------------------------------------------------------------------
// Drag-and-drop (HTML5). Re-uses the "snap-to-column" pattern from the
// daily view but applies it to status columns (and cabinet sub-buckets
// inside the "in chair" column).
// ---------------------------------------------------------------------
interface DragState {
  appointmentId: string
  targetColumnId: string | null
  targetCabinetName: string | null
}
const drag = ref<DragState | null>(null)

function onDragStart(apt: Appointment, e: DragEvent) {
  drag.value = {
    appointmentId: apt.id,
    targetColumnId: null,
    targetCabinetName: null
  }
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', apt.id)
  }
}

function onDragEnd() {
  drag.value = null
}

function onDragOverColumn(col: ColumnDef, e: DragEvent, cabinetName?: string) {
  if (!drag.value) return
  const apt = props.appointments.find(a => a.id === drag.value!.appointmentId)
  if (!apt) return
  if (!canDropOn(apt, col)) return
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  drag.value = {
    ...drag.value,
    targetColumnId: col.id,
    targetCabinetName: cabinetName ?? null
  }
}

function onDragLeaveColumn(col: ColumnDef) {
  if (drag.value?.targetColumnId === col.id) {
    drag.value = { ...drag.value, targetColumnId: null, targetCabinetName: null }
  }
}

function canDropOn(apt: Appointment, col: ColumnDef): boolean {
  if (col.statuses.includes(apt.status)) {
    // Moving inside the same column does nothing unless it's a cabinet
    // change inside "in chair".
    return col.id === 'in_chair'
  }
  const targets: AppointmentStatus[] = [col.dropPrimary, ...(col.dropAlternatives ?? [])]
  return targets.some(t => canTransition(apt.status, t))
}

function cabinetIdByName(name: string): string | null {
  return props.cabinets.find(c => c.name === name)?.id ?? null
}

async function onDrop(col: ColumnDef, e: DragEvent, cabinetName?: string) {
  e.preventDefault()
  if (!drag.value) return
  const aptId = drag.value.appointmentId
  const apt = props.appointments.find(a => a.id === aptId)
  drag.value = null
  if (!apt) return

  // Case A: moving within "in chair" — the patient is already being
  // treated, we're just physically moving them to another cabinet.
  if (col.id === 'in_chair' && col.statuses.includes(apt.status)) {
    if (cabinetName && cabinetName !== apt.cabinet) {
      const cabId = cabinetIdByName(cabinetName)
      if (cabId) await safeAssign(aptId, cabId)
    }
    return
  }

  // Case B: transition to another column.
  const target = [col.dropPrimary, ...(col.dropAlternatives ?? [])].find(t =>
    canTransition(apt.status, t)
  )
  if (!target) return

  try {
    // When dropping on a specific cabinet inside "in chair", assign the
    // cabinet FIRST and then transition — the transition to in_treatment
    // requires a cabinet (backend rule from #51). If the second step
    // fails we leave the cabinet assignment in place per the product
    // decision: less confusing than an auto-unassign rollback.
    if (col.id === 'in_chair' && cabinetName && cabinetName !== apt.cabinet) {
      const cabId = cabinetIdByName(cabinetName)
      if (cabId) await safeAssign(aptId, cabId)
    }
    await transition(aptId, target)
    if (target === 'completed') {
      completionFollowup.trigger(apt)
    }
  } catch (e) {
    toast.add({ title: t('appointments.transitionFailed'), description: errorDetail(e), color: 'error' })
  }
}

async function safeAssign(aptId: string, cabinetId: string | null) {
  try {
    await assignCabinet(aptId, cabinetId)
  } catch (e) {
    toast.add({ title: t('appointments.conflict'), description: errorDetail(e), color: 'error' })
    throw new Error('cabinet_assign_failed')
  }
}

// ---------------------------------------------------------------------
// Live refresh. Polling is suspended when the tab is hidden — no point
// hammering the API when nobody's looking. Comes back instantly on focus.
// ---------------------------------------------------------------------
const POLL_INTERVAL_MS = 30_000
let pollTimer: ReturnType<typeof setInterval> | null = null
let tickTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    if (document.visibilityState === 'visible') {
      void refreshDay()
    }
  }, POLL_INTERVAL_MS)
  // Re-evaluate column subtitles ("waiting 12 min") without refetching.
  tickTimer = setInterval(() => {
    now.value = new Date()
  }, 30_000)
}
function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (tickTimer !== null) {
    clearInterval(tickTimer)
    tickTimer = null
  }
}
async function refreshDay() {
  const start = new Date(props.currentDate); start.setHours(0, 0, 0, 0)
  const end = new Date(props.currentDate); end.setHours(23, 59, 59, 999)
  await fetchAppointments(start, end)
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible') void refreshDay()
}

onMounted(() => {
  startPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
})
onBeforeUnmount(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

// ---------------------------------------------------------------------
// Column header counters. Show what the user cares about operationally
// at a glance: how many are waiting, average wait time, cabinets free.
// ---------------------------------------------------------------------
function avgWaitMinutes(): number | null {
  const waiting = appointmentsForColumn(COLUMNS[1]!)
  if (waiting.length === 0) return null
  const total = waiting.reduce((acc, apt) => {
    return acc + (now.value.getTime() - new Date(apt.current_status_since).getTime())
  }, 0)
  return Math.round(total / waiting.length / 60_000)
}

function cabinetsFreeCount(): number {
  return inChairByCabinet.value.filter(x => x.appointment === null).length
}

function cabinetsBusyCount(): number {
  return inChairByCabinet.value.filter(x => x.appointment !== null).length
}

function headerSubtitle(col: ColumnDef): string {
  const items = appointmentsForColumn(col)
  if (col.id === 'waiting') {
    const avg = avgWaitMinutes()
    if (avg === null) return t('appointments.kanban.subtitleEmpty')
    return t('appointments.kanban.subtitleWaiting', { count: items.length, avg })
  }
  if (col.id === 'in_chair') {
    return t('appointments.kanban.subtitleInChair', {
      busy: cabinetsBusyCount(),
      free: cabinetsFreeCount()
    })
  }
  return t('appointments.kanban.subtitleCount', { count: items.length })
}

// ---------------------------------------------------------------------
// Date navigation.
// ---------------------------------------------------------------------
function formattedDate(): string {
  return props.currentDate.toLocaleDateString(locale.value, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

function nextDay() {
  const d = new Date(props.currentDate)
  d.setDate(d.getDate() + 1)
  emit('date-change', d)
}
function prevDay() {
  const d = new Date(props.currentDate)
  d.setDate(d.getDate() - 1)
  emit('date-change', d)
}
function goToday() {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  emit('date-change', d)
}

function isDropHint(col: ColumnDef, cabinetName?: string): boolean {
  return !!drag.value
    && drag.value.targetColumnId === col.id
    && (drag.value.targetCabinetName ?? null) === (cabinetName ?? null)
}

function isInvalidHint(col: ColumnDef): boolean {
  if (!drag.value) return false
  const apt = props.appointments.find(a => a.id === drag.value!.appointmentId)
  if (!apt) return false
  return !canDropOn(apt, col)
}
</script>

<template>
  <div class="flex flex-col h-full w-full min-w-0">
    <!-- Date nav -->
    <div class="flex items-center justify-between mb-4 flex-shrink-0 min-w-0">
      <div class="flex items-center gap-2">
        <UButton variant="outline" color="neutral" icon="i-lucide-chevron-left" @click="prevDay" />
        <UButton variant="outline" color="neutral" @click="goToday">
          {{ t('appointments.today') }}
        </UButton>
        <UButton variant="outline" color="neutral" icon="i-lucide-chevron-right" @click="nextDay" />
      </div>
      <h2 class="text-h2 text-default capitalize truncate ml-4">{{ formattedDate() }}</h2>
    </div>

    <!-- Professionals strip (#51): one pill per working pro today, live
         state derived from appointments + schedules. -->
    <ProfessionalsStrip
      ref="stripRef"
      :current-date="currentDate"
      :professionals="professionals"
      :filtered-id="pillFilteredId"
      @pill-click="onPillClick"
    />

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin" :style="{ color: 'var(--color-primary)' }" />
    </div>

    <!-- Kanban scroll container: horizontal scroll lives HERE so the
         header + filters above stay within the viewport. -->
    <div
      v-else
      class="flex-1 min-h-0 min-w-0 overflow-x-auto overflow-y-hidden"
    >
      <div
        class="h-full grid gap-3 pb-2"
        :style="{
          gridTemplateColumns: 'repeat(5, minmax(260px, 1fr))',
          minWidth: '1320px'
        }"
      >
      <div
        v-for="col in COLUMNS"
        :key="col.id"
        class="flex flex-col rounded-lg ring-1 ring-[var(--color-border)] bg-surface-muted min-h-0"
        :class="{
          'ring-2 ring-[var(--color-primary)]': drag && isDropHint(col),
          'opacity-60 ring-dashed ring-red-300': drag && isInvalidHint(col)
        }"
        @dragover="onDragOverColumn(col, $event)"
        @dragleave="onDragLeaveColumn(col)"
        @drop="onDrop(col, $event)"
      >
        <!-- Header -->
        <div
          class="flex items-center justify-between px-3 py-2 border-b border-default bg-surface rounded-t-lg cursor-pointer select-none"
          @click="toggleCollapsed(col.id)"
        >
          <div class="flex items-center gap-2 min-w-0">
            <UIcon :name="col.icon" class="w-4 h-4 shrink-0" :style="{ color: statusColour(col.dropPrimary) }" />
            <div class="min-w-0">
              <div class="text-ui text-default truncate">{{ t(col.labelKey) }}</div>
              <div class="text-caption text-subtle truncate">{{ headerSubtitle(col) }}</div>
            </div>
          </div>
          <UIcon
            :name="collapsedColumns.has(col.id) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
            class="w-4 h-4 text-subtle"
          />
        </div>

        <!-- Body -->
        <div v-if="!collapsedColumns.has(col.id)" class="flex-1 overflow-auto p-2 space-y-2">
          <!-- Sub-grouping by cabinet inside "in chair" -->
          <template v-if="col.id === 'in_chair'">
            <div
              v-for="entry in inChairByCabinet"
              :key="entry.cabinet.name"
              class="rounded-md ring-1 ring-[var(--color-border)] bg-surface p-2 border-l-4 transition-shadow"
              :style="{ borderLeftColor: CABINET_STATE_ACCENT[entry.state] }"
              :class="{ 'ring-2 ring-[var(--color-primary)]': drag && isDropHint(col, entry.cabinet.name) }"
              @dragover.stop="onDragOverColumn(col, $event, entry.cabinet.name)"
              @drop.stop="onDrop(col, $event, entry.cabinet.name)"
            >
              <div class="flex items-center gap-2 mb-1.5">
                <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: entry.cabinet.color }" />
                <span class="text-ui text-default truncate">{{ entry.cabinet.name }}</span>
                <span
                  v-if="!entry.appointment"
                  class="ml-auto text-caption text-subtle italic"
                >{{ entry.state === 'inactive' ? t('appointments.kanban.inactive') : t('appointments.kanban.free') }}</span>
              </div>
              <AppointmentCard
                v-if="entry.appointment"
                :appointment="entry.appointment"
                :cabinets="cabinets"
                :professionals="professionals"
                draggable="true"
                @click="emit('appointment-click', entry.appointment as Appointment)"
                @dragstart="onDragStart(entry.appointment as Appointment, $event)"
                @dragend="onDragEnd"
              />
              <div
                v-else-if="nextForCabinet(entry.cabinet.name)"
                class="text-caption text-subtle italic px-1"
              >
                {{ t('appointments.kanban.nextIn', {
                  time: new Date(nextForCabinet(entry.cabinet.name)!.start_time)
                    .toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
                }) }}
              </div>
            </div>
          </template>

          <!-- Flat card list for every other column -->
          <template v-else>
            <AppointmentCard
              v-for="apt in appointmentsForColumn(col)"
              :key="apt.id"
              :appointment="apt"
              :cabinets="cabinets"
              :professionals="professionals"
              draggable="true"
              @click="emit('appointment-click', apt)"
              @dragstart="onDragStart(apt, $event)"
              @dragend="onDragEnd"
            />
            <div
              v-if="appointmentsForColumn(col).length === 0"
              class="text-center text-subtle text-sm py-6"
            >
              {{ t('appointments.kanban.empty') }}
            </div>
          </template>
        </div>

        <!-- Collapsed footer -->
        <div
          v-else
          class="px-3 py-2 text-caption text-subtle"
        >
          {{ statusLabel(col.dropPrimary) }}
        </div>
      </div>
      </div>
    </div>
  </div>
</template>
