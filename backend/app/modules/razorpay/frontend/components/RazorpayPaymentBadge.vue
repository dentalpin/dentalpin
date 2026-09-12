<script setup lang="ts">
/**
 * Slot entry into `payments.list.row.meta` on the payments list
 * (`/payments`). Renders nothing for a payment that wasn't
 * gateway-collected (`GET .../gateway-info` returns `request: null`)
 * — every non-gateway payment row is completely unaffected.
 */

import type { PaymentRecord } from '~~/app/types'
import type { GatewayInfo } from '../composables/useRazorpay'

interface Ctx {
  payment: PaymentRecord
  clinic: { id: string, country?: string | null, settings?: { country?: string | null } | null } | null
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()
const { getGatewayInfo } = useRazorpay()

const info = ref<GatewayInfo | null>(null)
const isLoading = ref(true)
const showDetail = ref(false)

onMounted(async () => {
  // `reference` is "razorpay:<payment id>" for every gateway-collected
  // payment (set by PaymentRequestService.confirm) — skip the round trip
  // for the manual rows so a 20-row page costs 0 extra requests, not 20.
  if (!props.ctx.payment.reference?.startsWith('razorpay:')) {
    isLoading.value = false
    return
  }
  try {
    info.value = await getGatewayInfo(props.ctx.payment.id)
  } catch {
    info.value = null
  } finally {
    isLoading.value = false
  }
})

const label = computed(() => {
  const method = info.value?.request?.requested_method
  if (!method) return 'Razorpay'
  return `Razorpay · ${t(`razorpay.collect.methods.${method}`)}`
})
</script>

<template>
  <button
    v-if="!isLoading && info?.request"
    type="button"
    class="inline-flex items-center gap-1 text-caption text-primary-accent hover:underline"
    @click="showDetail = true"
  >
    <UIcon
      name="i-lucide-credit-card"
      class="w-3.5 h-3.5"
    />
    {{ label }}
  </button>

  <RazorpayTransactionDetailModal
    v-if="info?.request"
    v-model:open="showDetail"
    :payment="ctx.payment"
    :info="info"
    @updated="info = $event"
  />
</template>
