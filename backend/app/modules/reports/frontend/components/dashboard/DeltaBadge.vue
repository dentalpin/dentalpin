<script setup lang="ts">
interface Props {
  value: number | null
  /** When true, positive delta is bad (e.g. no-show rate going up). */
  inverted?: boolean
  /** Optional override label shown next to the percentage (e.g. "vs. periodo anterior"). */
  label?: string
}

const props = withDefaults(defineProps<Props>(), {
  inverted: false,
  label: undefined
})

const hasValue = computed(() => props.value != null && Number.isFinite(props.value))

const direction = computed<'up' | 'down' | 'flat'>(() => {
  if (!hasValue.value) return 'flat'
  if (Math.abs(props.value!) < 0.05) return 'flat'
  return props.value! > 0 ? 'up' : 'down'
})

const tone = computed<'success' | 'danger' | 'neutral'>(() => {
  if (direction.value === 'flat') return 'neutral'
  const isPositive = direction.value === 'up'
  const good = props.inverted ? !isPositive : isPositive
  return good ? 'success' : 'danger'
})

const icon = computed(() => {
  if (direction.value === 'up') return 'i-lucide-trending-up'
  if (direction.value === 'down') return 'i-lucide-trending-down'
  return 'i-lucide-minus'
})

const colorClass = computed(() => {
  switch (tone.value) {
    case 'success':
      return 'text-[var(--color-success-accent)]'
    case 'danger':
      return 'text-[var(--color-danger-accent)]'
    default:
      return 'text-subtle'
  }
})

const formatted = computed(() => {
  if (!hasValue.value) return '—'
  const v = props.value!
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(1)}%`
})
</script>

<template>
  <span
    class="inline-flex items-center gap-1 text-caption tnum"
    :class="colorClass"
  >
    <UIcon
      :name="icon"
      class="w-3 h-3"
      aria-hidden="true"
    />
    <span>{{ formatted }}</span>
    <span
      v-if="label"
      class="text-subtle ms-1"
    >{{ label }}</span>
  </span>
</template>
