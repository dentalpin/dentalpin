<script setup lang="ts">
import type { BudgetListItem, BudgetStatus, ApiResponse, PaginatedResponse } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

/**
 * /budgets — list page.
 *
 * Native filters (status, professional, validity, date range, search,
 * sort) hit ``GET /api/v1/budget/budgets`` directly.
 *
 * Cross-module enrichment (collected / pending / payment-status) is
 * rendered via the ``budget.list.row.payments`` slot — payments
 * registers the filler. The page bulk-fetches the summary after each
 * page load and passes it into ctx.
 *
 * Cross-module filter "Cobro" plugs into the ``budget.list.filter``
 * slot. The page translates it into a payments-side call that returns
 * ``budget_ids``; we intersect with /budgets via ``?budget_ids=``.
 *
 * Budget module never imports payments code — public HTTP only.
 */

interface BudgetPaymentSummary {
  collected: string
  pending: string
  payment_status: 'unpaid' | 'partial' | 'paid'
}

interface PatientBrief {
  id: string
  first_name: string
  last_name: string
}

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const api = useApi()
const { can } = usePermissions()
const { downloadPDF, deleteBudget } = useBudgets()

// --- Filters --------------------------------------------------------------
interface BudgetListFilters {
  q: string
  status: string[]
  payment_status: string[]
  assigned_professional_id: string | null
  validity: 'valid' | 'expiring' | 'expired' | ''
  date_from: string | null
  date_to: string | null
}

const defaults: BudgetListFilters = {
  q: '',
  status: [],
  payment_status: [],
  assigned_professional_id: null,
  validity: '',
  date_from: null,
  date_to: null
}

const summaries = ref<Record<string, BudgetPaymentSummary | null>>({})

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function inDaysIso(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

async function fetcher(q: {
  filters: BudgetListFilters
  page: number
  pageSize: number
  sort: string
}) {
  // Step 1: cross-module payment-status filter → budget_ids intersect.
  let budgetIdsIntersect: string[] | undefined
  if (q.filters.payment_status.length) {
    try {
      const search = new URLSearchParams()
      for (const s of q.filters.payment_status) search.append('status', s)
      const res = await api.get<ApiResponse<{ budget_ids: string[], truncated: boolean }>>(
        `/api/v1/payments/filters/budgets-by-status?${search.toString()}`
      )
      budgetIdsIntersect = res.data.budget_ids ?? []
      if (res.data.truncated) {
        toast.add({ title: t('lists.truncatedWarning'), color: 'warning' })
      }
      if (!budgetIdsIntersect.length) {
        summaries.value = {}
        return { data: [], total: 0 }
      }
    } catch {
      budgetIdsIntersect = undefined
    }
  }

  // Step 2: native /budgets query.
  const params = new URLSearchParams()
  params.set('page', String(q.page))
  params.set('page_size', String(q.pageSize))
  if (q.filters.q) params.set('search', q.filters.q)
  for (const s of q.filters.status) params.append('status', s)
  if (q.filters.assigned_professional_id) {
    params.set('assigned_professional_id', q.filters.assigned_professional_id)
  }
  if (q.filters.validity === 'expired') {
    params.set('expired', 'true')
  } else if (q.filters.validity === 'valid') {
    params.set('expired', 'false')
  } else if (q.filters.validity === 'expiring') {
    params.set('valid_until_after', todayIso())
    params.set('valid_until_before', inDaysIso(7))
  }
  if (q.filters.date_from) params.set('date_from', q.filters.date_from)
  if (q.filters.date_to) params.set('date_to', q.filters.date_to)
  if (budgetIdsIntersect) {
    for (const id of budgetIdsIntersect) params.append('budget_ids', id)
  }
  if (q.sort) params.set('sort', q.sort)

  const response = await api.get<PaginatedResponse<BudgetListItem>>(
    `/api/v1/budget/budgets?${params.toString()}`
  )

  // Step 3: bulk summaries enrichment.
  if (can(PERMISSIONS.payments.recordRead) && response.data.length) {
    try {
      const summaryRes = await api.post<ApiResponse<{ summaries: Record<string, BudgetPaymentSummary> }>>(
        '/api/v1/payments/summary/by-budgets',
        { budget_ids: response.data.map(b => b.id) }
      )
      summaries.value = summaryRes.data.summaries
    } catch {
      summaries.value = {}
    }
  } else {
    summaries.value = {}
  }

  return { data: response.data, total: response.total }
}

const {
  filters,
  page,
  pageSize,
  sort,
  rows: budgets,
  total,
  totalPages,
  isLoading,
  error,
  setFilter,
  resetFilters,
  refresh
} = useListQuery<BudgetListFilters, BudgetListItem>({
  defaults,
  pageSize: 20,
  sortable: ['created_at', 'valid_until', 'total', 'status', 'budget_number'],
  defaultSort: 'created_at:desc',
  searchKey: 'q',
  fetcher
})

// --- Filter UI options ---------------------------------------------------
const statusItems = computed(() => [
  { label: t('budget.status.draft'), value: 'draft' as BudgetStatus },
  { label: t('budget.status.sent'), value: 'sent' as BudgetStatus },
  { label: t('budget.status.accepted'), value: 'accepted' as BudgetStatus },
  { label: t('budget.status.rejected'), value: 'rejected' as BudgetStatus },
  { label: t('budget.status.expired'), value: 'expired' as BudgetStatus },
  { label: t('budget.status.cancelled'), value: 'cancelled' as BudgetStatus }
])

const validityItems = computed(() => [
  { label: t('budget.filters.validityValid'), value: 'valid' },
  { label: t('budget.filters.validityExpiringSoon'), value: 'expiring' },
  { label: t('budget.filters.validityExpired'), value: 'expired' }
])

const sortOptions = computed(() => [
  { field: 'created_at', label: t('budget.sortFields.createdAt'), defaultDir: 'desc' as const },
  { field: 'valid_until', label: t('budget.sortFields.validUntil'), defaultDir: 'asc' as const },
  { field: 'total', label: t('budget.sortFields.total'), defaultDir: 'desc' as const },
  { field: 'status', label: t('budget.sortFields.status'), defaultDir: 'asc' as const }
])

// Validity is single-select. Translate to/from the toggle list.
const validityList = computed({
  get: () => (filters.value.validity ? [filters.value.validity] : []),
  set: (v: string[]) => setFilter('validity', (v[0] ?? '') as BudgetListFilters['validity'])
})

const dateRange = computed({
  get: () => ({ from: filters.value.date_from, to: filters.value.date_to }),
  set: (v: { from: string | null, to: string | null }) => {
    setFilter('date_from', v.from)
    setFilter('date_to', v.to)
  }
})

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.value.status.length) n++
  if (filters.value.payment_status.length) n++
  if (filters.value.assigned_professional_id) n++
  if (filters.value.validity) n++
  if (filters.value.date_from || filters.value.date_to) n++
  return n
})

