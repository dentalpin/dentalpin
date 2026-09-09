<script setup lang="ts">
/**
 * Budget-specific collect modal — thin wrapper around the shared
 * ``CollectAmountModal`` that handles the payments orchestrator call
 * + on-account excess narration. Optimised for receptionists.
 */

import type { PaymentMethod, PaymentRecord, PaymentAllocationCreate } from '~~/app/types'

const props = withDefaults(defineProps<{
  open: boolean
  budgetId: string
  patientId: string
  budgetNumber?: string
  patientName?: string
  pendingAmount: number
}>(), {
  budgetNumber: undefined,
  patientName: undefined
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'created', payment: PaymentRecord): void
}>()

const { t } = useI18n()
const { create } = usePayments()
const { format: formatCurrency } = useCurrency()
const toast = useToast()

const isSubmitting = ref(false)
const errorMsg = ref<string | null>(null)

const title = computed(() =>
  t('payments.budgetCollect.title') + (props.budgetNumber ? ` · ${props.budgetNumber}` : '')
)

function fmt(value: number | string) {
  return formatCurrency(Number(value || 0))
}

function buildAllocations(amount: number): PaymentAllocationCreate[] {
  const pending = Math.max(0, Number(props.pendingAmount || 0))
  const toBudget = Math.min(amount, pending)
  const toOnAccount = Math.max(0, amount - pending)
  const allocs: PaymentAllocationCreate[] = []
  if (toBudget > 0) {
    allocs.push({ target_type: 'budget', target_id: props.budgetId, amount: toBudget })
  }
  if (toOnAccount > 0) {
    allocs.push({ target_type: 'on_account', amount: toOnAccount })
  }
  return allocs
}

async function handleSubmit(payload: {
  amount: number
  method: PaymentMethod
  payment_date: string
  reference?: string
  notes?: string
}) {
  errorMsg.value = null
  isSubmitting.value = true
  try {
    const created = await create({
      patient_id: props.patientId,
      amount: payload.amount,
      method: payload.method,
      payment_date: payload.payment_date,
      reference: payload.reference,
      notes: payload.notes,
      allocations: buildAllocations(payload.amount)
    })
    if (created) {
      toast.add({
        title: t('payments.budgetCollect.success'),
        description: fmt(payload.amount),
        color: 'success'
      })
      emit('created', created)
      emit('update:open', false)
    } else {
      errorMsg.value = t('payments.budgetCollect.errorGeneric')
    }
  } catch (e) {
    errorMsg.value = (e as Error)?.message || t('payments.budgetCollect.errorGeneric')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <CollectAmountModal
    :open="open"
    :title="title"
    :subtitle="patientName"
    :pending-amount="pendingAmount"
    :submitting="isSubmitting"
    :error="errorMsg"
    :submit-label="t('payments.budgetCollect.submit')"
    @update:open="emit('update:open', $event)"
    @submit="handleSubmit"
  >
    <template #narration="{ amount, pending }">
      <section
        v-if="amount > 0"
        class="rounded-md border-s-4 px-3 py-2 text-sm"
        :class="amount > pending
          ? 'border-amber-400 bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-100'
          : amount === pending && pending > 0
            ? 'border-green-500 bg-green-50 text-green-900 dark:bg-green-950 dark:text-green-100'
            : 'border-info-accent bg-info-50 text-info-900 dark:bg-info-950 dark:text-info-100'"
      >
        <p v-if="pending === 0">
          {{ t('payments.budgetCollect.noteBudgetSettled') }}
          <strong>{{ fmt(amount) }}</strong>
          {{ t('payments.budgetCollect.noteToOnAccount') }}
        </p>
        <p v-else-if="amount > pending">
          <strong>{{ fmt(pending) }}</strong>
          {{ t('payments.budgetCollect.noteToBudget') }}
          <strong>{{ fmt(amount - pending) }}</strong>
          {{ t('payments.budgetCollect.noteExcessToOnAccount') }}
        </p>
        <p v-else-if="amount === pending">
          {{ t('payments.budgetCollect.noteFullySettled') }}
        </p>
        <p v-else>
          <strong>{{ fmt(amount) }}</strong>
          {{ t('payments.budgetCollect.noteAppliedToBudget') }}
          {{ t('payments.budgetCollect.notePendingAfter') }}
          <strong>{{ fmt(pending - amount) }}</strong>.
        </p>
      </section>
    </template>
  </CollectAmountModal>
</template>
