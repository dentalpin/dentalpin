<script setup lang="ts">
/**
 * Mobile agenda — single-track day view with explicit free slots.
 * Issue #61.
 *
 * Composes the week-strip date nav, the day summary (resource selector
 * + metrics + min-duration filter), and the timeline (busy/free/blocked
 * chronological list). Free slots are tappable and emit `free-slot-tap`
 * with a payload the parent can hand straight to the appointment
 * composer.
 */
import type { Appointment, Cabinet, Professional } from '~~/app/types'
import type {
  FreeSlotEntry,
  ResourceKind,
  ResourceRef,
  DayBounds
} from '../../composables/useFreeSlots'
import { useFreeSlots } from '../../composables/useFreeSlots'
import type { AvailabilityPayload } from '../../composables/useScheduleAvailability'
import { useScheduleAvailability } from '../../composables/useScheduleAvailability'

interface ProfessionalWithColor extends Professional {
  color: string
}

const props = defineProps<{
  appointments: readonly Appointment[]
  professionals: ProfessionalWithColor[]
  cabinets: Cabinet[]
  currentDate: Date
  isLoading?: boolean
  highlightedAppointmentId?: string | null
}>()

const emit = defineEmits<{
  'appointment-click': [appointment: Appointment]
  'date-change': [date: Date]
  'create-at': [date: Date]
  'free-slot-tap': [payload: { slot: FreeSlotEntry, resource: ResourceRef }]
  'highlight-cleared': []
}>()

const { t, locale } = useI18n()
const auth = useAuth()
const { fetch: fetchAvailability } = useScheduleAvailability()

const STORAGE_PREFIX = 'agenda:mobile:'

watch(() => props.highlightedAppointmentId, (newId) => {
  if (newId) setTimeout(() => emit('highlight-cleared'), 5000)
}, { immediate: true })

// ---- Resource selection (persisted) -------------------------------

const resourceKind = ref<ResourceKind>(loadKind())
const resourceId = ref<string | null>(null)

function loadKind(): ResourceKind {
  if (import.meta.server) return 'professional'
  const v = window.localStorage.getItem(STORAGE_PREFIX + 'resourceKind')
  return v === 'cabinet' ? 'cabinet' : 'professional'
}

function loadResourceId(kind: ResourceKind): string | null {
  if (import.meta.server) return null
  return window.localStorage.getItem(STORAGE_PREFIX + 'resourceId:' + kind)
}

function persistResource() {
  if (import.meta.server) return
  window.localStorage.setItem(STORAGE_PREFIX + 'resourceKind', resourceKind.value)
  if (resourceId.value) {
    window.localStorage.setItem(
      STORAGE_PREFIX + 'resourceId:' + resourceKind.value,
      resourceId.value
    )
  }
}

function defaultProfessionalId(): string | null {
  if (props.professionals.length === 0) return null
  const stored = loadResourceId('professional')
  if (stored && props.professionals.some(p => p.id === stored)) return stored
  // Prefer current user when they are a professional.
  const me = auth.user.value?.id
  if (me && props.professionals.some(p => p.id === me)) return me
  // Otherwise alphabetically first.
  const sorted = [...props.professionals].sort((a, b) => {
    const an = `${a.first_name ?? ''} ${a.last_name ?? ''}`
    const bn = `${b.first_name ?? ''} ${b.last_name ?? ''}`
    return an.localeCompare(bn)
  })
  return sorted[0]?.id ?? null
}

function defaultCabinetId(): string | null {
  if (props.cabinets.length === 0) return null
  const stored = loadResourceId('cabinet')
  if (stored && props.cabinets.some(c => c.name === stored)) return stored
  const sorted = [...props.cabinets].sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0))
  return sorted[0]?.name ?? null
}

watch(
  [resourceKind, () => props.professionals, () => props.cabinets],
  () => {
    if (resourceKind.value === 'professional') {
      const next = defaultProfessionalId()
      // Only override resourceId when current is invalid for new kind/list.
      if (!resourceId.value || !props.professionals.some(p => p.id === resourceId.value)) {
        resourceId.value = next
      }
    } else {
      const next = defaultCabinetId()
      if (!resourceId.value || !props.cabinets.some(c => c.name === resourceId.value)) {
        resourceId.value = next
      }
    }
    persistResource()
  },
  { immediate: true }
)

const resource = computed<ResourceRef | null>(() => {
  if (!resourceId.value) return null
  return { kind: resourceKind.value, id: resourceId.value }
})

