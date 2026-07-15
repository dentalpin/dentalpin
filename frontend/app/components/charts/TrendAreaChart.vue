<script setup lang="ts">
/**
 * TrendAreaChart — full-width area + line chart over time.
 *
 * Designed for the payment trends endpoint but generic: takes
 * a single series of points with x (ISO date string) and y (number).
 * An optional secondary `comparison` series is overlaid as a dashed
 * line — use for refunded vs collected, last period vs current, etc.
 *
 * Interaction: hovering snaps a cursor + value bubble to the nearest
 * point. Click → emits ``point-click`` with the x value (use to drill
 * down to a list filtered by that bucket).
 *
 * Calm aesthetic: thin stroke, soft fill, no grid lines except a
 * subtle baseline. Axis labels only at first/last/extremes.
 */
type Tone = 'primary' | 'success' | 'danger' | 'info' | 'warning' | 'neutral'

interface Point {
  x: string
  y: number
}

interface Props {
  series: Point[]
  comparison?: Point[]
  tone?: Tone
  comparisonTone?: Tone
  height?: number
  /** Format a Y value (e.g. as money). Used for axis + cursor bubble. */
  formatY?: (n: number) => string
  /** Format an X bucket label (e.g. "May 2026"). */
  formatX?: (x: string) => string
  /** Label for the main series shown in the cursor bubble. */
  seriesLabel?: string
  /** Label for the comparison series shown in the cursor bubble. */
  comparisonLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  comparison: () => [],
  tone: 'primary',
  comparisonTone: 'neutral',
  height: 220,
  formatY: (n: number) => String(Math.round(n)),
  formatX: (x: string) => x,
  seriesLabel: undefined,
  comparisonLabel: undefined
})

const emit = defineEmits<{ 'point-click': [x: string] }>()

const { t } = useI18n()

const W = 800
const H = computed(() => props.height)
const PAD_L = 8
const PAD_R = 8
const PAD_T = 8
const PAD_B = 20

function toneVar(tone: Tone): string {
  const map: Record<Tone, string> = {
    primary: 'var(--color-primary)',
    success: 'var(--color-success-accent)',
    danger: 'var(--color-danger-accent)',
    info: 'var(--color-info-accent)',
    warning: 'var(--color-warning-accent)',
    neutral: 'var(--color-text-muted)'
  }
  return map[tone]
}

const allValues = computed(() => {
  const a = props.series.map(p => p.y)
  const b = props.comparison.map(p => p.y)
  const merged = [...a, ...b]
  if (!merged.length) return { min: 0, max: 1 }
  const min = Math.min(0, ...merged)
  const max = Math.max(...merged, 1)
  return { min, max }
})

function buildPath(points: Point[], close: boolean) {
  if (points.length < 2) return ''
  const { min, max } = allValues.value
  const span = max - min || 1
  const innerW = W - PAD_L - PAD_R
  const innerH = H.value - PAD_T - PAD_B
  const stepX = innerW / (points.length - 1)
  const coords = points.map((p, i) => {
    const x = PAD_L + i * stepX
    const y = PAD_T + innerH - ((p.y - min) / span) * innerH
    return [x, y] as const
  })
  const line = coords.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ')
  if (!close) return line
  const last = coords[coords.length - 1]!
  const first = coords[0]!
  return `${line} L${last[0].toFixed(2)},${PAD_T + innerH} L${first[0].toFixed(2)},${PAD_T + innerH} Z`
}

const mainArea = computed(() => buildPath(props.series, true))
const mainLine = computed(() => buildPath(props.series, false))
const compLine = computed(() => buildPath(props.comparison, false))

const xLabels = computed(() => {
  const pts = props.series
  if (pts.length < 2) return [] as { x: number, label: string }[]
  const innerW = W - PAD_L - PAD_R
  const stepX = innerW / (pts.length - 1)
  const indices = [0, Math.floor((pts.length - 1) / 2), pts.length - 1]
  const seen = new Set<number>()
  return indices
    .filter(i => !seen.has(i) && seen.add(i))
    .map(i => ({ x: PAD_L + i * stepX, label: props.formatX(pts[i]!.x) }))
})

const yMaxLabel = computed(() => props.formatY(allValues.value.max))

const isEmpty = computed(() => props.series.length < 2)

// --- Hover cursor -------------------------------------------------------
const hoverIdx = ref<number | null>(null)
const wrapper = ref<HTMLDivElement | null>(null)

