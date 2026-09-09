import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface NavSettings {
  enabled: boolean
  environment: 'test' | 'prod'
  tax_number: string | null
  technical_user_login: string | null
  has_password: boolean
  has_signature_key: boolean
  has_exchange_key: boolean
  software_id: string
  software_dev_contact: string | null
  last_nav_response_at: string | null
  next_send_after: string | null
  last_error: string | null
}

export interface NavRecord {
  id: string
  invoice_id: string
  operation: string
  invoice_number: string
  issue_date: string
  gross_amount: string
  state: string
  attempts: number
  transaction_id: string | null
  nav_status: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  sent_at: string | null
  finished_at: string | null
}

export function useNavOnline() {
  const api = useApi()

  async function fetchSettings(): Promise<NavSettings> {
    return (await api.get<ApiResponse<NavSettings>>('/api/v1/nav_online/settings')).data
  }

  async function saveSettings(payload: Record<string, unknown>): Promise<NavSettings> {
    return (await api.put<ApiResponse<NavSettings>>('/api/v1/nav_online/settings', payload, { errorToast: false })).data
  }

  async function testConnection(): Promise<{ success: boolean, error?: string | null }> {
    return (await api.post<ApiResponse<{ success: boolean, error?: string | null }>>('/api/v1/nav_online/settings/test-connection', {}, { errorToast: false })).data
  }

  async function fetchRecords(query: Record<string, string | number | undefined | null>): Promise<PaginatedResponse<NavRecord>> {
    return await api.get<PaginatedResponse<NavRecord>>('/api/v1/nav_online/records', { query })
  }

  async function retryRecord(id: string): Promise<NavRecord> {
    return (await api.post<ApiResponse<NavRecord>>(`/api/v1/nav_online/records/${id}/retry`)).data
  }

  async function processNow(): Promise<Record<string, number>> {
    return (await api.post<ApiResponse<Record<string, number>>>('/api/v1/nav_online/queue/process-now', {})).data
  }

  return { fetchSettings, saveSettings, testConnection, fetchRecords, retryRecord, processNow }
}
