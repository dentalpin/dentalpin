<script setup lang="ts">
import {
  DAY_ORDER,
  SLOT_ORDER,
  canonicalDays,
  dayLabel,
  dayNarrowLabel,
  type AvailabilitySlot,
  type DayOfWeek
} from '../../utils/leadAvailability'

/**
 * The week picker: seven toggles plus an optional time of day.
 *
 * Two-way bound to the parent's form (`v-model:days` / `v-model:slot`), so
 * the manual lead form and any future enquiry form share one control. Days
 * are emitted already canonicalised (mon..sun, no duplicates) — the same
 * order the API stores, which keeps the saved value and the strip identical.
 */
interface Props {
  days: DayOfWeek[]
  timeSlot: string | null
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), { disabled: false })

const emit = defineEmits<{
  'update:days': [value: DayOfWeek[]]
  'update:timeSlot': [value: AvailabilitySlot | null]
}>()

const { t, locale } = useI18n()

const selected = computed(() => canonicalDays(props.days))

function toggle(day: DayOfWeek) {
  if (props.disabled) return
  const current = selected.value
  const next = current.includes(day)
    ? current.filter(value => value !== day)
    : canonicalDays([...current, day])
  emit('update:days', next)
}

const slotItems = computed(() => [
  { value: 'any', label: t('leads.slots.any') },
  ...SLOT_ORDER.map(value => ({ value, label: t(`leads.slots.${value}`) }))
])

const slotValue = computed(() => props.timeSlot ?? 'any')

function onSlot(value: string | number | undefined) {
  emit('update:timeSlot', value && value !== 'any' ? (value as AvailabilitySlot) : null)
}
</script>

<template>
  <div class="space-y-3">
    <div
      class="flex flex-wrap gap-1"
      role="group"
      :aria-label="t('leads.fields.availability')"
    >
      <UButton
        v-for="day in DAY_ORDER"
        :key="day"
        type="button"
        size="sm"
        :color="selected.includes(day) ? 'primary' : 'neutral'"
        :variant="selected.includes(day) ? 'soft' : 'outline'"
        :disabled="disabled"
        :aria-pressed="selected.includes(day)"
        :aria-label="dayLabel(day, locale)"
        :title="dayLabel(day, locale)"
        class="min-w-10 justify-center uppercase"
        @click="toggle(day)"
      >
        {{ dayNarrowLabel(day, locale) }}
      </UButton>
    </div>

    <USelect
      :model-value="slotValue"
      :items="slotItems"
      :disabled="disabled"
      icon="i-lucide-clock"
      class="max-w-xs"
      @update:model-value="onSlot"
    />
  </div>
</template>
