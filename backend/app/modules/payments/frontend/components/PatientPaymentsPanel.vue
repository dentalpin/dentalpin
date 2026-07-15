<script setup lang="ts">
/**
 * Slot entry into ``patient.detail.administracion.payments``.
 *
 * Patient-centric ledger view rendered inside the patient-detail
 * "Administración" tab. Shows the three core balances (total paid,
 * clinic receivable, on-account), an optional status banner (debt /
 * credit / settled) and the full money timeline returned by
 * ``GET /payments/patients/{id}/ledger``.
 *
 * The host (`patients`) never imports this file — it only exposes the
 * slot name and renders `<ModuleSlot>`. We receive `ctx` verbatim from
 * the host.
 */

import type { PatientExtended, PatientLedger, PatientLedgerEntry, PaymentMethod } from '~~/app/types'
import type { TotalLine } from '~~/app/components/shared/EntityTotalsCard.vue'
import type { SemanticRole } from '~~/app/config/severity'
import { PERMISSIONS } from '~~/app/config/permissions'
import PendingChargesCard from './payments/PendingChargesCard.vue'

interface PendingCharge {
  entry_id: string
  treatment_id: string
  session_id: string | null
  description: string | null
  amount: string
  occurred_at: string
}

interface PatientPaymentsCtx {
  patient: PatientExtended | null
  patientId: string
}

const props = defineProps<{ ctx: PatientPaymentsCtx }>()

const { t, locale } = useI18n()
const { can } = usePermissions()
const { format: formatCurrency } = useCurrency()
const { fetchPatientLedger, fetchPendingCharges } = usePayments()

const ledger = ref<PatientLedger | null>(null)
const pendingCharges = ref<PendingCharge[]>([])
const isLoading = ref(false)
const loadError = ref(false)
const showCobrar = ref(false)
const showRefund = ref(false)
const refundTarget = ref<{ id: string, amount: number, method: PaymentMethod } | null>(null)
const prefilledCobrarAmount = ref<number | null>(null)

const canCollect = computed(() => can(PERMISSIONS.payments.recordWrite))
const canRefund = computed(() => can(PERMISSIONS.payments.recordRefund))

const totalPaid = computed(() => Number(ledger.value?.total_paid ?? 0))
const debt = computed(() => Number(ledger.value?.clinic_receivable ?? 0))
const credit = computed(() => Number(ledger.value?.patient_credit ?? 0))
const totalEarned = computed(() => Number(ledger.value?.total_earned ?? 0))

const patientFullName = computed(() => {
  const p = props.ctx.patient
  if (!p) return ''
  return [p.first_name, p.last_name].filter(Boolean).join(' ').trim()
})

// Newest first. Backend returns chronological asc.
const timeline = computed<PatientLedgerEntry[]>(() => {
  const tl = ledger.value?.timeline ?? []
  return [...tl].sort((a, b) =>
    new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime()
  )
})

const lastPaymentDate = computed(() => {
  const lastPayment = timeline.value.find(e => e.entry_type === 'payment')
  return lastPayment?.occurred_at ?? null
})

const totalLines = computed<TotalLine[]>(() => [
  {
    key: 'totalPaid',
    label: t('payments.patientPanel.kpis.totalPaid'),
    value: totalPaid.value,
    emphasis: 'strong',
    role: totalPaid.value > 0 ? 'success' : 'neutral'
  },
  {
    key: 'debt',
    label: t('payments.patientPanel.kpis.debt'),
    value: debt.value,
    role: debt.value > 0 ? 'warning' : 'neutral'
  },
  {
    key: 'onAccount',
    // "A cuenta" surfaces the *net* available credit (patient_credit =
    // max(0, paid − earned)), not the gross on_account_balance which
    // accumulates raw allocations without subtracting earned treatments
    // already covered by them via FIFO. Reception cares about "how much
    // is the patient really sitting on", not the bookkeeping figure.
    label: t('payments.patientPanel.kpis.onAccount'),
    value: credit.value,
    role: credit.value > 0 ? 'info' : 'neutral'
  }
])

