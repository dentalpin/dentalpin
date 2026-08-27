<script setup lang="ts">
import type {
  AppointmentFunnel,
  CabinetUtilization,
  DayOfWeekStats,
  DurationVarianceStats,
  FirstVisitsSummary,
  HoursByProfessional,
  PunctualityStats,
  SchedulingSummary,
  WaitingTimeStats
} from '../../composables/useReports'

const { t } = useI18n()
const router = useRouter()
const {
  fetchSchedulingSummary,
  fetchFirstVisits,
  fetchHoursByProfessional,
  fetchCabinetUtilization,
  fetchByDayOfWeek,
  fetchWaitingTimes,
  fetchPunctuality,
  fetchDurationVariance,
  fetchFunnel,
  formatHours,
  getDayOfWeekLabel,
  fetchFailed,
  resetFetchFailed
} = useReports()

const { cabinets } = useClinic()
const {
  professionals,
  fetchProfessionals,
  getProfessionalColor,
  getProfessionalInitials,
  getProfessionalFullName
} = useProfessionals()

// ─── State ───────────────────────────────────────────────────────────
const isLoading = ref(false)
const summary = ref<SchedulingSummary | null>(null)
const firstVisits = ref<FirstVisitsSummary | null>(null)
const hoursByProfessional = ref<HoursByProfessional[]>([])
const cabinetUtilization = ref<CabinetUtilization[]>([])
const dayOfWeekStats = ref<DayOfWeekStats[]>([])
const waitingStats = ref<WaitingTimeStats | null>(null)
const punctuality = ref<PunctualityStats | null>(null)
const durationVariance = ref<DurationVarianceStats | null>(null)
const funnel = ref<AppointmentFunnel | null>(null)

// ─── Date range ──────────────────────────────────────────────────────
const today = new Date()
const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1)
const dateFrom = ref(firstDayOfMonth.toISOString().split('T')[0] as string)
const dateTo = ref(today.toISOString().split('T')[0] as string)

const dateRangeOptions = computed(() => [
  { label: t('reports.billing.thisMonth'), value: 'month' },
  { label: t('reports.billing.thisQuarter'), value: 'quarter' },
  { label: t('reports.billing.thisYear'), value: 'year' },
  { label: t('reports.billing.lastMonth'), value: 'last_month' },
  { label: t('reports.billing.lastQuarter'), value: 'last_quarter' },
  { label: t('reports.billing.lastYear'), value: 'last_year' },
  { label: t('reports.scheduling.filters.custom'), value: 'custom' }
])
const selectedRange = ref('month')

watch(selectedRange, (range) => {
  if (range === 'custom') return
  const now = new Date()
  let from: Date
  let to: Date

  switch (range) {
    case 'month':
      from = new Date(now.getFullYear(), now.getMonth(), 1)
      to = now
      break
    case 'quarter': {
      const quarter = Math.floor(now.getMonth() / 3)
      from = new Date(now.getFullYear(), quarter * 3, 1)
      to = now
      break
    }
    case 'year':
      from = new Date(now.getFullYear(), 0, 1)
      to = now
      break
    case 'last_month':
      from = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      to = new Date(now.getFullYear(), now.getMonth(), 0)
      break
    case 'last_quarter': {
      const lastQuarter = Math.floor(now.getMonth() / 3) - 1
      const year = lastQuarter < 0 ? now.getFullYear() - 1 : now.getFullYear()
      const q = lastQuarter < 0 ? 3 : lastQuarter
      from = new Date(year, q * 3, 1)
      to = new Date(year, q * 3 + 3, 0)
      break
    }
    case 'last_year':
      from = new Date(now.getFullYear() - 1, 0, 1)
      to = new Date(now.getFullYear() - 1, 11, 31)
      break
    default:
      return
  }

  dateFrom.value = from.toISOString().split('T')[0] as string
  dateTo.value = to.toISOString().split('T')[0] as string
})

// ─── Filters ─────────────────────────────────────────────────────────
const selectedCabinetId = ref<string | null>(null)
const selectedProfessionalId = ref<string | null>(null)

const analyticsFilters = computed(() => ({
  cabinetId: selectedCabinetId.value,
  professionalId: selectedProfessionalId.value
}))

// ─── Tabs ────────────────────────────────────────────────────────────
const activeTab = ref<'overview' | 'activity' | 'quality'>('overview')

