<script setup lang="ts">
import type { PaymentMethod, PaymentRecord, PaginatedResponse } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

/**
 * /payments — list page.
 *
 * Owns its own data — payments module both renders this list and owns
 * the underlying ``GET /api/v1/payments`` endpoint.
 *
 * Off-books safe: rows show the gross amount, allocations (budget +
 * on_account), and refunded total per row. The page never displays
 * an invoiced-vs-paid comparison.
 */

definePageMeta({ middleware: 'auth' })

const { t, locale } = useI18n()
const api = useApi()
const { can } = usePermissions()

interface PatientBrief {
  id: string
  first_name: string
  last_name: string
}

interface PaymentListFilters {
  q: string
  method: string[]
  patient_id: string | null
  has_refunds: boolean
  has_unallocated: boolean
  date_from: string | null
  date_to: string | null
}

const defaults: PaymentListFilters = {
  q: '',
  method: [],
  patient_id: null,
  has_refunds: false,
  has_unallocated: false,
  date_from: null,
  date_to: null
}

async function fetcher(q: {
  filters: PaymentListFilters
  page: number
  pageSize: number
  sort: string
}) {
  const params = new URLSearchParams()
  params.set('page', String(q.page))
  params.set('page_size', String(q.pageSize))
  if (q.filters.method.length === 1) params.set('method', q.filters.method[0]!)
  // For multi-method, do client-side intersect would require multiple calls.
  // Keep server-side single-method for now (matches existing API surface).
  if (q.filters.patient_id) params.set('patient_id', q.filters.patient_id)
  if (q.filters.has_refunds) params.set('has_refunds', 'true')
  if (q.filters.has_unallocated) params.set('has_unallocated', 'true')
  if (q.filters.date_from) params.set('date_from', q.filters.date_from)
  if (q.filters.date_to) params.set('date_to', q.filters.date_to)
  if (q.sort) params.set('sort', q.sort)

  const response = await api.get<PaginatedResponse<PaymentRecord>>(`/api/v1/payments?${params.toString()}`)
  // Client-side multi-method filter (until backend accepts list).
  let data = response.data
  if (q.filters.method.length > 1) {
    data = data.filter(p => q.filters.method.includes(p.method))
  }
  // Search filter (client-side, since /payments doesn't expose ?search yet).
  if (q.filters.q) {
    const term = q.filters.q.toLowerCase()
    data = data.filter((p) => {
      const name = p.patient ? `${p.patient.first_name} ${p.patient.last_name}`.toLowerCase() : ''
      return name.includes(term) || (p.reference ?? '').toLowerCase().includes(term)
    })
  }
  return { data, total: response.total }
}

const {
  filters,
  page,
  pageSize,
  sort,
  rows: payments,
  total,
  totalPages,
  isLoading,
  error,
  setFilter,
  resetFilters,
  refresh
} = useListQuery<PaymentListFilters, PaymentRecord>({
  defaults,
  pageSize: 20,
  sortable: ['payment_date', 'amount', 'created_at'],
  defaultSort: 'payment_date:desc',
  searchKey: 'q',
  fetcher
})

const PAYMENT_METHODS: PaymentMethod[] = ['cash', 'card', 'bank_transfer', 'direct_debit', 'insurance', 'other']

const methodItems = computed(() =>
  PAYMENT_METHODS.map(m => ({ label: t(`payments.methods.${m}`), value: m }))
)

const sortOptions = computed(() => [
  { field: 'payment_date', label: t('payments.list.sort.paymentDate'), defaultDir: 'desc' as const },
  { field: 'amount', label: t('payments.list.sort.amount'), defaultDir: 'desc' as const }
])

const dateRange = computed({
  get: () => ({ from: filters.value.date_from, to: filters.value.date_to }),
  set: (v: { from: string | null, to: string | null }) => {
    setFilter('date_from', v.from)
    setFilter('date_to', v.to)
  }
})

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.value.method.length) n++
  if (filters.value.patient_id) n++
  if (filters.value.has_refunds) n++
  if (filters.value.has_unallocated) n++
  if (filters.value.date_from || filters.value.date_to) n++
  return n
})

