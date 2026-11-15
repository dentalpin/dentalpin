<script setup lang="ts">
/**
 * FilterDateRange — date range filter with preset chips.
 *
 * Presets (Hoy / 7d / 30d / Este mes / Trimestre / Año / Personalizado)
 * resolve to concrete ``date_from`` / ``date_to`` ISO strings before
 * being emitted, so the parent + URL stay simple (two scalar values
 * instead of an enum).
 *
 * v-model returns ``{ from: string | null, to: string | null }``.
 */
import { toISODate } from '~/utils/wallClock'

interface Range {
  from: string | null
  to: string | null
}

interface Props {
  modelValue: Range
  label?: string
}

const props = withDefaults(defineProps<Props>(), {
  label: undefined
})

const emit = defineEmits<{
  'update:modelValue': [value: Range]
}>()

const { t } = useI18n()

const isOpen = ref(false)
const draft = ref<Range>({ ...props.modelValue })

// UInput's v-model is string|undefined; the parent shape uses string|null.
// Two computed bridges keep both sides honest without leaking the null
// representation into the input control.
const draftFrom = computed({
  get: () => draft.value.from ?? '',
  set: (v: string) => {
    draft.value = { ...draft.value, from: v ? v : null }
  }
})
const draftTo = computed({
  get: () => draft.value.to ?? '',
  set: (v: string) => {
    draft.value = { ...draft.value, to: v ? v : null }
  }
})

watch(
  () => props.modelValue,
  (v) => {
    draft.value = { ...v }
  },
  { deep: true }
)

function applyPreset(preset: 'today' | 'last7' | 'last30' | 'thisMonth' | 'thisQuarter' | 'thisYear') {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  let from = new Date(today)
  const to = new Date(today)
  switch (preset) {
    case 'today':
      break
    case 'last7':
      from.setDate(today.getDate() - 6)
      break
    case 'last30':
      from.setDate(today.getDate() - 29)
      break
    case 'thisMonth':
      from = new Date(today.getFullYear(), today.getMonth(), 1)
      break
    case 'thisQuarter': {
      const q = Math.floor(today.getMonth() / 3)
      from = new Date(today.getFullYear(), q * 3, 1)
      break
    }
    case 'thisYear':
      from = new Date(today.getFullYear(), 0, 1)
      break
  }
  draft.value = { from: toISODate(from), to: toISODate(to) }
}

function apply() {
  emit('update:modelValue', { ...draft.value })
  isOpen.value = false
}

function clear() {
  draft.value = { from: null, to: null }
  emit('update:modelValue', { from: null, to: null })
  isOpen.value = false
}

const labelText = computed(() => {
  const base = props.label ?? t('lists.filter.date')
  if (props.modelValue.from && props.modelValue.to) {
    return `${base} · ${props.modelValue.from} → ${props.modelValue.to}`
  }
  if (props.modelValue.from) return `${base} · ≥ ${props.modelValue.from}`
  if (props.modelValue.to) return `${base} · ≤ ${props.modelValue.to}`
  return base
})

const isActive = computed(() => Boolean(props.modelValue.from || props.modelValue.to))
</script>

<template>
  <UPopover v-model:open="isOpen">
    <UButton
      :color="isActive ? 'primary' : 'neutral'"
      :variant="isActive ? 'soft' : 'outline'"
      size="sm"
      icon="i-lucide-calendar"
      trailing-icon="i-lucide-chevron-down"
    >
      {{ labelText }}
    </UButton>

    <template #content>
      <div class="flex w-[min(260px,90vw)] flex-col gap-3 p-3">
        <div class="flex flex-wrap gap-1">
          <UButton
            size="xs"
            variant="ghost"
            @click="applyPreset('today')"
          >
            {{ t('lists.datePreset.today') }}
          </UButton>
          <UButton
            size="xs"
            variant="ghost"
            @click="applyPreset('last7')"
          >
            {{ t('lists.datePreset.last7') }}
          </UButton>
          <UButton
            size="xs"
            variant="ghost"
            @click="applyPreset('last30')"
          >
            {{ t('lists.datePreset.last30') }}
          </UButton>
          <UButton
            size="xs"
            variant="ghost"
            @click="applyPreset('thisMonth')"
          >
            {{ t('lists.datePreset.thisMonth') }}
          </UButton>
          <UButton
            size="xs"
            variant="ghost"
            @click="applyPreset('thisQuarter')"
          >
            {{ t('lists.datePreset.thisQuarter') }}
          </UButton>
          <UButton
            size="xs"
            variant="ghost"
            @click="applyPreset('thisYear')"
          >
            {{ t('lists.datePreset.thisYear') }}
          </UButton>
        </div>

        <UFormField :label="t('lists.filter.dateFrom')">
          <UInput
            v-model="draftFrom"
            type="date"
          />
        </UFormField>
        <UFormField :label="t('lists.filter.dateTo')">
          <UInput
            v-model="draftTo"
            type="date"
          />
        </UFormField>

        <div class="flex items-center justify-between gap-2">
          <UButton
            variant="ghost"
            color="neutral"
            size="sm"
            @click="clear"
          >
            {{ t('lists.filter.clear') }}
          </UButton>
          <UButton
            color="primary"
            size="sm"
            @click="apply"
          >
            {{ t('lists.filter.apply') }}
          </UButton>
        </div>
      </div>
    </template>
  </UPopover>
</template>
