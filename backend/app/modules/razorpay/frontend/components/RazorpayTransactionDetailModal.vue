<script setup lang="ts">
/**
 * Transaction detail: gateway audit trail, allocation, settlement, and
 * refund history for one gateway-collected core Payment — plus the
 * "refund via Razorpay" action. Fully separate from the core
 * `RefundConfirmModal` (manual refunds keep using that).
 */

import type { PaymentRecord } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import type { GatewayInfo } from '../composables/useRazorpay'

const props = defineProps<{
  open: boolean
  payment: PaymentRecord
  info: GatewayInfo
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'updated', info: GatewayInfo): void
}>()

const { t, locale } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { format: formatCurrency } = useCurrency()
const { getGatewayInfo, createGatewayRefund } = useRazorpay()

const canRefund = computed(() => can(PERMISSIONS.payments.recordRefund))

const REASON_CODES = ['duplicate', 'overpaid', 'treatment_cancelled', 'dispute', 'other']

const showRefundForm = ref(false)
const isSubmittingRefund = ref(false)
const refundForm = ref({ amount: 0, reason_code: 'duplicate', reason_note: '' })

const refundableAmount = computed(() => Number(props.payment.net_amount ?? 0))

function formatDate(s: string | null | undefined): string {
  if (!s) return '—'
  return new Date(s).toLocaleString(locale.value)
}

function stateColor(state: string): 'success' | 'error' | 'warning' | 'neutral' {
  if (state === 'succeeded' || state === 'completed') return 'success'
  if (state === 'failed' || state === 'expired' || state === 'cancelled') return 'error'
  if (state === 'processing' || state === 'requested' || state === 'awaiting_customer_action') return 'warning'
  return 'neutral'
}

function openRefundForm() {
  refundForm.value = { amount: refundableAmount.value, reason_code: 'duplicate', reason_note: '' }
  showRefundForm.value = true
}

async function submitRefund() {
  if (!(refundForm.value.amount > 0) || refundForm.value.amount > refundableAmount.value) return
  isSubmittingRefund.value = true
  try {
    await createGatewayRefund({
      payment_id: props.payment.id,
      amount: Number(refundForm.value.amount),
      reason_code: refundForm.value.reason_code,
      reason_note: refundForm.value.reason_note || undefined
    })
    const fresh = await getGatewayInfo(props.payment.id)
    emit('updated', fresh)
    showRefundForm.value = false
    toast.add({ title: t('common.success'), description: t('razorpay.detail.refundRequested'), color: 'success' })
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('razorpay.detail.refundError')),
      color: 'error'
    })
  } finally {
    isSubmittingRefund.value = false
  }
}
</script>