const tabOptions = computed(() => [
  { value: 'overview', label: t('reports.scheduling.tabs.overview'), icon: 'i-lucide-layout-dashboard' },
  { value: 'activity', label: t('reports.scheduling.tabs.activity'), icon: 'i-lucide-activity' },
  { value: 'quality', label: t('reports.scheduling.tabs.quality'), icon: 'i-lucide-gauge' }
])

// ─── Data load ───────────────────────────────────────────────────────
async function loadReports() {
  isLoading.value = true
  resetFetchFailed()

  try {
    const [
      summaryData,
      firstVisitsData,
      hoursData,
      cabinetData,
      dayOfWeekData,
      waitData,
      punctualityData,
      durationData,
      funnelData
    ] = await Promise.all([
      fetchSchedulingSummary(dateFrom.value, dateTo.value),
      fetchFirstVisits(dateFrom.value, dateTo.value),
      fetchHoursByProfessional(dateFrom.value, dateTo.value),
      fetchCabinetUtilization(dateFrom.value, dateTo.value),
      fetchByDayOfWeek(dateFrom.value, dateTo.value),
      fetchWaitingTimes(dateFrom.value, dateTo.value, analyticsFilters.value),
      fetchPunctuality(dateFrom.value, dateTo.value, analyticsFilters.value),
      fetchDurationVariance(dateFrom.value, dateTo.value, analyticsFilters.value),
      fetchFunnel(dateFrom.value, dateTo.value, analyticsFilters.value)
    ])

    summary.value = summaryData
    firstVisits.value = firstVisitsData
    hoursByProfessional.value = hoursData
    cabinetUtilization.value = cabinetData
    dayOfWeekStats.value = dayOfWeekData
    waitingStats.value = waitData
    punctuality.value = punctualityData
    durationVariance.value = durationData
    funnel.value = funnelData
  } catch (e) {
    console.error('Failed to load scheduling reports:', e)
  } finally {
    isLoading.value = false
  }
}

watch([dateFrom, dateTo, selectedCabinetId, selectedProfessionalId], () => {
  loadReports()
})

onMounted(async () => {
  await fetchProfessionals()
  await loadReports()
})

// ─── Formatters ──────────────────────────────────────────────────────
function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(1)}%`
}

function formatMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const rounded = Math.round(value * 10) / 10
  return `${rounded} min`
}

function formatSignedMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${Math.round(value * 10) / 10} min`
}

// ─── Derived: hero ───────────────────────────────────────────────────
const noShowSurface = computed(() => {
  const rate = summary.value?.no_show_rate ?? 0
  return rate > 10 ? 'alert-surface-danger' : 'alert-surface-warning'
})

// ─── Derived: bar chart maxes ────────────────────────────────────────
const maxHours = computed(() =>
  Math.max(...hoursByProfessional.value.map(p => p.total_minutes), 1)
)
const maxCabinetMinutes = computed(() =>
  Math.max(...cabinetUtilization.value.map(c => c.total_minutes), 1)
)
const maxDayCount = computed(() =>
  Math.max(...dayOfWeekStats.value.map(d => d.appointment_count), 1)
)
const maxWaitBucket = computed(() => {
  if (!waitingStats.value) return 1
  return Math.max(...waitingStats.value.distribution.map(b => b.count), 1)
})
const maxPunctualityBucket = computed(() => {
  if (!punctuality.value) return 1
  return Math.max(...punctuality.value.distribution.map(b => b.count), 1)
})

// ─── Derived: funnel ─────────────────────────────────────────────────
const funnelStageLabels: Record<string, string> = {
  scheduled: 'appointments.status.scheduled',
  confirmed: 'appointments.status.confirmed',
  checked_in: 'appointments.status.checked_in',
  in_treatment: 'appointments.status.in_treatment',
  completed: 'appointments.status.completed',
  cancelled: 'appointments.status.cancelled',
  no_show: 'appointments.status.no_show'
}

