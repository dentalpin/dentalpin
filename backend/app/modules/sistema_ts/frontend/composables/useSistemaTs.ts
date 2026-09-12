import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface TsSettings {
  enabled: boolean
  environment: 'test' | 'prod'
  username: string | null
  has_password: boolean
  has_pincode: boolean
  has_custom_certificate: boolean
  certificate_expires_at: string | null
  cf_proprietario: string | null
  codice_regione: string | null
  codice_asl: string | null
  codice_ssa: string | null
  dispositivo: string
  default_tipo_spesa: string
  sync_from: string | null
  last_response_at: string | null
  next_send_after: string | null
  last_error: string | null
  year: number
  deadline: string
  unsent_count: number
  accepted_count: number
  rejected_count: number
}

export interface TsDocument {
  id: string
  invoice_id: string
  patient_id: string
  operation: string
  num_documento: string
  data_emissione: string
  data_pagamento: string | null
  total_amount: string
  pagamento_tracciato: string
  flag_opposizione: boolean
  voci: { tipo_spesa: string, importo: string, aliquota_iva: string | null, natura_iva: string | null }[]
  state: string
  attempts: number
  next_attempt_at: string | null
  esito: number | null
  protocollo: string | null
  messages: { codice: string, descrizione: string, tipo: string }[] | null
  error_message: string | null
  environment: string | null
  created_at: string
  sent_at: string | null
  finished_at: string | null
}

export interface Opposition {
  patient_id: string
  opposed: boolean
  opposed_since: string | null
  revoked_at: string | null
  note: string | null
}

export interface ItemType {
  catalog_item_id: string
  tipo_spesa: string
  flag_tipo_spesa: string | null
}

export const TS_STATES = ['pending', 'sending', 'accepted', 'accepted_with_warnings', 'rejected', 'failed'] as const
export const TIPI_SPESA = ['SR', 'IC', 'AD', 'PI', 'SP', 'AA', 'TK', 'FC', 'AS', 'CT'] as const

/** ISO timestamp → the viewer's locale, short. */
export function fmtWhen(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString() : ''
}

/** ISO date (YYYY-MM-DD) → the viewer's locale. */
export function fmtDate(iso: string | null | undefined): string {
  return iso ? new Date(`${iso}T00:00:00`).toLocaleDateString() : ''
}

export function useSistemaTs() {
  const api = useApi()

  async function fetchSettings(): Promise<TsSettings> {
    return (await api.get<ApiResponse<TsSettings>>('/api/v1/sistema_ts/settings')).data
  }

  async function saveSettings(payload: Record<string, unknown>): Promise<TsSettings> {
    return (await api.put<ApiResponse<TsSettings>>('/api/v1/sistema_ts/settings', payload, { errorToast: false })).data
  }

  async function fetchDocuments(query: Record<string, string | number | undefined | null>): Promise<PaginatedResponse<TsDocument>> {
    return await api.get<PaginatedResponse<TsDocument>>('/api/v1/sistema_ts/documents', { query })
  }

  async function fetchForInvoice(invoiceId: string): Promise<TsDocument[]> {
    return (await api.get<ApiResponse<TsDocument[]>>(`/api/v1/sistema_ts/documents/by-invoice/${invoiceId}`)).data
  }

  async function retry(id: string): Promise<TsDocument> {
    return (await api.post<ApiResponse<TsDocument>>(`/api/v1/sistema_ts/documents/${id}/retry`, {})).data
  }

  async function processNow(): Promise<Record<string, number>> {
    return (await api.post<ApiResponse<Record<string, number>>>('/api/v1/sistema_ts/queue/process-now', {})).data
  }

  async function fetchOpposition(patientId: string): Promise<Opposition> {
    return (await api.get<ApiResponse<Opposition>>(`/api/v1/sistema_ts/opposition/${patientId}`)).data
  }

  async function setOpposition(patientId: string, opposed: boolean, note?: string | null): Promise<Opposition> {
    return (await api.put<ApiResponse<Opposition>>(`/api/v1/sistema_ts/opposition/${patientId}`, { opposed, note: note ?? null })).data
  }

  async function fetchItemTypes(): Promise<ItemType[]> {
    return (await api.get<ApiResponse<ItemType[]>>('/api/v1/sistema_ts/item-types')).data
  }

  async function setItemType(catalogItemId: string, tipoSpesa: string, flag?: string | null): Promise<ItemType> {
    return (await api.put<ApiResponse<ItemType>>(`/api/v1/sistema_ts/item-types/${catalogItemId}`, { tipo_spesa: tipoSpesa, flag_tipo_spesa: flag ?? null })).data
  }

  return { fetchSettings, saveSettings, fetchDocuments, fetchForInvoice, retry, processNow, fetchOpposition, setOpposition, fetchItemTypes, setItemType }
}
