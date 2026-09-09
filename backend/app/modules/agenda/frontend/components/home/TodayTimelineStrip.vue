<script setup lang="ts">
import type { Appointment } from '~~/app/types'
import { clinicNow, parseWallClock } from '~~/app/utils/wallClock'

defineProps<{ ctx?: unknown }>()

const { t, locale } = useI18n()
const { todayAppointments, todayLoaded, fetchToday } = useHomeAgenda()
const { professionals, fetchProfessionals, getProfessionalColor, getProfessionalFullName } = useProfessionals()
const { currentClinic } = useClinic()

// Clinic wall-clock, like the appointment times it is drawn against.
const now = ref(clinicNow(currentClinic.value?.timezone))
let intervalId: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  if (professionals.value.length === 0) await fetchProfessionals()
  if (!todayLoaded.value) await fetchToday()
  intervalId = setInterval(() => {
    now.value = clinicNow(currentClinic.value?.timezone)
  }, 60_000)
})

onBeforeUnmount(() => {
  if (intervalId) clearInterval(intervalId)
})

function hourFloat(iso: string): number {
  const d = parseWallClock(iso)
  return d.getHours() + d.getMinutes() / 60 + d.getSeconds() / 3600
}

function nowHourFloat(): number {
  return now.value.getHours() + now.value.getMinutes() / 60
}

const hourRange = computed(() => {
  let min = 8
  let max = 20
  for (const a of todayAppointments.value) {
    const s = hourFloat(a.start_time)
    const e = hourFloat(a.end_time)
    if (s < min) min = Math.floor(s)
    if (e > max) max = Math.ceil(e)
  }
  // Always show the now-marker in range.
  const h = nowHourFloat()
  if (h < min) min = Math.floor(h)
  if (h > max) max = Math.ceil(h)
  return { min, max, span: Math.max(1, max - min) }
})

const hourMarkers = computed(() => {
  const arr: number[] = []
  for (let h = hourRange.value.min; h <= hourRange.value.max; h++) arr.push(h)
  return arr
})

function leftPct(iso: string): number {
  return ((hourFloat(iso) - hourRange.value.min) / hourRange.value.span) * 100
}

function widthPct(startIso: string, endIso: string): number {
  const diff = hourFloat(endIso) - hourFloat(startIso)
  return (diff / hourRange.value.span) * 100
}

const nowLeftPct = computed(() => {
  const h = nowHourFloat()
  if (h < hourRange.value.min || h > hourRange.value.max) return null
  return ((h - hourRange.value.min) / hourRange.value.span) * 100
})

const nowLabel = computed(() =>
  now.value.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' })
)

interface Lane { id: string, label: string, color: string, appts: Appointment[] }

const professionalLanes = computed<Lane[]>(() => {
  const map = new Map<string, Lane>()
  for (const a of todayAppointments.value) {
    const pid = a.professional_id
    if (!map.has(pid)) {
      const prof = professionals.value.find(p => p.id === pid)
      map.set(pid, {
        id: pid,
        label: prof ? getProfessionalFullName(prof) : '—',
        color: getProfessionalColor(pid),
        appts: []
      })
    }
    map.get(pid)!.appts.push(a)
  }
  return Array.from(map.values())
})

function formatApptTime(iso: string): string {
  return parseWallClock(iso).toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' })
}

function statusIcon(a: Appointment): string | null {
  switch (a.status) {
    case 'completed': return 'i-lucide-check'
    case 'in_treatment': return 'i-lucide-circle-dot'
    case 'checked_in': return 'i-lucide-clock'
    case 'confirmed': return 'i-lucide-check-check'
    case 'no_show': return 'i-lucide-alert-circle'
    case 'cancelled': return 'i-lucide-x'
    default: return null
  }
}

function apptTitle(a: Appointment): string {
  const name = [a.patient?.first_name, a.patient?.last_name].filter(Boolean).join(' ') || '—'
  return `${formatApptTime(a.start_time)} · ${name}`
}

