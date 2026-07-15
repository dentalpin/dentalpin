<script setup lang="ts">
/**
 * DonutChart — proportional donut with center total + side legend.
 *
 * Slices receive a tone from a calm-palette cycle (primary, success,
 * info, warning, danger, neutral) when not specified explicitly.
 *
 * Click on a slice or a legend row emits ``slice-click`` with the
 * slice key — wire this to drill-down navigation.
 */
type Tone = 'primary' | 'success' | 'danger' | 'info' | 'warning' | 'neutral'

interface Slice {
  key: string
  label: string
  value: number
  hint?: string
  tone?: Tone
}

interface Props {
  slices: Slice[]
  size?: number
  thickness?: number
  /** Formatter for both slice values and the center total. */
  formatValue?: (n: number) => string
  /** Label shown above the center total (e.g. "Total"). */
  centerLabel?: string
  clickable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 168,
  thickness: 18,
  formatValue: (n: number) => String(n),
  centerLabel: undefined,
  clickable: false
})

defineEmits<{ 'slice-click': [key: string] }>()

const { t } = useI18n()

const PALETTE: Tone[] = ['primary', 'success', 'info', 'warning', 'danger', 'neutral']

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

interface RenderedSlice extends Slice {
  tone: Tone
  color: string
  pct: number
  d: string
}

const radius = computed(() => props.size / 2)
const inner = computed(() => radius.value - props.thickness)

const total = computed(() => props.slices.reduce((acc, s) => acc + (s.value || 0), 0))

function arcPath(startA: number, endA: number, rOuter: number, rInner: number): string {
  // Single full-circle slice needs to be drawn as two arcs to avoid the
  // 0-length degenerate case.
  const sweep = endA - startA
  if (sweep <= 0) return ''
  const cx = rOuter
  const cy = rOuter
  if (sweep >= 2 * Math.PI - 1e-6) {
    return [
      `M ${cx} ${cy - rOuter}`,
      `A ${rOuter} ${rOuter} 0 1 1 ${cx} ${cy + rOuter}`,
      `A ${rOuter} ${rOuter} 0 1 1 ${cx} ${cy - rOuter}`,
      `M ${cx} ${cy - rInner}`,
      `A ${rInner} ${rInner} 0 1 0 ${cx} ${cy + rInner}`,
      `A ${rInner} ${rInner} 0 1 0 ${cx} ${cy - rInner}`,
      'Z'
    ].join(' ')
  }
  const large = sweep > Math.PI ? 1 : 0
  const sxO = cx + rOuter * Math.cos(startA)
  const syO = cy + rOuter * Math.sin(startA)
  const exO = cx + rOuter * Math.cos(endA)
  const eyO = cy + rOuter * Math.sin(endA)
  const sxI = cx + rInner * Math.cos(endA)
  const syI = cy + rInner * Math.sin(endA)
  const exI = cx + rInner * Math.cos(startA)
  const eyI = cy + rInner * Math.sin(startA)
  return [
    `M ${sxO.toFixed(3)} ${syO.toFixed(3)}`,
    `A ${rOuter} ${rOuter} 0 ${large} 1 ${exO.toFixed(3)} ${eyO.toFixed(3)}`,
    `L ${sxI.toFixed(3)} ${syI.toFixed(3)}`,
    `A ${rInner} ${rInner} 0 ${large} 0 ${exI.toFixed(3)} ${eyI.toFixed(3)}`,
    'Z'
  ].join(' ')
}

const rendered = computed<RenderedSlice[]>(() => {
  if (!total.value) return []
  let start = -Math.PI / 2
  return props.slices.map((s, i) => {
    const pct = (s.value || 0) / total.value
    const end = start + pct * 2 * Math.PI
    const tone = s.tone ?? PALETTE[i % PALETTE.length]!
    const d = arcPath(start, end, radius.value, inner.value)
    start = end
    return { ...s, tone, color: toneVar(tone), pct, d }
  })
})

const isEmpty = computed(() => !total.value)
</script>

<template>
  <div class="flex flex-col gap-4 md:flex-row md:items-center">
    <div
      class="relative shrink-0 self-center"
      :style="{ width: `${size}px`, height: `${size}px` }"
    >
      <svg
        v-if="!isEmpty"
        :width="size"
        :height="size"
        :viewBox="`0 0 ${size} ${size}`"
        role="img"
        :aria-label="t('charts.donut.ariaLabel', { count: slices.length })"
      >
        <path
          v-for="s in rendered"
          :key="s.key"
          :d="s.d"
          :fill="s.color"
          :class="clickable ? 'cursor-pointer transition-opacity hover:opacity-80' : ''"
          @click="clickable && $emit('slice-click', s.key)"
        >
          <title>{{ s.label }}: {{ formatValue(s.value) }}</title>
        </path>
      </svg>
      <div
        v-else
        class="w-full h-full rounded-full border-2 border-dashed border-default flex items-center justify-center"
      >
        <UIcon
          name="i-lucide-pie-chart"
          class="w-6 h-6 text-subtle"
        />
      </div>
      <div
        v-if="!isEmpty"
        class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center"
      >
        <div
          v-if="centerLabel"
          class="text-caption text-muted"
        >
          {{ centerLabel }}
        </div>
        <div class="text-h2 text-default font-semibold tnum">
          {{ formatValue(total) }}
        </div>
      </div>
    </div>

    <ul class="flex-1 min-w-0 space-y-1.5">
      <li
        v-for="s in rendered"
        :key="s.key"
      >
        <component
          :is="clickable ? 'button' : 'div'"
          :type="clickable ? 'button' : undefined"
          class="w-full flex items-center gap-2 text-left group"
          :class="clickable ? 'cursor-pointer rounded-token-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]' : ''"
          @click="clickable && $emit('slice-click', s.key)"
        >
          <span
            class="w-2.5 h-2.5 rounded-full shrink-0"
            :style="{ backgroundColor: s.color }"
            aria-hidden="true"
          />
          <span
            class="text-ui text-default truncate flex-1"
            :class="clickable ? 'group-hover:text-[var(--color-primary)] transition-colors' : ''"
          >
            {{ s.label }}
          </span>
          <span
            v-if="s.hint"
            class="text-caption text-subtle tnum shrink-0"
          >
            {{ s.hint }}
          </span>
          <span class="text-ui text-default font-medium tnum tabular-nums shrink-0">
            {{ formatValue(s.value) }}
          </span>
        </component>
      </li>
    </ul>
  </div>
</template>