function onUpdateResourceKind(kind: ResourceKind) {
  resourceKind.value = kind
  // Reset resourceId so the watcher above picks the default for the new kind.
  resourceId.value = kind === 'professional' ? defaultProfessionalId() : defaultCabinetId()
  persistResource()
}

function onUpdateResourceId(id: string) {
  resourceId.value = id
  persistResource()
}

// ---- Min-duration filter (persisted) ------------------------------

const minDurationMin = ref<number>(loadMinDuration())

function loadMinDuration(): number {
  if (import.meta.server) return 20
  const raw = window.localStorage.getItem(STORAGE_PREFIX + 'minDurationMin')
  const n = raw ? Number.parseInt(raw, 10) : NaN
  return Number.isFinite(n) && n > 0 ? n : 20
}

function onUpdateMinDuration(value: number) {
  minDurationMin.value = value
  if (!import.meta.server) {
    window.localStorage.setItem(STORAGE_PREFIX + 'minDurationMin', String(value))
  }
}

// ---- Availability fetch ------------------------------------------

const availability = ref<AvailabilityPayload | null>(null)

function isoLocalDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

async function refreshAvailability() {
  const iso = isoLocalDate(props.currentDate)
  const params: { start: string, end: string, professional_id?: string } = {
    start: iso,
    end: iso
  }
  if (resourceKind.value === 'professional' && resourceId.value) {
    params.professional_id = resourceId.value
  }
  availability.value = await fetchAvailability(params)
}

watch(
  [() => props.currentDate, resourceKind, resourceId],
  () => { refreshAvailability() },
  { immediate: true }
)

// ---- Bounds (derive from availability open ranges; default 8–21) --

const DEFAULT_BOUNDS: DayBounds = { startHour: 8, endHour: 21 }

const bounds = computed<DayBounds>(() => {
  const payload = availability.value
  if (!payload) return DEFAULT_BOUNDS
  const open = payload.ranges.filter(r => r.state === 'open')
  if (open.length === 0) return DEFAULT_BOUNDS
  let minHour = 24
  let maxHour = 0
  for (const r of open) {
    const s = new Date(r.start)
    const e = new Date(r.end)
    minHour = Math.min(minHour, s.getHours())
    const eh = e.getMinutes() > 0 || e.getSeconds() > 0 ? e.getHours() + 1 : e.getHours()
    maxHour = Math.max(maxHour, eh)
  }
  minHour = Math.max(0, Math.min(minHour, 23))
  maxHour = Math.max(minHour + 1, Math.min(maxHour, 24))
  return { startHour: minHour, endHour: maxHour }
})

// ---- Free-slot engine -------------------------------------------

const appointmentsRef = computed(() => props.appointments)

const { entries, summary } = useFreeSlots({
  appointments: appointmentsRef,
  availability,
  resource,
  date: toRef(() => props.currentDate),
  minDurationMin,
  bounds
})

function onFreeSlotTap(slot: FreeSlotEntry) {
  if (!resource.value) return
  emit('free-slot-tap', { slot, resource: resource.value })
}

// ---- Header / week strip ----------------------------------------

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate()
}

function getMonday(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  d.setHours(0, 0, 0, 0)
  return d
}

const weekDays = computed<Date[]>(() => {
  const start = getMonday(props.currentDate)
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    return d
  })
})

function formatWeekdayShort(date: Date): string {
  return new Intl.DateTimeFormat(locale.value, { weekday: 'narrow' }).format(date)
}

function formatHeaderDate(date: Date): string {
  return new Intl.DateTimeFormat(locale.value, {
    weekday: 'long',
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  }).format(date)
}

function countForDay(day: Date): number {
  return props.appointments.filter((apt) => {
    const d = new Date(apt.start_time)
    return isSameDay(d, day) && apt.status !== 'cancelled'
  }).length
}

function shiftDay(days: number) {
  const next = new Date(props.currentDate)
  next.setDate(next.getDate() + days)
  emit('date-change', next)
}

function selectDay(d: Date) {
  if (!isSameDay(d, props.currentDate)) emit('date-change', new Date(d))
}

function isToday(d: Date): boolean {
  return isSameDay(d, new Date())
}

function createNow() {
  emit('create-at', new Date(props.currentDate))
}

const hasAnyEntry = computed(() => entries.value.length > 0)
</script>

