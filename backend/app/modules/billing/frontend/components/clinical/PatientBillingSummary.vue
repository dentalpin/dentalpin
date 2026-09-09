<script setup lang="ts">
import type { PatientBillingSummary, InvoiceListItem, InvoicePaymentDetail, PaginatedResponse } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{
  patientId: string
}>()

const { t, locale } = useI18n()
const { can } = usePermissions()
const api = useApi()
const { fetchPatientSummary, fetchPayments, getPaymentMethodLabel } = useInvoices()

// State
const summary = ref<PatientBillingSummary | null>(null)
const invoices = ref<InvoiceListItem[]>([])
const invoicesTotal = ref(0)
const currentPage = ref(1)
const pageSize = 20
const totalPages = computed(() => Math.ceil(invoicesTotal.value / pageSize))
const isLoading = ref(true)
const expandedInvoices = ref<Set<string>>(new Set())
const invoicePayments = ref<Map<string, InvoicePaymentDetail[]>>(new Map())
const loadingPayments = ref<Set<string>>(new Set())

async function loadInvoices() {
  const params = new URLSearchParams({
    patient_id: props.patientId,
    page: String(currentPage.value),
    page_size: String(pageSize)
  })
  try {
    const response = await api.get<PaginatedResponse<InvoiceListItem>>(
      `/api/v1/billing/invoices?${params.toString()}`
    )
    invoices.value = response.data
    invoicesTotal.value = response.total
  } catch {
    invoices.value = []
    invoicesTotal.value = 0
  }
}

// Fetch data
async function loadData() {
  isLoading.value = true
  try {
    const [summaryData] = await Promise.all([
      fetchPatientSummary(props.patientId),
      loadInvoices()
    ])
    summary.value = summaryData
  } finally {
    isLoading.value = false
  }
}

watch(currentPage, loadInvoices)

// Toggle invoice expansion and load payments
async function toggleInvoice(invoiceId: string) {
  if (expandedInvoices.value.has(invoiceId)) {
    expandedInvoices.value.delete(invoiceId)
  } else {
    expandedInvoices.value.add(invoiceId)
    // Load payments if not already loaded
    if (!invoicePayments.value.has(invoiceId)) {
      loadingPayments.value.add(invoiceId)
      try {
        const payments = await fetchPayments(invoiceId)
        invoicePayments.value.set(invoiceId, payments)
      } finally {
        loadingPayments.value.delete(invoiceId)
      }
    }
  }
}

// Format currency — clinic-wide, no per-invoice override.
const { format: formatCurrency } = useCurrency()

// Format date
function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString(locale.value, {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit'
  })
}

// Status badge color
type BadgeColor = 'success' | 'warning' | 'neutral' | 'error' | 'info' | 'primary' | 'secondary'

function getInvoiceStatusColor(status: string): BadgeColor {
  switch (status) {
    case 'draft': return 'neutral'
    case 'issued': return 'info'
    case 'partial': return 'warning'
    case 'paid': return 'success'
    case 'cancelled':
    case 'voided': return 'error'
    default: return 'neutral'
  }
}

// Load data on mount
onMounted(loadData)

