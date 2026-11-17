import type { ApiResponse } from '~~/app/types'

export const MANUAL_WHATSAPP_PATH = '/whatsapp-manual'
const base = '/api/v1/whatsapp_manual'

export interface ManualWhatsAppDraft {
  id: string
  patient_name: string | null
  phone: string
  text: string
  created_at: string
  appointment_start_at: string | null
}

export interface ManualWhatsAppTray {
  items: ManualWhatsAppDraft[]
  total: number
  enabled: boolean
}

export function useManualWhatsApp() {
  const api = useApi()
  const options = { errorToast: false }
  return {
    tray: (page: number) => api.get<ApiResponse<ManualWhatsAppTray>>(`${base}/tray`, { ...options, query: { page } }),
    count: () => api.get<ApiResponse<number>>(`${base}/count`, options),
    settings: () => api.get<ApiResponse<{ enabled: boolean }>>(`${base}/settings`, options),
    configure: (enabled: boolean) => api.put(`${base}/settings`, { enabled }, options),
    open: (id: string) => api.post<ApiResponse<string>>(`${base}/tray/${id}/open`, {}, options),
    action: (action: 'mark_sent' | 'dismiss', ids: string[]) =>
      api.post(`${base}/tray/actions`, { action, ids }, options),
    queue: (draft: { patient_id: string, appointment_id?: string, text: string, request_id: string }) =>
      api.post(`${base}/drafts`, draft, options)
  }
}
