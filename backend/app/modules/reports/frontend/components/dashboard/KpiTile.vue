<script setup lang="ts">
import SummaryCard from '~~/app/components/shared/SummaryCard.vue'
import Sparkline from '~~/app/components/charts/Sparkline.vue'
import DeltaBadge from './DeltaBadge.vue'

type Severity = 'neutral' | 'info' | 'success' | 'warning' | 'danger'
type Tone = 'primary' | 'success' | 'danger' | 'info' | 'warning' | 'neutral'

interface Props {
  title: string
  icon?: string
  severity?: Severity
  to?: string
  loading?: boolean
  empty?: boolean
  /** Main formatted value (already locale + currency formatted). */
  value?: string
  /** Optional secondary line below the big number. */
  hint?: string
  /** Sparkline series (raw numbers). Omit to hide. */
  sparklinePoints?: number[]
  sparklineTone?: Tone
  /** Percentage delta vs previous period. null hides the badge. */
  delta?: number | null
  /** Mark up-is-bad (no-show rate, debt, etc.). */
  deltaInverted?: boolean
  deltaLabel?: string
  /** Show a "snapshot" badge to communicate this metric ignores the date filter. */
  snapshot?: boolean
  snapshotLabel?: string
}

withDefaults(defineProps<Props>(), {
  icon: undefined,
  severity: 'neutral',
  to: undefined,
  loading: false,
  empty: false,
  value: '—',
  hint: undefined,
  sparklinePoints: () => [],
  sparklineTone: 'primary',
  delta: null,
  deltaInverted: false,
  deltaLabel: undefined,
  snapshot: false,
  snapshotLabel: undefined
})
</script>

<template>
  <SummaryCard
    :title="title"
    :icon="icon"
    :severity="severity"
    :to="to"
    :loading="loading"
    :empty="empty"
  >
    <template
      v-if="snapshot"
      #header-trailing
    >
      <span
        class="ms-auto inline-flex items-center gap-1 text-caption text-subtle"
        :title="snapshotLabel"
      >
        <UIcon
          name="i-lucide-clock"
          class="w-3 h-3"
        />
        {{ snapshotLabel }}
      </span>
    </template>

    <template #empty>
      <slot name="empty">
        <span class="text-caption">{{ hint ?? '—' }}</span>
      </slot>
    </template>

    <div class="flex flex-col gap-1.5">
      <div class="text-h1 text-default font-semibold tnum tabular-nums truncate">
        {{ value }}
      </div>
      <div class="flex items-center gap-2 min-w-0">
        <DeltaBadge
          v-if="delta != null"
          :value="delta"
          :inverted="deltaInverted"
        />
        <div
          v-if="hint"
          class="text-caption text-muted truncate"
        >
          {{ hint }}
        </div>
      </div>
      <Sparkline
        v-if="sparklinePoints && sparklinePoints.length >= 2"
        :points="sparklinePoints"
        :tone="sparklineTone"
        :height="32"
      />
    </div>
  </SummaryCard>
</template>
