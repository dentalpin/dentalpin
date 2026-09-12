import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

interface ClinicCtx {
  clinic?: { country?: string | null, settings?: { country?: string | null } | null } | null
}

// Same country-gating pattern india_gst/verifactu already use: read
// from the server-authoritative clinic object, never a client-editable
// field. Razorpay UPI/QR/payment-link collection only makes sense for
// India clinics — everything else (non-India) sees nothing from this
// module at all.
function isIndiaClinicCtx(raw: unknown): boolean {
  const ctx = (raw ?? {}) as ClinicCtx
  const country = ctx.clinic?.country ?? ctx.clinic?.settings?.country ?? null
  return country === 'IN'
}

export default defineNuxtPlugin(() => {
  registerSlot('settings.sections', {
    id: 'razorpay.settings.cards',
    component: defineAsyncComponent(() => import('../components/RazorpaySettingsCardsSlot.vue')),
    order: 62,
    category: 'billing',
    labelKey: 'razorpay.settingsCards.title',
    descriptionKey: 'razorpay.settingsCards.description',
    searchKeywords: ['razorpay', 'upi', 'gateway', 'payment', 'qr', 'india']
  })

  // Gateway rails inside the core "Record payment" modal's method row
  // (#263 review, point 3): the modal stays a plain form; on submit it
  // hands the validated form to RazorpayCollectPanel, which owns the
  // QR / Checkout.js / link wait, polling and expiry.
  registerSlot('payments.create.methods', {
    id: 'razorpay.payments.create.methods',
    component: defineAsyncComponent(() => import('../components/RazorpayMethodChips.vue')),
    order: 10,
    condition: isIndiaClinicCtx
  })

  // Small "Razorpay · UPI" badge on each gateway-collected payment row
  // — renders nothing for a manually-recorded payment.
  registerSlot('payments.list.row.meta', {
    id: 'razorpay.payments.list.row.meta',
    component: defineAsyncComponent(() => import('../components/RazorpayPaymentBadge.vue')),
    order: 10,
    condition: isIndiaClinicCtx
  })
})