async function patientFetcher(q: string) {
  const params = new URLSearchParams()
  params.set('page_size', '20')
  if (q) params.set('search', q)
  const res = await api.get<PaginatedResponse<PatientBrief & { phone?: string }>>(
    `/api/v1/patients?${params.toString()}`
  )
  return res.data.map(p => ({
    id: p.id,
    label: `${p.last_name}, ${p.first_name}`,
    sublabel: p.phone ?? undefined
  }))
}

async function patientResolver(id: string) {
  try {
    const res = await api.get<{ data: PatientBrief }>(`/api/v1/patients/${id}`)
    return { id: res.data.id, label: `${res.data.last_name}, ${res.data.first_name}` }
  } catch {
    return null
  }
}

// --- Modals -------------------------------------------------------------
const showCreate = ref(false)
const showRefund = ref(false)
const refundTarget = ref<PaymentRecord | null>(null)

function openRefund(p: PaymentRecord) {
  refundTarget.value = p
  showRefund.value = true
}

async function handleRefunded() {
  showRefund.value = false
  refundTarget.value = null
  await refresh()
}

function handleCreated() {
  refresh()
}

// --- Row helpers --------------------------------------------------------
const { format: formatCurrency } = useCurrency()

function methodIcon(method: string): string {
  switch (method) {
    case 'cash':
      return 'i-lucide-banknote'
    case 'card':
      return 'i-lucide-credit-card'
    case 'bank_transfer':
      return 'i-lucide-landmark'
    case 'direct_debit':
      return 'i-lucide-repeat'
    case 'insurance':
      return 'i-lucide-shield'
    default:
      return 'i-lucide-circle-dollar-sign'
  }
}

function patientName(p: PatientBrief | undefined | null): string {
  if (!p) return t('payments.list.row.noPatient')
  return `${p.last_name}, ${p.first_name}`
}

function allocationBreakdown(p: PaymentRecord): Array<{ label: string, amount: string }> {
  const out: Array<{ label: string, amount: string }> = []
  let toBudget = 0
  let onAccount = 0
  for (const a of p.allocations ?? []) {
    const amount = Number(a.amount)
    if (a.target_type === 'budget') toBudget += amount
    else if (a.target_type === 'on_account') onAccount += amount
  }
  if (toBudget) out.push({ label: t('payments.new.allocationToBudget'), amount: formatCurrency(toBudget) })
  if (onAccount) out.push({ label: t('payments.new.allocationOnAccount'), amount: formatCurrency(onAccount) })
  return out
}

function formatDate(s: string | undefined): string {
  if (!s) return '—'
  return new Date(s).toLocaleDateString(locale.value)
}
</script>