function onMove(evt: PointerEvent) {
  if (!props.series.length || !wrapper.value) return
  const rect = wrapper.value.getBoundingClientRect()
  const relX = evt.clientX - rect.left
  const ratio = Math.max(0, Math.min(1, relX / rect.width))
  const idx = Math.round(ratio * (props.series.length - 1))
  hoverIdx.value = idx
}

function onLeave() {
  hoverIdx.value = null
}

function onClick() {
  if (hoverIdx.value == null) return
  const pt = props.series[hoverIdx.value]
  if (pt) emit('point-click', pt.x)
}

const cursor = computed(() => {
  if (hoverIdx.value == null || !props.series.length) return null
  const idx = hoverIdx.value
  const innerW = W - PAD_L - PAD_R
  const innerH = H.value - PAD_T - PAD_B
  const stepX = props.series.length > 1 ? innerW / (props.series.length - 1) : 0
  const x = PAD_L + idx * stepX
  const { min, max } = allValues.value
  const span = max - min || 1
  const pt = props.series[idx]!
  const compPt = props.comparison[idx]
  const y = PAD_T + innerH - ((pt.y - min) / span) * innerH
  return {
    x,
    y,
    main: pt,
    comparison: compPt,
    xPct: (x / W) * 100
  }
})
</script>

<template>
  <div class="w-full">
    <div
      v-if="!isEmpty"
      ref="wrapper"
      class="relative w-full select-none"
      :style="{ height: `${H}px` }"
      @pointermove="onMove"
      @pointerleave="onLeave"
      @click="onClick"
    >
      <svg
        :viewBox="`0 0 ${W} ${H}`"
        preserveAspectRatio="none"
        role="img"
        :aria-label="t('charts.trend.ariaLabel', { count: series.length })"
        class="w-full h-full overflow-visible"
      >
        <path
          :d="mainArea"
          :fill="toneVar(tone)"
          fill-opacity="0.1"
        />
        <path
          v-if="compLine"
          :d="compLine"
          :stroke="toneVar(comparisonTone)"
          stroke-width="1.25"
          stroke-dasharray="4 4"
          fill="none"
          opacity="0.7"
        />
        <path
          :d="mainLine"
          :stroke="toneVar(tone)"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
          fill="none"
        />
        <line
          v-if="cursor"
          :x1="cursor.x"
          :x2="cursor.x"
          :y1="PAD_T"
          :y2="H - PAD_B"
          stroke="var(--color-text-muted)"
          stroke-width="0.75"
          stroke-dasharray="2 3"
          opacity="0.5"
        />
        <circle
          v-if="cursor"
          :cx="cursor.x"
          :cy="cursor.y"
          r="3"
          :fill="toneVar(tone)"
          stroke="var(--color-surface)"
          stroke-width="1.5"
        />
      </svg>

      <!-- X axis labels (3 max) -->
      <div
        v-for="(l, i) in xLabels"
        :key="i"
        class="absolute text-caption text-subtle tnum -translate-x-1/2 pointer-events-none"
        :style="{ left: `${(l.x / W) * 100}%`, bottom: '0px' }"
      >
        {{ l.label }}
      </div>

      <!-- Y max label -->
      <div
        class="absolute top-0 left-0 text-caption text-subtle tnum pointer-events-none"
      >
        {{ yMaxLabel }}
      </div>

      <!-- Hover bubble -->
      <div
        v-if="cursor"
        class="absolute -translate-x-1/2 -translate-y-full px-2 py-1 rounded-token-sm bg-surface shadow-token-sm border border-default text-caption text-default pointer-events-none whitespace-nowrap"
        :style="{ left: `${cursor.xPct}%`, top: '0px' }"
      >
        <div class="text-subtle">
          {{ formatX(cursor.main.x) }}
        </div>
        <div class="tnum">
          <span
            v-if="seriesLabel"
            class="text-muted mr-1"
          >{{ seriesLabel }}:</span>{{ formatY(cursor.main.y) }}
        </div>
        <div
          v-if="cursor.comparison"
          class="tnum text-muted"
        >
          <span
            v-if="comparisonLabel"
            class="mr-1"
          >{{ comparisonLabel }}:</span>{{ formatY(cursor.comparison.y) }}
        </div>
      </div>
    </div>

    <div
      v-else
      class="w-full flex items-center justify-center bg-surface-muted rounded-token-sm border border-dashed border-default"
      :style="{ height: `${H}px` }"
    >
      <UIcon
        name="i-lucide-line-chart"
        class="w-6 h-6 text-subtle"
      />
    </div>
  </div>
</template>
