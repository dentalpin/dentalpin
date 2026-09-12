<script setup lang="ts">
/**
 * Hand-off panel rendered by the core "Record payment" modal once a
 * Razorpay rail is submitted (`payments.create.methods` contract).
 * Opens the `PaymentRequest`, shows the QR / Checkout.js / payment
 * link, polls until `payment_gateways` reports a terminal state and
 * only then emits `created` with the real Payment — never on a browser
 * callback alone. `back` returns to the form (cancel / try again).
 */

import type { PaymentAllocationCreate, PaymentRecord } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'
import type { GatewayMethod, PaymentRequest } from '../composables/useRazorpay'

const props = defineProps<{
  form: {
    patient_id: string
    patient_name: string
    amount: number
    allocations: PaymentAllocationCreate[]
  }
  method: GatewayMethod
}>()

const emit = defineEmits<{
  (e: 'created', payment: PaymentRecord): void
  (e: 'back'): void
}>()

const { t } = useI18n()
const toast = useToast()
const { format: formatCurrency } = useCurrency()
const { get: getPayment } = usePayments()
const { createPaymentRequest, getPaymentRequest, refreshPaymentRequest, cancelPaymentRequest } = useRazorpay()

const request = ref<PaymentRequest | null>(null)
const error = ref<string | null>(null)
const isRefreshing = ref(false)
const TERMINAL = ['succeeded', 'failed', 'expired', 'cancelled']
let pollTimer: ReturnType<typeof setInterval> | null = null

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
}

async function settle(fresh: PaymentRequest) {
  request.value = fresh
  if (!TERMINAL.includes(fresh.state)) return
  stopPolling()
  if (fresh.state === 'succeeded' && fresh.payment_id) {
    const payment = await getPayment(fresh.payment_id)
    if (payment) {
      toast.add({ title: t('common.success'), description: t('razorpay.collect.success'), color: 'success' })
      emit('created', payment)
    }
  }
}

function startPolling(id: string) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      await settle(await getPaymentRequest(id))
    } catch {
      // transient poll failure — next tick retries
    }
  }, 3000)
}

let checkoutJs: Promise<void> | null = null
function loadCheckoutJs(): Promise<void> {
  if (checkoutJs) return checkoutJs
  checkoutJs = new Promise((resolve, reject) => {
    if ((window as unknown as { Razorpay?: unknown }).Razorpay) return resolve()
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('checkout.js failed to load'))
    document.head.appendChild(script)
  })
  return checkoutJs
}

async function openCheckout(req: PaymentRequest) {
  if (!req.checkout?.checkout_payload) return
  try {
    await loadCheckoutJs()
  } catch {
    toast.add({ title: t('common.error'), description: t('razorpay.collect.checkoutLoadError'), color: 'error' })
    return
  }
  interface RazorpayCtor { new (options: Record<string, unknown>): { open: () => void } }
  const Ctor = (window as unknown as { Razorpay: RazorpayCtor }).Razorpay
  new Ctor({
    ...req.checkout.checkout_payload,
    handler: () => startPolling(req.id) // browser callback — cue to poll, never authoritative
  }).open()
}

onMounted(async () => {
  try {
    const created = await createPaymentRequest({
      patient_id: props.form.patient_id,
      amount: props.form.amount,
      method: props.method,
      allocations: props.form.allocations
    })
    request.value = created
    if (props.method === 'card') await openCheckout(created)
    startPolling(created.id)
  } catch (e) {
    error.value = errorMessage(e, t('razorpay.collect.createError'))
  }
})

onBeforeUnmount(stopPolling)

async function refresh() {
  if (!request.value) return
  isRefreshing.value = true
  try {
    await settle(await refreshPaymentRequest(request.value.id))
  } finally {
    isRefreshing.value = false
  }
}

async function cancel() {
  stopPolling()
  if (request.value && !TERMINAL.includes(request.value.state)) {
    try {
      await cancelPaymentRequest(request.value.id)
    } catch {
      // already terminal server-side — going back is still right
    }
  }
  emit('back')
}

async function copyLink() {
  const url = request.value?.checkout?.redirect_url
  if (!url) return
  try {
    await navigator.clipboard.writeText(url)
    toast.add({ title: t('razorpay.collect.linkCopied'), color: 'success' })
  } catch {
    // clipboard unavailable — the field stays visible to copy by hand
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between rounded-token-md bg-surface-muted p-3">
      <span class="text-sm truncate">{{ form.patient_name }}</span>
      <span class="font-semibold tnum">{{ formatCurrency(form.amount) }}</span>
    </div>

    <p
      v-if="error"
      class="text-sm text-danger-accent"
    >
      {{ error }}
    </p>

    <div
      v-else-if="!request || request.state === 'awaiting_customer_action' || request.state === 'pending'"
      class="space-y-3"
    >
      <div
        v-if="method === 'qr' && request?.checkout?.qr_image_url"
        class="text-center"
      >
        <img
          :src="request.checkout.qr_image_url"
          :alt="t('razorpay.collect.scanQr')"
          class="mx-auto w-48 h-48 rounded-token-md border border-default"
        >
        <p class="text-caption text-subtle mt-2">
          {{ t('razorpay.collect.scanQr') }}
        </p>
      </div>
      <div
        v-else-if="request?.checkout?.redirect_url"
        class="flex items-center gap-2"
      >
        <UInput
          :model-value="request.checkout.redirect_url"
          readonly
          class="flex-1 font-mono text-xs"
        />
        <UButton
          variant="soft"
          icon="i-lucide-copy"
          @click="copyLink"
        >
          {{ t('common.copy') }}
        </UButton>
      </div>
      <div
        v-else-if="request?.checkout?.checkout_payload"
        class="text-center"
      >
        <UButton
          color="primary"
          icon="i-lucide-credit-card"
          @click="openCheckout(request)"
        >
          {{ t('razorpay.collect.openCheckout') }}
        </UButton>
      </div>
      <div class="flex items-center justify-center gap-2 text-caption text-subtle">
        <UIcon
          name="i-lucide-loader-2"
          class="animate-spin w-4 h-4"
        />
        {{ t('razorpay.collect.waiting') }}
      </div>
    </div>

    <div
      v-else-if="request.state === 'authorised_awaiting_capture'"
      class="text-center py-2 text-sm"
    >
      {{ t('razorpay.collect.authorizing') }}
    </div>

    <div
      v-else-if="request.state !== 'succeeded'"
      class="text-center space-y-1 py-2"
    >
      <p class="font-medium">
        {{ t(`razorpay.collect.states.${request.state}`) }}
      </p>
      <p
        v-if="request.error_message"
        class="text-caption text-subtle"
      >
        {{ request.error_message }}
      </p>
    </div>

    <div class="flex justify-end gap-2 pt-2 border-t border-default">
      <UButton
        variant="ghost"
        @click="cancel"
      >
        {{ error || (request && TERMINAL.includes(request.state)) ? t('razorpay.collect.tryAgain') : t('common.cancel') }}
      </UButton>
      <UButton
        v-if="request && !TERMINAL.includes(request.state)"
        variant="soft"
        :loading="isRefreshing"
        @click="refresh"
      >
        {{ t('razorpay.collect.checkStatus') }}
      </UButton>
    </div>
  </div>
</template>