// Watch for patient changes
watch(() => props.patientId, () => {
  currentPage.value = 1
  loadData()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Loading state -->
    <div v-if="isLoading">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <USkeleton
          v-for="i in 6"
          :key="i"
          class="h-[72px] rounded-lg"
        />
      </div>
      <USkeleton class="h-8 w-32 mb-4" />
      <USkeleton class="h-12 w-full mb-2" />
      <USkeleton class="h-12 w-full mb-2" />
      <USkeleton class="h-12 w-full" />
    </div>

    <template v-else>
      <!-- Summary metrics - 3x2 grid -->
      <div
        v-if="summary"
        class="grid grid-cols-1 sm:grid-cols-3 gap-4"
      >
        <!-- Row 1: Budget metrics -->
        <div class="bg-surface-muted/50 rounded-lg p-4 border border-default">
          <p class="text-xs font-medium text-muted uppercase tracking-wide">
            {{ t('patientBilling.totalBudgeted') }}
          </p>
          <p class="text-display text-default text-default mt-1">
            {{ formatCurrency(summary.total_budgeted) }}
          </p>
          <p
            v-if="summary.total_discount > 0"
            class="text-caption text-success-accent tnum mt-1"
          >
            −{{ formatCurrency(summary.total_discount) }} {{ t('patientBilling.totalDiscount') }}
          </p>
        </div>

        <div class="alert-surface-info rounded-token-lg p-4">
          <p class="text-caption uppercase tracking-wide">
            {{ t('patientBilling.workInProgress') }}
          </p>
          <p class="text-display tnum mt-1">
            {{ formatCurrency(summary.work_in_progress) }}
          </p>
        </div>

        <div class="alert-surface-success rounded-token-lg p-4">
          <p class="text-caption uppercase tracking-wide">
            {{ t('patientBilling.workCompleted') }}
          </p>
          <p class="text-display tnum mt-1">
            {{ formatCurrency(summary.work_completed) }}
          </p>
        </div>

        <!-- Row 2: Invoice metrics -->
        <div class="bg-surface-muted/50 rounded-token-lg p-4 border border-default">
          <p class="text-caption text-muted uppercase tracking-wide">
            {{ t('patientBilling.totalInvoiced') }}
          </p>
          <p class="text-display tnum text-default mt-1">
            {{ formatCurrency(summary.total_invoiced) }}
          </p>
        </div>

        <div class="alert-surface-success rounded-token-lg p-4">
          <p class="text-caption uppercase tracking-wide">
            {{ t('patientBilling.totalPaid') }}
          </p>
          <p class="text-display tnum mt-1">
            {{ formatCurrency(summary.total_paid) }}
          </p>
        </div>

        <div
          :class="[
            'rounded-token-lg p-4',
            summary.balance_pending > 0
              ? 'alert-surface-warning'
              : 'bg-surface-muted/50 border border-default'
          ]"
        >
          <p
            :class="[
              'text-caption uppercase tracking-wide',
              summary.balance_pending > 0 ? '' : 'text-muted'
            ]"
          >
            {{ t('patientBilling.balancePending') }}
          </p>
          <p
            :class="[
              'text-display tnum mt-1',
              summary.balance_pending > 0 ? '' : 'text-default'
            ]"
          >
            {{ formatCurrency(summary.balance_pending) }}
          </p>
        </div>
      </div>

      <!-- Invoices section -->
      <div>
        <!-- Header -->
        <div class="flex items-center justify-between mb-4 pb-4 border-b border-default">
          <h3 class="text-base font-semibold text-default">
            {{ t('patientBilling.invoices') }}
          </h3>
          <UButton
            v-if="can(PERMISSIONS.billing.write)"
            :to="`/invoices/new?patient_id=${patientId}&from=patient`"
            icon="i-lucide-plus"
            size="sm"
          >
            {{ t('patientBilling.createInvoice') }}
          </UButton>
        </div>

        <!-- Empty state -->
        <div
          v-if="invoicesTotal === 0"
          class="text-center py-12 bg-surface-muted/30 rounded-lg"
        >
          <UIcon
            name="i-lucide-receipt"
            class="w-10 h-10 text-subtle mx-auto mb-3"
          />
          <p class="text-sm text-muted mb-4">
            {{ t('patientBilling.noInvoices') }}
          </p>
          <UButton
            v-if="can(PERMISSIONS.billing.write)"
            :to="`/invoices/new?patient_id=${patientId}&from=patient`"
            icon="i-lucide-plus"
            size="sm"
            variant="outline"
          >
            {{ t('patientBilling.createInvoice') }}
          </UButton>
        </div>

        <!-- Invoices table -->
        <div
          v-else
          class="border border-default rounded-lg overflow-hidden"
        >
          <table class="w-full">
            <thead class="bg-surface-muted/50">
              <tr>
                <th class="w-8 px-3 py-2" />
                <th class="px-3 py-2 text-start text-xs font-medium text-muted uppercase">
                  {{ t('invoice.invoiceNumber') }}
                </th>
                <th class="px-3 py-2 text-start text-xs font-medium text-muted uppercase">
                  {{ t('common.date') }}
                </th>
                <th class="px-3 py-2 text-start text-xs font-medium text-muted uppercase">
                  {{ t('budget.status.title') }}
                </th>
                <th class="px-3 py-2 text-end text-xs font-medium text-muted uppercase">
                  {{ t('invoice.total') }}
                </th>
                <th class="px-3 py-2 text-end text-xs font-medium text-muted uppercase">
                  {{ t('invoice.balance') }}
                </th>
                <th class="w-16 px-3 py-2" />
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--color-border-subtle)]">
              <template
                v-for="invoice in invoices"
                :key="invoice.id"
              >
                <!-- Invoice row -->
                <tr
                  class="hover:bg-surface-muted/30 cursor-pointer transition-colors"
                  @click="toggleInvoice(invoice.id)"
                >
                  <td class="px-3 py-3">
                    <UIcon
                      :name="expandedInvoices.has(invoice.id) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                      class="w-4 h-4 text-subtle"
                    />
                  </td>
                  <td class="px-3 py-3">
                    <span class="font-medium text-default">
                      {{ invoice.invoice_number || t('invoice.draftNoNumber') }}
                    </span>
                  </td>
                  <td class="px-3 py-3 text-sm text-muted">
                    {{ formatDate(invoice.issue_date || invoice.created_at) }}
                  </td>
                  <td class="px-3 py-3">
                    <UBadge
                      :color="getInvoiceStatusColor(invoice.status)"
                      variant="subtle"
                      size="xs"
                    >
                      {{ t(`invoice.status.${invoice.status}`) }}
                    </UBadge>
                  </td>
                  <td class="px-3 py-3 text-end font-medium text-default">
                    {{ formatCurrency(invoice.total) }}
                  </td>
                  <td class="px-3 py-3 text-end">
                    <span
                      :class="invoice.balance_due > 0 ? 'text-warning font-medium' : 'text-muted'"
                    >
                      {{ formatCurrency(invoice.balance_due) }}
                    </span>
                  </td>
                  <td class="px-3 py-3 text-end">
                    <NuxtLink
                      :to="`/invoices/${invoice.id}?from=patient&patientId=${patientId}`"
                      class="text-primary-accent hover:underline text-sm"
                      @click.stop
                    >
                      {{ t('invoice.view') }}
                    </NuxtLink>
                  </td>
                </tr>

                <!-- Expanded payments row -->
                <tr v-if="expandedInvoices.has(invoice.id)">
                  <td
                    colspan="7"
                    class="bg-surface-muted/30 px-4 py-3"
                  >
                    <!-- Loading payments -->
                    <div
                      v-if="loadingPayments.has(invoice.id)"
                      class="flex items-center gap-2 text-caption text-subtle ps-6"
                    >
                      <UIcon
                        name="i-lucide-loader-2"
                        class="w-4 h-4 animate-spin"
                      />
                      {{ t('common.loading') }}
                    </div>

                    <!-- No payments -->
                    <div
                      v-else-if="!invoicePayments.get(invoice.id)?.length"
                      class="text-sm text-muted ps-6"
                    >
                      {{ t('invoice.payments.noPayments') }}
                    </div>

                    <!-- Payments list -->
                    <div
                      v-else
                      class="ps-6 space-y-2"
                    >
                      <p class="text-xs font-medium text-muted uppercase mb-2">
                        {{ t('invoice.payments.title') }}
                      </p>
                      <div
                        v-for="link in invoicePayments.get(invoice.id)"
                        :key="link.id"
                        class="flex items-center gap-4 text-sm"
                      >
                        <span class="text-muted w-20">
                          {{ formatDate(link.payment.payment_date) }}
                        </span>
                        <span class="text-muted w-28">
                          {{ getPaymentMethodLabel(link.payment.method) }}
                        </span>
                        <span class="font-medium text-default">
                          {{ formatCurrency(link.amount) }}
                        </span>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <PaginationBar
          v-model:page="currentPage"
          :total-pages="totalPages"
          :total="invoicesTotal"
          :page-size="pageSize"
        />
      </div>
    </template>
  </div>
</template>
