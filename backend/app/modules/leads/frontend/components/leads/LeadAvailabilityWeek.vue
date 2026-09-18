<script setup lang="ts">
import {
  DAY_ORDER,
  canonicalDays,
  dayLabel,
  dayNarrowLabel,
  daysSummary,
  isSlot
} from '../../utils/leadAvailability'

/**
 * Read-only availability: a week strip plus the preferred time of day.
 *
 * The strip is the point of the feature — the front desk sees *which days*
 * are open without reading a sentence. It is a visual summary, so it is
 * exposed to assistive tech as one labelled image (`role="img"`) whose
 * label spells the days out in the reader's language, instead of seven
 * cryptic letter cells.
 */
interface Props {
  days?: string[] | null
  timeSlot?: string | null
  size?: 'sm' | 'md'
  /** Render the empty week too (used in the picker's preview). */
  always?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  days: null,
  timeSlot: null,
  size: 'sm',
  always: false
})

const { t, locale } = useI18n()

const selected = computed(() => canonicalDays(props.days))
const hasDays = computed(() => selected.value.length > 0)
const hasSlot = computed(() => isSlot(props.timeSlot))
const visible = computed(() => hasDays.value || hasSlot.value || props.always)

const accessibleLabel = computed(() => {
  const parts: string[] = []
  if (hasDays.value) parts.push(daysSummary(selected.value, locale.value))
  if (hasSlot.value) parts.push(t(`leads.slots.${props.timeSlot}`))
  return parts.join(' · ')
})

const pillSize = computed(() =>
  props.size === 'md' ? 'h-6 w-6 text-caption' : 'h-5 w-5 text-[0.65rem]'
)
</script>

<template>
  <div
    v-if="visible"
    class="flex flex-wrap items-center gap-x-2 gap-y-1"
    :role="accessibleLabel ? 'img' : undefined"
    :aria-label="accessibleLabel || undefined"
  >
    <ul
      class="flex items-center gap-0.5"
      aria-hidden="true"
    >
      <li
        v-for="day in DAY_ORDER"
        :key="day"
        :title="dayLabel(day, locale)"
        class="flex items-center justify-center rounded-full font-semibold uppercase leading-none"
        :class="[
          pillSize,
          selected.includes(day)
            ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-soft-text)]'
            : 'text-subtle opacity-50'
        ]"
      >
        {{ dayNarrowLabel(day, locale) }}
      </li>
    </ul>

    <span
      v-if="hasSlot"
      class="inline-flex items-center gap-1 text-caption text-muted whitespace-nowrap"
      aria-hidden="true"
    >
      <UIcon
        name="i-lucide-clock"
        class="w-3.5 h-3.5 text-subtle"
      />
      {{ t(`leads.slots.${timeSlot}`) }}
    </span>
  </div>
</template>
