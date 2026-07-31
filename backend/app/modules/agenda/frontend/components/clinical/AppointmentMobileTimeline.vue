<script setup lang="ts">
/**
 * Mobile agenda timeline. Issue #61.
 *
 * Renders a chronological list of busy appointments, free-slot cards,
 * and blocked (off-hours / closed) bands for one resource on one day.
 * Free slots are explicit and tappable so the receptionist can spot a
 * hole at a glance and book it with a single tap.
 */
import type { Appointment, Professional } from '~~/app/types'
import type { TimelineEntry, FreeSlotEntry, BusyEntry, BlockedEntry } from '../../composables/useFreeSlots'
import { formatDuration } from '../../composables/useFreeSlots'

interface ProfessionalWithColor extends Professional {
  color: string
}

const props = defineProps<{
  entries: TimelineEntry[]
  professionals: ProfessionalWithColor[]
  highlightedAppointmentId?: string | null
}>()

const emit = defineEmits<{
  'appointment-click': [appointment: Appointment]
  'free-slot-tap': [slot: FreeSlotEntry]
}>()

const { t, locale } = useI18n()
const notesIndicator = useAppointmentNotesIndicator()

function isFree(e: TimelineEntry): e is FreeSlotEntry {
  return e.type === 'free'
}
function isBusy(e: TimelineEntry): e is BusyEntry {
  return e.type === 'busy'
}
function isBlocked(e: TimelineEntry): e is BlockedEntry {
  return e.type === 'blocked'
}

function formatTime(d: Date): string {
  return d.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit', hour12: false })
}

function professionalFor(id: string): ProfessionalWithColor | undefined {
  return props.professionals.find(p => p.id === id)
}

function professionalInitials(p: ProfessionalWithColor): string {
  return `${p.first_name?.[0] ?? ''}${p.last_name?.[0] ?? ''}`.toUpperCase()
}

function patientName(apt: Appointment): string {
  if (apt.patient) {
    const full = `${apt.patient.first_name ?? ''} ${apt.patient.last_name ?? ''}`.trim()
    return full || t('appointments.noPatient')
  }
  return t('appointments.noPatient')
}

function busyDurationMin(apt: Appointment): number {
  return Math.round((new Date(apt.end_time).getTime() - new Date(apt.start_time).getTime()) / 60000)
}

function statusColor(s: Appointment['status']): 'neutral' | 'primary' | 'success' | 'warning' | 'error' | 'info' {
  switch (s) {
    case 'scheduled': return 'neutral'
    case 'confirmed': return 'info'
    case 'checked_in': return 'warning'
    case 'in_treatment': return 'primary'
    case 'completed': return 'success'
    case 'cancelled': return 'neutral'
    case 'no_show': return 'error'
    default: return 'neutral'
  }
}

function statusLabel(s: Appointment['status']): string {
  return t(`appointments.status.${s}`, s)
}

function blockedLabel(e: BlockedEntry): string {
  if (e.reason === 'clinic_closed') return t('appointments.freeSlots.clinicClosed', 'Clínica cerrada')
  if (e.reason === 'on_break') return t('appointments.freeSlots.onBreak', 'Pausa')
  return t('appointments.freeSlots.professionalOff', 'No disponible')
}

function freeAriaLabel(e: FreeSlotEntry): string {
  return t(
    'appointments.freeSlots.tapToBookAria',
    'Hueco libre de {duration} a las {time}',
    { duration: formatDuration(e.durationMin), time: formatTime(e.start) }
  )
}

function entryKey(e: TimelineEntry, i: number): string {
  if (isBusy(e)) return `b-${e.appointment.id}`
  if (isFree(e)) return `f-${e.start.toISOString()}-${e.end.toISOString()}`
  return `x-${i}-${e.start.toISOString()}`
}
</script>