const funnelRows = computed(() => {
  if (!funnel.value) return []
  const order: Array<keyof typeof funnelStageLabels> = [
    'scheduled',
    'confirmed',
    'checked_in',
    'in_treatment',
    'completed',
    'cancelled',
    'no_show'
  ]
  const max = Math.max(...Object.values(funnel.value.counts_by_status), 1)
  return order.map(stage => ({
    stage,
    labelKey: funnelStageLabels[stage] as string,
    count: funnel.value!.counts_by_status[stage] ?? 0,
    widthPct: ((funnel.value!.counts_by_status[stage] ?? 0) / max) * 100
  }))
})

// ─── Cabinet chips ───────────────────────────────────────────────────
const cabinetChips = computed(() =>
  cabinets.value.map(c => ({
    id: c.id,
    label: c.name,
    color: c.color
  }))
)

function toggleCabinet(id: string) {
  selectedCabinetId.value = selectedCabinetId.value === id ? null : id
}

function toggleProfessional(id: string) {
  selectedProfessionalId.value = selectedProfessionalId.value === id ? null : id
}

function clearFilters() {
  selectedCabinetId.value = null
  selectedProfessionalId.value = null
}

const hasActiveAnalyticsFilter = computed(() =>
  selectedCabinetId.value !== null || selectedProfessionalId.value !== null
)

function goBack() {
  router.push('/reports')
}
</script>

