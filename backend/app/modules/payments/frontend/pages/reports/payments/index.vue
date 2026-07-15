<script setup lang="ts">
/**
 * /reports/payments — payment reports dashboard.
 *
 * Calm-design composition over the six payment report endpoints
 * (summary, trends, by-method, by-professional, aging-receivables,
 * refunds). Every interactive surface drills down to a filtered
 * /payments (or /patients) list so the dashboard becomes the entry
 * point, not a dead end.
 *
 * Off-books invariant: no KPI in this page subtracts paid from
 * invoiced or earned from invoiced. See payments/CLAUDE.md gotchas
 * and ADR 0010.
 */
import type {
  PaymentsSummary,
  PaymentsTrends,
  MethodBreakdown,
  ProfessionalBreakdown,
  AgingBuckets,
  RefundsReport
} from '~~/app/types'

definePageMeta({ middleware: 'auth' })

const { t, locale } = useI18n()
const { format: formatMoney } = useCurrency()
const { summary, byMethod, byProfessional, aging, refunds, trends } = usePaymentReports()

type Granularity = 'day' | 'week' | 'month'

interface Range {
  from: string | null
  to: string | null
}

function toIso(d: Date) {
  return d.toISOString().slice(0, 10)
}

function defaultRange(): Range {
  const to = new Date()
  const from = new Date()
  from.setDate(to.getDate() - 89)
  return { from: toIso(from), to: toIso(to) }
}

const range = ref<Range>(defaultRange())
const granularity = ref<Granularity>('month')

const summaryData = ref<PaymentsSummary | null>(null)
const previousSummary = ref<PaymentsSummary | null>(null)
const methodsData = ref<MethodBreakdown[]>([])
const profData = ref<ProfessionalBreakdown[]>([])
const agingData = ref<AgingBuckets | null>(null)
const refundsData = ref<RefundsReport | null>(null)
const trendsData = ref<PaymentsTrends | null>(null)

const loadingPrimary = ref(false)
const loadingTrends = ref(false)

const dateRangeQuery = computed(() => {
  const q: Record<string, string> = {}
  if (range.value.from) q.date_from = range.value.from
  if (range.value.to) q.date_to = range.value.to
  return q
})

function previousRange(r: Range): Range | null {
  if (!r.from || !r.to) return null
  const from = new Date(r.from)
  const to = new Date(r.to)
  const span = to.getTime() - from.getTime()
  if (span < 0) return null
  const prevTo = new Date(from.getTime() - 86_400_000)
  const prevFrom = new Date(prevTo.getTime() - span)
  return { from: toIso(prevFrom), to: toIso(prevTo) }
}

const delta = computed(() => {
  if (!summaryData.value || !previousSummary.value) return null
  const now = Number(summaryData.value.net_collected || 0)
  const prev = Number(previousSummary.value.net_collected || 0)
  if (prev === 0) return now > 0 ? { pct: null, direction: 'up' as const } : null
  const pct = ((now - prev) / Math.abs(prev)) * 100
  return { pct, direction: pct >= 0 ? ('up' as const) : ('down' as const) }
})

const granularityOptions = computed(() => [
  { value: 'day', label: t('payments.reports.granularity.day') },
  { value: 'week', label: t('payments.reports.granularity.week') },
  { value: 'month', label: t('payments.reports.granularity.month') }
])

async function refreshPrimary() {
  if (!range.value.from || !range.value.to) return
  loadingPrimary.value = true
  const [s, m, p, a, r] = await Promise.all([
    summary(range.value.from, range.value.to),
    byMethod(range.value.from, range.value.to),
    byProfessional(range.value.from, range.value.to),
    aging(),
    refunds(range.value.from, range.value.to)
  ])
  summaryData.value = s
  methodsData.value = m
  profData.value = p
  agingData.value = a
  refundsData.value = r
  loadingPrimary.value = false
}

async function refreshTrends() {
  if (!range.value.from || !range.value.to) return
  loadingTrends.value = true
  trendsData.value = await trends(range.value.from, range.value.to, granularity.value)
  loadingTrends.value = false
}

async function refreshDelta() {
  const prev = previousRange(range.value)
  if (!prev || !prev.from || !prev.to) {
    previousSummary.value = null
    return
  }
  previousSummary.value = await summary(prev.from, prev.to)
}

