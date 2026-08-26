<script setup lang="ts">
import type { Shift, WeekdayShifts } from '../composables/useClinicHours'

const props = defineProps<{
  modelValue: WeekdayShifts[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WeekdayShifts[]]
}>()

const { t } = useI18n()

function shiftsForDay(weekday: number): Shift[] {
  const entry = props.modelValue.find(d => d.weekday === weekday)
  return entry?.shifts ? [...entry.shifts] : []
}

function updateDay(weekday: number, shifts: Shift[]) {
  const next = [...props.modelValue]
  const idx = next.findIndex(d => d.weekday === weekday)
  if (idx === -1) {
    next.push({ weekday, shifts })
  } else {
    next[idx] = { weekday, shifts }
  }
  emit('update:modelValue', next)
}

function addShift(weekday: number) {
  const current = shiftsForDay(weekday)
  current.push({ start_time: '09:00:00', end_time: '14:00:00' })
  updateDay(weekday, current)
}

function removeShift(weekday: number, index: number) {
  const current = shiftsForDay(weekday)
  current.splice(index, 1)
  updateDay(weekday, current)
}

function updateShift(weekday: number, index: number, field: 'start_time' | 'end_time', value: string) {
  const current = shiftsForDay(weekday)
  const padded = value.length === 5 ? `${value}:00` : value
  const existing = current[index]
  if (!existing) return
  current[index] = { ...existing, [field]: padded }
  updateDay(weekday, current)
}

function timeForInput(value: string | undefined): string {
  if (!value) return ''
  return value.length >= 5 ? value.substring(0, 5) : value
}
</script>

<template>
  <div class="space-y-2">
    <div
      v-for="weekday in 7"
      :key="weekday - 1"
      class="flex items-start gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-800"
    >
      <div class="w-28 pt-1 font-medium">
        {{ t(`schedules.weekday.${weekday - 1}`) }}
      </div>
      <div class="flex-1 space-y-2">
        <div
          v-for="(shift, idx) in shiftsForDay(weekday - 1)"
          :key="idx"
          class="flex items-center gap-2"
        >
          <UInput
            type="time"
            :model-value="timeForInput(shift.start_time)"
            :disabled="disabled"
            size="sm"
            class="w-28"
            @update:model-value="(v) => updateShift(weekday - 1, idx, 'start_time', String(v))"
          />
          <span class="text-gray-400">—</span>
          <UInput
            type="time"
            :model-value="timeForInput(shift.end_time)"
            :disabled="disabled"
            size="sm"
            class="w-28"
            @update:model-value="(v) => updateShift(weekday - 1, idx, 'end_time', String(v))"
          />
          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-x"
            :aria-label="t('common.remove')"
            size="xs"
            :disabled="disabled"
            @click="removeShift(weekday - 1, idx)"
          />
        </div>
        <div
          v-if="shiftsForDay(weekday - 1).length === 0"
          class="text-sm text-gray-400 italic"
        >
          {{ t('schedules.weekday.closed') }}
        </div>
        <UButton
          size="xs"
          variant="soft"
          icon="i-lucide-plus"
          :disabled="disabled"
          @click="addShift(weekday - 1)"
        >
          {{ t('schedules.weekday.addShift') }}
        </UButton>
      </div>
    </div>
  </div>
</template>
