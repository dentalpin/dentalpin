<script setup lang="ts">
import type {
  BudgetSummary,
  BudgetByProfessional,
  BudgetByTreatment,
  BudgetByStatus
} from '../../composables/useReports'
import type { UiColor } from '~~/app/config/severity'

const { t } = useI18n()
const router = useRouter()
const {
  fetchBudgetSummary,
  fetchBudgetsByProfessional,
  fetchBudgetsByTreatment,
  fetchBudgetsByStatus,
  formatCurrency,
  getBudgetStatusLabel,
  fetchFailed,
  resetFetchFailed
} = useReports()

// State
const isLoading = ref(false)
const summary = ref<BudgetSummary | null>(null)
const byProfessional = ref<BudgetByProfessional[]>([])
const byTreatment = ref<BudgetByTreatment[]>([])
const byStatus = ref<BudgetByStatus[]>([])

// Date range
const today = new Date()
const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1)
const dateFrom = ref(firstDayOfMonth.toISOString().slice(0, 10))
const dateTo = ref(today.toISOString().slice(0, 10))

// Quick date range options
const dateRangeOptions = computed(() => [
  { label: t('reports.billing.thisMonth'), value: 'month' },
  { label: t('reports.billing.thisQuarter'), value: 'quarter' },
  { label: t('reports.billing.thisYear'), value: 'year' },
  { label: t('reports.billing.lastMonth'), value: 'last_month' },
  { label: t('reports.billing.lastQuarter'), value: 'last_quarter' },
  { label: t('reports.billing.lastYear'), value: 'last_year' }
])
const selectedRange = ref('month')

watch(selectedRange, (range) => {
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

  dateFrom.value = from.toISOString().slice(0, 10)
  dateTo.value = to.toISOString().slice(0, 10)
})

// Load all report data
async function loadReports() {
  isLoading.value = true
  resetFetchFailed()

  try {
    const [summaryData, professionalsData, treatmentsData, statusData] = await Promise.all([
      fetchBudgetSummary(dateFrom.value, dateTo.value),
      fetchBudgetsByProfessional(dateFrom.value, dateTo.value),
      fetchBudgetsByTreatment(dateFrom.value, dateTo.value),
      fetchBudgetsByStatus(dateFrom.value, dateTo.value)
    ])

    summary.value = summaryData
    byProfessional.value = professionalsData
    byTreatment.value = treatmentsData
    byStatus.value = statusData
  } catch (e) {
    console.error('Failed to load budget reports:', e)
  } finally {
    isLoading.value = false
  }
}

// Reload when dates change
watch([dateFrom, dateTo], () => {
  loadReports()
})

onMounted(() => {
  loadReports()
})

