import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'

/**
 * #828: the backend sends `filename="name.pdf"`, quoted. A greedy
 * `/filename="?(.+)"?/` kept the closing quote, and Windows saved the
 * file as `name.pdf_`. Every PDF download must use the bare name.
 */
const raw = vi.fn()

mockNuxtImport('useApi', () => () => ({
  get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn(), raw
}))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: { value: 'en' } }))

function pdfResponse(disposition: string | null): Response {
  const headers = new Headers({ 'Content-Type': 'application/pdf' })
  if (disposition !== null) headers.set('Content-Disposition', disposition)
  return new Response(new Blob(['%PDF-1.7']), { status: 200, headers })
}

const downloads: Record<string, () => Promise<void>> = {
  'documents downloadDocument': async () => {
    const { useManagedDocuments } = await import('#module-layers/documents/frontend/composables/useManagedDocuments')
    await useManagedDocuments().downloadDocument('fff5f582-0000-0000-0000-000000000000')
  },
  'billing downloadPDF': async () => {
    const { useInvoices } = await import('#module-layers/billing/frontend/composables/useInvoices')
    await useInvoices().downloadPDF('inv-1')
  },
  'budget downloadPDF': async () => {
    const { useBudgets } = await import('#module-layers/budget/frontend/composables/useBudgets')
    await useBudgets().downloadPDF('bud-1')
  },
  'budget downloadSignedPDF': async () => {
    const { useBudgets } = await import('#module-layers/budget/frontend/composables/useBudgets')
    await useBudgets().downloadSignedPDF('bud-1')
  },
  'purchase_orders downloadPurchaseOrderPdf': async () => {
    const { useProcurement } = await import('#module-layers/purchase_orders/frontend/composables/useProcurement')
    await useProcurement().downloadPurchaseOrderPdf('po-1')
  }
}

describe.each(Object.entries(downloads))('%s', (_name, download) => {
  let saved: string[]

  beforeEach(() => {
    saved = []
    raw.mockReset()
    vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:test')
    vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {})
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download)
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('saves a quoted filename without the closing quote', async () => {
    raw.mockResolvedValue(pdfResponse('attachment; filename="medical_certificate_fff5f582.pdf"'))
    await download()
    expect(saved).toEqual(['medical_certificate_fff5f582.pdf'])
  })

  it('saves an unquoted filename as is', async () => {
    raw.mockResolvedValue(pdfResponse('attachment; filename=report.pdf'))
    await download()
    expect(saved).toEqual(['report.pdf'])
  })

  it('falls back to a generated .pdf name without the header', async () => {
    raw.mockResolvedValue(pdfResponse(null))
    await download()
    expect(saved).toHaveLength(1)
    expect(saved[0]).toMatch(/\.pdf$/)
  })
})