async function refreshAll() {
  await Promise.all([refreshPrimary(), refreshTrends(), refreshDelta()])
}

onMounted(() => {
  refreshAll()
})

watch(range, () => {
  refreshPrimary()
  refreshTrends()
  refreshDelta()
}, { deep: true })

watch(granularity, () => {
  refreshTrends()
})

// --- Aging derivations --------------------------------------------------

const agingTotal = computed(() => {
  if (!agingData.value) return 0
  return agingData.value.buckets.reduce((acc, b) => acc + Number(b.total || 0), 0)
})

const agingMaxBucket = computed(() => {
  if (!agingData.value) return 0
  return Math.max(1, ...agingData.value.buckets.map((b) => Number(b.total || 0)))
})

function agingToneFor(label: string): 'success' | 'info' | 'warning' | 'danger' {
  // Backend labels are bucket boundaries like "0-30", "31-60", "61-90", "90+".
  if (label.startsWith('0')) return 'success'
  if (label.startsWith('31')) return 'info'
  if (label.startsWith('61')) return 'warning'
  return 'danger'
}


// --- Method palette -----------------------------------------------------
//
// Stable mapping so the donut and the drill-down badge always agree.
const METHOD_TONE: Record<string, 'primary' | 'success' | 'info' | 'warning' | 'danger' | 'neutral'> = {
  card: 'primary',
  cash: 'success',
  bank_transfer: 'info',
  direct_debit: 'warning',
  insurance: 'danger',
  other: 'neutral'
}

const methodSlices = computed(() =>
  methodsData.value.map((m) => ({
    key: m.method,
    label: t(`payments.methods.${m.method}`),
    value: Number(m.total || 0),
    hint: t('payments.reports.countShort', { n: m.count }),
    tone: METHOD_TONE[m.method] ?? 'neutral'
  }))
)

// --- Professionals derivation -------------------------------------------

const topProfessionals = computed(() => profData.value.slice(0, 8))

const professionalMax = computed(() =>
  Math.max(1, ...topProfessionals.value.map((p) => Number(p.total_earned || 0)))
)

const refundMax = computed(() => {
  if (!refundsData.value) return 0
  return Math.max(1, ...refundsData.value.by_reason.map((r) => Number(r.total || 0)))
})

// --- Trends derivation --------------------------------------------------

const trendSeries = computed(() => {
  if (!trendsData.value) return []
  return trendsData.value.points.map((p) => ({ x: p.bucket_start, y: Number(p.net || 0) }))
})

const trendRefundsSeries = computed(() => {
  if (!trendsData.value) return []
  return trendsData.value.points.map((p) => ({ x: p.bucket_start, y: Number(p.refunded || 0) }))
})

const heroSparkline = computed(() => trendSeries.value.map((p) => p.y))

function formatBucketLabel(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const opts: Intl.DateTimeFormatOptions =
    granularity.value === 'day'
      ? { day: '2-digit', month: 'short' }
      : granularity.value === 'week'
        ? { day: '2-digit', month: 'short' }
        : { month: 'short', year: '2-digit' }
  return d.toLocaleDateString(locale.value, opts)
}

// --- Drill-down navigation ---------------------------------------------

function goToPaymentsList(extra: Record<string, string> = {}) {
  navigateTo({ path: '/payments', query: { ...dateRangeQuery.value, ...extra } })
}

function goToPatientsWithDebt() {
  // /patients list owns the threshold (currently hardcoded to 0.01
  // when `with_debt` is on). Aging buckets all map to the same query.
  navigateTo({ path: '/patients', query: { with_debt: 'true' } })
}

function onMethodClick(method: string) {
  goToPaymentsList({ method })
}

function onTrendPointClick(bucketIso: string) {
  // Single-point drill-down: anchor the list date range to this bucket.
  // Width depends on granularity.
  const start = new Date(bucketIso)
  if (Number.isNaN(start.getTime())) return
  const end = new Date(start)
  if (granularity.value === 'day') end.setDate(start.getDate() + 1)
  else if (granularity.value === 'week') end.setDate(start.getDate() + 7)
  else end.setMonth(start.getMonth() + 1)
  end.setDate(end.getDate() - 1)
  navigateTo({
    path: '/payments',
    query: { date_from: toIso(start), date_to: toIso(end) }
  })
}

// --- Empty / loading helpers -------------------------------------------