<template>
  <ul class="divide-y divide-subtle">
    <li
      v-for="(entry, i) in entries"
      :key="entryKey(entry, i)"
    >
      <!-- Busy appointment -->
      <button
        v-if="isBusy(entry)"
        type="button"
        class="w-full flex items-start gap-3 px-3 py-3 text-left hover:bg-surface-muted transition-colors min-h-[60px]"
        :class="{ 'bg-[var(--color-primary-soft)]/30': entry.appointment.id === highlightedAppointmentId }"
        @click="emit('appointment-click', entry.appointment)"
      >
        <div class="flex flex-col items-end shrink-0 w-14 pt-0.5">
          <span class="text-ui font-medium text-default tnum">
            {{ formatTime(entry.start) }}
          </span>
          <span class="text-caption text-subtle tnum">
            {{ busyDurationMin(entry.appointment) }}m
          </span>
        </div>
        <span
          class="w-1 self-stretch rounded-full shrink-0"
          :style="{ backgroundColor: professionalFor(entry.appointment.professional_id)?.color || 'var(--color-primary)' }"
        />
        <div class="flex-1 min-w-0 flex flex-col gap-1">
          <div class="flex items-center gap-2 min-w-0">
            <span class="text-ui text-default truncate font-medium">
              {{ patientName(entry.appointment) }}
            </span>
            <UIcon
              v-if="notesIndicator.has(entry.appointment.id)"
              name="i-lucide-sticky-note"
              class="w-3.5 h-3.5 text-primary shrink-0"
              :title="t('appointments.hasNotes', 'Tiene notas')"
            />
          </div>
          <div class="flex items-center gap-2 flex-wrap text-caption text-subtle">
            <span
              v-if="professionalFor(entry.appointment.professional_id)"
              class="inline-flex items-center gap-1"
            >
              <span
                class="inline-flex items-center justify-center w-4 h-4 rounded-full text-[9px] text-white font-medium"
                :style="{ backgroundColor: professionalFor(entry.appointment.professional_id)?.color }"
              >
                {{ professionalInitials(professionalFor(entry.appointment.professional_id)!) }}
              </span>
              <span class="truncate">
                {{ professionalFor(entry.appointment.professional_id)?.first_name }}
                {{ professionalFor(entry.appointment.professional_id)?.last_name }}
              </span>
            </span>
            <span
              v-if="entry.appointment.cabinet"
              class="inline-flex items-center gap-1"
            >
              <UIcon
                name="i-lucide-door-open"
                class="w-3 h-3"
              />
              {{ entry.appointment.cabinet }}
            </span>
          </div>
        </div>
        <UBadge
          :color="statusColor(entry.appointment.status)"
          variant="soft"
          size="sm"
          class="shrink-0"
        >
          {{ statusLabel(entry.appointment.status) }}
        </UBadge>
      </button>

      <!-- Free slot — qualifying (prominent, tappable) -->
      <button
        v-else-if="isFree(entry) && entry.qualifies"
        type="button"
        class="group w-full flex items-stretch gap-3 px-3 py-3 text-left transition-colors min-h-[64px] bg-[var(--color-primary-soft)]/40 hover:bg-[var(--color-primary-soft)]/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
        :aria-label="freeAriaLabel(entry)"
        @click="emit('free-slot-tap', entry)"
      >
        <div class="flex flex-col items-end shrink-0 w-14 self-center">
          <span class="text-ui font-semibold text-default tnum">
            {{ formatTime(entry.start) }}
          </span>
          <span class="text-caption text-subtle tnum">
            {{ formatTime(entry.end) }}
          </span>
        </div>
        <span
          class="w-1 self-stretch rounded-full shrink-0 bg-[var(--color-primary)]"
          aria-hidden="true"
        />
        <div class="flex-1 min-w-0 flex items-center justify-between gap-2">
          <div class="flex flex-col gap-0.5 min-w-0">
            <span class="text-ui font-semibold text-[var(--color-primary)]">
              {{ formatDuration(entry.durationMin) }}
              <span class="text-default font-normal">
                {{ t('appointments.freeSlots.freeSuffix', 'libre') }}
              </span>
            </span>
            <span class="text-caption text-subtle">
              {{ t('appointments.freeSlots.tapToBook', 'Tocar para reservar') }}
            </span>
          </div>
          <UIcon
            name="i-lucide-plus-circle"
            class="w-6 h-6 shrink-0 text-[var(--color-primary)] group-hover:scale-110 transition-transform"
          />
        </div>
      </button>

      <!-- Free slot — does not qualify (faded, still tappable) -->
      <button
        v-else-if="isFree(entry)"
        type="button"
        class="w-full flex items-center gap-3 px-3 py-2 text-left text-caption text-muted opacity-60 hover:opacity-100 transition-opacity min-h-[44px]"
        :aria-label="freeAriaLabel(entry)"
        @click="emit('free-slot-tap', entry)"
      >
        <span class="w-14 text-right tnum">{{ formatTime(entry.start) }}</span>
        <span class="flex-1 truncate">
          {{ formatDuration(entry.durationMin) }}
          {{ t('appointments.freeSlots.freeSuffix', 'libre') }}
        </span>
        <UIcon
          name="i-lucide-plus"
          class="w-4 h-4 text-subtle"
        />
      </button>

      <!-- Blocked range -->
      <div
        v-else-if="isBlocked(entry)"
        class="flex items-center gap-3 px-3 py-2 bg-surface-muted/40 text-caption text-subtle"
      >
        <span class="w-14 text-right tnum">{{ formatTime(entry.start) }}</span>
        <UIcon
          v-if="entry.reason === 'clinic_closed'"
          name="i-lucide-lock"
          class="w-3.5 h-3.5"
        />
        <UIcon
          v-else
          name="i-lucide-moon"
          class="w-3.5 h-3.5"
        />
        <span class="flex-1 truncate">{{ blockedLabel(entry) }}</span>
        <span class="tnum">{{ formatTime(entry.end) }}</span>
      </div>
    </li>
  </ul>
</template>
