<script setup lang="ts">
/**
 * Slot entry into ``budget.detail.sidebar``.
 *
 * Renders the payments view of a budget: cobrado vs presupuesto with a
 * progress bar, pendiente con CTA "Cobrar", and the list of allocations
 * targeting the budget. The card lives in the ``payments`` module so
 * the ``budget`` module never imports payments code — they only share
 * the ``ModuleSlot`` contract.
 */

import type { PaymentAllocation, PaymentMethod } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

interface BudgetCtx {
  budget: {
    id: string
    patient_id: string
    budget_number?: string
    total: number | string
    status: string
    patient?: { id: string, first_name: string, last_name: string } | null
  } | null
}

const props = defineProps<{ ctx: BudgetCtx }>()

const { t } = useI18n()
const { currentLocale } = useLocale()
const { can } = usePermissions()
const { fetchBudgetAllocations } = usePayments()
const { format: formatCurrency } = useCurrency()

const allocations = ref<PaymentAllocation[]>([])
const isLoading = ref(false)
const showCreate = ref(false)

const budgetTotal = computed(() => Number(props.ctx?.budget?.total ?? 0))

const collected = computed(() =>
  allocations.value.reduce((sum, a) => sum + Number(a.amount || 0), 0)
)

const pending = computed(() => Math.max(0, budgetTotal.value - collected.value))

const progressPct = computed(() => {
  if (budgetTotal.value <= 0) return 0
  return Math.min(100, Math.round((collected.value / budgetTotal.value) * 100))
})

type CardState = 'empty' | 'partial' | 'settled'
const state = computed<CardState>(() => {
  if (collected.value <= 0) return 'empty'
  if (collected.value >= budgetTotal.value) return 'settled'
  return 'partial'
})

const METHOD_ICONS: Record<PaymentMethod, string> = {
  cash: 'i-lucide-banknote',
  card: 'i-lucide-credit-card',
  bank_transfer: 'i-lucide-landmark',
  direct_debit: 'i-lucide-repeat',
  insurance: 'i-lucide-shield',
  upi: 'i-lucide-smartphone-nfc',
  netbanking: 'i-lucide-landmark',
  other: 'i-lucide-circle-dollar-sign'
}

function methodIcon(method?: PaymentMethod): string {
  return method ? METHOD_ICONS[method] : 'i-lucide-circle-dollar-sign'
}

function relDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = d.getTime() - now.getTime()
  const diffDays = Math.round(diffMs / 86_400_000)
  if (Math.abs(diffDays) > 30) {
    return d.toLocaleDateString(currentLocale.value)
  }
  const rtf = new Intl.RelativeTimeFormat(currentLocale.value, { numeric: 'auto' })
  if (Math.abs(diffDays) >= 1) return rtf.format(diffDays, 'day')
  const diffH = Math.round(diffMs / 3_600_000)
  if (Math.abs(diffH) >= 1) return rtf.format(diffH, 'hour')
  const diffMin = Math.round(diffMs / 60_000)
  return rtf.format(diffMin, 'minute')
}

async function refresh() {
  if (!props.ctx?.budget?.id) return
  isLoading.value = true
  try {
    allocations.value = await fetchBudgetAllocations(props.ctx.budget.id)
  } finally {
    isLoading.value = false
  }
}

onMounted(refresh)
watch(() => props.ctx?.budget?.id, refresh)

function handleCreated() {
  refresh()
}
</script>

<template>
  <UCard v-if="ctx?.budget">
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <h3 class="text-h1 text-default">
          {{ t('payments.budgetCard.title') }}
        </h3>
        <UButton
          v-if="pending > 0 && can(PERMISSIONS.payments.recordWrite)"
          icon="i-lucide-wallet"
          size="sm"
          @click="showCreate = true"
        >
          {{ t('payments.budgetCard.collect') }}
        </UButton>
        <ModuleSlot
          name="payments.collect.actions"
          :ctx="{ budget: ctx.budget, patient: ctx.budget?.patient ?? null }"
        />
      </div>
    </template>

    <!-- Loading skeleton -->
    <div
      v-if="isLoading"
      class="space-y-2"
    >
      <div class="h-5 w-2/3 rounded bg-[var(--ui-bg-elevated)] animate-pulse" />
      <div class="h-2 w-full rounded-full bg-[var(--ui-bg-elevated)] animate-pulse" />
    </div>

    <div
      v-else
      class="space-y-3"
    >
      <!-- Compact summary: Cobrado X / Total Y, % + progress -->
      <div>
        <div class="flex items-baseline justify-between gap-2">
          <div class="min-w-0">
            <span
              class="text-lg font-semibold tabular-nums"
              :class="state === 'empty' ? 'text-default' : 'text-success-accent'"
            >
              {{ formatCurrency(collected) }}
            </span>
            <span class="text-caption text-subtle">
              / {{ formatCurrency(budgetTotal) }}
            </span>
          </div>
          <span class="text-caption text-subtle tabular-nums shrink-0">
            {{ progressPct }}%
          </span>
        </div>
        <div class="mt-2 h-2 w-full rounded-full bg-[var(--ui-bg-elevated)] overflow-hidden">
          <div
            class="h-full rounded-full transition-[width] duration-300"
            :class="state === 'settled' ? 'bg-success' : 'bg-primary'"
            :style="{ width: progressPct + '%' }"
          />
        </div>
      </div>

      <!-- Pending status — single line -->
      <div class="flex items-center justify-between gap-2 text-body">
        <span class="text-subtle">{{ t('payments.budgetCard.pendingLabel') }}</span>
        <span
          v-if="state === 'settled'"
          class="font-semibold text-success-accent flex items-center gap-1"
        >
          <UIcon
            name="i-lucide-check-circle-2"
            class="w-4 h-4"
          />
          {{ t('payments.budgetCard.settled') }}
        </span>
        <span
          v-else
          class="font-semibold tabular-nums"
          :class="state === 'partial' ? 'text-warning-accent' : 'text-default'"
        >
          {{ formatCurrency(pending) }}
        </span>
      </div>

      <!-- Empty state (compact) -->
      <p
        v-if="allocations.length === 0"
        class="text-caption text-subtle text-center border-t border-default pt-3"
      >
        {{ t('payments.budgetCard.emptyDetailed') }}
      </p>

      <!-- Allocations history -->
      <div
        v-else
        class="border-t border-default pt-2"
      >
        <p class="text-caption text-muted mb-1">
          {{ t('payments.budgetCard.history') }}
        </p>
        <ul class="space-y-1">
          <li
            v-for="a in allocations"
            :key="a.id"
            class="flex items-center gap-2 py-0.5 text-sm"
          >
            <UIcon
              :name="methodIcon(a.method)"
              class="text-primary-accent shrink-0 w-4 h-4"
            />
            <span class="flex-1 min-w-0 truncate text-default">
              {{ a.method ? t(`payments.methods.${a.method}`) : t('payments.budgetCard.payment') }}
              <span class="text-subtle">· {{ relDate(a.created_at) }}</span>
            </span>
            <span class="font-medium tabular-nums shrink-0">
              {{ formatCurrency(a.amount) }}
            </span>
          </li>
        </ul>
      </div>
    </div>

    <BudgetCollectModal
      v-model:open="showCreate"
      :budget-id="ctx.budget.id"
      :patient-id="ctx.budget.patient_id"
      :budget-number="ctx.budget.budget_number"
      :patient-name="ctx.budget.patient
        ? `${ctx.budget.patient.first_name} ${ctx.budget.patient.last_name}`
        : undefined"
      :pending-amount="pending"
      @created="handleCreated"
    />
  </UCard>
</template>