type Banner = { role: SemanticRole, title: string, description: string }
const banner = computed<Banner | null>(() => {
  if (debt.value > 0) {
    return {
      role: 'warning',
      title: t('payments.patientPanel.banner.debtTitle', { amount: formatCurrency(debt.value) }),
      description: t('payments.patientPanel.banner.debtDescription')
    }
  }
  if (credit.value > 0) {
    return {
      role: 'info',
      title: t('payments.patientPanel.banner.creditTitle', { amount: formatCurrency(credit.value) }),
      description: t('payments.patientPanel.banner.creditDescription')
    }
  }
  return null
})

const ENTRY_ICONS: Record<PatientLedgerEntry['entry_type'], string> = {
  payment: 'i-lucide-arrow-down-circle',
  refund: 'i-lucide-arrow-up-circle',
  earned: 'i-lucide-stethoscope'
}

const ENTRY_ICON_CLASS: Record<PatientLedgerEntry['entry_type'], string> = {
  payment: 'text-success-accent',
  refund: 'text-danger-accent',
  earned: 'text-subtle'
}

function entryAmountClass(type: PatientLedgerEntry['entry_type']) {
  if (type === 'payment') return 'text-success-accent'
  if (type === 'refund') return 'text-danger-accent'
  return 'text-default'
}

