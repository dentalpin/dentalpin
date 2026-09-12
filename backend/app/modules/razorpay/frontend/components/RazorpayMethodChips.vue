<script setup lang="ts">
/**
 * Slot entry into `payments.create.methods` (India clinics only — see
 * plugins/slots.client.ts). Renders the gateway rails as chips inside
 * the core "Record payment" modal's method row; picking one hands the
 * modal's form to `RazorpayCollectPanel` on submit. Chips reuse the
 * modal's unscoped `.method-chip` style so they look native.
 */

import type { Component } from 'vue'
import type { GatewayMethod } from '../composables/useRazorpay'
import RazorpayCollectPanel from './RazorpayCollectPanel.vue'

// Mirrors payments' PaymentCreateModal `ModuleRail` contract (kept
// structural on purpose — a module never imports another layer's code).
interface Rail {
  id: string
  label: string
  panel: Component
  panelProps?: Record<string, unknown>
}

interface Ctx {
  clinic: unknown
  selectedId: string | null
  select: (rail: Rail) => void
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()
const { getSettings } = useRazorpay()

const RAILS: { id: string, method: GatewayMethod, icon: string, labelKey: string }[] = [
  { id: 'razorpay.qr', method: 'qr', icon: 'i-lucide-qr-code', labelKey: 'razorpay.collect.railUpiQr' },
  { id: 'razorpay.card', method: 'card', icon: 'i-lucide-zap', labelKey: 'razorpay.collect.railCheckout' },
  { id: 'razorpay.payment_link', method: 'payment_link', icon: 'i-lucide-link', labelKey: 'razorpay.collect.railPaymentLink' }
]

// Only an active, keyed settings row offers the rails; until we know,
// the chips render enabled so the row doesn't jump.
const configured = ref(true)
onMounted(async () => {
  try {
    const s = await getSettings()
    configured.value = s.is_active && s.has_key_secret
  } catch {
    configured.value = false
  }
})

function pick(rail: typeof RAILS[number]) {
  props.ctx.select({
    id: rail.id,
    label: t(rail.labelKey),
    panel: markRaw(RazorpayCollectPanel),
    panelProps: { method: rail.method }
  })
}
</script>

<template>
  <button
    v-for="rail in RAILS"
    :key="rail.id"
    type="button"
    class="method-chip"
    :class="{ active: ctx.selectedId === rail.id }"
    :disabled="!configured"
    :title="!configured ? t('razorpay.collect.notConfiguredHint') : undefined"
    @click="pick(rail)"
  >
    <UIcon
      :name="rail.icon"
      class="w-4 h-4"
    />
    <span>{{ t(rail.labelKey) }}</span>
  </button>
</template>