<template>
  <UModal
    :open="open"
    :title="t('razorpay.detail.title')"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div
        v-if="info.request"
        class="space-y-5"
      >
        <!-- Audit trail -->
        <div>
          <h4 class="text-caption font-semibold text-subtle uppercase tracking-wide mb-2">
            {{ t('razorpay.detail.auditTrail') }}
          </h4>
          <dl class="space-y-1.5 text-sm">
            <div class="flex items-center justify-between">
              <dt class="text-subtle">
                {{ t('razorpay.detail.method') }}
              </dt>
              <dd>{{ t(`razorpay.collect.methods.${info.request.requested_method}`) }}</dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-subtle">
                {{ t('razorpay.detail.status') }}
              </dt>
              <dd>
                <UBadge
                  :color="stateColor(info.request.state)"
                  variant="subtle"
                  size="xs"
                >
                  {{ t(`razorpay.detail.states.${info.request.state}`) }}
                </UBadge>
              </dd>
            </div>
            <div
              v-if="info.request.provider_payment_reference"
              class="flex items-center justify-between"
            >
              <dt class="text-subtle">
                {{ t('razorpay.detail.providerReference') }}
              </dt>
              <dd class="font-mono text-xs">
                {{ info.request.provider_payment_reference }}
              </dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-subtle">
                {{ t('razorpay.detail.initiated') }}
              </dt>
              <dd>{{ formatDate(info.request.created_at) }}</dd>
            </div>
            <div
              v-if="info.request.confirmed_at"
              class="flex items-center justify-between"
            >
              <dt class="text-subtle">
                {{ t('razorpay.detail.confirmed') }}
              </dt>
              <dd>{{ formatDate(info.request.confirmed_at) }}</dd>
            </div>
          </dl>
        </div>

        <!-- Allocation -->
        <div v-if="payment.allocations?.length">
          <h4 class="text-caption font-semibold text-subtle uppercase tracking-wide mb-2">
            {{ t('razorpay.detail.allocation') }}
          </h4>
          <ul class="space-y-1 text-sm">
            <li
              v-for="a in payment.allocations"
              :key="a.id"
              class="flex items-center justify-between"
            >
              <span class="text-subtle">
                {{ a.target_type === 'budget' ? t('payments.new.allocationToBudget') : t('payments.new.allocationOnAccount') }}
              </span>
              <span class="tabular-nums">{{ formatCurrency(a.amount) }}</span>
            </li>
          </ul>
        </div>

        <!-- Refund history -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <h4 class="text-caption font-semibold text-subtle uppercase tracking-wide">
              {{ t('razorpay.detail.refundHistory') }}
            </h4>
            <UButton
              v-if="canRefund && refundableAmount > 0 && !showRefundForm"
              size="xs"
              variant="soft"
              color="warning"
              icon="i-lucide-rotate-ccw"
              @click="openRefundForm"
            >
              {{ t('razorpay.detail.refundAction') }}
            </UButton>
            <span
              v-else-if="!canRefund"
              class="text-caption text-subtle"
            >
              {{ t('razorpay.detail.refundPermissionDenied') }}
            </span>
          </div>

          <div
            v-if="showRefundForm"
            class="space-y-3 p-3 rounded-token-md bg-surface-muted mb-3"
          >
            <UFormField :label="t('payments.refund.amount')">
              <UInput
                v-model.number="refundForm.amount"
                type="number"
                step="0.01"
                :max="refundableAmount"
                min="0"
              />
              <template #hint>
                {{ t('razorpay.detail.maxRefundable', { amount: formatCurrency(refundableAmount) }) }}
              </template>
            </UFormField>
            <UFormField :label="t('payments.refund.reason')">
              <USelectMenu
                v-model="refundForm.reason_code"
                :items="REASON_CODES.map(c => ({ label: t(`payments.refund.reasonCodes.${c}`), value: c }))"
                value-key="value"
              />
            </UFormField>
            <UFormField :label="t('payments.refund.note')">
              <UInput v-model="refundForm.reason_note" />
            </UFormField>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                size="xs"
                @click="showRefundForm = false"
              >
                {{ t('payments.new.cancel') }}
              </UButton>
              <UButton
                size="xs"
                color="warning"
                :loading="isSubmittingRefund"
                :disabled="!(refundForm.amount > 0) || refundForm.amount > refundableAmount"
                @click="submitRefund"
              >
                {{ t('payments.refund.submit') }}
              </UButton>
            </div>
          </div>

          <div
            v-if="info.refund_requests.length === 0"
            class="text-caption text-subtle"
          >
            {{ t('razorpay.detail.noRefunds') }}
          </div>
          <ul
            v-else
            class="space-y-2"
          >
            <li
              v-for="r in info.refund_requests"
              :key="r.id"
              class="flex items-center justify-between text-sm"
            >
              <div class="flex items-center gap-2">
                <UBadge
                  :color="stateColor(r.state)"
                  variant="subtle"
                  size="xs"
                >
                  {{ t(`razorpay.detail.refundStates.${r.state}`) }}
                </UBadge>
                <span class="text-caption text-subtle">{{ formatDate(r.created_at) }}</span>
              </div>
              <span class="tabular-nums">{{ formatCurrency(r.requested_amount) }}</span>
            </li>
          </ul>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end">
        <UButton
          variant="ghost"
          @click="emit('update:open', false)"
        >
          {{ t('common.close') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>
