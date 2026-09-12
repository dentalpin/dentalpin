/**
 * Sistema TS slots: the opposition card in the patient summary and the
 * submission panel on the invoice page. Both hide themselves outside
 * Italian clinics (the components check the clinic country); the invoice
 * panel additionally hides for B2B invoices, which are the SDI's.
 */
import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

interface InvoiceCtx {
  clinic?: { country?: string | null, settings?: { country?: string | null } | null } | null
}

const isITClinic = (raw: unknown) => {
  const ctx = (raw ?? {}) as InvoiceCtx
  const country = ctx.clinic?.country ?? ctx.clinic?.settings?.country ?? null
  return country === 'IT'
}

export default defineNuxtPlugin(() => {
  registerSlot('patient.summary.cards', {
    id: 'sistema_ts.patient.summary.cards.opposition',
    component: defineAsyncComponent(() => import('../components/ts/PatientOppositionCard.vue')),
    order: 55,
    permission: 'sistema_ts.opposition.read'
  })
  registerSlot('invoice.detail.compliance', {
    id: 'sistema_ts.invoice.detail.compliance',
    component: defineAsyncComponent(() => import('../components/ts/InvoiceTsSlot.vue')),
    order: 30,
    permission: 'sistema_ts.documents.read',
    condition: isITClinic
  })
})
