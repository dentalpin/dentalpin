<script setup lang="ts">
/**
 * BalanceCard — patient ledger smart-card.
 *
 * Registered into ``patient.summary.cards`` by payments. Surfaces the
 * three core balances (debt, on-account credit, total paid) and links
 * one click into the Administración → Cobros panel that the same
 * module already provides via the ``patient.detail.administracion.payments``
 * slot.
 */
import type { PatientExtended, PatientLedger } from '~~/app/types'

interface Ctx {
  patient: PatientExtended
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()
const { format: formatCurrency } = useCurrency()
const { fetchPatientLedger } = usePayments()

const patientId = computed(() => props.ctx.patient.id)

const { data: ledger, status } = await useAsyncData<PatientLedger | null>(
  () => `payments:summary-card:${patientId.value}`,
  () => fetchPatientLedger(patientId.value),
  { watch: [patientId], default: () => null, server: false }
)

const debt = computed(() => Number(ledger.value?.clinic_receivable ?? 0))
const credit = computed(() => Number(ledger.value?.patient_credit ?? 0))
const totalPaid = computed(() => Number(ledger.value?.total_paid ?? 0))

const severity = computed<'neutral' | 'success' | 'warning' | 'danger'>(() => {
  if (debt.value > 0) return 'danger'
  if (credit.value > 0) return 'warning'
  if (totalPaid.value > 0) return 'success'
  return 'neutral'
})

const href = computed(
  () => `/patients/${patientId.value}?tab=administration&adminMode=payments`
)

const ctaLabel = computed(() => {
  if (debt.value > 0) return t('patientDetail.collect')
  return t('patientDetail.viewLedger')
})

const isEmpty = computed(() =>
  totalPaid.value === 0 && debt.value === 0 && credit.value === 0
)
</script>

<template>
  <SummaryCard
    :title="t('patientDetail.balance')"
    icon="i-lucide-wallet"
    :severity="severity"
    :loading="status === 'pending'"
    :empty="isEmpty"
    :to="href"
  >
    <template #empty>
      {{ t('patientDetail.noPayments') }}
    </template>

    <dl class="space-y-1 text-ui">
      <div
        v-if="debt > 0"
        class="flex items-baseline justify-between gap-2"
      >
        <dt class="text-caption text-muted">
          {{ t('payments.balance.debt') }}
        </dt>
        <dd class="text-h2 text-[var(--color-danger-accent)] tnum">
          {{ formatCurrency(debt) }}
        </dd>
      </div>
      <div
        v-if="credit > 0"
        class="flex items-baseline justify-between gap-2"
      >
        <dt class="text-caption text-muted">
          {{ t('payments.balance.credit') }}
        </dt>
        <dd class="text-default tnum">
          {{ formatCurrency(credit) }}
        </dd>
      </div>
      <div class="flex items-baseline justify-between gap-2">
        <dt class="text-caption text-muted">
          {{ t('payments.balance.paid') }}
        </dt>
        <dd class="text-default tnum">
          {{ formatCurrency(totalPaid) }}
        </dd>
      </div>
    </dl>

    <template #footer>
      <span>{{ ctaLabel }}</span>
    </template>
  </SummaryCard>
</template>