const allReportsEmpty = computed(() => {
  if (loadingPrimary.value) return false
  if (!summaryData.value) return true
  return (
    Number(summaryData.value.total_collected || 0) === 0 &&
    Number(summaryData.value.total_refunded || 0) === 0 &&
    !methodsData.value.length &&
    !profData.value.length &&
    (!refundsData.value || !refundsData.value.by_reason.length)
  )
})
</script>

<template>
  <div class="space-y-6 p-4 md:p-6 max-w-7xl mx-auto">
    <PageHeader
      :title="t('payments.reports.title')"
      :subtitle="t('payments.reports.subtitle')"
    >
      <template #actions>
        <FilterDateRange v-model="range" />
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-refresh-cw"
          size="sm"
          :loading="loadingPrimary || loadingTrends"
          :aria-label="t('payments.reports.refresh')"
          @click="refreshAll"
        />
      </template>
    </PageHeader>

    <!-- HERO ROW -->
    <div class="grid gap-4 md:grid-cols-2">
      <!-- Net collected hero -->
      <SectionCard
        icon="i-lucide-trending-up"
        icon-role="success"
        :title="t('payments.reports.hero.netCollected')"
      >
        <template #subtitle>
          {{ t('payments.reports.hero.netCollectedHint') }}
        </template>
        <template #actions>
          <UButton
            variant="ghost"
            color="neutral"
            size="xs"
            icon="i-lucide-arrow-right"
            :aria-label="t('payments.reports.drilldown.viewPayments')"
            :title="t('payments.reports.drilldown.viewPayments')"
            @click="goToPaymentsList()"
          />
        </template>

        <div
          v-if="loadingPrimary && !summaryData"
          class="space-y-3"
        >
          <USkeleton class="h-9 w-40" />
          <USkeleton class="h-9 w-full" />
        </div>
        <template v-else>
          <div class="flex items-baseline gap-3 flex-wrap">
            <Money
              :value="summaryData?.net_collected"
              strong
              class="text-display"
            />
            <div
              v-if="delta && delta.pct !== null"
              class="text-ui tnum"
              :class="delta.direction === 'up' ? 'text-[var(--color-success-accent)]' : 'text-[var(--color-danger-accent)]'"
            >
              <UIcon
                :name="delta.direction === 'up' ? 'i-lucide-arrow-up-right' : 'i-lucide-arrow-down-right'"
                class="w-3.5 h-3.5 inline -mt-0.5"
              />
              {{ Math.abs(delta.pct).toFixed(1) }}%
              <span class="text-subtle">{{ t('payments.reports.hero.vsPrevious') }}</span>
            </div>
          </div>
          <div class="mt-3 -mb-1">
            <Sparkline
              :points="heroSparkline"
              :height="44"
              tone="success"
              :aria-label="t('payments.reports.hero.netCollected')"
            />
          </div>
          <div class="mt-2 text-caption text-muted tnum">
            {{ t('payments.reports.hero.transactionsCount', { n: summaryData?.payment_count ?? 0 }) }}
          </div>
        </template>
      </SectionCard>

      <!-- Receivable hero -->
      <SectionCard
        icon="i-lucide-clock"
        icon-role="warning"
        :title="t('payments.reports.hero.receivable')"
      >
        <template #subtitle>
          {{ t('payments.reports.hero.receivableHint') }}
        </template>

        <div
          v-if="loadingPrimary && !summaryData"
          class="space-y-3"
        >
          <USkeleton class="h-9 w-40" />
          <USkeleton class="h-16 w-full" />
        </div>
        <template v-else>
          <Money
            :value="summaryData?.clinic_receivable_total"
            strong
            class="text-display"
          />
          <div
            v-if="agingData && agingTotal > 0"
            class="mt-3 grid grid-cols-4 gap-2"
          >
            <button
              v-for="b in agingData.buckets"
              :key="b.label"
              type="button"
              class="rounded-token-sm border border-default p-2 text-center hover:border-[var(--color-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] transition-colors"
              :aria-label="t('payments.reports.drilldown.viewPatients')"
              @click="goToPatientsWithDebt()"
            >
              <div class="text-caption text-muted">{{ t('payments.reports.bucket', { range: b.label }) }}</div>
              <div class="text-ui font-medium text-default tnum mt-0.5">
                {{ formatMoney(b.total) }}
              </div>
              <div class="text-caption text-subtle tnum">
                {{ b.patient_count }}
              </div>
              <div
                class="mt-1 h-1 rounded-full"
                :style="{
                  width: '100%',
                  background: 'var(--color-surface-muted)'
                }"
              >
                <div
                  class="h-full rounded-full"
                  :style="{
                    width: `${(Number(b.total) / agingMaxBucket) * 100}%`,
                    backgroundColor: agingToneFor(b.label) === 'success' ? 'var(--color-success-accent)'
                      : agingToneFor(b.label) === 'info' ? 'var(--color-info-accent)'
                        : agingToneFor(b.label) === 'warning' ? 'var(--color-warning-accent)'
                          : 'var(--color-danger-accent)'
                  }"
                />
              </div>
            </button>
          </div>
          <div
            v-else
            class="mt-3 text-caption text-muted"
          >
            {{ t('payments.reports.empty.noReceivable') }}
          </div>
        </template>
      </SectionCard>
    </div>

    <!-- Empty banner if nothing in range -->
    <SectionCard
      v-if="allReportsEmpty"
      no-header
    >
      <EmptyState
        icon="i-lucide-calendar-x"
        :title="t('payments.reports.empty.noDataTitle')"
        :description="t('payments.reports.empty.noDataDescription')"
      />
    </SectionCard>

    <template v-else>
      <!-- SECONDARY KPIS -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button
          type="button"
          class="text-left rounded-token-md bg-surface border border-default p-3 hover:border-[var(--color-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] transition-colors"
          @click="goToPaymentsList()"
        >
          <div class="text-caption text-muted">{{ t('payments.reports.collected') }}</div>
          <Money
            :value="summaryData?.total_collected"
            strong
            class="text-h2"
          />
          <div class="mt-1">
            <Sparkline
              :points="trendsData?.points.map(p => Number(p.collected)) ?? []"
              :height="20"
              tone="primary"
            />
          </div>
        </button>

        <button
          type="button"
          class="text-left rounded-token-md bg-surface border border-default p-3 hover:border-[var(--color-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] transition-colors"
          @click="goToPaymentsList({ has_refunds: 'true' })"
        >
          <div class="text-caption text-muted">{{ t('payments.reports.refunded') }}</div>
          <Money
            :value="summaryData?.total_refunded"
            strong
            class="text-h2"
          />
          <div class="mt-1">
            <Sparkline
              :points="trendsData?.points.map(p => Number(p.refunded)) ?? []"
              :height="20"
              tone="danger"
            />
          </div>
        </button>

        <div class="rounded-token-md bg-surface border border-default p-3">
          <div class="text-caption text-muted">{{ t('payments.reports.patientCredit') }}</div>
          <Money
            :value="summaryData?.patient_credit_total"
            strong
            class="text-h2"
          />
          <div class="mt-1 text-caption text-subtle">
            {{ t('payments.reports.patientCreditHint') }}
          </div>
        </div>

        <div class="rounded-token-md bg-surface border border-default p-3">
          <div class="text-caption text-muted">{{ t('payments.reports.refundRatio') }}</div>
          <div class="text-h2 font-semibold text-default tnum">
            {{ ((summaryData?.refund_ratio ?? 0) * 100).toFixed(1) }}%
          </div>
          <div class="mt-1 text-caption text-subtle tnum">
            {{ summaryData?.refund_count ?? 0 }} / {{ summaryData?.payment_count ?? 0 }}
          </div>
        </div>
      </div>

      <!-- TREND -->
      <SectionCard
        icon="i-lucide-line-chart"
        icon-role="primary"
        :title="t('payments.reports.trend.title')"
      >
        <template #subtitle>
          {{ t('payments.reports.trend.subtitle') }}
        </template>
        <template #actions>
          <SegmentedControl
            v-model="granularity"
            :options="granularityOptions"
          />
        </template>

        <div
          v-if="loadingTrends && !trendsData"
        >
          <USkeleton class="h-[220px] w-full" />
        </div>
        <EmptyState
          v-else-if="!trendSeries.length"
          icon="i-lucide-line-chart"
          :title="t('payments.reports.empty.noTrend')"
        />
        <TrendAreaChart
          v-else
          :series="trendSeries"
          :comparison="trendRefundsSeries"
          tone="primary"
          comparison-tone="danger"
          :format-y="formatMoney"
          :format-x="formatBucketLabel"
          :series-label="t('payments.reports.net')"
          :comparison-label="t('payments.reports.refunded')"
          @point-click="onTrendPointClick"
        />
      </SectionCard>

      <!-- TWO COLUMN: METHOD + PROFESSIONAL -->
      <div class="grid gap-4 md:grid-cols-2">
        <SectionCard
          icon="i-lucide-credit-card"
          icon-role="info"
          :title="t('payments.reports.byMethod')"
        >
          <div
            v-if="loadingPrimary && !methodsData.length"
            class="space-y-2"
          >
            <USkeleton class="h-[168px] w-full" />
          </div>
          <EmptyState
            v-else-if="!methodSlices.length"
            icon="i-lucide-credit-card"
            :title="t('payments.reports.empty.noMethods')"
          />
          <DonutChart
            v-else
            :slices="methodSlices"
            :format-value="formatMoney"
            :center-label="t('payments.reports.collected')"
            clickable
            @slice-click="onMethodClick"
          />
        </SectionCard>

        <SectionCard
          icon="i-lucide-stethoscope"
          icon-role="success"
          :title="t('payments.reports.byProfessional')"
        >
          <template #subtitle>
            {{ t('payments.reports.byProfessionalHint') }}
          </template>
          <div
            v-if="loadingPrimary && !profData.length"
            class="space-y-2"
          >
            <USkeleton
              v-for="i in 4"
              :key="i"
              class="h-9 w-full"
            />
          </div>
          <EmptyState
            v-else-if="!topProfessionals.length"
            icon="i-lucide-stethoscope"
            :title="t('payments.reports.empty.noProfessionals')"
          />
          <ul
            v-else
            class="space-y-3"
          >
            <li
              v-for="p in topProfessionals"
              :key="p.professional_id || 'unknown'"
            >
              <BarRow
                :value="Number(p.total_earned)"
                :max="professionalMax"
                :label="p.professional_name || t('payments.reports.unknownProfessional')"
                :value-label="formatMoney(p.total_earned)"
                :hint="t('payments.reports.countShort', { n: p.count })"
                tone="success"
                clickable
                :action-label="t('payments.reports.drilldown.viewPayments')"
                @click="goToPaymentsList()"
              />
            </li>
          </ul>
        </SectionCard>
      </div>

      <!-- AGING DETAIL -->
      <SectionCard
        v-if="agingData && agingTotal > 0"
        icon="i-lucide-hourglass"
        icon-role="warning"
        :title="t('payments.reports.aging')"
      >
        <template #subtitle>
          {{ t('payments.reports.agingHint') }}
        </template>
        <ul class="space-y-3">
          <li
            v-for="b in agingData.buckets"
            :key="b.label"
          >
            <BarRow
              :value="Number(b.total)"
              :max="agingMaxBucket"
              :label="t('payments.reports.bucket', { range: b.label })"
              :value-label="formatMoney(b.total)"
              :hint="t('payments.reports.countPatients', { n: b.patient_count })"
              :tone="agingToneFor(b.label)"
              clickable
              :action-label="t('payments.reports.drilldown.viewPatients')"
              @click="goToPatientsWithDebt()"
            />
          </li>
        </ul>
      </SectionCard>

      <!-- REFUNDS BY REASON -->
      <SectionCard
        v-if="refundsData && refundsData.by_reason.length"
        icon="i-lucide-rotate-ccw"
        icon-role="danger"
        :title="t('payments.reports.refunds')"
      >
        <template #subtitle>
          {{ t('payments.reports.refundsHint') }}
        </template>
        <ul class="space-y-3">
          <li
            v-for="r in refundsData.by_reason"
            :key="r.reason_code"
          >
            <BarRow
              :value="Number(r.total)"
              :max="refundMax"
              :label="t(`payments.refund.reasonCodes.${r.reason_code}`)"
              :value-label="formatMoney(r.total)"
              :hint="t('payments.reports.countShort', { n: r.count })"
              tone="danger"
              clickable
              :action-label="t('payments.reports.drilldown.viewPayments')"
              @click="goToPaymentsList({ has_refunds: 'true' })"
            />
          </li>
        </ul>
      </SectionCard>
    </template>
  </div>
</template>
