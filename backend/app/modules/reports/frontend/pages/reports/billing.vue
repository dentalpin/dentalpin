<script setup lang="ts">
import type {
  BillingSummary,
  NumberingGap,
  OverdueInvoice,
  PaymentMethodSummary,
  ProfessionalBillingSummary,
  VatSummaryItem
} from '~~/app/types'

const { t, locale } = useI18n()
const router = useRouter()
const {
  fetchBillingSummary,
  fetchOverdueInvoices,
  fetchByPaymentMethod,
  fetchBillingByProfessional,
  fetchVatSummary,
  fetchNumberingGaps,
  formatCurrency,
  getPaymentMethodLabel
} = useReports()

// State
const isLoading = ref(false)
const summary = ref<BillingSummary | null>(null)
const overdueInvoices = ref<OverdueInvoice[]>([])
const paymentMethods = ref<PaymentMethodSummary[]>([])
const professionals = ref<ProfessionalBillingSummary[]>([])
const vatSummary = ref<VatSummaryItem[]>([])
const numberingGaps = ref<NumberingGap[]>([])

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

  try {
    const [
      summaryData,
      overdueData,
      paymentMethodsData,
      professionalsData,
      vatData,
      gapsData
    ] = await Promise.all([
      fetchBillingSummary(dateFrom.value, dateTo.value),
      fetchOverdueInvoices(),
      fetchByPaymentMethod(dateFrom.value, dateTo.value),
      fetchBillingByProfessional(dateFrom.value, dateTo.value),
      fetchVatSummary(dateFrom.value, dateTo.value),
      fetchNumberingGaps()
    ])

    summary.value = summaryData
    overdueInvoices.value = overdueData
    paymentMethods.value = paymentMethodsData
    professionals.value = professionalsData
    vatSummary.value = vatData
    numberingGaps.value = gapsData
  } catch (e) {
    console.error('Failed to load reports:', e)
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

// Format date
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(locale.value, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

// Get payment method icon
function getPaymentMethodIcon(method: string): string {
  const icons: Record<string, string> = {
    cash: 'i-lucide-banknote',
    card: 'i-lucide-credit-card',
    bank_transfer: 'i-lucide-building-2',
    direct_debit: 'i-lucide-repeat',
    other: 'i-lucide-circle'
  }
  return icons[method] || 'i-lucide-circle'
}

// Navigate to invoice
function goToInvoice(id: string) {
  router.push(`/invoices/${id}`)
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
            {{ t('reports.billing.title') }}
          </h1>
          <p class="text-caption text-subtle">
            {{ t('reports.billing.description') }}
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

    <template v-else>
      <!-- Summary Cards -->
      <div
        v-if="summary"
        class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <UCard>
          <div class="text-center">
            <p class="text-caption text-subtle">
              {{ t('reports.billing.totalInvoiced') }}
            </p>
            <p class="text-display text-default">
              {{ formatCurrency(summary.total_invoiced) }}
            </p>
            <p class="text-caption text-subtle">
              {{ summary.invoice_count }} {{ t('reports.billing.invoices') }}
            </p>
          </div>
        </UCard>

        <UCard>
          <div class="text-center">
            <p class="text-caption text-subtle">
              {{ t('reports.billing.totalCollected') }}
            </p>
            <p class="text-display text-default text-success-accent">
              {{ formatCurrency(summary.total_paid) }}
            </p>
            <p class="text-caption text-subtle">
              {{ summary.paid_count }} {{ t('reports.billing.paid') }}
            </p>
          </div>
        </UCard>

        <UCard>
          <div class="text-center">
            <p class="text-caption text-subtle">
              {{ t('reports.billing.pending') }}
            </p>
            <p class="text-display text-default text-warning-accent">
              {{ formatCurrency(summary.total_pending) }}
            </p>
          </div>
        </UCard>

        <UCard>
          <div class="text-center">
            <p class="text-caption text-subtle">
              {{ t('reports.billing.overdue') }}
            </p>
            <p
              class="text-display text-default"
              :class="summary.overdue_count > 0 ? 'text-danger-accent' : 'text-default'"
            >
              {{ summary.overdue_count }}
            </p>
            <p class="text-caption text-subtle">
              {{ t('reports.billing.invoices') }}
            </p>
          </div>
        </UCard>
      </div>

      <!-- Numbering Gaps Alert -->
      <UAlert
        v-if="numberingGaps.length > 0"
        color="warning"
        icon="i-lucide-alert-triangle"
        :title="t('reports.billing.gapsDetected')"
      >
        <template #description>
          <div class="space-y-1">
            <div
              v-for="gap in numberingGaps"
              :key="`${gap.series_prefix}-${gap.year}`"
              class="text-sm"
            >
              {{ gap.series_prefix }}-{{ gap.year }}:
              {{ t('reports.billing.missingNumbers') }}
              <span class="font-mono">{{ gap.missing_numbers.join(', ') }}</span>
            </div>
          </div>
        </template>
      </UAlert>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Payment Methods -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('reports.billing.byPaymentMethod') }}
            </h3>
          </template>

          <div
            v-if="paymentMethods.length > 0"
            class="space-y-3"
          >
            <div
              v-for="pm in paymentMethods"
              :key="pm.payment_method"
              class="flex items-center justify-between"
            >
              <div class="flex items-center gap-2">
                <UIcon
                  :name="getPaymentMethodIcon(pm.payment_method)"
                  class="h-5 w-5 text-subtle"
                />
                <span class="text-muted">
                  {{ getPaymentMethodLabel(pm.payment_method) }}
                </span>
              </div>
              <div class="text-right">
                <p class="font-semibold text-default">
                  {{ formatCurrency(pm.total_amount) }}
                </p>
                <p class="text-caption text-subtle">
                  {{ pm.payment_count }} {{ t('reports.billing.payments') }}
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

        <!-- VAT Summary -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('reports.billing.vatSummary') }}
            </h3>
          </template>

          <div
            v-if="vatSummary.length > 0"
            class="overflow-x-auto"
          >
            <table class="min-w-full divide-y divide-[var(--color-border-subtle)]">
              <thead>
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-medium text-subtle uppercase">
                    {{ t('reports.billing.vatType') }}
                  </th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-subtle uppercase">
                    {{ t('reports.billing.base') }}
                  </th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-subtle uppercase">
                    {{ t('reports.billing.tax') }}
                  </th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-subtle uppercase">
                    {{ t('invoice.total') }}
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[var(--color-border-subtle)]">
                <tr
                  v-for="vat in vatSummary"
                  :key="vat.vat_type_id || 'exempt'"
                >
                  <td class="px-3 py-2 text-sm text-muted">
                    {{ vat.vat_name }} ({{ vat.vat_rate }}%)
                  </td>
                  <td class="px-3 py-2 text-sm text-right text-muted">
                    {{ formatCurrency(vat.base_amount) }}
                  </td>
                  <td class="px-3 py-2 text-sm text-right text-muted">
                    {{ formatCurrency(vat.tax_amount) }}
                  </td>
                  <td class="px-3 py-2 text-sm text-right font-medium text-default">
                    {{ formatCurrency(vat.total_amount) }}
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

        <!-- Billing by Professional -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('reports.billing.byProfessional') }}
            </h3>
          </template>

          <div
            v-if="professionals.length > 0"
            class="space-y-3"
          >
            <div
              v-for="prof in professionals"
              :key="prof.professional_id"
              class="flex items-center justify-between"
            >
              <div class="flex items-center gap-2">
                <UAvatar
                  :alt="prof.professional_name"
                  size="sm"
                />
                <span class="text-muted">
                  {{ prof.professional_name }}
                </span>
              </div>
              <div class="text-right">
                <p class="font-semibold text-default">
                  {{ formatCurrency(prof.total_invoiced) }}
                </p>
                <p class="text-caption text-subtle">
                  {{ prof.invoice_count }} {{ t('reports.billing.invoices') }}
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

        <!-- Overdue Invoices -->
        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h3 class="font-semibold text-default">
                {{ t('reports.billing.overdueInvoices') }}
              </h3>
              <UBadge
                v-if="overdueInvoices.length > 0"
                color="error"
              >
                {{ overdueInvoices.length }}
              </UBadge>
            </div>
          </template>

          <div
            v-if="overdueInvoices.length > 0"
            class="divide-y divide-[var(--color-border-subtle)] max-h-80 overflow-y-auto"
          >
            <div
              v-for="inv in overdueInvoices"
              :key="inv.id"
              class="py-3 hover:bg-surface-muted cursor-pointer"
              @click="goToInvoice(inv.id)"
            >
              <div class="flex justify-between items-start">
                <div>
                  <p class="font-medium text-default">
                    {{ inv.invoice_number }}
                  </p>
                  <p class="text-caption text-subtle">
                    {{ inv.patient_name }}
                  </p>
                </div>
                <div class="text-right">
                  <p class="font-semibold text-danger-accent">
                    {{ formatCurrency(inv.balance_due) }}
                  </p>
                  <p class="text-xs text-danger-accent">
                    {{ inv.days_overdue }} {{ t('reports.billing.daysOverdue') }}
                  </p>
                </div>
              </div>
              <p class="text-xs text-subtle mt-1">
                {{ t('invoice.dueDate') }}: {{ formatDate(inv.due_date) }}
              </p>
            </div>
          </div>
          <div
            v-else
            class="text-center py-8"
          >
            <UIcon
              name="i-lucide-check-circle"
              class="h-12 w-12 text-success-accent mx-auto mb-2"
            />
            <p class="text-subtle">
              {{ t('reports.billing.noOverdue') }}
            </p>
          </div>
        </UCard>
      </div>
    </template>
  </div>
</template>