function entryAmountSign(entry: PatientLedgerEntry): string {
  // Backend returns positive magnitudes — refunds carry their own
  // semantic via entry_type. Display a leading sign for clarity.
  const formatted = formatCurrency(entry.amount)
  if (entry.entry_type === 'refund') {
    return formatted.startsWith('-') ? formatted : `- ${formatted}`
  }
  if (entry.entry_type === 'payment') return `+ ${formatted}`
  return formatted
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(locale.value, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

function entryDescription(entry: PatientLedgerEntry): string {
  if (entry.entry_type === 'earned' && entry.treatment_name) return entry.treatment_name
  if (entry.description) return entry.description
  return t(`payments.patientPanel.timeline.types.${entry.entry_type}`)
}

function treatmentStatusLabel(status: string | null | undefined): string {
  if (!status) return ''
  const key = `payments.patientPanel.timeline.treatmentStatus.${status}`
  // Fall back to capitalising the raw status string when no i18n
  // entry exists yet (e.g. a new lifecycle value lands before the
  // translation does) so the column stays informative.
  const translated = t(key)
  if (translated === key) return status.charAt(0).toUpperCase() + status.slice(1)
  return translated
}

function entryMeta(entry: PatientLedgerEntry): string[] {
  if (entry.entry_type !== 'earned') return []
  const parts: string[] = []
  if (entry.treatment_status) parts.push(treatmentStatusLabel(entry.treatment_status))
  if (entry.professional_name) parts.push(t('payments.patientPanel.timeline.drPrefix', { name: entry.professional_name }))
  return parts
}

async function refresh() {
  if (!props.ctx.patientId) return
  isLoading.value = true
  loadError.value = false
  try {
    const [data, pending] = await Promise.all([
      fetchPatientLedger(props.ctx.patientId),
      fetchPendingCharges(props.ctx.patientId)
    ])
    ledger.value = data
    pendingCharges.value = pending
    loadError.value = data === null
  } finally {
    isLoading.value = false
  }
}

onMounted(refresh)
watch(() => props.ctx.patientId, refresh)

function openCobrar() {
  prefilledCobrarAmount.value = null
  showCobrar.value = true
}

function openCobrarPending(amount: number) {
  prefilledCobrarAmount.value = amount
  showCobrar.value = true
}

function openRefund(entry: PatientLedgerEntry) {
  refundTarget.value = {
    id: entry.reference_id,
    amount: Number(entry.amount),
    // PatientLedgerEntry doesn't carry method; default to cash, modal lets operator change.
    method: 'cash'
  }
  showRefund.value = true
}

function rowMenuItems(entry: PatientLedgerEntry) {
  if (entry.entry_type !== 'payment') return []
  const items: Array<{ label: string, icon: string, to?: string, onSelect?: () => void, color?: string }> = [
    {
      label: t('payments.patientPanel.timeline.rowMenu.detail'),
      icon: 'i-lucide-eye',
      to: `/payments/${entry.reference_id}`
    }
  ]
  if (canRefund.value) {
    items.push({
      label: t('payments.patientPanel.timeline.rowMenu.refund'),
      icon: 'i-lucide-undo-2',
      color: 'error',
      onSelect: () => openRefund(entry)
    })
  }
  return items
}

function handlePaymentCreated() {
  refresh()
}

function handleRefunded() {
  refundTarget.value = null
  refresh()
}
</script>

<template>
  <div class="space-y-4 pb-20 lg:pb-0">
    <!-- Pendiente de cobrar — surfaces completed-but-uncharged sessions
         so reception can collect when the patient leaves the box. -->
    <PendingChargesCard
      v-if="!isLoading && pendingCharges.length > 0"
      :charges="pendingCharges"
      :can-collect="canCollect"
      @collect="openCobrarPending"
    />

    <!-- Status banner (debt or credit). Hidden when settled. -->
    <EntityCriticalBanner
      v-if="banner && !isLoading"
      :role="banner.role"
      :title="banner.title"
      :description="banner.description"
    />

    <!-- KPIs + sidebar -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="lg:col-span-2">
        <EntityTotalsCard
          v-if="!loadError"
          :title="t('payments.patientPanel.title')"
          :lines="totalLines"
        />
        <UCard v-else>
          <div class="text-center py-6">
            <UIcon
              name="i-lucide-alert-triangle"
              class="w-8 h-8 text-warning-accent mx-auto mb-2"
            />
            <p class="text-body mb-3">
              {{ t('payments.patientPanel.timeline.loadError') }}
            </p>
            <UButton
              size="sm"
              variant="soft"
              icon="i-lucide-refresh-cw"
              @click="refresh"
            >
              {{ t('payments.patientPanel.timeline.retry') }}
            </UButton>
          </div>
        </UCard>
      </div>

      <UCard class="hidden lg:block">
        <template #header>
          <h3 class="text-h2 text-default">
            {{ t('payments.patientPanel.sidebar.title') }}
          </h3>
        </template>
        <dl class="space-y-2 text-body">
          <div class="flex items-baseline justify-between gap-2">
            <dt class="text-subtle">
              {{ t('payments.patientPanel.sidebar.credit') }}
            </dt>
            <dd
              class="tabular-nums font-medium"
              :class="credit > 0 ? 'text-info-accent' : ''"
            >
              {{ formatCurrency(credit) }}
            </dd>
          </div>
          <div class="flex items-baseline justify-between gap-2">
            <dt class="text-subtle">
              {{ t('payments.patientPanel.sidebar.totalEarned') }}
            </dt>
            <dd class="tabular-nums">
              {{ formatCurrency(totalEarned) }}
            </dd>
          </div>
          <div class="flex items-baseline justify-between gap-2">
            <dt class="text-subtle">
              {{ t('payments.patientPanel.sidebar.lastPayment') }}
            </dt>
            <dd class="tabular-nums text-caption text-muted">
              <template v-if="lastPaymentDate">
                {{ formatDate(lastPaymentDate) }}
              </template>
              <template v-else>
                {{ t('payments.patientPanel.sidebar.noLastPayment') }}
              </template>
            </dd>
          </div>
        </dl>
        <div
          v-if="canCollect"
          class="mt-4 pt-4 border-t border-default"
        >
          <UButton
            block
            color="primary"
            icon="i-lucide-wallet"
            @click="openCobrar"
          >
            {{ t('payments.patientPanel.cobrar') }}
          </UButton>
        </div>
      </UCard>
    </div>

    <!-- Timeline -->
    <UCard>
      <template #header>
        <h3 class="text-h2 text-default">
          {{ t('payments.patientPanel.timeline.title') }}
        </h3>
      </template>

      <div
        v-if="isLoading"
        class="space-y-2"
      >
        <USkeleton
          v-for="i in 4"
          :key="i"
          class="h-12 w-full"
        />
      </div>

      <div
        v-else-if="!loadError && timeline.length === 0"
        class="text-center py-8"
      >
        <UIcon
          name="i-lucide-wallet"
          class="w-12 h-12 text-subtle mx-auto mb-3"
        />
        <p class="text-muted mb-4">
          {{ t('payments.patientPanel.timeline.empty') }}
        </p>
        <UButton
          v-if="canCollect"
          icon="i-lucide-plus"
          @click="openCobrar"
        >
          {{ t('payments.patientPanel.timeline.emptyCta') }}
        </UButton>
      </div>

      <ul
        v-else-if="!loadError"
        class="divide-y divide-[var(--color-border-subtle)]"
      >
        <li
          v-for="entry in timeline"
          :key="`${entry.entry_type}-${entry.reference_id}-${entry.occurred_at}`"
          class="py-3 first:pt-0 last:pb-0"
        >
          <!-- Two-row layout on mobile, single-row on lg -->
          <div class="flex items-start lg:items-center gap-3">
            <UIcon
              :name="ENTRY_ICONS[entry.entry_type]"
              :class="['w-5 h-5 shrink-0 mt-0.5 lg:mt-0', ENTRY_ICON_CLASS[entry.entry_type]]"
            />
            <div class="flex-1 min-w-0">
              <div class="flex flex-wrap items-baseline gap-x-2">
                <span class="font-medium text-default">
                  {{ t(`payments.patientPanel.timeline.types.${entry.entry_type}`) }}
                </span>
                <span class="text-caption text-subtle truncate">
                  {{ entryDescription(entry) }}
                </span>
              </div>
              <div
                v-if="entryMeta(entry).length > 0"
                class="text-caption text-subtle mt-0.5 flex flex-wrap gap-x-2"
              >
                <span
                  v-for="(meta, idx) in entryMeta(entry)"
                  :key="idx"
                >
                  {{ meta }}<span
                    v-if="idx < entryMeta(entry).length - 1"
                    class="text-muted"
                  > · </span>
                </span>
              </div>
              <div class="text-caption text-muted mt-0.5">
                {{ formatDate(entry.occurred_at) }}
              </div>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <span
                class="tabular-nums font-semibold"
                :class="entryAmountClass(entry.entry_type)"
              >
                {{ entryAmountSign(entry) }}
              </span>
              <UDropdownMenu
                v-if="entry.entry_type === 'payment'"
                :items="rowMenuItems(entry)"
              >
                <UButton
                  variant="ghost"
                  color="neutral"
                  icon="i-lucide-more-vertical"
                  size="xs"
                  :aria-label="t('payments.patientPanel.timeline.rowMenu.detail')"
                />
              </UDropdownMenu>
            </div>
          </div>
        </li>
      </ul>
    </UCard>

    <!-- Mobile sticky CTA. Hidden on lg+ where the sidebar shows the button. -->
    <div
      v-if="canCollect"
      class="lg:hidden fixed bottom-0 left-0 right-0 z-10 px-3 py-3 bg-default border-t border-default"
    >
      <UButton
        block
        color="primary"
        icon="i-lucide-wallet"
        size="lg"
        @click="openCobrar"
      >
        {{ t('payments.patientPanel.cobrar') }}
      </UButton>
    </div>

    <PaymentCreateModal
      v-model:open="showCobrar"
      :default-patient-id="ctx.patientId"
      :default-patient-name="patientFullName"
      :default-amount="prefilledCobrarAmount ?? undefined"
      :suggested-amount="debt > 0 ? debt : undefined"
      @created="handlePaymentCreated"
    />

    <RefundConfirmModal
      v-if="refundTarget"
      v-model:open="showRefund"
      :payment-id="refundTarget.id"
      :default-amount="refundTarget.amount"
      :default-method="refundTarget.method"
      @refunded="handleRefunded"
    />
  </div>
</template>