<template>
  <DataListLayout
    :title="t('payments.list.title')"
    :subtitle="t('payments.list.subtitle')"
    :loading="isLoading"
    :empty="!payments.length"
    :error="error"
    :page="page"
    :page-size="pageSize"
    :total="total"
    :total-pages="totalPages"
    @update:page="(v) => (page = v)"
  >
    <template #actions>
      <UButton
        v-if="can(PERMISSIONS.payments.recordWrite)"
        color="primary"
        icon="i-lucide-plus"
        @click="showCreate = true"
      >
        {{ t('payments.list.new') }}
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
            :placeholder="t('payments.list.searchPlaceholder')"
            max-width="max-w-sm"
            @update:model-value="(v) => setFilter('q', v)"
          />
        </template>

        <FilterChipMulti
          :model-value="filters.method"
          :items="methodItems"
          :label="t('payments.list.filter.method')"
          icon="i-lucide-credit-card"
          @update:model-value="(v) => setFilter('method', v)"
        />

        <FilterDateRange v-model="dateRange" />

        <FilterEntityPicker
          :model-value="filters.patient_id"
          :label="t('payments.list.filter.patient')"
          icon="i-lucide-user"
          :fetcher="patientFetcher"
          :resolve="patientResolver"
          @update:model-value="(v) => setFilter('patient_id', v)"
        />

        <FilterToggle
          :model-value="filters.has_refunds"
          :label="t('payments.list.filter.hasRefunds')"
          icon="i-lucide-rotate-ccw"
          @update:model-value="(v) => setFilter('has_refunds', Boolean(v))"
        />

        <FilterToggle
          :model-value="filters.has_unallocated"
          :label="t('payments.list.filter.hasUnallocated')"
          icon="i-lucide-piggy-bank"
          @update:model-value="(v) => setFilter('has_unallocated', Boolean(v))"
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
        icon="i-lucide-wallet"
        :title="t('payments.list.empty')"
      >
        <template
          v-if="!activeFilterCount && !filters.q && can(PERMISSIONS.payments.recordWrite)"
          #actions
        >
          <UButton
            color="primary"
            icon="i-lucide-plus"
            @click="showCreate = true"
          >
            {{ t('payments.list.new') }}
          </UButton>
        </template>
      </EmptyState>
    </template>

    <template #rows>
      <DataListItem
        v-for="p in payments"
        :key="p.id"
      >
        <template #row>
          <div class="shrink-0">
            <UAvatar
              :alt="p.patient?.first_name ?? '?'"
              size="sm"
            />
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-ui text-default flex items-center gap-2 flex-wrap">
              {{ patientName(p.patient) }}
            </div>
            <div class="text-caption text-subtle flex items-center gap-2 flex-wrap">
              <span>{{ formatDate(p.payment_date) }}</span>
              <span class="inline-flex items-center gap-1">
                <UIcon
                  :name="methodIcon(p.method)"
                  class="w-3.5 h-3.5"
                />
                {{ t(`payments.methods.${p.method}`) }}
              </span>
              <span
                v-if="p.reference"
                class="truncate max-w-[160px]"
                :title="p.reference"
              >· {{ p.reference }}</span>
            </div>
          </div>
          <div class="shrink-0 hidden sm:flex flex-col items-end gap-0.5 max-w-[200px]">
            <span
              v-for="a in allocationBreakdown(p)"
              :key="a.label"
              class="text-caption text-subtle tnum"
            >
              {{ a.amount }} <span class="opacity-60">· {{ a.label }}</span>
            </span>
          </div>
          <div class="shrink-0 text-right min-w-[100px]">
            <Money
              :value="p.amount"
              strong
            />
            <div
              v-if="Number(p.refunded_total) > 0"
              class="text-caption text-danger tnum"
            >
              − {{ formatCurrency(p.refunded_total) }}
            </div>
          </div>
          <UButton
            v-if="can(PERMISSIONS.payments.recordRefund) && Number(p.net_amount) > 0"
            variant="soft"
            color="warning"
            size="xs"
            icon="i-lucide-rotate-ccw"
            :aria-label="t('payments.detail.refund')"
            :title="t('payments.detail.refund')"
            @click="openRefund(p)"
          />
        </template>

        <template #card>
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="font-medium text-default truncate">
                {{ patientName(p.patient) }}
              </div>
              <div class="text-caption text-subtle truncate flex items-center gap-1">
                <UIcon
                  :name="methodIcon(p.method)"
                  class="w-3.5 h-3.5"
                />
                {{ formatDate(p.payment_date) }} · {{ t(`payments.methods.${p.method}`) }}
              </div>
            </div>
            <div class="text-right shrink-0">
              <Money
                :value="p.amount"
                strong
              />
              <div
                v-if="Number(p.refunded_total) > 0"
                class="text-caption text-danger tnum"
              >
                − {{ formatCurrency(p.refunded_total) }}
              </div>
            </div>
          </div>
          <div
            v-if="allocationBreakdown(p).length"
            class="flex flex-wrap gap-1"
          >
            <UBadge
              v-for="a in allocationBreakdown(p)"
              :key="a.label"
              color="neutral"
              variant="subtle"
              size="xs"
            >
              {{ a.amount }} · {{ a.label }}
            </UBadge>
          </div>
          <div
            v-if="can(PERMISSIONS.payments.recordRefund) && Number(p.net_amount) > 0"
            class="flex justify-end"
          >
            <UButton
              variant="soft"
              color="warning"
              size="xs"
              icon="i-lucide-rotate-ccw"
              @click="openRefund(p)"
            >
              {{ t('payments.detail.refund') }}
            </UButton>
          </div>
        </template>
      </DataListItem>
    </template>
  </DataListLayout>

  <PaymentCreateModal
    v-model:open="showCreate"
    @created="handleCreated"
  />

  <RefundConfirmModal
    v-if="refundTarget"
    v-model:open="showRefund"
    :payment-id="refundTarget.id"
    :default-amount="refundTarget.net_amount"
    :default-method="refundTarget.method"
    @refunded="handleRefunded"
  />
</template>