function paymentStatusFilterCtx() {
  return {
    value: filters.value.payment_status,
    onChange: (v: string[]) => setFilter('payment_status', v)
  }
}

async function professionalFetcher(query: string) {
  // Cheap: hits /api/v1/auth/professionals which is already paginated.
  const res = await api.get<{ data: Array<{ id: string, first_name: string, last_name: string, email?: string }> }>(
    `/api/v1/auth/professionals${query ? `?q=${encodeURIComponent(query)}` : ''}`
  )
  return res.data.map(p => ({
    id: p.id,
    label: `${p.first_name} ${p.last_name}`.trim(),
    sublabel: p.email ?? undefined
  }))
}

async function professionalResolver(id: string) {
  try {
    const res = await api.get<{ data: { id: string, first_name: string, last_name: string } }>(
      `/api/v1/auth/users/${id}`
    )
    return {
      id: res.data.id,
      label: `${res.data.first_name} ${res.data.last_name}`.trim()
    }
  } catch {
    return null
  }
}

// --- Row helpers ---------------------------------------------------------
function formatDate(s: string | undefined | null): string {
  if (!s) return '—'
  return new Date(s).toLocaleDateString(locale.value)
}

function patientName(p: PatientBrief | undefined): string {
  if (!p) return '—'
  return `${p.last_name}, ${p.first_name}`
}

function validityBadge(b: BudgetListItem): { label: string, color: 'success' | 'warning' | 'error' | 'neutral' } | null {
  if (!b.valid_until) return null
  const today = new Date()
  const until = new Date(b.valid_until)
  const diff = Math.floor((until.getTime() - today.getTime()) / (24 * 3600 * 1000))
  if (diff < 0) return { label: t('budget.validity.expired'), color: 'error' }
  if (diff <= 7) return { label: t('budget.validity.expiresIn', { days: diff }), color: 'warning' }
  return null
}

function createBudget() {
  router.push('/budgets/new')
}

async function handleDownloadPDF(b: BudgetListItem, ev: Event) {
  ev.preventDefault()
  ev.stopPropagation()
  try {
    await downloadPDF(b.id, locale.value)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('budget.pdf.downloadError')),
      color: 'error'
    })
  }
}

async function handleDelete(b: BudgetListItem, ev: Event) {
  ev.preventDefault()
  ev.stopPropagation()
  if (!confirm(t('budget.confirmations.delete'))) return
  try {
    await deleteBudget(b.id)
    toast.add({ title: t('common.success'), description: t('budget.messages.deleted'), color: 'success' })
    await refresh()
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('budget.errors.delete')), color: 'error' })
  }
}
</script>

