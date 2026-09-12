interface ApiOk<T> { data: T }

export interface ExportFilters {
  date_from?: string
  date_to?: string
  status?: string[]
}

export interface ExportPreview {
  invoice_count: number
  payment_count: number
  total_base: string
  total_cuota: string
  total: string
  sample_invoices: Record<string, unknown>[]
  sample_payments: Record<string, unknown>[]
}

function qs(filters: ExportFilters, extra: Record<string, string> = {}): string {
  const p = new URLSearchParams()
  if (filters.date_from) p.append('date_from', filters.date_from)
  if (filters.date_to) p.append('date_to', filters.date_to)
  for (const s of filters.status ?? []) p.append('status', s)
  for (const [k, v] of Object.entries(extra)) p.append(k, v)
  return p.toString()
}

export function useAccountingExport() {
  const api = useApi()
  const config = useRuntimeConfig()

  async function preview(filters: ExportFilters): Promise<ApiOk<ExportPreview>> {
    const s = qs(filters)
    return await api.get<ApiOk<ExportPreview>>(
      `/api/v1/accounting_export/preview${s ? `?${s}` : ''}`
    )
  }

  // Authenticated blob download (JWT in header, so a plain <a href> won't do).
  async function download(filters: ExportFilters, separator: ',' | ';' = ';'): Promise<void> {
    const url = config.public.apiBaseUrl
      + `/api/v1/accounting_export/run?${qs(filters, { separator })}`
    const res = await fetch(url, { credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const blob = await res.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = `gestoria_${filters.date_from ?? 'inicio'}_${filters.date_to ?? 'fin'}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  }

  return { preview, download }
}
