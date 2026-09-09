<script setup lang="ts">
/**
 * Invoice-specific collect modal — thin wrapper around the shared
 * ``CollectAmountModal``. Calls billing's orchestrator
 * (``POST /api/v1/billing/invoices/{id}/payments``) which records a
 * payment + invoice allocation in one shot. Excess amount handling is
 * server-side (creates on-account balance for the patient).
 */

import type { InvoicePayment, PaymentMethod } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

const props = withDefaults(defineProps<{
  open: boolean
  invoiceId: string
  invoiceNumber?: string | null
  patientName?: string
  balanceDue: number
  total: number
}>(), {
  invoiceNumber: undefined,
  patientName: undefined
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'recorded', payment: InvoicePayment): void
}>()

const { t } = useI18n()
const { recordPayment } = useInvoices()
const { format: formatCurrency } = useCurrency()
const toast = useToast()

const isSubmitting = ref(false)
const errorMsg = ref<string | null>(null)

const title = computed(() => {
  const base = t('invoice.collect.title')
  const number = props.invoiceNumber ?? t('invoice.draftNoNumber')
  return `${base} · ${number}`
})

function fmt(value: number | string) {
  return formatCurrency(Number(value || 0))
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
    const recorded = await recordPayment(props.invoiceId, {
      amount: payload.amount,
      method: payload.method,
      payment_date: payload.payment_date,
      reference: payload.reference,
      notes: payload.notes
    })
    toast.add({
      title: t('invoice.messages.paymentRecorded'),
      description: fmt(payload.amount),
      color: 'success'
    })
    emit('recorded', recorded)
    emit('update:open', false)
  } catch (e: unknown) {
    errorMsg.value = errorMessage(e, t('invoice.errors.recordPayment'))
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
    :pending-amount="balanceDue"
    :submitting="isSubmitting"
    :error="errorMsg"
    :submit-label="t('invoice.collect.submit')"
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
          {{ t('invoice.collect.noteInvoiceSettled') }}
          <strong>{{ fmt(amount) }}</strong>
          {{ t('invoice.collect.noteToOnAccount') }}
        </p>
        <p v-else-if="amount > pending">
          <strong>{{ fmt(pending) }}</strong>
          {{ t('invoice.collect.noteToInvoice') }}
          <strong>{{ fmt(amount - pending) }}</strong>
          {{ t('invoice.collect.noteExcessToOnAccount') }}
        </p>
        <p v-else-if="amount === pending">
          {{ t('invoice.collect.noteFullySettled') }}
        </p>
        <p v-else>
          <strong>{{ fmt(amount) }}</strong>
          {{ t('invoice.collect.noteAppliedToInvoice') }}
          {{ t('invoice.collect.notePendingAfter') }}
          <strong>{{ fmt(pending - amount) }}</strong>.
        </p>
      </section>
    </template>
  </CollectAmountModal>
</template>
