<script setup lang="ts">
import type { InvoiceListItem, InvoiceStatus, PaginatedResponse } from '~~/app/types'
import { INVOICE_STATUS_ROLE, roleToUiColor } from '~~/app/config/severity'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

/**
 * /invoices — list page.
 *
 * Preserves the existing compliance slots:
 *   - ``invoice.list.toolbar.filters`` (compliance modules inject the
 *     severity multi-select; billing only owns the param shape).
 *   - ``invoice.list.row.meta`` (compliance modules inject the per-row
 *     badge — verifactu / factur-x / etc).
 *
 * Adds date range to the main toolbar, server-side sort, and the
 * shared DataListLayout shell with card view on mobile.
 *
 * Stays off-books safe: balance_due is per-invoice — never compared
 * to payments-axis aggregates anywhere on this page.
 */

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const api = useApi()
const { can } = usePermissions()
const { currentClinic } = useClinic()
const { deleteInvoice, formatCurrency } = useInvoices()

function getStatusBadgeColor(status: InvoiceStatus) {
  return roleToUiColor(INVOICE_STATUS_ROLE[status] ?? 'neutral')
}

// --- Filters --------------------------------------------------------------
interface InvoiceListFilters {
  q: string
  status: string[]
  overdue: boolean
  compliance_severity: string[]
  date_from: string | null
  date_to: string | null
  is_credit_note: boolean
}

const defaults: InvoiceListFilters = {
  q: '',
  status: [],
  overdue: false,
  compliance_severity: [],
  date_from: null,
  date_to: null,
  is_credit_note: false
}

async function fetcher(q: {
  filters: InvoiceListFilters
  page: number
  pageSize: number
  sort: string
}) {
  const params = new URLSearchParams()
  params.set('page', String(q.page))
  params.set('page_size', String(q.pageSize))
  if (q.filters.q) params.set('search', q.filters.q)
  for (const s of q.filters.status) params.append('status', s)
  if (q.filters.overdue) params.set('overdue', 'true')
  for (const c of q.filters.compliance_severity) params.append('compliance_severity', c)
  if (q.filters.date_from) params.set('date_from', q.filters.date_from)
  if (q.filters.date_to) params.set('date_to', q.filters.date_to)
  if (q.filters.is_credit_note) params.set('is_credit_note', 'true')
  if (q.sort) params.set('sort', q.sort)

  const response = await api.get<PaginatedResponse<InvoiceListItem>>(
    `/api/v1/billing/invoices?${params.toString()}`
  )
  return { data: response.data, total: response.total }
}

const {
  filters,
  page,
  pageSize,
  sort,
  rows: invoices,
  total,
  totalPages,
  isLoading,
  error,
  setFilter,
  resetFilters
} = useListQuery<InvoiceListFilters, InvoiceListItem>({
  defaults,
  pageSize: 20,
  sortable: ['issue_date', 'due_date', 'total', 'created_at', 'invoice_number'],
  defaultSort: 'created_at:desc',
  searchKey: 'q',
  fetcher
})

const statusItems = computed(() => [
  { label: t('invoice.status.draft'), value: 'draft' as InvoiceStatus },
  { label: t('invoice.status.issued'), value: 'issued' as InvoiceStatus },
  { label: t('invoice.status.partial'), value: 'partial' as InvoiceStatus },
  { label: t('invoice.status.paid'), value: 'paid' as InvoiceStatus },
  { label: t('invoice.status.cancelled'), value: 'cancelled' as InvoiceStatus },
  { label: t('invoice.status.voided'), value: 'voided' as InvoiceStatus }
])

const sortOptions = computed(() => [
  { field: 'created_at', label: t('invoice.sortFields.created'), defaultDir: 'desc' as const },
  { field: 'issue_date', label: t('invoice.sortFields.issueDate'), defaultDir: 'desc' as const },
  { field: 'due_date', label: t('invoice.sortFields.dueDate'), defaultDir: 'asc' as const },
  { field: 'total', label: t('invoice.sortFields.total'), defaultDir: 'desc' as const }
])

