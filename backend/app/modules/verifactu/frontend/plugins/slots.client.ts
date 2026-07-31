import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

interface InvoiceCtx {
  invoice?: { compliance_data?: Record<string, unknown> | null } | null
  clinic?: { country?: string | null, settings?: { country?: string | null } | null } | null
}

export default defineNuxtPlugin(() => {
  registerSlot('settings.sections', {
    id: 'verifactu.settings.cards',
    component: defineAsyncComponent(() => import('../components/SettingsCardsSlot.vue')),
    order: 60,
    category: 'billing',
    labelKey: 'verifactu.settingsCards.title',
    descriptionKey: 'verifactu.settingsCards.description',
    searchKeywords: ['verifactu', 'aeat', 'impuesto', 'factura electronica', 'factura electrónica', 'rd 1007/2023']
  })

  // Renders the Verifactu state panel inside the invoice detail page
  // for ES clinics (or whenever the invoice already carries an ES
  // compliance block — e.g. issued before country setting was set).
  // Billing knows nothing about this entry.
  registerSlot('invoice.detail.compliance', {
    id: 'verifactu.invoice.detail.compliance',
    component: defineAsyncComponent(() => import('../components/verifactu/InvoiceVerifactuSlot.vue')),
    order: 10,
    condition: (raw) => {
      const ctx = (raw ?? {}) as InvoiceCtx
      const country = ctx.clinic?.country ?? ctx.clinic?.settings?.country ?? null
      const hasES = !!(ctx.invoice?.compliance_data as Record<string, unknown> | undefined)?.ES
      return country === 'ES' || hasES
    }
  })

  // Global banner. The layout renders <ModuleSlot name="app.banners">
  // unconditionally; the banner component self-fetches /health and
  // hides itself when rejected_count is zero. Fast no-op for clinics
  // that don't use Verifactu.
  registerSlot('app.banners', {
    id: 'verifactu.app.banners.rejected',
    component: defineAsyncComponent(
      () => import('../components/verifactu/RejectedGlobalBanner.vue')
    ),
    order: 10
  })

  // Compact AEAT chip in each invoice list row + invoice detail header.
  // Same component (ComplianceBadge) — the slot ctx carries the
  // invoice. Hidden automatically when the row has no compliance_data
  // for ES (badge composable returns null).
  const isESInvoiceCtx = (raw: unknown) => {
    const ctx = (raw ?? {}) as InvoiceCtx
    const country = ctx.clinic?.country ?? ctx.clinic?.settings?.country ?? null
    const hasES = !!(ctx.invoice?.compliance_data as Record<string, unknown> | undefined)?.ES
    return country === 'ES' || hasES
  }

  registerSlot('invoice.list.row.meta', {
    id: 'verifactu.invoice.list.row.meta',
    component: defineAsyncComponent(
      () => import('../components/verifactu/ComplianceBadge.vue')
    ),
    order: 10,
    condition: isESInvoiceCtx
  })

  registerSlot('invoice.detail.header.meta', {
    id: 'verifactu.invoice.detail.header.meta',
    component: defineAsyncComponent(
      () => import('../components/verifactu/ComplianceBadge.vue')
    ),
    order: 10,
    condition: isESInvoiceCtx
  })

  // Toolbar filter on the invoice list. Multi-select severity +
  // "Solo problemas" shortcut. Mounted only for ES clinics.
  registerSlot('invoice.list.toolbar.filters', {
    id: 'verifactu.invoice.list.toolbar.filters',
    component: defineAsyncComponent(
      () => import('../components/verifactu/ComplianceFilter.vue')
    ),
    order: 10,
    condition: (raw) => {
      const ctx = (raw ?? {}) as { clinic?: { country?: string | null, settings?: { country?: string | null } | null } }
      const country = ctx.clinic?.country ?? ctx.clinic?.settings?.country ?? null
      return country === 'ES'
    }
  })
})