<template>
  <DataListLayout
    :title="t('budget.title')"
    :loading="isLoading"
    :empty="!budgets.length"
    :error="error"
    :page="page"
    :page-size="pageSize"
    :total="total"
    :total-pages="totalPages"
    @update:page="(v) => (page = v)"
  >
    <template #actions>
      <UButton
        v-if="can(PERMISSIONS.budget.write)"
        color="primary"
        variant="soft"
        icon="i-lucide-plus"
        @click="createBudget"
      >
        {{ t('budget.new') }}
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
            :placeholder="t('budget.searchPlaceholder')"
            max-width="max-w-sm"
            @update:model-value="(v) => setFilter('q', v)"
          />
        </template>

        <FilterChipMulti
          :model-value="filters.status"
          :items="statusItems"
          :label="t('budget.filters.status')"
          icon="i-lucide-circle-dot"
          @update:model-value="(v) => setFilter('status', v)"
        />

        <ModuleSlot
          name="budget.list.filter"
          :ctx="paymentStatusFilterCtx()"
        />

        <FilterChipMulti
          v-model="validityList"
          :items="validityItems"
          :label="t('budget.filters.validity')"
          icon="i-lucide-calendar"
          :multiple="false"
        />

        <FilterEntityPicker
          :model-value="filters.assigned_professional_id"
          :label="t('budget.filters.professional')"
          icon="i-lucide-user"
          :fetcher="professionalFetcher"
          :resolve="professionalResolver"
          @update:model-value="(v) => setFilter('assigned_professional_id', v)"
        />

        <FilterDateRange v-model="dateRange" />

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
        icon="i-lucide-file-text"
        :title="activeFilterCount || filters.q ? t('budget.noItems') : t('budget.empty')"
      >
        <template
          v-if="!activeFilterCount && !filters.q && can(PERMISSIONS.budget.write)"
          #actions
        >
          <UButton
            color="primary"
            variant="soft"
            icon="i-lucide-plus"
            @click="createBudget"
          >
            {{ t('budget.emptyAction') }}
          </UButton>
        </template>
      </EmptyState>
    </template>

    <template #rows>
      <DataListItem
        v-for="b in budgets"
        :key="b.id"
        :to="`/budgets/${b.id}`"
      >
        <!-- Desktop -->
        <template #row>
          <div class="flex-1 min-w-0 flex items-center gap-3">
            <div class="min-w-0 flex-1">
              <div class="text-ui text-default flex items-center gap-2 flex-wrap">
                <span class="tnum">{{ b.budget_number }}</span>
                <span class="text-caption text-subtle tnum">v{{ b.version }}</span>
                <BudgetStatusBadge :status="b.status" />
                <UBadge
                  v-if="validityBadge(b)"
                  :color="validityBadge(b)!.color"
                  variant="subtle"
                  size="xs"
                >
                  {{ validityBadge(b)!.label }}
                </UBadge>
              </div>
              <div class="text-caption text-subtle truncate">
                {{ patientName(b.patient) }}
              </div>
            </div>
          </div>
          <div class="shrink-0 flex items-center gap-3">
            <ModuleSlot
              name="budget.list.row.payments"
              :ctx="{ budget_id: b.id, summary: summaries[b.id] ?? null, total: b.total }"
            />
            <span class="hidden lg:inline text-caption text-subtle tnum">
              {{ formatDate(b.created_at) }}
            </span>
            <Money
              :value="b.total"
              strong
            />
          </div>
          <div class="shrink-0 flex items-center gap-1">
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-download"
              size="xs"
              :aria-label="t('budget.actions.downloadPdf')"
              :title="t('budget.actions.downloadPdf')"
              @click="handleDownloadPDF(b, $event)"
            />
            <UButton
              v-if="can(PERMISSIONS.budget.admin)"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              size="xs"
              :aria-label="t('budget.delete')"
              :title="t('budget.delete')"
              @click="handleDelete(b, $event)"
            />
            <UIcon
              name="i-lucide-chevron-right"
              class="text-subtle"
            />
          </div>
        </template>

        <!-- Mobile -->
        <template #card>
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="font-medium text-default truncate flex items-center gap-2">
                <span class="tnum">{{ b.budget_number }}</span>
                <BudgetStatusBadge :status="b.status" />
              </div>
              <div class="text-caption text-subtle truncate">
                {{ patientName(b.patient) }}
              </div>
            </div>
            <Money
              :value="b.total"
              strong
              class="shrink-0"
            />
          </div>
          <div class="flex items-center justify-between gap-2">
            <ModuleSlot
              name="budget.list.row.payments"
              :ctx="{ budget_id: b.id, summary: summaries[b.id] ?? null, total: b.total }"
            />
            <UBadge
              v-if="validityBadge(b)"
              :color="validityBadge(b)!.color"
              variant="subtle"
              size="xs"
            >
              {{ validityBadge(b)!.label }}
            </UBadge>
          </div>
        </template>
      </DataListItem>
    </template>
  </DataListLayout>
</template>