const dateRange = computed({
  get: () => ({ from: filters.value.date_from, to: filters.value.date_to }),
  set: (v: { from: string | null, to: string | null }) => {
    setFilter('date_from', v.from)
    setFilter('date_to', v.to)
  }
})

function applyComplianceSeverity(next: string[]) {
  setFilter('compliance_severity', next)
}

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.value.status.length) n++
  if (filters.value.overdue) n++
  if (filters.value.compliance_severity.length) n++
  if (filters.value.date_from || filters.value.date_to) n++
  if (filters.value.is_credit_note) n++
  return n
})

function formatDate(s: string | undefined | null): string {
  if (!s) return '—'
  return new Date(s).toLocaleDateString(locale.value)
}

function patientName(inv: InvoiceListItem): string {
  if (!inv.patient) return '—'
  return `${inv.patient.last_name}, ${inv.patient.first_name}`
}

function isOverdue(inv: InvoiceListItem): boolean {
  if (!inv.due_date) return false
  if (!['issued', 'partial'].includes(inv.status)) return false
  return new Date(inv.due_date) < new Date()
}

function daysOverdue(inv: InvoiceListItem): number {
  if (!inv.due_date) return 0
  const ms = Date.now() - new Date(inv.due_date).getTime()
  return Math.max(0, Math.floor(ms / (24 * 3600 * 1000)))
}

function createInvoice() {
  router.push('/invoices/new')
}

async function handleDelete(inv: InvoiceListItem, ev: Event) {
  ev.preventDefault()
  ev.stopPropagation()
  if (inv.status !== 'draft') {
    toast.add({
      title: t('common.error'),
      description: t('invoice.errors.canOnlyDeleteDraft'),
      color: 'error'
    })
    return
  }
  if (!confirm(t('invoice.confirmations.delete'))) return
  try {
    await deleteInvoice(inv.id)
    toast.add({ title: t('common.success'), description: t('invoice.messages.deleted'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('invoice.errors.delete')), color: 'error' })
  }
}
</script>

