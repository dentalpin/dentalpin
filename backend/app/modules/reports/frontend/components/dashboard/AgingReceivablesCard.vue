<script setup lang="ts">
import SummaryCard from '~~/app/components/shared/SummaryCard.vue'
import BarRow from '~~/app/components/charts/BarRow.vue'
import type { PaymentsAgingBuckets } from '../../composables/useReports'

type Tone = 'primary' | 'success' | 'danger' | 'info' | 'warning' | 'neutral'

const BUCKET_TONES: Record<string, Tone> = {
  '0-30': 'success',
  '31-60': 'warning',
  '61-90': 'danger',
  '90+': 'danger'
}

const BUCKET_KEYS: Record<string, string> = {
  '0-30': 'reports.dashboard.aging.bucket0_30',
  '31-60': 'reports.dashboard.aging.bucket31_60',
  '61-90': 'reports.dashboard.aging.bucket61_90',
  '90+': 'reports.dashboard.aging.bucket90plus'
}

interface Props {
  state: {
    loading: boolean
    error: boolean
    data: PaymentsAgingBuckets | null
  }
}

const props = defineProps<Props>()
const { t } = useI18n()
const { format } = useCurrency()

const buckets = computed(() => props.state.data?.buckets ?? [])

const maxTotal = computed(() =>
  buckets.value.reduce((acc, b) => Math.max(acc, parseFloat(b.total || '0')), 0)
)

const total = computed(() =>
  buckets.value.reduce((acc, b) => acc + parseFloat(b.total || '0'), 0)
)

const isEmpty = computed(() =>
  !props.state.loading && (buckets.value.length === 0 || total.value === 0)
)
</script>

<template>
  <SummaryCard
    :title="t('reports.dashboard.kpi.aging')"
    icon="i-lucide-alert-circle"
    severity="warning"
    to="/reports/billing"
    :loading="state.loading"
    :empty="isEmpty"
  >
    <template #header-trailing>
      <span class="ms-auto inline-flex items-center gap-1 text-caption text-subtle">
        <UIcon
          name="i-lucide-clock"
          class="w-3 h-3"
        />
        {{ t('reports.dashboard.snapshotBadge') }}
      </span>
    </template>
    <template #empty>
      {{ t('reports.dashboard.aging.empty') }}
    </template>

    <div class="space-y-3">
      <div class="text-h1 text-default font-semibold tnum tabular-nums">
        {{ format(total) }}
      </div>
      <ul class="space-y-3">
        <li
          v-for="b in buckets"
          :key="b.label"
        >
          <BarRow
            :value="parseFloat(b.total || '0')"
            :max="maxTotal || 1"
            :label="t(BUCKET_KEYS[b.label] ?? '') || b.label"
            :value-label="format(parseFloat(b.total || '0'))"
            :hint="t('reports.dashboard.aging.patientCount', { count: b.patient_count })"
            :tone="BUCKET_TONES[b.label] ?? 'neutral'"
          />
        </li>
      </ul>
    </div>
  </SummaryCard>
</template>
