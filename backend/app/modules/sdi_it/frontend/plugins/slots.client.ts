/**
 * Invoice-page slots for the SDI module. Billing has no compile-time
 * dependency on this layer; the condition keeps the slots invisible
 * outside Italian clinics (or invoices that already carry an IT block).
 */
import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

interface InvoiceCtx {
  invoice?: { compliance_data?: Record<string, unknown> | null } | null
  clinic?: { country?: string | null, settings?: { country?: string | null } | null } | null
}

const isITInvoiceCtx = (raw: unknown) => {
  const ctx = (raw ?? {}) as InvoiceCtx
  const country = ctx.clinic?.country ?? ctx.clinic?.settings?.country ?? null
  const hasIT = !!(ctx.invoice?.compliance_data as Record<string, unknown> | undefined)?.IT
  return country === 'IT' || hasIT
}

export default defineNuxtPlugin(() => {
  registerSlot('invoice.detail.compliance', {
    id: 'sdi_it.invoice.detail.compliance',
    component: defineAsyncComponent(() => import('../components/sdi/InvoiceSdiSlot.vue')),
    order: 20,
    condition: isITInvoiceCtx
  })
  registerSlot('invoice.list.row.meta', {
    id: 'sdi_it.invoice.list.row.meta',
    component: defineAsyncComponent(() => import('../components/sdi/SdiBadge.vue')),
    order: 20,
    condition: isITInvoiceCtx
  })
  registerSlot('invoice.detail.header.meta', {
    id: 'sdi_it.invoice.detail.header.meta',
    component: defineAsyncComponent(() => import('../components/sdi/SdiBadge.vue')),
    order: 20,
    condition: isITInvoiceCtx
  })
})
