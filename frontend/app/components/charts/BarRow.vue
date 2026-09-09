<script setup lang="ts">
/**
 * BarRow — horizontal proportional bar with label + value.
 *
 * Reusable across modules. Use a list of these for breakdowns
 * (aging buckets, top professionals, refund reasons, etc.).
 *
 * Clickable variant emits @click — give it a meaningful aria-label
 * via the `actionLabel` prop so screen readers announce what
 * activating the row will do.
 */
type Tone = 'primary' | 'success' | 'danger' | 'info' | 'warning' | 'neutral'

interface Props {
  value: number
  max: number
  label: string
  valueLabel: string
  /** Optional secondary label below the main one (e.g. "12 pacientes") */
  hint?: string
  tone?: Tone
  clickable?: boolean
  actionLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  hint: undefined,
  tone: 'primary',
  clickable: false,
  actionLabel: undefined
})

defineEmits<{ click: [] }>()

const toneVar = computed(() => {
  const map: Record<Tone, string> = {
    primary: 'var(--color-primary)',
    success: 'var(--color-success-accent)',
    danger: 'var(--color-danger-accent)',
    info: 'var(--color-info-accent)',
    warning: 'var(--color-warning-accent)',
    neutral: 'var(--color-text-muted)'
  }
  return map[props.tone]
})

const pct = computed(() => {
  if (!props.max || props.max <= 0) return 0
  const raw = (props.value / props.max) * 100
  return Math.max(0, Math.min(100, raw))
})
</script>

<template>
  <component
    :is="clickable ? 'button' : 'div'"
    :type="clickable ? 'button' : undefined"
    class="block w-full text-start group"
    :class="clickable ? 'cursor-pointer rounded-token-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]' : ''"
    :aria-label="actionLabel"
    @click="clickable && $emit('click')"
  >
    <div class="flex items-baseline justify-between gap-3 mb-1">
      <div class="min-w-0">
        <div
          class="text-ui text-default truncate"
          :class="clickable ? 'group-hover:text-[var(--color-primary)] transition-colors' : ''"
        >
          {{ label }}
        </div>
        <div
          v-if="hint"
          class="text-caption text-muted truncate"
        >
          {{ hint }}
        </div>
      </div>
      <div class="text-ui text-default font-medium tnum shrink-0">
        {{ valueLabel }}
      </div>
    </div>
    <div
      class="h-2 w-full rounded-full overflow-hidden bg-surface-muted"
      :aria-hidden="true"
    >
      <div
        class="h-full rounded-full transition-[width] duration-300 ease-out"
        :style="{ width: `${pct}%`, backgroundColor: toneVar }"
      />
    </div>
  </component>
</template>