function isoDay(iso: string): string {
  const d = parseWallClock(iso)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function openAppointment(a: Appointment) {
  navigateTo(`/appointments?highlight=${a.id}&date=${isoDay(a.start_time)}`)
}

const pending = computed(() => !todayLoaded.value)
const isEmpty = computed(() => !pending.value && todayAppointments.value.length === 0)
</script>

<template>
  <SectionCard
    icon="i-lucide-clock"
    icon-role="primary"
    :title="t('dashboard.timeline.title')"
  >
    <template #actions>
      <UButton
        to="/appointments"
        variant="ghost"
        color="neutral"
        size="xs"
        trailing-icon="i-lucide-arrow-right"
      >
        {{ t('dashboard.timeline.openSchedule') }}
      </UButton>
    </template>

    <div
      v-if="pending"
      class="space-y-2"
    >
      <USkeleton class="h-5 w-full" />
      <USkeleton class="h-8 w-full" />
      <USkeleton class="h-8 w-full" />
    </div>

    <EmptyState
      v-else-if="isEmpty"
      icon="i-lucide-calendar-x"
      :title="t('dashboard.timeline.empty')"
    />

    <div
      v-else
      class="relative overflow-x-auto"
    >
      <div class="min-w-[480px] md:min-w-[640px]">
        <div class="relative h-5 border-b border-[var(--color-border-subtle)] mb-3">
          <span
            v-for="h in hourMarkers"
            :key="h"
            class="absolute top-0 -translate-x-1/2 text-caption text-subtle tnum"
            :style="{ left: `${((h - hourRange.min) / hourRange.span) * 100}%` }"
          >
            {{ String(h).padStart(2, '0') }}
          </span>
        </div>

        <div
          class="relative"
          :style="{ minHeight: `${Math.max(1, professionalLanes.length) * 36}px` }"
        >
          <div class="absolute inset-0 pointer-events-none">
            <div
              v-for="h in hourMarkers"
              :key="h"
              class="absolute top-0 bottom-0 w-px bg-[var(--color-border-subtle)]"
              :style="{ left: `${((h - hourRange.min) / hourRange.span) * 100}%` }"
            />
          </div>

          <div
            v-if="nowLeftPct !== null"
            class="absolute top-[-1.25rem] bottom-0 z-10 pointer-events-none"
            :style="{ left: `${nowLeftPct}%` }"
            :aria-label="`${t('dashboard.timeline.now')} ${nowLabel}`"
          >
            <div class="absolute top-0 -translate-x-1/2 px-1.5 py-0.5 rounded-full bg-[var(--color-primary)] text-white text-micro tnum whitespace-nowrap">
              {{ nowLabel }}
            </div>
            <div class="absolute top-5 bottom-0 start-0 w-px bg-[var(--color-primary)]" />
          </div>

          <div class="relative space-y-1">
            <div
              v-for="lane in professionalLanes"
              :key="lane.id"
              class="relative h-8"
            >
              <button
                v-for="a in lane.appts"
                :key="a.id"
                type="button"
                class="absolute top-0 h-full rounded-token-sm text-caption truncate px-1.5 text-start focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] transition-[box-shadow] hover:ring-1 hover:ring-[var(--color-border-strong)]"
                :class="{ 'opacity-50 line-through': a.status === 'cancelled' }"
                :style="{
                  left: `${leftPct(a.start_time)}%`,
                  width: `max(40px, ${widthPct(a.start_time, a.end_time)}%)`,
                  backgroundColor: `color-mix(in srgb, ${lane.color} 14%, transparent)`,
                  borderInlineStart: `3px solid ${lane.color}`,
                  color: 'var(--color-text)'
                }"
                :title="`${apptTitle(a)} · ${lane.label}`"
                @click="openAppointment(a)"
              >
                <span class="flex items-center gap-1 min-w-0 h-full">
                  <UIcon
                    v-if="statusIcon(a)"
                    :name="statusIcon(a)!"
                    class="w-3 h-3 shrink-0"
                    :style="{ color: lane.color }"
                  />
                  <span class="tnum shrink-0 text-subtle">{{ formatApptTime(a.start_time) }}</span>
                  <span class="truncate">{{ a.patient?.first_name || '—' }}</span>
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </SectionCard>
</template>