// Format percentage
function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`
}

// Get status badge color
function getStatusBadgeColor(status: string): UiColor {
  const colors: Record<string, UiColor> = {
    draft: 'neutral',
    accepted: 'success',
    rejected: 'error',
    completed: 'info',
    expired: 'warning',
    cancelled: 'neutral'
  }
  return colors[status] || 'neutral'
}

function goBack() {
  router.push('/reports')
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-arrow-left"
          :aria-label="t('common.back')"
          @click="goBack"
        />
        <div>
          <h1 class="text-display text-default">
            {{ t('reports.budgets.title') }}
          </h1>
          <p class="text-caption text-subtle">
            {{ t('reports.budgets.description') }}
          </p>
        </div>
      </div>
    </div>

    <!-- Date Range Filters -->
    <UCard>
      <div class="flex flex-wrap items-end gap-4">
        <UFormField :label="t('reports.billing.period')">
          <USelectMenu
            v-model="selectedRange"
            :items="dateRangeOptions"
            value-key="value"
            class="w-48"
          />
        </UFormField>

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

        <UButton
          :loading="isLoading"
          @click="loadReports"
        >
          {{ t('reports.billing.refresh') }}
        </UButton>
      </div>
    </UCard>

    <!-- Loading state -->
    <div
      v-if="isLoading"
      class="flex justify-center py-12"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="h-8 w-8 animate-spin text-primary-accent"
      />
    </div>

    <!-- Load error — never render 0 € / empty charts for a failed read (issue #101). -->
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
      <!-- Summary Cards -->
      <div
        v-if="summary"
        class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <UCard>
          <div class="text-center">
            <p class="text-caption text-subtle">
              {{ t('reports.budgets.labels.totalCreated') }}
            </p>
            <p class="text-display text-default">
              {{ summary.total_created }}
            </p>
            <p class="text-caption text-subtle">
              {{ formatCurrency(summary.total_amount) }}
            </p>
          </div>
        </UCard>

        <UCard>
          <div class="text-center">
            <p class="text-caption text-subtle">
              {{ t('reports.budgets.labels.accepted') }}
            </p>
            <p class="text-display text-default text-success-accent">
              {{ summary.accepted_count }}
            </p>
            <p class="text-caption text-subtle">
              {{ formatCurrency(summary.accepted_amount) }}
            </p>
          </div>
        </UCard>

        <UCard>
          <div class="text-center">
            <p class="text-caption text-subtle">
              {{ t('reports.budgets.labels.acceptanceRate') }}
            </p>
            <p class="text-display text-default text-info-accent">
              {{ formatPercent(summary.acceptance_rate) }}
            </p>
            <p class="text-caption text-subtle">
              {{ summary.rejected_count }} {{ t('reports.budgets.labels.rejected') }}
            </p>
          </div>
        </UCard>

        <UCard>
          <div class="text-center">
            <p class="text-caption text-subtle">
              {{ t('reports.budgets.labels.averageValue') }}
            </p>
            <p class="text-display text-default">
              {{ formatCurrency(summary.average_value) }}
            </p>
            <p class="text-caption text-subtle">
              {{ summary.pending_count }} {{ t('reports.budgets.labels.pending') }}
            </p>
          </div>
        </UCard>
      </div>

      <!-- Completed Budget Info -->
      <div
        v-if="summary && summary.completed_count > 0"
        class="grid grid-cols-1 md:grid-cols-2 gap-4"
      >
        <UCard>
          <div class="text-center">
            <p class="text-caption text-subtle">
              {{ t('reports.budgets.labels.completed') }}
            </p>
            <p class="text-display text-default text-purple-600">
              {{ summary.completed_count }}
            </p>
            <p class="text-caption text-subtle">
              {{ formatCurrency(summary.completed_amount) }}
            </p>
          </div>
        </UCard>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- By Status -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('reports.budgets.labels.byStatus') }}
            </h3>
          </template>

          <div
            v-if="byStatus.length > 0"
            class="space-y-3"
          >
            <div
              v-for="item in byStatus"
              :key="item.status"
              class="flex items-center justify-between"
            >
              <div class="flex items-center gap-2">
                <UBadge
                  :color="getStatusBadgeColor(item.status)"
                  size="sm"
                >
                  {{ getBudgetStatusLabel(item.status) }}
                </UBadge>
              </div>
              <div class="text-right">
                <p class="font-semibold text-default">
                  {{ item.count }}
                </p>
                <p class="text-caption text-subtle">
                  {{ formatCurrency(item.total_amount) }}
                </p>
              </div>
            </div>
          </div>
          <p
            v-else
            class="text-subtle text-center py-4"
          >
            {{ t('reports.billing.noData') }}
          </p>
        </UCard>

        <!-- By Professional -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('reports.budgets.features.byProfessional') }}
            </h3>
          </template>

          <div
            v-if="byProfessional.length > 0"
            class="space-y-3"
          >
            <div
              v-for="prof in byProfessional"
              :key="prof.professional_id || 'unknown'"
              class="flex items-center justify-between"
            >
              <div class="flex items-center gap-2">
                <UAvatar
                  :alt="prof.professional_name"
                  size="sm"
                />
                <div>
                  <p class="text-muted">
                    {{ prof.professional_name }}
                  </p>
                  <p class="text-caption text-subtle">
                    {{ formatPercent(prof.acceptance_rate) }} {{ t('reports.budgets.labels.acceptanceRate').toLowerCase() }}
                  </p>
                </div>
              </div>
              <div class="text-right">
                <p class="font-semibold text-default">
                  {{ prof.budget_count }}
                </p>
                <p class="text-caption text-subtle">
                  {{ formatCurrency(prof.total_amount) }}
                </p>
              </div>
            </div>
          </div>
          <p
            v-else
            class="text-subtle text-center py-4"
          >
            {{ t('reports.billing.noData') }}
          </p>
        </UCard>

        <!-- By Treatment (Top 10) -->
        <UCard class="lg:col-span-2">
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('reports.budgets.labels.topTreatments') }}
            </h3>
          </template>

          <div
            v-if="byTreatment.length > 0"
            class="overflow-x-auto"
          >
            <table class="min-w-full divide-y divide-[var(--color-border-subtle)]">
              <thead>
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-medium text-subtle uppercase">
                    {{ t('reports.budgets.labels.treatment') }}
                  </th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-subtle uppercase">
                    {{ t('reports.budgets.labels.occurrences') }}
                  </th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-subtle uppercase">
                    {{ t('reports.budgets.labels.quantity') }}
                  </th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-subtle uppercase">
                    {{ t('invoice.total') }}
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[var(--color-border-subtle)]">
                <tr
                  v-for="treatment in byTreatment"
                  :key="treatment.catalog_item_id || treatment.treatment_name"
                >
                  <td class="px-3 py-2 text-sm text-muted">
                    {{ treatment.treatment_name }}
                  </td>
                  <td class="px-3 py-2 text-sm text-right text-muted">
                    {{ treatment.occurrence_count }}
                  </td>
                  <td class="px-3 py-2 text-sm text-right text-muted">
                    {{ treatment.total_quantity }}
                  </td>
                  <td class="px-3 py-2 text-sm text-right font-medium text-default">
                    {{ formatCurrency(treatment.total_amount) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p
            v-else
            class="text-subtle text-center py-4"
          >
            {{ t('reports.billing.noData') }}
          </p>
        </UCard>
      </div>
    </template>
  </div>
</template>