<template>
  <div class="flex flex-col h-full w-full min-w-0">
    <!-- Sticky header: date nav + week strip + day summary -->
    <div class="sticky top-0 z-20 bg-surface border-b border-subtle">
      <div class="flex items-center justify-between px-3 py-2">
        <UButton
          variant="ghost"
          color="neutral"
          size="sm"
          icon="i-lucide-chevron-left"
          :aria-label="t('common.previous', 'Anterior')"
          @click="shiftDay(-1)"
        />
        <button
          type="button"
          class="text-ui text-default capitalize px-3 py-1 rounded-token-md hover:bg-surface-muted min-h-[36px]"
          @click="emit('date-change', new Date())"
        >
          {{ formatHeaderDate(currentDate) }}
        </button>
        <UButton
          variant="ghost"
          color="neutral"
          size="sm"
          icon="i-lucide-chevron-right"
          :aria-label="t('common.next', 'Siguiente')"
          @click="shiftDay(1)"
        />
      </div>

      <!-- 7-day strip -->
      <div class="grid grid-cols-7 gap-1 px-2 pb-2">
        <button
          v-for="d in weekDays"
          :key="d.toISOString()"
          type="button"
          class="flex flex-col items-center gap-1 py-2 rounded-token-md transition-colors"
          :class="[
            isSameDay(d, currentDate)
              ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-soft-text)]'
              : 'text-muted hover:bg-surface-muted',
            isToday(d) && !isSameDay(d, currentDate) ? 'ring-1 ring-[var(--color-primary)]' : ''
          ]"
          @click="selectDay(d)"
        >
          <span class="text-caption uppercase">{{ formatWeekdayShort(d) }}</span>
          <span class="text-ui tnum font-medium">{{ d.getDate() }}</span>
          <span
            v-if="countForDay(d) > 0"
            class="text-[10px] leading-none px-1.5 py-0.5 rounded-full bg-[var(--color-primary)] text-white tnum"
          >
            {{ countForDay(d) }}
          </span>
          <span
            v-else
            class="h-[14px]"
          />
        </button>
      </div>

      <AppointmentMobileDaySummary
        :resource-kind="resourceKind"
        :resource-id="resourceId"
        :professionals="professionals"
        :cabinets="cabinets"
        :summary="summary"
        :min-duration-min="minDurationMin"
        :is-loading="isLoading"
        @update:resource-kind="onUpdateResourceKind"
        @update:resource-id="onUpdateResourceId"
        @update:min-duration-min="onUpdateMinDuration"
      />
    </div>

    <!-- Timeline body -->
    <div class="flex-1 overflow-y-auto pb-24">
      <div
        v-if="isLoading"
        class="p-6 flex justify-center"
      >
        <UIcon
          name="i-lucide-loader-2"
          class="w-8 h-8 animate-spin"
          :style="{ color: 'var(--color-primary)' }"
        />
      </div>

      <div
        v-else-if="!resource"
        class="p-6 flex flex-col items-center gap-3 text-center"
      >
        <UIcon
          name="i-lucide-user-round-search"
          class="w-10 h-10 text-subtle"
        />
        <p class="text-ui text-muted">
          {{ resourceKind === 'professional'
            ? t('appointments.noProfessionals')
            : t('appointments.cabinetAssignment.unassigned') }}
        </p>
      </div>

      <div
        v-else-if="!hasAnyEntry"
        class="p-6 flex flex-col items-center gap-3 text-center"
      >
        <UIcon
          name="i-lucide-calendar-x"
          class="w-10 h-10 text-subtle"
        />
        <p class="text-ui text-muted">
          {{ t('appointments.emptyDay', 'No hay citas este día') }}
        </p>
        <UButton
          color="primary"
          variant="soft"
          icon="i-lucide-plus"
          @click="createNow"
        >
          {{ t('appointments.create') }}
        </UButton>
      </div>

      <AppointmentMobileTimeline
        v-else
        :entries="entries"
        :professionals="professionals"
        :highlighted-appointment-id="highlightedAppointmentId"
        @appointment-click="emit('appointment-click', $event)"
        @free-slot-tap="onFreeSlotTap"
      />
    </div>

    <!-- FAB: create appointment -->
    <UButton
      class="fixed right-4 z-30 shadow-lg"
      :style="{ bottom: 'calc(1rem + env(safe-area-inset-bottom))' }"
      color="primary"
      size="lg"
      icon="i-lucide-plus"
      :aria-label="t('appointments.create')"
      @click="createNow"
    />
  </div>
</template>
