<script setup lang="ts">
/**
 * Sticky mobile-agenda header. Issue #61.
 *
 * Three layers:
 *   1. Resource selector — pick one professional or one cabinet to scope
 *      the day-track view (single-track UX confirmed with user).
 *   2. Day metrics — total free time, next free slot, qualifying-gaps count.
 *   3. Min-duration filter chips — controls which gaps qualify as
 *      bookable; persisted per-user in localStorage.
 */
import type { Professional, Cabinet } from '~~/app/types'
import type { ResourceKind, DaySummary } from '../../composables/useFreeSlots'
import { formatDuration } from '../../composables/useFreeSlots'

interface ProfessionalWithColor extends Professional {
  color: string
}

const props = defineProps<{
  resourceKind: ResourceKind
  resourceId: string | null
  professionals: ProfessionalWithColor[]
  cabinets: Cabinet[]
  summary: DaySummary
  minDurationMin: number
  isLoading?: boolean
}>()

const emit = defineEmits<{
  'update:resourceKind': [value: ResourceKind]
  'update:resourceId': [value: string]
  'update:minDurationMin': [value: number]
}>()

const { t, locale } = useI18n()

const MIN_DURATION_OPTIONS = [15, 20, 30, 45, 60]

function selectKind(kind: ResourceKind) {
  if (kind !== props.resourceKind) emit('update:resourceKind', kind)
}

function selectResource(id: string) {
  if (id !== props.resourceId) emit('update:resourceId', id)
}

function selectMinDuration(value: number) {
  if (value !== props.minDurationMin) emit('update:minDurationMin', value)
}

function professionalInitials(p: ProfessionalWithColor): string {
  return `${p.first_name?.[0] ?? ''}${p.last_name?.[0] ?? ''}`.toUpperCase()
}

function professionalLabel(p: ProfessionalWithColor): string {
  return `${p.first_name ?? ''} ${p.last_name ?? ''}`.trim()
}

function formatNextFreeTime(d: Date): string {
  return d.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit', hour12: false })
}

function minDurationLabel(value: number): string {
  return value >= 60 ? `${value}+` : `${value}`
}
</script>

<template>
  <div class="bg-surface border-b border-subtle">
    <!-- Resource type tabs (Profesional / Cabinete) -->
    <div class="flex items-center gap-2 px-3 pt-2">
      <button
        type="button"
        class="flex-1 px-3 py-1.5 rounded-token-md text-ui transition-colors min-h-[36px]"
        :class="resourceKind === 'professional'
          ? 'bg-surface-muted text-default font-medium ring-1 ring-[var(--color-border-strong)]'
          : 'text-muted hover:bg-surface-muted/60'"
        @click="selectKind('professional')"
      >
        <UIcon
          name="i-lucide-user-round"
          class="w-4 h-4 inline-block align-text-bottom mr-1"
        />
        {{ t('appointments.freeSlots.byProfessional', 'Profesional') }}
      </button>
      <button
        type="button"
        class="flex-1 px-3 py-1.5 rounded-token-md text-ui transition-colors min-h-[36px]"
        :class="resourceKind === 'cabinet'
          ? 'bg-surface-muted text-default font-medium ring-1 ring-[var(--color-border-strong)]'
          : 'text-muted hover:bg-surface-muted/60'"
        @click="selectKind('cabinet')"
      >
        <UIcon
          name="i-lucide-door-open"
          class="w-4 h-4 inline-block align-text-bottom mr-1"
        />
        {{ t('appointments.freeSlots.byCabinet', 'Gabinete') }}
      </button>
    </div>

    <!-- Resource chip scroll (single-select) -->
    <div
      v-if="resourceKind === 'professional'"
      class="flex items-center gap-1.5 px-3 py-2 overflow-x-auto no-scrollbar"
    >
      <FilterChip
        v-for="prof in professionals"
        :key="prof.id"
        :label="professionalLabel(prof)"
        :color="prof.color"
        :initials="professionalInitials(prof)"
        :selected="resourceId === prof.id"
        class="shrink-0"
        @toggle="selectResource(prof.id)"
      />
      <span
        v-if="professionals.length === 0"
        class="text-caption text-subtle px-2"
      >
        {{ t('appointments.noProfessionals') }}
      </span>
    </div>
    <div
      v-else
      class="flex items-center gap-1.5 px-3 py-2 overflow-x-auto no-scrollbar"
    >
      <FilterChip
        v-for="cab in cabinets"
        :key="cab.id"
        :label="cab.name"
        :color="cab.color"
        :selected="resourceId === cab.name"
        class="shrink-0"
        @toggle="selectResource(cab.name)"
      />
      <span
        v-if="cabinets.length === 0"
        class="text-caption text-subtle px-2"
      >
        {{ t('appointments.cabinetAssignment.unassigned') }}
      </span>
    </div>

    <!-- Day metrics row -->
    <div class="flex items-center gap-2 px-3 py-2 overflow-x-auto no-scrollbar text-caption">
      <div
        class="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-token-sm bg-[var(--color-primary-soft)]/50 text-[var(--color-primary-soft-text)]"
      >
        <UIcon
          name="i-lucide-clock"
          class="w-3.5 h-3.5"
        />
        <span class="tnum">
          {{ summary.totalFreeMin > 0
            ? formatDuration(summary.totalFreeMin)
            : t('appointments.freeSlots.noFreeTime', 'Sin huecos') }}
          <span class="text-subtle">
            {{ t('appointments.freeSlots.freeShort', 'libres') }}
          </span>
        </span>
      </div>
      <div
        v-if="summary.nextFreeStart && summary.nextFreeDurationMin"
        class="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-token-sm bg-surface-muted text-default"
      >
        <UIcon
          name="i-lucide-arrow-right-circle"
          class="w-3.5 h-3.5"
        />
        <span class="tnum">
          {{ t('appointments.freeSlots.nextFreeAt', 'Próximo {time}', {
            time: formatNextFreeTime(summary.nextFreeStart)
          }) }}
          <span class="text-subtle">
            ({{ formatDuration(summary.nextFreeDurationMin) }})
          </span>
        </span>
      </div>
      <div
        class="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-token-sm bg-surface-muted text-muted"
      >
        <UIcon
          name="i-lucide-list"
          class="w-3.5 h-3.5"
        />
        <span class="tnum">
          {{ t('appointments.freeSlots.gapsAtLeast', '{count} huecos ≥ {min} min', {
            count: summary.qualifyingGapsCount,
            min: minDurationMin
          }) }}
        </span>
      </div>
    </div>

    <!-- Min-duration chips -->
    <div class="flex items-center gap-1.5 px-3 pb-2 overflow-x-auto no-scrollbar">
      <span class="text-caption text-subtle shrink-0 mr-1">
        {{ t('appointments.freeSlots.minDuration', 'Mínimo') }}
      </span>
      <button
        v-for="opt in MIN_DURATION_OPTIONS"
        :key="opt"
        type="button"
        class="shrink-0 px-2.5 py-1 rounded-token-sm text-ui transition-colors min-h-[32px] tnum"
        :class="minDurationMin === opt
          ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-soft-text)] font-medium ring-1 ring-[var(--color-primary)]'
          : 'text-muted hover:bg-surface-muted'"
        @click="selectMinDuration(opt)"
      >
        {{ minDurationLabel(opt) }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
