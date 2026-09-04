<script setup lang="ts">
/**
 * Refund confirmation modal — small form for `POST /payments/{id}/refunds`.
 *
 * Used from the patient ledger timeline overflow menu. Pre-fills the
 * amount and method from the source payment; the operator can override
 * both (partial refund, different refund channel) and must select a
 * reason code. Permission gating happens upstream — this modal only
 * renders when the caller already passed `payments.record.refund`.
 */

import type { PaymentMethod, PaymentRefund, RefundReason } from '~~/app/types'

const props = withDefaults(defineProps<{
  open: boolean
  paymentId: string
  defaultAmount?: number
  defaultMethod?: PaymentMethod
}>(), {
  defaultAmount: 0,
  defaultMethod: 'cash'
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'refunded', refund: PaymentRefund): void
}>()

const { t } = useI18n()
const { refund } = usePayments()

const BASE_METHODS: PaymentMethod[] = [
  'cash', 'card', 'bank_transfer', 'direct_debit', 'insurance', 'other'
]
// The source payment's method (e.g. upi / netbanking, #365) must always be
// selectable, whatever the clinic's country.
const PAYMENT_METHODS = computed<PaymentMethod[]>(() =>
  props.defaultMethod && !BASE_METHODS.includes(props.defaultMethod)
    ? [...BASE_METHODS, props.defaultMethod]
    : BASE_METHODS
)

const REASON_CODES: RefundReason[] = [
  'duplicate', 'overpaid', 'treatment_cancelled', 'dispute', 'other'
]

function buildInitialForm() {
  return {
    amount: Number(props.defaultAmount ?? 0),
    method: props.defaultMethod ?? 'cash' as PaymentMethod,
    reason_code: 'other' as RefundReason,
    reason_note: ''
  }
}

const form = ref(buildInitialForm())
const formError = ref<string | null>(null)
const isSubmitting = ref(false)

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    form.value = buildInitialForm()
    formError.value = null
  }
})

const isValid = computed(() => Number(form.value.amount) > 0 && !!form.value.reason_code)

async function submit() {
  if (!isValid.value || isSubmitting.value) return
  formError.value = null
  isSubmitting.value = true
  try {
    const created = await refund(props.paymentId, {
      amount: Number(form.value.amount),
      method: form.value.method,
      reason_code: form.value.reason_code,
      reason_note: form.value.reason_note || undefined
    })
    if (created) {
      emit('refunded', created)
      emit('update:open', false)
    } else {
      formError.value = t('payments.patientPanel.refundModal.errorGeneric')
    }
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <UModal
    :open="open"
    :title="t('payments.patientPanel.refundModal.title')"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div class="space-y-3">
        <UFormField :label="t('payments.patientPanel.refundModal.amount')">
          <UInput
            v-model.number="form.amount"
            type="number"
            step="0.01"
            min="0"
          />
        </UFormField>

        <UFormField :label="t('payments.patientPanel.refundModal.method')">
          <USelect
            v-model="form.method"
            :items="PAYMENT_METHODS.map(m => ({ label: t(`payments.methods.${m}`), value: m }))"
          />
        </UFormField>

        <UFormField :label="t('payments.patientPanel.refundModal.reason')">
          <USelect
            v-model="form.reason_code"
            :items="REASON_CODES.map(r => ({ label: t(`payments.refund.reasonCodes.${r}`), value: r }))"
          />
        </UFormField>

        <UFormField :label="t('payments.patientPanel.refundModal.note')">
          <UInput v-model="form.reason_note" />
        </UFormField>

        <p
          v-if="formError"
          class="text-sm text-danger-accent"
        >
          {{ formError }}
        </p>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton
          variant="ghost"
          color="neutral"
          @click="emit('update:open', false)"
        >
          {{ t('payments.patientPanel.refundModal.cancel') }}
        </UButton>
        <UButton
          color="error"
          :loading="isSubmitting"
          :disabled="!isValid"
          @click="submit"
        >
          {{ t('payments.patientPanel.refundModal.submit') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>