<template>
  <DataListLayout
    :title="t('invoice.title')"
    :loading="isLoading"
    :empty="!invoices.length"
    :error="error"
    :page="page"
    :page-size="pageSize"
    :total="total"
    :total-pages="totalPages"
    @update:page="(v) => (page = v)"
  >
    <template #actions>
      <UButton
        v-if="can(PERMISSIONS.billing.write)"
        color="primary"
        variant="solid"
        icon="i-lucide-plus"
        @click="createInvoice"
      >
        {{ t('invoice.new') }}
      </UButton>
    </template>

    <template #toolbar>
      <FilterBar
        :active-count="activeFilterCount"
        @reset="resetFilters"
      >
        <template #search>
          <SearchBar
            :model-value="filters.q"
            :placeholder="t('invoice.searchPlaceholder')"
            max-width="max-w-sm"
            @update:model-value="(v) => setFilter('q', v)"
          />
        </template>

        <FilterChipMulti
          :model-value="filters.status"
          :items="statusItems"
          :label="t('invoice.filters.allStatuses')"
          icon="i-lucide-circle-dot"
          @update:model-value="(v) => setFilter('status', v)"
        />

        <FilterToggle
          :model-value="filters.overdue"
          :label="t('invoice.filters.overdueOnly')"
          icon="i-lucide-clock-alert"
          @update:model-value="(v) => setFilter('overdue', Boolean(v))"
        />

        <FilterDateRange v-model="dateRange" />

        <!-- Compliance severity (verifactu, factur-x, …) -->
        <ModuleSlot
          name="invoice.list.toolbar.filters"
          :ctx="{
            severity: filters.compliance_severity,
            onChange: applyComplianceSeverity,
            clinic: currentClinic
          }"
        />

        <template #right>
          <SortMenu
            :model-value="sort"
            :options="sortOptions"
            @update:model-value="(v) => (sort = v)"
          />
        </template>
      </FilterBar>
    </template>

    <template #empty>
      <EmptyState
        icon="i-lucide-receipt"
        :title="activeFilterCount || filters.q ? t('invoice.noItems') : t('invoice.empty')"
      >
        <template
          v-if="!activeFilterCount && !filters.q && can(PERMISSIONS.billing.write)"
          #actions
        >
          <UButton
            color="primary"
            variant="solid"
            icon="i-lucide-plus"
            @click="createInvoice"
          >
            {{ t('invoice.emptyAction') }}
          </UButton>
        </template>
      </EmptyState>
    </template>

    <template #rows>
      <DataListItem
        v-for="invoice in invoices"
        :key="invoice.id"
        :to="`/invoices/${invoice.id}`"
      >
        <template #row>
          <div class="flex-1 min-w-0 flex items-center gap-3">
            <div class="min-w-0 flex-1">
              <div class="text-ui text-default flex items-center gap-2 flex-wrap">
                <span class="tnum">{{ invoice.invoice_number || t('invoice.draftNoNumber') }}</span>
                <UBadge
                  :color="getStatusBadgeColor(invoice.status)"
                  variant="subtle"
                  size="xs"
                >
                  {{ t(`invoice.status.${invoice.status}`) }}
                </UBadge>
                <StatusBadge
                  v-if="isOverdue(invoice)"
                  role="danger"
                  :label="t('invoice.overdue')"
                  size="xs"
                  dot
                />
                <ModuleSlot
                  name="invoice.list.row.meta"
                  :ctx="{ invoice, clinic: currentClinic }"
                />
              </div>
              <div class="text-caption text-subtle truncate">
                {{ patientName(invoice) }}
              </div>
            </div>
          </div>
          <div class="shrink-0 flex items-center gap-3 text-right">
            <span class="hidden lg:inline text-caption text-subtle tnum">
              {{ formatDate(invoice.issue_date) }}
            </span>
            <span
              class="hidden md:inline text-caption tnum"
              :class="isOverdue(invoice) ? 'text-danger font-medium' : 'text-subtle'"
            >
              {{ formatDate(invoice.due_date) }}
            </span>
            <div class="text-right">
              <Money
                :value="invoice.total"
                strong
              />
              <div
                v-if="invoice.balance_due > 0 && invoice.status !== 'draft'"
                class="text-caption text-warning tnum"
              >
                {{ t('invoice.balance') }}: {{ formatCurrency(invoice.balance_due) }}
              </div>
            </div>
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <UButton
              v-if="invoice.status === 'draft' && can(PERMISSIONS.billing.admin)"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              size="xs"
              :aria-label="t('invoice.delete')"
              :title="t('invoice.delete')"
              @click="handleDelete(invoice, $event)"
            />
            <UIcon
              name="i-lucide-chevron-right"
              class="text-subtle"
            />
          </div>
        </template>

        <template #card>
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="font-medium text-default truncate flex items-center gap-2 flex-wrap">
                <span class="tnum">{{ invoice.invoice_number || t('invoice.draftNoNumber') }}</span>
                <UBadge
                  :color="getStatusBadgeColor(invoice.status)"
                  variant="subtle"
                  size="xs"
                >
                  {{ t(`invoice.status.${invoice.status}`) }}
                </UBadge>
                <ModuleSlot
                  name="invoice.list.row.meta"
                  :ctx="{ invoice, clinic: currentClinic }"
                />
              </div>
              <div class="text-caption text-subtle truncate">
                {{ patientName(invoice) }}
              </div>
            </div>
            <div class="text-right shrink-0">
              <Money
                :value="invoice.total"
                strong
              />
              <div
                v-if="invoice.balance_due > 0 && invoice.status !== 'draft'"
                class="text-caption text-warning tnum"
              >
                {{ t('invoice.balance') }}: {{ formatCurrency(invoice.balance_due) }}
              </div>
            </div>
          </div>
          <div class="flex items-center justify-between gap-2 text-caption text-subtle">
            <span>
              {{ formatDate(invoice.issue_date) }}
            </span>
            <span
              v-if="invoice.due_date"
              :class="isOverdue(invoice) ? 'text-danger font-medium' : ''"
            >
              {{ isOverdue(invoice)
                ? t('invoice.overdueByDays', { days: daysOverdue(invoice) })
                : formatDate(invoice.due_date) }}
            </span>
          </div>
        </template>
      </DataListItem>
    </template>
  </DataListLayout>
</template>