<template>
  <div class="space-y-6">
    <!-- Page header -->
    <PageHeader
      :title="t('reports.scheduling.title')"
      :subtitle="t('reports.scheduling.description')"
    >
      <template #actions>
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-arrow-left"
          @click="goBack"
        >
          {{ t('common.back') }}
        </UButton>
      </template>
    </PageHeader>

    <!-- Filter bar -->
    <div class="space-y-3">
      <div class="flex flex-wrap items-end gap-3">
        <UFormField :label="t('reports.billing.period')">
          <USelectMenu
            v-model="selectedRange"
            :items="dateRangeOptions"
            value-key="value"
            class="w-48"
          />
        </UFormField>

        <template v-if="selectedRange === 'custom'">
          <UFormField :label="t('reports.billing.from')">
            <UInput
              v-model="dateFrom"
              type="date"
            />
          </UFormField>
          <UFormField :label="t('reports.billing.to')">
            <UInput
              v-model="dateTo"
              type="date"
            />
          </UFormField>
        </template>

        <div class="ml-auto flex items-center gap-2">
          <UButton
            v-if="hasActiveAnalyticsFilter"
            variant="ghost"
            color="neutral"
            icon="i-lucide-x"
            size="sm"
            @click="clearFilters"
          >
            {{ t('reports.scheduling.filters.clear') }}
          </UButton>
          <UButton
            :loading="isLoading"
            variant="soft"
            icon="i-lucide-refresh-cw"
            @click="loadReports"
          >
            {{ t('reports.billing.refresh') }}
          </UButton>
        </div>
      </div>

      <!-- Cabinet & professional chips -->
      <div
        v-if="cabinetChips.length > 0 || professionals.length > 0"
        class="flex flex-col gap-2"
      >
        <div
          v-if="cabinetChips.length > 0"
          class="flex flex-wrap items-center gap-1.5"
        >
          <span class="text-caption text-subtle mr-1">
            {{ t('reports.scheduling.filters.cabinet') }}
          </span>
          <FilterChip
            :label="t('reports.scheduling.filters.all')"
            :selected="selectedCabinetId === null"
            @toggle="selectedCabinetId = null"
          />
          <FilterChip
            v-for="c in cabinetChips"
            :key="c.id"
            :label="c.label"
            :selected="selectedCabinetId === c.id"
            :color="c.color"
            @toggle="toggleCabinet(c.id)"
          />
        </div>

        <div
          v-if="professionals.length > 0"
          class="flex flex-wrap items-center gap-1.5"
        >
          <span class="text-caption text-subtle mr-1">
            {{ t('reports.scheduling.filters.professional') }}
          </span>
          <FilterChip
            :label="t('reports.scheduling.filters.all')"
            :selected="selectedProfessionalId === null"
            @toggle="selectedProfessionalId = null"
          />
          <FilterChip
            v-for="p in professionals"
            :key="p.id"
            :label="getProfessionalFullName(p)"
            :selected="selectedProfessionalId === p.id"
            :color="getProfessionalColor(p.id)"
            :initials="getProfessionalInitials(p)"
            @toggle="toggleProfessional(p.id)"
          />
        </div>
      </div>
    </div>

    <!-- Skeleton (first load only) -->
    <div
      v-if="isLoading && !summary"
      class="space-y-6"
    >
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <USkeleton
          v-for="i in 4"
          :key="i"
          class="h-24 rounded-token-lg"
        />
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <USkeleton class="h-64 rounded-token-lg" />
        <USkeleton class="h-64 rounded-token-lg" />
      </div>
      <USkeleton class="h-48 rounded-token-lg" />
    </div>

    <!-- Load error — never render 0 / empty stats for a failed read (issue #101). -->
    <UAlert
      v-else-if="fetchFailed"
      icon="i-lucide-triangle-alert"
      color="error"
      variant="subtle"
      :title="t('reports.loadError')"
      :actions="[{
        label: t('common.retry'),
        color: 'error',
        variant: 'soft',
        onClick: () => loadReports()
      }]"
    />

    <template v-else>
      <!-- Hero strip -->
      <div
        v-if="summary"
        class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3"
      >
        <div class="bg-surface-muted rounded-token-md px-4 py-3">
          <p class="text-caption text-subtle">
            {{ t('reports.scheduling.labels.totalAppointments') }}
          </p>
          <p class="text-display text-default tnum">
            {{ summary.total_appointments }}
          </p>
          <p class="text-caption text-subtle">
            {{ t('reports.scheduling.hero.inPeriod') }}
          </p>
        </div>

        <div class="alert-surface-success rounded-token-md px-4 py-3">
          <p class="text-caption opacity-75">
            {{ t('reports.scheduling.labels.completionRate') }}
          </p>
          <p class="text-display tnum">
            {{ formatPercent(summary.completion_rate) }}
          </p>
          <p class="text-caption opacity-75">
            {{ summary.completed }} {{ t('reports.scheduling.labels.completed') }}
          </p>
        </div>

        <div
          :class="noShowSurface"
          class="rounded-token-md px-4 py-3"
        >
          <p class="text-caption opacity-75">
            {{ t('reports.scheduling.labels.noShowRate') }}
          </p>
          <p class="text-display tnum">
            {{ formatPercent(summary.no_show_rate) }}
          </p>
          <p class="text-caption opacity-75">
            {{ summary.no_show }} {{ t('reports.scheduling.labels.noShows') }}
          </p>
        </div>

        <div class="alert-surface-info rounded-token-md px-4 py-3">
          <p class="text-caption opacity-75">
            {{ t('reports.scheduling.features.firstVisits') }}
          </p>
          <p class="text-display tnum">
            {{ firstVisits?.new_patients ?? 0 }}
          </p>
          <p class="text-caption opacity-75">
            {{ formatPercent(firstVisits?.first_visit_rate) }} {{ t('reports.scheduling.labels.ofTotalAppointments') }}
          </p>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex items-center">
        <SegmentedControl
          v-model="activeTab"
          :options="tabOptions"
          size="md"
        />
      </div>

      <!-- Overview tab -->
      <div
        v-if="activeTab === 'overview'"
        class="space-y-6"
      >
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- Hours by professional -->
          <SectionCard
            icon="i-lucide-user-round"
            icon-role="primary"
            :title="t('reports.scheduling.features.hoursWorked')"
          >
            <div
              v-if="hoursByProfessional.length > 0"
              class="space-y-1"
            >
              <ListRow
                v-for="prof in hoursByProfessional"
                :key="prof.professional_id || 'unknown'"
              >
                <template #leading>
                  <UAvatar
                    :alt="prof.professional_name"
                    size="sm"
                  />
                </template>
                <template #title>
                  {{ prof.professional_name }}
                </template>
                <template #subtitle>
                  <span class="tnum">{{ prof.appointment_count }}</span>
                  {{ t('reports.scheduling.labels.appointments') }}
                  <span class="mx-1 text-subtle">·</span>
                  <span class="text-success-accent tnum">{{ prof.completed_count }} ✓</span>
                  <span class="text-danger-accent tnum ml-1">{{ prof.cancelled_count }} ✗</span>
                  <span class="text-warning-accent tnum ml-1">{{ prof.no_show_count }} ⊘</span>
                </template>
                <template #meta>
                  <div class="flex flex-col items-end gap-1 w-24">
                    <span class="text-ui text-default font-semibold tnum">
                      {{ formatHours(prof.total_minutes) }}
                    </span>
                    <div class="w-full h-1 rounded-full bg-surface-sunken overflow-hidden">
                      <div
                        class="h-full bg-[var(--color-primary)] transition-all"
                        :style="{ width: `${(prof.total_minutes / maxHours) * 100}%` }"
                      />
                    </div>
                  </div>
                </template>
              </ListRow>
            </div>
            <EmptyState
              v-else
              icon="i-lucide-users"
              :title="t('reports.scheduling.empty.title')"
              :description="t('reports.scheduling.empty.desc')"
            />
          </SectionCard>

          <!-- Cabinet utilization -->
          <SectionCard
            icon="i-lucide-armchair"
            icon-role="primary"
            :title="t('reports.scheduling.features.cabinetUtilization')"
          >
            <div
              v-if="cabinetUtilization.length > 0"
              class="space-y-1"
            >
              <ListRow
                v-for="cabinet in cabinetUtilization"
                :key="cabinet.cabinet"
              >
                <template #leading>
                  <UIcon
                    name="i-lucide-armchair"
                    class="h-5 w-5 text-muted"
                  />
                </template>
                <template #title>
                  {{ cabinet.cabinet }}
                </template>
                <template #subtitle>
                  <span class="tnum">{{ cabinet.appointment_count }}</span>
                  {{ t('reports.scheduling.labels.appointments') }}
                  <span class="mx-1 text-subtle">·</span>
                  <span class="text-success-accent tnum">{{ cabinet.completed_count }}</span>
                  {{ t('reports.scheduling.labels.completed') }}
                </template>
                <template #meta>
                  <div class="flex flex-col items-end gap-1 w-24">
                    <span class="text-ui text-default font-semibold tnum">
                      {{ formatHours(cabinet.total_minutes) }}
                    </span>
                    <div class="w-full h-1 rounded-full bg-surface-sunken overflow-hidden">
                      <div
                        class="h-full bg-[var(--color-primary)] transition-all"
                        :style="{ width: `${(cabinet.total_minutes / maxCabinetMinutes) * 100}%` }"
                      />
                    </div>
                  </div>
                </template>
              </ListRow>
            </div>
            <EmptyState
              v-else
              icon="i-lucide-armchair"
              :title="t('reports.scheduling.empty.title')"
              :description="t('reports.scheduling.empty.desc')"
            />
          </SectionCard>
        </div>

        <!-- Day of week -->
        <SectionCard
          icon="i-lucide-calendar-days"
          icon-role="primary"
          :title="t('reports.scheduling.labels.byDayOfWeek')"
        >
          <template #actions>
            <div class="flex items-center gap-3 text-caption">
              <span class="flex items-center gap-1 text-muted">
                <span class="w-2.5 h-2.5 rounded-full bg-[var(--color-success-accent)]" />
                {{ t('reports.scheduling.labels.completed') }}
              </span>
              <span class="flex items-center gap-1 text-muted">
                <span class="w-2.5 h-2.5 rounded-full bg-[var(--color-danger-accent)]" />
                {{ t('reports.scheduling.labels.cancelled') }}
              </span>
              <span class="flex items-center gap-1 text-muted">
                <span class="w-2.5 h-2.5 rounded-full bg-[var(--color-warning-accent)]" />
                {{ t('reports.scheduling.labels.noShows') }}
              </span>
            </div>
          </template>

          <div
            v-if="dayOfWeekStats.length > 0"
            class="space-y-2"
          >
            <div
              v-for="day in dayOfWeekStats"
              :key="day.day_of_week"
              class="flex items-center gap-3"
            >
              <div class="w-24 text-ui text-muted">
                {{ getDayOfWeekLabel(day.day_name) }}
              </div>
              <div class="flex-1 bg-surface-sunken rounded-full h-3 overflow-hidden">
                <div
                  class="flex h-3"
                  :style="{ width: `${(day.appointment_count / maxDayCount) * 100}%` }"
                >
                  <div
                    v-if="day.completed_count > 0"
                    class="bg-[var(--color-success-accent)] transition-all"
                    :style="{ width: `${(day.completed_count / day.appointment_count) * 100}%` }"
                    :title="`${day.completed_count} ${t('reports.scheduling.labels.completed')}`"
                  />
                  <div
                    v-if="day.cancelled_count > 0"
                    class="bg-[var(--color-danger-accent)] transition-all"
                    :style="{ width: `${(day.cancelled_count / day.appointment_count) * 100}%` }"
                    :title="`${day.cancelled_count} ${t('reports.scheduling.labels.cancelled')}`"
                  />
                  <div
                    v-if="day.no_show_count > 0"
                    class="bg-[var(--color-warning-accent)] transition-all"
                    :style="{ width: `${(day.no_show_count / day.appointment_count) * 100}%` }"
                    :title="`${day.no_show_count} ${t('reports.scheduling.labels.noShows')}`"
                  />
                  <div
                    v-if="day.appointment_count - day.completed_count - day.cancelled_count - day.no_show_count > 0"
                    class="bg-[var(--color-border-strong)] transition-all"
                    :style="{ width: `${((day.appointment_count - day.completed_count - day.cancelled_count - day.no_show_count) / day.appointment_count) * 100}%` }"
                    :title="`${day.appointment_count - day.completed_count - day.cancelled_count - day.no_show_count} ${t('reports.scheduling.labels.pending')}`"
                  />
                </div>
              </div>
              <span class="w-10 text-right text-ui text-default tnum">
                {{ day.appointment_count }}
              </span>
            </div>
          </div>
          <EmptyState
            v-else
            icon="i-lucide-calendar-days"
            :title="t('reports.scheduling.empty.title')"
            :description="t('reports.scheduling.empty.desc')"
          />
        </SectionCard>
      </div>

      <!-- Activity tab -->
      <div
        v-if="activeTab === 'activity'"
        class="space-y-6"
      >
        <SectionCard
          v-if="funnel"
          icon="i-lucide-filter"
          icon-role="primary"
          :title="t('reports.scheduling.analytics.funnel')"
        >
          <template #subtitle>
            {{ t('reports.scheduling.analytics.funnelDesc') }}
          </template>

          <div
            v-if="funnel.total > 0"
            class="space-y-2"
          >
            <div
              v-for="row in funnelRows"
              :key="row.stage"
              class="flex items-center gap-3"
            >
              <span class="w-32 text-ui text-muted">
                {{ t(row.labelKey) }}
              </span>
              <div class="flex-1 bg-surface-sunken rounded-full h-3 overflow-hidden">
                <div
                  class="h-full bg-[var(--color-primary)] transition-all"
                  :style="{ width: `${row.widthPct}%` }"
                />
              </div>
              <span class="w-10 text-right text-ui text-default tnum">
                {{ row.count }}
              </span>
            </div>
          </div>
          <EmptyState
            v-else
            icon="i-lucide-filter"
            :title="t('reports.scheduling.empty.title')"
            :description="t('reports.scheduling.empty.desc')"
          />

          <template #footer>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
              <div>
                <p class="text-caption text-subtle">
                  {{ t('reports.scheduling.analytics.completionRate') }}
                </p>
                <p class="text-h2 text-success-accent tnum">
                  {{ formatPercent(funnel.completion_rate) }}
                </p>
              </div>
              <div>
                <p class="text-caption text-subtle">
                  {{ t('reports.scheduling.analytics.noShowRate') }}
                </p>
                <p class="text-h2 text-danger-accent tnum">
                  {{ formatPercent(funnel.no_show_rate) }}
                </p>
              </div>
              <div>
                <p class="text-caption text-subtle">
                  {{ t('reports.scheduling.analytics.cancellationRate') }}
                </p>
                <p class="text-h2 text-warning-accent tnum">
                  {{ formatPercent(funnel.cancellation_rate) }}
                </p>
              </div>
            </div>
          </template>
        </SectionCard>
      </div>

      <!-- Quality tab -->
      <div
        v-if="activeTab === 'quality'"
        class="space-y-6"
      >
        <!-- Waiting times -->
        <SectionCard
          v-if="waitingStats"
          icon="i-lucide-hourglass"
          icon-role="primary"
          :title="t('reports.scheduling.analytics.waitingTimes')"
        >
          <template #subtitle>
            {{ t('reports.scheduling.analytics.waitingTimesDesc') }}
          </template>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.samples') }}
              </p>
              <p class="text-h1 text-default tnum">
                {{ waitingStats.sample_size }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.average') }}
              </p>
              <p class="text-h1 text-default tnum">
                {{ formatMinutes(waitingStats.avg_minutes) }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.median') }}
              </p>
              <p class="text-h1 text-default tnum">
                {{ formatMinutes(waitingStats.median_minutes) }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.p90') }}
              </p>
              <p class="text-h1 text-default tnum">
                {{ formatMinutes(waitingStats.p90_minutes) }}
              </p>
            </div>
          </div>

          <div
            v-if="waitingStats.sample_size > 0"
            class="space-y-2"
          >
            <div
              v-for="bucket in waitingStats.distribution"
              :key="bucket.label"
              class="flex items-center gap-3"
            >
              <span class="w-20 text-ui text-muted tnum">
                {{ bucket.label }} min
              </span>
              <div class="flex-1 bg-surface-sunken rounded-full h-2 overflow-hidden">
                <div
                  class="h-full bg-[var(--color-primary)] transition-all"
                  :style="{ width: `${(bucket.count / maxWaitBucket) * 100}%` }"
                />
              </div>
              <span class="w-10 text-right text-ui text-default tnum">
                {{ bucket.count }}
              </span>
            </div>
          </div>
          <EmptyState
            v-else
            icon="i-lucide-hourglass"
            :title="t('reports.scheduling.empty.title')"
            :description="t('reports.scheduling.empty.desc')"
          />
        </SectionCard>

        <!-- Punctuality -->
        <SectionCard
          v-if="punctuality"
          icon="i-lucide-clock"
          icon-role="info"
          :title="t('reports.scheduling.analytics.punctuality')"
        >
          <template #subtitle>
            {{ t('reports.scheduling.analytics.punctualityDesc') }}
          </template>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.samples') }}
              </p>
              <p class="text-h1 text-default tnum">
                {{ punctuality.sample_size }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.avgDelta') }}
              </p>
              <p class="text-h1 text-default tnum">
                {{ formatSignedMinutes(punctuality.avg_delta_minutes) }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.medianDelta') }}
              </p>
              <p class="text-h1 text-default tnum">
                {{ formatSignedMinutes(punctuality.median_delta_minutes) }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.onTime') }}
              </p>
              <p class="text-h1 text-success-accent tnum">
                {{ formatPercent(punctuality.on_time_pct) }}
              </p>
            </div>
          </div>

          <div
            v-if="punctuality.sample_size > 0"
            class="space-y-2"
          >
            <div
              v-for="bucket in punctuality.distribution"
              :key="bucket.label"
              class="flex items-center gap-3"
            >
              <span class="w-28 text-ui text-muted">
                {{ t(`reports.scheduling.analytics.punctuality_${bucket.label}`) }}
              </span>
              <div class="flex-1 bg-surface-sunken rounded-full h-2 overflow-hidden">
                <div
                  class="h-full bg-[var(--color-info-accent)] transition-all"
                  :style="{ width: `${(bucket.count / maxPunctualityBucket) * 100}%` }"
                />
              </div>
              <span class="w-10 text-right text-ui text-default tnum">
                {{ bucket.count }}
              </span>
            </div>
          </div>
          <EmptyState
            v-else
            icon="i-lucide-clock"
            :title="t('reports.scheduling.empty.title')"
            :description="t('reports.scheduling.empty.desc')"
          />
        </SectionCard>

        <!-- Duration variance -->
        <SectionCard
          v-if="durationVariance"
          icon="i-lucide-gauge"
          icon-role="warning"
          :title="t('reports.scheduling.analytics.durationVariance')"
        >
          <template #subtitle>
            {{ t('reports.scheduling.analytics.durationVarianceDesc') }}
          </template>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.samples') }}
              </p>
              <p class="text-h1 text-default tnum">
                {{ durationVariance.sample_size }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.avgOverrun') }}
              </p>
              <p class="text-h1 text-default tnum">
                {{ formatPercent(durationVariance.avg_overrun_pct) }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.overrunCount') }}
              </p>
              <p class="text-h1 text-warning-accent tnum">
                {{ durationVariance.overrun_count }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('reports.scheduling.analytics.underCount') }}
              </p>
              <p class="text-h1 text-success-accent tnum">
                {{ durationVariance.under_count }}
              </p>
            </div>
          </div>
        </SectionCard>
      </div>
    </template>
  </div>
</template>
