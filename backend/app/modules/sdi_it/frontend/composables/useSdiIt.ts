import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface SdiSettings {
  enabled: boolean
  transport: 'manual' | 'pec'
  regime_fiscale: string
  bollo_virtuale: boolean
  riferimento_normativo: string
  progressivo_invio: number
  last_receipt_at: string | null
  last_error: string | null
  pec_address: string | null
  sdi_pec_address: string
  smtp_host: string | null
  smtp_port: number
  smtp_username: string | null
  has_smtp_password: boolean
  imap_host: string | null
  imap_port: number
  imap_folder: string
  last_pec_poll_at: string | null
  next_send_after: string | null
}

export interface SdiRecord {
  id: string
  invoice_id: string
  tipo_documento: string
  invoice_number: string
  issue_date: string
  gross_amount: string
  recipient_name: string | null
  recipient_tax_id: string | null
  codice_destinatario: string
  progressivo: string
  file_name: string
  state: string
  attempts: number
  next_attempt_at: string | null
  transport: string | null
  message_id: string | null
  sdi_identifier: string | null
  receipt_type: string | null
  receipt_at: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  sent_at: string | null
  finished_at: string | null
}

export interface ReceiptImportResult {
  record_id: string
  receipt_type: string
  state: string
  errors: { code: string, description: string }[]
}

export const SDI_STATES = ['pending', 'exported', 'delivered', 'undeliverable', 'rejected', 'failed'] as const

/** ISO timestamp → the viewer's locale, short; raw ISO with microseconds reads badly in a panel. */
export function fmtWhen(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString() : ''
}

export function useSdiIt() {
  const api = useApi()

  async function fetchSettings(): Promise<SdiSettings> {
    return (await api.get<ApiResponse<SdiSettings>>('/api/v1/sdi_it/settings')).data
  }

  async function saveSettings(payload: Record<string, unknown>): Promise<SdiSettings> {
    return (await api.put<ApiResponse<SdiSettings>>('/api/v1/sdi_it/settings', payload, { errorToast: false })).data
  }

  async function testPec(): Promise<{ smtp: string, imap: string }> {
    return (await api.post<ApiResponse<{ smtp: string, imap: string }>>('/api/v1/sdi_it/pec/test', {}, { errorToast: false })).data
  }

  async function fetchRecords(query: Record<string, string | number | undefined | null>): Promise<PaginatedResponse<SdiRecord>> {
    return await api.get<PaginatedResponse<SdiRecord>>('/api/v1/sdi_it/records', { query })
  }

  async function fetchLatestForInvoice(invoiceId: string): Promise<SdiRecord | null> {
    try {
      return (await api.get<ApiResponse<SdiRecord | null>>(`/api/v1/sdi_it/records/by-invoice/${invoiceId}`)).data
    } catch {
      return null
    }
  }

  /** Blob download of the FPR12 file; the browser saves it under its SDI name.
   *  ``useApi().raw`` attaches the session cookies (ADR 0023). */
  async function downloadXml(record: SdiRecord): Promise<void> {
    const res = await api.raw(`/api/v1/sdi_it/records/${record.id}/xml`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = record.file_name
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  async function markExported(id: string): Promise<SdiRecord> {
    return (await api.post<ApiResponse<SdiRecord>>(`/api/v1/sdi_it/records/${id}/exported`, {})).data
  }

  async function requeue(id: string): Promise<SdiRecord> {
    return (await api.post<ApiResponse<SdiRecord>>(`/api/v1/sdi_it/records/${id}/requeue`, {})).data
  }

  async function importReceipt(xml: string, fileName?: string): Promise<ReceiptImportResult> {
    return (await api.post<ApiResponse<ReceiptImportResult>>('/api/v1/sdi_it/receipts', { xml, file_name: fileName ?? null }, { errorToast: false })).data
  }

  async function processNow(): Promise<Record<string, number>> {
    return (await api.post<ApiResponse<Record<string, number>>>('/api/v1/sdi_it/queue/process-now', {})).data
  }

  return { fetchSettings, saveSettings, testPec, fetchRecords, fetchLatestForInvoice, downloadXml, markExported, requeue, importReceipt, processNow }
}
